---
title: Collector
weight: 3
---

# Process Collector

The Python client automatically exports metrics about process CPU usage, RAM,
file descriptors and start time. These all have the prefix `process`, and
are only currently available on Linux.

The namespace and pid constructor arguments allows for exporting metrics about
other processes, for example:
```
ProcessCollector(namespace='mydaemon', pid=lambda: open('/var/run/daemon.pid').read())
```

# Platform Collector

The client also automatically exports some metadata about Python. If using Jython,
metadata about the JVM in use is also included. This information is available as
labels on the `python_info` metric. The value of the metric is 1, since it is the
labels that carry information.

# Disabling Default Collector metrics

By default the collected `process`, `gc`, and `platform` collector metrics are exported.
If this information is not helpful, it can be disabled using the following:

```python
import prometheus_client

prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)
```

## API Reference

### ProcessCollector

```python
ProcessCollector(namespace='', pid=lambda: 'self', proc='/proc', registry=REGISTRY)
```

Collects process metrics from `/proc`. Only available on Linux.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `namespace` | `str` | `''` | Prefix added to all metric names, e.g. `'mydaemon'` produces `mydaemon_process_cpu_seconds_total`. |
| `pid` | `Callable[[], int or str]` | `lambda: 'self'` | Callable that returns the PID to monitor. `'self'` monitors the current process. |
| `proc` | `str` | `'/proc'` | Path to the proc filesystem. Useful for testing or containerised environments with a non-standard mount point. |
| `registry` | `CollectorRegistry` | `REGISTRY` | Registry to register with. Pass `None` to skip registration. |

Metrics exported:

| Metric | Description |
|--------|-------------|
| `process_cpu_seconds_total` | Total user and system CPU time in seconds. |
| `process_virtual_memory_bytes` | Virtual memory size in bytes. |
| `process_resident_memory_bytes` | Resident memory size in bytes. |
| `process_start_time_seconds` | Start time since Unix epoch in seconds. |
| `process_open_fds` | Number of open file descriptors. |
| `process_max_fds` | Maximum number of open file descriptors. |

The module-level `PROCESS_COLLECTOR` is the default instance registered with `REGISTRY`.

### PlatformCollector

```python
PlatformCollector(registry=REGISTRY, platform=None)
```

Exports Python runtime metadata as a `python_info` gauge metric with labels.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `registry` | `CollectorRegistry` | `REGISTRY` | Registry to register with. Pass `None` to skip registration. |
| `platform` | module | `None` | Override the `platform` module. Intended for testing. |

Labels on `python_info`: `version`, `implementation`, `major`, `minor`, `patchlevel`.
On Jython, additional labels are added: `jvm_version`, `jvm_release`, `jvm_vendor`, `jvm_name`.

The module-level `PLATFORM_COLLECTOR` is the default instance registered with `REGISTRY`.

### GCCollector

```python
GCCollector(registry=REGISTRY)
```

Exports Python garbage collector statistics. Only active on CPython (skipped silently on
other implementations).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `registry` | `CollectorRegistry` | `REGISTRY` | Registry to register with. Pass `None` to skip registration. |

Metrics exported:

| Metric | Description |
|--------|-------------|
| `python_gc_objects_collected_total` | Objects collected during GC, by generation. |
| `python_gc_objects_uncollectable_total` | Uncollectable objects found during GC, by generation. |
| `python_gc_collections_total` | Number of times each generation was collected. |

The module-level `GC_COLLECTOR` is the default instance registered with `REGISTRY`.
