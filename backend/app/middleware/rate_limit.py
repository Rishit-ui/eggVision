"""Sliding-window rate limiter with client IP extraction."""

import asyncio
from time import perf_counter

from fastapi import HTTPException, Request, status


def get_client_ip(request: Request) -> str:
    """Extract client IP safely from X-Forwarded-For or socket host."""
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        # Leftmost entry is the client address when behind reverse proxy
        client_ip = forwarded.split(",")[0].strip()
        if client_ip:
            return client_ip
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter for sensitive endpoints."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        now = perf_counter()
        async with self._lock:
            timestamps = self._history.get(key, [])
            valid = [t for t in timestamps if now - t < self.window_seconds]
            if len(valid) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - valid[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )
            valid.append(now)
            self._history[key] = valid

    async def reset(self) -> None:
        async with self._lock:
            self._history.clear()


login_rate_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
