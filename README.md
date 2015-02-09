# Prometheus Python Client

This is a first pass at a Python client for Prometheus.

## Installation

```
pip install prometheus_client
```

## Example Usage

```python
from prometheus_client import *
from prometheus_client import MetricsHandler

c = Counter('cc', 'A counter')
c.inc()

g = Gauge('gg', 'A gauge')
g.set(17)

s = Summary('ss', 'A summary', ['a', 'b'])
s.labels('c', 'd').observe(17)

from BaseHTTPServer import HTTPServer
server_address = ('', 8000)
httpd = HTTPServer(server_address, MetricsHandler)
httpd.serve_forever()
```

Visit http://localhost:8000/ to view the metrics.
