import unittest
import threading
try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer

from prometheus_client import Counter, CollectorRegistry
from prometheus_client.bridge.graphite import GraphiteBridge

def fake_timer():
    return 1434898897.5

class TestGraphiteBridge(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()

        self.data = ''
        class TCPHandler(SocketServer.BaseRequestHandler):
            def handle(s):
                self.data = s.request.recv(1024)
        server = SocketServer.TCPServer(('localhost', 0), TCPHandler)
        class ServingThread(threading.Thread):
            def run(self):
                server.handle_request()
                server.socket.close()
        self.t = ServingThread()
        self.t.start()

        # Explicitly use localhost as the target host, since connecting to 0.0.0.0 fails on Windows
        address = ('localhost', server.server_address[1])
        self.gb = GraphiteBridge(address, self.registry, _timer=fake_timer)

    def test_nolabels(self):
        counter = Counter('c', 'help', registry=self.registry)
        counter.inc()

        self.gb.push()
        self.t.join()

        self.assertEqual(b'c 1.0 1434898897\n', self.data)

    def test_labels(self):
        labels = Counter('labels', 'help', ['a', 'b'], registry=self.registry)
        labels.labels('c', 'd').inc()

        self.gb.push()
        self.t.join()

        self.assertEqual(b'labels.a.c.b.d 1.0 1434898897\n', self.data)

    def test_prefix(self):
        labels = Counter('labels', 'help', ['a', 'b'], registry=self.registry)
        labels.labels('c', 'd').inc()

        self.gb.push(prefix = 'pre.fix')
        self.t.join()

        self.assertEqual(b'pre.fix.labels.a.c.b.d 1.0 1434898897\n', self.data)

    def test_sanitizing(self):
        labels = Counter('labels', 'help', ['a'], registry=self.registry)
        labels.labels('c.:8').inc()

        self.gb.push()
        self.t.join()

        self.assertEqual(b'labels.a.c__8 1.0 1434898897\n', self.data)
