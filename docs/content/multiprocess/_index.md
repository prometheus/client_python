---
title: Multiprocess Mode
weight: 5
---

Prometheus client libraries presume a threaded model, where metrics are shared
across workers. This doesn't work so well for languages such as Python where
it's common to have processes rather than threads to handle large workloads.

To handle this the client library can be put in multiprocess mode.
This comes with a number of limitations:

- Registries can not be used as normal
  - Registering metrics to a registry later used by a `MultiProcessCollector`
    may cause duplicate metrics to be exported
  - Filtering on metrics works but is inefficient
- Custom collectors do not work (e.g. cpu and memory metrics)
- Gauges cannot use `set_function`
- Info and Enum metrics do not work
- The pushgateway cannot be used
- Gauges cannot use the `pid` label
- Exemplars are not supported
- Remove and Clear of labels are currently not supported in multiprocess mode.

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
- 'mostrecent': Return a single timeseries that is the most recent value among all processes (alive or dead).

Prepend 'live' to the beginning of the mode to return the same result but only considering living processes
(e.g., 'liveall, 'livesum', 'livemax', 'livemin', 'livemostrecent').

```python
from prometheus_client import Gauge

# Example gauge
IN_PROGRESS = Gauge("inprogress_requests", "help", multiprocess_mode='livesum')
```
