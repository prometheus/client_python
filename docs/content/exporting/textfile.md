---
title: Node exporter textfile collector
weight: 2
---

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

## API Reference

### `write_to_textfile(path, registry, escaping='allow-utf-8', tmpdir=None)`

Writes metrics from the registry to a file in Prometheus text format.

The file is written atomically: metrics are first written to a temporary file in the same
directory as `path` (or in `tmpdir` if provided), then renamed into place. This prevents the
Node exporter from reading a partially written file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Destination file path. Must end in `.prom` for the Node exporter textfile collector to process it. |
| `registry` | `Collector` | required | Registry whose metrics are written. |
| `escaping` | `str` | `'allow-utf-8'` | Escaping scheme for metric and label names. Accepted values: `'allow-utf-8'`, `'underscores'`, `'dots'`, `'values'`. |
| `tmpdir` | `Optional[str]` | `None` | Directory for the temporary file used during the atomic write. Defaults to the same directory as `path`. If provided, must be on the same filesystem as `path`. |

Returns `None`. Raises an exception if the file cannot be written; the temporary file is cleaned
up automatically on failure.