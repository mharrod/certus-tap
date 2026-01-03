from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, NamedTuple
from urllib.parse import urlparse

import git

from certus_assurance.logs import LogStream
from certus_assurance.manifest import ManifestFetcher
from certus_assurance.models import ArtifactBundle, PipelineResult, PipelineStepResult, ScanRequest, SourceContext
from certus_assurance.signing import CosignClient

logger = logging.getLogger(__name__)

try:
    from security_module.runtime import ManagedRuntime, ScanRuntime
    from security_module.scanner import SecurityScanner
except ImportError:  # pragma: no cover
    ManagedRuntime = None  # type: ignore
    SecurityScanner = None  # type: ignore
    ScanRuntime = None  # type: ignore


# Deprecated: Use SourceContext instead
class RepoClone(NamedTuple):
    path: Path
    commit: str
    branch: str | None


def _default_runtime_factory(stream: LogStream | None) -> ScanRuntime:
    if ManagedRuntime is None:
        raise RuntimeError("security_module is not available on PYTHONPATH")
    return ManagedRuntime(log_sink=_stream_adapter(stream))


def _stream_adapter(stream: LogStream | None) -> Callable[[str, dict[str, Any]], None] | None:
    if stream is None:
        return None

    def emit(event_type: str, data: dict[str, Any]) -> None:
        stream.emit(event_type, **data)

    return emit


@dataclass(slots=True)
class CertusAssuranceRunner:
    """Managed service runner that delegates to the shared security module."""

    output_root: Path | str
    runtime_factory: Callable[[LogStream | None], ScanRuntime] | None = None
    scanner_builder: Callable[[ScanRuntime], Any] | None = None
    registry: str = "registry.example.com"
    registry_repository: str = "certus-assurance"
    trust_base_url: str = "http://certus-trust:8000"
    manifest_fetcher: ManifestFetcher | None = None
    cosign_client: CosignClient | None = None
    manifest_key_ref: str | None = None
    require_manifest_verification: bool = False
    preserve_sample_metadata: bool = False
    _workspace_root: Path | None = None

    def __post_init__(self) -> None:
        self.output_root = Path(self.output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        if self.runtime_factory is None:
            self.runtime_factory = _default_runtime_factory
        self.registry = self.registry.rstrip("/")
        self.registry_repository = self.registry_repository.strip("/")
        # Resolve the repository root used for relative git clone paths.
        self._workspace_root = Path(os.getenv("CERTUS_ASSURANCE_WORKSPACE_ROOT", Path(__file__).resolve().parents[2]))

    # Public API ----------------------------------------------------------------

    def run(self, request: ScanRequest) -> PipelineResult:
        start = time.time()
        steps: list[PipelineStepResult] = []
        bundle_path: Path | None = None
        manifest_digest: str | None = request.manifest_digest
        manifest_metadata: dict[str, Any] | None = None
        source_context: SourceContext | None = None
        stream = request.log_stream
        manifest_signature_bytes: bytes | None = None
        cleanup_callbacks: list[Callable[[], None]] = []

        manifest_text = request.manifest_text
        status = "SUCCEEDED"
        try:
            # Prepare source (git, directory, or archive)
            source_context = self._prepare_source(request, stream)
            steps.append(
                PipelineStepResult(
                    name="source_preparation",
                    status="SUCCEEDED",
                    details={
                        "source_type": source_context.source_type,
                        "provenance_id": source_context.provenance_id,
                        "metadata": source_context.metadata,
                    },
                )
            )

            # Load manifest from source if needed
            manifest_text = manifest_text or self._load_manifest_from_source(source_context, request)
            if manifest_text is None and request.manifest_uri:
                manifest_text, manifest_signature_bytes = self._load_manifest_from_uri(request, cleanup_callbacks)
            if manifest_text is None:
                raise ValueError("manifest input is required for Certus Assurance runs")
            manifest_digest = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

            # Execute scan
            bundle_path = self._execute_scan(request, source_context, manifest_text)
            manifest_metadata = self._hydrate_bundle(
                bundle_path,
                manifest_text,
                manifest_digest,
                stream,
                manifest_signature_bytes,
            )
            steps.append(
                PipelineStepResult(
                    name="scan",
                    status="SUCCEEDED",
                    details={"bundle": str(bundle_path)},
                )
            )
        except Exception as exc:
            status = "FAILED"
            steps.append(
                PipelineStepResult(
                    name="pipeline",
                    status="FAILED",
                    details={"error": str(exc)},
                )
            )
            if stream:
                stream.emit("error", message=str(exc))
            logger.exception("Certus Assurance run failed: test_id=%s", request.test_id)
            raise
        finally:
            self._finalize_stream(stream, status, manifest_digest, bundle_path)
            # Cleanup temporary source paths
            if source_context and source_context.metadata.get("cleanup_required"):
                shutil.rmtree(source_context.path, ignore_errors=True)
            for cleanup in cleanup_callbacks:
                cleanup()

        metadata = self._compose_metadata(
            request=request,
            source=source_context,
            bundle=bundle_path,
            manifest_digest=manifest_digest,
            manifest_metadata=manifest_metadata,
            status=status,
            started=start,
        )
        self._write_metadata_file(bundle_path, metadata)
        artifacts = ArtifactBundle.discover(bundle_path) if bundle_path else ArtifactBundle(Path("."))

        return PipelineResult(
            test_id=request.test_id,
            workspace_id=request.workspace_id,
            component_id=request.component_id,
            assessment_id=request.assessment_id,
            status=status,
            artifacts=artifacts,
            steps=steps,
            metadata=metadata,
            manifest_digest=manifest_digest,
            manifest_metadata=manifest_metadata,
        )

    # Internal helpers ----------------------------------------------------------

    def _prepare_source(self, request: ScanRequest, stream: LogStream | None) -> SourceContext:
        """Prepare source for scanning based on source_type.

        Dispatcher that routes to the appropriate source preparation method.
        """
        source_type = request.source_type

        if source_type == "git":
            return self._prepare_git_source(request, stream)
        elif source_type == "directory":
            return self._prepare_directory_source(request, stream)
        elif source_type == "archive":
            return self._prepare_archive_source(request, stream)
        else:
            raise ValueError(f"Unsupported source_type: {source_type}")

    def _prepare_git_source(self, request: ScanRequest, stream: LogStream | None) -> SourceContext:
        """Clone git repository and return SourceContext."""
        stream and stream.emit("phase", message="Cloning repository")
        clone_dir = Path(tempfile.mkdtemp(prefix=f"certus-assurance-{request.test_id}-"))
        git_source = self._resolve_git_source(request.git_url)
        repo = git.Repo.clone_from(git_source, clone_dir)

        if request.branch:
            repo.git.checkout(request.branch)
        if request.commit:
            repo.git.checkout(request.commit)

        branch = None
        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = request.branch

        commit = repo.head.commit.hexsha
        stream and stream.emit("phase", message="Clone complete", commit=commit, branch=branch)

        return SourceContext(
            path=clone_dir,
            provenance_id=commit,
            source_type="git",
            metadata={
                "commit": commit,
                "branch": branch,
                "git_url": request.git_url,
                "cleanup_required": True,  # Temp clone needs cleanup
            },
        )

    def _prepare_directory_source(self, request: ScanRequest, stream: LogStream | None) -> SourceContext:
        """Prepare local directory for scanning."""
        stream and stream.emit("phase", message="Preparing directory source")

        if not request.directory_path:
            raise ValueError("directory_path is required for directory source_type")

        directory = Path(request.directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")

        # Calculate content hash for provenance
        content_hash = self._calculate_directory_hash(directory)

        stream and stream.emit("phase", message="Directory prepared", hash=content_hash)

        return SourceContext(
            path=directory,
            provenance_id=content_hash,
            source_type="directory",
            metadata={
                "directory_path": str(directory),
                "content_hash": content_hash,
                "cleanup_required": False,  # Don't delete user's directory
            },
        )

    def _prepare_archive_source(self, request: ScanRequest, stream: LogStream | None) -> SourceContext:
        """Extract archive and prepare for scanning."""
        stream and stream.emit("phase", message="Extracting archive")

        if not request.archive_path:
            raise ValueError("archive_path is required for archive source_type")

        archive_file = Path(request.archive_path)
        if not archive_file.exists():
            raise FileNotFoundError(f"Archive not found: {archive_file}")

        # Calculate archive hash for provenance
        archive_hash = self._calculate_file_hash(archive_file)

        # Extract to temporary directory
        extract_dir = Path(tempfile.mkdtemp(prefix=f"certus-assurance-{request.test_id}-"))

        import tarfile
        import zipfile

        try:
            if archive_file.suffix in {".tar", ".gz", ".tgz", ".tar.gz", ".tar.bz2"}:
                with tarfile.open(archive_file, "r:*") as tar:
                    tar.extractall(extract_dir)
            elif archive_file.suffix == ".zip":
                with zipfile.ZipFile(archive_file, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
            else:
                raise ValueError(f"Unsupported archive format: {archive_file.suffix}")
        except Exception as e:
            shutil.rmtree(extract_dir, ignore_errors=True)
            raise ValueError(f"Failed to extract archive: {e}") from e

        stream and stream.emit("phase", message="Archive extracted", hash=archive_hash)

        return SourceContext(
            path=extract_dir,
            provenance_id=archive_hash,
            source_type="archive",
            metadata={
                "archive_path": str(archive_file),
                "archive_hash": archive_hash,
                "archive_name": archive_file.name,
                "cleanup_required": True,  # Extracted temp directory needs cleanup
            },
        )

    def _calculate_directory_hash(self, directory: Path) -> str:
        """Calculate reproducible hash of directory contents."""
        hasher = hashlib.sha256()

        # Walk directory in sorted order for reproducibility
        for root, dirs, files in os.walk(directory):
            # Sort for reproducibility
            dirs.sort()
            files.sort()

            for filename in files:
                filepath = Path(root) / filename
                # Include relative path in hash
                rel_path = filepath.relative_to(directory)
                hasher.update(str(rel_path).encode("utf-8"))

                # Include file contents in hash
                try:
                    with filepath.open("rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hasher.update(chunk)
                except (OSError, PermissionError):
                    # Skip files we can't read
                    continue

        return hasher.hexdigest()

    def _calculate_file_hash(self, filepath: Path) -> str:
        """Calculate SHA256 hash of a file."""
        hasher = hashlib.sha256()
        with filepath.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _load_manifest_from_source(self, source: SourceContext, request: ScanRequest) -> str | None:
        """Load manifest from source context (replaces _load_manifest_from_repo)."""
        if not request.manifest_path:
            return None
        manifest_path = (source.path / request.manifest_path).resolve()
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest path {request.manifest_path} not found in source")
        return manifest_path.read_text(encoding="utf-8")

    def _load_manifest_from_repo(self, clone: RepoClone, request: ScanRequest) -> str | None:
        if not request.manifest_path:
            return None
        manifest_path = (clone.path / request.manifest_path).resolve()
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest path {request.manifest_path} not found in repository")
        return manifest_path.read_text(encoding="utf-8")

    def _load_manifest_from_uri(
        self,
        request: ScanRequest,
        cleanup_callbacks: list[Callable[[], None]],
    ) -> tuple[str, bytes | None]:
        if not self.manifest_fetcher:
            raise ValueError("manifest_uri provided but manifest fetching is not configured")
        manifest_path, signature_path, cleanup = self.manifest_fetcher.fetch(
            request.manifest_uri, request.manifest_signature_uri
        )
        cleanup_callbacks.append(cleanup)
        self._verify_manifest_signature(manifest_path, signature_path)
        signature_bytes = signature_path.read_bytes() if signature_path and signature_path.exists() else None
        return manifest_path.read_text(encoding="utf-8"), signature_bytes

    def _clone_repository(self, request: ScanRequest, stream: LogStream | None) -> RepoClone:
        stream and stream.emit("phase", message="Cloning repository")
        clone_dir = Path(tempfile.mkdtemp(prefix=f"certus-assurance-{request.test_id}-"))
        git_source = self._resolve_git_source(request.git_url)
        repo = git.Repo.clone_from(git_source, clone_dir)
        if request.branch:
            repo.git.checkout(request.branch)
        if request.commit:
            repo.git.checkout(request.commit)
        branch = None
        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = request.branch
        commit = repo.head.commit.hexsha
        stream and stream.emit("phase", message="Clone complete", commit=commit, branch=branch)
        return RepoClone(path=clone_dir, commit=commit, branch=branch)

    def _resolve_git_source(self, source: str | Path) -> str:
        """Resolve local git sources relative to the workspace root."""
        if not source:
            raise ValueError("git_url is required for Certus Assurance runs")

        if isinstance(source, Path):
            candidate = source
            scheme = ""
        else:
            parsed = urlparse(str(source))
            scheme = parsed.scheme
            if scheme and scheme not in {"file"}:
                return str(source)
            candidate = Path(parsed.path) if scheme == "file" else Path(str(source))

        if not candidate.is_absolute():
            candidate = (self._workspace_root / candidate).resolve()

        if candidate.exists():
            return candidate.as_posix()

        # Fall back to the original source (git will raise if invalid).
        return str(source)

    def _execute_scan(self, request: ScanRequest, source: SourceContext, manifest_text: str) -> Path:
        bundle_dir = self.output_root / request.test_id
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)

        runtime = self.runtime_factory(request.log_stream)
        scanner_builder = self.scanner_builder
        if scanner_builder is None:
            if SecurityScanner is None:
                raise RuntimeError("security_module is not available; provide scanner_builder when running outside TAP")
            scanner_builder = lambda runtime: SecurityScanner(runtime)
        scanner = scanner_builder(runtime)
        result = asyncio.run(
            scanner.run(
                profile=request.profile,
                workspace=source.path,
                manifest_text=manifest_text,
                export_dir=self.output_root,
                bundle_id=request.test_id,
            )
        )
        return result.artifacts if isinstance(result.artifacts, Path) else Path(result.artifacts)

    def _hydrate_bundle(
        self,
        bundle: Path,
        manifest_text: str,
        digest: str | None,
        stream: LogStream | None,
        signature_bytes: bytes | None = None,
    ) -> dict[str, Any] | None:
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / "manifest.json").write_text(manifest_text, encoding="utf-8")
        if signature_bytes:
            (bundle / "manifest.sig").write_bytes(signature_bytes)

        self._ensure_layout(bundle)
        manifest_info = bundle / "manifest-info.json"
        metadata = None
        if manifest_info.exists():
            metadata = json.loads(manifest_info.read_text(encoding="utf-8"))
        self._write_log(bundle, metadata, stream)
        self._write_image_markers(bundle)
        if digest and metadata and not metadata.get("manifest_digest"):
            metadata["manifest_digest"] = digest
            manifest_info.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return metadata

    def _ensure_layout(self, bundle: Path) -> None:
        layout: dict[str, list[tuple[str, str] | str]] = {
            "reports/sast": [
                "trivy.sarif.json",
                "bandit.json",
                "opengrep.sarif.json",
                "detect-secrets.json",
                "ruff.txt",
            ],
            "reports/sbom": [("syft.spdx.json", "syft.spdx.json"), "sbom.cyclonedx.json"],
            "reports/dast": ["dast-results.json", "zap-report.html", "zap-report.json"],
            "reports/signing": ["attestation.intoto.json"],
        }
        for rel_dir, files in layout.items():
            target_dir = bundle / rel_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            for filename in files:
                if isinstance(filename, tuple):
                    src_name, dest_name = filename
                else:
                    src_name = dest_name = filename
                src = bundle / src_name
                if src.exists():
                    dest = target_dir / dest_name
                    if src.resolve() != dest.resolve():
                        shutil.move(str(src), str(dest))
        (bundle / "logs").mkdir(parents=True, exist_ok=True)
        (bundle / "artifacts").mkdir(parents=True, exist_ok=True)

    def _write_log(self, bundle: Path, manifest_metadata: dict[str, Any] | None, stream: LogStream | None) -> None:
        log_path = bundle / "logs" / "runner.log"
        stream_path = bundle / "stream.jsonl"
        lines = []
        if manifest_metadata:
            lines.append(json.dumps({"type": "manifest", "data": manifest_metadata}))
        if stream:
            for event in stream.history:
                lines.append(event.to_json())
        log_path.write_text("\n".join(lines), encoding="utf-8")
        stream_path.write_text("\n".join(lines), encoding="utf-8")

    def _write_image_markers(self, bundle: Path) -> None:
        image = bundle / "artifacts"
        image_ref = f"registry.example.com/certus-assurance/{bundle.name}:latest"
        digest = hashlib.sha256(bundle.name.encode("utf-8")).hexdigest()
        (image / "image.txt").write_text(image_ref, encoding="utf-8")
        (image / "image.digest").write_text(f"sha256:{digest}", encoding="utf-8")

    def _compose_metadata(
        self,
        *,
        request: ScanRequest,
        source: SourceContext | None,
        bundle: Path | None,
        manifest_digest: str | None,
        manifest_metadata: dict[str, Any] | None,
        status: str,
        started: float,
    ) -> dict[str, Any]:
        completed = time.time()
        sample_metadata = self._load_existing_metadata(bundle) if self.preserve_sample_metadata else None
        artifacts = ArtifactBundle.discover(bundle) if bundle else None

        # Build source-specific metadata
        source_metadata: dict[str, Any] = {
            "source_type": source.source_type if source else request.source_type,
            "provenance_id": source.provenance_id if source else None,
        }

        if source and source.is_git:
            source_metadata.update({
                "git_url": source.metadata.get("git_url") or request.git_url,
                "git_commit": source.commit,
                "branch": source.branch,
            })
        elif source and source.source_type == "directory":
            source_metadata.update({
                "directory_path": source.metadata.get("directory_path"),
                "content_hash": source.metadata.get("content_hash"),
            })
        elif source and source.source_type == "archive":
            source_metadata.update({
                "archive_path": source.metadata.get("archive_path"),
                "archive_hash": source.metadata.get("archive_hash"),
                "archive_name": source.metadata.get("archive_name"),
            })

        metadata = {
            "test_id": request.test_id,
            "workspace_id": request.workspace_id,
            "component_id": request.component_id,
            "assessment_id": request.assessment_id,
            "status": status,
            **source_metadata,  # Include source-specific fields
            "requested_by": request.requested_by,
            "profile": request.profile,
            "manifest_digest": manifest_digest,
            "artifacts": artifacts.artifact_map() if artifacts else {},
            "warnings": [],
            "errors": [],
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(completed)),
            "manifest_metadata": manifest_metadata,
        }

        if sample_metadata:
            merged = dict(sample_metadata)
            merged.update({
                "scan_id": request.test_id,
                "test_id": request.test_id,
                "workspace_id": request.workspace_id,
                "component_id": request.component_id,
                "assessment_id": request.assessment_id,
                "status": status,
                **source_metadata,  # Update source fields in sample metadata too
                "manifest_digest": manifest_digest,
                "manifest_metadata": manifest_metadata,
                "started_at": metadata["started_at"],
                "completed_at": metadata["completed_at"],
                "warnings": metadata["warnings"],
                "errors": metadata["errors"],
            })
            if artifacts:
                merged.setdefault("artifacts", artifacts.artifact_map())
            else:
                merged.setdefault("artifacts", {})
            return merged
        return metadata

    def _write_metadata_file(self, bundle: Path | None, metadata: dict[str, Any]) -> None:
        if not bundle:
            return
        target = bundle / "scan.json"
        target.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def _load_existing_metadata(self, bundle: Path | None) -> dict[str, Any] | None:
        if not bundle:
            return None
        target = bundle / "scan.json"
        if not target.exists():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _finalize_stream(
        self,
        stream: LogStream | None,
        status: str,
        manifest_digest: str | None,
        bundle: Path | None,
    ) -> None:
        if not stream:
            return
        data: dict[str, Any] = {}
        if manifest_digest:
            data["manifest_digest"] = manifest_digest
        if bundle:
            data["bundle"] = str(bundle)
        stream.close(status, **data)

    def _verify_manifest_signature(self, manifest_path: Path, signature_path: Path | None) -> None:
        if not self.manifest_key_ref:
            if self.require_manifest_verification:
                raise ValueError("Manifest verification requires a key reference")
            return
        if not self.cosign_client:
            raise ValueError("Cosign client is required for manifest verification")
        if not signature_path or not signature_path.exists():
            if self.require_manifest_verification:
                raise ValueError("Manifest signature is required for verification")
            return
        self.cosign_client.verify_blob(
            blob_path=manifest_path,
            signature_path=signature_path,
            key_ref=self.manifest_key_ref,
        )

    def _calculate_artifact_hash(self, path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(4096), b""):
                sha256_hash.update(chunk)
        return f"sha256:{sha256_hash.hexdigest()}"

    def _submit_upload_request(self, upload_request: Any) -> dict[str, Any]:
        """Submit upload request to Trust for verification and permission.

        Calls Trust's /v1/verify-and-permit-upload endpoint.
        Trust verifies the signature and returns permission decision.
        """
        import httpx

        from certus_assurance.settings import settings

        trust_url = settings.trust_base_url

        try:
            # Convert upload_request (dataclass) to dict for JSON serialization
            from dataclasses import asdict

            if hasattr(upload_request, "__dataclass_fields__"):
                # It's a dataclass - use asdict
                request_data = asdict(upload_request)
            elif hasattr(upload_request, "model_dump"):
                # It's a Pydantic v2 model
                request_data = upload_request.model_dump(exclude_none=True, mode="json")
            elif hasattr(upload_request, "dict"):
                # It's a Pydantic v1 model
                request_data = upload_request.dict(exclude_none=True)
            else:
                request_data = upload_request

            logger.debug(f"Submitting upload request to Trust: {trust_url}/v1/verify-and-permit-upload")

            # Call Trust service
            # Use verify=False for local development to avoid SSL certificate issues
            response = httpx.post(
                f"{trust_url}/v1/verify-and-permit-upload",
                json=request_data,
                timeout=30.0,
                verify=False,
            )
            response.raise_for_status()

            permission_response = response.json()

            logger.info(
                f"Trust permission response: permitted={permission_response.get('permitted')}",
                extra={
                    "scan_id": upload_request.scan_id,
                    "permission_id": permission_response.get("upload_permission_id"),
                    "tier": upload_request.tier,
                },
            )

            return permission_response

        except httpx.HTTPError as e:
            logger.error(
                f"Failed to call Trust service: {e}",
                extra={
                    "scan_id": upload_request.scan_id,
                    "trust_url": trust_url,
                    "error": str(e),
                },
            )
            # Fallback to mock for development when Trust is unavailable
            logger.warning("Trust service unavailable, using mock permission (development only)")
            return {
                "permitted": True,
                "upload_permission_id": f"{upload_request.scan_id}-permit-fallback",
                "reason": "trust_unavailable",
            }
