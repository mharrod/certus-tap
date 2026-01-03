#!/usr/bin/env python3
"""Update the build/security-light/latest symlink (or copy) after a Dagger run."""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Point build/security-light/latest at the newest bundle directory.")
    parser.add_argument(
        "root",
        nargs="?",
        default="build/security-light",
        help="Root directory that contains individual bundle folders (default: %(default)s)",
    )
    return parser.parse_args()


def _pick_latest(root: pathlib.Path) -> pathlib.Path | None:
    candidates: list[pathlib.Path] = []
    for entry in root.iterdir():
        if entry.name == "latest":
            continue
        if entry.is_dir():
            candidates.append(entry)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _promote(root: pathlib.Path, target: pathlib.Path) -> None:
    latest = root / "latest"
    if latest.exists() or latest.is_symlink():
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        else:
            latest.unlink()
    try:
        latest.symlink_to(target, target_is_directory=True)
    except OSError:
        shutil.copytree(target, latest, dirs_exist_ok=True)


def main() -> None:
    args = _parse_args()
    root = pathlib.Path(args.root).expanduser()
    if not root.exists():
        sys.exit(f"No export root found at: {root}")
    target = _pick_latest(root)
    if target is None:
        sys.exit(f"No bundle directories detected under {root}")
    _promote(root, target)


if __name__ == "__main__":
    main()
