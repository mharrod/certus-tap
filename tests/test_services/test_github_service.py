from pathlib import Path
from types import SimpleNamespace

import pytest

from certus_ask.services import github

pytestmark = pytest.mark.integration


def test_inject_token_embeds_credentials(monkeypatch):
    """HTTPS URLs should receive a token prefix when configured."""
    monkeypatch.setattr("certus_ask.services.github.settings", SimpleNamespace(github_token="abc123"))

    injected = github._inject_token("https://github.com/example/repo.git")
    assert injected.startswith("https://abc123@github.com")


def test_iter_repository_files_respects_globs(tmp_path: Path):
    """iter_repository_files should honor default includes/excludes and size limits."""
    repo = tmp_path / "repo"
    repo.mkdir()
    allowed = repo / "docs" / "README.md"
    allowed.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_text("hello", encoding="utf-8")
    excluded = repo / "node_modules" / "bundle.min.js"
    excluded.parent.mkdir(parents=True, exist_ok=True)
    excluded.write_text("skip me", encoding="utf-8")

    files = github.iter_repository_files(repo)

    assert allowed in files
    assert excluded not in files


def test_clone_repository_passes_branch_and_depth(monkeypatch, tmp_path: Path):
    """clone_repository should inject tokens, honor branch, and clean up submodules."""
    repo_dir = tmp_path / "cloned"
    monkeypatch.setattr("tempfile.mkdtemp", lambda prefix: str(repo_dir))
    monkeypatch.setattr("certus_ask.services.github._inject_token", lambda url: f"{url}?token")

    captured = {}

    class DummyRepo:
        def __init__(self):
            self.submodules = []
            self.git = SimpleNamespace(submodule=lambda *args, **kwargs: None)

    def fake_clone(url, path, **kwargs):
        captured["url"] = url
        captured["path"] = path
        captured["kwargs"] = kwargs
        return DummyRepo()

    monkeypatch.setattr("certus_ask.services.github.Repo.clone_from", fake_clone)

    repo_ctx = github.clone_repository("https://example.com/repo.git", branch="main")

    assert captured["url"].endswith("?token")
    assert captured["path"] == repo_dir
    assert captured["kwargs"]["depth"] == 1
    assert captured["kwargs"]["branch"] == "main"
    assert repo_ctx.path == repo_dir
