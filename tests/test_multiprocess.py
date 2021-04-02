from __future__ import unicode_literals

import glob
import os
import shutil
import sys
import tempfile
import warnings

from prometheus_client import mmap_dict, values
from prometheus_client.core import (
    CollectorRegistry, Counter, Gauge, Histogram, Sample, Summary,
)
from prometheus_client.multiprocess import (
    mark_process_dead, MultiProcessCollector,
)
from prometheus_client.values import (
    get_value_class, MultiProcessValue, MutexValue,
)

if sys.version_info < (2, 7):
    # We need the skip decorators from unittest2 on Python 2.6.
    import unittest2 as unittest
else:
    import unittest


class TestMultiProcessDeprecation(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        del os.environ['prometheus_multiproc_dir']
        del os.environ['PROMETHEUS_MULTIPROC_DIR']
        values.ValueClass = MutexValue
        shutil.rmtree(self.tempdir)

    def test_deprecation_warning(self):
        os.environ['prometheus_multiproc_dir'] = self.tempdir
        with warnings.catch_warnings(record=True) as w:
            values.ValueClass = get_value_class()
            registry = CollectorRegistry()
            collector = MultiProcessCollector(registry)
            Counter('c', 'help', registry=None)

            assert os.environ['PROMETHEUS_MULTIPROC_DIR'] == self.tempdir
            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert "PROMETHEUS_MULTIPROC_DIR" in str(w[-1].message)


class TestMultiProcess(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        os.environ['PROMETHEUS_MULTIPROC_DIR'] = self.tempdir
        values.ValueClass = MultiProcessValue(lambda: 123)
        self.registry = CollectorRegistry()
        self.collector = MultiProcessCollector(self.registry)

    @property
    def _value_class(self):
        return

    def tearDown(self):
        del os.environ['PROMETHEUS_MULTIPROC_DIR']
        shutil.rmtree(self.tempdir)
        values.ValueClass = MutexValue

    def test_counter_adds(self):
        c1 = Counter('c', 'help', registry=None)
        values.ValueClass = MultiProcessValue(lambda: 456)
        c2 = Counter('c', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('c_total'))
        c1.inc(1)
        c2.inc(2)
        self.assertEqual(3, self.registry.get_sample_value('c_total'))

    def test_summary_adds(self):
        s1 = Summary('s', 'help', registry=None)
        values.ValueClass = MultiProcessValue(lambda: 456)
        s2 = Summary('s', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        self.assertEqual(0, self.registry.get_sample_value('s_sum'))
        s1.observe(1)
        s2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value('s_count'))
        self.assertEqual(3, self.registry.get_sample_value('s_sum'))

    def test_histogram_adds(self):
        h1 = Histogram('h', 'help', registry=None)
        values.ValueClass = MultiProcessValue(lambda: 456)
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
        values.ValueClass = MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(0, self.registry.get_sample_value('g', {'pid': '456'}))
        g1.set(1)
        g2.set(2)
        mark_process_dead(123)
        self.assertEqual(1, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'pid': '456'}))

    def test_gauge_liveall(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        values.ValueClass = MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        self.assertEqual(0, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(0, self.registry.get_sample_value('g', {'pid': '456'}))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'pid': '456'}))
        mark_process_dead(123, os.environ['PROMETHEUS_MULTIPROC_DIR'])
        self.assertEqual(None, self.registry.get_sample_value('g', {'pid': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'pid': '456'}))

    def test_gauge_min(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        values.ValueClass = MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value('g'))

    def test_gauge_max(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        values.ValueClass = MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(2, self.registry.get_sample_value('g'))

    def test_gauge_livesum(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        values.ValueClass = MultiProcessValue(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(3, self.registry.get_sample_value('g'))
        mark_process_dead(123, os.environ['PROMETHEUS_MULTIPROC_DIR'])
        self.assertEqual(2, self.registry.get_sample_value('g'))

    def test_namespace_subsystem(self):
        c1 = Counter('c', 'help', registry=None, namespace='ns', subsystem='ss')
        c1.inc(1)
        self.assertEqual(1, self.registry.get_sample_value('ns_ss_c_total'))

    def test_counter_across_forks(self):
        pid = 0
        values.ValueClass = MultiProcessValue(lambda: pid)
        c1 = Counter('c', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('c_total'))
        c1.inc(1)
        c1.inc(1)
        pid = 1
        c1.inc(1)
        self.assertEqual(3, self.registry.get_sample_value('c_total'))
        self.assertEqual(1, c1._value.get())

    def test_initialization_detects_pid_change(self):
        pid = 0
        values.ValueClass = MultiProcessValue(lambda: pid)

        # can not inspect the files cache directly, as it's a closure, so we
        # check for the actual files themselves
        def files():
            fs = os.listdir(os.environ['PROMETHEUS_MULTIPROC_DIR'])
            fs.sort()
            return fs

        c1 = Counter('c1', 'c1', registry=None)
        self.assertEqual(files(), ['counter_0.db'])
        c2 = Counter('c2', 'c2', registry=None)
        self.assertEqual(files(), ['counter_0.db'])
        pid = 1
        c3 = Counter('c3', 'c3', registry=None)
        self.assertEqual(files(), ['counter_0.db', 'counter_1.db'])

    @unittest.skipIf(sys.version_info < (2, 7), "Test requires Python 2.7+.")
    def test_collect(self):
        pid = 0
        values.ValueClass = MultiProcessValue(lambda: pid)
        labels = dict((i, i) for i in 'abcd')

        def add_label(key, value):
            l = labels.copy()
            l[key] = value
            return l

        c = Counter('c', 'help', labelnames=labels.keys(), registry=None)
        g = Gauge('g', 'help', labelnames=labels.keys(), registry=None)
        h = Histogram('h', 'help', labelnames=labels.keys(), registry=None)

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)
        h.labels(**labels).observe(1)

        pid = 1

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)
        h.labels(**labels).observe(5)

        metrics = dict((m.name, m) for m in self.collector.collect())

        self.assertEqual(
            metrics['c'].samples, [Sample('c_total', labels, 2.0)]
        )
        metrics['g'].samples.sort(key=lambda x: x[1]['pid'])
        self.assertEqual(metrics['g'].samples, [
            Sample('g', add_label('pid', '0'), 1.0),
            Sample('g', add_label('pid', '1'), 1.0),
        ])

        metrics['h'].samples.sort(
            key=lambda x: (x[0], float(x[1].get('le', 0)))
        )
        expected_histogram = [
            Sample('h_bucket', add_label('le', '0.005'), 0.0),
            Sample('h_bucket', add_label('le', '0.01'), 0.0),
            Sample('h_bucket', add_label('le', '0.025'), 0.0),
            Sample('h_bucket', add_label('le', '0.05'), 0.0),
            Sample('h_bucket', add_label('le', '0.075'), 0.0),
            Sample('h_bucket', add_label('le', '0.1'), 0.0),
            Sample('h_bucket', add_label('le', '0.25'), 0.0),
            Sample('h_bucket', add_label('le', '0.5'), 0.0),
            Sample('h_bucket', add_label('le', '0.75'), 0.0),
            Sample('h_bucket', add_label('le', '1.0'), 1.0),
            Sample('h_bucket', add_label('le', '2.5'), 1.0),
            Sample('h_bucket', add_label('le', '5.0'), 2.0),
            Sample('h_bucket', add_label('le', '7.5'), 2.0),
            Sample('h_bucket', add_label('le', '10.0'), 2.0),
            Sample('h_bucket', add_label('le', '+Inf'), 2.0),
            Sample('h_count', labels, 2.0),
            Sample('h_sum', labels, 6.0),
        ]

        self.assertEqual(metrics['h'].samples, expected_histogram)

    @unittest.skipIf(sys.version_info < (2, 7), "Test requires Python 2.7+.")
    def test_merge_no_accumulate(self):
        pid = 0
        values.ValueClass = MultiProcessValue(lambda: pid)
        labels = dict((i, i) for i in 'abcd')

        def add_label(key, value):
            l = labels.copy()
            l[key] = value
            return l

        h = Histogram('h', 'help', labelnames=labels.keys(), registry=None)
        h.labels(**labels).observe(1)
        pid = 1
        h.labels(**labels).observe(5)

        path = os.path.join(os.environ['PROMETHEUS_MULTIPROC_DIR'], '*.db')
        files = glob.glob(path)
        metrics = dict(
            (m.name, m) for m in self.collector.merge(files, accumulate=False)
        )

        metrics['h'].samples.sort(
            key=lambda x: (x[0], float(x[1].get('le', 0)))
        )
        expected_histogram = [
            Sample('h_bucket', add_label('le', '0.005'), 0.0),
            Sample('h_bucket', add_label('le', '0.01'), 0.0),
            Sample('h_bucket', add_label('le', '0.025'), 0.0),
            Sample('h_bucket', add_label('le', '0.05'), 0.0),
            Sample('h_bucket', add_label('le', '0.075'), 0.0),
            Sample('h_bucket', add_label('le', '0.1'), 0.0),
            Sample('h_bucket', add_label('le', '0.25'), 0.0),
            Sample('h_bucket', add_label('le', '0.5'), 0.0),
            Sample('h_bucket', add_label('le', '0.75'), 0.0),
            Sample('h_bucket', add_label('le', '1.0'), 1.0),
            Sample('h_bucket', add_label('le', '2.5'), 0.0),
            Sample('h_bucket', add_label('le', '5.0'), 1.0),
            Sample('h_bucket', add_label('le', '7.5'), 0.0),
            Sample('h_bucket', add_label('le', '10.0'), 0.0),
            Sample('h_bucket', add_label('le', '+Inf'), 0.0),
            Sample('h_sum', labels, 6.0),
        ]

        self.assertEqual(metrics['h'].samples, expected_histogram)

    def test_missing_gauge_file_during_merge(self):
        # These files don't exist, just like if mark_process_dead(9999999) had been
        # called during self.collector.collect(), after the glob found it
        # but before the merge actually happened.
        # This should not raise and return no metrics
        self.assertFalse(self.collector.merge([
            os.path.join(self.tempdir, 'gauge_liveall_9999999.db'),
            os.path.join(self.tempdir, 'gauge_livesum_9999999.db'),
        ]))


class TestMmapedDict(unittest.TestCase):
    def setUp(self):
        fd, self.tempfile = tempfile.mkstemp()
        os.close(fd)
        self.d = mmap_dict.MmapedDict(self.tempfile)

    def test_process_restart(self):
        self.d.write_value('abc', 123.0)
        self.d.close()
        self.d = mmap_dict.MmapedDict(self.tempfile)
        self.assertEqual(123, self.d.read_value('abc'))
        self.assertEqual([('abc', 123.0)], list(self.d.read_all_values()))

    def test_expansion(self):
        key = 'a' * mmap_dict._INITIAL_MMAP_SIZE
        self.d.write_value(key, 123.0)
        self.assertEqual([(key, 123.0)], list(self.d.read_all_values()))

    def test_multi_expansion(self):
        key = 'a' * mmap_dict._INITIAL_MMAP_SIZE * 4
        self.d.write_value('abc', 42.0)
        self.d.write_value(key, 123.0)
        self.d.write_value('def', 17.0)
        self.assertEqual(
            [('abc', 42.0), (key, 123.0), ('def', 17.0)],
            list(self.d.read_all_values()))

    def test_corruption_detected(self):
        self.d.write_value('abc', 42.0)
        # corrupt the written data
        self.d._m[8:16] = b'somejunk'
        with self.assertRaises(RuntimeError):
            list(self.d.read_all_values())

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
