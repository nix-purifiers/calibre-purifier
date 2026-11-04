import os
import subprocess
from pathlib import Path

from calibre_purifier_prepare import prepare

state = Path(os.environ["TMPDIR"]) / "calibre-state"
env = os.environ.copy() | prepare(
    state,
    os.environ["CALIBRE_PURIFIER_ENVIRONMENT"],
    os.environ["CALIBRE_PURIFIER_HOOKS"],
)
env.update(HOME=str(state / "home"), QT_QPA_PLATFORM="offscreen")
subprocess.run(
    [
        os.environ["CALIBRE_PURIFIER_COMMAND_BINARY"],
        "--exec-file",
        os.environ["CALIBRE_PURIFIER_SCRIPT"],
    ],
    env=env,
    check=True,
)
