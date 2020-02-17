from __future__ import absolute_import, unicode_literals

import sys

from prometheus_client import CollectorRegistry, Counter, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

if sys.version_info < (2, 7):
    from unittest2 import skipUnless
else:
    from unittest import skipUnless

from prometheus_client import make_wsgi_app
from unittest import TestCase
from wsgiref.util import setup_testing_defaults
from parameterized import parameterized


class WSGITest(TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.captured_status = None
        self.captured_headers = None

    def capture(self, status, header):
        self.captured_status = status
        self.captured_headers = header

    @parameterized.expand([
        ["counter", "A counter"],
        ["counter", "Another counter"],
        ["requests", "Number of requests"],
        ["failed_requests", "Number of failed requests"],
    ])
    def test_reports_metrics(self, metric_name, help_text):
        """
        WSGI app serves the metrics from the provided registry.
        """
        c = Counter(metric_name, help_text, registry=self.registry)
        c.inc()
        # Setup WSGI environment
        environ = {}
        setup_testing_defaults(environ)
        # Create and run WSGI app
        app = make_wsgi_app(self.registry)
        outputs = app(environ, self.capture)
        # Assert outputs
        self.assertEqual(len(outputs), 1)
        output = outputs[0].decode('utf8')
        # Status code
        self.assertEqual(self.captured_status, "200 OK")
        # Headers
        self.assertEqual(len(self.captured_headers), 1)
        self.assertEqual(self.captured_headers[0], ("Content-Type", CONTENT_TYPE_LATEST))
        # Body
        self.assertIn("# HELP " + metric_name + "_total " + help_text + "\n", output)
        self.assertIn("# TYPE " + metric_name + "_total counter\n", output)
        self.assertIn(metric_name + "_total 1.0\n", output)
