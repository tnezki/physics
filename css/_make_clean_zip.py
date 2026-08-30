#!/usr/bin/env python3
"""
~make_clean_zip.py

Create a clean ZIP archive from a folder while excluding common macOS,
Python, editor, and temporary junk.

Usage:
    python3 ~make_clean_zip.py /path/to/folder
    python3 ~make_clean_zip.py /path/to/folder /path/to/output.zip

If no output path is given, the ZIP is created beside the folder using:
    <folder_name>.zip
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

EXCLUDED_DIR_NAMES = {"__MACOSX", "__pycache__", ".git", ".svn", ".hg"}
EXCLUDED_FILE_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".temp", ".swp", ".swo"}
EXCLUDED_PREFIXES = {"._", "~$"}


def should_exclude(path: Path, source_root: Path, output_zip: Path) -> bool:
    try:
        if path.resolve() == output_zip.resolve():
            return True
    except FileNotFoundError:
        pass
    rel_parts = path.relative_to(source_root).parts
    if any(part in EXCLUDED_DIR_NAMES for part in rel_parts[:-1]):
        return True
    if path.is_dir() and path.name in EXCLUDED_DIR_NAMES:
        return True
    if path.name in EXCLUDED_FILE_NAMES:
        return True
    if any(path.name.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return False


def make_clean_zip(source_folder: Path, output_zip: Path) -> tuple[int, int]:
    source_folder = source_folder.expanduser().resolve()
    output_zip = output_zip.expanduser().resolve()
    if not source_folder.exists():
        raise FileNotFoundError(f"Source folder does not exist: {source_folder}")
    if not source_folder.is_dir():
        raise NotADirectoryError(f"Source path is not a folder: {source_folder}")
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    included = 0
    skipped = 0
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(source_folder.rglob("*")):
            if should_exclude(path, source_folder, output_zip):
                skipped += 1
                continue
            if path.is_file():
                arcname = Path(source_folder.name) / path.relative_to(source_folder)
                zf.write(path, arcname)
                included += 1
    with zipfile.ZipFile(output_zip, "r") as zf:
        bad_file = zf.testzip()
        if bad_file is not None:
            raise RuntimeError(f"ZIP integrity test failed at: {bad_file}")
    return included, skipped


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print("Usage:\n  python3 ~make_clean_zip.py /path/to/folder\n  python3 ~make_clean_zip.py /path/to/folder /path/to/output.zip")
        sys.exit(2)
    source = Path(sys.argv[1])
    if len(sys.argv) == 3:
        output = Path(sys.argv[2])
        if output.suffix.lower() != ".zip":
            output = output.with_suffix(".zip")
    else:
        source_expanded = source.expanduser().resolve()
        output = source_expanded.parent / f"{source_expanded.name}.zip"
    try:
        included, skipped = make_clean_zip(source, output)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    print(f"Created: {output.resolve()}")
    print(f"Included files: {included}")
    print(f"Skipped junk/temp paths: {skipped}")
    print("ZIP integrity: PASS")


if __name__ == "__main__":
    main()
