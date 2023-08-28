# Prometheus Python Client

The official Python client for [Prometheus](https://prometheus.io).

## Three Step Demo

**One**: Install the client:
```
pip install prometheus-client
```

**Two**: Paste the following into a Python interpreter:
```python
from prometheus_client import start_http_server, Summary
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
pip install prometheus-client
```

This package can be found on
[PyPI](https://pypi.python.org/pypi/prometheus_client).

## Instrumenting

Four types of metric are offered: Counter, Gauge, Summary and Histogram.
See the documentation on [metric types](http://prometheus.io/docs/concepts/metric_types/)
and [instrumentation best practices](https://prometheus.io/docs/practices/instrumentation/#counter-vs-gauge-summary-vs-histogram)
on how to use them.

### Counter

Counters go up, and reset when the process restarts.


```python
from prometheus_client import Counter
c = Counter('my_failures', 'Description of counter')
c.inc()     # Increment by 1
c.inc(1.6)  # Increment by given value
```

If there is a suffix of `_total` on the metric name, it will be removed. When
exposing the time series for counter, a `_total` suffix will be added. This is
for compatibility between OpenMetrics and the Prometheus text format, as OpenMetrics
requires the `_total` suffix.

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

A Gauge can also take its value from a callback:

```python
d = Gauge('data_objects', 'Number of objects')
my_dict = {}
d.set_function(lambda: len(my_dict))
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

The Python client doesn't store or expose quantile information at this time.

### Histogram

Histograms track the size and number of events in buckets.
This allows for aggregatable calculation of quantiles.

```python
from prometheus_client import Histogram
h = Histogram('request_latency_seconds', 'Description of histogram')
h.observe(4.7)    # Observe 4.7 (seconds in this case)
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

### Info

Info tracks key-value information, usually about a whole target.

```python
from prometheus_client import Info
i = Info('my_build_version', 'Description of info')
i.info({'version': '1.2.3', 'buildhost': 'foo@bar'})
```

### Enum

Enum tracks which of a set of states something is currently in.

```python
from prometheus_client import Enum
e = Enum('my_task_state', 'Description of enum',
        states=['starting', 'running', 'stopped'])
e.state('running')
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

Labels can also be passed as keyword-arguments:

```python
from prometheus_client import Counter
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels(method='get', endpoint='/').inc()
c.labels(method='post', endpoint='/submit').inc()
```

Metrics with labels are not initialized when declared, because the client can't
know what values the label can have. It is recommended to initialize the label
values by calling the `.labels()` method alone:

```python
from prometheus_client import Counter
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels('get', '/')
c.labels('post', '/submit')
```

### Exemplars

Exemplars can be added to counter and histogram metrics. Exemplars can be
specified by passing a dict of label value pairs to be exposed as the exemplar.
For example with a counter:

```python
from prometheus_client import Counter
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels('get', '/').inc(exemplar={'trace_id': 'abc123'})
c.labels('post', '/submit').inc(1.0, {'trace_id': 'def456'})
```

And with a histogram:

```python
from prometheus_client import Histogram
h = Histogram('request_latency_seconds', 'Description of histogram')
h.observe(4.7, {'trace_id': 'abc123'})
```

Exemplars are only rendered in the OpenMetrics exposition format. If using the
HTTP server or apps in this library, content negotiation can be used to specify
OpenMetrics (which is done by default in Prometheus). Otherwise it will be
necessary to use `generate_latest` from
`prometheus_client.openmetrics.exposition` to view exemplars.

To view exemplars in Prometheus it is also necessary to enable the the
exemplar-storage feature flag:
```
--enable-feature=exemplar-storage
```
Additional information is available in [the Prometheus
documentation](https://prometheus.io/docs/prometheus/latest/feature_flags/#exemplars-storage).

### Disabling `_created` metrics

By default counters, histograms, and summaries export an additional series
suffixed with `_created` and a value of the unix timestamp for when the metric
was created. If this information is not helpful, it can be disabled by setting
the environment variable `PROMETHEUS_DISABLE_CREATED_SERIES=True`.

### Process Collector

The Python client automatically exports metrics about process CPU usage, RAM,
file descriptors and start time. These all have the prefix `process`, and
are only currently available on Linux.

The namespace and pid constructor arguments allows for exporting metrics about
other processes, for example:
```
ProcessCollector(namespace='mydaemon', pid=lambda: open('/var/run/daemon.pid').read())
```

### Platform Collector

The client also automatically exports some metadata about Python. If using Jython,
metadata about the JVM in use is also included. This information is available as 
labels on the `python_info` metric. The value of the metric is 1, since it is the 
labels that carry information.

### Disabling Default Collector metrics

By default the collected `process`, `gc`, and `platform` collector metrics are exported.
If this information is not helpful, it can be disabled using the following:
```python
import prometheus_client

prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)
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

To add Prometheus exposition to an existing HTTP server, see the `MetricsHandler` class
which provides a `BaseHTTPRequestHandler`. It also serves as a simple example of how
to write a custom endpoint.

By default, the prometheus client will accept only HTTP requests from Prometheus.
To enable HTTPS, `certfile` and `keyfile` need to be provided. The certificate is
presented to Prometheus as a server certificate during the TLS handshake, and
the private key in the key file must belong to the public key in the certificate.

When HTTPS is enabled, by default mutual TLS (mTLS) is enforced (i.e. Prometheus is
required to present a client certificate during TLS handshake) and the client certificate
including its hostname is validated against the CA certificate chain.
insecure_skip_verify=True` can be used to disable the certificate and hostname
validations.

`cafile` can be used to specify a certificate file containing a CA certificate chain that
is used to validate the client certificate. If not provided, a default CA certificate chain
is used (see Python [ssl.SSLContext.load_default_certs()](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.load_default_certs))

```
from prometheus_client import start_http_server

start_http_server(8000, certfile="server_certificate.pem", keyfile="private_key.pem")
```

#### Twisted

To use prometheus with [twisted](https://twistedmatrix.com/), there is `MetricsResource` which exposes metrics as a twisted resource.

```python
from prometheus_client.twisted import MetricsResource
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor

root = Resource()
root.putChild(b'metrics', MetricsResource())

factory = Site(root)
reactor.listenTCP(8000, factory)
reactor.run()
```

#### WSGI

To use Prometheus with [WSGI](http://wsgi.readthedocs.org/en/latest/), there is
`make_wsgi_app` which creates a WSGI application.

```python
from prometheus_client import make_wsgi_app
from wsgiref.simple_server import make_server

app = make_wsgi_app()
httpd = make_server('', 8000, app)
httpd.serve_forever()
```

Such an application can be useful when integrating Prometheus metrics with WSGI
apps.

The method `start_wsgi_server` can be used to serve the metrics through the
WSGI reference implementation in a new thread.

```python
from prometheus_client import start_wsgi_server

start_wsgi_server(8000)
```

By default, the WSGI application will respect `Accept-Encoding:gzip` headers used by Prometheus
and compress the response if such a header is present. This behaviour can be disabled by passing
`disable_compression=True` when creating the app, like this:

```python
app = make_wsgi_app(disable_compression=True)
```

#### ASGI

To use Prometheus with [ASGI](http://asgi.readthedocs.org/en/latest/), there is
`make_asgi_app` which creates an ASGI application.

```python
from prometheus_client import make_asgi_app

app = make_asgi_app()
```
Such an application can be useful when integrating Prometheus metrics with ASGI
apps.

By default, the WSGI application will respect `Accept-Encoding:gzip` headers used by Prometheus
and compress the response if such a header is present. This behaviour can be disabled by passing 
`disable_compression=True` when creating the app, like this:

```python
app = make_asgi_app(disable_compression=True)
```

#### Flask

To use Prometheus with [Flask](http://flask.pocoo.org/) we need to serve metrics through a Prometheus WSGI application. This can be achieved using [Flask's application dispatching](http://flask.pocoo.org/docs/latest/patterns/appdispatch/). Below is a working example.

Save the snippet below in a `myapp.py` file

```python
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app

# Create my app
app = Flask(__name__)

# Add prometheus wsgi middleware to route /metrics requests
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})
```

Run the example web application like this

```bash
# Install uwsgi if you do not have it
pip install uwsgi
uwsgi --http 127.0.0.1:8000 --wsgi-file myapp.py --callable app
```

Visit http://localhost:8000/metrics to see the metrics

#### FastAPI + Gunicorn

To use Prometheus with [FastAPI](https://fastapi.tiangolo.com/) and [Gunicorn](https://gunicorn.org/) we need to serve metrics through a Prometheus ASGI application.

Save the snippet below in a `myapp.py` file

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app

# Create app
app = FastAPI(debug=False)

# Add prometheus asgi middleware to route /metrics requests
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

For Multiprocessing support, use this modified code snippet. Full multiprocessing instructions are provided [here](https://github.com/prometheus/client_python#multiprocess-mode-eg-gunicorn).

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app

app = FastAPI(debug=False)

# Using multiprocess collector for registry
def make_metrics_app():
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return make_asgi_app(registry=registry)


metrics_app = make_metrics_app()
app.mount("/metrics", metrics_app)
```

Run the example web application like this

```bash
# Install gunicorn if you do not have it
pip install gunicorn
# If using multiple workers, add `--workers n` parameter to the line below
gunicorn -b 127.0.0.1:8000 myapp:app -k uvicorn.workers.UvicornWorker
```

Visit http://localhost:8000/metrics to see the metrics


### Node exporter textfile collector

The [textfile collector](https://github.com/prometheus/node_exporter#textfile-collector)
allows machine-level statistics to be exported out via the Node exporter.

This is useful for monitoring cronjobs, or for writing cronjobs to expose metrics
about a machine system that the Node exporter does not support or would not make sense
to perform at every scrape (for example, anything involving subprocesses).

```python
from prometheus_client import CollectorRegistry, Gauge, write_to_textfile

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
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

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

### Handlers for authentication

If the push gateway you are connecting to is protected with HTTP Basic Auth,
you can use a special handler to set the Authorization header.

```python
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from prometheus_client.exposition import basic_auth_handler

def my_auth_handler(url, method, timeout, headers, data):
    username = 'foobar'
    password = 'secret123'
    return basic_auth_handler(url, method, timeout, headers, data, username, password)
registry = CollectorRegistry()
g = Gauge('job_last_success_unixtime', 'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
push_to_gateway('localhost:9091', job='batchA', registry=registry, handler=my_auth_handler)
```

TLS Auth is also supported when using the push gateway with a special handler.

```python
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from prometheus_client.exposition import tls_auth_handler


def my_auth_handler(url, method, timeout, headers, data):
    certfile = 'client-crt.pem'
    keyfile = 'client-key.pem'
    return tls_auth_handler(url, method, timeout, headers, data, certfile, keyfile)

registry = CollectorRegistry()
g = Gauge('job_last_success_unixtime', 'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
push_to_gateway('localhost:9091', job='batchA', registry=registry, handler=my_auth_handler)
```

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

Graphite [tags](https://grafana.com/blog/2018/01/11/graphite-1.1-teaching-an-old-dog-new-tricks/) are also supported.

```python
from prometheus_client.bridge.graphite import GraphiteBridge

gb = GraphiteBridge(('graphite.your.org', 2003), tags=True)
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels('get', '/').inc()
gb.push()
```

## Custom Collectors

Sometimes it is not possible to directly instrument code, as it is not
in your control. This requires you to proxy metrics from other systems.

To do so you need to create a custom collector, for example:

```python
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY

class CustomCollector(object):
    def collect(self):
        yield GaugeMetricFamily('my_gauge', 'Help text', value=7)
        c = CounterMetricFamily('my_counter_total', 'Help text', labels=['foo'])
        c.add_metric(['bar'], 1.7)
        c.add_metric(['baz'], 3.8)
        yield c

REGISTRY.register(CustomCollector())
```

`SummaryMetricFamily`, `HistogramMetricFamily` and `InfoMetricFamily` work similarly.

A collector may implement a `describe` method which returns metrics in the same
format as `collect` (though you don't have to include the samples). This is
used to predetermine the names of time series a `CollectorRegistry` exposes and
thus to detect collisions and duplicate registrations.

Usually custom collectors do not have to implement `describe`. If `describe` is
not implemented and the CollectorRegistry was created with `auto_describe=True`
(which is the case for the default registry) then `collect` will be called at
registration time instead of `describe`. If this could cause problems, either
implement a proper `describe`, or if that's not practical have `describe`
return an empty list.


## Multiprocess Mode (E.g. Gunicorn)

Prometheus client libraries presume a threaded model, where metrics are shared
across workers. This doesn't work so well for languages such as Python where
it's common to have processes rather than threads to handle large workloads.

To handle this the client library can be put in multiprocess mode.
This comes with a number of limitations:

- Registries can not be used as normal, all instantiated metrics are exported
  - Registering metrics to a registry later used by a `MultiProcessCollector`
    may cause duplicate metrics to be exported
- Custom collectors do not work (e.g. cpu and memory metrics)
- Info and Enum metrics do not work
- The pushgateway cannot be used
- Gauges cannot use the `pid` label
- Exemplars are not supported

There's several steps to getting this working:

**1. Deployment**:

The `PROMETHEUS_MULTIPROC_DIR` environment variable must be set to a directory
that the client library can use for metrics. This directory must be wiped
between process/Gunicorn runs (before startup is recommended).

This environment variable should be set from a start-up shell script,
and not directly from Python (otherwise it may not propagate to child processes).

**2. Metrics collector**:

The application must initialize a new `CollectorRegistry`, and store the
multi-process collector inside. It is a best practice to create this registry
inside the context of a request to avoid metrics registering themselves to a
collector used by a `MultiProcessCollector`. If a registry with metrics
registered is used by a `MultiProcessCollector` duplicate metrics may be
exported, one for multiprocess, and one for the process serving the request.

```python
from prometheus_client import multiprocess
from prometheus_client import generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST, Counter

MY_COUNTER = Counter('my_counter', 'Description of my counter')

# Expose metrics.
def app(environ, start_response):
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    data = generate_latest(registry)
    status = '200 OK'
    response_headers = [
        ('Content-type', CONTENT_TYPE_LATEST),
        ('Content-Length', str(len(data)))
    ]
    start_response(status, response_headers)
    return iter([data])
```

**3. Gunicorn configuration**:

The `gunicorn` configuration file needs to include the following function:

```python
from prometheus_client import multiprocess

def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
```

**4. Metrics tuning (Gauge)**:

When `Gauge`s are used in multiprocess applications,
you must decide how to handle the metrics reported by each process.
Gauges have several modes they can run in, which can be selected with the `multiprocess_mode` parameter.

- 'all': Default. Return a timeseries per process (alive or dead), labelled by the process's `pid` (the label is added internally).
- 'min': Return a single timeseries that is the minimum of the values of all processes (alive or dead).
- 'max': Return a single timeseries that is the maximum of the values of all processes (alive or dead).
- 'sum': Return a single timeseries that is the sum of the values of all processes (alive or dead).

Prepend 'live' to the beginning of the mode to return the same result but only considering living processes
(e.g., 'liveall, 'livesum', 'livemax', 'livemin').

```python
from prometheus_client import Gauge

# Example gauge
IN_PROGRESS = Gauge("inprogress_requests", "help", multiprocess_mode='livesum')
```


## Parser

The Python client supports parsing the Prometheus text format.
This is intended for advanced use cases where you have servers
exposing Prometheus metrics and need to get them into some other
system.

```python
from prometheus_client.parser import text_string_to_metric_families
for family in text_string_to_metric_families(u"my_gauge 1.0\n"):
  for sample in family.samples:
    print("Name: {0} Labels: {1} Value: {2}".format(*sample))
```

## Links

* [Releases](https://github.com/prometheus/client_python/releases): The releases page shows the history of the project and acts as a changelog.
* [PyPI](https://pypi.python.org/pypi/prometheus_client)
