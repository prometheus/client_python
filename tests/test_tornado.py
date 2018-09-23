from __future__ import absolute_import, unicode_literals

import sys

if sys.version_info < (2, 7):
    from unittest2 import skipUnless
else:
    from unittest import skipUnless

from prometheus_client import Counter
from prometheus_client import CollectorRegistry, generate_latest

try:
    from prometheus_client.tornado import MetricsHandler

    import tornado.ioloop
    import tornado.web
    import tornado.testing
    TestCase = tornado.testing.AsyncHTTPTestCase
    HAVE_TORNADO = True
except ImportError:
    from unittest import TestCase
    HAVE_TORNADO = False


class MetricsResourceTest(TestCase):
    def get_app(self):
        self.registry = CollectorRegistry()
        return tornado.web.Application([
            (r'/metrics', MetricsHandler, {'registry': self.registry}),
        ])

    @skipUnless(HAVE_TORNADO, "Don't have tornado installed.")
    def test_reports_metrics(self):
        """
        ``MetricsHandler`` serves the metrics from the provided registry.
        """
        c = Counter('cc', 'A counter', registry=self.registry)
        c.inc()

        resp = self.fetch('/metrics')

        self.assertEqual(resp.code, 200)
        self.assertEqual(resp.body, generate_latest(self.registry))
