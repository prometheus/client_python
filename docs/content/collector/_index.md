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