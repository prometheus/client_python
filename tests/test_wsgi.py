from __future__ import absolute_import, unicode_literals

import sys
import unittest
from unittest import TestCase
from wsgiref.util import setup_testing_defaults

from prometheus_client import CollectorRegistry, Counter, make_wsgi_app
from prometheus_client.exposition import _bake_output, CONTENT_TYPE_LATEST


class WSGITest(TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.captured_status = None
        self.captured_headers = None
        # Setup WSGI environment
        self.environ = {}
        setup_testing_defaults(self.environ)

    def capture(self, status, header):
        self.captured_status = status
        self.captured_headers = header

    def assertIn(self, item, iterable):
        try:
            super().assertIn(item, iterable)
        except:  # Python < 2.7
            self.assertTrue(
                item in iterable,
                msg="{item} not found in {iterable}".format(
                    item=item, iterable=iterable
                )
            )

    def validate_metrics(self, metric_name, help_text, increments):
        """
        WSGI app serves the metrics from the provided registry.
        """
        c = Counter(metric_name, help_text, registry=self.registry)
        for _ in range(increments):
            c.inc()
        # Create and run WSGI app
        app = make_wsgi_app(self.registry)
        outputs = app(self.environ, self.capture)
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
        self.assertIn(metric_name + "_total " + str(increments) + ".0\n", output)

    def test_report_metrics_1(self):
        self.validate_metrics("counter", "A counter", 2)

    def test_report_metrics_2(self):
        self.validate_metrics("counter", "Another counter", 3)

    def test_report_metrics_3(self):
        self.validate_metrics("requests", "Number of requests", 5)

    def test_report_metrics_4(self):
        self.validate_metrics("failed_requests", "Number of failed requests", 7)

    @unittest.skipIf(sys.version_info < (3, 3), "Test requires Python 3.3+.")
    def test_favicon_path(self):
        from unittest.mock import patch

        # Create mock to enable counting access of _bake_output
        with patch("prometheus_client.exposition._bake_output", side_effect=_bake_output) as mock:
            # Create and run WSGI app
            app = make_wsgi_app(self.registry)
            # Try accessing the favicon path
            favicon_environ = dict(self.environ)
            favicon_environ['PATH_INFO'] = '/favicon.ico'
            outputs = app(favicon_environ, self.capture)
            # Test empty response
            self.assertEqual(outputs, [b''])
            self.assertEqual(mock.call_count, 0)
            # Try accessing normal paths
            app(self.environ, self.capture)
            self.assertEqual(mock.call_count, 1)
