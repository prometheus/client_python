from __future__ import unicode_literals
import os
import shutil
import tempfile
import time
import unittest

import prometheus_client
from prometheus_client.core import *
from prometheus_client.multiprocess import *

class TestMultiProcess(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        os.environ['prometheus_multiproc_dir'] = self.tempdir
        prometheus_client.core._ValueClass = prometheus_client.core._ShelveValue(123)
        self.registry = CollectorRegistry()
        ShelveCollector(self.registry, self.tempdir)

    def tearDown(self):
        del os.environ['prometheus_multiproc_dir']
        shutil.rmtree(self.tempdir)
        prometheus_client.core._ValueClass = prometheus_client.core._MutexValue

    def test_counter_adds(self):
        c1 = Counter('c', 'help', registry=None)
        prometheus_client.core._ValueClass = prometheus_client.core._ShelveValue(456)
        c2 = Counter('c', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('c'))
        c1.inc(1)
        c2.inc(2)
        self.assertEqual(3, self.registry.get_sample_value('c'))

    def test_summary_adds(self):
        s1 = Summary('s', 'help', registry=None)
        prometheus_client.core._ValueClass = prometheus_client.core._ShelveValue(456)
        s2 = Summary('s', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        self.assertEqual(0, self.registry.get_sample_value('s_sum'))
        s1.observe(1)
        s2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value('s_count'))
        self.assertEqual(3, self.registry.get_sample_value('s_sum'))

    def test_histogram_adds(self):
        h1 = Histogram('h', 'help', registry=None)
        prometheus_client.core._ValueClass = prometheus_client.core._ShelveValue(456)
        h2 = Histogram('h', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        self.assertEqual(0, self.registry.get_sample_value('h_sum'))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        h1.observe(1)
        h2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value('h_count'))
        self.assertEqual(3, self.registry.get_sample_value('h_sum'))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))

    def test_gauge_all(self):
        g1 = Gauge('g', 'help', registry=None)
        prometheus_client.core._ValueClass = prometheus_client.core._ShelveValue(456)
        g2 = Gauge('g', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(0, self.registry.get_sample_value('g', {'partition': '456'}))
        g1.set(1)
        g2.set(2)
        mark_process_dead(123, os.environ['prometheus_multiproc_dir'])
        self.assertEqual(1, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'partition': '456'}))

    def test_gauge_liveall(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        prometheus_client.core._ValueClass = prometheus_client.core._ShelveValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        self.assertEqual(0, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(0, self.registry.get_sample_value('g', {'partition': '456'}))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'partition': '456'}))
        mark_process_dead(123, os.environ['prometheus_multiproc_dir'])
        self.assertEqual(None, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'partition': '456'}))

    def test_gauge_min(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        prometheus_client.core._ValueClass = prometheus_client.core._ShelveValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value('g'))

    def test_gauge_max(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        prometheus_client.core._ValueClass = prometheus_client.core._ShelveValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(2, self.registry.get_sample_value('g'))

    def test_gauge_livesum(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        prometheus_client.core._ValueClass = prometheus_client.core._ShelveValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(3, self.registry.get_sample_value('g'))
        mark_process_dead(123, os.environ['prometheus_multiproc_dir'])
        self.assertEqual(2, self.registry.get_sample_value('g'))
