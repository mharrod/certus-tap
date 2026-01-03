"""Artifact helpers shared across the security module."""

from __future__ import annotations

from pathlib import Path


def ensure_export_dir(path: str | Path) -> Path:
    """Ensure export directory exists and return its path.

    Args:
        path: Directory path to ensure exists

    Returns:
        Resolved Path object
    """
    export_path = Path(path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.mkdir(parents=True, exist_ok=True)
    return export_path
