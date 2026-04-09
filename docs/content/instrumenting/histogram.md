---
title: Histogram
weight: 4
---

A Histogram samples observations and counts them in configurable buckets. Use it
when you want to track distributions — request latency, response sizes — and need
to calculate quantiles (p50, p95, p99) in your queries.

```python
from prometheus_client import Histogram
h = Histogram('request_latency_seconds', 'Description of histogram')
h.observe(4.7)    # Observe 4.7 (seconds in this case)
```

A Histogram exposes three time series per metric:
- `<name>_bucket{le="<bound>"}` — count of observations with value ≤ le (cumulative)
- `<name>_sum` — sum of all observed values
- `<name>_count` — total number of observations

## Constructor

```python
Histogram(name, documentation, labelnames=(), namespace='', subsystem='', unit='', registry=REGISTRY, buckets=DEFAULT_BUCKETS)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. |
| `documentation` | `str` | required | Help text shown in the `/metrics` output and Prometheus UI. |
| `labelnames` | `Iterable[str]` | `()` | Names of labels for this metric. See [Labels](../labels/). Note: `le` is reserved and cannot be used as a label name. |
| `namespace` | `str` | `''` | Optional prefix. |
| `subsystem` | `str` | `''` | Optional middle component. |
| `unit` | `str` | `''` | Optional unit suffix appended to the metric name. |
| `registry` | `CollectorRegistry` | `REGISTRY` | Registry to register with. Pass `None` to skip registration, which is useful in tests where you create metrics without wanting them in the global registry. |
| `buckets` | `Sequence[float]` | `DEFAULT_BUCKETS` | Upper bounds of the histogram buckets. Must be in ascending order. `+Inf` is always appended automatically. |

`namespace`, `subsystem`, and `name` are joined with underscores to form the full metric name:

```python
# namespace='myapp', subsystem='http', name='request_duration_seconds'
# produces: myapp_http_request_duration_seconds
Histogram('request_duration_seconds', 'Latency', namespace='myapp', subsystem='http')
```

Default buckets are intended to cover typical web/RPC request latency in seconds and are
accessible as `Histogram.DEFAULT_BUCKETS`:

```
.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, +Inf
```

To override with buckets tuned to your workload:

```python
h = Histogram('request_latency_seconds', 'Latency', buckets=[.1, .5, 1, 2, 5])
```

## Methods

### `observe(amount, exemplar=None)`

Record a single observation. The amount is typically positive or zero.

```python
h.observe(0.43)   # observe 430ms
```

To attach trace context to an observation, pass an `exemplar` dict. Exemplars are
only rendered in OpenMetrics format. See [Exemplars](../exemplars/) for details.

```python
h.observe(0.43, exemplar={'trace_id': 'abc123'})
```

### `time()`

Observe the duration in seconds of a block of code or function and add it to the
histogram. Every call accumulates — unlike `Gauge.time()`, which only keeps the
most recent duration. Can be used as a decorator or context manager.

```python
@h.time()
def process():
    pass

with h.time():
    pass
```

## Labels

See [Labels](../labels/) for how to use `.labels()`, `.remove()`, `.remove_by_labels()`, and `.clear()`.

## Real-world example

Tracking HTTP request latency with custom buckets tuned to the workload:

```python
from prometheus_client import Histogram, start_http_server

REQUEST_LATENCY = Histogram(
    'request_duration_seconds',
    'HTTP request latency',
    labelnames=['method', 'endpoint'],
    namespace='myapp',
    buckets=[.01, .05, .1, .25, .5, 1, 2.5, 5],
)

def handle_request(method, endpoint):
    with REQUEST_LATENCY.labels(method=method, endpoint=endpoint).time():
        # ... handle the request ...
        pass

if __name__ == '__main__':
    start_http_server(8000)  # exposes metrics at http://localhost:8000/metrics
    # ... start your application ...
```

This produces time series like:
```
myapp_request_duration_seconds_bucket{method="GET",endpoint="/api/users",le="0.1"} 42
myapp_request_duration_seconds_sum{method="GET",endpoint="/api/users"} 3.7
myapp_request_duration_seconds_count{method="GET",endpoint="/api/users"} 50
```
