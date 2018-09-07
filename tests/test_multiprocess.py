from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

from prometheus_client import core
from prometheus_client.core import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
)
from prometheus_client.multiprocess import (
    mark_process_dead,
    MultiProcessCollector,
)


class TestMultiProcess(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        os.environ['prometheus_multiproc_dir'] = self.tempdir
        core._ValueClass = core._MultiProcessValue(lambda: 123)
        self.registry = CollectorRegistry()
        MultiProcessCollector(self.registry, self.tempdir)

    def tearDown(self):
        del os.environ['prometheus_multiproc_dir']
        shutil.rmtree(self.tempdir)
        core._ValueClass = core._MutexValue

    def test_counter_adds(self):
        c1 = Counter('c', 'help', registry=None)
        core._ValueClass = core._MultiProcessValue(lambda: 456)
        c2 = Counter('c', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('c_total'))
        c1.inc(1)
        c2.inc(2)
        self.assertEqual(3, self.registry.get_sample_value('c_total'))

    def test_summary_adds(self):
        s1 = Summary('s', 'help', registry=None)
        core._ValueClass = core._MultiProcessValue(lambda: 456)
        s2 = Summary('s', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        self.assertEqual(0, self.registry.get_sample_value('s_sum'))
        s1.observe(1)
        s2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value('s_count'))
        self.assertEqual(3, self.registry.get_sample_value('s_sum'))

    def test_histogram_adds(self):
        h1 = Histogram('h', 'help', registry=None)
        core._ValueClass = core._MultiProcessValue(lambda: 456)
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
        core._ValueClass = core._MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(0, self.registry.get_sample_value('g', {'pid': '456'}))
        g1.set(1)
        g2.set(2)
        mark_process_dead(123, os.environ['prometheus_multiproc_dir'])
        self.assertEqual(1, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'pid': '456'}))

    def test_gauge_liveall(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        core._ValueClass = core._MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        self.assertEqual(0, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(0, self.registry.get_sample_value('g', {'pid': '456'}))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'pid': '456'}))
        mark_process_dead(123, os.environ['prometheus_multiproc_dir'])
        self.assertEqual(None, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'pid': '456'}))

    def test_gauge_min(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        core._ValueClass = core._MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value('g'))

    def test_gauge_max(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        core._ValueClass = core._MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(2, self.registry.get_sample_value('g'))

    def test_gauge_livesum(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        core._ValueClass = core._MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(3, self.registry.get_sample_value('g'))
        mark_process_dead(123, os.environ['prometheus_multiproc_dir'])
        self.assertEqual(2, self.registry.get_sample_value('g'))

    def test_namespace_subsystem(self):
         c1 = Counter('c', 'help', registry=None, namespace='ns', subsystem='ss')
         c1.inc(1)
         self.assertEqual(1, self.registry.get_sample_value('ns_ss_c_total'))

    def test_counter_across_forks(self):
        pid = 0
        core._ValueClass = core._MultiProcessValue(lambda: pid)
        c1 = Counter('c', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('c_total'))
        c1.inc(1)
        c1.inc(1)
        pid = 1
        c1.inc(1)
        self.assertEqual(3, self.registry.get_sample_value('c_total'))
        self.assertEqual(1, c1._value.get())


class TestMmapedDict(unittest.TestCase):
    def setUp(self):
        fd, self.tempfile = tempfile.mkstemp()
        os.close(fd)
        self.d = core._MmapedDict(self.tempfile)

    def test_process_restart(self):
        self.d.write_value('abc', 123.0)
        self.d.close()
        self.d = core._MmapedDict(self.tempfile)
        self.assertEqual(123, self.d.read_value('abc'))
        self.assertEqual([('abc', 123.0)], list(self.d.read_all_values()))

    def test_expansion(self):
        key = 'a' * core._INITIAL_MMAP_SIZE
        self.d.write_value(key, 123.0)
        self.assertEqual([(key, 123.0)], list(self.d.read_all_values()))

    def test_multi_expansion(self):
        key = 'a' * core._INITIAL_MMAP_SIZE * 4
        self.d.write_value('abc', 42.0)
        self.d.write_value(key, 123.0)
        self.d.write_value('def', 17.0)
        self.assertEqual(
            [('abc', 42.0), (key, 123.0), ('def', 17.0)],
            list(self.d.read_all_values()))

    def tearDown(self):
        os.unlink(self.tempfile)


class TestUnsetEnv(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        fp, self.tmpfl = tempfile.mkstemp()
        os.close(fp)

    def test_unset_syncdir_env(self):
        self.assertRaises(
            ValueError, MultiProcessCollector, self.registry)

    def test_file_syncpath(self):
        registry = CollectorRegistry()
        self.assertRaises(
            ValueError, MultiProcessCollector, registry, self.tmpfl)

    def tearDown(self):
        os.remove(self.tmpfl)
