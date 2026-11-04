"""Use calibre's catalog, compatibility checks, ZIP loader and installer."""

import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from calibre.customize import ui
from calibre.gui2.dialogs import plugin_updater


def catalog(request):
    from compression import bz2

    raw = Path(request["feed"]).read_bytes()
    metadata = json.loads(bz2.decompress(raw))
    original_fetch = plugin_updater.get_https_resource_securely
    plugin_updater.get_https_resource_securely = lambda url: (
        raw if url == plugin_updater.INDEX_URL else original_fetch(url)
    )
    available = {
        plugin.name: plugin
        for plugin in plugin_updater.read_available_plugins(raise_error=True)
    }
    selected = []
    for name in request["selection"]["plugins"]:
        plugin = available.get(name)
        if not plugin or not plugin.is_valid_to_install():
            raise ValueError(f"no compatible calibre plugin: {name}")
        record = next(
            value for value in metadata.values() if value["index_name"] == name
        )
        filename = Path(urlsplit(plugin.zip_url).path).name
        if not filename.endswith(".zip"):
            raise ValueError("native catalog returned an unsupported archive filename")
        selected.append(
            {
                "path": filename,
                "url": plugin.zip_url,
                "metadata": record,
                "calibre": {
                    "name": plugin.qname,
                    "index_name": plugin.name,
                    "version": list(plugin.available_version),
                },
            }
        )
    return selected


def install(request):
    loaded = []
    for entry in request["entries"]:
        plugin = ui.add_plugin(entry["archive"])
        if (
            plugin.name != entry["calibre"]["name"]
            or list(plugin.version) != entry["calibre"]["version"]
        ):
            raise ValueError(
                f"native archive identity/version changed: {entry['path']}"
            )
        if Path(plugin.name).name != plugin.name or plugin.name in {"", ".", ".."}:
            raise ValueError("unsupported native plugin filename")
        loaded.append((entry, plugin))
    if len({plugin.name for _, plugin in loaded}) != len(loaded):
        raise ValueError("selected archives have conflicting native plugin names")
    for entry, plugin in loaded:
        status = plugin_updater.DisplayPlugin(request["catalog"][entry["path"]])
        plugin_updater.get_installed_plugin_status(status)
        if status.uninstall_plugins:
            raise ValueError(
                f"selected plugins conflict under native uninstall rules: {status.uninstall_plugins}"
            )
    destination = Path(request["destination"])
    (destination / "plugins").mkdir(parents=True, exist_ok=True)
    manifest = []
    for entry, plugin in loaded:
        filename = plugin.name + ".zip"
        shutil.copyfile(
            Path(ui.plugin_dir) / filename, destination / "plugins" / filename
        )
        manifest.append(
            {
                "name": plugin.name,
                "version": list(plugin.version),
                "minimum": list(plugin.minimum_calibre_version),
                "platforms": list(plugin.supported_platforms),
            }
        )
    (destination / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n"
    )
    return manifest


request = json.loads(Path(os.environ["CALIBRE_PURIFIER_REQUEST"]).read_text())
result = catalog(request) if request["action"] == "catalog" else install(request)
Path(os.environ["CALIBRE_PURIFIER_RESPONSE"]).write_text(
    json.dumps(result, sort_keys=True) + "\n"
)
