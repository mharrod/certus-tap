import pytest

from certus_ask.core.exceptions import ValidationError
from certus_ask.services.ingestion.utils import enforce_verified_digest, match_expected_digest

pytestmark = pytest.mark.integration


def test_match_expected_digest_from_uri():
    artifact_locations = {
        "s3": {
            "uri": "s3://raw/security-scans/scan123/scan123/reports/sarif.json",
            "digest": "sha256:abc",
        }
    }

    digest = match_expected_digest(
        artifact_locations,
        "raw",
        "security-scans/scan123/scan123/reports/sarif.json",
    )
    assert digest == "sha256:abc"


def test_enforce_verified_digest_success():
    artifact_locations = {
        "s3": {
            "uri": "s3://raw/security-scans/scan123/reports/file.txt",
            "digest": "sha256:afa27b44d43b02a9fea41d13cedc2e4016cfcf87c5dbf990e593669aa8ce286d",
        }
    }
    payload = b"hello-world"

    # Should not raise
    enforce_verified_digest(payload, artifact_locations, "raw", "security-scans/scan123/reports/file.txt")


def test_enforce_verified_digest_mismatch():
    artifact_locations = {
        "s3": {
            "uri": "s3://raw/security-scans/scan123/reports/file.txt",
            "digest": "sha256:deadbeef",
        }
    }
    payload = b"hello-world"

    with pytest.raises(ValidationError):
        enforce_verified_digest(payload, artifact_locations, "raw", "security-scans/scan123/reports/file.txt")
