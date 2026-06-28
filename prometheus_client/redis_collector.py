import json
from collections.abc import Iterable
from typing import cast

from .metrics_core import Metric
from .redis import redis_client
from .registry import Collector, CollectorRegistry
from .samples import Sample
from .values import MULTIPROCESS_MODE_T


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
        multiprocess: dict[str, MULTIPROCESS_MODE_T] = {}

        for key, value_s in self._iter_values():
            # FIXME: Catch ValueError here, just in case?
            prefix_b, typ_b, multiprocess_mode_b, mmap_key = key.split(b":", 3)
            assert prefix_b == b"value"
            value = float(value_s)

            metric_name, name, labels, help_text = json.loads(mmap_key)

            metric = metrics.get(metric_name)
            if metric is None:
                typ = typ_b.decode()
                metric = Metric(metric_name, help_text, typ)
                metrics[metric_name] = metric

                if typ in ("histogram", "gaugehistogram"):
                    histograms.add(metric_name)

                multiprocess_mode = cast(
                    MULTIPROCESS_MODE_T, multiprocess_mode_b.decode()
                )
                if typ in ("gauge", "gaugehistogram") and multiprocess_mode:
                    multiprocess[metric_name] = multiprocess_mode

            metric.add_sample(name, labels, value)

        for name, multiprocess_mode in multiprocess.items():
            self._accumulate_multiprocess(metrics[name], multiprocess_mode)

        for name in histograms:
            self._fix_histogram(metrics[name])

        return metrics.values()

    def _accumulate_multiprocess(
        self, metric: Metric, multiprocess_mode: MULTIPROCESS_MODE_T
    ) -> None:
        """Merge metrics from multiple processes using multiprocess_mode."""
        # We deal with live/dead with Redis expiry
        if multiprocess_mode.startswith("live"):
            multiprocess_mode = cast(
                MULTIPROCESS_MODE_T, multiprocess_mode[len("live") :]
            )
        if multiprocess_mode == "all":
            return

        by_label: dict[tuple[tuple[str, ...], str], Sample] = {}

        for sample in metric.samples:
            labels = sample.labels.copy()
            labels.pop("pid")
            key = (tuple(labels.values()), sample.name)
            value = sample.value
            if key in by_label:
                current_value = by_label[key].value
                if multiprocess_mode == "min" and value > current_value:
                    continue
                if multiprocess_mode == "max" and value < current_value:
                    continue
                if multiprocess_mode == "sum":
                    value += current_value
                if multiprocess_mode == "mostrecent":
                    raise NotImplementedError(
                        "The 'mostrecent' modes are not supported in RedisCollector"
                    )
            by_label[key] = Sample(sample.name, labels, value)

        metric.samples = list(by_label.values())

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

                labels_without_le = sample.labels.copy()
                labels_without_le.pop("le")
                metric.samples.append(
                    Sample(f"{metric.name}_count", labels_without_le, value)
                )

            else:
                metric.samples.extend(samples)
