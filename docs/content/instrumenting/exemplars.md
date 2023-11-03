---
title: Exemplars
weight: 8
---

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
