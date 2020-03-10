#!/usr/bin/python

from __future__ import unicode_literals

from collections import defaultdict
import errno
import glob
import json
import logging
import os
import re
import shutil
import tempfile

from .metrics import Counter, Gauge, Histogram
from .metrics_core import Metric
from .mmap_dict import mmap_key, MmapedDict
from .samples import Sample
from .utils import floatToGoString


PROMETHEUS_MULTIPROC_DIR = "prometheus_multiproc_dir"
_db_pattern = re.compile(r"(\w+)_(\d+)\.db")


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
            parts = os.path.splitext(os.path.basename(f))[0].split('_')
            typ = parts[0]
            multiprocess_mode = parts[1] if typ == Gauge._type else None
            pid = parts[2] if multiprocess_mode and len(parts) > 2 else None
            try:
                d = MmapedDict(f, read_mode=True)
            except EnvironmentError:
                # The liveall and livesum gauge metrics, which only track
                # metrics from live processes, are deleted when the worker
                # process dies (mark_process_dead and, in postal-main,
                # boot.gunicornconf.child_exit).
                # Additionally, we have a single thread which will collect
                # metrics files from dead workers, and merge them into a set of
                # archive files at regular interviews (see
                # multiprocess_exporter).
                # Since collecting the files to
                # merge and reading those files are non-atomic, it's very
                # possible, and expected, that these files will not exist at
                # this point
                continue
            for key, value, timestamp in d.read_all_values():
                metric_name, name, labels = json.loads(key)
                if pid:
                    labels["pid"] = pid
                labels_key = tuple(sorted(labels.items()))

                metric = metrics.get(metric_name)
                if metric is None:
                    metric = Metric(metric_name, 'Multiprocess metric', typ)
                    metrics[metric_name] = metric
                if multiprocess_mode:
                    metric._multiprocess_mode = multiprocess_mode
                metric.add_sample(name, labels_key, value, timestamp=timestamp)
            d.close()

        for metric in metrics.itervalues():
            # Handle the Gauge "latest" multiprocess mode type:
            if metric.type == Gauge._type and metric._multiprocess_mode == Gauge.LATEST:
                s = max(metric.samples, key=lambda i: i.timestamp)
                # Group samples by name, labels:
                grouped_samples = defaultdict(list)
                for s in metric.samples:
                    labels = dict(s.labels)
                    if "pid" in labels:
                        del labels["pid"]
                    grouped_samples[s.name, tuple(sorted(labels.items()))].append(s)
                metric.samples = []
                for (name, labels), sample_group in grouped_samples.iteritems():
                    s = max(sample_group, key=lambda i: i.timestamp)
                    metric.samples.append(Sample(name,
                                                 dict(labels),
                                                 value=s.value,
                                                 timestamp=s.timestamp))
                continue

            samples = defaultdict(float)
            buckets = {}
            for s in metric.samples:
                name, labels, value = s.name, s.labels, s.value
                if metric.type == Gauge._type:
                    without_pid = tuple(l for l in labels if l[0] != 'pid')
                    if metric._multiprocess_mode == Gauge.MIN:
                        current = samples.setdefault((name, without_pid), value)
                        if value < current:
                            samples[(s.name, without_pid)] = value
                    elif metric._multiprocess_mode == Gauge.MAX:
                        current = samples.setdefault((name, without_pid), value)
                        if value > current:
                            samples[(s.name, without_pid)] = value
                    elif metric._multiprocess_mode == Gauge.LIVESUM:
                        samples[(name, without_pid)] += value
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
    path = _multiproc_dir() if path is None else path
    _remove_livesum_dbs(pid, path=path)


def _remove_livesum_dbs(pid, path):
    for gauge_type in [Gauge.LIVESUM, Gauge.LIVEALL]:
        _safe_remove("{}/gauge_{}_{}.db".format(path, gauge_type, pid))


def _multiproc_dir():
    return os.environ[PROMETHEUS_MULTIPROC_DIR]


def cleanup_process(pid, prom_dir=None):
    """Aggregate dead worker's metrics into a single archive file."""
    prom_dir = _multiproc_dir() if prom_dir is None else prom_dir

    worker_paths = [
        "counter_{}.db".format(pid),
        "gauge_{}_{}.db".format(Gauge.LATEST, pid),
        "gauge_{}_{}.db".format(Gauge.MAX, pid),
        "gauge_{}_{}.db".format(Gauge.MIN, pid),
        "histogram_{}.db".format(pid),
    ]

    merged_paths = {
        (Histogram._type, None): "histogram.db",
        (Counter._type, None): "counter.db",
        (Gauge._type, Gauge.LATEST): "gauge_{}.db".format(Gauge.LATEST),
        (Gauge._type, Gauge.MAX): "gauge_{}.db".format(Gauge.MAX),
        (Gauge._type, Gauge.MIN): "gauge_{}.db".format(Gauge.MIN),
    }

    merged_paths = {
        k: os.path.join(prom_dir, f) for k, f in merged_paths.iteritems()
    }

    worker_paths = (os.path.join(prom_dir, f) for f in worker_paths)
    worker_paths = filter(os.path.exists, worker_paths)
    if worker_paths:
        all_paths = worker_paths + filter(os.path.exists, merged_paths.values())
        collector = MultiProcessCollector(None, path=prom_dir)
        metrics = collector.merge(all_paths, accumulate=False)
        _write_metrics(metrics, merged_paths)
    for worker_path in worker_paths:
        _safe_remove(worker_path)
    _remove_livesum_dbs(pid, path=prom_dir)


def _safe_remove(p):
    try:
        os.unlink(p)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def _write_metrics(metrics, metric_type_to_dst_path):
    mmaped_dicts = defaultdict(lambda: MmapedDict(tempfile.mktemp()))
    for metric in metrics:
        if metric.type not in [Histogram._type, Counter._type, Gauge._type]:
            continue
        mode = None
        if metric.type == Gauge._type:
            mode = metric._multiprocess_mode
            if mode not in [Gauge.MIN, Gauge.MAX, Gauge.LATEST]:
                continue
        sink = mmaped_dicts[metric.type, mode]

        for sample in metric.samples:
            # prometheus_client 0.4+ adds extra fields
            key = mmap_key(
                metric.name,
                sample.name,
                tuple(sample.labels),
                tuple(sample.labels.values()),
            )
            sink.write_value(key, sample.value, timestamp=sample.timestamp)
    for k, mmaped_dict in mmaped_dicts.iteritems():
        mmaped_dict.close()
        dst_path = metric_type_to_dst_path[k]
        # Replace existing file:
        shutil.move(mmaped_dict._fname, dst_path)


def _is_alive(pid):
    """Check to see if pid is alive"""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def cleanup_dead_processes(root=None):
    """Cleanup/merge database files from dead processes

    This is not threadsafe and should only be called from one thread/process at
    a time (e.g. a single thread on the multiprocess exporter)
    """
    if root is None:
        root = os.environ[PROMETHEUS_MULTIPROC_DIR]
    to_clean = set()
    for dirname, _, filenames in os.walk(root):
        for fname in filenames:
            m = _db_pattern.match(fname)
            if not m:
                continue
            name, pid = m.groups()
            pid = int(pid)
            if pid not in to_clean and not _is_alive(pid):
                to_clean.add(pid)
    for pid in to_clean:
        logging.info("cleaning up worker %r", pid)
        cleanup_process(pid)
