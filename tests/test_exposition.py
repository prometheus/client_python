from __future__ import unicode_literals
import os
import sys
import threading
import time
import unittest


from prometheus_client import Gauge, Counter, Summary, Histogram, Metric
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client import push_to_gateway, pushadd_to_gateway, delete_from_gateway
from prometheus_client import CONTENT_TYPE_LATEST, instance_ip_grouping_key

try:
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
except ImportError:
    # Python 3
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer


class TestGenerateText(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()

    def test_counter(self):
        c = Counter('cc', 'A counter', registry=self.registry)
        c.inc()
        self.assertEqual(b'# HELP cc A counter\n# TYPE cc counter\ncc 1.0\n', generate_latest(self.registry))

    def test_gauge(self):
        g = Gauge('gg', 'A gauge', registry=self.registry)
        g.set(17)
        self.assertEqual(b'# HELP gg A gauge\n# TYPE gg gauge\ngg 17.0\n', generate_latest(self.registry))

    def test_summary(self):
        s = Summary('ss', 'A summary', ['a', 'b'], registry=self.registry)
        s.labels('c', 'd').observe(17)
        self.assertEqual(b'# HELP ss A summary\n# TYPE ss summary\nss_count{a="c",b="d"} 1.0\nss_sum{a="c",b="d"} 17.0\n', generate_latest(self.registry))

    def test_histogram(self):
        s = Histogram('hh', 'A histogram', registry=self.registry)
        s.observe(0.05)
        self.assertEqual(b'''# HELP hh A histogram
# TYPE hh histogram
hh_bucket{le="0.005"} 0.0
hh_bucket{le="0.01"} 0.0
hh_bucket{le="0.025"} 0.0
hh_bucket{le="0.05"} 1.0
hh_bucket{le="0.075"} 1.0
hh_bucket{le="0.1"} 1.0
hh_bucket{le="0.25"} 1.0
hh_bucket{le="0.5"} 1.0
hh_bucket{le="0.75"} 1.0
hh_bucket{le="1.0"} 1.0
hh_bucket{le="2.5"} 1.0
hh_bucket{le="5.0"} 1.0
hh_bucket{le="7.5"} 1.0
hh_bucket{le="10.0"} 1.0
hh_bucket{le="+Inf"} 1.0
hh_count 1.0
hh_sum 0.05
''', generate_latest(self.registry))

    def test_unicode(self):
        c = Counter('cc', '\u4500', ['l'], registry=self.registry)
        c.labels('\u4500').inc()
        self.assertEqual(b'# HELP cc \xe4\x94\x80\n# TYPE cc counter\ncc{l="\xe4\x94\x80"} 1.0\n', generate_latest(self.registry))

    def test_escaping(self):
        c = Counter('cc', 'A\ncount\\er', ['a'], registry=self.registry)
        c.labels('\\x\n"').inc(1)
        self.assertEqual(b'# HELP cc A\\ncount\\\\er\n# TYPE cc counter\ncc{a="\\\\x\\n\\""} 1.0\n', generate_latest(self.registry))

    def test_nonnumber(self):
        class MyNumber():
            def __repr__(self):
              return "MyNumber(123)"
            def __float__(self):
              return 123.0
        class MyCollector():
            def collect(self):
                metric = Metric("nonnumber", "Non number", 'untyped')
                metric.add_sample("nonnumber", {}, MyNumber())
                yield metric
        self.registry.register(MyCollector())
        self.assertEqual(b'# HELP nonnumber Non number\n# TYPE nonnumber untyped\nnonnumber 123.0\n', generate_latest(self.registry))


class TestPushGateway(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.counter = Gauge('g', 'help', registry=self.registry)
        self.requests = requests = []
        class TestHandler(BaseHTTPRequestHandler):
            def do_PUT(self):
                self.send_response(201)
                length = int(self.headers['content-length'])
                requests.append((self, self.rfile.read(length)))
                self.end_headers()

            do_POST = do_PUT
            do_DELETE = do_PUT

        httpd = HTTPServer(('localhost', 0), TestHandler)
        self.address = ':'.join([str(x) for x in httpd.server_address])
        class TestServer(threading.Thread):
            def run(self):
                httpd.handle_request()
        self.server = TestServer()
        self.server.daemon = True
        self.server.start()

    def test_push(self):
        push_to_gateway(self.address, "my_job", self.registry)
        self.assertEqual(self.requests[0][0].command, 'PUT')
        self.assertEqual(self.requests[0][0].path, '/metrics/job/my_job')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_push_with_groupingkey(self):
        push_to_gateway(self.address, "my_job", self.registry, {'a': 9})
        self.assertEqual(self.requests[0][0].command, 'PUT')
        self.assertEqual(self.requests[0][0].path, '/metrics/job/my_job/a/9')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_push_with_complex_groupingkey(self):
        push_to_gateway(self.address, "my_job", self.registry, {'a': 9, 'b': 'a/ z'})
        self.assertEqual(self.requests[0][0].command, 'PUT')
        self.assertEqual(self.requests[0][0].path, '/metrics/job/my_job/a/9/b/a%2F+z')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_pushadd(self):
        pushadd_to_gateway(self.address, "my_job", self.registry)
        self.assertEqual(self.requests[0][0].command, 'POST')
        self.assertEqual(self.requests[0][0].path, '/metrics/job/my_job')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_pushadd_with_groupingkey(self):
        pushadd_to_gateway(self.address, "my_job", self.registry, {'a': 9})
        self.assertEqual(self.requests[0][0].command, 'POST')
        self.assertEqual(self.requests[0][0].path, '/metrics/job/my_job/a/9')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_delete(self):
        delete_from_gateway(self.address, "my_job")
        self.assertEqual(self.requests[0][0].command, 'DELETE')
        self.assertEqual(self.requests[0][0].path, '/metrics/job/my_job')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'')

    def test_delete_with_groupingkey(self):
        delete_from_gateway(self.address, "my_job", {'a': 9})
        self.assertEqual(self.requests[0][0].command, 'DELETE')
        self.assertEqual(self.requests[0][0].path, '/metrics/job/my_job/a/9')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'')

    @unittest.skipIf(
        sys.platform == "darwin",
        "instance_ip_grouping_key() does not work on macOS."
    )
    def test_instance_ip_grouping_key(self):
        self.assertTrue('' != instance_ip_grouping_key()['instance'])


if __name__ == '__main__':
    unittest.main()
