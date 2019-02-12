#!/usr/bin/python

from __future__ import unicode_literals

import gc
import os

from .metrics_core import GaugeMetricFamily
from .registry import REGISTRY


class GCCollector(object):
    """Collector for Garbage collection statistics."""

    def __init__(self, registry=REGISTRY):
        # the GC collector is always disabled in multiprocess mode.
        if 'prometheus_multiproc_dir' in os.environ:
            return

        if not hasattr(gc, 'get_stats'):
            return
        registry.register(self)

    def collect(self):
        collected = GaugeMetricFamily(
            'python_gc_collected_objects',
            'Objects collected during gc',
            labels=['generation'],
        )
        uncollectable = GaugeMetricFamily(
            'python_gc_uncollectable_objects',
            'Uncollectable object found during GC',
            labels=['generation'],
        )

        collections = GaugeMetricFamily(
            'python_gc_collections',
            'Number of times this generation was collected',
            labels=['generation'],
        )

        for generation, stat in enumerate(gc.get_stats()):
            generation = str(generation)
            collected.add_metric([generation], value=stat['collected'])
            uncollectable.add_metric([generation], value=stat['uncollectable'])
            collections.add_metric([generation], value=stat['collections'])

        return [collected, uncollectable, collections]


GC_COLLECTOR = GCCollector()
"""Default GCCollector in default Registry REGISTRY."""
