from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Callable


class CosignError(RuntimeError):
    pass


class CosignClient:
    """Thin wrapper around the cosign CLI for signing + attestations."""

    def __init__(
        self, binary: str = "cosign", runner: Callable[[Sequence[str], dict[str, str] | None], None] | None = None
    ):
        self.binary = binary
        self._runner = runner or self._default_runner

    def sign(self, image_ref: str, key_ref: str, password: str | None = None) -> None:
        if not key_ref:
            raise CosignError("cosign key reference is required for signing")
        cmd = [self.binary, "sign", "--key", key_ref, "--yes", image_ref]
        self._runner(cmd, self._build_env(password))

    def attest(
        self,
        image_ref: str,
        predicate_path: Path,
        key_ref: str,
        password: str | None = None,
        predicate_type: str = "https://slsa.dev/provenance/v1",
    ) -> None:
        if not key_ref:
            raise CosignError("cosign key reference is required for attestations")
        cmd = [
            self.binary,
            "attest",
            "--predicate",
            str(predicate_path),
            "--type",
            predicate_type,
            "--key",
            key_ref,
            "--yes",
            image_ref,
        ]
        self._runner(cmd, self._build_env(password))

    def sign_blob(
        self,
        blob_path: Path,
        key_ref: str,
        output_signature: Path,
        password: str | None = None,
    ) -> None:
        if not key_ref:
            raise CosignError("cosign key reference is required for blob signing")
        cmd = [
            self.binary,
            "sign-blob",
            "--key",
            key_ref,
            "--output-signature",
            str(output_signature),
            str(blob_path),
        ]
        self._runner(cmd, self._build_env(password))

    def verify_blob(self, blob_path: Path, signature_path: Path, key_ref: str) -> None:
        if not key_ref:
            raise CosignError("cosign key reference is required for blob verification")
        cmd = [
            self.binary,
            "verify-blob",
            "--key",
            key_ref,
            "--signature",
            str(signature_path),
            str(blob_path),
        ]
        self._runner(cmd, None)

    def _build_env(self, password: str | None) -> dict[str, str] | None:
        if not password:
            return None
        env = os.environ.copy()
        env["COSIGN_PASSWORD"] = password
        return env

    @staticmethod
    def _default_runner(cmd: Sequence[str], env: dict[str, str] | None) -> None:
        subprocess.run(cmd, check=True, env=env)
