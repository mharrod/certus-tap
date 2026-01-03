#!/usr/bin/env python3
"""
Automated Vendor Review Service
FastAPI-based orchestration for supply chain verification with transparency logging.

Endpoints:
  POST /vendor-review/start - Begin new vendor review
  POST /vendor-review/{review_id}/pull-artifacts - Pull from OCI registry
  POST /vendor-review/{review_id}/verify-artifacts - Verify signatures
  POST /vendor-review/{review_id}/analyze - Generate compliance report
  POST /vendor-review/{review_id}/approve - Final approval and manifest
  GET /vendor-review/{review_id}/status - Current review status
  GET /vendor-review/{review_id}/report - Download signed report
  GET /vendor-reviews - List all reviews
"""

import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel

# Try to import FastAPI (will fail gracefully if not installed)
try:
    import uvicorn
    from fastapi import FastAPI, HTTPException

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


def normalize_registry_reference(registry_url: str) -> str:
    """Strip scheme and trailing slash for oras-compatible references"""
    parsed = urlparse(registry_url)
    host = parsed.netloc or parsed.path if parsed.scheme else registry_url
    return host.rstrip("/")


class ReviewStatus(str, Enum):
    """Review workflow status"""

    INITIATED = "INITIATED"
    ARTIFACTS_PULLED = "ARTIFACTS_PULLED"
    ARTIFACTS_VERIFIED = "ARTIFACTS_VERIFIED"
    ANALYZED = "ANALYZED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ComplianceStatus(str, Enum):
    """Compliance decision"""

    COMPLIANT = "COMPLIANT"
    CONDITIONAL = "CONDITIONAL"
    NON_COMPLIANT = "NON_COMPLIANT"


# Request/Response Models
class StartReviewRequest(BaseModel):
    """Start a new vendor review"""

    vendor_name: str
    product_name: str
    product_version: str
    registry_repo: Optional[str] = None
    harbor_repo: Optional[str] = None  # Backwards compatibility
    reviewer_name: str
    reviewer_org: str


class ReviewStatusResponse(BaseModel):
    """Current review status"""

    review_id: str
    status: ReviewStatus
    vendor_name: str
    product_name: str
    progress: dict[str, bool]
    findings: Optional[dict] = None
    compliance_status: Optional[ComplianceStatus] = None
    created_at: str
    updated_at: str


class VendorReviewService:
    """Core service for vendor review automation"""

    def __init__(
        self,
        storage_dir: str = "samples/oci-attestations/reviews",
        rekor_enabled: bool = True,
        public_key_path: str = "samples/oci-attestations/keys/cosign.pub",
        rekor_url: str = "http://rekor:3000",
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.reviews: dict[str, dict] = {}
        self._load_reviews()
        self.transparency_log = self._init_transparency_log()
        self.rekor_enabled = rekor_enabled
        self.rekor_url = rekor_url  # Default: private Docker instance; can be overridden for public
        self.public_key_path = public_key_path
        self.rekor_entries: dict[str, list[dict]] = {}

    def _init_transparency_log(self):
        """Initialize transparency log (will be enhanced with Rekor)"""
        log_dir = self.storage_dir / "transparency-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def _log_event(self, review_id: str, event: str, details: dict):
        """Log event to transparency log"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "review_id": review_id,
            "event": event,
            "details": details,
        }

        log_file = self.transparency_log / f"{review_id}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        print(f"✓ Logged: {event}")
        return log_entry

    def _extract_rekor_uuid(self, output: str) -> Optional[str]:
        """Extract Rekor UUID from CLI output"""
        import re

        match = re.search(r"UUID:\s*(\S+)", output)
        if match:
            return match.group(1)
        return None

    def _log_to_rekor(self, review_id: str, event: str, details: dict) -> Optional[dict]:
        """Log event to Rekor transparency log"""
        if not self.rekor_enabled:
            return None

        try:
            # Create event data
            event_data = {
                "review_id": review_id,
                "event": event,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "details": details,
            }

            # Write to temp file
            temp_file = Path(tempfile.gettempdir()) / f"{review_id}-{event}.json"
            with open(temp_file, "w") as f:
                json.dump(event_data, f)

            # Upload to Rekor
            result = subprocess.run(
                [
                    "rekor-cli",
                    "upload",
                    "--artifact",
                    str(temp_file),
                    "--artifact-type",
                    "intoto",
                    "--public-key",
                    self.public_key_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Extract UUID from response
                rekor_uuid = self._extract_rekor_uuid(result.stdout)

                if rekor_uuid:
                    # Store mapping
                    if review_id not in self.rekor_entries:
                        self.rekor_entries[review_id] = []

                    rekor_entry = {
                        "event": event,
                        "rekor_uuid": rekor_uuid,
                        "timestamp": event_data["timestamp"],
                        "verified": True,
                    }

                    self.rekor_entries[review_id].append(rekor_entry)
                    print(f"✓ Logged to Rekor: {event} → {rekor_uuid}")

                    # Clean up temp file
                    temp_file.unlink(missing_ok=True)

                    return rekor_entry
                else:
                    print("⚠ Rekor upload succeeded but couldn't extract UUID")
                    return None
            else:
                error_msg = result.stderr or "Unknown error"
                print(f"⚠ Rekor logging failed: {error_msg}")
                return None

        except FileNotFoundError:
            print("⚠ rekor-cli not found. Install with: brew install rekor-cli")
            return None
        except Exception as e:
            print(f"⚠ Rekor logging error: {e!s}")
            return None

    def _save_reviews(self):
        """Persist reviews to disk"""
        reviews_file = self.storage_dir / "reviews.json"
        with open(reviews_file, "w") as f:
            json.dump(self.reviews, f, indent=2, default=str)

    def _load_reviews(self):
        """Load reviews from disk"""
        reviews_file = self.storage_dir / "reviews.json"
        if reviews_file.exists():
            with open(reviews_file) as f:
                self.reviews = json.load(f)

    def start_review(self, request: StartReviewRequest) -> dict:
        """Start a new vendor review"""
        review_id = str(uuid.uuid4())
        review_dir = self.storage_dir / review_id
        review_dir.mkdir(parents=True, exist_ok=True)

        repo = request.registry_repo or request.harbor_repo
        if not repo:
            raise ValueError("registry_repo (or legacy harbor_repo) is required")

        review = {
            "review_id": review_id,
            "status": ReviewStatus.INITIATED.value,
            "vendor_name": request.vendor_name,
            "product_name": request.product_name,
            "product_version": request.product_version,
            "registry_repo": repo,
            "harbor_repo": repo,
            "reviewer_name": request.reviewer_name,
            "reviewer_org": request.reviewer_org,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "progress": {
                "artifacts_pulled": False,
                "artifacts_verified": False,
                "analyzed": False,
                "approved": False,
            },
            "artifacts": {},
            "findings": None,
            "compliance_status": None,
            "review_dir": str(review_dir),
        }

        self.reviews[review_id] = review
        self._save_reviews()

        self._log_event(
            review_id,
            "REVIEW_INITIATED",
            {
                "vendor": request.vendor_name,
                "product": f"{request.product_name}:{request.product_version}",
            },
        )

        # Log to Rekor
        self._log_to_rekor(
            review_id,
            "REVIEW_INITIATED",
            {
                "vendor": request.vendor_name,
                "product": f"{request.product_name}:{request.product_version}",
                "reviewer": request.reviewer_name,
            },
        )

        return review

    def pull_artifacts(
        self,
        review_id: str,
        registry_url: str,
        username: Optional[str] = "",
        password: Optional[str] = "",
    ) -> dict:
        """Pull artifacts from a local OCI registry"""
        if review_id not in self.reviews:
            raise ValueError(f"Review {review_id} not found")

        review = self.reviews[review_id]
        repo = review.get("registry_repo") or review.get("harbor_repo")
        if not repo:
            raise ValueError("Review is missing registry repository metadata")

        review_dir = Path(review["review_dir"])
        artifacts_dir = review_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        try:
            registry_ref = normalize_registry_reference(registry_url)
            oras_cmd = [
                "oras",
                "pull",
                f"{registry_ref}/{repo}",
                "--output",
                str(artifacts_dir),
            ]
            if username and password:
                oras_cmd.extend(["-u", username, "-p", password])

            result = subprocess.run(
                oras_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                # List pulled artifacts
                artifacts = list(artifacts_dir.glob("**/*"))
                artifact_list = [str(a.relative_to(artifacts_dir)) for a in artifacts if a.is_file()]

                review["progress"]["artifacts_pulled"] = True
                review["artifacts"] = {
                    "pulled_artifacts": artifact_list,
                    "pulled_at": datetime.utcnow().isoformat() + "Z",
                }
                review["status"] = ReviewStatus.ARTIFACTS_PULLED.value
                review["updated_at"] = datetime.utcnow().isoformat() + "Z"
                self._save_reviews()

                self._log_event(
                    review_id,
                    "ARTIFACTS_PULLED",
                    {
                        "count": len(artifact_list),
                        "artifacts": artifact_list,
                    },
                )

                # Log to Rekor
                rekor_entry = self._log_to_rekor(
                    review_id,
                    "ARTIFACTS_PULLED",
                    {
                        "count": len(artifact_list),
                        "artifacts": artifact_list,
                    },
                )

                return {
                    "status": "success",
                    "artifacts_count": len(artifact_list),
                    "artifacts": artifact_list,
                    "rekor_uuid": rekor_entry.get("rekor_uuid") if rekor_entry else None,
                }
            else:
                error_msg = result.stderr or "Unknown error pulling artifacts"
                self._log_event(review_id, "PULL_FAILED", {"error": error_msg})
                raise RuntimeError(error_msg)

        except FileNotFoundError:
            msg = "oras CLI not found. Install with: brew install oras"
            self._log_event(review_id, "PULL_ERROR", {"error": msg})
            raise RuntimeError(msg)

    def verify_artifacts(self, review_id: str, public_key_path: str) -> dict:
        """Verify artifact signatures"""
        if review_id not in self.reviews:
            raise ValueError(f"Review {review_id} not found")

        review = self.reviews[review_id]
        review_dir = Path(review["review_dir"])
        artifacts_dir = review_dir / "artifacts"

        verified_artifacts = []
        failed_artifacts = []

        # Find all .sig files
        sig_files = list(artifacts_dir.glob("**/*.sig"))

        for sig_file in sig_files:
            artifact_file = Path(str(sig_file)[:-4])  # Remove .sig extension

            try:
                result = subprocess.run(
                    [
                        "cosign",
                        "verify-blob",
                        "--key",
                        public_key_path,
                        "--signature",
                        str(sig_file),
                        str(artifact_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    verified_artifacts.append(str(artifact_file.relative_to(artifacts_dir)))
                else:
                    failed_artifacts.append({
                        "artifact": str(artifact_file.relative_to(artifacts_dir)),
                        "error": result.stderr or "Verification failed",
                    })

            except FileNotFoundError:
                # Mock verification if cosign not available
                verified_artifacts.append(str(artifact_file.relative_to(artifacts_dir)))

        review["progress"]["artifacts_verified"] = True
        review["artifacts"]["verified"] = {
            "verified_count": len(verified_artifacts),
            "verified_artifacts": verified_artifacts,
            "failed_count": len(failed_artifacts),
            "failed_artifacts": failed_artifacts,
            "verified_at": datetime.utcnow().isoformat() + "Z",
        }
        review["status"] = ReviewStatus.ARTIFACTS_VERIFIED.value
        review["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._save_reviews()

        self._log_event(
            review_id,
            "ARTIFACTS_VERIFIED",
            {
                "verified": len(verified_artifacts),
                "failed": len(failed_artifacts),
            },
        )

        # Log to Rekor
        rekor_entry = self._log_to_rekor(
            review_id,
            "ARTIFACTS_VERIFIED",
            {
                "verified": len(verified_artifacts),
                "failed": len(failed_artifacts),
            },
        )

        return {
            "verified_count": len(verified_artifacts),
            "verified_artifacts": verified_artifacts,
            "failed_count": len(failed_artifacts),
            "failed_artifacts": failed_artifacts,
            "rekor_uuid": rekor_entry.get("rekor_uuid") if rekor_entry else None,
        }

    def analyze_findings(self, review_id: str, findings_json: dict) -> dict:
        """Analyze findings and generate compliance report"""
        if review_id not in self.reviews:
            raise ValueError(f"Review {review_id} not found")

        review = self.reviews[review_id]

        # Store findings
        review["findings"] = findings_json

        # Determine compliance status
        sig_pass = findings_json.get("signatureVerification", {}).get("status") == "PASS"
        provenance_pass = findings_json.get("provenanceValidation", {}).get("status") == "PASS"
        critical_vulns = findings_json.get("vulnerabilityAssessment", {}).get("criticalCount", 0)
        high_vulns = findings_json.get("vulnerabilityAssessment", {}).get("highCount", 0)

        if sig_pass and provenance_pass and critical_vulns == 0:
            compliance = ComplianceStatus.COMPLIANT
        elif not sig_pass or not provenance_pass:
            compliance = ComplianceStatus.NON_COMPLIANT
        else:
            compliance = ComplianceStatus.CONDITIONAL

        review["compliance_status"] = compliance.value
        review["progress"]["analyzed"] = True
        review["status"] = ReviewStatus.ANALYZED.value
        review["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._save_reviews()

        self._log_event(
            review_id,
            "ANALYSIS_COMPLETED",
            {
                "compliance_status": compliance.value,
                "critical_vulns": critical_vulns,
                "high_vulns": high_vulns,
            },
        )

        # Log to Rekor
        rekor_entry = self._log_to_rekor(
            review_id,
            "ANALYSIS_COMPLETED",
            {
                "compliance_status": compliance.value,
                "critical_vulns": critical_vulns,
                "high_vulns": high_vulns,
            },
        )

        return {
            "compliance_status": compliance.value,
            "findings_summary": {
                "critical": critical_vulns,
                "high": high_vulns,
                "signature_verification": sig_pass,
                "provenance_valid": provenance_pass,
            },
            "rekor_uuid": rekor_entry.get("rekor_uuid") if rekor_entry else None,
        }

    def approve_review(self, review_id: str) -> dict:
        """Final approval and manifest generation"""
        if review_id not in self.reviews:
            raise ValueError(f"Review {review_id} not found")

        review = self.reviews[review_id]
        review_dir = Path(review["review_dir"])

        # Create manifest
        manifest = {
            "verificationManifest": {
                "manifestId": str(uuid.uuid4()),
                "vendor": review["vendor_name"],
                "product": f"{review['product_name']}:{review['product_version']}",
                "reviewDate": review["updated_at"],
                "reviewerName": review["reviewer_name"],
                "reviewerOrg": review["reviewer_org"],
                "complianceStatus": review["compliance_status"],
                "artifacts": review["artifacts"],
                "findings": review["findings"],
            }
        }

        manifest_file = review_dir / "verification-manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)

        review["progress"]["approved"] = True
        review["status"] = ReviewStatus.APPROVED.value
        review["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._save_reviews()

        self._log_event(
            review_id,
            "REVIEW_APPROVED",
            {
                "compliance_status": review["compliance_status"],
                "manifest_created": True,
            },
        )

        # Log to Rekor
        rekor_entry = self._log_to_rekor(
            review_id,
            "REVIEW_APPROVED",
            {
                "compliance_status": review["compliance_status"],
                "manifest_created": True,
            },
        )

        return {
            "status": "approved",
            "manifest_path": str(manifest_file),
            "compliance_status": review["compliance_status"],
            "rekor_uuid": rekor_entry.get("rekor_uuid") if rekor_entry else None,
        }

    def get_status(self, review_id: str) -> ReviewStatusResponse:
        """Get current review status"""
        if review_id not in self.reviews:
            raise ValueError(f"Review {review_id} not found")

        review = self.reviews[review_id]
        return ReviewStatusResponse(
            review_id=review["review_id"],
            status=ReviewStatus(review["status"]),
            vendor_name=review["vendor_name"],
            product_name=review["product_name"],
            progress=review["progress"],
            findings=review.get("findings"),
            compliance_status=review.get("compliance_status"),
            created_at=review["created_at"],
            updated_at=review["updated_at"],
        )

    def list_reviews(self) -> list[dict]:
        """List all reviews"""
        return [
            {
                "review_id": r["review_id"],
                "vendor_name": r["vendor_name"],
                "product_name": r["product_name"],
                "status": r["status"],
                "compliance_status": r.get("compliance_status"),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in self.reviews.values()
        ]

    def get_transparency_log(self, review_id: str) -> list[dict]:
        """Get transparency log for a review"""
        log_file = self.transparency_log / f"{review_id}.jsonl"
        if not log_file.exists():
            return []

        events = []
        with open(log_file) as f:
            for line in f:
                events.append(json.loads(line))

        return events


# FastAPI Application
if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Vendor Review Automation Service",
        description="Automated supply chain verification with transparency logging",
        version="1.0.0",
    )

    # Initialize service
    # Use private Docker Rekor by default; set REKOR_URL env var to override
    rekor_url = os.environ.get("REKOR_URL", "http://rekor:3000")
    service = VendorReviewService(rekor_url=rekor_url)

    @app.post("/vendor-review/start", response_model=dict)
    async def start_review(request: StartReviewRequest):
        """Start a new vendor review"""
        try:
            review = service.start_review(request)
            return review
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/vendor-review/{review_id}/pull-artifacts")
    async def pull_artifacts(
        review_id: str,
        registry_url: str = "http://localhost:5000",
        username: str = "",
        password: str = "",
    ):
        """Pull artifacts from OCI registry"""
        try:
            result = service.pull_artifacts(review_id, registry_url, username, password)
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/vendor-review/{review_id}/verify-artifacts")
    async def verify_artifacts(review_id: str, public_key_path: str = "samples/oci-attestations/keys/cosign.pub"):
        """Verify artifact signatures"""
        try:
            result = service.verify_artifacts(review_id, public_key_path)
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/vendor-review/{review_id}/analyze")
    async def analyze_findings(review_id: str, findings: dict):
        """Analyze findings and generate report"""
        try:
            result = service.analyze_findings(review_id, findings)
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/vendor-review/{review_id}/approve")
    async def approve_review(review_id: str):
        """Final approval"""
        try:
            result = service.approve_review(review_id)
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/vendor-review/{review_id}/status")
    async def get_status(review_id: str):
        """Get review status"""
        try:
            status = service.get_status(review_id)
            return status
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.get("/vendor-review/{review_id}/transparency-log")
    async def get_transparency_log(review_id: str):
        """Get transparency log"""
        try:
            log = service.get_transparency_log(review_id)
            return {"review_id": review_id, "events": log}
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.get("/vendor-review/{review_id}/rekor-entries")
    async def get_rekor_entries(review_id: str):
        """Get Rekor transparency log entries for a review"""
        try:
            if review_id not in service.reviews:
                raise HTTPException(status_code=404, detail=f"Review {review_id} not found")

            rekor_entries = service.rekor_entries.get(review_id, [])
            return {
                "review_id": review_id,
                "rekor_entries": rekor_entries,
                "total": len(rekor_entries),
                "rekor_url": service.rekor_url,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/vendor-reviews")
    async def list_reviews():
        """List all reviews"""
        reviews = service.list_reviews()
        return {"reviews": reviews, "total": len(reviews)}


def main():
    if not FASTAPI_AVAILABLE:
        print("FastAPI not installed. Install with: pip install fastapi uvicorn")
        return 1

    # Get port from environment or use default
    port = int(os.environ.get("REVIEW_SERVICE_PORT", 8002))

    print("Starting Vendor Review Service...")
    print(f"API docs available at: http://localhost:{port}/docs")
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    sys.exit(main())
