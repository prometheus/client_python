---
title: Extra Options
weight: 7
---

# Labels

All metrics can have labels, allowing grouping of related time series.

See the best practices on [naming](http://prometheus.io/docs/practices/naming/)
and [labels](http://prometheus.io/docs/practices/instrumentation/#use-labels).

Taking a counter as an example:

```python
from prometheus_client import Counter
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels('get', '/').inc()
c.labels('post', '/submit').inc()
```

Labels can also be passed as keyword-arguments:

```python
from prometheus_client import Counter
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels(method='get', endpoint='/').inc()
c.labels(method='post', endpoint='/submit').inc()
```

Metrics with labels are not initialized when declared, because the client can't
know what values the label can have. It is recommended to initialize the label
values by calling the `.labels()` method alone:

```python
from prometheus_client import Counter
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels('get', '/')
c.labels('post', '/submit')
```

# Exemplars

Exemplars can be added to counter and histogram metrics. Exemplars can be
specified by passing a dict of label value pairs to be exposed as the exemplar.
For example with a counter:

```python
from prometheus_client import Counter
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels('get', '/').inc(exemplar={'trace_id': 'abc123'})
c.labels('post', '/submit').inc(1.0, {'trace_id': 'def456'})
```

And with a histogram:

```python
from prometheus_client import Histogram
h = Histogram('request_latency_seconds', 'Description of histogram')
h.observe(4.7, {'trace_id': 'abc123'})
```

Exemplars are only rendered in the OpenMetrics exposition format. If using the
HTTP server or apps in this library, content negotiation can be used to specify
OpenMetrics (which is done by default in Prometheus). Otherwise it will be
necessary to use `generate_latest` from
`prometheus_client.openmetrics.exposition` to view exemplars.

To view exemplars in Prometheus it is also necessary to enable the the
exemplar-storage feature flag:
```
--enable-feature=exemplar-storage
```
Additional information is available in [the Prometheus
documentation](https://prometheus.io/docs/prometheus/latest/feature_flags/#exemplars-storage).

# Disabling `_created` metrics

By default counters, histograms, and summaries export an additional series
suffixed with `_created` and a value of the unix timestamp for when the metric
was created. If this information is not helpful, it can be disabled by setting
the environment variable `PROMETHEUS_DISABLE_CREATED_SERIES=True`.