---
title: Graphite
weight: 1
---

Metrics are pushed over TCP in the Graphite plaintext format.

```python
from prometheus_client.bridge.graphite import GraphiteBridge

gb = GraphiteBridge(('graphite.your.org', 2003))
# Push once.
gb.push()
# Push every 10 seconds in a daemon thread.
gb.start(10.0)
```

Graphite [tags](https://grafana.com/blog/2018/01/11/graphite-1.1-teaching-an-old-dog-new-tricks/) are also supported.

```python
from prometheus_client.bridge.graphite import GraphiteBridge

gb = GraphiteBridge(('graphite.your.org', 2003), tags=True)
c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
c.labels('get', '/').inc()
gb.push()
```