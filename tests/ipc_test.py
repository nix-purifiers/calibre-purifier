import os
import subprocess

# Never bind desktop-global calibre mutex names in the host network namespace.
assert os.readlink("/proc/self/ns/net") != os.environ["CALIBRE_PROOF_HOST_NETNS"]
base = os.environ.copy()
base.pop("PYTHONPATH", None)
process = subprocess.Popen(
    [
        os.environ["CALIBRE_PROOF_DEBUG"],
        "--exec-file",
        os.environ["CALIBRE_PROOF_HOLDER"],
    ],
    env=base,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)
try:
    assert process.stdout.readline().strip() == "ready"
    guarded = base | {"PYTHONPATH": os.environ["CALIBRE_PROOF_HOOKS"]}
    subprocess.run(
        [
            os.environ["CALIBRE_PROOF_DEBUG"],
            "--exec-file",
            os.environ["CALIBRE_PROOF_CHECK"],
        ],
        env=guarded,
        check=True,
    )
finally:
    process.communicate("x", timeout=10)
assert process.returncode == 0
