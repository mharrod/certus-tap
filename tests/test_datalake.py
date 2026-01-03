import boto3
import pytest
from moto import mock_aws

from certus_ask.core.config import settings
from certus_ask.core.exceptions import StorageError
from certus_ask.routers import datalake
from certus_ask.schemas.datalake import BatchPreprocessRequest, PreprocessRequest

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def override_settings(monkeypatch):
    raw_original = settings.datalake_raw_bucket
    golden_original = settings.datalake_golden_bucket
    folders_original = settings.datalake_default_folders
    settings.datalake_raw_bucket = "raw-bucket"
    settings.datalake_golden_bucket = "golden-bucket"
    settings.datalake_default_folders = []
    yield
    settings.datalake_raw_bucket = raw_original
    settings.datalake_golden_bucket = golden_original
    settings.datalake_default_folders = folders_original


@pytest.fixture
def moto_s3(monkeypatch):
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="raw-bucket")
        s3.create_bucket(Bucket="golden-bucket")
        monkeypatch.setattr(datalake, "get_s3_client", lambda: s3)
        yield s3


@pytest.mark.asyncio
async def test_promote_preserves_original_filename(moto_s3):
    moto_s3.put_object(
        Bucket="raw-bucket",
        Key="privacy-pack/incoming/privacy-quickstart.md",
        Body=b"secret",
    )

    request = PreprocessRequest(
        source_key="privacy-pack/incoming/privacy-quickstart.md",
        destination_prefix="privacy-pack/golden",
    )
    response = await datalake.promote_object(request)

    assert "privacy-pack/golden/privacy-quickstart.md" in response["message"]
    head = moto_s3.head_object(
        Bucket="golden-bucket",
        Key="privacy-pack/golden/privacy-quickstart.md",
    )
    assert head["ResponseMetadata"]["HTTPStatusCode"] == 200


@pytest.mark.asyncio
async def test_promote_batch_preserves_all_filenames(moto_s3):
    keys = [
        "privacy-pack/incoming/customer-onboarding.md",
        "privacy-pack/incoming/privacy-quickstart.md",
    ]
    for key in keys:
        moto_s3.put_object(Bucket="raw-bucket", Key=key, Body=f"body for {key}".encode())

    request = BatchPreprocessRequest(
        source_prefix="privacy-pack/incoming/",
        destination_prefix="privacy-pack/golden",
    )
    await datalake.promote_prefix(request)

    for key in keys:
        golden_key = key.replace("incoming", "golden", 1)
        head = moto_s3.head_object(Bucket="golden-bucket", Key=golden_key)
        assert head["ResponseMetadata"]["HTTPStatusCode"] == 200


@pytest.mark.asyncio
async def test_promote_requires_verification_proof(moto_s3):
    moto_s3.put_object(
        Bucket="raw-bucket",
        Key="security-scans/scan123/scan123/reports/sarif.json",
        Body=b"{}",
    )

    request = PreprocessRequest(
        source_key="security-scans/scan123/scan123/reports/sarif.json",
        destination_prefix="security-scans/scan123/golden",
    )

    with pytest.raises(StorageError):
        await datalake.promote_object(request)


@pytest.mark.asyncio
async def test_promote_allows_verified_scans(moto_s3):
    moto_s3.put_object(
        Bucket="raw-bucket",
        Key="security-scans/scan456/scan456/reports/sarif.json",
        Body=b"{}",
    )
    moto_s3.put_object(
        Bucket="raw-bucket",
        Key="security-scans/scan456/scan456/verification-proof.json",
        Body=b'{"chain_verified": true}',
    )

    request = PreprocessRequest(
        source_key="security-scans/scan456/scan456/reports/sarif.json",
        destination_prefix="security-scans/scan456/golden",
    )

    response = await datalake.promote_object(request)
    assert "Promoted security-scans/scan456/scan456/reports/sarif.json" in response["message"]
