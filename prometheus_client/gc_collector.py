#!/usr/bin/python

from __future__ import unicode_literals

import gc
import os
import time

from .metrics import Histogram
from .registry import REGISTRY


class GCCollector(object):
    """Collector for Garbage collection statistics."""

    def __init__(self, registry=REGISTRY, gc=gc):
        # To work around the deadlock issue described in
        # https://github.com/prometheus/client_python/issues/322,
        # the GC collector is always disabled in multiprocess mode.
        if 'prometheus_multiproc_dir' in os.environ:
            return

        if not hasattr(gc, 'callbacks'):
            return

        collected = Histogram(
            'python_gc_collected_objects',
            'Objects collected during gc',
            ['generation'],
            buckets=[500, 1000, 5000, 10000, 50000],
            registry=registry
        )

        uncollectable = Histogram(
            'python_gc_uncollectable_objects',
            'Uncollectable object found during GC',
            ['generation'],
            buckets=[500, 1000, 5000, 10000, 50000],
            registry=registry
        )

        latency = Histogram(
            'python_gc_duration_seconds',
            'Time spent in garbage collection',
            ['generation'],
            registry=registry
        )

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
                    latency.labels(gen).observe(delta)
                    if 'collected' in info:
                        collected.labels(gen).observe(info['collected'])
                    if 'uncollectable' in info:
                        uncollectable.labels(gen).observe(info['uncollectable'])
            finally:
                self.gc_cb_active = False

        gc.callbacks.append(_cb)


GC_COLLECTOR = GCCollector()
"""Default GCCollector in default Registry REGISTRY."""
