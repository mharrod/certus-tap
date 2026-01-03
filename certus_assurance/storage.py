from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from botocore.client import BaseClient

from certus_assurance.models import PipelineResult
from certus_assurance.signing import CosignClient

logger = logging.getLogger(__name__)


class TransformArtifactPublisher:
    """Uploads scan bundles using the raw→golden pattern described in the TAP architecture."""

    def __init__(
        self,
        client: BaseClient,
        *,
        raw_bucket: str,
        golden_bucket: str,
        raw_prefix: str,
        golden_prefix: str,
    ) -> None:
        self.client = client
        self.raw_bucket = raw_bucket
        self.golden_bucket = golden_bucket
        self.raw_prefix = raw_prefix.strip("/")
        self.golden_prefix = golden_prefix.strip("/")

    def stage_and_promote(
        self, result: PipelineResult, manifest_digest: str | None = None
    ) -> dict[str, dict[str, str]]:
        root = result.artifacts.root
        raw_uris: dict[str, str] = {}
        golden_uris: dict[str, str] = {}
        metadata = self._build_metadata(
            result.test_id, result.workspace_id, result.component_id, result.assessment_id, manifest_digest
        )
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(root)
            raw_key = self._raw_key(result.test_id, rel)
            self._upload_file(file_path, self.raw_bucket, raw_key, metadata)
            raw_uris[str(rel)] = f"s3://{self.raw_bucket}/{raw_key}"
            golden_key = self._golden_key(result.test_id, rel)
            self._copy_object(self.raw_bucket, raw_key, self.golden_bucket, golden_key, metadata)
            golden_uris[str(rel)] = f"s3://{self.golden_bucket}/{golden_key}"

        logger.info(
            "Uploaded %s artifacts for test %s",
            len(raw_uris),
            result.test_id,
            extra={"test_id": result.test_id, "manifest_digest": manifest_digest},
        )
        return {"raw": raw_uris, "golden": golden_uris}

    def _upload_file(self, path: Path, bucket: str, key: str, metadata: dict[str, str]) -> None:
        self.client.upload_file(str(path), bucket, key, ExtraArgs={"Metadata": metadata})

    def _copy_object(
        self, src_bucket: str, src_key: str, dest_bucket: str, dest_key: str, metadata: dict[str, str]
    ) -> None:
        copy_source = {"Bucket": src_bucket, "Key": src_key}
        self.client.copy(
            copy_source,
            dest_bucket,
            dest_key,
            ExtraArgs={"Metadata": metadata, "MetadataDirective": "REPLACE"},
        )

    def _raw_key(self, test_id: str, rel_path: Path) -> str:
        parts = [self.raw_prefix, test_id, "incoming", str(rel_path).replace("\\", "/")]
        return "/".join(part for part in parts if part)

    def _golden_key(self, test_id: str, rel_path: Path) -> str:
        parts = [self.golden_prefix, test_id, "golden", str(rel_path).replace("\\", "/")]
        return "/".join(part for part in parts if part)

    def _build_metadata(
        self,
        test_id: str,
        workspace_id: str,
        component_id: str,
        assessment_id: str,
        manifest_digest: str | None,
    ) -> dict[str, str]:
        payload = {
            "test_id": test_id,
            "workspace_id": workspace_id,
            "component_id": component_id,
            "assessment_id": assessment_id,
        }
        if manifest_digest:
            payload["manifest_digest"] = manifest_digest
        return {key: str(value) for key, value in payload.items()}


class RegistryMirrorPublisher:
    """Placeholder registry publisher that mirrors artifacts locally.

    Until real image pushes are wired, we copy signing outputs + references into a
    configurable directory so downstream systems can read them as if they were
    hosted in a registry/attestation store.
    """

    def __init__(self, mirror_root: Path | str):
        self.root = Path(mirror_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(self, result: PipelineResult) -> dict[str, str]:
        dest = self.root / result.test_id
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        signing_dest = dest / "reports" / "signing"
        signing_dest.mkdir(parents=True)
        shutil.copy2(result.artifacts.attestation, signing_dest / result.artifacts.attestation.name)
        shutil.copy2(result.artifacts.image_reference, dest / "image.txt")
        shutil.copy2(result.artifacts.image_digest, dest / "image.digest")
        if result.artifacts.manifest_json and result.artifacts.manifest_json.exists():
            policy_dest = dest / "policy"
            policy_dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(result.artifacts.manifest_json, policy_dest / "manifest.json")
            if result.artifacts.manifest_signature and result.artifacts.manifest_signature.exists():
                shutil.copy2(result.artifacts.manifest_signature, policy_dest / "manifest.sig")

        logger.info("Mirrored registry artifacts for test %s to %s", result.test_id, dest)
        return {
            "image_reference": result.artifacts.image_reference.read_text(encoding="utf-8").strip(),
            "digest": result.artifacts.image_digest.read_text(encoding="utf-8").strip(),
            "mirror_path": str(dest),
            "manifest": {
                "path": str(dest / "policy" / "manifest.json")
                if (dest / "policy" / "manifest.json").exists()
                else None,
                "signature": str(dest / "policy" / "manifest.sig")
                if (dest / "policy" / "manifest.sig").exists()
                else None,
            },
        }


class DockerRegistryPublisher:
    """Builds a tiny OCI image per scan, pushes it, and optionally cosign-signs it."""

    def __init__(
        self,
        registry: str,
        repository: str,
        username: str | None = None,
        password: str | None = None,
        run_cmd: Callable[[list[str]], None] | None = None,
        cosign: CosignClient | None = None,
        cosign_key_ref: str | None = None,
        cosign_password: str | None = None,
    ) -> None:
        self.registry = registry.rstrip("/")
        self.repository = repository.strip("/")
        self.username = username
        self.password = password
        self.cosign = cosign
        self.cosign_key_ref = cosign_key_ref
        self.cosign_password = cosign_password
        self._run_cmd = run_cmd or self._default_run

    def publish(self, result: PipelineResult) -> dict[str, str]:
        image_ref = result.artifacts.image_reference.read_text(encoding="utf-8").strip()
        manifest_path = result.artifacts.manifest_json
        manifest_sig_path = result.artifacts.manifest_signature
        if manifest_path and self.cosign:
            manifest_sig_path = manifest_path.parent / "manifest.sig"
            self.cosign.sign_blob(manifest_path, self.cosign_key_ref, manifest_sig_path, self.cosign_password)
            result.artifacts.manifest_signature = manifest_sig_path
        with tempfile.TemporaryDirectory(prefix="certus-assurance-image-") as tmp:
            tmp_path = Path(tmp)
            shutil.copy2(result.artifacts.metadata, tmp_path / "scan.json")
            dockerfile = tmp_path / "Dockerfile"
            copy_statements = ["FROM scratch", "COPY scan.json /scan.json"]
            if manifest_path and manifest_path.exists():
                manifest_temp = tmp_path / "manifest.json"
                shutil.copy2(manifest_path, manifest_temp)
                copy_statements.append("COPY manifest.json /manifest.json")
            if manifest_sig_path and manifest_sig_path.exists():
                manifest_sig_temp = tmp_path / "manifest.sig"
                shutil.copy2(manifest_sig_path, manifest_sig_temp)
                copy_statements.append("COPY manifest.sig /manifest.sig")
            dockerfile.write_text("\n".join(copy_statements) + "\n", encoding="utf-8")

            self._run_cmd(["docker", "build", "-t", image_ref, str(tmp_path)])

            if self.username:
                login_cmd = ["docker", "login", self.registry, "-u", self.username]
                if self.password:
                    login_cmd.extend(["-p", self.password])
                self._run_cmd(login_cmd)

            self._run_cmd(["docker", "push", image_ref])

        logger.info("Pushed Certus Assurance image %s", image_ref)
        info = {
            "image_reference": image_ref,
            "digest": result.artifacts.image_digest.read_text(encoding="utf-8").strip(),
            "registry": self.registry,
        }

        if self.cosign:
            if not self.cosign_key_ref:
                raise ValueError("Cosign key reference is required when cosign is enabled")
            predicate = result.artifacts.metadata
            self.cosign.sign(image_ref, self.cosign_key_ref, self.cosign_password)
            self.cosign.attest(image_ref, predicate, self.cosign_key_ref, self.cosign_password)
            info["cosign"] = {
                "signed": True,
                "predicate": str(predicate),
            }
            if manifest_path:
                info["manifest"] = {
                    "path": str(manifest_path),
                    "signature": str(result.artifacts.manifest_signature)
                    if result.artifacts.manifest_signature
                    else None,
                }
        elif manifest_path:
            info["manifest"] = {
                "path": str(manifest_path),
                "signature": str(result.artifacts.manifest_signature) if result.artifacts.manifest_signature else None,
            }

        return info

    def _default_run(self, cmd: list[str]) -> None:
        subprocess.run(cmd, check=True)
