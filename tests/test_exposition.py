from __future__ import unicode_literals

import sys
import threading
import time

if sys.version_info < (2, 7):
    # We need the skip decorators from unittest2 on Python 2.6.
    import unittest2 as unittest
else:
    import unittest

from prometheus_client import Gauge, Counter, Summary, Histogram, Info, Enum, Metric
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client import push_to_gateway, pushadd_to_gateway, delete_from_gateway
from prometheus_client import CONTENT_TYPE_LATEST, instance_ip_grouping_key
from prometheus_client.core import GaugeHistogramMetricFamily, Timestamp
from prometheus_client.exposition import default_handler, basic_auth_handler, MetricsHandler

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

        # Mock time so _created values are fixed.
        self.old_time = time.time
        time.time = lambda: 123.456

    def tearDown(self):
        time.time = self.old_time

    def custom_collector(self, metric_family):
        class CustomCollector(object):
            def collect(self):
                return [metric_family]
        self.registry.register(CustomCollector())

    def test_counter(self):
        c = Counter('cc', 'A counter', registry=self.registry)
        c.inc()
        self.assertEqual(b'''# HELP cc_total A counter
# TYPE cc_total counter
cc_total 1.0
# TYPE cc_created gauge
cc_created 123.456
''', generate_latest(self.registry))

    def test_counter_total(self):
        c = Counter('cc_total', 'A counter', registry=self.registry)
        c.inc()
        self.assertEqual(b'''# HELP cc_total A counter
# TYPE cc_total counter
cc_total 1.0
# TYPE cc_created gauge
cc_created 123.456
''', generate_latest(self.registry))

    def test_gauge(self):
        g = Gauge('gg', 'A gauge', registry=self.registry)
        g.set(17)
        self.assertEqual(b'# HELP gg A gauge\n# TYPE gg gauge\ngg 17.0\n', generate_latest(self.registry))

    def test_summary(self):
        s = Summary('ss', 'A summary', ['a', 'b'], registry=self.registry)
        s.labels('c', 'd').observe(17)
        self.assertEqual(b'''# HELP ss A summary
# TYPE ss summary
ss_count{a="c",b="d"} 1.0
ss_sum{a="c",b="d"} 17.0
# TYPE ss_created gauge
ss_created{a="c",b="d"} 123.456
''', generate_latest(self.registry))

    @unittest.skipIf(sys.version_info < (2, 7), "Test requires Python 2.7+.")
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
# TYPE hh_created gauge
hh_created 123.456
''', generate_latest(self.registry))

    def test_gaugehistogram(self):
        self.custom_collector(GaugeHistogramMetricFamily('gh', 'help', buckets=[('1.0', 4), ('+Inf', 5)], gsum_value=7))
        self.assertEqual(b'''# HELP gh help
# TYPE gh histogram
gh_bucket{le="1.0"} 4.0
gh_bucket{le="+Inf"} 5.0
# TYPE gh_gcount gauge
gh_gcount 5.0
# TYPE gh_gsum gauge
gh_gsum 7.0
''', generate_latest(self.registry))

    def test_info(self):
        i = Info('ii', 'A info', ['a', 'b'], registry=self.registry)
        i.labels('c', 'd').info({'foo': 'bar'})
        self.assertEqual(b'# HELP ii_info A info\n# TYPE ii_info gauge\nii_info{a="c",b="d",foo="bar"} 1.0\n', generate_latest(self.registry))

    def test_enum(self):
        i = Enum('ee', 'An enum', ['a', 'b'], registry=self.registry, states=['foo', 'bar'])
        i.labels('c', 'd').state('bar')
        self.assertEqual(b'# HELP ee An enum\n# TYPE ee gauge\nee{a="c",b="d",ee="foo"} 0.0\nee{a="c",b="d",ee="bar"} 1.0\n', generate_latest(self.registry))

    def test_unicode(self):
        c = Gauge('cc', '\u4500', ['l'], registry=self.registry)
        c.labels('\u4500').inc()
        self.assertEqual(b'# HELP cc \xe4\x94\x80\n# TYPE cc gauge\ncc{l="\xe4\x94\x80"} 1.0\n', generate_latest(self.registry))

    def test_escaping(self):
        g = Gauge('cc', 'A\ngaug\\e', ['a'], registry=self.registry)
        g.labels('\\x\n"').inc(1)
        self.assertEqual(b'# HELP cc A\\ngaug\\\\e\n# TYPE cc gauge\ncc{a="\\\\x\\n\\""} 1.0\n', generate_latest(self.registry))

    def test_nonnumber(self):

        class MyNumber(object):
            def __repr__(self):
                return "MyNumber(123)"

            def __float__(self):
                return 123.0

        class MyCollector(object):
            def collect(self):
                metric = Metric("nonnumber", "Non number", 'untyped')
                metric.add_sample("nonnumber", {}, MyNumber())
                yield metric

        self.registry.register(MyCollector())
        self.assertEqual(b'# HELP nonnumber Non number\n# TYPE nonnumber untyped\nnonnumber 123.0\n', generate_latest(self.registry))

    def test_timestamp(self):
        class MyCollector(object):
            def collect(self):
                metric = Metric("ts", "help", 'untyped')
                metric.add_sample("ts", {"foo": "a"}, 0, 123.456)
                metric.add_sample("ts", {"foo": "b"}, 0, -123.456)
                metric.add_sample("ts", {"foo": "c"}, 0, 123)
                metric.add_sample("ts", {"foo": "d"}, 0, Timestamp(123, 456000000))
                metric.add_sample("ts", {"foo": "e"}, 0, Timestamp(123, 456000))
                metric.add_sample("ts", {"foo": "f"}, 0, Timestamp(123, 456))
                yield metric

        self.registry.register(MyCollector())
        self.assertEqual(b'''# HELP ts help
# TYPE ts untyped
ts{foo="a"} 0.0 123456
ts{foo="b"} 0.0 -123456
ts{foo="c"} 0.0 123000
ts{foo="d"} 0.0 123456
ts{foo="e"} 0.0 123000
ts{foo="f"} 0.0 123000
''', generate_latest(self.registry))


class TestPushGateway(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.counter = Gauge('g', 'help', registry=self.registry)
        self.requests = requests = []

        class TestHandler(BaseHTTPRequestHandler):
            def do_PUT(self):
                if 'with_basic_auth' in self.requestline and self.headers['authorization'] != 'Basic Zm9vOmJhcg==':
                    self.send_response(401)
                else:
                    self.send_response(201)
                length = int(self.headers['content-length'])
                requests.append((self, self.rfile.read(length)))
                self.end_headers()

            do_POST = do_PUT
            do_DELETE = do_PUT

        httpd = HTTPServer(('localhost', 0), TestHandler)
        self.address = 'http://localhost:{0}'.format(httpd.server_address[1])

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

    def test_push_with_handler(self):
        def my_test_handler(url, method, timeout, headers, data):
            headers.append(['X-Test-Header', 'foobar'])
            # Handler should be passed sane default timeout
            self.assertEqual(timeout, 30)
            return default_handler(url, method, timeout, headers, data)
        push_to_gateway(self.address, "my_job", self.registry, handler=my_test_handler)
        self.assertEqual(self.requests[0][0].command, 'PUT')
        self.assertEqual(self.requests[0][0].path, '/metrics/job/my_job')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][0].headers.get('x-test-header'), 'foobar')
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_push_with_basic_auth_handler(self):
        def my_auth_handler(url, method, timeout, headers, data):
            return basic_auth_handler(url, method, timeout, headers, data, "foo", "bar")
        push_to_gateway(self.address, "my_job_with_basic_auth", self.registry, handler=my_auth_handler)
        self.assertEqual(self.requests[0][0].command, 'PUT')
        self.assertEqual(self.requests[0][0].path, '/metrics/job/my_job_with_basic_auth')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    @unittest.skipIf(
        sys.platform == "darwin",
        "instance_ip_grouping_key() does not work on macOS."
    )
    def test_instance_ip_grouping_key(self):
        self.assertTrue('' != instance_ip_grouping_key()['instance'])

    def test_metrics_handler(self):
        handler = MetricsHandler.factory(self.registry)
        self.assertEqual(handler.registry, self.registry)


if __name__ == '__main__':
    unittest.main()
