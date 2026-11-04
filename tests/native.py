"""Exercise native plugin loading, workers, preferences and source edits."""

import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

cli = Path(sys.argv[1]).resolve() / "bin"
original = Path(sys.argv[2]).resolve() / "bin/calibre-debug"
source = Path(__file__).resolve().parents[1]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"project networking works")

    def log_message(self, *args):
        pass


with tempfile.TemporaryDirectory(prefix="calibre-native-") as temporary:
    root = Path(temporary)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".calibre-purifier", "output"),
    )
    env = os.environ.copy() | {
        "HOME": str(root),
        "CALIBRE_PURIFIER_PROJECT": str(project),
        "CALIBRE_PURIFIER_OUTPUT": str(project / "output"),
        "QT_QPA_PLATFORM": "offscreen",
    }
    for name in [
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "WAYLAND_SOCKET",
        "DBUS_SESSION_BUS_ADDRESS",
    ]:
        env.pop(name, None)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env["CALIBRE_TEST_URL"] = f"http://127.0.0.1:{server.server_port}/"
    script = project / "build.py"
    script.write_text(
        script.read_text()
        + """
import json, stat, urllib.request
with urllib.request.urlopen(os.environ["CALIBRE_TEST_URL"]) as response:
    assert response.read() == b"project networking works"
from calibre.customize import ui, PluginInstallationType
from calibre.ebooks.metadata.sources import update
from calibre.utils.config import JSONConfig
from calibre.utils.ipc.simple_worker import fork_job
plugin = ui.find_plugin('EpubMerge')
assert plugin.installation_type == PluginInstallationType.SYSTEM
assert Path(plugin.plugin_path).resolve().is_relative_to('/nix/store')
assert not (Path(plugin.plugin_path).stat().st_mode & stat.S_IWUSR)
for method in [ui.add_plugin, ui.remove_plugin]:
    try:
        method(None)
    except RuntimeError as error:
        assert 'locked' in str(error)
    else:
        raise AssertionError('mutable installer still enabled')
marker = output / 'metadata-code-ran'
update.cache['malicious-source'] = f'from pathlib import Path; Path({str(marker)!r}).touch()'
update.patch_plugins()
assert not update.update_sources(wait_for_completion=True)
assert not marker.exists()
ui.disable_plugin('EpubMerge')
assert ui.is_disabled('EpubMerge')
ui.enable_plugin('EpubMerge')
settings = JSONConfig('plugins/purifier-test')
settings['counter'] = settings.get('counter', 0) + 1
worker = fork_job('calibre.customize.ui', 'get_system_plugins', timeout=30)['result']
assert Path(worker['EpubMerge']).resolve().is_relative_to('/nix/store')
(output / 'proof.json').write_text(json.dumps({'counter': settings['counter']}))
"""
    )

    def call(*args):
        return subprocess.run(
            [cli / "calibre-debug", *args],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    first = project / "first.html"
    text = first.read_text()
    lock = project / "calibre-purifier.lock.json"
    locked = lock.read_bytes()
    hashes = []
    for counter, value in enumerate(["42", "43", "42"], 1):
        first.write_text(text.replace("42", value))
        result = call("--exec-file", script)
        assert result.returncode == 0, result.stdout + result.stderr
        output = project / "output/combined.txt"
        assert value in output.read_text()
        hashes.append(hashlib.sha256(output.read_bytes()).hexdigest())
        assert (
            json.loads((project / "output/proof.json").read_text())["counter"]
            == counter
        )
        assert lock.read_bytes() == locked
    server.shutdown()
    server.server_close()
    assert hashes[0] != hashes[1] and hashes[0] == hashes[2]
    poison = project / ".calibre-purifier/config/plugins/ambient.zip"
    poison.write_bytes(b"ambient code")
    result = call("--version")
    assert result.returncode and "unlocked calibre plugin code" in result.stderr
    poison.unlink()
    (project / "calibre-purifier.json").write_text('{"plugins": []}')
    result = call("--version")
    assert result.returncode and "selection changed" in result.stderr
    lock.unlink()
    for arguments in [["--version"], ["--unknown-purifier-command"]]:
        expected = subprocess.run(
            [original, *arguments],
            cwd=project,
            env=env,
            capture_output=True,
            check=False,
        )
        actual = subprocess.run(
            [cli / "calibre-debug", *arguments],
            check=False,
            cwd=project,
            env=env,
            capture_output=True,
        )
        assert actual.returncode == expected.returncode
        assert actual.stdout == expected.stdout
        assert actual.stderr == (
            b"warning: no calibre purifier lock; using ordinary, impure plugin resolution\n"
            + expected.stderr
        )
print(
    "calibre native source, preferences, worker, immutable code and fallback checks passed"
)
