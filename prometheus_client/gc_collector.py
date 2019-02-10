#!/usr/bin/python

from __future__ import unicode_literals

import gc
import os
import time
from collections import defaultdict

from .metrics_core import HistogramMetricFamily
from .registry import REGISTRY
from .utils import INF


class GCCollector(object):
    """Collector for Garbage collection statistics."""

    _LATENCY = 'latency'
    _COLLECTED = 'collected'
    _UNCOLLECTABLE = 'uncollectable'

    def __init__(self, registry=REGISTRY):
        # To work around the deadlock issue described in
        # https://github.com/prometheus/client_python/issues/322,
        # the GC collector is always disabled in multiprocess mode.
        if 'prometheus_multiproc_dir' in os.environ:
            return

        if not hasattr(gc, 'callbacks'):
            return

        self._buckets = [{
            self._LATENCY: defaultdict(lambda: 0.0),
            self._COLLECTED: defaultdict(lambda: 0),
            self._UNCOLLECTABLE: defaultdict(lambda: 0),
        } for _ in [0, 1, 2]]

        self._sums = [{
            self._LATENCY: 0.0,
            self._COLLECTED: 0,
            self._UNCOLLECTABLE: 0,
        } for _ in [0, 1, 2]]

        times = {}

        # Avoid _cb() being called re-entrantly
        # by setting this flag and clearing it once
        # the callback operation is complete.
        # See https://github.com/prometheus/client_python/issues/322#issuecomment-438021132
        self.gc_cb_active = False

        def _cb(phase, info):
            try:
                if self.gc_cb_active:
                    return
                self.gc_cb_active = True

                gen = info['generation']

                if phase == 'start':
                    times[gen] = time.time()

                if phase == 'stop':
                    delta = time.time() - times[gen]
                    self._add_to_bucket(self._LATENCY, gen, delta)
                    if 'collected' in info and info['collected'] != 0:
                        self._add_to_bucket(self._COLLECTED, gen, info['collected'])
                    if 'uncollectable' in info and info['uncollectable'] != 0:
                        self._add_to_bucket(self._UNCOLLECTABLE, gen, info['uncollectable'])
            finally:
                self.gc_cb_active = False

        gc.callbacks.append(_cb)
        registry.register(self)

    def _add_to_bucket(self, bucket_name, gen, value):
        bucket = self._buckets[gen][bucket_name]
        self._sums[gen][bucket_name] += value

        for bound in self._get_bounds(gen, bucket_name):
            if value <= bound:
                bucket[INF] += 1
                bucket[bound] += 1
                break

    @staticmethod
    def _get_bounds(gen, bucket_name):
        if bucket_name == GC_COLLECTOR._LATENCY:
            return .005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0
        _max = gc.get_threshold()[gen] * 2
        return int(_max / 100), int(_max / 50), int(_max / 10), int(_max / 5), int(_max / 2), _max

    def collect(self):
        collected = HistogramMetricFamily(
            'python_gc_collected_objects',
            'Objects collected during gc',
            labels=['generation'],
        )
        uncollectable = HistogramMetricFamily(
            'python_gc_uncollectable_objects',
            'Uncollectable object found during GC',
            labels=['generation'],
        )

        latency = HistogramMetricFamily(
            'python_gc_duration_seconds',
            'Time spent in garbage collection',
            labels=['generation'],
        )

        for generation, buckets in enumerate(self._buckets):
            _sums = self._sums[generation]
            generation = str(generation)

            if _sums[self._LATENCY] != 0:
                latency.add_metric([generation], buckets=list(buckets[self._LATENCY].items()),
                                   sum_value=_sums[self._LATENCY])
            if _sums[self._COLLECTED] != 0:
                collected.add_metric([generation], buckets=list(buckets[self._COLLECTED].items()),
                                     sum_value=_sums[self._COLLECTED])
            if _sums[self._UNCOLLECTABLE] != 0:
                uncollectable.add_metric([generation], buckets=list(buckets[self._UNCOLLECTABLE].items()),
                                         sum_value=_sums[self._UNCOLLECTABLE])
        return [collected, uncollectable, latency]


GC_COLLECTOR = GCCollector()
"""Default GCCollector in default Registry REGISTRY."""
