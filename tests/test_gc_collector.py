from __future__ import unicode_literals

import unittest

from prometheus_client import CollectorRegistry, GCCollector


class TestGCCollector(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.gc = _MockGC()

    def test_working(self):
        collector = GCCollector(registry=self.registry, gc=self.gc)
        self.gc.start_gc({'generation': 0})
        self.gc.stop_gc({'generation': 0, 'collected': 10, 'uncollectable': 2})

        self.assertEqual(1,
            self.registry.get_sample_value(
                'python_gc_duration_seconds_count',
                labels={"generation": "0"}))

        self.assertEqual(1,
            self.registry.get_sample_value(
                'python_gc_collected_objects_count',
                labels={"generation": "0"}))

        self.assertEqual(1,
            self.registry.get_sample_value(
                'python_gc_uncollectable_objects_count',
                labels={"generation": "0"}))

        self.assertEqual(10,
            self.registry.get_sample_value(
                'python_gc_collected_objects_sum',
                labels={"generation": "0"}))

        self.assertEqual(2,
            self.registry.get_sample_value(
                'python_gc_uncollectable_objects_sum',
                labels={"generation": "0"}))


class _MockGC(object):
    def __init__(self):
        self.callbacks = []

    def start_gc(self, info):
        for cb in self.callbacks:
            cb('start', info)

    def stop_gc(self, info):
        for cb in self.callbacks:
            cb('stop', info)
