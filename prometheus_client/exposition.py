#!/usr/bin/python

from __future__ import unicode_literals

import os
import socket
import time
import threading
from contextlib import closing
from wsgiref.simple_server import make_server

from . import core
try:
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
    from urllib2 import build_opener, Request, HTTPHandler
    from urllib import quote_plus
except ImportError:
    # Python 3
    unicode = str
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer
    from urllib.request import build_opener, Request, HTTPHandler
    from urllib.parse import quote_plus


CONTENT_TYPE_LATEST = str('text/plain; version=0.0.4; charset=utf-8')
'''Content type of the latest text format'''


def make_wsgi_app(registry=core.REGISTRY):
    '''Create a WSGI app which serves the metrics from a registry.'''
    def prometheus_app(environ, start_response):
        status = str('200 OK')
        headers = [(str('Content-type'), CONTENT_TYPE_LATEST)]
        start_response(status, headers)
        return [generate_latest(registry)]
    return prometheus_app


def start_wsgi_server(port, addr='', registry=core.REGISTRY):
    """Starts a WSGI server for prometheus metrics as a daemon thread."""
    class PrometheusMetricsServer(threading.Thread):
        def run(self):
            httpd = make_server(addr, port, make_wsgi_app(registry))
            httpd.serve_forever()
    t = PrometheusMetricsServer()
    t.daemon = True
    t.start()


def generate_latest(registry=core.REGISTRY):
    '''Returns the metrics from the registry in latest text format as a string.'''
    output = []
    for metric in registry.collect():
        output.append('# HELP {0} {1}'.format(
            metric.name, metric.documentation.replace('\\', r'\\').replace('\n', r'\n')))
        output.append('\n# TYPE {0} {1}\n'.format(metric.name, metric.type))
        for name, labels, value in metric.samples:
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


def push_to_gateway(gateway, job, registry, grouping_key=None, timeout=None):
    '''Push metrics to the given pushgateway.

    `gateway` the url for your push gateway. Either of the form
              'http://pushgateway.local', or 'pushgateway.local'.
              Scheme defaults to 'http' if none is provided
    `job` is the job label to be attached to all pushed metrics
    `registry` is an instance of CollectorRegistry
    `grouping_key` please see the pushgateway documentation for details.
                   Defaults to None
    `timeout` is how long push will attempt to connect before giving up.
              Defaults to None

    This overwrites all metrics with the same job and grouping_key.
    This uses the PUT HTTP method.'''
    _use_gateway('PUT', gateway, job, registry, grouping_key, timeout)


def pushadd_to_gateway(gateway, job, registry, grouping_key=None, timeout=None):
    '''PushAdd metrics to the given pushgateway.

    `gateway` the url for your push gateway. Either of the form
              'http://pushgateway.local', or 'pushgateway.local'.
              Scheme defaults to 'http' if none is provided
    `job` is the job label to be attached to all pushed metrics
    `registry` is an instance of CollectorRegistry
    `grouping_key` please see the pushgateway documentation for details.
                   Defaults to None
    `timeout` is how long push will attempt to connect before giving up.
              Defaults to None

    This replaces metrics with the same name, job and grouping_key.
    This uses the POST HTTP method.'''
    _use_gateway('POST', gateway, job, registry, grouping_key, timeout)


def delete_from_gateway(gateway, job, grouping_key=None, timeout=None):
    '''Delete metrics from the given pushgateway.

    `gateway` the url for your push gateway. Either of the form
              'http://pushgateway.local', or 'pushgateway.local'.
              Scheme defaults to 'http' if none is provided
    `job` is the job label to be attached to all pushed metrics
    `grouping_key` please see the pushgateway documentation for details.
                   Defaults to None
    `timeout` is how long delete will attempt to connect before giving up.
              Defaults to None

    This deletes metrics with the given job and grouping_key.
    This uses the DELETE HTTP method.'''
    _use_gateway('DELETE', gateway, job, None, grouping_key, timeout)


def _use_gateway(method, gateway, job, registry, grouping_key, timeout):
    if not (gateway.startswith('http://') or gateway.startswith('https://')):
        gateway = 'http://{0}'.format(gateway)
    url = '{0}/metrics/job/{1}'.format(gateway, quote_plus(job))

    data = b''
    if method != 'DELETE':
        data = generate_latest(registry)

    if grouping_key is None:
        grouping_key = {}
    url = url + ''.join(['/{0}/{1}'.format(quote_plus(str(k)), quote_plus(str(v)))
                             for k, v in sorted(grouping_key.items())])

    request = Request(url, data=data)
    request.add_header('Content-Type', CONTENT_TYPE_LATEST)
    request.get_method = lambda: method
    resp = build_opener(HTTPHandler).open(request, timeout=timeout)
    if resp.code >= 400:
        raise IOError("error talking to pushgateway: {0} {1}".format(
            resp.code, resp.msg))

def instance_ip_grouping_key():
    '''Grouping key with instance set to the IP Address of this host.'''
    with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
        s.connect(('localhost', 0))
        return {'instance': s.getsockname()[0]}
