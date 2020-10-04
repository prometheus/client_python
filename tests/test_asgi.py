from __future__ import absolute_import, unicode_literals

import sys
from unittest import TestCase

from prometheus_client import CollectorRegistry, Counter
from prometheus_client.exposition import CONTENT_TYPE_LATEST

if sys.version_info < (2, 7):
    from unittest2 import skipUnless
else:
    from unittest import skipUnless

try:
    # Python >3.5 only
    import asyncio

    from asgiref.testing import ApplicationCommunicator

    from prometheus_client import make_asgi_app
    HAVE_ASYNCIO_AND_ASGI = True
except ImportError:
    HAVE_ASYNCIO_AND_ASGI = False


def setup_testing_defaults(scope):
    scope.update(
        {
            "client": ("127.0.0.1", 32767),
            "headers": [],
            "http_version": "1.0",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "scheme": "http",
            "server": ("127.0.0.1", 80),
            "type": "http",
        }
    )


class ASGITest(TestCase):
    @skipUnless(HAVE_ASYNCIO_AND_ASGI, "Don't have asyncio/asgi installed.")
    def setUp(self):
        self.registry = CollectorRegistry()
        self.captured_status = None
        self.captured_headers = None
        # Setup ASGI scope
        self.scope = {}
        setup_testing_defaults(self.scope)
        self.communicator = None

    def tearDown(self):
        if self.communicator:
            asyncio.get_event_loop().run_until_complete(
                self.communicator.wait()
            )
            
    def seed_app(self, app):
        self.communicator = ApplicationCommunicator(app, self.scope)

    def send_input(self, payload):
        asyncio.get_event_loop().run_until_complete(
            self.communicator.send_input(payload)
        )

    def send_default_request(self):
        self.send_input({"type": "http.request", "body": b""})

    def get_output(self):
        output = asyncio.get_event_loop().run_until_complete(
            self.communicator.receive_output(0)
        )
        return output

    def get_all_output(self):
        outputs = []
        while True:
            try:
                outputs.append(self.get_output())
            except asyncio.TimeoutError:
                break
        return outputs

    def validate_metrics(self, metric_name, help_text, increments):
        """
        ASGI app serves the metrics from the provided registry.
        """
        c = Counter(metric_name, help_text, registry=self.registry)
        for _ in range(increments):
            c.inc()
        # Create and run ASGI app
        app = make_asgi_app(self.registry)
        self.seed_app(app)
        self.send_default_request()
        # Assert outputs
        outputs = self.get_all_output()
        # Assert outputs
        self.assertEqual(len(outputs), 2)
        response_start = outputs[0]
        self.assertEqual(response_start['type'], 'http.response.start')
        response_body = outputs[1]
        self.assertEqual(response_body['type'], 'http.response.body')
        # Status code
        self.assertEqual(response_start['status'], 200)
        # Headers
        self.assertEqual(len(response_start['headers']), 1)
        self.assertEqual(response_start['headers'][0], (b"Content-Type", CONTENT_TYPE_LATEST.encode('utf8')))
        # Body
        output = response_body['body'].decode('utf8')
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
