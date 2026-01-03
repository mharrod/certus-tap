"""Unit tests for S3 client initialization and configuration."""

from unittest.mock import Mock, patch

from certus_transform.services.s3_client import get_s3_client


class TestGetS3Client:
    """Test S3 client initialization and memoization."""

    def test_get_s3_client_returns_boto3_client(self):
        """Test returns boto3 S3 client."""
        with patch("certus_transform.services.s3_client.boto3.client") as mock_boto:
            mock_client = Mock()
            mock_boto.return_value = mock_client

            # Clear cache first
            get_s3_client.cache_clear()

            client = get_s3_client()

            assert client == mock_client
            mock_boto.assert_called_once_with(
                "s3",
                endpoint_url=mock_boto.call_args[1]["endpoint_url"],
                aws_access_key_id=mock_boto.call_args[1]["aws_access_key_id"],
                aws_secret_access_key=mock_boto.call_args[1]["aws_secret_access_key"],
                region_name=mock_boto.call_args[1]["region_name"],
            )

    def test_get_s3_client_memoization(self):
        """Test lru_cache returns same instance on repeated calls."""
        with patch("certus_transform.services.s3_client.boto3.client") as mock_boto:
            mock_client = Mock()
            mock_boto.return_value = mock_client

            # Clear cache
            get_s3_client.cache_clear()

            # First call
            client1 = get_s3_client()
            # Second call
            client2 = get_s3_client()

            # Should be same instance
            assert client1 is client2
            # boto3.client should only be called once due to caching
            assert mock_boto.call_count == 1

    def test_get_s3_client_configuration(self):
        """Test client is configured with settings values."""
        with patch("certus_transform.services.s3_client.boto3.client") as mock_boto:
            with patch("certus_transform.services.s3_client.settings") as mock_settings:
                mock_settings.s3_endpoint_url = "http://localhost:4566"
                mock_settings.aws_access_key_id = "test-access-key"
                mock_settings.aws_secret_access_key = "test-secret-key"
                mock_settings.aws_region = "us-west-2"

                get_s3_client.cache_clear()
                get_s3_client()

                mock_boto.assert_called_once()
                call_kwargs = mock_boto.call_args[1]

                assert call_kwargs["endpoint_url"] == "http://localhost:4566"
                assert call_kwargs["aws_access_key_id"] == "test-access-key"
                assert call_kwargs["aws_secret_access_key"] == "test-secret-key"
                assert call_kwargs["region_name"] == "us-west-2"

    def test_get_s3_client_with_custom_endpoint(self):
        """Test client uses custom endpoint from settings."""
        with patch("certus_transform.services.s3_client.boto3.client") as mock_boto:
            with patch("certus_transform.services.s3_client.settings") as mock_settings:
                mock_settings.s3_endpoint_url = "http://custom-s3.example.com:9000"
                mock_settings.aws_access_key_id = "key"
                mock_settings.aws_secret_access_key = "secret"
                mock_settings.aws_region = "us-east-1"

                get_s3_client.cache_clear()
                get_s3_client()

                call_kwargs = mock_boto.call_args[1]
                assert call_kwargs["endpoint_url"] == "http://custom-s3.example.com:9000"

    def test_get_s3_client_service_name(self):
        """Test client is created for 's3' service."""
        with patch("certus_transform.services.s3_client.boto3.client") as mock_boto:
            get_s3_client.cache_clear()
            get_s3_client()

            # First positional arg should be 's3'
            assert mock_boto.call_args[0][0] == "s3"

    def test_get_s3_client_cache_info(self):
        """Test cache statistics are tracked."""
        with patch("certus_transform.services.s3_client.boto3.client") as mock_boto:
            mock_boto.return_value = Mock()

            get_s3_client.cache_clear()

            # First call - cache miss
            get_s3_client()
            cache_info = get_s3_client.cache_info()
            assert cache_info.misses == 1
            assert cache_info.hits == 0

            # Second call - cache hit
            get_s3_client()
            cache_info = get_s3_client.cache_info()
            assert cache_info.hits == 1

    def test_get_s3_client_cache_clear(self):
        """Test cache can be cleared."""
        with patch("certus_transform.services.s3_client.boto3.client") as mock_boto:
            mock_boto.return_value = Mock()

            get_s3_client.cache_clear()
            get_s3_client()

            # Clear cache
            get_s3_client.cache_clear()

            # Next call should create new client
            get_s3_client()

            # Should have 2 boto3.client calls (before and after clear)
            assert mock_boto.call_count == 2
