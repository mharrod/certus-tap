from __future__ import annotations

from pathlib import Path

import pytest

from certus_assurance.signing import CosignClient, CosignError


def test_cosign_client_sign_and_attest(monkeypatch) -> None:
    commands: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_run(cmd, env):
        commands.append((list(cmd), env))

    client = CosignClient(binary="cosign", runner=fake_run)
    client.sign("localhost:5000/repo:tag", key_ref="cosign.key", password="secret")
    client.attest(
        "localhost:5000/repo:tag",
        Path("/tmp/predicate.json"),
        key_ref="cosign.key",
        password="secret",
    )

    assert commands[0][0][:3] == ["cosign", "sign", "--key"]
    assert commands[0][1]["COSIGN_PASSWORD"] == "secret"
    assert commands[1][0][0:2] == ["cosign", "attest"]
    assert "--predicate" in commands[1][0]


def test_cosign_client_requires_key() -> None:
    client = CosignClient(binary="cosign", runner=lambda *_: None)
    with pytest.raises(CosignError):
        client.sign("image", key_ref="")
