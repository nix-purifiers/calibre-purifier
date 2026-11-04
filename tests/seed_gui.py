import os

from calibre.db.legacy import LibraryDatabase
from calibre.utils.config import dynamic

dynamic.set("welcome_wizard_was_run", True)
db = LibraryDatabase(os.environ["CALIBRE_PROOF_LIBRARY"])
db.close()
