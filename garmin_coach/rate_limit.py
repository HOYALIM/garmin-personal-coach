import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds

            self._requests[key] = [t for t in self._requests[key] if t > cutoff]

            if len(self._requests[key]) >= self.max_requests:
                return False

            self._requests[key].append(now)
            return True

    def reset(self, key: str):
        with self._lock:
            if key in self._requests:
                del self._requests[key]

    def get_remaining(self, key: str) -> int:
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]
            return max(0, self.max_requests - len(self._requests[key]))

    def get_reset_time(self, key: str) -> float:
        with self._lock:
            if key not in self._requests or not self._requests[key]:
                return 0
            oldest = min(self._requests[key])
            return max(0, oldest + self.window_seconds - time.time())


class MultiLimiter:
    def __init__(self):
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = Lock()

    def get_limiter(self, name: str, **kwargs) -> RateLimiter:
        with self._lock:
            if name not in self._limiters:
                self._limiters[name] = RateLimiter(**kwargs)
            return self._limiters[name]


GLOBAL_LIMITER = MultiLimiter()
HANDLER_LIMITER = GLOBAL_LIMITER.get_limiter("handler", max_requests=60, window_seconds=60)
MCP_LIMITER = GLOBAL_LIMITER.get_limiter("mcp", max_requests=100, window_seconds=60)
