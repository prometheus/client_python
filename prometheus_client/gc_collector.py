#!/usr/bin/python

from __future__ import unicode_literals

import gc
import time

from . import core

class GCCollector(object):
    """Collector for Garbage collection statistics."""
    def __init__(self, registry=core.REGISTRY, gc=gc):
        if not hasattr(gc, 'callbacks'):
            return

        collected = core.Histogram(
           'python_gc_collected_objects',
           'Objects collected during gc',
           ['generation'],
           buckets=[500, 1000, 5000, 10000, 50000],
           registry=registry
        )

        uncollectable = core.Histogram(
           'python_gc_uncollectable_objects',
           'Uncollectable object found during GC',
           ['generation'],
           buckets=[500, 1000, 5000, 10000, 50000],
           registry=registry
        )

        latency = core.Histogram(
           'python_gc_duration_seconds',
           'Time spent in garbage collection',
           ['generation'],
           registry=registry
        )

        times = {}

        def _cb(phase, info):
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

        gc.callbacks.append(_cb)


GC_COLLECTOR = GCCollector()
"""Default GCCollector in default Registry REGISTRY."""
