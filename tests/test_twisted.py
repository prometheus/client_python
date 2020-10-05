from __future__ import absolute_import, unicode_literals

import sys

from prometheus_client import CollectorRegistry, Counter, generate_latest

if sys.version_info < (2, 7):
    from unittest2 import skipUnless
else:
    from unittest import skipUnless

try:
    from twisted.internet import reactor
    from twisted.trial.unittest import TestCase
    from twisted.web.client import Agent, readBody
    from twisted.web.resource import Resource
    from twisted.web.server import Site

    from prometheus_client.twisted import MetricsResource

    HAVE_TWISTED = True
except ImportError:
    from unittest import TestCase

    HAVE_TWISTED = False


class MetricsResourceTest(TestCase):
    @skipUnless(HAVE_TWISTED, "Don't have twisted installed.")
    def setUp(self):
        self.registry = CollectorRegistry()

    def test_reports_metrics(self):
        """
        ``MetricsResource`` serves the metrics from the provided registry.
        """
        c = Counter('cc', 'A counter', registry=self.registry)
        c.inc()

        root = Resource()
        root.putChild(b'metrics', MetricsResource(registry=self.registry))
        server = reactor.listenTCP(0, Site(root))
        self.addCleanup(server.stopListening)

        agent = Agent(reactor)
        port = server.getHost().port
        url = "http://localhost:{port}/metrics".format(port=port)
        d = agent.request(b"GET", url.encode("ascii"))

        d.addCallback(readBody)
        d.addCallback(self.assertEqual, generate_latest(self.registry))

        return d
