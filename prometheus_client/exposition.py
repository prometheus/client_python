#!/usr/bin/python

from __future__ import unicode_literals

import os
import time
import threading

from . import core
try:
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
except ImportError:
    # Python 3
    unicode = str
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer


CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4; charset=utf-8'
'''Content type of the latest text format'''


def generate_latest(registry=core.REGISTRY):
    '''Returns the metrics from the registry in latest text format as a string.'''
    output = []
    for metric in registry.collect():
        output.append('# HELP {0} {1}'.format(
            metric._name, metric._documentation.replace('\\', r'\\').replace('\n', r'\n')))
        output.append('\n# TYPE {0} {1}\n'.format(metric._name, metric._type))
        for name, labels, value in metric._samples:
            if labels:
                labelstr = '{{{0}}}'.format(','.join(
                    ['{0}="{1}"'.format(
                     k, v.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"'))
                     for k, v in sorted(labels.items())]))
            else:
                labelstr = ''
            output.append('{0}{1} {2}\n'.format(name, labelstr, core._floatToGoString(value)))
    return ''.join(output).encode('utf-8')


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(generate_latest(core.REGISTRY))

    def log_message(self, format, *args):
        return


def start_http_server(port, addr=''):
    """Starts a HTTP server for prometheus metrics as a daemon thread."""
    class PrometheusMetricsServer(threading.Thread):
        def run(self):
            httpd = HTTPServer((addr, port), MetricsHandler)
            httpd.serve_forever()
    t = PrometheusMetricsServer()
    t.daemon = True
    t.start()


def write_to_textfile(path, registry):
    '''Write metrics to the given path.

    This is intended for use with the Node exporter textfile collector.
    The path must end in .prom for the textfile collector to process it.'''
    tmppath = '%s.%s.%s' % (path, os.getpid(), threading.current_thread().ident)
    with open(tmppath, 'wb') as f:
        f.write(generate_latest(registry))
    # rename(2) is atomic.
    os.rename(tmppath, path)
