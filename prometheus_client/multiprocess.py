#!/usr/bin/python

from __future__ import unicode_literals

import glob
import json
import os
import shelve

from . import core


class MetricKind:
    """Constants to represent a metric kind.
    """

    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    COUNTER = "counter"
    SUMMARY = "summary"

    __all__ = (GAUGE, HISTOGRAM, COUNTER, SUMMARY)


class Submetric(object):
    """Simple submetric with a parent and value.
    """

    def __init__(self, name, parent, value=None, labels=None, kind=None, collect_mode=None):
        self.name = name
        self.parent = parent
        self.value = value
        self.labels = labels
        self.kind = kind
        self.collect_mode = collect_mode

    @classmethod
    def from_data(cls, data):
        """Generates a ``Submetric`` from an opqaue dict.
        """
        parent, name, label_names, label_values = json.loads(data["key"])
        labels = zip(label_names, label_values)

        if data.get("parition") is not None:
            labels += (("partition", data["partition"]), )

        return cls(
            name,
            parent,
            value=data["value"],
            labels=labels,
            kind=data["kind"],
            collect_mode=data.get("collect_mode")
        )


class Metric(object):
    """Full metric comprised of at least one submetric.
    """

    def __init__(self, name=None, kind=None, labels=None):
        self.name = name
        self.kind = kind
        self.labels = labels or []

        self._samples = []
        self.submetrics = []

    def add_submetric(self, submetric):
        """Merges in a new submetric, given it is of the same type.

        :param SingleMetric single_metric:
        """
        if not isinstance(submetric, Submetric):
            raise ValueError(
                "Cannot add item of type '%r', expected 'Submetric'" % type(submetric)
            )

        if self.name != submetric.parent:
            raise ValueError("Cannot add submetric with different parent")

        if self.kind != submetric.kind:
            raise ValueError("Cannot add submetrics of different kinds")

        self.submetrics.append(submetric)

    def materialize(self):
        """Express the metric as a core Prometheus metric with proper samples.
        """
        metric = core.Metric(self.name, "Multiprocess metric", self.kind)

        samples = []
        for (name, labels), val in self._samples.iteritems():
            samples.append((name, dict(labels), val))

        metric.samples = samples
        return metric

    @classmethod
    def from_submetric(cls, submetric):
        """Build a new ``Metric`` from an initial ``Submetric``.
        """
        if not isinstance(submetric, Submetric):
            raise ValueError(
                "Cannot create metric from '%r', expected one of 'Submetric'" % type(submetric)
            )

        metric = cls(
            name=submetric.parent,
            kind=submetric.kind,
            labels=submetric.labels
        )
        metric.submetrics = [submetric]
        return metric


class PartitionedMetric(object):
    """Metric that must be merged with all other partitions during collection.
    """
    pass


class GaugePartitionedMetric(PartitionedMetric):

    @classmethod
    def build(cls, submetric, samples):
        """Generate samples for this submetric.
        """
        labels_without_partition = tuple([l for l in submetric.labels if l[0] != "partition"])
        key = (submetric.name, labels_without_partition)
        mode = submetric.collect_mode

        if mode == "min":
            sample = samples.get(key)
            if sample is None or sample > submetric.value:
                samples[key] = submetric.value
        elif mode == "max":
            sample = samples.get(key)
            if sample is None or sample < submetric.value:
                samples[key] = submetric.value
        elif mode == "livesum":
            sample = samples.get(key, 0.0)
            samples[key] = sample + submetric.value
        else:
            all_key = (submetric.name, tuple(submetric.labels))
            samples[all_key] = submetric.value

        return samples


class HistogramPartitionedMetric(PartitionedMetric):

    @classmethod
    def build(cls, submetric, samples, buckets):
        """Generate samples and buckets for this submetric.
        """
        # TODO: This is a weird way to determind if this is a bucket or sum
        # sample...
        bucket = [float(l[1]) for l in submetric.labels if l[0] == 'le']
        if bucket:
            bucket = bucket[0]

        if bucket:
            key = tuple([l for l in submetric.labels if l[0] != 'le'])
            histogram = buckets.get(key, {})
            measurement = histogram.get(bucket, 0.0)
            histogram[bucket] = measurement + submetric.value
            buckets[key] = histogram
        else:
            key = (submetric.name, tuple(submetric.labels))
            sample = samples.get(key, 0.0)
            samples[key] = sample + submetric.value

        return samples, buckets


class PartitionedCollector(object):
    """Joins disparate metrics samples as one.

    This is particularly useful with multiprocess setups in which there is no
    shared state. In those cases the shared state can be simulated by having
    each independent process collect its own metrics, then join these metrics
    into a snapshot of all processes' metrics at collect time.
    """

    def __init__(self, registry):
        self.metrics = {}
        if registry:
            registry.register(self)

    def gather(self):
        """Gather metrics prior to collection.

        This method must gather the necessary metrics and return them as a list
        of dicts with key, value, kind, and optionally partition and
        collect_mode.

        [
            {
                'key': '["h", "h_sum", [], []]'
                'kind': 'gauge',
                'value': 0.5,
                'partition': '123'
            }
        ]
        """
        raise NotImplementedError

    def build_from_raw(self, raw):
        for data in raw:
            submetric = Submetric.from_data(data)

            if data.get("partition") is not None:
                submetric.labels += (("partition", data["partition"]), )

            if submetric.parent in self.metrics:
                self.metrics[submetric.parent].add_submetric(submetric)
            else:
                self.metrics[submetric.parent] = Metric.from_submetric(submetric)

    def collect(self):
        """Fold up all metrics properly by kind.
        """
        self.metrics = {}
        raw = self.gather()
        self.build_from_raw(raw)
            
        results = []
        for metric_key, metric in self.metrics.iteritems():
            samples = {}
            buckets = {}

            for submetric in metric.submetrics:
                if submetric.kind == MetricKind.GAUGE:
                    samples = GaugePartitionedMetric.build(submetric, samples)
                elif submetric.kind == MetricKind.HISTOGRAM:
                    samples, buckets = HistogramPartitionedMetric.build(
                        submetric,
                        samples,
                        buckets
                    )
                elif submetric.kind in (MetricKind.COUNTER, MetricKind.SUMMARY):
                    key = (submetric.name, tuple(submetric.labels))
                    sample = samples.get(key, 0.0)
                    samples[key] = sample + submetric.value

            # Accumulate bucket values.
            if metric.kind == MetricKind.HISTOGRAM:
                for labels, values in buckets.items():
                    acc = 0.0
                    for bucket, value in sorted(values.items()):
                        acc += value
                        samples[(metric.name + '_bucket', labels + (('le', core._floatToGoString(bucket)), ))] = acc
                    samples[(metric.name + '_count', labels)] = acc

            metric._samples = samples
            results.append(metric.materialize())
        return results


class ShelveCollector(PartitionedCollector):
    def __init__(self, registry, path=os.environ.get("prometheus_multiproc_dir")):
        super(ShelveCollector, self).__init__(registry)
        self._path = path

    def gather(self):
        raw = []
        for f in glob.glob(os.path.join(self._path, '*.db')):
            parts = os.path.basename(f).split('_')
            kind = parts[0]
            db = shelve.open(f)

            for encoded_key, value in db.items():
                payload = dict(
                    key=encoded_key,
                    kind=kind,
                    value=value
                )

                if kind == MetricKind.GAUGE:
                    payload["partition"] = parts[2][:-3]  # pid
                    payload["collect_mode"] = parts[1]

                raw.append(payload)
            db.close()
        return raw


class UWSGICollector(PartitionedCollector):

    @staticmethod
    def _pid_dead(pid, workers):
        """Checks uWSGI worker statuses for the given PID.

        :note:
          The enum of potential statuses is undocumented in uWSGI's Python
          module. The options are:

          - ``cheap``: Worker is killed (has been "cheaped")
          - ``pause``: Worker has been paused or suspended
          - ``sigN``: Worker is handling signal N
          - ``busy``: Worker is alive and currently processing a request
          - ``idle``: Worker is alive and idle

          This implementation simply assumes the status is NOT ``cheap`` or
          ``pause``.
        """
        ws = [w for w in workers if str(w["pid"]) == str(pid)]
        if ws:
            return ws[0]["status"] in ["cheap", "pause"]

        # XXX: If the worker is not in the list of workers, it's probably dead
        return True

    def gather(self):
        import uwsgi

        workers = uwsgi.workers()
        resolution = 1000000

        raw = []
        keys = uwsgi.cache_keys()
        for key in keys:
            if key.startswith("prometheus_"):
                key_body = key.replace("prometheus_", "")
                key_prefix, encoded_key = key_body.split("-")

                parts = key_prefix.split('_')
                kind = parts[0]
                partition = parts[1]

                if len(parts) > 2:
                    collect_mode = parts[1]
                    partition = parts[2]

                value = uwsgi.cache_num(key) / resolution
                payload = dict(
                    key=encoded_key,
                    kind=kind,
                    value=value
                )

                if kind == MetricKind.GAUGE:
                    payload["partition"] = partition
                    payload["collect_mode"] = collect_mode

                    if collect_mode in ["livesum", "liveall"] and self._pid_dead(partition, workers):
                        continue

                raw.append(payload)
        return raw


def mark_process_dead(pid, path=os.environ.get('prometheus_multiproc_dir')):
    """Do bookkeeping for when one process dies in a multi-process setup."""
    for f in glob.glob(os.path.join(path, 'gauge_livesum_{0}.db'.format(pid))):
        os.remove(f)
    for f in glob.glob(os.path.join(path, 'gauge_liveall_{0}.db'.format(pid))):
        os.remove(f)
