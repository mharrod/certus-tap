"""Unit tests for SaaS service integration."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from certus_transform.services.saas import ingest_security_keys


class TestIngestSecurityKeys:
    """Test SaaS ingestion service."""

    @pytest.mark.asyncio
    async def test_ingest_security_keys_empty_keys_returns_empty(self):
        """Test empty keys sequence returns empty list."""
        result = await ingest_security_keys("workspace-id", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_ingest_security_keys_builds_correct_payload(self):
        """Test payload structure for each key."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "indexed"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.saas.httpx.AsyncClient", return_value=mock_client):
            with patch("certus_transform.services.saas.settings") as mock_settings:
                mock_settings.golden_bucket = "golden-bucket"
                mock_settings.saas_api_key = None
                mock_settings.saas_base_url = "http://saas.example.com"
                mock_settings.saas_verify_ssl = True

                await ingest_security_keys("test-workspace", ["scans/trivy.json"])

        # Verify post was called with correct payload
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args

        assert call_args[0][0] == "/v1/test-workspace/index/security/s3"
        assert call_args[1]["json"] == {
            "bucket_name": "golden-bucket",
            "key": "scans/trivy.json",
        }

    @pytest.mark.asyncio
    async def test_ingest_security_keys_uses_authorization_header(self):
        """Test Authorization header when api_key is set."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.saas.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            with patch("certus_transform.services.saas.settings") as mock_settings:
                mock_settings.saas_api_key = "secret-api-key"
                mock_settings.golden_bucket = "bucket"
                mock_settings.saas_base_url = "http://saas.example.com"
                mock_settings.saas_verify_ssl = True

                await ingest_security_keys("workspace", ["key1.json"])

            # Verify AsyncClient was created with Authorization header
            client_call = mock_async_client.call_args
            headers = client_call[1]["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer secret-api-key"

    @pytest.mark.asyncio
    async def test_ingest_security_keys_no_auth_without_key(self):
        """Test no Authorization header when api_key is None."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.saas.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            with patch("certus_transform.services.saas.settings") as mock_settings:
                mock_settings.saas_api_key = None
                mock_settings.golden_bucket = "bucket"
                mock_settings.saas_base_url = "http://saas.example.com"
                mock_settings.saas_verify_ssl = True

                await ingest_security_keys("workspace", ["key1.json"])

            # Verify AsyncClient headers don't include Authorization
            client_call = mock_async_client.call_args
            headers = client_call[1]["headers"]
            assert "Authorization" not in headers or headers["Authorization"] is None

    @pytest.mark.asyncio
    async def test_ingest_security_keys_endpoint_url_construction(self):
        """Test endpoint URL format."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.saas.httpx.AsyncClient", return_value=mock_client):
            with patch("certus_transform.services.saas.settings") as mock_settings:
                mock_settings.golden_bucket = "bucket"
                mock_settings.saas_api_key = None
                mock_settings.saas_base_url = "http://saas.example.com"
                mock_settings.saas_verify_ssl = True

                await ingest_security_keys("my-workspace", ["test.json"])

        # Check endpoint path format
        call_args = mock_client.post.call_args[0]
        assert call_args[0] == "/v1/my-workspace/index/security/s3"

    @pytest.mark.asyncio
    async def test_ingest_security_keys_ssl_verification(self):
        """Test SSL verification setting."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.saas.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            with patch("certus_transform.services.saas.settings") as mock_settings:
                mock_settings.saas_verify_ssl = False
                mock_settings.golden_bucket = "bucket"
                mock_settings.saas_api_key = None
                mock_settings.saas_base_url = "http://saas.example.com"

                await ingest_security_keys("workspace", ["key.json"])

            # Verify verify=False was passed
            client_call = mock_async_client.call_args
            assert client_call[1]["verify"] is False

    @pytest.mark.asyncio
    async def test_ingest_security_keys_timeout_configuration(self):
        """Test timeout is set to 60.0."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.saas.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            with patch("certus_transform.services.saas.settings") as mock_settings:
                mock_settings.golden_bucket = "bucket"
                mock_settings.saas_api_key = None
                mock_settings.saas_base_url = "http://saas.example.com"
                mock_settings.saas_verify_ssl = True

                await ingest_security_keys("workspace", ["key.json"])

            # Verify timeout=60.0 was passed
            client_call = mock_async_client.call_args
            assert client_call[1]["timeout"] == 60.0

    @pytest.mark.asyncio
    async def test_ingest_security_keys_multiple_keys(self):
        """Test multiple keys result in multiple POST requests."""
        mock_response = AsyncMock()
        mock_response.json.side_effect = [
            {"status": "indexed", "key": "key1"},
            {"status": "indexed", "key": "key2"},
            {"status": "indexed", "key": "key3"},
        ]
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.saas.httpx.AsyncClient", return_value=mock_client):
            with patch("certus_transform.services.saas.settings") as mock_settings:
                mock_settings.golden_bucket = "bucket"
                mock_settings.saas_api_key = None
                mock_settings.saas_base_url = "http://saas.example.com"
                mock_settings.saas_verify_ssl = True

                results = await ingest_security_keys("workspace", ["key1.json", "key2.sarif", "key3.json"])

        # Should make 3 POST calls
        assert mock_client.post.call_count == 3
        # Should return 3 results
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_ingest_security_keys_handles_http_error(self):
        """Test HTTP error propagates from raise_for_status."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "404 Not Found",
                request=Mock(),
                response=Mock(status_code=404),
            )
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.saas.httpx.AsyncClient", return_value=mock_client):
            with patch("certus_transform.services.saas.settings") as mock_settings:
                mock_settings.golden_bucket = "bucket"
                mock_settings.saas_api_key = None
                mock_settings.saas_base_url = "http://saas.example.com"
                mock_settings.saas_verify_ssl = True

                with pytest.raises(httpx.HTTPStatusError):
                    await ingest_security_keys("workspace", ["key.json"])

    @pytest.mark.asyncio
    async def test_ingest_security_keys_base_url_configuration(self):
        """Test base_url is set from settings."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.saas.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            with patch("certus_transform.services.saas.settings") as mock_settings:
                mock_settings.saas_base_url = "https://custom-saas.certus.cloud"
                mock_settings.golden_bucket = "bucket"
                mock_settings.saas_api_key = None
                mock_settings.saas_verify_ssl = True

                await ingest_security_keys("workspace", ["key.json"])

            # Verify base_url
            client_call = mock_async_client.call_args
            assert client_call[1]["base_url"] == "https://custom-saas.certus.cloud"
