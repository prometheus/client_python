# Prometheus Python Client

The official Python 2 and 3 client for [Prometheus](http://prometheus.io).

## Three Step Demo

**One**: Install the client:
```
pip install prometheus_client
```

**Two**: Paste the following into a Python interpreter:
```python
from prometheus_client import start_http_server,Summary
import random
import time

# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')

# Decorate function with metric.
@REQUEST_TIME.time()
def process_request(t):
    """A dummy function that takes some time."""
    time.sleep(t)

if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(8000)
    # Generate some requests.
    while True:
        process_request(random.random())
```

**Three**: Visit [http://localhost:8000/](http://localhost:8000/) to view the metrics.

From one easy to use decorator you get:
  * `request_processing_seconds_count`: Number of times this function was called.
  * `request_processing_seconds_sum`: Total amount of time spent in this function.

Prometheus's `rate` function allows calculation of both requests per second,
and latency over time from this data.

In addition if you're on Linux the `process` metrics expose CPU, memory and
other information about the process for free!

## Installation

```
pip install prometheus_client
```

This package can be found on
[PyPI](https://pypi.python.org/pypi/prometheus_client).

## Instrumenting

Four types of metric are offered: Counter, Gauge, Summary and Histogram.
See the documentation on [metric types](http://prometheus.io/docs/concepts/metric_types/)
and [instrumentation best practices](http://prometheus.io/docs/practices/instrumentation/#counter-vs.-gauge,-summary-vs.-histogram)
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
@c.count_exceptions()
def f():
  pass

with c.count_exceptions():
  pass

# Count only one type of exception
with c.count_exceptions(ValueError):
  pass
```

### Gauge

Gauges can go up and down.

```python
from prometheus_client import Gauge
g = Gauge('my_inprogress_requests', 'Description of gauge')
g.inc()      # Increment by 1
g.dec(10)    # Decrement by given value
g.set(4.2)   # Set to a given value
```

There are utilities for common use cases:

```python
g.set_to_current_time()   # Set to current unixtime

# Increment when entered, decrement when exited.
@g.track_inprogress()
def f():
  pass

with g.track_inprogress():
  pass
```

A Gauge can also take it's value from a callback:

```python
d = Gauge('data_objects', 'Number of objects')
my_dict = {}
d.set_function(lambda: len(my_dict))
```

### Summary

Summaries track the size and number of events.

```python
from prometheus_client import Summary
s = Summary('request_size_bytes', 'Description of summary')
s.observe(512)    # Observe 512 (bytes in this case)
```

There are utilities for timing code:

```python
@s.time()
def f():
  pass

with s.time():
  pass
```

The Python client doesn't store or expose quantile information at this time.

### Histogram

Histograms track the size and number of events in buckets.
This allows for aggregatable calculation of quantiles.

```python
from prometheus_client import Histogram
h = Histogram('request_size_bytes', 'Description of histogram')
h.observe(512)    # Observe 512 (bytes in this case)
```

The default buckets are intended to cover a typical web/rpc request from milliseconds to seconds.
They can be overridden by passing `buckets` keyword argument to `Histogram`.

There are utilities for timing code:

```python
@h.time()
def f():
  pass

with h.time():
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

Labels can also be provided as a dict:

```python
from prometheus_client import Counter
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels({'method': 'get', 'endpoint': '/'}).inc()
c.labels({'method': 'post', 'endpoint': '/submit'}).inc()
```

### Process Collector

The Python client automatically exports metrics about process CPU usage, RAM,
file descriptors and start time. These all have the prefix `process`, and
are only currently available on Linux.

The namespace and pid constructor arguments allows for exporting metrics about
other processes, for example:
```
ProcessCollector(namespace='mydaemon', pid=lambda: open('/var/run/daemon.pid').read())
```

## Exporting

There are several options for exporting metrics.

### HTTP

Metrics are usually exposed over HTTP, to be read by the Prometheus server.

The easiest way to do this is via `start_http_server`, which will start a HTTP
server in a daemon thread on the given port:

```python
from prometheus_client import start_http_server
start_http_server(8000)
```

Visit [http://localhost:8000/](http://localhost:8000/) to view the metrics.

To add Prometheus exposition to an existing HTTP server, see the `MetricsServlet` class
which provides a `BaseHTTPRequestHandler`. It also serves as a simple example of how
to write a custom endpoint.

### Node exporter textfile collector

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

A separate registry is used, as the default registry may contain other metrics
such as those from the Process Collector.

## Exporting to a Pushgateway

The [Pushgateway](https://github.com/prometheus/pushgateway)
allows ephemeral and batch jobs to expose their metrics to Prometheus.

```python
from prometheus_client import CollectorRegistry,Gauge,push_to_gateway
registry = CollectorRegistry()
g = Gauge('job_last_success_unixtime', 'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
push_to_gateway('localhost:9091', job='batchA', registry=registry)
```

A separate registry is used, as the default registry may contain other metrics
such as those from the Process Collector.

Pushgateway functions take a grouping key. `push_to_gateway` replaces metrics
with the same grouping key, `pushadd_to_gateway` only replaces metrics with the
same name and grouping key and `delete_from_gateway` deletes metrics with the
given job and grouping key. See the
[Pushgateway documentation](https://github.com/prometheus/pushgateway/blob/master/README.md)
for more information.

`instance_ip_grouping_key` returns a grouping key with the instance label set
to the host's IP address.


## Bridges

It is also possible to expose metrics to systems other than Prometheus.
This allows you to take advantage of Prometheus instrumentation even
if you are not quite ready to fully transition to Prometheus yet.

### Graphite

Metrics are pushed over TCP in the Graphite plaintext format.

```python
from prometheus_client.bridge.graphite import GraphiteBridge
gb = GraphiteBridge(('graphite.your.org', 2003))
# Push once.
gb.push()
# Push every 10 seconds in a daemon thread.
gb.start(10.0)
```
