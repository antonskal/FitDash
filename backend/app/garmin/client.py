"""Thin, thread-safe wrapper around `garminconnect.Garmin`.

Responsibilities:
  * restore a persisted OAuth session from `./.garmin_tokens` on startup;
  * run a two-step credential + MFA login flow suitable for a web UI
    (`login()` returns `needs_mfa`, `submit_mfa()` completes it);
  * persist tokens after a successful login so the next launch is silent;
  * centralise rate limiting, exponential-backoff retries and 429 handling
    for every outbound Garmin call.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, TypeVar

import requests
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from app.config import Settings, get_settings

log = logging.getLogger(__name__)
T = TypeVar("T")


class GarminNotAuthenticated(Exception):
    """Raised when an API call is attempted without a valid session."""


class GarminRateLimited(Exception):
    """Raised after exhausting retries on HTTP 429."""

    def __init__(self, retry_after_s: float):
        super().__init__(f"Garmin rate limit hit; retry after {retry_after_s:.0f}s")
        self.retry_after_s = retry_after_s


class GarminNotFound(Exception):
    """A specific resource (activity file, metric) does not exist."""


@dataclass
class AuthStatus:
    state: str = "unauthenticated"  # unauthenticated | needs_mfa | authenticated
    display_name: str | None = None
    email: str | None = None
    message: str | None = None
    token_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "displayName": self.display_name,
            "email": self.email,
            "message": self.message,
            "tokenDir": self.token_dir,
        }


@dataclass
class _MfaPending:
    email: str
    client_state: dict[str, Any] = field(repr=False)


class GarminClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._lock = threading.RLock()
        self._api: Garmin | None = None
        self._mfa: _MfaPending | None = None
        self._status = AuthStatus(token_dir=str(self.settings.token_dir))
        self._last_call_at = 0.0

    # ------------------------------------------------------------- session
    @property
    def is_authenticated(self) -> bool:
        return self._api is not None and self._status.state == "authenticated"

    def status(self) -> AuthStatus:
        return self._status

    def try_restore_session(self) -> bool:
        """Attempt a silent login with persisted tokens. Never raises."""
        with self._lock:
            token_file = self.settings.token_dir / "garmin_tokens.json"
            if not token_file.exists():
                self._status = AuthStatus(state="unauthenticated", token_dir=str(self.settings.token_dir),
                                          message="No saved Garmin session found. Sign in to start syncing.")
                return False
            try:
                api = Garmin(is_cn=self.settings.garmin_is_cn)
                api.login(str(self.settings.token_dir))
                self._set_authenticated(api)
                log.info("Restored Garmin session from %s", token_file)
                return True
            except (GarminConnectAuthenticationError, GarminConnectConnectionError, FileNotFoundError) as exc:
                log.warning("Stored Garmin session invalid: %s", exc)
                self._status = AuthStatus(state="unauthenticated", token_dir=str(self.settings.token_dir),
                                          message="Saved session expired. Please sign in again.")
                return False
            except Exception as exc:  # pragma: no cover - defensive
                log.exception("Unexpected error restoring Garmin session")
                self._status = AuthStatus(state="unauthenticated", token_dir=str(self.settings.token_dir),
                                          message=f"Could not restore session: {exc}")
                return False

    def login(self, email: str, password: str) -> AuthStatus:
        """Step 1 of login. Returns status with state `authenticated` or `needs_mfa`."""
        with self._lock:
            api = Garmin(email=email, password=password, is_cn=self.settings.garmin_is_cn, return_on_mfa=True)
            try:
                result, client_state = api.login(str(self.settings.token_dir))
            except GarminConnectTooManyRequestsError as exc:
                self._status = AuthStatus(state="unauthenticated", message=str(exc), token_dir=str(self.settings.token_dir))
                raise
            except GarminConnectAuthenticationError as exc:
                self._status = AuthStatus(state="unauthenticated", message=str(exc), token_dir=str(self.settings.token_dir))
                raise

            if result == "needs_mfa":
                self._api = api
                self._mfa = _MfaPending(email=email, client_state=client_state)
                self._status = AuthStatus(state="needs_mfa", email=email, token_dir=str(self.settings.token_dir),
                                          message="Enter the one-time code Garmin sent to your email or phone.")
                return self._status

            api.client.dump(str(self.settings.token_dir))
            self._set_authenticated(api, email=email)
            return self._status

    def submit_mfa(self, code: str) -> AuthStatus:
        """Step 2 of login (only when `login()` returned `needs_mfa`)."""
        with self._lock:
            if not self._mfa or not self._api:
                raise GarminNotAuthenticated("No MFA challenge is pending")
            try:
                self._api.resume_login(self._mfa.client_state, code.strip())
            except GarminConnectAuthenticationError as exc:
                self._status.message = f"MFA failed: {exc}"
                raise
            self._api.client.dump(str(self.settings.token_dir))
            email = self._mfa.email
            self._mfa = None
            self._set_authenticated(self._api, email=email)
            return self._status

    def logout(self) -> None:
        with self._lock:
            token_file = self.settings.token_dir / "garmin_tokens.json"
            try:
                if token_file.exists():
                    token_file.unlink()
            finally:
                self._api = None
                self._mfa = None
                self._status = AuthStatus(state="unauthenticated", token_dir=str(self.settings.token_dir),
                                          message="Signed out.")

    def _set_authenticated(self, api: Garmin, email: str | None = None) -> None:
        self._api = api
        name = None
        try:
            name = api.get_full_name()
        except Exception:  # profile lookups are best-effort
            name = getattr(api, "display_name", None)
        self._status = AuthStatus(state="authenticated", display_name=name, email=email,
                                  token_dir=str(self.settings.token_dir), message=None)

    # ---------------------------------------------------------------- calls
    @property
    def api(self) -> Garmin:
        if not self.is_authenticated or self._api is None:
            raise GarminNotAuthenticated("Garmin session is not authenticated")
        return self._api

    def _throttle(self) -> None:
        wait = self.settings.rate_limit_seconds - (time.monotonic() - self._last_call_at)
        if wait > 0:
            time.sleep(wait)
        self._last_call_at = time.monotonic()

    def call(self, fn: Callable[..., T], *args: Any, retries: int | None = None, **kwargs: Any) -> T:
        """Invoke a Garmin API method with throttling and retry/backoff.

        * 429 → sleep `rate_limit_backoff_seconds` (once), then raise GarminRateLimited.
        * 404 → GarminNotFound (caller decides whether that is OK).
        * 5xx / connection errors → exponential backoff with jitter.
        * 401 → attempt a silent token refresh via login(tokenstore) once.
        """
        attempts = (self.settings.max_retries if retries is None else retries) + 1
        delay = 2.0
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            self._throttle()
            try:
                return fn(*args, **kwargs)
            except GarminConnectTooManyRequestsError as exc:
                last_exc = exc
                backoff = self.settings.rate_limit_backoff_seconds
                if attempt < attempts:
                    log.warning("Garmin 429 rate limit; sleeping %ss before retry", backoff)
                    time.sleep(backoff)
                    continue
                raise GarminRateLimited(backoff) from exc
            except GarminConnectAuthenticationError as exc:
                last_exc = exc
                if attempt < attempts and self._refresh_session():
                    continue
                self._status = AuthStatus(state="unauthenticated", token_dir=str(self.settings.token_dir),
                                          message="Garmin session expired. Please sign in again.")
                self._api = None
                raise GarminNotAuthenticated(str(exc)) from exc
            except (requests.exceptions.HTTPError, GarminConnectConnectionError) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                text = str(exc)
                if status == 404 or " 404" in text or "Not Found" in text:
                    raise GarminNotFound(text) from exc
                if status == 429 or "429" in text:
                    if attempt < attempts:
                        log.warning("Garmin 429 (wrapped); sleeping %ss", self.settings.rate_limit_backoff_seconds)
                        time.sleep(self.settings.rate_limit_backoff_seconds)
                        continue
                    raise GarminRateLimited(self.settings.rate_limit_backoff_seconds) from exc
                if status is not None and 400 <= status < 500 and status not in (408,):
                    raise  # other client errors are not retryable
                last_exc = exc
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                last_exc = exc
            if attempt < attempts:
                sleep_for = delay + random.uniform(0, 1)
                log.warning("Garmin call %s failed (attempt %d/%d): %s — retrying in %.1fs",
                            getattr(fn, "__name__", fn), attempt, attempts, last_exc, sleep_for)
                time.sleep(sleep_for)
                delay = min(delay * 2, 30)
        assert last_exc is not None
        raise last_exc

    def _refresh_session(self) -> bool:
        try:
            api = Garmin(is_cn=self.settings.garmin_is_cn)
            api.login(str(self.settings.token_dir))
            self._set_authenticated(api, email=self._status.email)
            log.info("Refreshed Garmin session from stored tokens")
            return True
        except Exception as exc:
            log.warning("Session refresh failed: %s", exc)
            return False


@lru_cache
def get_garmin_client() -> GarminClient:
    return GarminClient(get_settings())
