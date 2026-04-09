---
title: Info
weight: 5
---

Info tracks key-value pairs that describe a target — build version, configuration, or environment metadata. The values are static: once set, the metric outputs a single time series with all key-value pairs as labels and a constant value of 1.

```python
from prometheus_client import Info
i = Info('my_build_version', 'Description of info')
i.info({'version': '1.2.3', 'buildhost': 'foo@bar'})
```

Info exposes one time series per metric:
- `<name>_info{<key>="<value>", ...}` — always 1; the key-value pairs become labels

Note: Info metrics do not work in multiprocess mode.

## Constructor

```python
Info(name, documentation, labelnames=(), namespace='', subsystem='', unit='', registry=REGISTRY)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. A `_info` suffix is appended automatically when exposing the time series. |
| `documentation` | `str` | required | Help text shown in the `/metrics` output and Prometheus UI. |
| `labelnames` | `Iterable[str]` | `()` | Names of labels for this metric. See [Labels](../labels/). Keys passed to `.info()` must not overlap with these label names. |
| `namespace` | `str` | `''` | Optional prefix. |
| `subsystem` | `str` | `''` | Optional middle component. |
| `unit` | `str` | `''` | Not supported — raises `ValueError`. Info metrics cannot have a unit. |
| `registry` | `CollectorRegistry` | `REGISTRY` | Registry to register with. Pass `None` to skip registration, which is useful in tests where you create metrics without wanting them in the global registry. |

`namespace`, `subsystem`, and `name` are joined with underscores to form the full metric name:

```python
# namespace='myapp', subsystem='http', name='build'
# produces: myapp_http_build_info
Info('build', 'Build information', namespace='myapp', subsystem='http')
```

## Methods

### `info(val)`

Set the key-value pairs for this metric. `val` must be a `dict[str, str]` — both keys and values must be strings. Keys must not overlap with the metric's label names and values cannot be `None`. Calling `info()` again overwrites the previous value.

```python
i.info({'version': '1.4.2', 'revision': 'abc123', 'branch': 'main'})
```

## Labels

See [Labels](../labels/) for how to use `.labels()`, `.remove()`, `.remove_by_labels()`, and `.clear()`.

## Real-world example

Exposing application build metadata so dashboards can join on version:

```python
from prometheus_client import Info, start_http_server

BUILD_INFO = Info(
    'build',
    'Application build information',
    namespace='myapp',
)

BUILD_INFO.info({
    'version': '1.4.2',
    'revision': 'abc123def456',
    'branch': 'main',
    'build_date': '2024-01-15',
})

if __name__ == '__main__':
    start_http_server(8000)  # exposes metrics at http://localhost:8000/metrics
    # ... start your application ...
```

This produces:
```
myapp_build_info{branch="main",build_date="2024-01-15",revision="abc123def456",version="1.4.2"} 1.0
```
