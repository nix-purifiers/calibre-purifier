import os
import traceback

try:
    import calibre_purifier_guard

    calibre_purifier_guard.install()
    import calibre_gui_probe

    calibre_gui_probe.install()
except BaseException:
    os.write(2, traceback.format_exc().encode())
    os._exit(1)
