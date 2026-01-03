from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from certus_ask.services import datalake

pytestmark = pytest.mark.integration


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code}}, "HeadBucket")


def test_ensure_bucket_creates_missing_bucket(monkeypatch):
    client = MagicMock()
    client.head_bucket.side_effect = _client_error("404")

    datalake.ensure_bucket(client, "raw-bucket")

    client.create_bucket.assert_called_once_with(Bucket="raw-bucket")


def test_ensure_folders_puts_each_key():
    client = MagicMock()
    datalake.ensure_folders(client, "raw-bucket", ["foo", "bar"])

    calls = [(((), {"Bucket": "raw-bucket", "Key": "foo/"})), ((), {"Bucket": "raw-bucket", "Key": "bar/"})]
    actual = [(call.args, call.kwargs) for call in client.put_object.call_args_list]
    assert actual == calls


def test_upload_directory_dispatches_through_upload_file(monkeypatch, tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "a.txt").write_text("a")
    subdir = root / "nested"
    subdir.mkdir()
    (subdir / "b.txt").write_text("b")

    uploaded = []

    def fake_upload(client, file_path, bucket_name, target_key):
        uploaded.append((bucket_name, target_key))

    monkeypatch.setattr(datalake, "upload_file", fake_upload)

    client = MagicMock()
    datalake.upload_directory(client, root, "raw", target_prefix="prefix")

    assert ("raw", "prefix/a.txt") in uploaded
    assert ("raw", "prefix/nested/b.txt") in uploaded


def test_mask_file_creates_masked_copy(monkeypatch, tmp_path):
    source = tmp_path / "pii.txt"
    source.write_text("My SSN is 123-45-6789", encoding="utf-8")

    monkeypatch.setattr(datalake, "scan_file_for_privacy_data", lambda file_path: ["ENTITY"])

    class DummyAnonymizer:
        def anonymize(self, text, analyzer_results):
            return SimpleNamespace(text="<MASKED>")

    monkeypatch.setattr("certus_ask.services.datalake.get_anonymizer", lambda: DummyAnonymizer())

    masked_path = datalake.mask_file(source)

    assert masked_path.read_text(encoding="utf-8") == "<MASKED>"
    assert masked_path.name.endswith(".masked")


def test_initialize_datalake_structure_invokes_helpers(monkeypatch):
    ensure_bucket = MagicMock()
    ensure_folders = MagicMock()

    monkeypatch.setattr(datalake, "ensure_bucket", ensure_bucket)
    monkeypatch.setattr(datalake, "ensure_folders", ensure_folders)

    client = MagicMock()
    datalake.initialize_datalake_structure(client)

    assert ensure_bucket.call_count == 2
    ensure_folders.assert_called_once()
