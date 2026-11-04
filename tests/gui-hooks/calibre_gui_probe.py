import importlib.abc
import importlib.machinery
import json
import os
import sys
import traceback
from pathlib import Path


def install():
    class Loader:
        def __init__(self, original):
            self.original = original

        def create_module(self, spec):
            return self.original.create_module(spec)

        def __getattr__(self, name):
            return getattr(self.original, name)

        def exec_module(self, module):
            self.original.exec_module(module)
            if module.__name__ == "calibre.gui2.main":
                # This proof uses a fresh private library; isolate its DB mutex
                # from desktop instances as well. Production retains the DB mutex.
                from calibre.utils import lock

                original = lock.create_single_instance_mutex
                token = Path(os.environ["CALIBRE_CONFIG_DIRECTORY"]).parent.name
                lock.create_single_instance_mutex = lambda name, per_user=True: (
                    original(name + "-private-test-" + token, per_user)
                )
            elif module.__name__ == "calibre.gui2.ui":
                original = module.Main.initialize

                def initialize(self, *args, **kwargs):
                    result = original(self, *args, **kwargs)
                    try:
                        from calibre.customize import PluginInstallationType, ui
                        from calibre.utils.ipc import gui_socket_address
                        from qt.core import QTimer

                        action = self.iactions["EpubMerge"]
                        assert action.__class__.__name__ == "EpubMergePlugin"
                        assert action.qaction is not None
                        assert (
                            Path(action.plugin_path)
                            .resolve()
                            .is_relative_to("/nix/store")
                        )
                        assert action.installation_type == PluginInstallationType.SYSTEM
                        assert "purifier-" in gui_socket_address()
                        try:
                            ui.add_plugin(None)
                        except RuntimeError as error:
                            assert "locked" in str(error)
                        else:
                            raise AssertionError("GUI plugin manager was not frozen")
                        Path(os.environ["CALIBRE_PROOF_JSON"]).write_text(
                            json.dumps(
                                {
                                    "action": action.name,
                                    "path": action.plugin_path,
                                    "socket": gui_socket_address(),
                                },
                                indent=2,
                            )
                        )
                        QTimer.singleShot(0, lambda: os._exit(0))
                    except BaseException:
                        os.write(2, traceback.format_exc().encode())
                        os._exit(17)
                    return result

                module.Main.initialize = initialize

    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname in {"calibre.gui2.main", "calibre.gui2.ui"}:
                spec = importlib.machinery.PathFinder.find_spec(fullname, path)
                spec.loader = Loader(spec.loader)
                return spec

    sys.meta_path.insert(0, Finder())
