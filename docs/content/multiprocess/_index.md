---
title: Multiprocess Mode
weight: 5
---

Prometheus client libraries presume a threaded model, where metrics are shared
across workers. This doesn't work so well for languages such as Python where
it's common to have processes rather than threads to handle large workloads.

To handle this the client library can be put in multiprocess mode.
This comes with a number of limitations:

- Registries can not be used as normal:
  - all instantiated metrics are collected
  - Registering metrics to a registry later used by a `MultiProcessCollector`
    may cause duplicate metrics to be exported
  - Filtering on metrics works if and only if the constructor was called with
    `support_collectors_without_names=True` and it but might be inefficient.
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

## Cleaning `PROMETHEUS_MULTIPROC_DIR`

The multiprocess directory is not cleaned automatically. If it is not wiped before startup, stale files from a previous run can lead to incorrect metrics.

A common pattern is to wipe and recreate the directory in your process manager/entrypoint script **before** starting Gunicorn/workers:

```bash
rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
```

Notes:
- Only wipe a directory that is dedicated to multiprocess metric files.
- In containerized deployments, `PROMETHEUS_MULTIPROC_DIR` is often set to a dedicated path such as `/tmp/prometheus_multiproc_dir`.
- If you run multiple independent apps on the same machine, each should use a separate multiprocess directory.

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
    registry = CollectorRegistry(support_collectors_without_names=True)
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

## API Reference

### `MultiProcessCollector(registry, path=None)`

Collector that aggregates metrics written by all processes in the multiprocess directory.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `registry` | `CollectorRegistry` | required | Registry to register with. Pass a registry created inside the request context to avoid duplicate metrics. |
| `path` | `Optional[str]` | `None` | Path to the directory containing the per-process metric files. Defaults to the `PROMETHEUS_MULTIPROC_DIR` environment variable. |

Raises `ValueError` if `path` is not set or does not point to an existing directory.

```python
from prometheus_client import multiprocess, CollectorRegistry

def app(environ, start_response):
    registry = CollectorRegistry(support_collectors_without_names=True)
    multiprocess.MultiProcessCollector(registry)
    ...
```

To use a custom path instead of the environment variable:

```python
collector = multiprocess.MultiProcessCollector(registry, path='/var/run/prom')
```

### `mark_process_dead(pid, path=None)`

Removes the per-process metric files for a dead process. Call this from your process manager
when a worker exits to prevent stale `live*` gauge values from accumulating.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pid` | `int` | required | PID of the process that has exited. |
| `path` | `Optional[str]` | `None` | Path to the multiprocess directory. Defaults to the `PROMETHEUS_MULTIPROC_DIR` environment variable. |

Returns `None`. Only removes files for `live*` gauge modes (e.g. `livesum`, `liveall`); files
for non-live modes are left in place so their last values remain visible until the directory is
wiped on restart.

```python
# Gunicorn config
from prometheus_client import multiprocess

def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
```
