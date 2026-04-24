---
title: Registry
weight: 8
---

A `CollectorRegistry` holds all the collectors whose metrics are exposed when
the registry is scraped. The global default registry is `REGISTRY`, which all
metric constructors register with automatically unless told otherwise.

```python
from prometheus_client import REGISTRY, CollectorRegistry

# Use the default global registry
from prometheus_client import Counter
c = Counter('my_counter', 'A counter')  # registered with REGISTRY automatically

# Create an isolated registry, e.g. for testing
r = CollectorRegistry()
c2 = Counter('my_counter', 'A counter', registry=r)
```

## Constructor

```python
CollectorRegistry(auto_describe=False, target_info=None, support_collectors_without_names=False)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `auto_describe` | `bool` | `False` | If `True`, calls `collect()` on a collector at registration time if the collector does not implement `describe()`. Used to detect duplicate metric names. The default `REGISTRY` is created with `auto_describe=True`. |
| `target_info` | `Dict[str, str]` | `None` | Key-value labels to attach as a `target_info` metric. Equivalent to calling `set_target_info` after construction. |
| `support_collectors_without_names` | `bool` | `False` | If `True`, allows registering collectors that produce no named metrics (i.e. whose `describe()` returns an empty list). |

## Methods

### `register(collector)`

Register a collector with this registry. Raises `ValueError` if any of the
metric names the collector produces are already registered.

```python
from prometheus_client.registry import Collector

class MyCollector(Collector):
    def collect(self):
        ...

REGISTRY.register(MyCollector())
```

### `unregister(collector)`

Remove a previously registered collector.

```python
from prometheus_client import GC_COLLECTOR
REGISTRY.unregister(GC_COLLECTOR)
```

### `collect()`

Yield all metrics from every registered collector. Also yields the
`target_info` metric if one has been set.

```python
for metric in REGISTRY.collect():
    print(metric.name, metric.type)
```

### `restricted_registry(names)`

Return a view of this registry that only exposes the named metrics. Useful
for partial scrapes. See [Restricted registry](../restricted-registry/) for
usage with `generate_latest` and the built-in HTTP server.

```python
from prometheus_client import generate_latest

subset = REGISTRY.restricted_registry(['python_info', 'process_cpu_seconds_total'])
output = generate_latest(subset)
```

### `get_sample_value(name, labels=None)`

Return the current value of a single sample, or `None` if not found. Intended
for use in unit tests; not efficient for production use.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Full sample name including any suffix (e.g. `'my_counter_total'`). |
| `labels` | `Dict[str, str]` | `{}` | Label key-value pairs to match. An empty dict matches an unlabelled sample. |

```python
from prometheus_client import Counter, CollectorRegistry

r = CollectorRegistry()
c = Counter('requests_total', 'Total requests', registry=r)
c.inc(3)

assert r.get_sample_value('requests_total') == 3.0
```

### `set_target_info(labels)`

Set or replace the target metadata labels exposed as a `target_info` metric.
Pass `None` to remove the target info metric.

```python
REGISTRY.set_target_info({'env': 'production', 'region': 'us-east-1'})
```

### `get_target_info()`

Return the current target info labels as a `Dict[str, str]`, or `None` if not set.

```python
info = REGISTRY.get_target_info()
```

## The global REGISTRY

`REGISTRY` is the module-level default instance, created as:

```python
REGISTRY = CollectorRegistry(auto_describe=True)
```

All metric constructors (`Counter`, `Gauge`, etc.) register with `REGISTRY`
by default. Pass `registry=None` to skip registration, or pass a different
`CollectorRegistry` instance to use a custom registry.

```python
from prometheus_client import Counter, CollectorRegistry

# skip global registration — useful in tests
c = Counter('my_counter', 'A counter', registry=None)

# register with a custom registry
r = CollectorRegistry()
c2 = Counter('my_counter', 'A counter', registry=r)
```
