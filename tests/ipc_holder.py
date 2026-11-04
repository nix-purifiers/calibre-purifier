import sys

from calibre.utils.lock import create_single_instance_mutex

database = create_single_instance_mutex("db")
gui = create_single_instance_mutex("GUI")
assert database and gui
print("ready", flush=True)
try:
    sys.stdin.read(1)
finally:
    gui()
    database()
