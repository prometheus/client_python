from unittest import skipUnless

from prometheus_client import CollectorRegistry, Counter, generate_latest

try:
    from twisted.internet import defer, protocol, reactor
    from twisted.trial.unittest import TestCase
    from twisted.web.client import Agent
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

    @staticmethod
    def _read_response_body(response):
        class BodyReaderProtocol(protocol.Protocol):
            def __init__(self, finished):
                self.finished = finished
                self.data = b""

            def dataReceived(self, data):
                self.data += data

            def connectionLost(self, reason):
                self.finished.callback(self.data)

        finished = defer.Deferred()
        response.deliverBody(BodyReaderProtocol(finished))
        return finished

    if HAVE_TWISTED:
        @defer.inlineCallbacks
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
            url = f"http://localhost:{port}/metrics"
            response = yield agent.request(b"GET", url.encode("ascii"))
            body = yield self._read_response_body(response)

            self.assertEqual(body, generate_latest(self.registry))
    else:
        def test_reports_metrics(self):
            pass
