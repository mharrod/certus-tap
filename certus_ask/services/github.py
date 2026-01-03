from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path

from certus_ask.core.config import settings

GIT_EXTRA_MESSAGE = "Git integration requires the 'git' extra. Install with: pip install 'certus-tap[git]'"

# Import guards for optional git integration dependencies
try:
    from git import Repo
except ImportError as exc:
    raise ImportError(GIT_EXTRA_MESSAGE) from exc

DEFAULT_INCLUDE_GLOBS = [
    "**/*.md",
    "**/*.mdx",
    "**/*.rst",
    "**/*.txt",
    "**/*.py",
    "**/*.js",
    "**/*.ts",
    "**/*.java",
    "**/*.go",
    "**/*.rb",
    "**/*.cs",
]
DEFAULT_EXCLUDE_GLOBS = [
    "**/.git/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/node_modules/**",
    "**/*.min.js",
]


class GitRepository:
    """Context manager for cloning and cleaning up temporary repositories."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> GitRepository:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.cleanup()


def clone_repository(repo_url: str, branch: str | None = None) -> GitRepository:
    tmp_dir = Path(tempfile.mkdtemp(prefix="certus-git-"))
    clone_url = _inject_token(repo_url)
    clone_kwargs = {"depth": 1}
    if branch:
        clone_kwargs["branch"] = branch
    repo = Repo.clone_from(clone_url, tmp_dir, **clone_kwargs)  # type: ignore[arg-type]
    # If branch was None, GitPython checks out default branch automatically.
    # Ensure submodules are discarded for simplicity.
    if repo.submodules:
        repo.git.submodule("deinit", "--all")
    return GitRepository(tmp_dir)


def iter_repository_files(
    repo_path: Path,
    include_globs: Iterable[str] | None = None,
    exclude_globs: Iterable[str] | None = None,
    max_file_size_kb: int = 256,
) -> list[Path]:
    includes = list(include_globs or DEFAULT_INCLUDE_GLOBS)
    excludes = list(exclude_globs or DEFAULT_EXCLUDE_GLOBS)
    max_bytes = max(1, max_file_size_kb) * 1024
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_path)
        if excludes and any(rel.match(pattern) for pattern in excludes):
            continue
        if includes and not any(rel.match(pattern) for pattern in includes):
            continue
        try:
            if path.stat().st_size > max_bytes:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def _inject_token(repo_url: str) -> str:
    token = settings.github_token
    if not token or not repo_url.startswith("https://"):
        return repo_url
    # Insert token after protocol. Use netloc-safe format.
    protocol, rest = repo_url.split("://", 1)
    if "@" in rest:
        return repo_url  # assume token already embedded
    return f"{protocol}://{token}@{rest}"
