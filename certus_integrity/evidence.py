import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog
from pydantic import BaseModel

from certus_integrity.schemas import IntegrityDecision

logger = structlog.get_logger(__name__)


class SignedEvidence(BaseModel):
    """
    Represents the final authorized evidence bundle.
    """

    evidence_id: str
    timestamp: str
    decision: dict[str, Any]
    content_hash: str
    signature: Optional[str] = None
    signer_certificate: Optional[str] = None
    transparency_log_entry: Optional[dict[str, Any]] = None
    verification_status: str = "unsigned"  # signed, failed, offline


class EvidenceGenerator:
    """
    Handles the creation, signing, and persistence of integrity evidence.
    """

    def __init__(self, service_name: str, trust_url: Optional[str] = None):
        self.service_name = service_name
        # Use env var if not provided, fallback to internal docker default
        self.trust_url = trust_url or os.getenv("TRUST_BASE_URL", "http://certus-trust:8000")
        self.storage_path = Path("/tmp/evidence")  # TODO: Configurable (S3/Volume)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def process_decision(self, decision: IntegrityDecision) -> SignedEvidence:
        """
        Main workflow: Bundle -> Hash -> Sign -> Save.
        """
        try:
            # 1. Prepare Content
            evidence_id = decision.decision_id
            content = decision.model_dump(mode="json")

            # Canonical JSON serialization for consistent hashing
            canonical_json = json.dumps(content, sort_keys=True, separators=(",", ":"))
            content_hash = hashlib.sha256(canonical_json.encode()).hexdigest()

            # 2. Sign (Stage 3b)
            signature_data = await self._sign_hash(content_hash, title=f"integrity-decision-{evidence_id}")

            # 3. Assemble Bundle
            signed_bundle = SignedEvidence(
                evidence_id=evidence_id,
                timestamp=datetime.utcnow().isoformat(),
                decision=content,
                content_hash=content_hash,
                signature=signature_data.get("signature"),
                signer_certificate=signature_data.get("certificate"),
                transparency_log_entry=signature_data.get("transparency_entry"),
                verification_status="signed" if signature_data.get("signature") else "offline",
            )

            # 4. Save to Disk (Durable Storage)
            self._save_to_disk(signed_bundle)

            return signed_bundle

        except Exception as e:
            logger.error("evidence_generation_failed", error=str(e), decision_id=decision.decision_id)
            # Fallback: Save unsigned bundle so we don't lose the audit trail
            fallback = SignedEvidence(
                evidence_id=decision.decision_id,
                timestamp=datetime.utcnow().isoformat(),
                decision=decision.model_dump(mode="json"),
                content_hash="error",
                verification_status="failed",
            )
            self._save_to_disk(fallback)
            return fallback

    async def _sign_hash(self, digest: str, title: str) -> dict[str, Any]:
        """
        Calls certus-trust to sign the artifact hash.
        """
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                payload = {
                    "artifact": digest,
                    "artifact_type": "integrity_evidence",
                    "subject": f"{self.service_name}:{title}",
                    "predicates": {"generator": "certus-integrity-chassis"},
                }
                response = await client.post(f"{self.trust_url}/v1/sign", json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning("signing_service_unavailable", error=str(e), url=self.trust_url)
            return {}

    def _save_to_disk(self, bundle: SignedEvidence):
        """
        Persists the bundle to the local filesystem (simulating S3).
        """
        try:
            file_path = self.storage_path / f"dec_{bundle.evidence_id}.json"
            with open(file_path, "w") as f:
                f.write(bundle.model_dump_json(indent=2))
        except Exception as e:
            logger.error("evidence_save_failed", error=str(e), path=str(self.storage_path))
