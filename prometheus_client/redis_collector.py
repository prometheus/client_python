from collections.abc import Iterable
import json
import os
from urllib.parse import urlsplit

from .metrics_core import Metric
from .registry import Collector, CollectorRegistry
from .samples import Sample


def redis_client():
    """
    Create a redis client for PROMETHEUS_REDIS_URL.

    Configure the redis database via a URL in PROMETHEUS_REDIS_URL of the form
    redis://localhost:6379/0
    """
    from redis import Redis

    parsed_url = urlsplit(os.environ["PROMETHEUS_REDIS_URL"])
    assert parsed_url.scheme == "redis"
    assert parsed_url.path.startswith("/")
    assert parsed_url.path[1:].isdigit()
    port = parsed_url.port or 6379
    db = int(parsed_url.path[1:])
    return Redis(host=parsed_url.hostname, port=port, db=db)


class RedisCollector(Collector):
    """Collector for redis mode."""

    def __init__(self, registry: CollectorRegistry | None) -> None:
        self._client = redis_client()
        if registry:
            registry.register(self)

    def _iter_values(self) -> Iterable[tuple[bytes, str]]:
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match="value:*")
            values = self._client.mget(keys)
            yield from zip(keys, values)
            if cursor == 0:
                break

    def collect(self) -> Iterable[Metric]:
        metrics: dict[str, Metric] = {}
        histograms: set[str] = set()

        for key, value_s in self._iter_values():
            # FIXME: Catch ValueError here, just in case?
            prefix_b, typ_b, mmap_key = key.split(b":", 2)
            assert prefix_b == b"value"
            typ = typ_b.decode()
            value = float(value_s)

            metric_name, name, labels, help_text = json.loads(mmap_key)

            metric = metrics.get(metric_name)
            if metric is None:
                metric = Metric(metric_name, help_text, typ)
                metrics[metric_name] = metric
                if typ in ("histogram", "gaugehistogram"):
                    histograms.add(metric_name)

            metric.add_sample(name, labels, value)

        for name in histograms:
            self._fix_histogram(metrics[name])

        return metrics.values()

    def _fix_histogram(self, metric: Metric) -> None:
        """
        Fix-up histogram samples.

        Sort the buckets as expected by a client, and accumulate the values.
        The Histogram class is optimized to only increment the bucket that a
        value first appears in, not larger ones that would also contain it.
        """
        by_label: dict[tuple[tuple[str, ...], str], list[Sample]] = {}

        # Organize into lists of samples by label
        for sample in metric.samples:
            if "le" in sample.labels:
                labels_without_le = sample.labels.copy()
                labels_without_le.pop("le")
                key = (tuple(labels_without_le.values()), sample.name)
            else:
                key = (tuple(sample.labels.values()), sample.name)
            by_label.setdefault(key, []).append(sample)

        metric.samples = []

        for (labels, name), samples in sorted(by_label.items()):
            if name.endswith("_bucket"):
                # Sort buckets within each label
                samples.sort(key=lambda sample: float(sample.labels["le"]))

                # Accumulate values into larger buckets
                value = 0.0
                for sample in samples:
                    value += sample.value
                    metric.samples.append(Sample(sample.name, sample.labels, value))

            else:
                metric.samples.extend(samples)
