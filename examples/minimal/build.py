"""Merge two books with the locked plugin and export reproducible plain text."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

source = Path(__file__).resolve().parent
output = Path(os.environ.get("CALIBRE_PURIFIER_OUTPUT", "output")).resolve()
output.mkdir(parents=True, exist_ok=True)


def call(name, *arguments):
    subprocess.run(
        [str(Path(sys.executables_location) / name), *map(str, arguments)], check=True
    )


with tempfile.TemporaryDirectory(prefix="calibre-books-") as temporary:
    root = Path(temporary)
    call(
        "ebook-convert",
        source / "first.html",
        root / "one.epub",
        "--title",
        "First",
        "--authors",
        "Purifier",
    )
    call(
        "ebook-convert",
        source / "second.html",
        root / "two.epub",
        "--title",
        "Second",
        "--authors",
        "Purifier",
    )
    call(
        "calibre-debug",
        "--run-plugin",
        "EpubMerge",
        "--",
        "-o",
        root / "merged.epub",
        root / "one.epub",
        root / "two.epub",
    )
    call(
        "ebook-convert",
        root / "merged.epub",
        output / "combined.txt",
        "--txt-output-formatting",
        "plain",
    )
