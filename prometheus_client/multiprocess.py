#!/usr/bin/python

from __future__ import unicode_literals

import glob
import json
import os
import shelve

from . import core


class Submetric(object):
    """Simple submetric with a parent and value.
    """

    def __init__(self, name, parent_name, value=None, labels=None, kind=None):
        self.name = name
        self.parent_name = parent_name
        self.value = value
        self.labels = labels
        self.kind = kind
        self.meta = None

    def __repr__(self):
        return "Submetric('{}', '{}', value={}, labels={}, kind='{}')".format(
            self.name,
            self.parent_name,
            self.value,
            self.labels,
            self.kind
        )

    @classmethod
    def from_key(cls, key, kind, value=None):
        """Generates a ``Submetric`` from a legacy encoded key.
        """
        parent_name, name, label_names, label_values = json.loads(key)

        return cls(
            name,
            parent_name,
            value=value,
            labels=zip(label_names, label_values),
            kind=kind
        )


class Metric(object):
    """Full metric that groups submetrics.
    """

    def __init__(self, name=None, kind=None, labels=None):
        self.name = name
        self.kind = kind
        self.labels = labels or []

        self._samples = []
        self._submetrics = []

    def add_submetric(self, submetric):
        """Merges in a new submetric, given it is of the same type.

        :param SingleMetric single_metric:
        """
        if not isinstance(submetric, Submetric):
            raise ValueError(
                "Cannot add item of type '%r', expected 'Submetric'" % type(submetric)
            )

        if self.name != submetric.parent_name:
            raise ValueError("Cannot add submetric with different parent")

        if self.kind != submetric.kind:
            raise ValueError("Cannot add submetrics of different kinds")

        self._submetrics.append(submetric)

    def materialize(self):
        """Express the Metric as a fully-formed Prometheus metric with samples.
        """
        metric = core.Metric(self.name, "Multiprocess metric", self.kind)
        metric.samples = [
            (name, dict(labels), value) for (name, labels), value in self._samples.iteritems()
        ]
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
            name=submetric.parent_name,
            kind=submetric.kind,
            labels=submetric.labels
        )
        metric._submetrics = [submetric]
        return metric


class MergeMetric(object):
    """Metric intended to be merged against others during collection.
    """
    pass


class GaugeMergeMetric(MergeMetric):

    @classmethod
    def build(cls, submetric, samples):
        """Generate samples for this submetric.
        """
        labels_without_partition = tuple([l for l in submetric.labels if l[0] != "partition"])
        key = (submetric.name, labels_without_partition)
        mode = submetric.meta["collect_mode"]

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


class HistogramMergeMetric(MergeMetric):

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

        This method must gather the necessary metrics and set them as a dict
        of a JSON-encoded key to another dict of (at least) value and kind:

        {
            '["h", "h_sum", [], []]': {
                'kind': 'gauge',
                'value': 0.5,
                'partition': '123'
            }
        }
        """
        raise NotImplementedError

    def post_gather(self, raw):
        for data in raw:
            submetric = Submetric.from_key(data["key"], data["kind"], value=data["value"])
            submetric.meta = data.get("meta")

            if data.get("partition") is not None:
                submetric.labels += (("partition", data["partition"]), )

            if submetric.parent_name in self.metrics:
                self.metrics[submetric.parent_name].add_submetric(submetric)
            else:
                self.metrics[submetric.parent_name] = Metric.from_submetric(submetric)

    def collect(self):
        """Entry point that must collect and return from multiple ``Metric``s.
        """
        raise NotImplementedError


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

                if kind == "gauge":
                    payload["partition"] = parts[2][:-3]  # pid
                    payload["meta"] = dict(
                        collect_mode=parts[1]
                    )

                raw.append(payload)
            db.close()
        return raw

    def collect(self):
        """Fold up all metrics properly by kind.
        """
        self.metrics = {}
        raw = self.gather()
        self.post_gather(raw)
            
        results = []
        for metric_key, metric in self.metrics.iteritems():
            samples = {}
            buckets = {}

            for submetric in metric._submetrics:
                if submetric.kind == "gauge":
                    samples = GaugeMergeMetric.build(submetric, samples)
                elif submetric.kind == "histogram":
                    samples, buckets = HistogramMergeMetric.build(
                        submetric,
                        samples,
                        buckets
                    )
                else:
                    # Counter and Summary.
                    key = (submetric.name, tuple(submetric.labels))
                    sample = samples.get(key, 0.0)
                    samples[key] = sample + submetric.value

            # Accumulate bucket values.
            if metric.kind == "histogram":
                for labels, values in buckets.items():
                    acc = 0.0
                    for bucket, value in sorted(values.items()):
                        acc += value
                        samples[(metric.name + '_bucket', labels + (('le', core._floatToGoString(bucket)), ))] = acc
                    samples[(metric.name + '_count', labels)] = acc

            metric._samples = samples
            results.append(metric.materialize())
        return results


def mark_process_dead(pid, path=os.environ.get('prometheus_multiproc_dir')):
    """Do bookkeeping for when one process dies in a multi-process setup."""
    for f in glob.glob(os.path.join(path, 'gauge_livesum_{0}.db'.format(pid))):
        os.remove(f)
    for f in glob.glob(os.path.join(path, 'gauge_liveall_{0}.db'.format(pid))):
        os.remove(f)
