import os
import traceback

try:
    if os.environ.get("CALIBRE_PURIFIER_ENVIRONMENT"):
        from calibre_purifier_guard import install

        install()
except BaseException:
    os.write(2, traceback.format_exc().encode())
    os._exit(1)
