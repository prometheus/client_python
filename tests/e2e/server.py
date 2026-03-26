import os
import sys

# Use LockedMmapedValue for this server
os.environ['PROMETHEUS_VALUE_CLASS'] = 'prometheus_client.values.LockedMmapedValue'

import http.server
import json
from urllib.parse import urlparse, parse_qs
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest, values
from prometheus_client.multiprocess import MultiProcessAggregateCollector

# Define metrics at module level
C = Counter('c', 'test counter', ['l'])
G_SUM = Gauge('g_sum', 'test gauge sum', ['l'], multiprocess_mode='sum')
G_MAX = Gauge('g_max', 'test gauge max', ['l'], multiprocess_mode='max')
G_MIN = Gauge('g_min', 'test gauge min', ['l'], multiprocess_mode='min')
G_MOSTRECENT = Gauge('g_mostrecent', 'test gauge mostrecent', ['l'], multiprocess_mode='mostrecent')
G_ALL = Gauge('g_all', 'test gauge all', ['l'], multiprocess_mode='all')
G_LIVESUM = Gauge('g_livesum', 'test gauge livesum', ['l'], multiprocess_mode='livesum')
G_LIVEMAX = Gauge('g_livemax', 'test gauge livemax', ['l'], multiprocess_mode='livemax')
G_LIVEMIN = Gauge('g_livemin', 'test gauge livemin', ['l'], multiprocess_mode='livemin')
G_LIVEMOSTRECENT = Gauge('g_livemostrecent', 'test gauge livemostrecent', ['l'], multiprocess_mode='livemostrecent')
G_LIVEALL = Gauge('g_liveall', 'test gauge liveall', ['l'], multiprocess_mode='liveall')
H = Histogram('h', 'test histogram', ['l'], buckets=(1.0, 5.0, 10.0))

METRICS = {
    'c': C,
    'g_sum': G_SUM,
    'g_max': G_MAX,
    'g_min': G_MIN,
    'g_mostrecent': G_MOSTRECENT,
    'g_all': G_ALL,
    'g_livesum': G_LIVESUM,
    'g_livemax': G_LIVEMAX,
    'g_livemin': G_LIVEMIN,
    'g_livemostrecent': G_LIVEMOSTRECENT,
    'g_liveall': G_LIVEALL,
    'h': H,
}

class MetricHandler(http.server.BaseHTTPRequestHandler):
    def send_ok(self, data=b'OK', content_type='text/plain'):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.wfile.write(data)

    def send_error(self, code=404):
        self.send_response(code)
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        query = parse_qs(parsed_url.query)
        path = parsed_url.path

        if path == '/metrics':
            registry = CollectorRegistry()
            MultiProcessAggregateCollector(registry)
            self.send_ok(generate_latest(registry))
        elif path in ('/inc', '/set', '/observe'):
            name = query.get('name', [None])[0]
            labels_json = query.get('labels', ['{}'])[0]
            labels = json.loads(labels_json)
            value = float(query.get('value', query.get('amount', [1]))[0])

            if name not in METRICS:
                self.send_error(400)
                return

            m = METRICS[name]
            metric_with_labels = m.labels(**labels) if labels else m
            
            if path == '/inc':
                metric_with_labels.inc(value)
            elif path == '/set':
                metric_with_labels.set(value)
            elif path == '/observe':
                metric_with_labels.observe(value)
                
            self.send_ok()
        else:
            self.send_error()

if __name__ == '__main__':
    port = int(sys.argv[1])
    server = http.server.HTTPServer(('127.0.0.1', port), MetricHandler)
    print(f'Starting server on port {port}')
    server.serve_forever()
