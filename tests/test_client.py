"""Tests for DaskClient — token management, retries, and rate limiting."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.client.dask_client import ApiError, DaskClient, TokenError
from src.config import Config


@pytest.fixture
def config() -> Config:
    """Return a test config with fast settings."""
    return Config(
        base_url="https://adreskodu.dask.gov.tr",
        request_delay=0.0,  # No delay in tests
        max_retries=2,
        retry_delay=0.0,
        request_timeout=5,
    )


@pytest.fixture
def client(config: Config) -> DaskClient:
    """Return a DaskClient instance."""
    return DaskClient(config)


class TestTokenManagement:
    """Tests for token fetching and cleanup."""

    def test_clean_token_replaces_plus_and_equals(self, client: DaskClient):
        """Token cleaning should replace + with space and remove =."""
        result = client._clean_token("abc+def=ghi+jkl==")
        assert result == "abc defghi jkl"

    def test_clean_token_no_changes_needed(self, client: DaskClient):
        """Token with no special chars should pass through unchanged."""
        result = client._clean_token("simpletoken")
        assert result == "simpletoken"

    @patch("src.client.dask_client.requests.Session.get")
    def test_fetch_token_success(self, mock_get, client: DaskClient):
        """Successful token fetch should clean and store the token."""
        mock_resp = MagicMock()
        mock_resp.text = "abc+def=123"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        token = client.fetch_token()
        assert token == "abc def123"

    @patch("src.client.dask_client.requests.Session.get")
    def test_fetch_token_empty_falls_back(self, mock_get, client: DaskClient):
        """Empty token response should fall back to empty string (no raise)."""
        mock_resp = MagicMock()
        mock_resp.text = "  "
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        token = client.fetch_token()
        assert token == ""

    @patch("src.client.dask_client.requests.Session.get")
    def test_fetch_token_retries_on_failure(self, mock_get, client: DaskClient):
        """Should retry on network errors and fall back to empty token."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        token = client.fetch_token()
        assert token == ""
        assert mock_get.call_count == 2

    @patch("src.client.dask_client.requests.Session.get")
    def test_refresh_token_clears_old(self, mock_get, client: DaskClient):
        """refresh_token should clear old token and fetch new one."""
        mock_resp = MagicMock()
        mock_resp.text = "new+token="
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client._token = "old token"
        new = client.refresh_token()
        assert new == "new token"
        assert client._token == "new token"


class TestLoad:
    """Tests for the load() method (core API requests)."""

    @patch("src.client.dask_client.requests.Session.post")
    @patch("src.client.dask_client.requests.Session.get")
    def test_load_success(self, mock_get, mock_post, client: DaskClient):
        """Successful load should return response text."""
        # Token fetch
        token_resp = MagicMock()
        token_resp.text = "tok+en="
        token_resp.raise_for_status = MagicMock()
        mock_get.return_value = token_resp

        # Load response
        load_resp = MagicMock()
        load_resp.status_code = 200
        load_resp.text = '{"yt": [{"value": "1", "text": "ADANA"}]}'
        load_resp.raise_for_status = MagicMock()
        mock_post.return_value = load_resp

        result = client.load("il", 0)
        assert "ADANA" in result

    @patch("src.client.dask_client.requests.Session.post")
    @patch("src.client.dask_client.requests.Session.get")
    def test_load_retries_on_504(self, mock_get, mock_post, client: DaskClient):
        """504 errors should trigger token refresh and retry."""
        # Token fetch
        token_resp = MagicMock()
        token_resp.text = "token"
        token_resp.raise_for_status = MagicMock()
        mock_get.return_value = token_resp

        # First call: 504, second: success
        resp_504 = MagicMock()
        resp_504.status_code = 504

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.text = '{"yt": []}'
        resp_ok.raise_for_status = MagicMock()

        mock_post.side_effect = [resp_504, resp_ok]

        result = client.load("il", 0)
        assert result == '{"yt": []}'

    @patch("src.client.dask_client.requests.Session.post")
    @patch("src.client.dask_client.requests.Session.get")
    def test_load_raises_after_all_retries(self, mock_get, mock_post, client: DaskClient):
        """Should raise ApiError after exhausting retries."""
        token_resp = MagicMock()
        token_resp.text = "token"
        token_resp.raise_for_status = MagicMock()
        mock_get.return_value = token_resp

        mock_post.side_effect = requests.ConnectionError("down")

        with pytest.raises(ApiError, match="Request failed after 2"):
            client.load("il", 0)


class TestRateLimiting:
    """Tests for rate limiting between requests."""

    def test_rate_limit_respects_delay(self, config: Config):
        """Rate limiter should enforce minimum delay."""
        config.request_delay = 0.1
        client = DaskClient(config)
        client._last_request_time = time.time()

        start = time.time()
        client._rate_limit()
        elapsed = time.time() - start

        assert elapsed >= 0.05  # Some tolerance

    def test_rate_limit_skips_when_enough_time(self, config: Config):
        """Rate limiter should not sleep if enough time has passed."""
        config.request_delay = 0.1
        client = DaskClient(config)
        client._last_request_time = time.time() - 1.0  # 1 second ago

        start = time.time()
        client._rate_limit()
        elapsed = time.time() - start

        assert elapsed < 0.05


class TestContextManager:
    """Tests for context manager protocol."""

    def test_enter_returns_self(self, client: DaskClient):
        """__enter__ should return the client itself."""
        assert client.__enter__() is client

    @patch.object(DaskClient, "close")
    def test_exit_calls_close(self, mock_close, client: DaskClient):
        """__exit__ should call close()."""
        client.__exit__(None, None, None)
        mock_close.assert_called_once()
