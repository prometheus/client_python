---
title: Counter
weight: 1
---

A Counter tracks a value that only ever goes up. Use it for things you count — requests
served, errors raised, bytes sent. When the process restarts, the counter resets to zero.

If your value can go down, use a [Gauge](../gauge/) instead.

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

## Constructor

```python
Counter(name, documentation, labelnames=(), namespace='', subsystem='', unit='', registry=REGISTRY)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. A `_total` suffix is appended automatically when exposing the time series. |
| `documentation` | `str` | required | Help text shown in the `/metrics` output and Prometheus UI. |
| `labelnames` | `Iterable[str]` | `()` | Names of labels for this metric. See [Labels](../labels/). |
| `namespace` | `str` | `''` | Optional prefix. |
| `subsystem` | `str` | `''` | Optional middle component. |
| `unit` | `str` | `''` | Optional unit suffix appended to the metric name. |
| `registry` | `CollectorRegistry` | `REGISTRY` | Registry to register with. Pass `None` to skip registration, which is useful in tests where you create metrics without wanting them in the global registry. |

`namespace`, `subsystem`, and `name` are joined with underscores to form the full metric name:

```python
# namespace='myapp', subsystem='http', name='requests_total'
# produces: myapp_http_requests_total
Counter('requests_total', 'Total requests', namespace='myapp', subsystem='http')
```

## Methods

### `inc(amount=1, exemplar=None)`

Increment the counter by the given amount. The amount must be non-negative.

```python
c.inc()       # increment by 1
c.inc(5)      # increment by 5
c.inc(0.7)    # fractional increments are allowed
```

To attach trace context to an observation, pass an `exemplar` dict. Exemplars are
only rendered in OpenMetrics format. See [Exemplars](../exemplars/) for details.

```python
c.inc(exemplar={'trace_id': 'abc123'})
```

### `reset()`

Reset the counter to zero. Use this when a logical process restarts without
restarting the actual Python process.

```python
c.reset()
```

### `count_exceptions(exception=Exception)`

Count exceptions raised in a block of code or function. Can be used as a
decorator or context manager. Increments the counter each time an exception
of the given type is raised.

```python
@c.count_exceptions()
def f():
    pass

with c.count_exceptions():
    pass

# Count only a specific exception type
with c.count_exceptions(ValueError):
    pass
```

## Labels

See [Labels](../labels/) for how to use `.labels()`, `.remove()`, `.remove_by_labels()`, and `.clear()`.

## Real-world example

Tracking HTTP requests by method and status code in a web application:

```python
from prometheus_client import Counter, start_http_server

REQUESTS = Counter(
    'requests_total',
    'Total HTTP requests received',
    labelnames=['method', 'status'],
    namespace='myapp',
)
EXCEPTIONS = Counter(
    'exceptions_total',
    'Total unhandled exceptions',
    labelnames=['handler'],
    namespace='myapp',
)

def handle_request(method, handler):
    with EXCEPTIONS.labels(handler=handler).count_exceptions():
        # ... process the request ...
        status = '200'
    REQUESTS.labels(method=method, status=status).inc()

if __name__ == '__main__':
    start_http_server(8000)  # exposes metrics at http://localhost:8000/metrics
    # ... start your application ...
```

This produces time series like `myapp_requests_total{method="GET",status="200"}`.
