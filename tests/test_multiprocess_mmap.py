from __future__ import unicode_literals

import glob
import os
import sys
import tempfile
import unittest

import pytest

from prometheus_client import values, Histogram
from prometheus_client.core import Counter
from prometheus_client.multiprocess import mmap_collector, mmap_dict
from prometheus_client.multiprocess.mmaped_value import MmapedValue
from prometheus_client.samples import Sample
from tests.common_multiprocess_tests import CommonMultiprocessTests


class TestMmapMultiProcess(CommonMultiprocessTests, unittest.TestCase):
    _value_class = staticmethod(MmapedValue)
    _collector_class = staticmethod(mmap_collector.MmapMultiProcessCollector)
    _multiprocess_backend = 'mmap'

    def test_initialization_detects_pid_change(self):
        pid = 0
        values.ValueClass = self._value_class(lambda: pid)

        # can not inspect the files cache directly, as it's a closure, so we
        # check for the actual files themselves
        def files():
            fs = os.listdir(os.environ['prometheus_multiproc_dir'])
            fs.sort()
            return fs

        c1 = Counter('c1', 'c1', registry=None)
        self.assertEqual(files(), ['counter_0.db'])
        c2 = Counter('c2', 'c2', registry=None)
        self.assertEqual(files(), ['counter_0.db'])
        pid = 1
        c3 = Counter('c3', 'c3', registry=None)
        self.assertEqual(files(), ['counter_0.db', 'counter_1.db'])

    @pytest.mark.skipif(sys.version_info < (2, 7), reason="Test requires Python 2.7+.")
    def test_merge_no_accumulate(self):
        pid = 0
        values.ValueClass = self._value_class(lambda: pid)
        labels = dict((i, i) for i in 'abcd')

        def add_label(key, value):
            l = labels.copy()
            l[key] = value
            return l

        h = Histogram('h', 'help', labelnames=labels.keys(), registry=None)
        h.labels(**labels).observe(1)
        pid = 1
        h.labels(**labels).observe(5)

        path = os.path.join(os.environ['prometheus_multiproc_dir'], '*.db')
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

        assert expected_histogram == metrics['h'].samples


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
        with pytest.raises(RuntimeError):
            list(self.d.read_all_values())

    def tearDown(self):
        os.unlink(self.tempfile)
