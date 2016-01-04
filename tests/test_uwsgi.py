from __future__ import unicode_literals
import httplib
import os
import pytest
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest

from mock import patch

import prometheus_client
from prometheus_client.core import *
from prometheus_client.multiprocess import *

no_uwsgi = False
try:
    import uwsgi
except ImportError:
    no_uwsgi = True

class TestUWSGI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global no_uwsgi
        if no_uwsgi:
            venv_path = os.getenv("VIRTUAL_ENV")
            uwsgi_path = os.path.join(venv_path, "bin", "uwsgi")
            args = shlex.split("{uwsgi} --wsgi-file tests/test_uwsgi.py --http 127.0.0.1:9090 --cache2 name=prometheus,items=100 --virtualenv {venv} --workers 2 --threads 2".format(uwsgi=uwsgi_path, venv=venv_path))
            cls.uwsgi_instance = subprocess.Popen(args)

    @classmethod
    def tearDownClass(cls):
        global no_uwsgi
        if no_uwsgi:
            cls.uwsgi_instance.terminate()

    def setUp(self):
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(123)
        self.registry = CollectorRegistry()
        UWSGICollector(self.registry)

        try:
            import uwsgi
            uwsgi.cache_clear()
        except ImportError:
            pass

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

    @pytest.mark.skipif(no_uwsgi, reason="Not running under uWSGI")
    def test_counter_adds(self):
        c1 = Counter('c', 'help', registry=None)
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        c2 = Counter('c', 'help', registry=None)
        self.assertEqual(0, self.registry.get_sample_value('c'))
        c1.inc(1)
        c2.inc(2)
        self.assertEqual(3, self.registry.get_sample_value('c'))

    @pytest.mark.skipif(no_uwsgi, reason="Not running under uWSGI")
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

    @pytest.mark.skipif(no_uwsgi, reason="Not running under uWSGI")
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

    @pytest.mark.skipif(no_uwsgi, reason="Not running under uWSGI")
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

    @pytest.mark.skipif(no_uwsgi, reason="Not running under uWSGI")
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

    @pytest.mark.skipif(no_uwsgi, reason="Not running under uWSGI")
    def test_gauge_min(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='min')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value('g'))

    @pytest.mark.skipif(no_uwsgi, reason="Not running under uWSGI")
    def test_gauge_max(self):
        g1 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        prometheus_client.core._ValueClass = prometheus_client.core._UWSGIValue(456)
        g2 = Gauge('g', 'help', registry=None, multiprocess_mode='max')
        self.assertEqual(0, self.registry.get_sample_value('g'))
        g1.set(1)
        g2.set(2)
        self.assertEqual(2, self.registry.get_sample_value('g'))

    @pytest.mark.skipif(no_uwsgi, reason="Not running under uWSGI")
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

    @pytest.mark.skipif(not no_uwsgi, reason="Already running under uWSGI")
    def test_run_uwsgi_suite(self):
        conn = httplib.HTTPConnection("127.0.0.1:9090")
        conn.request("GET", "/")
        resp = conn.getresponse()
        conn.close()
        self.assertEqual(resp.status, 204)

def application(env, start_response):
    import pytest
    result = pytest.main("tests/test_uwsgi.py")
    if result == 0:
        start_response('204 No Content', [('Content-Type','text/plain')])
    else:
        start_response('500 Internal Server Error', [('Content-Type','text/plain')])
