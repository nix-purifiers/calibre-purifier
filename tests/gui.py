import os
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

p = Path(__file__).resolve().parent
cli = Path(sys.argv[1]).resolve()
sdk = Path(sys.argv[2]).resolve()
xvfb = Path(sys.argv[3]).resolve()
resources = Path(sys.argv[4]).resolve()
source = p.parent
with tempfile.TemporaryDirectory(prefix="calibre-gui-") as temporary:
    root = Path(temporary)
    for name in ["home", "config", "data", "cache", "runtime"]:
        (root / name).mkdir(mode=0o700)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".calibre-purifier", "output"),
    )
    managed = Path(
        subprocess.check_output(
            [cli / "bin/calibre-purifier", "--project", project, "prefetch"], text=True
        ).strip()
    )
    bus = ET.Element("busconfig")
    ET.SubElement(bus, "type").text = "session"
    ET.SubElement(bus, "listen").text = "unix:tmpdir=" + str(root / "runtime")
    ET.SubElement(bus, "auth").text = "EXTERNAL"
    policy = ET.SubElement(bus, "policy", context="default")
    for attribute in ["own", "send_destination", "receive_sender"]:
        ET.SubElement(policy, "allow", {attribute: "*"})
    ET.ElementTree(bus).write(root / "bus.conf", encoding="UTF-8", xml_declaration=True)
    env = os.environ.copy()
    for name in [
        "WAYLAND_DISPLAY",
        "WAYLAND_SOCKET",
        "DBUS_SESSION_BUS_ADDRESS",
        "DBUS_STARTER_ADDRESS",
        "DBUS_STARTER_BUS_TYPE",
        "SESSION_MANAGER",
        "AT_SPI_BUS_ADDRESS",
        "QT_QPA_PLATFORMTHEME",
        "XDG_ACTIVATION_TOKEN",
        "DESKTOP_STARTUP_ID",
        "INTERACTIVE_HTML_BOM_CLI_MODE",
    ]:
        env.pop(name, None)
    env.update(
        HOME=str(root / "home"),
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_DATA_HOME=str(root / "data"),
        XDG_CACHE_HOME=str(root / "cache"),
        XDG_RUNTIME_DIR=str(root / "runtime"),
        QT_QPA_PLATFORM="xcb",
        GDK_BACKEND="x11",
        GTK_USE_PORTAL="0",
        QTWEBENGINE_DISABLE_SANDBOX="1",
        NO_AT_BRIDGE="1",
        LIBGL_ALWAYS_SOFTWARE="1",
        DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "no-system-bus"),
        FONTCONFIG_FILE=str(resources / "fonts.conf"),
        CALIBRE_PROOF_JSON=str(root / "gui.json"),
        CALIBRE_PROOF_LIBRARY=str(root / "library"),
        CALIBRE_CONFIG_DIRECTORY=str(root / "config"),
        CALIBRE_PURIFIER_ENVIRONMENT=str(managed),
        PYTHONPATH=str(p / "gui-hooks") + ":" + str(source / "native/hooks"),
        PYTHONNOUSERSITE="1",
    )
    subprocess.run(
        [sdk / "bin/calibre-debug", "--exec-file", p / "seed_gui.py"],
        env=env,
        check=True,
    )
    args = [
        str(xvfb / "bin/xvfb-run"),
        "-a",
        str(resources / "bin/dbus-run-session"),
        "--dbus-daemon=" + str(resources / "bin/dbus-daemon"),
        "--config-file=" + str(root / "bus.conf"),
        "--",
        str(sdk / "bin/calibre"),
        "--no-update-check",
        "--with-library",
        str(root / "library"),
    ]
    with (root / "gui-test.log").open("w") as log:
        process = subprocess.Popen(
            args, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            status = process.wait(timeout=45)
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        assert status == 0, (root / "gui-test.log").read_text()
    print((root / "gui.json").read_text())
