from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import boto3
import httpx

from certus_assurance.settings import CertusAssuranceSettings


class ManifestFetcher:
    """Fetches manifest artifacts from local files, S3, or OCI registry bundles."""

    def __init__(self, cfg: CertusAssuranceSettings):
        self.cfg = cfg
        self._s3_client = None

    def fetch(self, uri: str, signature_uri: str | None = None) -> tuple[Path, Path | None, Callable[[], None]]:
        parsed = urlparse(uri)
        scheme = parsed.scheme or "file"
        if scheme in ("file", ""):
            path = Path(parsed.path if parsed.scheme == "file" else uri).expanduser()
            sig_path = None
            if signature_uri:
                sig_parsed = urlparse(signature_uri)
                if sig_parsed.scheme not in ("file", ""):
                    raise ValueError("Signature URI for local manifests must also be a local path")
                sig_path = Path(sig_parsed.path if sig_parsed.scheme == "file" else signature_uri).expanduser()
            return path, sig_path, lambda: None
        if scheme == "s3":
            return self._download_s3(parsed.netloc, parsed.path.lstrip("/"), signature_uri)
        if scheme == "oci":
            return self._download_oci(f"{parsed.netloc}{parsed.path}")
        if scheme in ("http", "https"):
            return self._download_http(uri, signature_uri)
        raise ValueError(f"Unsupported manifest URI scheme '{scheme}'")

    # S3 helpers ----------------------------------------------------------------

    def _download_s3(
        self, bucket: str, key: str, signature_uri: str | None
    ) -> tuple[Path, Path | None, Callable[[], None]]:
        client = self._get_s3_client()
        tmp_dir = Path(tempfile.mkdtemp(prefix="certus-manifest-s3-"))
        manifest_path = tmp_dir / "manifest.json"
        client.download_file(bucket, key, str(manifest_path))

        signature_path = None
        if signature_uri:
            parsed = urlparse(signature_uri)
            sig_bucket = parsed.netloc or bucket
            sig_key = parsed.path.lstrip("/")
            signature_path = tmp_dir / "manifest.sig"
            client.download_file(sig_bucket, sig_key, str(signature_path))

        def cleanup() -> None:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return manifest_path, signature_path if signature_path and signature_path.exists() else None, cleanup

    def _get_s3_client(self):
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.cfg.s3_endpoint_url,
                region_name=self.cfg.s3_region,
                aws_access_key_id=self.cfg.s3_access_key_id,
                aws_secret_access_key=self.cfg.s3_secret_access_key,
            )
        return self._s3_client

    # HTTP/HTTPS helpers --------------------------------------------------------

    def _download_http(self, uri: str, signature_uri: str | None) -> tuple[Path, Path | None, Callable[[], None]]:
        tmp_dir = Path(tempfile.mkdtemp(prefix="certus-manifest-http-"))
        manifest_path = tmp_dir / "manifest.json"

        # Download manifest
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(uri)
            response.raise_for_status()
            manifest_path.write_bytes(response.content)

        # Download signature if provided
        signature_path = None
        if signature_uri:
            signature_path = tmp_dir / "manifest.sig"
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                try:
                    sig_response = client.get(signature_uri)
                    sig_response.raise_for_status()
                    signature_path.write_bytes(sig_response.content)
                except httpx.HTTPError:
                    # Signature download failed, set to None
                    signature_path = None

        def cleanup() -> None:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return manifest_path, signature_path, cleanup

    # OCI helpers ---------------------------------------------------------------

    def _download_oci(self, reference: str) -> tuple[Path, Path | None, Callable[[], None]]:
        tmp_dir = Path(tempfile.mkdtemp(prefix="certus-manifest-oci-"))
        container_name = f"manifest-fetch-{uuid.uuid4().hex[:8]}"
        try:
            self._docker_login()
            self._run(["docker", "pull", reference])
            self._run(["docker", "create", "--name", container_name, reference])
            container_id = container_name
            manifest_path = tmp_dir / "manifest.json"
            self._run(["docker", "cp", f"{container_id}:/manifest.json", str(manifest_path)])
            signature_path = tmp_dir / "manifest.sig"
            try:
                self._run(["docker", "cp", f"{container_id}:/manifest.sig", str(signature_path)])
            except subprocess.CalledProcessError:
                signature_path = None
        except Exception:
            with contextlib.suppress(subprocess.CalledProcessError):
                self._run(["docker", "rm", "-f", container_name])
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

        def cleanup() -> None:
            with contextlib.suppress(subprocess.CalledProcessError):
                self._run(["docker", "rm", "-f", container_name])
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return manifest_path, signature_path if signature_path and signature_path.exists() else None, cleanup

    def _docker_login(self) -> None:
        if not self.cfg.registry_username:
            return
        cmd = ["docker", "login", self.cfg.registry.rstrip("/"), "-u", self.cfg.registry_username]
        if self.cfg.registry_password:
            cmd.extend(["-p", self.cfg.registry_password])
        self._run(cmd)

    def _run(self, cmd: list[str]) -> None:
        subprocess.run(cmd, check=True)
