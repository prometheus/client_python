from __future__ import unicode_literals

import gc
import platform
import sys

if sys.version_info < (2, 7):
    # We need the skip decorators from unittest2 on Python 2.6.
    import unittest2 as unittest
else:
    import unittest

from prometheus_client import CollectorRegistry, GCCollector

SKIP = sys.version_info < (3, 4) or platform.python_implementation() != "CPython"


@unittest.skipIf(SKIP, "Test requires CPython 3.4 +")
class TestGCCollector(unittest.TestCase):
    def setUp(self):
        gc.disable()
        gc.collect()
        self.registry = CollectorRegistry()

    def test_working(self):
        GCCollector(registry=self.registry)
        self.registry.collect()
        before = self.registry.get_sample_value('python_gc_objects_collected_total',
                                                labels={"generation": "0"})

        #  add targets for gc
        a = []
        a.append(a)
        del a
        b = []
        b.append(b)
        del b

        gc.collect(0)
        self.registry.collect()

        after = self.registry.get_sample_value('python_gc_objects_collected_total',
                                               labels={"generation": "0"})
        self.assertEqual(2, after - before)
        self.assertEqual(0,
                         self.registry.get_sample_value(
                             'python_gc_objects_uncollectable_total',
                             labels={"generation": "0"}))

    def test_empty(self):
        GCCollector(registry=self.registry)
        self.registry.collect()
        before = self.registry.get_sample_value('python_gc_objects_collected_total',
                                                labels={"generation": "0"})
        gc.collect(0)
        self.registry.collect()

        after = self.registry.get_sample_value('python_gc_objects_collected_total',
                                               labels={"generation": "0"})
        self.assertEqual(0, after - before)

    def tearDown(self):
        gc.enable()
