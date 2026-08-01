"""Core CSQAQ API client with rate limiting and error handling."""

import logging
import threading
import time
from typing import Any

import requests

from src.config import Settings

logger = logging.getLogger("csqaq.client")


class CSQAQAPIError(Exception):
    """Raised when the CSQAQ API returns an error response."""

    def __init__(self, message: str, code: int | None = None, response_body: Any = None):
        super().__init__(message)
        self.code = code
        self.response_body = response_body


# ── Global rate-limit lock ──────────────────────────────────
# All CSQAQClient instances share this lock and timestamp so that
# concurrent requests from different API endpoints are properly
# serialized to respect the 1-request-per-second rate limit.
#
# The lock uses a **slot-reservation** strategy: when a thread needs
# to wait, it reserves its time slot (last + cooldown) BEFORE releasing
# the lock. This ensures concurrent threads queue after each other
# instead of waking simultaneously and causing 429 errors.

_global_lock = threading.Lock()
_global_last_request_time: float = 0.0
_global_last_bind_ip_time: float = 0.0
_global_last_rebind_success: float = 0.0  # monotonic time of last successful IP rebind


class CSQAQClient:
    """Low-level HTTP client for CSQAQ API.

    Enforces per-endpoint rate limits using a **global** lock shared
    across all client instances:
    - Normal endpoints: 1 request per second per IP.
    - ``/sys/bind_local_ip``: 1 request per 30 seconds.

    Automatically retries on HTTP 429 with exponential backoff.
    """

    NORMAL_COOLDOWN: float = 2.0  # above 1s for safety margin
    BIND_IP_COOLDOWN: float = 30.0  # CSQAQ enforces 30s between bind calls
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 3.0  # base delay for 429 retry backoff
    RATE_LIMIT_PENALTY: float = 3.0  # extra cooldown applied after a 429

    # ── Shared session ──────────────────────────────────────────
    # A single requests.Session is shared across all CSQAQClient instances
    # so that HTTP keep-alive reuses the same TCP connection (and thus the
    # same outbound IP) for every request.  This is critical because the
    # CSQAQ API binds a single IP per token — if the outbound IP changes
    # between requests we get HTTP 401 and must rebind (rate-limited to
    # once per 30 s).
    _shared_session: requests.Session | None = None

    @classmethod
    def _get_shared_session(cls) -> requests.Session:
        """Return the process-wide shared requests session."""
        if cls._shared_session is None:
            cls._shared_session = requests.Session()
            # Tune the HTTP adapter for better connection reuse
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=4,
                pool_maxsize=10,
                max_retries=0,  # we handle retries ourselves
            )
            cls._shared_session.mount("https://", adapter)
            cls._shared_session.mount("http://", adapter)
        return cls._shared_session

    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or self._get_shared_session()

    def _wait_for_rate_limit(self, path: str) -> None:
        """Sleep if needed to respect API rate limits. Thread-safe.

        Uses a **slot-reservation** strategy to prevent the thundering-herd
        race condition: when a thread decides to sleep, it atomically
        reserves its time slot (``last + cooldown``) in the global timestamp
        BEFORE releasing the lock. This guarantees that the next thread
        acquiring the lock sees a future timestamp and queues after us,
        rather than computing the same wait duration and waking up
        simultaneously.
        """
        global _global_last_request_time, _global_last_bind_ip_time

        with _global_lock:
            now = time.monotonic()
            if path == "/sys/bind_local_ip":
                cooldown = self.BIND_IP_COOLDOWN
                last = _global_last_bind_ip_time
            else:
                cooldown = self.NORMAL_COOLDOWN
                last = _global_last_request_time

            # The earliest time we are allowed to make a request.
            earliest = last + cooldown
            if now < earliest:
                # We need to wait. Reserve our slot by updating the
                # global timestamp to our scheduled time, so the next
                # thread queues after us instead of waking up at the
                # same moment and causing a 429.
                wait = earliest - now
                if path == "/sys/bind_local_ip":
                    _global_last_bind_ip_time = earliest
                else:
                    _global_last_request_time = earliest
                # Release lock while sleeping so other threads can queue
                _global_lock.release()
                try:
                    time.sleep(wait)
                finally:
                    _global_lock.acquire()
            else:
                # No wait needed — reserve our slot as now.
                if path == "/sys/bind_local_ip":
                    _global_last_bind_ip_time = now
                else:
                    _global_last_request_time = now

    def _mark_request(self, path: str, *, rate_limited: bool = False) -> None:
        """Record the timestamp of a completed request.

        When ``rate_limited`` is True (HTTP 429), a penalty is added to the
        timestamp so that subsequent requests wait longer before retrying.
        This prevents the retry loop from immediately hitting the API again
        after a rate-limit error.
        """
        global _global_last_request_time, _global_last_bind_ip_time

        with _global_lock:
            now = time.monotonic()
            if rate_limited:
                # Push the timestamp into the future so the next
                # _wait_for_rate_limit enforces an extra cooldown.
                ts = now + self.RATE_LIMIT_PENALTY
            else:
                ts = now
            _global_last_request_time = ts
            if path == "/sys/bind_local_ip":
                _global_last_bind_ip_time = ts

    def _url(self, path: str) -> str:
        """Build full URL from base URL and path."""
        base = self.settings.base_url.rstrip("/")
        return f"{base}{path}"

    def _rebind_ip(self) -> None:
        """Bind the current outbound IP to the API token.

        Called automatically when the CSQAQ API returns a 401 (unauthorized),
        which typically means the IP has changed since the last binding.
        Retries on 429 with exponential backoff.

        Skips the rebind attempt if a successful rebind was performed within
        the last ``BIND_IP_COOLDOWN`` seconds, to avoid hitting the CSQAQ
        bind endpoint's 30-second rate limit.
        """
        global _global_last_rebind_success

        # Check if we recently rebound successfully — if so, the 401 is
        # likely because the IP changed again, but we can't rebind for
        # another few seconds.  Raise immediately so the caller can return
        # an error to the user instead of blocking for 30 s.
        with _global_lock:
            now = time.monotonic()
            elapsed = now - _global_last_rebind_success
            if _global_last_rebind_success > 0 and elapsed < self.BIND_IP_COOLDOWN:
                remaining = self.BIND_IP_COOLDOWN - elapsed
                raise CSQAQAPIError(
                    f"IP recently rebound; next rebind available in {remaining:.0f}s",
                    code=429,
                )

        logger.info("Attempting IP rebind...")
        for bind_attempt in range(self.MAX_RETRIES + 1):
            self._wait_for_rate_limit("/sys/bind_local_ip")
            headers = {"ApiToken": self.settings.api_token}
            url = self._url("/sys/bind_local_ip")
            response = self.session.post(url, headers=headers)

            # Handle 429 on bind endpoint with retry
            if response.status_code == 429:
                # Apply penalty so the next attempt waits longer
                self._mark_request("/sys/bind_local_ip", rate_limited=True)
                if bind_attempt < self.MAX_RETRIES:
                    backoff = self.RETRY_BASE_DELAY * (bind_attempt + 1)
                    logger.warning(
                        "IP rebind rate limited (429), retrying in %.1fs (attempt %d/%d)",
                        backoff, bind_attempt + 1, self.MAX_RETRIES,
                    )
                    time.sleep(backoff)
                    continue
                raise CSQAQAPIError(
                    f"IP rebind HTTP 429 after {self.MAX_RETRIES + 1} attempts",
                    code=429,
                    response_body=response.text,
                )

            # Non-429 response — mark normally
            self._mark_request("/sys/bind_local_ip")

            if response.status_code != 200:
                raise CSQAQAPIError(
                    f"IP rebind HTTP error: {response.status_code}",
                    code=response.status_code,
                    response_body=response.text,
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise CSQAQAPIError(
                    f"IP rebind invalid JSON: {exc}",
                    response_body=response.text,
                ) from exc

            # Accept both integer and string 200 as success
            api_code = payload.get("code")
            if api_code in (429, "429"):
                # CSQAQ returns code=429 in JSON body for rate limit
                raise CSQAQAPIError(
                    f"IP rebind rate limited: {payload.get('data')}",
                    code=429,
                    response_body=payload,
                )
            if api_code not in (200, "200"):
                logger.warning("IP rebind unexpected response: %s", payload)
                raise CSQAQAPIError(
                    f"IP rebind API error (code={api_code}): {payload.get('msg')}",
                    code=api_code if isinstance(api_code, int) else 0,
                    response_body=payload,
                )

            # Record successful rebind time
            with _global_lock:
                _global_last_rebind_success = time.monotonic()

            logger.info("IP rebind successful: %s", payload.get("data"))
            return

    @staticmethod
    def _parse_retry_after(response: requests.Response) -> float | None:
        """Parse the ``Retry-After`` header from a 429 response.

        Supports both delta-seconds (e.g. ``"5"``) and HTTP-date format.
        Returns ``None`` if the header is absent or unparseable.
        """
        value = response.headers.get("Retry-After")
        if not value:
            return None
        # Try integer seconds first.
        try:
            return float(value)
        except ValueError:
            pass
        # Try HTTP-date format (RFC 7231).
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(value)
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            delta = (dt - now).total_seconds()
            return max(0.0, delta)
        except Exception:
            return None

    def request(
        self, method: str, path: str, *, skip_rate_limit: bool = False, **kwargs: Any
    ) -> Any:
        """Make an HTTP request and return the API ``data`` payload.

        Automatically retries on HTTP 429 (Too Many Requests) with
        exponential backoff up to ``MAX_RETRIES`` times.
        Automatically rebinds IP on HTTP 401 (Unauthorized) once per call.

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
        last_exc: CSQAQAPIError | None = None
        rebound = False  # Only attempt IP rebind once per request

        for attempt in range(self.MAX_RETRIES + 1):
            if not skip_rate_limit:
                self._wait_for_rate_limit(path)

            headers = kwargs.setdefault("headers", {})
            headers["ApiToken"] = self.settings.api_token

            url = self._url(path)
            response = self.session.request(method, url, **kwargs)

            # ── Handle HTTP 429 with retry ──────────────────────
            if response.status_code == 429:
                # Apply penalty so the next _wait_for_rate_limit enforces
                # a longer cooldown before retrying.
                self._mark_request(path, rate_limited=True)

                if attempt < self.MAX_RETRIES:
                    # Respect Retry-After header if present, otherwise use
                    # exponential backoff.
                    retry_after = self._parse_retry_after(response)
                    backoff = retry_after if retry_after else self.RETRY_BASE_DELAY * (attempt + 1)
                    logger.warning(
                        "Rate limited (429) on %s %s, retrying in %.1fs (attempt %d/%d)",
                        method, url, backoff, attempt + 1, self.MAX_RETRIES,
                    )
                    time.sleep(backoff)
                    continue

                last_exc = CSQAQAPIError(
                    f"HTTP 429 after {self.MAX_RETRIES + 1} attempts for {method} {url}",
                    code=429,
                    response_body=response.text,
                )
                break

            # ── Handle HTTP 401 — auto-rebind IP and retry ──────
            if response.status_code == 401 and not rebound and path != "/sys/bind_local_ip":
                self._mark_request(path)
                logger.warning("HTTP 401 on %s %s, attempting IP rebind...", method, url)
                try:
                    self._rebind_ip()
                    rebound = True
                    continue  # Retry the original request
                except CSQAQAPIError as e:
                    logger.warning("IP rebind failed: %s", e)
                    # Raise with a helpful message that includes the rebind failure
                    raise CSQAQAPIError(
                        f"Unauthorized (401) and IP rebind failed: {e}",
                        code=401,
                        response_body=response.text,
                    ) from e

            # Successful (or non-429/401) HTTP response — mark normally.
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

            # ── Handle API-level 429 (code field in JSON body) ──
            api_code = payload.get("code")
            if api_code in (429, "429"):
                # Apply penalty for API-level rate limit too.
                self._mark_request(path, rate_limited=True)

                if attempt < self.MAX_RETRIES:
                    backoff = self.RETRY_BASE_DELAY * (attempt + 1)
                    logger.warning(
                        "API rate limited (code=429) on %s %s, retrying in %.1fs (attempt %d/%d)",
                        method, url, backoff, attempt + 1, self.MAX_RETRIES,
                    )
                    time.sleep(backoff)
                    continue

                last_exc = CSQAQAPIError(
                    f"API code=429 after {self.MAX_RETRIES + 1} attempts for {method} {url}",
                    code=429,
                    response_body=payload,
                )
                break

            # ── Handle API-level 401 — auto-rebind IP and retry ─
            if api_code in (401, "401") and not rebound and path != "/sys/bind_local_ip":
                logger.warning("API code=401 on %s %s, attempting IP rebind...", method, url)
                try:
                    self._rebind_ip()
                    rebound = True
                    continue  # Retry the original request
                except CSQAQAPIError as e:
                    logger.warning("IP rebind failed: %s", e)
                    raise CSQAQAPIError(
                        f"Unauthorized (401) and IP rebind failed: {e}",
                        code=401,
                        response_body=payload,
                    ) from e

            if api_code not in (200, "200"):
                raise CSQAQAPIError(
                    f"API error {api_code}: {payload.get('msg')}",
                    code=api_code if isinstance(api_code, int) else 0,
                    response_body=payload,
                )

            return payload.get("data")

        # Exhausted all retries
        if last_exc:
            raise last_exc
        raise CSQAQAPIError(
            f"Exhausted all {self.MAX_RETRIES} retries for {method} {url}",
            code=429,
        )

    def get(self, path: str, **kwargs: Any) -> Any:
        """Convenience wrapper for GET requests."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        """Convenience wrapper for POST requests."""
        return self.request("POST", path, **kwargs)
