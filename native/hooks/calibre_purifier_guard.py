import hashlib
import importlib.abc
import importlib.machinery
import json
import os
import sys
import traceback
from pathlib import Path


def frozen(*args, **kwargs):
    raise RuntimeError("calibre plugins are locked; run calibre-purifier lock --update")


def install():
    environment = Path(os.environ["CALIBRE_PURIFIER_ENVIRONMENT"]).resolve()
    expected = json.loads((environment / "manifest.json").read_text())
    identity = hashlib.sha256(
        (
            str(Path(os.environ["CALIBRE_CONFIG_DIRECTORY"]).resolve())
            + "\0"
            + str(environment)
        ).encode()
    ).hexdigest()[:16]

    def freeze_ui(namespace):
        original_config = namespace["config"]

        class Config:
            def __getitem__(self, key):
                return {} if key == "plugins" else original_config[key]

            def __setitem__(self, key, value):
                if key == "plugins" and value:
                    frozen()
                original_config[key] = value

            def __getattr__(self, key):
                return getattr(original_config, key)

            def get(self, key):
                return self[key]

        namespace["config"] = Config()
        namespace["add_plugin"] = namespace["remove_plugin"] = frozen
        original_load = namespace["load_plugin"]

        def load(path):
            if not Path(path).resolve().is_relative_to(environment / "plugins"):
                frozen()
            return original_load(path)

        namespace["load_plugin"] = load
        original_initialize = namespace["initialize_plugins"]

        def initialize(*args, **kwargs):
            original_initialize(*args, **kwargs)
            for entry in expected:
                plugin = namespace["find_plugin"](entry["name"])
                if (
                    not plugin
                    or tuple(plugin.version) != tuple(entry["version"])
                    or not Path(plugin.plugin_path)
                    .resolve()
                    .is_relative_to(environment / "plugins")
                ):
                    os.write(2, b"locked calibre plugin failed native initialization\n")
                    os._exit(1)

        namespace["initialize_plugins"] = initialize

    class Loader:
        def __init__(self, original):
            self.original = original

        def create_module(self, spec):
            return self.original.create_module(spec)

        def __getattr__(self, name):
            return getattr(self.original, name)

        def exec_module(self, module):
            try:
                if module.__name__ == "calibre.customize.ui":
                    source = self.original.get_source(module.__name__)
                    marker = "\ninitialize_plugins()\n"
                    assert source.count(marker) == 1
                    module.__dict__["_calibre_purifier_freeze"] = freeze_ui
                    source = source.replace(
                        marker,
                        "\n_calibre_purifier_freeze(globals())\ninitialize_plugins()\n",
                    )
                    exec(compile(source, module.__file__, "exec"), module.__dict__)
                else:
                    self.original.exec_module(module)
                if module.__name__ == "calibre.constants":
                    module.system_plugins_loc = str(environment / "plugins")
                elif module.__name__ == "calibre.ebooks.metadata.sources.update":
                    module.patch_plugins = lambda: None
                    module.update_sources = lambda *args, **kwargs: False
                    module.load_plugin = module.patch_search_engines = module.main = (
                        frozen
                    )
                elif module.__name__ == "calibre.utils.ipc":
                    original = module.socket_address
                    module.socket_address = lambda which: original(
                        which + "-purifier-" + identity
                    )
                elif module.__name__ == "calibre.utils.lock":
                    original = module.create_single_instance_mutex

                    def mutex(name, per_user=True):
                        if name in {"GUI", "calibre_viewer", "calibre_cyoa"}:
                            name += "-purifier-" + identity
                        return original(name, per_user)

                    module.create_single_instance_mutex = mutex
            except BaseException:
                os.write(2, traceback.format_exc().encode())
                os._exit(1)

    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname in {
                "calibre.constants",
                "calibre.customize.ui",
                "calibre.ebooks.metadata.sources.update",
                "calibre.utils.ipc",
                "calibre.utils.lock",
            }:
                spec = importlib.machinery.PathFinder.find_spec(fullname, path)
                spec.loader = Loader(spec.loader)
                return spec

    sys.meta_path.insert(0, Finder())
