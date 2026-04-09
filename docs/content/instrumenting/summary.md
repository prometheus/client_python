---
title: Summary
weight: 3
---

A Summary samples observations and tracks the total count and sum. Use it when
you want to track the size or duration of events and compute averages, but do not
need per-bucket breakdown or quantiles in your Prometheus queries.

The Python client does not compute quantiles locally. If you need p50/p95/p99,
use a [Histogram](../histogram/) instead.

```python
from prometheus_client import Summary
s = Summary('request_latency_seconds', 'Description of summary')
s.observe(4.7)    # Observe 4.7 (seconds in this case)
```

A Summary exposes two time series per metric:
- `<name>_count` — total number of observations
- `<name>_sum` — sum of all observed values

## Constructor

```python
Summary(name, documentation, labelnames=(), namespace='', subsystem='', unit='', registry=REGISTRY)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. |
| `documentation` | `str` | required | Help text shown in the `/metrics` output and Prometheus UI. |
| `labelnames` | `Iterable[str]` | `()` | Names of labels for this metric. See [Labels](../labels/). Note: `quantile` is reserved and cannot be used as a label name. |
| `namespace` | `str` | `''` | Optional prefix. |
| `subsystem` | `str` | `''` | Optional middle component. |
| `unit` | `str` | `''` | Optional unit suffix appended to the metric name. |
| `registry` | `CollectorRegistry` | `REGISTRY` | Registry to register with. Pass `None` to skip registration, which is useful in tests where you create metrics without wanting them in the global registry. |

`namespace`, `subsystem`, and `name` are joined with underscores to form the full metric name:

```python
# namespace='myapp', subsystem='worker', name='task_duration_seconds'
# produces: myapp_worker_task_duration_seconds
Summary('task_duration_seconds', 'Task duration', namespace='myapp', subsystem='worker')
```

## Methods

### `observe(amount)`

Record a single observation. The amount is typically positive or zero.

```python
s.observe(0.43)   # observe 430ms
s.observe(1024)   # observe 1024 bytes
```

### `time()`

Observe the duration in seconds of a block of code or function and add it to the
summary. Every call accumulates — unlike `Gauge.time()`, which only keeps the
most recent duration. Can be used as a decorator or context manager.

```python
@s.time()
def process():
    pass

with s.time():
    pass
```

## Labels

See [Labels](../labels/) for how to use `.labels()`, `.remove()`, `.remove_by_labels()`, and `.clear()`.

## Real-world example

Tracking the duration of background tasks:

```python
from prometheus_client import Summary, start_http_server

TASK_DURATION = Summary(
    'task_duration_seconds',
    'Time spent processing background tasks',
    labelnames=['task_type'],
    namespace='myapp',
)

def run_task(task_type, task):
    with TASK_DURATION.labels(task_type=task_type).time():
        # ... run the task ...
        pass

if __name__ == '__main__':
    start_http_server(8000)  # exposes metrics at http://localhost:8000/metrics
    # ... start your application ...
```

This produces:
```
myapp_task_duration_seconds_count{task_type="email"} 120
myapp_task_duration_seconds_sum{task_type="email"} 48.3
```

You can compute the average duration in PromQL as:
```
rate(myapp_task_duration_seconds_sum[5m]) / rate(myapp_task_duration_seconds_count[5m])
```
