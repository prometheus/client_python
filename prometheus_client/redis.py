import os
from datetime import timedelta
from threading import Event, Thread
from typing import Any
from urllib.parse import urlsplit

from redis import Redis

# For testing, a pool of otherwise anonymous FakeRedis instances are made
# available by ID
_fake_redis_pool: dict[int, Redis] = {}


def redis_client() -> Redis:
    """
    Create a redis client for PROMETHEUS_REDIS_URL.

    Configure the redis database via a URL in PROMETHEUS_REDIS_URL of the form
    redis://localhost:6379/0
    """
    parsed_url = urlsplit(os.environ["PROMETHEUS_REDIS_URL"])
    assert parsed_url.path.startswith("/")
    assert parsed_url.path[1:].isdigit()
    port = parsed_url.port or 6379
    db = int(parsed_url.path[1:])

    if parsed_url.scheme == "fakeredis":
        from fakeredis import FakeRedis

        if db not in _fake_redis_pool:
            _fake_redis_pool[db] = FakeRedis()
        return _fake_redis_pool[db]

    assert parsed_url.scheme == "redis"
    assert parsed_url.hostname
    return Redis(host=parsed_url.hostname, port=port, db=db)


# For each process identifier, a list of keys that should be kept from expiring
_live_metrics: dict[str, set[str]] = {}


def _key_expiry() -> timedelta:
    """Return the configured expiry for multiprocess keys."""
    return timedelta(seconds=int(os.environ.get("PROMETHEUS_REDIS_REFRESH_TTL", 20)))


class KeepMetricsAliveThread(Thread):
    """A daemon thread that keeps metrics from expiring as long as we live."""

    stop: Event
    identifier: str
    client: Redis

    def __init__(
        self, identifier: str, client: Redis, *args: Any, **kwargs: Any
    ) -> None:
        self.stop = Event()
        self.identifier = identifier
        self.client = client
        super().__init__(*args, **kwargs)

    def loop_wait(self, delay: float) -> bool:
        return self.stop.wait(delay)

    def run(self) -> None:
        delay = float(os.environ.get("PROMETHEUS_REDIS_REFRESH_FREQUENCY", 10))
        expiry = _key_expiry()
        while not self.loop_wait(delay):
            for key in _live_metrics[self.identifier]:
                self.client.expire(key, expiry)


_daemon_threads: dict[str, KeepMetricsAliveThread] = {}


def _keep_key_from_expiring(identifier: str, key: str) -> None:
    """Stop key for process identifier from expiring as long as we are alive."""
    _live_metrics.setdefault(identifier, set()).add(key)
    if identifier not in _daemon_threads:
        thread = KeepMetricsAliveThread(
            identifier=identifier, client=redis_client(), daemon=True
        )
        thread.start()
        _daemon_threads[identifier] = thread


def mark_process_dead(identifier: str | int) -> None:
    """Immediately expire all live* metrics for process identifier."""
    thread = _daemon_threads.pop(str(identifier), None)
    if thread is not None:
        thread.stop.set()
        thread.join()

    keys = _live_metrics.pop(str(identifier), None)
    if not keys:
        return
    redis_client().delete(*keys)
