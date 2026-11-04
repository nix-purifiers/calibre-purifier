from calibre.utils.ipc import gui_socket_address
from calibre.utils.lock import create_single_instance_mutex

assert create_single_instance_mutex("db") is None, "database safety mutex was bypassed"
gui = create_single_instance_mutex("GUI")
assert gui, "locked GUI would reuse the unwrapped GUI namespace"
gui()
assert "purifier-" in gui_socket_address()
print("native database mutex preserved; GUI generation namespace isolated")
