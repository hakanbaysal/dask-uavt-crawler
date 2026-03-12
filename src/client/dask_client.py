"""HTTP client for DASK UAVT API with token management and retry logic."""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from src.config import Config


class TokenError(Exception):
    """Raised when token retrieval or refresh fails."""


class ApiError(Exception):
    """Raised when an API request fails after all retries."""


class DaskClient:
    """
    HTTP client for adreskodu.dask.gov.tr.

    Handles:
    - Token acquisition and cleanup
    - Automatic token refresh on expiry
    - Request retry with configurable delay
    - Rate limiting between requests
    """

    TOKEN_PATH = "/site-element/control/y.ashx"
    LOAD_PATH = "/site-element/control/load.ashx"

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = logging.getLogger("dask_uavt.client")
        self._session = requests.Session()
        self._token: Optional[str] = None
        self._last_request_time: float = 0.0

        # Set default headers matching the PHP reference
        self._session.headers.update(
            {
                "Host": "adreskodu.dask.gov.tr",
                "Referer": "http://adreskodu.dask.gov.tr/",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )

    # ── Token Management ──────────────────────────────────────────────

    def _clean_token(self, raw: str) -> str:
        """
        Clean raw token per PHP reference:
        str_replace('+', ' ') then str_replace('=', '')
        """
        return raw.replace("+", " ").replace("=", "")

    def fetch_token(self) -> str:
        """
        Fetch a new dynamic token from the API.

        Returns:
            Cleaned token string.

        Raises:
            TokenError: If token retrieval fails after retries.
        """
        url = f"{self._config.base_url}{self.TOKEN_PATH}"

        for attempt in range(1, self._config.max_retries + 1):
            try:
                self._logger.debug("Fetching token (attempt %d)...", attempt)
                resp = self._session.get(url, timeout=self._config.request_timeout)
                resp.raise_for_status()

                raw_token = resp.text.strip()
                if not raw_token:
                    raise TokenError("Empty token received")

                self._token = self._clean_token(raw_token)
                self._logger.info("Token acquired: %s...", self._token[:20])
                return self._token

            except (requests.RequestException, TokenError) as exc:
                self._logger.warning(
                    "Token fetch attempt %d failed: %s", attempt, exc
                )
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_delay)

        raise TokenError(
            f"Failed to fetch token after {self._config.max_retries} attempts"
        )

    def _ensure_token(self) -> str:
        """Return existing token or fetch a new one."""
        if self._token is None:
            return self.fetch_token()
        return self._token

    def refresh_token(self) -> str:
        """Force-refresh the token."""
        self._token = None
        return self.fetch_token()

    # ── Rate Limiting ─────────────────────────────────────────────────

    def _rate_limit(self) -> None:
        """Enforce minimum delay between consecutive requests."""
        if self._config.request_delay <= 0:
            return

        elapsed = time.time() - self._last_request_time
        remaining = self._config.request_delay - elapsed

        if remaining > 0:
            self._logger.debug("Rate limit: sleeping %.2fs", remaining)
            time.sleep(remaining)

    # ── Core Request ──────────────────────────────────────────────────

    def load(self, type_code: str, parent_id: int) -> str:
        """
        Send a POST request to the DASK load endpoint.

        Args:
            type_code: Hierarchy type ('il', 'ce', 'vl', 'mh', 'sf', 'dk', 'ick', 'adr').
            parent_id: Parent entity ID (0 for cities).

        Returns:
            Raw response text (JSON or HTML depending on type_code).

        Raises:
            ApiError: If all retry attempts fail.
        """
        token = self._ensure_token()
        url = f"{self._config.base_url}{self.LOAD_PATH}"
        body = f"{token}=%3D&t={type_code}&u={parent_id}"

        for attempt in range(1, self._config.max_retries + 1):
            try:
                self._rate_limit()

                self._logger.debug(
                    "POST load.ashx t=%s u=%d (attempt %d)",
                    type_code, parent_id, attempt,
                )

                resp = self._session.post(
                    url, data=body, timeout=self._config.request_timeout
                )
                self._last_request_time = time.time()

                # 504 Gateway Timeout — retry with token refresh
                if resp.status_code == 504:
                    self._logger.warning("504 Gateway Timeout, refreshing token...")
                    token = self.refresh_token()
                    body = f"{token}=%3D&t={type_code}&u={parent_id}"
                    time.sleep(self._config.retry_delay)
                    continue

                resp.raise_for_status()
                return resp.text

            except requests.RequestException as exc:
                self._logger.warning(
                    "Request failed (t=%s, u=%d, attempt %d): %s",
                    type_code, parent_id, attempt, exc,
                )

                # Refresh token in case of auth issues
                if attempt < self._config.max_retries:
                    try:
                        token = self.refresh_token()
                        body = f"{token}=%3D&t={type_code}&u={parent_id}"
                    except TokenError:
                        pass
                    time.sleep(self._config.retry_delay)

        raise ApiError(
            f"Request failed after {self._config.max_retries} attempts: "
            f"t={type_code}, u={parent_id}"
        )

    # ── Cleanup ───────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()
        self._logger.debug("HTTP session closed.")

    def __enter__(self) -> DaskClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()
