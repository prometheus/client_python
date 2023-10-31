---
title: WSGI
weight: 2
---

To use Prometheus with [WSGI](http://wsgi.readthedocs.org/en/latest/), there is
`make_wsgi_app` which creates a WSGI application.

```python
from prometheus_client import make_wsgi_app
from wsgiref.simple_server import make_server

app = make_wsgi_app()
httpd = make_server('', 8000, app)
httpd.serve_forever()
```

Such an application can be useful when integrating Prometheus metrics with WSGI
apps.

The method `start_wsgi_server` can be used to serve the metrics through the
WSGI reference implementation in a new thread.

```python
from prometheus_client import start_wsgi_server

start_wsgi_server(8000)
```

By default, the WSGI application will respect `Accept-Encoding:gzip` headers used by Prometheus
and compress the response if such a header is present. This behaviour can be disabled by passing
`disable_compression=True` when creating the app, like this:

```python
app = make_wsgi_app(disable_compression=True)
```