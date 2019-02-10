from __future__ import unicode_literals

import gc
import sys

if sys.version_info < (2, 7):
    # We need the skip decorators from unittest2 on Python 2.6.
    import unittest2 as unittest
else:
    import unittest

from prometheus_client import CollectorRegistry, GCCollector


@unittest.skipIf(sys.version_info < (3, ), "Test requires Python 3.+")
class TestGCCollector(unittest.TestCase):
    def setUp(self):
        gc.disable()
        gc.collect()
        self.registry = CollectorRegistry()

    def test_working(self):

        GCCollector(registry=self.registry)

        #  add targets for gc
        a = []
        a.append(a)
        del a
        b = []
        b.append(b)
        del b

        gc.collect(0)
        self.registry.collect()

        self.assertEqual(1,
                         self.registry.get_sample_value(
                             'python_gc_duration_seconds_count',
                             labels={"generation": "0"}))
        self.assertEqual(1,
                         self.registry.get_sample_value(
                             'python_gc_duration_seconds_bucket',
                             labels={"generation": "0", "le": 0.005}))

        self.assertEqual(1,
                         self.registry.get_sample_value(
                             'python_gc_collected_objects_count',
                             labels={"generation": "0"}))

        self.assertEqual(2,
                         self.registry.get_sample_value(
                             'python_gc_collected_objects_sum',
                             labels={"generation": "0"}))
        self.assertEqual(1,
                         self.registry.get_sample_value(
                             'python_gc_collected_objects_bucket',
                             labels={
                                 "generation": "0",
                                 "le": gc.get_threshold()[0] * 2 / 100
                             }))

    def test_empty(self):

        GCCollector(registry=self.registry)
        gc.collect(0)
        self.registry.collect()

        self.assertEqual(1,
                         self.registry.get_sample_value(
                             'python_gc_duration_seconds_count',
                             labels={"generation": "0"}))
        self.assertEqual(1,
                         self.registry.get_sample_value(
                             'python_gc_duration_seconds_bucket',
                             labels={"generation": "0", "le": 0.005}))

        self.assertIsNone(self.registry.get_sample_value(
                             'python_gc_collected_objects_count',
                             labels={"generation": "0"}))

        self.assertIsNone(self.registry.get_sample_value(
                             'python_gc_collected_objects_sum',
                             labels={"generation": "0"}))

        self.assertIsNone(self.registry.get_sample_value(
                             'python_gc_collected_objects_bucket',
                             labels={"generation": "0", "le": 7}))

    def tearDown(self):
        gc.enable()
