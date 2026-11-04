"""CALIBRE's normal application workflow with a frozen native extension profile."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def public_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("CALIBRE addon repositories must use public HTTPS URLs")
    return url


def selection(project):
    value = json.loads((project / "calibre-purifier.json").read_text())
    if set(value) != {"plugins"} or not isinstance(value["plugins"], list):
        raise ValueError("calibre-purifier.json needs a plugins list")
    if any(
        not isinstance(name, str)
        or not name.strip()
        or any(c in name for c in "\r\n\0")
        for name in value["plugins"]
    ):
        raise ValueError("invalid calibre catalog plugin name")
    if len(set(value["plugins"])) != len(value["plugins"]):
        raise ValueError("duplicate calibre plugin")
    return value


def project_path(explicit):
    if explicit:
        return Path(explicit).resolve()
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "calibre-purifier.json").exists() or (
            parent / "calibre-purifier.lock.json"
        ).exists():
            return parent
    return current


def validate(project, lock):
    data = json.loads(lock.read_text())
    if data.get("version") != 1 or data.get("purifier") != "calibre":
        raise ValueError("unsupported CALIBRE lock")
    if data.get("sdk") != os.environ["CALIBRE_PURIFIER_SDK"]:
        raise ValueError("CALIBRE SDK changed; run calibre-purifier lock --update")
    if data.get("selection") != selection(project):
        raise ValueError(
            "extension selection changed; run calibre-purifier lock --update"
        )
    return data


def realize(project, lock, target="environment", out_link=None):
    args = [
        "nix",
        "build",
        "--impure",
        "--file",
        os.environ["CALIBRE_PURIFIER_REALIZE"],
        "--argstr",
        "projectPath",
        str(project),
        "--argstr",
        "lockPath",
        str(lock),
        "--argstr",
        "target",
        target,
        "--json",
    ]
    args += ["--out-link", str(out_link)] if out_link else ["--no-link"]
    result = run(args, stdout=subprocess.PIPE, text=True)
    return Path(json.loads(result.stdout)[0]["outputs"]["out"])


def sdk_env(env):
    original = Path(os.environ["CALIBRE_PURIFIER_ORIGINAL"])
    env.pop("CALIBRE_DEVELOP_FROM", None)
    env.update(
        CALIBRE_PYTHON_PATH=str(original / "lib/calibre"),
        CALIBRE_RESOURCES_PATH=str(original / "share/calibre"),
        CALIBRE_EXTENSIONS_PATH=str(original / "lib/calibre/calibre/plugins"),
        CALIBRE_EXECUTABLES_PATH=str(original / "bin"),
    )
    return env


def native_operation(root, request):
    request_file = root / "request.json"
    response = root / "response.json"
    request_file.write_text(json.dumps(request))
    response.unlink(missing_ok=True)
    env = sdk_env(os.environ.copy())
    env.pop("CALIBRE_PURIFIER_ENVIRONMENT", None)
    env.pop("PYTHONPATH", None)
    for name, directory in {
        "HOME": "home",
        "XDG_CONFIG_HOME": "config",
        "XDG_DATA_HOME": "data",
        "XDG_CACHE_HOME": "cache",
    }.items():
        path = root / directory
        path.mkdir(exist_ok=True)
        env[name] = str(path)
    env.update(
        CALIBRE_CONFIG_DIRECTORY=str(root / "calibre"),
        PYTHONNOUSERSITE="1",
        QT_QPA_PLATFORM="offscreen",
        CALIBRE_PURIFIER_REQUEST=str(request_file),
        CALIBRE_PURIFIER_RESPONSE=str(response),
    )
    executable = Path(os.environ["CALIBRE_PURIFIER_ORIGINAL"]) / "bin/calibre-debug"
    run(
        [
            str(executable),
            "--exec-file",
            str(
                Path(os.environ["CALIBRE_PURIFIER_NATIVE"])
                / "calibre_purifier_native.py"
            ),
        ],
        env=env,
        stdout=sys.stderr,
    )
    return json.loads(response.read_text())


def prefetch(url):
    env = os.environ.copy()
    env["NIX_SSL_CERT_FILE"] = str(
        Path(os.environ["CALIBRE_PURIFIER_ORIGINAL"])
        / "share/calibre/calibre-ebook-root-CA.crt"
    )
    return json.loads(
        run(
            ["nix", "store", "prefetch-file", "--json", public_url(url)],
            env=env,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
    )


def capture(project, lock):
    requested = selection(project)
    with tempfile.TemporaryDirectory(prefix="calibre-purifier-") as temporary:
        root = Path(temporary)
        feed = (
            prefetch("https://code.calibre-ebook.com/plugins/plugins.json.bz2")
            if requested["plugins"]
            else None
        )
        selected = (
            native_operation(
                root,
                {
                    "action": "catalog",
                    "feed": feed["storePath"],
                    "selection": requested,
                },
            )
            if feed
            else []
        )
        entries = []
        catalog = {}
        for item in selected:
            fetched = prefetch(item["url"])
            entries.append(
                {
                    "path": item["path"],
                    "url": item["url"],
                    "mirrors": [],
                    "hash": fetched["hash"],
                    "calibre": item["calibre"],
                }
            )
            catalog[item["path"]] = item["metadata"]
        data = {
            "version": 1,
            "purifier": "calibre",
            "sdk": os.environ["CALIBRE_PURIFIER_SDK"],
            "selection": requested,
            "native": {"catalog": catalog},
            "entries": entries,
        }
        candidate = root / "calibre-purifier.lock.json"
        candidate.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        realize(project, candidate)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=lock.parent, delete=False
        ) as output:
            output.write(candidate.read_text())
            pending = Path(output.name)
        try:
            os.replace(pending, lock)
        finally:
            pending.unlink(missing_ok=True)


def native_exec(project, lock, arguments, command="calibre-debug"):
    executable = Path(os.environ["CALIBRE_PURIFIER_ORIGINAL"]) / "bin" / command
    if not lock.exists():
        print(
            "warning: no calibre purifier lock; using ordinary, impure plugin resolution",
            file=sys.stderr,
        )
        env = os.environ.copy()
        env.pop("CALIBRE_PURIFIER_ENVIRONMENT", None)
        os.execve(executable, [str(executable), *arguments], env)
    validate(project, lock)
    state = project / ".calibre-purifier"
    state.mkdir(exist_ok=True)
    environment = realize(project, lock, out_link=state / "environment")
    sys.path.insert(0, os.environ["CALIBRE_PURIFIER_NATIVE"])
    from calibre_purifier_prepare import prepare

    env = sdk_env(
        os.environ.copy()
        | prepare(state, environment, os.environ["CALIBRE_PURIFIER_HOOKS"])
    )
    env.update(CALIBRE_PURIFIER_PROJECT=str(project), CALIBRE_PURIFIER_LOCK=str(lock))
    os.execve(executable, [str(executable), *arguments], env)


def main():
    if os.environ.get("CALIBRE_PURIFIER_COMMAND") not in {None, "calibre-purifier"}:
        project = project_path(os.environ.get("CALIBRE_PURIFIER_PROJECT"))
        lock = Path(
            os.environ.get(
                "CALIBRE_PURIFIER_LOCK", project / "calibre-purifier.lock.json"
            )
        ).resolve()
        native_exec(project, lock, sys.argv[1:], os.environ["CALIBRE_PURIFIER_COMMAND"])
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--lock")
    sub = parser.add_subparsers(dest="action", required=True)
    lock_parser = sub.add_parser("lock")
    lock_parser.add_argument("--update", action="store_true")
    sub.add_parser("prefetch")
    for name in ["build", "bundle"]:
        sub.add_parser(name)
    publish = sub.add_parser("publish")
    publish.add_argument("--tag", required=True)
    execute = sub.add_parser("exec")
    execute.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    project = project_path(args.project or os.environ.get("CALIBRE_PURIFIER_PROJECT"))
    lock = Path(
        args.lock
        or os.environ.get(
            "CALIBRE_PURIFIER_LOCK", project / "calibre-purifier.lock.json"
        )
    ).resolve()
    if args.action == "lock" and args.update:
        capture(project, lock)
        return
    if args.action == "exec":
        arguments = (
            args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        )
        native_exec(project, lock, arguments)
        return
    validate(project, lock)
    if args.action == "lock":
        realize(project, lock)
    elif args.action == "prefetch":
        print(realize(project, lock))
    elif args.action in {"build", "bundle"}:
        print(
            realize(project, lock, "project" if args.action == "build" else "release")
        )
    elif args.action == "publish":
        release = realize(project, lock, "release")
        run(
            [
                os.environ.get("CALIBRE_PURIFIER_GH", "gh"),
                "release",
                "upload",
                args.tag,
                str(release / "calibre-project.tar.gz"),
                "--clobber",
            ]
        )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"calibre-purifier: {error}", file=sys.stderr)
        sys.exit(1)
