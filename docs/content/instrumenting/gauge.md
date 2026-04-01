---
title: Gauge
weight: 2
---

A Gauge tracks a value that can go up and down. Use it for things you sample at a
point in time — active connections, queue depth, memory usage, temperature.

```python
from prometheus_client import Gauge
g = Gauge('my_inprogress_requests', 'Description of gauge')
g.inc()      # Increment by 1
g.dec(10)    # Decrement by given value
g.set(4.2)   # Set to a given value
```

## Constructor

```python
Gauge(name, documentation, labelnames=(), namespace='', subsystem='', unit='', registry=REGISTRY, multiprocess_mode='all')
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. |
| `documentation` | `str` | required | Help text shown in the `/metrics` output and Prometheus UI. |
| `labelnames` | `Iterable[str]` | `()` | Names of labels for this metric. See [Labels](../labels/). |
| `namespace` | `str` | `''` | Optional prefix. |
| `subsystem` | `str` | `''` | Optional middle component. |
| `unit` | `str` | `''` | Optional unit suffix appended to the metric name. |
| `registry` | `CollectorRegistry` | `REGISTRY` | Registry to register with. Pass `None` to skip registration, which is useful in tests where you create metrics without wanting them in the global registry. |
| `multiprocess_mode` | `str` | `'all'` | How to aggregate this gauge across multiple processes. See [Multiprocess mode](../../multiprocess/). Options: `all`, `liveall`, `min`, `livemin`, `max`, `livemax`, `sum`, `livesum`, `mostrecent`, `livemostrecent`. |

`namespace`, `subsystem`, and `name` are joined with underscores to form the full metric name:

```python
# namespace='myapp', subsystem='db', name='connections_active'
# produces: myapp_db_connections_active
Gauge('connections_active', 'Active DB connections', namespace='myapp', subsystem='db')
```

## Methods

### `inc(amount=1)`

Increment the gauge by the given amount.

```python
g.inc()    # increment by 1
g.inc(3)   # increment by 3
```

Note: raises `RuntimeError` if `multiprocess_mode` is `mostrecent` or `livemostrecent`.

### `dec(amount=1)`

Decrement the gauge by the given amount.

```python
g.dec()    # decrement by 1
g.dec(3)   # decrement by 3
```

Note: raises `RuntimeError` if `multiprocess_mode` is `mostrecent` or `livemostrecent`.

### `set(value)`

Set the gauge to the given value.

```python
g.set(42.5)
```

### `set_to_current_time()`

Set the gauge to the current Unix timestamp in seconds. Useful for tracking
when an event last occurred.

```python
g.set_to_current_time()
```

### `track_inprogress()`

Increment the gauge when a block of code or function is entered, and decrement
it when exited. Can be used as a decorator or context manager.

```python
@g.track_inprogress()
def process_job():
    pass

with g.track_inprogress():
    pass
```

### `time()`

Set the gauge to the duration in seconds of the most recent execution of a
block of code or function. Unlike `Histogram.time()` and `Summary.time()`,
which accumulate all observations, this overwrites the gauge with the latest
duration each time. Can be used as a decorator or context manager.

```python
@g.time()
def process():
    pass

with g.time():
    pass
```

### `set_function(f)`

Bind a callback function that returns the gauge value. The function is called
each time the metric is scraped. All other methods become no-ops after calling
this.

```python
queue = []
g.set_function(lambda: len(queue))
```

## Labels

See [Labels](../labels/) for how to use `.labels()`, `.remove()`, `.remove_by_labels()`, and `.clear()`.

## Real-world example

Tracking active database connections and queue depth:

```python
from prometheus_client import Gauge, start_http_server

ACTIVE_CONNECTIONS = Gauge(
    'connections_active',
    'Number of active database connections',
    namespace='myapp',
)
QUEUE_SIZE = Gauge(
    'job_queue_size',
    'Number of jobs waiting in the queue',
    namespace='myapp',
)

job_queue = []
QUEUE_SIZE.set_function(lambda: len(job_queue))

def acquire_connection():
    ACTIVE_CONNECTIONS.inc()

def release_connection():
    ACTIVE_CONNECTIONS.dec()

if __name__ == '__main__':
    start_http_server(8000)  # exposes metrics at http://localhost:8000/metrics
    # ... start your application ...
```
