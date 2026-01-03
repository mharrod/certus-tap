from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from certus_transform.services.privacy import scan_prefix


class _StubAnalyzer:
    def analyze(self, text: str, language: str = "en"):
        return ["PII"] if "Secret" in text else []


@pytest.fixture
def fake_analyzer(monkeypatch):
    monkeypatch.setattr("certus_transform.services.privacy.get_analyzer", lambda: _StubAnalyzer())


@pytest.fixture
def fake_s3_client(monkeypatch):
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="raw")
        monkeypatch.setattr("certus_transform.services.privacy.get_s3_client", lambda: client)
        yield client


def _seed_objects(client):
    client.put_object(Bucket="raw", Key="security-scans/scan123/clean.txt", Body=b"Hello world")
    client.put_object(Bucket="raw", Key="security-scans/scan123/pii.txt", Body=b"Secret SSN 123")
    client.put_object(
        Bucket="raw",
        Key="security-scans/scan123/verification-proof.json",
        Body=b"Secret verifier email",
    )
    client.put_object(
        Bucket="raw",
        Key="security-scans/scan123/scan.json",
        Body=b"Secret metadata",
    )


def test_scan_prefix_quarantines_objects(fake_s3_client, fake_analyzer):
    _seed_objects(fake_s3_client)

    summary = scan_prefix(bucket="raw", prefix="security-scans/scan123/")

    assert summary.quarantined == 1
    assert summary.clean == 1
    quarantined_keys = [r.key for r in summary.results if r.quarantined]
    assert quarantined_keys == ["security-scans/scan123/pii.txt"]

    # ensure object moved
    resp = fake_s3_client.list_objects_v2(Bucket="raw", Prefix="security-scans/scan123/quarantine/")
    keys = [item["Key"] for item in resp.get("Contents", [])]
    assert "security-scans/scan123/quarantine/pii.txt" in keys


def test_scan_prefix_dry_run_does_not_move(fake_s3_client, fake_analyzer):
    _seed_objects(fake_s3_client)

    summary = scan_prefix(bucket="raw", prefix="security-scans/scan123/", dry_run=True)

    assert summary.quarantined == 1

    resp = fake_s3_client.list_objects_v2(Bucket="raw", Prefix="security-scans/scan123/")
    keys = [item["Key"] for item in resp.get("Contents", [])]
    assert "security-scans/scan123/pii.txt" in keys


def test_scan_prefix_skips_verification_metadata(fake_s3_client, fake_analyzer):
    _seed_objects(fake_s3_client)

    summary = scan_prefix(bucket="raw", prefix="security-scans/scan123/")

    tracked_keys = [result.key for result in summary.results]
    assert "security-scans/scan123/verification-proof.json" not in tracked_keys
    assert "security-scans/scan123/scan.json" not in tracked_keys

    resp = fake_s3_client.list_objects_v2(Bucket="raw", Prefix="security-scans/scan123/")
    keys = [item["Key"] for item in resp.get("Contents", [])]
    assert "security-scans/scan123/verification-proof.json" in keys
    assert "security-scans/scan123/scan.json" in keys
