#!/usr/bin/env python3
"""Small, thread-safe sliding-window rate limiter for sensitive endpoints."""

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class RateLimitDecision:
    """Result returned when an attempt is atomically admitted or rejected."""

    allowed: bool
    retry_after: int = 0


class SlidingWindowRateLimiter:
    """Track attempts across one or more keys within a fixed time window.

    Keys are checked and consumed under one lock, preventing concurrent
    requests from exceeding the configured limit. Storage is bounded so
    attacker-controlled client identifiers cannot grow memory indefinitely.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: int,
        *,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ):
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")
        if max_keys < 1:
            raise ValueError("max_keys must be at least 1")

        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._attempts: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_full_prune = self._clock()

    def consume(self, keys: Iterable[str]) -> RateLimitDecision:
        """Atomically consume one attempt for every unique non-empty key."""
        normalized_keys = tuple(dict.fromkeys(str(key) for key in keys if key))
        if not normalized_keys:
            normalized_keys = ("unknown",)

        with self._lock:
            now = self._clock()
            if now - self._last_full_prune >= min(self.window_seconds, 60):
                self._prune_all(now)
            else:
                self._prune_keys(normalized_keys, now)

            retry_after = 0
            for key in normalized_keys:
                attempts = self._attempts.get(key)
                if attempts and len(attempts) >= self.limit:
                    remaining = attempts[0] + self.window_seconds - now
                    retry_after = max(retry_after, max(1, math.ceil(remaining)))

            if retry_after:
                return RateLimitDecision(allowed=False, retry_after=retry_after)

            for key in normalized_keys:
                self._ensure_capacity(key, now)
                self._attempts.setdefault(key, deque()).append(now)

            return RateLimitDecision(allowed=True)

    def reset(self, keys: Iterable[str] | None = None) -> None:
        """Clear selected buckets, or every bucket when keys are omitted."""
        with self._lock:
            if keys is None:
                self._attempts.clear()
                return
            for key in keys:
                self._attempts.pop(str(key), None)

    def _prune_all(self, now: float) -> None:
        self._prune_keys(tuple(self._attempts), now)
        self._last_full_prune = now

    def _prune_keys(self, keys: Iterable[str], now: float) -> None:
        cutoff = now - self.window_seconds
        for key in keys:
            attempts = self._attempts.get(key)
            if not attempts:
                continue
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if not attempts:
                self._attempts.pop(key, None)

    def _ensure_capacity(self, incoming_key: str, now: float) -> None:
        if incoming_key in self._attempts or len(self._attempts) < self.max_keys:
            return

        self._prune_all(now)
        if len(self._attempts) < self.max_keys:
            return

        # All remaining buckets are active. Evict the least recently used
        # bucket to preserve the hard memory bound.
        oldest_key = min(self._attempts, key=lambda key: self._attempts[key][-1])
        self._attempts.pop(oldest_key, None)
