# Prometheus Python Client

This client is under active development.

## Installation

```
pip install prometheus_client
```

This package can be found on [PyPI](https://pypi.python.org/pypi/prometheus_client).

## Instrumenting

Three types of metric are offered: Counter, Gauge, and Summary.
See the documentation on [metric types](http://prometheus.io/docs/concepts/metric_types/)
and [instrumentation best practices](http://prometheus.io/docs/practices/instrumentation/#counter-vs.-gauge-vs.-summary)
on how to use them.

### Counter

Counters go up, and reset when the process restarts.


```python
from prometheus_client import Counter
c = Counter('my_failures_total', 'Description of counter')
c.inc()     # Increment by 1
c.inc(1.6)  # Increment by given value
```

There are utilities to count exceptions raised:

```python
@c.countExceptions()
def f():
  pass

with c.countExceptions():
  pass

# Count only one type of exception
with c.countExceptions(ValueError):
  pass
```

### Gauge

Gauges can go up and down.


```python
from prometheus_client import Gauge
g = Gauge('my_inprogress_requests', 'Description of gauge')
g.inc()      # Increment by 1
g.dev(10)    # Decrement by given value
g.set(4.2)   # Set to a given value
```

There are utilities for common use cases:

```python
g.setToCurrentTime()   # Set to current unixtime

# Increment when entered, decrement when exited.
@g.trackInprogress()
def f():
  pass

with g.trackInprogress():
  pass
```

### Summary

Summaries track the size and number of events.

```python
from prometheus_client import Summary
s = Summary('request_latency_seconds', 'Description of summary')
s.observe(4.7)    # Observe 4.7 (seconds in this case)
```

There are utilities for timing code:

```python
@s.time()
def f():
  pass

with s.time():
  pass
```

### Labels

All metrics can have labels, allowing grouping of related time series.

See the best practices on [naming](http://prometheus.io/docs/practices/naming/)
and [labels](http://prometheus.io/docs/practices/instrumentation/#use-labels).

Taking a counter as an example:

```python
from prometheus_client import Counter
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels('get', '/').inc()
c.labels('post', '/submit').inc()
```

## Exporting

There are several options for exporting metrics.

## HTTP handler

Metrics are usuall exposed over HTTP, to be read by the Prometheus server. For example:

```python
from prometheus_client import MetricsHandler
from BaseHTTPServer import HTTPServer
server_address = ('', 8000)
httpd = HTTPServer(server_address, MetricsHandler)
httpd.serve_forever()
```

Visit [http://localhost:8000/](http://localhost:8000/) to view the metrics.

## Node exporter textfile collector

The [textfile collector](https://github.com/prometheus/node_exporter#textfile-collector)
allows machine-level statistics to be exported out via the Node exporter.

This is useful for monitoring cronjobs, or for writing cronjobs to expose metrics
about a machine system that the Node exporter does not support or would not make sense
to perform at every scrape (for example, anything involving subprocesses).

```python
from prometheus_client import CollectorRegistry,Gauge,write_to_textfile
registry = CollectorRegistry()
g = Gauge('raid_status', '1 if raid array is okay', registry=registry)
g.set(1)
write_to_textfile('/configured/textfile/path/raid.prom', registry)
```

A separate registry is used, as the default registry may contain other metrics.
