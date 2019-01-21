from __future__ import unicode_literals

import os
import shutil
import sys
import tempfile

import pytest

from prometheus_client import values
from prometheus_client.core import (
    CollectorRegistry, Counter, Gauge, Histogram, Sample, Summary,
)
import prometheus_client.multiprocess as multiprocess


class CommonMultiprocessTests:

    _multiprocess_backend = None
    _collector_class = None
    _value_class = None

    def setUp(self):
        multiprocess.multiprocess_backend = self._multiprocess_backend
        self.tempdir = tempfile.mkdtemp()
        os.environ['prometheus_multiproc_dir'] = self.tempdir
        values.ValueClass = self._value_class(lambda: 123)
        self.registry = CollectorRegistry()
        self.collector = self._collector_class(self.registry, path=self.tempdir)

    def tearDown(self):
        del os.environ['prometheus_multiproc_dir']
        shutil.rmtree(self.tempdir)
        multiprocess.multiprocess_backend = None
        values.ValueClass = values.MutexValue

    def test_counter_adds(self):
        c1 = Counter('c', 'help', registry=None)
        values.ValueClass = self._value_class(lambda: 456)
        c2 = Counter('c', 'help', registry=None)
        assert self.registry.get_sample_value('c_total') == 0
        c1.inc(1)
        c2.inc(2)
        assert self.registry.get_sample_value('c_total') == 3

    def test_summary_adds(self):
        s1 = Summary('s', 'help', registry=None)
        values.ValueClass = self._value_class(lambda: 456)
        s2 = Summary('s', 'help', registry=None)
        assert self.registry.get_sample_value('s_count') == 0
        assert self.registry.get_sample_value('s_sum') == 0
        s1.observe(1)
        s2.observe(2)
        assert self.registry.get_sample_value('s_count') == 2
        assert self.registry.get_sample_value('s_sum') == 3

    def test_histogram_adds(self):
        h1 = Histogram('h', 'help', registry=None)
        values.ValueClass = self._value_class(lambda: 456)
        h2 = Histogram('h', 'help', registry=None)
        assert self.registry.get_sample_value('h_count') == 0
        assert self.registry.get_sample_value('h_sum') == 0
        assert self.registry.get_sample_value('h_bucket', {'le': '5.0'}) == 0
        h1.observe(1)
        h2.observe(2)
        assert self.registry.get_sample_value('h_count') == 2
        assert self.registry.get_sample_value('h_sum') == 3
        assert self.registry.get_sample_value('h_bucket', {'le': '5.0'}) == 2

    def test_gauge_all(self):
        g1 = Gauge('g', 'help', registry=None)
        values.ValueClass = self._value_class(lambda: 456)
        g2 = Gauge('g', 'help', registry=None)
        assert self.registry.get_sample_value('g', {'pid': '123'}) == 0
        assert self.registry.get_sample_value('g', {'pid': '456'}) == 0
        g1.set(1)
        g2.set(2)
        multiprocess.mark_process_dead(123, os.environ['prometheus_multiproc_dir'])
        assert self.registry.get_sample_value('g', {'pid': '123'}) == 1
        assert self.registry.get_sample_value('g', {'pid': '456'}) == 2

    def test_gauge_liveall(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        values.ValueClass = self._value_class(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        assert self.registry.get_sample_value('g', {'pid': '123'}) == 0
        assert self.registry.get_sample_value('g', {'pid': '456'}) == 0
        g1.set(1)
        g2.set(2)
        assert self.registry.get_sample_value('g', {'pid': '123'}) == 1
        assert self.registry.get_sample_value('g', {'pid': '456'}) == 2
        multiprocess.mark_process_dead(123, os.environ['prometheus_multiproc_dir'])
        assert self.registry.get_sample_value('g', {'pid': '123'}) == None
        assert self.registry.get_sample_value('g', {'pid': '456'}) == 2

    def test_gauge_min(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        values.ValueClass = self._value_class(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        assert self.registry.get_sample_value('g') == 0
        g1.set(1)
        g2.set(2)
        assert self.registry.get_sample_value('g') == 1

    def test_gauge_max(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        values.ValueClass = self._value_class(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        assert self.registry.get_sample_value('g') == 0
        g1.set(1)
        g2.set(2)
        assert self.registry.get_sample_value('g') == 2

    def test_gauge_livesum(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        values.ValueClass = self._value_class(lambda: 456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        assert self.registry.get_sample_value('g') == 0
        g1.set(1)
        g2.set(2)
        assert self.registry.get_sample_value('g') == 3
        multiprocess.mark_process_dead(123, os.environ['prometheus_multiproc_dir'])
        assert self.registry.get_sample_value('g') == 2

    def test_namespace_subsystem(self):
        c1 = Counter('c', 'help', registry=None, namespace='ns', subsystem='ss')
        c1.inc(1)
        assert self.registry.get_sample_value('ns_ss_c_total') == 1

    def test_counter_across_forks(self):
        pid = 0
        values.ValueClass = self._value_class(lambda: pid)
        c1 = Counter('c', 'help', registry=None)
        assert self.registry.get_sample_value('c_total') == 0
        c1.inc(1)
        c1.inc(1)
        pid = 1
        c1.inc(1)
        assert self.registry.get_sample_value('c_total') == 3
        assert c1._value.get() == 1

    @pytest.mark.skipif(sys.version_info < (2, 7), reason="Test requires Python 2.7+.")
    def test_collect(self):
        pid = 0
        values.ValueClass = self._value_class(lambda: pid)
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

        assert metrics['c'].samples == [Sample('c_total', labels, 2.0)]
        metrics['g'].samples.sort(key=lambda x: x[1]['pid'])
        assert metrics['g'].samples == [
            Sample('g', add_label('pid', '0'), 1.0),
            Sample('g', add_label('pid', '1'), 1.0),
        ]

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

        assert expected_histogram == metrics['h'].samples
