import httpx
import pytest

from certus_ask.services.trust import TrustClient


@pytest.fixture(autouse=True)
def override_trust_settings(monkeypatch):
    """Provide deterministic Trust settings for tests."""

    class DummySettings:
        trust_base_url = "https://trust.local"
        trust_api_key = "test-key"
        trust_verify_ssl = False

    monkeypatch.setattr("certus_ask.services.trust.get_settings", lambda: DummySettings())


class DummyResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {"chain_verified": True}
        self.status_code = status_code
        self.text = ""
        self.content = b""
        self.request = httpx.Request("POST", "https://trust.local/v1/verify-chain")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=self.request, response=self)


@pytest.mark.asyncio
async def test_verify_chain_sends_auth_header(monkeypatch):
    """Trust client should attach Authorization headers and return parsed response."""
    captured = {}

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["headers"] = kwargs.get("headers")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, path, json):
            captured["path"] = path
            captured["payload"] = json
            return DummyResponse()

    monkeypatch.setattr("certus_ask.services.trust.httpx.AsyncClient", DummyAsyncClient)

    client = TrustClient()
    result = await client.verify_chain({"s3": {}}, {"inner": {}}, sigstore_entry_id="sig-1")

    assert result.chain_verified is True
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["path"] == "/v1/verify-chain"
    assert captured["payload"]["sigstore_entry_id"] == "sig-1"


@pytest.mark.asyncio
async def test_verify_chain_retries_on_timeout(monkeypatch):
    """verify_chain should retry when transient httpx.TimeoutException occurs."""
    attempts = {"count": 0}

    class FlakyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, path, json):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise httpx.TimeoutException("timeout")
            return DummyResponse()

    monkeypatch.setattr("certus_ask.services.trust.httpx.AsyncClient", FlakyAsyncClient)
    monkeypatch.setattr("tenacity.wait.wait_exponential.__call__", lambda self, state: 0)

    client = TrustClient()
    result = await client.verify_chain({"s3": {}}, {"inner": {}})

    assert attempts["count"] == 3
    assert result.chain_verified is True
