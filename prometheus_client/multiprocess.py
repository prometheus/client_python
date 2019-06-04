#!/usr/bin/python

from __future__ import unicode_literals

from collections import defaultdict
import errno
import glob
import json
import os

from .metrics_core import Metric
from .mmap_dict import MmapedDict
from .samples import Sample
from .utils import floatToGoString

GAUGE_LATEST = "latest"
GAUGE_LIVEALL = "liveall"
GAUGE_LIVESUM = "livesum"
GAUGE_MAX = "max"
GAUGE_MIN = "min"

GAUGES = [
    GAUGE_LATEST,
    GAUGE_LIVEALL,
    GAUGE_LIVESUM,
    GAUGE_MAX,
    GAUGE_MIN,
]


class MultiProcessCollector(object):
    """Collector for files for multi-process mode."""

    def __init__(self, registry, path=None):
        if path is None:
            path = os.environ.get('prometheus_multiproc_dir')
        if not path or not os.path.isdir(path):
            raise ValueError('env prometheus_multiproc_dir is not set or not a directory')
        self._path = path
        if registry:
            registry.register(self)

    @staticmethod
    def merge(files, accumulate=True):
        """Merge metrics from given mmap files.

        By default, histograms are accumulated, as per prometheus wire format.
        But if writing the merged data back to mmap files, use
        accumulate=False to avoid compound accumulation.
        """
        metrics = {}
        for f in files:
            parts = os.path.basename(f).split('_')
            typ = parts[0]
            d = MmapedDict(f, read_mode=True)
            for key, value, ts in d.read_all_values():
                metric_name, name, labels = json.loads(key)
                labels_key = tuple(sorted(labels.items()))

                metric = metrics.get(metric_name)
                if metric is None:
                    metric = Metric(metric_name, 'Multiprocess metric', typ)
                    metrics[metric_name] = metric

                if typ == 'gauge':
                    pid = parts[2][:-3]
                    metric._multiprocess_mode = parts[1]
                    metric.add_sample(name, labels_key + (('pid', pid),), value, timestamp=ts)
                else:
                    # The duplicates and labels are fixed in the next for.
                    metric.add_sample(name, labels_key, value, timestamp=ts)
            d.close()

        for n, metric in metrics.iteritems():
            samples = defaultdict(float)
            buckets = {}
            for s in metric.samples:
                name, labels, value = s.name, s.labels, s.value
                if metric.type == 'gauge':
                    without_pid = tuple(l for l in labels if l[0] != 'pid')
                    if metric._multiprocess_mode == 'min':
                        current = samples.setdefault((name, without_pid), value)
                        if value < current:
                            samples[(s.name, without_pid)] = value
                    elif metric._multiprocess_mode == 'max':
                        current = samples.setdefault((name, without_pid), value)
                        if value > current:
                            samples[(s.name, without_pid)] = value
                    elif metric._multiprocess_mode == 'livesum':
                        samples[(name, without_pid)] += value
                    elif metric._multiprocess_mode == "livelatest":
                        continue
                    else:  # all/liveall
                        samples[(name, labels)] = value

                elif metric.type == 'histogram':
                    bucket = tuple(float(l[1]) for l in labels if l[0] == 'le')
                    if bucket:
                        # _bucket
                        without_le = tuple(l for l in labels if l[0] != 'le')
                        buckets.setdefault(without_le, {})
                        buckets[without_le].setdefault(bucket[0], 0.0)
                        buckets[without_le][bucket[0]] += value
                    else:
                        # _sum/_count
                        samples[(s.name, labels)] += value
                else:
                    # Counter and Summary.
                    samples[(s.name, labels)] += value

            # Handle the livelatest gauge multiprocess mode type:
            # The livelatest gauge stores a pair value named $(METRIC_NAME)_at with the updated timestamp
            # Each we see a livelatest metric, lookup the "at" value for each sample pid and choose the latest value:
            if metric.type == "gauge" and metric._multiprocess_mode == "livelatest":
                at_pid = []
                for s in metric.samples:
                    if s.name.endswith("_at"):
                        labels = dict(s.labels)
                        at_pid.append((s.value, labels["pid"]))
                if at_pid:
                    ts, pid = max(at_pid)
                    for s in metric.samples:
                        if s.name.endswith("_at"):
                            continue
                        labels = dict(s.labels)
                        if labels["pid"] == pid:
                            del labels["pid"]
                            metric.samples = [Sample(s.name,
                                                     labels=labels,
                                                     value=s.value,
                                                     timestamp=ts)]
                            break
                continue

            # Accumulate bucket values.
            if metric.type == 'histogram':
                for labels, values in buckets.items():
                    acc = 0.0
                    for bucket, value in sorted(values.items()):
                        sample_key = (
                            metric.name + '_bucket',
                            labels + (('le', floatToGoString(bucket)),),
                        )
                        if accumulate:
                            acc += value
                            samples[sample_key] = acc
                        else:
                            samples[sample_key] = value
                    if accumulate:
                        samples[(metric.name + '_count', labels)] = acc
            # Convert to correct sample format.
            metric.samples = [Sample(name_, dict(labels), value) for (name_, labels), value in samples.items()]
        return metrics.values()

    def collect(self):
        files = glob.glob(os.path.join(self._path, '*.db'))
        return self.merge(files, accumulate=True)


def mark_process_dead(pid, path=None):
    """Do bookkeeping for when one process dies in a multi-process setup."""
    if path is None:
        path = os.environ.get('prometheus_multiproc_dir')
    for gauge_type in GAUGES:
        try:
            os.unlink("{}/gauge_{}_{}.db".format(path, gauge_type, pid))
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
