from __future__ import unicode_literals
import os
import shutil
import tempfile
import time
import unittest

from mock import patch

import prometheus_client
from prometheus_client.core import *
from prometheus_client.multiprocess import *

class TestMultiProcess(unittest.TestCase):
    def setUp(self):
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(123)
        self.registry = CollectorRegistry()
        UWSGICollector(self.registry)

        import uwsgi
        uwsgi.cache_clear()

    def tearDown(self):
        prometheus_client.core._ValueClass = prometheus_client.core._MutexValue

    def test_pid_alive(self):
        ws = (
            {
                "pid": 123,
                "status": "idle"
            },
        )
        self.assertFalse(UWSGICollector._pid_dead(123, ws))

    def test_pid_dead(self):
        ws = (
            {
                "pid": 456,
                "status": "cheap"
            },
        )
        self.assertTrue(UWSGICollector._pid_dead(456, ws))

    def test_pid_not_in_workers(self):
        ws = (
            {
                "pid": 789,
                "status": "cheap"
            },
        )
        self.assertTrue(UWSGICollector._pid_dead(200, ws))

    def test_counter_adds(self):
        c1 = Counter('c', 'help', registry=None)
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        c2 = Counter('c', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('c'))
        c1.inc(1)
        c2.inc(2)
        self.assertEqual(3, self.registry.get_sample_value('c'))

    def test_summary_adds(self):
        s1 = Summary('s', 'help', registry=None)
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        s2 = Summary('s', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        self.assertEqual(0, self.registry.get_sample_value('s_sum'))
        s1.observe(1)
        s2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value('s_count'))
        self.assertEqual(3, self.registry.get_sample_value('s_sum'))

    def test_histogram_adds(self):
        h1 = Histogram('h', 'help', registry=None)
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        h2 = Histogram('h', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        self.assertEqual(0, self.registry.get_sample_value('h_sum'))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        h1.observe(1)
        h2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value('h_count'))
        self.assertEqual(3, self.registry.get_sample_value('h_sum'))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))

    @patch("uwsgi.workers")
    def test_gauge_all(self, workers_):
        workers_.return_value = (
            dict(pid="123", status="idle"),
            dict(pid="456", status="idle")
        )

        g1 = Gauge('g', 'help', registry=None)
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        g2 = Gauge('g', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(0, self.registry.get_sample_value('g', {'partition': '456'}))
        g1.set(1)
        g2.set(2)

        workers_.return_value = (
            dict(pid="123", status="cheap"),
            dict(pid="456", status="busy")
        )

        self.assertEqual(1, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'partition': '456'}))

    @patch("uwsgi.workers")
    def test_gauge_liveall(self, workers_):
        workers_.return_value = (
            dict(pid="123", status="idle"),
            dict(pid="456", status="idle")
        )

        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='liveall')
        self.assertEqual(0, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(0, self.registry.get_sample_value('g', {'partition': '456'}))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'partition': '456'}))

        workers_.return_value = (
            dict(pid=123, status="cheap"),
            dict(pid=456, status="busy")
        )

        self.assertEqual(None, self.registry.get_sample_value('g', {'partition': '123'}))
        self.assertEqual(2, self.registry.get_sample_value('g', {'partition': '456'}))

    def test_gauge_min(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value('g'))

    def test_gauge_max(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(2, self.registry.get_sample_value('g'))

    @patch("uwsgi.workers")
    def test_gauge_livesum(self, workers_):
        workers_.return_value = (
            dict(pid=123, status="idle"),
            dict(pid=456, status="idle")
        )

        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='livesum')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(3, self.registry.get_sample_value('g'))

        workers_.return_value = (
            dict(pid=123, status="cheap"),
            dict(pid=456, status="busy")
        )

        self.assertEqual(2, self.registry.get_sample_value('g'))

def application(env, start_response):
    import uwsgi
    import pytest
    pytest.main("tests/test_uwsgi.py")
    start_response('200 OK', [('Content-Type','text/html')])
    return [b""]
