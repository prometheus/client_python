---
title: Twisted
weight: 1
---

To use prometheus with [twisted](https://twistedmatrix.com/), there is `MetricsResource` which exposes metrics as a twisted resource.

```python
from prometheus_client.twisted import MetricsResource
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor

root = Resource()
root.putChild(b'metrics', MetricsResource())

factory = Site(root)
reactor.listenTCP(8000, factory)
reactor.run()
```