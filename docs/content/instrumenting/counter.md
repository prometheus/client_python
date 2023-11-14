---
title: Counter
weight: 1
---

Counters go up, and reset when the process restarts.


```python
from prometheus_client import Counter
c = Counter('my_failures', 'Description of counter')
c.inc()     # Increment by 1
c.inc(1.6)  # Increment by given value
```

If there is a suffix of `_total` on the metric name, it will be removed. When
exposing the time series for counter, a `_total` suffix will be added. This is
for compatibility between OpenMetrics and the Prometheus text format, as OpenMetrics
requires the `_total` suffix.

There are utilities to count exceptions raised:

```python
@c.count_exceptions()
def f():
  pass

with c.count_exceptions():
  pass

# Count only one type of exception
with c.count_exceptions(ValueError):
  pass
```