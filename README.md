# Prometheus Python Client

This is a first pass at a Python client for Prometheus.

## Installation

```
easy_install prometheus_client
```

## Example Usage

```python
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
