---
title: ASGI
weight: 3
---

To use Prometheus with [ASGI](http://asgi.readthedocs.org/en/latest/), there is
`make_asgi_app` which creates an ASGI application.

```python
from prometheus_client import make_asgi_app

app = make_asgi_app()
```
Such an application can be useful when integrating Prometheus metrics with ASGI
apps.

By default, the WSGI application will respect `Accept-Encoding:gzip` headers used by Prometheus
and compress the response if such a header is present. This behaviour can be disabled by passing 
`disable_compression=True` when creating the app, like this:

```python
app = make_asgi_app(disable_compression=True)
```