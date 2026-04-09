---
title: Instrumenting
weight: 2
---

Six metric types are available. Pick based on what your value does:

| Type | Update model | Use for |
|------|-----------|---------|
| [Counter](counter/) | only up | requests served, errors, bytes sent |
| [Gauge](gauge/) | up and down | queue depth, active connections, memory usage |
| [Histogram](histogram/) | observations in buckets | request latency, request size — when you need quantiles in queries |
| [Summary](summary/) | observations (count + sum) | request latency, request size — when average is enough |
| [Info](info/) | static key-value pairs | build version, environment metadata |
| [Enum](enum/) | one of N states | task state, lifecycle phase |

See the Prometheus documentation on [metric types](https://prometheus.io/docs/concepts/metric_types/)
and [instrumentation best practices](https://prometheus.io/docs/practices/instrumentation/#counter-vs-gauge-summary-vs-histogram)
for deeper guidance on choosing between Histogram and Summary.

## Disabling `_created` metrics

By default counters, histograms, and summaries export an additional series
suffixed with `_created` and a value of the unix timestamp for when the metric
was created. If this information is not helpful, it can be disabled by setting
the environment variable `PROMETHEUS_DISABLE_CREATED_SERIES=True` or in code:
```python
from prometheus_client import disable_created_metrics
disable_created_metrics()
```
