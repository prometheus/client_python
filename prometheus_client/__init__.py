#!/usr/bin/python

from . import (
    exposition, gc_collector, metrics, metrics_core, platform_collector,
    process_collector, registry,
)

__all__ = ['Counter', 'Gauge', 'Summary', 'Histogram', 'Info', 'Enum']

from .registry import CollectorRegistry
from .registry import REGISTRY
from .metrics_core import Metric
from .metrics import Counter
from .metrics import Gauge
from .metrics import Summary
from .metrics import Histogram
from .metrics import Info
from .metrics import Enum

from .exposition import CONTENT_TYPE_LATEST
from .exposition import generate_latest
from .exposition import MetricsHandler
from .exposition import make_wsgi_app
from .exposition import make_asgi_app
from .exposition import start_http_server
from .exposition import start_wsgi_server
from .exposition import write_to_textfile
from .exposition import push_to_gateway
from .exposition import pushadd_to_gateway
from .exposition import delete_from_gateway
from .exposition import instance_ip_grouping_key

from .process_collector import ProcessCollector
from .process_collector import PROCESS_COLLECTOR

from .platform_collector import PlatformCollector
from .platform_collector import PLATFORM_COLLECTOR

from .gc_collector import GCCollector
from .gc_collector import GC_COLLECTOR

if __name__ == '__main__':
    c = Counter('cc', 'A counter')
    c.inc()

    g = Gauge('gg', 'A gauge')
    g.set(17)

    s = Summary('ss', 'A summary', ['a', 'b'])
    s.labels('c', 'd').observe(17)

    h = Histogram('hh', 'A histogram')
    h.observe(.6)

    start_http_server(8000)
    import time

    while True:
        time.sleep(1)
