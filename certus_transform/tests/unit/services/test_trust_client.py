"""Unit tests for Trust client service."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from certus_transform.services.trust import (
    TrustClient,
    VerifyChainResponse,
    get_trust_client,
)


class TestTrustClientInit:
    """Test TrustClient initialization."""

    def test_trust_client_init_with_defaults(self):
        """Test initialization uses settings by default."""
        with patch("certus_transform.services.trust.settings") as mock_settings:
            mock_settings.trust_base_url = "http://trust.example.com"
            mock_settings.trust_api_key = "test-key"
            mock_settings.trust_verify_ssl = True

            client = TrustClient()

            assert client.base_url == "http://trust.example.com"
            assert client.api_key == "test-key"
            assert client.verify_ssl is True

    def test_trust_client_init_with_custom_values(self):
        """Test custom parameters override settings."""
        with patch("certus_transform.services.trust.settings"):
            client = TrustClient(
                base_url="http://custom.example.com",
                api_key="custom-key",
                verify_ssl=False,
            )

            assert client.base_url == "http://custom.example.com"
            assert client.api_key == "custom-key"
            assert client.verify_ssl is False

    def test_trust_client_init_partial_override(self):
        """Test partial override of settings."""
        with patch("certus_transform.services.trust.settings") as mock_settings:
            mock_settings.trust_base_url = "http://trust.example.com"
            mock_settings.trust_api_key = "default-key"
            mock_settings.trust_verify_ssl = True

            # Override only base_url
            client = TrustClient(base_url="http://override.com")

            assert client.base_url == "http://override.com"
            assert client.api_key == "default-key"
            assert client.verify_ssl is True

    def test_get_trust_client_singleton(self):
        """Test get_trust_client returns singleton instance."""
        with patch("certus_transform.services.trust.settings"):
            # Reset singleton
            import certus_transform.services.trust

            certus_transform.services.trust._trust_client = None

            client1 = get_trust_client()
            client2 = get_trust_client()

            # Should be same instance
            assert client1 is client2


class TestVerifyChain:
    """Test verify_chain method."""

    @pytest.mark.asyncio
    async def test_verify_chain_builds_correct_payload(self):
        """Test payload structure sent to Trust service."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "chain_verified": True,
            "inner_signature_valid": True,
            "outer_signature_valid": True,
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        artifact_locations = {"s3": "s3://bucket/key", "registry": "registry/repo:tag"}
        signatures = {"inner": "sig1", "outer": "sig2"}
        sigstore_entry_id = "uuid-12345"

        with patch("certus_transform.services.trust.httpx.AsyncClient", return_value=mock_client):
            client = TrustClient(base_url="http://trust.example.com")
            await client.verify_chain(artifact_locations, signatures, sigstore_entry_id)

        # Verify payload
        call_args = mock_client.post.call_args
        assert call_args[1]["json"] == {
            "artifact_locations": artifact_locations,
            "signatures": signatures,
            "sigstore_entry_id": sigstore_entry_id,
        }

    @pytest.mark.asyncio
    async def test_verify_chain_uses_authorization_header(self):
        """Test Authorization header when api_key is set."""
        mock_response = Mock()
        mock_response.json.return_value = {"chain_verified": False}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.trust.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            client = TrustClient(base_url="http://trust.example.com", api_key="secret-key")
            await client.verify_chain({}, {})

            # Verify AsyncClient created with Authorization header
            client_call = mock_async_client.call_args
            headers = client_call[1]["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer secret-key"

    @pytest.mark.asyncio
    async def test_verify_chain_no_auth_without_key(self):
        """Test no Authorization header when api_key is None."""
        mock_response = Mock()
        mock_response.json.return_value = {"chain_verified": False}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.trust.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            client = TrustClient(base_url="http://trust.example.com", api_key=None)
            await client.verify_chain({}, {})

            # Verify no Authorization header or empty
            client_call = mock_async_client.call_args
            headers = client_call[1]["headers"]
            assert not headers or "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_verify_chain_endpoint_url(self):
        """Test endpoint path is /v1/verify-chain."""
        mock_response = Mock()
        mock_response.json.return_value = {"chain_verified": True}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.trust.httpx.AsyncClient", return_value=mock_client):
            client = TrustClient(base_url="http://trust.example.com")
            await client.verify_chain({}, {})

        # Verify endpoint path
        call_args = mock_client.post.call_args[0]
        assert call_args[0] == "/v1/verify-chain"

    @pytest.mark.asyncio
    async def test_verify_chain_timeout(self):
        """Test timeout is set to 60.0."""
        mock_response = Mock()
        mock_response.json.return_value = {"chain_verified": True}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.trust.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            client = TrustClient(base_url="http://trust.example.com")
            await client.verify_chain({}, {})

            # Verify timeout
            client_call = mock_async_client.call_args
            assert client_call[1]["timeout"] == 60.0

    @pytest.mark.asyncio
    async def test_verify_chain_response_parsing(self):
        """Test VerifyChainResponse is created from response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "chain_verified": True,
            "inner_signature_valid": True,
            "outer_signature_valid": False,
            "signer_inner": "certus-assurance@certus.cloud",
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.trust.httpx.AsyncClient", return_value=mock_client):
            client = TrustClient(base_url="http://trust.example.com")
            result = await client.verify_chain({}, {})

        assert isinstance(result, VerifyChainResponse)
        assert result.chain_verified is True

    @pytest.mark.asyncio
    async def test_verify_chain_http_error_handling(self):
        """Test HTTP error propagates from raise_for_status."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "500 Server Error",
                request=Mock(),
                response=Mock(status_code=500),
            )
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.trust.httpx.AsyncClient", return_value=mock_client):
            client = TrustClient(base_url="http://trust.example.com")

            with pytest.raises(httpx.HTTPStatusError):
                await client.verify_chain({}, {})

    @pytest.mark.asyncio
    async def test_verify_chain_verify_ssl_configuration(self):
        """Test verify_ssl setting is passed to AsyncClient."""
        mock_response = Mock()
        mock_response.json.return_value = {"chain_verified": True}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("certus_transform.services.trust.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            client = TrustClient(base_url="http://trust.example.com", verify_ssl=False)
            await client.verify_chain({}, {})

            # Verify verify=False
            client_call = mock_async_client.call_args
            assert client_call[1]["verify"] is False


class TestVerifyChainResponse:
    """Test VerifyChainResponse properties."""

    def test_verify_chain_response_chain_verified_property(self):
        """Test chain_verified property."""
        response_true = VerifyChainResponse({"chain_verified": True})
        assert response_true.chain_verified is True

        response_false = VerifyChainResponse({"chain_verified": False})
        assert response_false.chain_verified is False

        response_missing = VerifyChainResponse({})
        assert response_missing.chain_verified is False

    def test_verify_chain_response_verification_proof_property(self):
        """Test verification_proof property returns all fields."""
        data = {
            "chain_verified": True,
            "inner_signature_valid": True,
            "outer_signature_valid": True,
            "chain_unbroken": True,
            "signer_inner": "certus-assurance@certus.cloud",
            "signer_outer": "certus-trust@certus.cloud",
            "sigstore_timestamp": "2025-12-18T10:00:00Z",
            "non_repudiation": True,
        }

        response = VerifyChainResponse(data)
        proof = response.verification_proof

        assert proof["chain_verified"] is True
        assert proof["inner_signature_valid"] is True
        assert proof["outer_signature_valid"] is True
        assert proof["chain_unbroken"] is True
        assert proof["signer_inner"] == "certus-assurance@certus.cloud"
        assert proof["signer_outer"] == "certus-trust@certus.cloud"
        assert proof["sigstore_timestamp"] == "2025-12-18T10:00:00Z"
        assert proof["non_repudiation"] is True

    def test_verify_chain_response_verification_proof_missing_fields(self):
        """Test verification_proof handles missing optional fields."""
        data = {
            "chain_verified": False,
            "inner_signature_valid": False,
        }

        response = VerifyChainResponse(data)
        proof = response.verification_proof

        assert proof["chain_verified"] is False
        assert proof["inner_signature_valid"] is False
        assert proof["outer_signature_valid"] is False  # Default
        assert proof["signer_inner"] is None
        assert proof["signer_outer"] is None

    def test_verify_chain_response_raw_property(self):
        """Test raw property returns original data dict."""
        data = {
            "chain_verified": True,
            "custom_field": "custom_value",
            "inner_signature_valid": True,
        }

        response = VerifyChainResponse(data)
        raw = response.raw

        assert raw == data
        assert raw["custom_field"] == "custom_value"

    def test_verify_chain_response_constructor_with_dict(self):
        """Test VerifyChainResponse accepts dict in constructor."""
        # The current implementation expects a dict, not **kwargs
        data = {"chain_verified": True, "test_field": "test_value"}
        response = VerifyChainResponse(data)

        assert response._data == data
        assert response._data["test_field"] == "test_value"
