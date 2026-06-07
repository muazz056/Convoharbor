"""
Thread-safe rate limiter for the Gemini Embedding API.

Gemini's free tier enforces a hard limit of 100 embedding requests per minute
per model per user per project. Hitting the limit returns HTTP 429 and the
caller has to wait until quota resets, which can take up to 60s.

This module provides a sliding-window token-bucket limiter shared across
all threads and all data sources, so that embedding calls automatically
back off when the quota is exhausted and resume as soon as a token is
available.

Usage:
    from app.services.rate_limiter import GeminiRateLimiter

    limiter = GeminiRateLimiter(rate=100, window_seconds=60)
    limiter.wait_for_token()   # blocks until a token is available
    # ... make the API call ...
"""
import threading
import time
from collections import deque
from typing import Optional

from flask import current_app


class GeminiRateLimiter:
    """
    Sliding-window rate limiter for Gemini Embedding API.

    Stores the timestamps of the last N requests in a deque. A new request
    is allowed only if the oldest timestamp in the window is older than
    `window_seconds`. Otherwise we sleep until that timestamp ages out.

    Thread-safe via an internal `threading.Lock` so multiple ingestion
    threads (one per uploaded document) all share the same budget.
    """

    def __init__(self, rate: int = 100, window_seconds: int = 60):
        if rate <= 0:
            raise ValueError("rate must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.rate = int(rate)
        self.window_seconds = int(window_seconds)
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def _prune_locked(self, now: float) -> None:
        """Drop timestamps that have aged out of the sliding window.

        MUST be called with `self._lock` held.
        """
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    def current_count(self) -> int:
        """How many requests are currently counted in the window."""
        with self._lock:
            self._prune_locked(time.monotonic())
            return len(self._timestamps)

    def available_tokens(self) -> int:
        """How many more requests can we issue right now without waiting."""
        with self._lock:
            self._prune_locked(time.monotonic())
            return max(0, self.rate - len(self._timestamps))

    def get_used(self) -> int:
        """Alias of ``current_count`` — current requests in the window."""
        return self.current_count()

    def get_capacity(self) -> int:
        """The total rate (requests allowed per window)."""
        return self.rate

    def wait_for_token(self, poll_interval: float = 0.5,
                       progress_callback=None) -> float:
        """
        Block until a token is available, then consume it.

        Args:
            poll_interval: seconds to sleep between quota checks when
                we have to wait.
            progress_callback: optional callable called with
                `(wait_seconds_remaining, used, capacity)` whenever we
                are about to wait. Useful for logging and frontend
                progress events.

        Returns:
            The number of seconds we had to wait (0 if the token was
            immediately available).
        """
        start = time.monotonic()
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                self._prune_locked(now)
                if len(self._timestamps) < self.rate:
                    # Consume a token.
                    self._timestamps.append(now)
                    return waited
                # Compute when the oldest timestamp will age out.
                oldest = self._timestamps[0]
                wait_for = max(0.0, (oldest + self.window_seconds) - now)
                used = len(self._timestamps)
                capacity = self.rate

            # We're going to have to wait. Call the progress callback
            # outside the lock so it can do logging / IO without
            # blocking other waiters.
            if progress_callback is not None:
                try:
                    progress_callback(wait_for, used, capacity)
                except Exception:
                    # Never let a progress callback break the limiter.
                    pass
            sleep_for = min(poll_interval, wait_for) if wait_for > 0 else poll_interval
            time.sleep(sleep_for)
            waited = time.monotonic() - start


# ---------------------------------------------------------------------------
# Process-wide singleton so all threads share the same budget.
# Re-initialised lazily on first use so tests can monkey-patch config
# values before the first embedding call.
# ---------------------------------------------------------------------------
_singleton: Optional[GeminiRateLimiter] = None
_singleton_lock = threading.Lock()


def get_gemini_rate_limiter() -> GeminiRateLimiter:
    """Return the process-wide Gemini rate limiter, creating it on demand."""
    global _singleton
    if _singleton is not None:
        return _singleton
    with _singleton_lock:
        if _singleton is None:
            rate = 100
            window = 60
            try:
                rate = int(current_app.config.get('GEMINI_RATE_LIMIT_PER_MINUTE', rate))
                window = int(current_app.config.get('GEMINI_RATE_LIMIT_WINDOW_SECONDS', window))
            except Exception:
                # No app context (shell / migration) — use defaults.
                pass
            _singleton = GeminiRateLimiter(rate=rate, window_seconds=window)
            try:
                current_app.logger.info(
                    f"[RATE_LIMITER] Gemini rate limiter initialised: "
                    f"{rate} requests per {window}s"
                )
            except Exception:
                pass
    return _singleton


def reset_gemini_rate_limiter() -> None:
    """Reset the singleton (useful for tests and after a config change)."""
    global _singleton
    with _singleton_lock:
        _singleton = None
