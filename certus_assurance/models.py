from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from certus_assurance.logs import LogStream


def _existing(path: Path | None) -> Path | None:
    if path and path.exists():
        return path
    return None


class SourceContext(NamedTuple):
    """Unified representation of scan source regardless of type."""

    path: Path  # Where the code lives
    provenance_id: str  # Git SHA, content hash, or archive hash
    source_type: str  # "git", "directory", or "archive"
    metadata: dict[str, Any]  # Type-specific metadata

    @property
    def is_git(self) -> bool:
        """Check if this is a git source."""
        return self.source_type == "git"

    @property
    def commit(self) -> str | None:
        """Git commit SHA if git source."""
        return self.metadata.get("commit") if self.is_git else None

    @property
    def branch(self) -> str | None:
        """Git branch if git source."""
        return self.metadata.get("branch") if self.is_git else None


@dataclass(slots=True)
class ScanRequest:
    """Input parameters for a Certus Assurance run."""

    test_id: str
    workspace_id: str
    component_id: str
    assessment_id: str

    # Source configuration (multi-source support)
    source_type: str = "git"  # "git", "directory", or "archive"
    git_url: str | None = None
    branch: str | None = None
    commit: str | None = None
    directory_path: str | None = None  # For directory scanning
    archive_path: str | None = None  # For archive scanning

    # Metadata
    requested_by: str | None = None
    profile: str = "light"
    manifest_text: str | None = None
    manifest_path: str | None = None
    manifest_uri: str | None = None
    manifest_signature_uri: str | None = None
    manifest_digest: str | None = None
    log_stream: LogStream | None = None


@dataclass(slots=True)
class ArtifactBundle:
    """Paths to all artifacts generated for a scan."""

    root: Path
    metadata: Path | None = None
    logs: Path | None = None
    manifest_info: Path | None = None
    manifest_json: Path | None = None
    manifest_signature: Path | None = None
    summary: Path | None = None
    sarif: Path | None = None
    sbom_spdx: Path | None = None
    sbom_cyclonedx: Path | None = None
    dast_json: Path | None = None
    dast_html: Path | None = None
    attestation: Path | None = None
    image_reference: Path | None = None
    image_digest: Path | None = None

    @classmethod
    def discover(cls, root: Path) -> ArtifactBundle:
        """Discover known artifact paths within the exported bundle."""

        def rel(*parts: str) -> Path:
            return root.joinpath(*parts)

        return cls(
            root=root,
            metadata=_existing(rel("scan.json")),
            logs=_existing(rel("logs", "runner.log")),
            manifest_info=_existing(rel("manifest-info.json")),
            manifest_json=_existing(rel("manifest.json")),
            manifest_signature=_existing(rel("manifest.sig")) or _existing(rel("manifest.json.sig")),
            summary=_existing(rel("summary.json")),
            sarif=_existing(rel("reports", "sast", "trivy.sarif.json")) or _existing(rel("trivy.sarif.json")),
            sbom_spdx=_existing(rel("reports", "sbom", "syft.spdx.json")) or _existing(rel("sbom.spdx.json")),
            sbom_cyclonedx=_existing(rel("reports", "sbom", "sbom.cyclonedx.json"))
            or _existing(rel("sbom.cyclonedx.json")),
            dast_json=_existing(rel("reports", "dast", "dast-results.json")) or _existing(rel("dast-results.json")),
            dast_html=_existing(rel("reports", "dast", "zap-report.html")) or _existing(rel("zap-report.html")),
            attestation=_existing(rel("reports", "signing", "attestation.intoto.json"))
            or _existing(rel("attestation.intoto.json")),
            image_reference=_existing(rel("artifacts", "image.txt")),
            image_digest=_existing(rel("artifacts", "image.digest")),
        )

    def artifact_map(self) -> dict[str, str]:
        """Return a map of artifact identifiers → relative paths."""

        mapping: dict[str, Path | None] = {
            "summary": self.summary,
            "manifest_info": self.manifest_info,
            "manifest_json": self.manifest_json,
            "manifest_signature": self.manifest_signature,
            "sarif": self.sarif,
            "sbom_spdx": self.sbom_spdx,
            "sbom_cyclonedx": self.sbom_cyclonedx,
            "dast_json": self.dast_json,
            "dast_html": self.dast_html,
            "attestation": self.attestation,
        }
        result: dict[str, str] = {}
        for key, path in mapping.items():
            if path and path.exists():
                result[key] = str(path.relative_to(self.root))
        return result


@dataclass(slots=True)
class PipelineStepResult:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineResult:
    test_id: str
    workspace_id: str
    component_id: str
    assessment_id: str
    status: str
    artifacts: ArtifactBundle
    steps: list[PipelineStepResult]
    metadata: dict[str, Any]
    upload_status: str = "pending"  # pending, permitted, failed
    upload_permission_id: str | None = None
    manifest_digest: str | None = None
    manifest_metadata: dict[str, Any] | None = None
