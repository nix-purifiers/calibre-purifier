"""Keep calibre settings writable while rejecting mutable dependency registrations."""

import json
from pathlib import Path


def prepare(state, environment, hooks):
    state = Path(state).resolve()
    environment = Path(environment).resolve()
    config = state / "config"
    config.mkdir(parents=True, exist_ok=True)
    settings = config / "customize.py.json"
    if settings.exists() and json.loads(settings.read_text()).get("plugins"):
        raise ValueError("unlocked calibre plugin registration in the private profile")
    plugins = config / "plugins"
    if plugins.exists():
        for item in plugins.iterdir():
            if (
                item.suffix.lower() in {".zip", ".py", ".pyc", ".so"}
                or item.is_symlink()
            ):
                raise ValueError(
                    f"unlocked calibre plugin code in the private profile: {item}"
                )
    for directory in ["home", "data", "cache", "tmp"]:
        (state / directory).mkdir(exist_ok=True)
    return {
        "CALIBRE_CONFIG_DIRECTORY": str(config),
        "CALIBRE_CACHE_DIRECTORY": str(state / "cache"),
        "CALIBRE_TEMP_DIR": str(state / "tmp"),
        "CALIBRE_PURIFIER_ENVIRONMENT": str(environment),
        "PYTHONPATH": str(hooks),
        "PYTHONNOUSERSITE": "1",
        "XDG_CONFIG_HOME": str(config),
        "XDG_DATA_HOME": str(state / "data"),
        "XDG_CACHE_HOME": str(state / "cache"),
    }
