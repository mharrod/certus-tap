"""Unit tests for privacy service PII scanning logic."""

from unittest.mock import Mock, patch

from certus_transform.services.privacy import (
    PrivacyScanResult,
    PrivacyScanSummary,
    _format_report,
    scan_active_prefix,
    scan_prefix,
)


class TestFormatReport:
    """Test report formatting logic."""

    def test_format_report_single_result(self):
        """Test report with single quarantined file."""
        results = [PrivacyScanResult(key="test/file.txt", quarantined=True, findings=3)]
        report = _format_report("my-bucket", results)
        assert report == "[BLOCK] s3://my-bucket/test/file.txt\n"

    def test_format_report_mixed_results(self):
        """Test report with mix of OK and BLOCK results."""
        results = [
            PrivacyScanResult(key="clean.txt", quarantined=False, findings=0),
            PrivacyScanResult(key="pii.txt", quarantined=True, findings=2),
            PrivacyScanResult(key="safe.json", quarantined=False, findings=0),
        ]
        report = _format_report("bucket", results)
        lines = report.strip().split("\n")
        assert len(lines) == 3
        assert "[OK] s3://bucket/clean.txt" in lines
        assert "[BLOCK] s3://bucket/pii.txt" in lines
        assert "[OK] s3://bucket/safe.json" in lines

    def test_format_report_empty_results(self):
        """Test report with no results."""
        results = []
        report = _format_report("bucket", results)
        assert report == "No objects scanned.\n"

    def test_format_report_special_characters_in_keys(self):
        """Test keys with special characters pass through unchanged."""
        results = [PrivacyScanResult(key="test/file with spaces.txt", quarantined=False, findings=0)]
        report = _format_report("bucket", results)
        assert "[OK] s3://bucket/test/file with spaces.txt" in report


class TestScanPrefix:
    """Test core scan_prefix business logic."""

    def test_scan_prefix_normalizes_prefixes_with_slashes(self):
        """Test prefix normalization adds trailing slash."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        # Empty result set
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Contents": []}]
        mock_s3.get_paginator.return_value = mock_paginator

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "test/prefix", quarantine_prefix="quarantine")

        # Should normalize to "test/prefix/"
        assert result.prefix == "test/prefix/"
        # Quarantine should be "quarantine/"
        assert result.quarantine_prefix == "quarantine/"

    def test_scan_prefix_quarantine_defaults_correctly(self):
        """Test quarantine_prefix defaults to prefix/quarantine/ when not specified."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Contents": []}]
        mock_s3.get_paginator.return_value = mock_paginator

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "active/")

        # Default quarantine should be "active/quarantine/"
        assert result.quarantine_prefix == "active/quarantine/"

    def test_scan_prefix_counts_consistency(self):
        """Test scanned = clean + quarantined."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        # Mock 3 files: 2 clean, 1 with PII
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "active/clean1.txt"},
                    {"Key": "active/pii.txt"},
                    {"Key": "active/clean2.json"},
                ]
            }
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        # Mock file reads
        mock_s3.get_object.side_effect = [
            {"Body": Mock(read=lambda: b"no sensitive data")},
            {"Body": Mock(read=lambda: b"SSN: 123-45-6789")},
            {"Body": Mock(read=lambda: b"clean data")},
        ]

        # Mock analyzer: first and third return empty, second returns findings
        mock_analyzer.analyze.side_effect = [
            [],  # clean1.txt
            [Mock()],  # pii.txt - has findings
            [],  # clean2.json
        ]

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "active/", dry_run=True)

        assert result.scanned == 3
        assert result.clean == 2
        assert result.quarantined == 1
        assert result.scanned == result.clean + result.quarantined

    def test_scan_prefix_skip_file_basenames(self):
        """Test files in SKIP_FILE_BASENAMES are skipped."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        # Include verification-proof.json which should be skipped
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "active/verification-proof.json"},
                    {"Key": "active/scan.json"},
                    {"Key": "active/regular.txt"},
                ]
            }
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        # Only regular.txt should be scanned
        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"content")}
        mock_analyzer.analyze.return_value = []

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "active/")

        # Only 1 file should be scanned (regular.txt)
        assert result.scanned == 1
        assert mock_s3.get_object.call_count == 1

    def test_scan_prefix_skip_quarantine_directory(self):
        """Test objects in quarantine_prefix are not re-scanned."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "active/file.txt"},
                    {"Key": "active/quarantine/blocked.txt"},  # Should skip
                ]
            }
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"content")}
        mock_analyzer.analyze.return_value = []

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "active/")

        # Only 1 file scanned (quarantine file skipped)
        assert result.scanned == 1

    def test_scan_prefix_dry_run_mode(self):
        """Test dry_run=True doesn't call delete/copy_object."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "active/pii.txt"}]}]
        mock_s3.get_paginator.return_value = mock_paginator

        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"SSN: 123-45-6789")}
        mock_analyzer.analyze.return_value = [Mock()]  # Has findings

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "active/", dry_run=True)

        # Should detect quarantine but not execute
        assert result.quarantined == 1
        mock_s3.copy_object.assert_not_called()
        mock_s3.delete_object.assert_not_called()

    def test_scan_prefix_s3_operations_on_findings(self):
        """Test copy_object and delete_object called correctly when findings detected."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "active/sensitive.txt"}]}]
        mock_s3.get_paginator.return_value = mock_paginator

        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"PII data")}
        mock_analyzer.analyze.return_value = [Mock(), Mock()]  # 2 findings

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "active/", dry_run=False)

        # Should quarantine
        assert result.quarantined == 1
        mock_s3.copy_object.assert_called_once()
        mock_s3.delete_object.assert_called_once()

        # Verify copy source and destination
        copy_call = mock_s3.copy_object.call_args
        assert copy_call[1]["CopySource"]["Bucket"] == "bucket"
        assert copy_call[1]["CopySource"]["Key"] == "active/sensitive.txt"
        assert copy_call[1]["Bucket"] == "bucket"
        assert "quarantine" in copy_call[1]["Key"]

    def test_scan_prefix_handles_encoding_errors(self):
        """Test UTF-8 decoding with errors='ignore'."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "active/binary.dat"}]}]
        mock_s3.get_paginator.return_value = mock_paginator

        # Binary content that can't be decoded as UTF-8
        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"\xff\xfe\x00\x01binary")}
        mock_analyzer.analyze.return_value = []

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                # Should not raise exception
                result = scan_prefix("bucket", "active/")

        assert result.scanned == 1
        # Verify analyzer was called (even with partial decode)
        mock_analyzer.analyze.assert_called_once()

    def test_scan_prefix_report_generation(self):
        """Test report_key creates plaintext report in S3."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "active/file.txt"}]}]
        mock_s3.get_paginator.return_value = mock_paginator

        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"content")}
        mock_analyzer.analyze.return_value = []

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "active/", report_key="reports/scan-report.txt")

        # Should write report
        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args
        assert call_args[1]["Bucket"] == "bucket"
        assert call_args[1]["Key"] == "reports/scan-report.txt"
        assert b"[OK] s3://bucket/active/file.txt" in call_args[1]["Body"]
        assert result.report_object == "reports/scan-report.txt"

    def test_scan_prefix_empty_prefix_scan(self):
        """Test with empty S3 prefix."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        mock_paginator = Mock()
        # No objects
        mock_paginator.paginate.return_value = [{}]
        mock_s3.get_paginator.return_value = mock_paginator

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "empty/")

        assert result.scanned == 0
        assert result.clean == 0
        assert result.quarantined == 0

    def test_scan_prefix_with_multiple_findings(self):
        """Test analyzer returning multiple findings."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "active/multi-pii.txt"}]}]
        mock_s3.get_paginator.return_value = mock_paginator

        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"SSN: 123-45-6789, Email: test@example.com")}
        # Return 5 findings
        mock_analyzer.analyze.return_value = [Mock() for _ in range(5)]

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "active/", dry_run=True)

        assert result.quarantined == 1
        assert result.results[0].findings == 5

    def test_scan_prefix_skips_directory_markers(self):
        """Test that directory markers (keys ending with /) are skipped."""
        mock_s3 = Mock()
        mock_analyzer = Mock()

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "active/"},  # Directory marker
                    {"Key": "active/subdir/"},  # Directory marker
                    {"Key": "active/file.txt"},  # Actual file
                ]
            }
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"content")}
        mock_analyzer.analyze.return_value = []

        with patch("certus_transform.services.privacy.get_s3_client", return_value=mock_s3):
            with patch("certus_transform.services.privacy.get_analyzer", return_value=mock_analyzer):
                result = scan_prefix("bucket", "active/")

        # Only 1 file scanned (directory markers skipped)
        assert result.scanned == 1


class TestScanActivePrefix:
    """Test backwards-compatible scan_active_prefix helper."""

    def test_scan_active_prefix_uses_defaults(self):
        """Test uses settings.raw_bucket and settings.active_prefix."""
        with patch("certus_transform.services.privacy.scan_prefix") as mock_scan:
            with patch("certus_transform.services.privacy.settings") as mock_settings:
                mock_settings.raw_bucket = "my-raw-bucket"
                mock_settings.active_prefix = "active/"
                mock_settings.quarantine_prefix = "quarantine/"

                mock_scan.return_value = PrivacyScanSummary(
                    bucket="my-raw-bucket",
                    prefix="active/",
                    quarantine_prefix="quarantine/",
                    scanned=0,
                    quarantined=0,
                    clean=0,
                    results=[],
                )

                scan_active_prefix()

                mock_scan.assert_called_once_with(
                    bucket="my-raw-bucket",
                    prefix="active/",
                    quarantine_prefix="quarantine/",
                )

    def test_scan_active_prefix_custom_prefix(self):
        """Test custom prefix overrides default."""
        with patch("certus_transform.services.privacy.scan_prefix") as mock_scan:
            with patch("certus_transform.services.privacy.settings") as mock_settings:
                mock_settings.raw_bucket = "bucket"
                mock_settings.quarantine_prefix = "quarantine/"

                mock_scan.return_value = PrivacyScanSummary(
                    bucket="bucket",
                    prefix="custom/",
                    quarantine_prefix="quarantine/",
                    scanned=0,
                    quarantined=0,
                    clean=0,
                    results=[],
                )

                scan_active_prefix(prefix="custom/")

                call_args = mock_scan.call_args
                assert call_args[1]["prefix"] == "custom/"

    def test_scan_active_prefix_returns_results_list(self):
        """Test returns list of PrivacyScanResult objects."""
        results = [
            PrivacyScanResult(key="file1.txt", quarantined=False, findings=0),
            PrivacyScanResult(key="file2.txt", quarantined=True, findings=2),
        ]

        with patch("certus_transform.services.privacy.scan_prefix") as mock_scan:
            with patch("certus_transform.services.privacy.settings"):
                mock_scan.return_value = PrivacyScanSummary(
                    bucket="bucket",
                    prefix="active/",
                    quarantine_prefix="quarantine/",
                    scanned=2,
                    quarantined=1,
                    clean=1,
                    results=results,
                )

                result = scan_active_prefix()

                assert len(result) == 2
                assert result[0].key == "file1.txt"
                assert result[1].quarantined is True
