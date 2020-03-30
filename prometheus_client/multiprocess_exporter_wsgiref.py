import argparse
from wsgiref.simple_server import make_server, WSGIServer

from prometheus_client import multiprocess
from prometheus_client.exposition import make_wsgi_app
from prometheus_client.multiprocess_exporter import start_archiver_thread
from prometheus_client.registry import CollectorRegistry
"""
An entrypoint for the a multiprocess exporter using Python's built-in wsgiref implementation
The reference wsgi implementation is not pre-fork, making it more suited for the InMemoryCollector than Gunicorn
"""

CLEANUP_INTERVAL = 5.0

registry = CollectorRegistry()
multiprocess.InMemoryCollector(registry)
app = make_wsgi_app(registry)

parser = argparse.ArgumentParser(description="Starts a multiprocess prometheus exporter, running on wsgiref")
parser.add_argument("--port", type=int, required=True)
args = parser.parse_args()
port = args.port


class ExporterHttpServer(WSGIServer):
    """
    An equivalent of the on_starting hook if running the multiprocess exporter without Gunicorn
    """
    def server_activate(self):
        # WSGIServer is still an old-style class in python 2.7, preventing use of super()
        WSGIServer.server_activate(self)
        start_archiver_thread()


httpd = make_server('', port, app, server_class=ExporterHttpServer)
httpd.serve_forever()
