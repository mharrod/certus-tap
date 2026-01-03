"""Shared constants for the security Dagger module."""

from __future__ import annotations

from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_EXPORT_DIR = Path.cwd() / "build" / "security-light"
ARTIFACT_ROOT = "/tmp/security-light"
SOURCE_MOUNT = "/src"
ASSETS_MOUNT = "/privacy-pack"
SEMGRP_CONFIG = MODULE_ROOT / "config" / "semgrep-baseline.yml"
PRIVACY_SAMPLE_DIR = MODULE_ROOT / "assets" / "privacy-pack"

EXCLUDES = [
    ".git",
    ".venv",
    "venv",
    "env",
    "test_venv",  # Exclude test virtual environments
    "dist",
    "site",
    "node_modules",
    "draft",
    "htmlcov",
    "__pycache__",
    "build",  # Exclude entire build directory
    "security-results",  # Exclude scan results from previous runs
    "samples",  # Exclude sample data
    "certus-assurance-artifacts",  # Exclude test artifacts
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "*.egg-info",
    ".tox",
    ".nox",
    "*.so",
    "*.dylib",
    ".DS_Store",
    "*.pyc",
    ".coverage",
    "coverage.xml",
]

SUMMARY_FILE = "summary.json"
