---
title: Instrumenting
weight: 2
---

Four types of metric are offered: Counter, Gauge, Summary and Histogram.
See the documentation on [metric types](http://prometheus.io/docs/concepts/metric_types/)
and [instrumentation best practices](https://prometheus.io/docs/practices/instrumentation/#counter-vs-gauge-summary-vs-histogram)
on how to use them.

## Disabling `_created` metrics

By default counters, histograms, and summaries export an additional series
suffixed with `_created` and a value of the unix timestamp for when the metric
was created. If this information is not helpful, it can be disabled by setting
the environment variable `PROMETHEUS_DISABLE_CREATED_SERIES=True`.