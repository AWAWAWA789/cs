"""Core CSQAQ API client with rate limiting and error handling."""

import time
from typing import Any

import requests

from src.config import Settings


class CSQAQAPIError(Exception):
    """Raised when the CSQAQ API returns an error response."""

    def __init__(self, message: str, code: int | None = None, response_body: Any = None):
        super().__init__(message)
        self.code = code
        self.response_body = response_body


class CSQAQClient:
    """Low-level HTTP client for CSQAQ API.

    Enforces per-endpoint rate limits:
    - Normal endpoints: 1 request per second per IP.
    - ``/sys/bind_local_ip``: 1 request per 30 seconds.
    """

    NORMAL_COOLDOWN: float = 1.0
    BIND_IP_COOLDOWN: float = 30.0

    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self._last_request_time: float = 0.0
        self._last_bind_ip_time: float = 0.0

    def _wait_for_rate_limit(self, path: str) -> None:
        """Sleep if needed to respect API rate limits."""
        now = time.monotonic()
        if path == "/sys/bind_local_ip":
            cooldown = self.BIND_IP_COOLDOWN
            last = self._last_bind_ip_time
        else:
            cooldown = self.NORMAL_COOLDOWN
            last = self._last_request_time

        elapsed = now - last
        if elapsed < cooldown:
            time.sleep(cooldown - elapsed)

    def _mark_request(self, path: str) -> None:
        """Record the timestamp of a completed request."""
        now = time.monotonic()
        self._last_request_time = now
        if path == "/sys/bind_local_ip":
            self._last_bind_ip_time = now

    def _url(self, path: str) -> str:
        """Build full URL from base URL and path."""
        base = self.settings.base_url.rstrip("/")
        return f"{base}{path}"

    def request(
        self, method: str, path: str, *, skip_rate_limit: bool = False, **kwargs: Any
    ) -> Any:
        """Make an HTTP request and return the API ``data`` payload.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path starting with ``/``.
            skip_rate_limit: If True, do not sleep for rate limiting.
                Intended for tests that need precise timing control.
            **kwargs: Extra arguments passed to ``requests.request``.

        Returns:
            The parsed ``data`` field from the JSON response.

        Raises:
            CSQAQAPIError: If the HTTP request fails or the API returns a non-200 code.
        """
        if not skip_rate_limit:
            self._wait_for_rate_limit(path)

        headers = kwargs.setdefault("headers", {})
        headers["ApiToken"] = self.settings.api_token

        url = self._url(path)
        response = self.session.request(method, url, **kwargs)
        self._mark_request(path)

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise CSQAQAPIError(
                f"HTTP error {response.status_code} for {method} {url}: {exc}",
                code=response.status_code,
                response_body=response.text,
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise CSQAQAPIError(
                f"Invalid JSON response for {method} {url}: {exc}",
                response_body=response.text,
            ) from exc

        api_code = payload.get("code")
        if api_code != 200:
            raise CSQAQAPIError(
                f"API error {api_code}: {payload.get('msg')}",
                code=api_code,
                response_body=payload,
            )

        return payload.get("data")

    def get(self, path: str, **kwargs: Any) -> Any:
        """Convenience wrapper for GET requests."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        """Convenience wrapper for POST requests."""
        return self.request("POST", path, **kwargs)
