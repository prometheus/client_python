---
title: Parser
weight: 6
---

The Python client supports parsing the Prometheus text format.
This is intended for advanced use cases where you have servers
exposing Prometheus metrics and need to get them into some other
system.

```python
from prometheus_client.parser import text_string_to_metric_families
for family in text_string_to_metric_families(u"my_gauge 1.0\n"):
  for sample in family.samples:
    print("Name: {0} Labels: {1} Value: {2}".format(*sample))
```