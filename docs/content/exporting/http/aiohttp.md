---
title: AIOHTTP
weight: 6
---

To use Prometheus with a [AIOHTTP server](https://docs.aiohttp.org/en/stable/web.html),
there is `make_aiohttp_handler` which creates a handler.

```python
from aiohttp import web
from prometheus_client.aiohttp import make_aiohttp_handler

app = web.Application()
app.router.add_get("/metrics", make_aiohttp_handler())
```

By default, this handler will instruct AIOHTTP to automatically compress the
response if requested by the client. This behaviour can be disabled by passing
`disable_compression=True` when creating the app, like this:

```python
app.router.add_get("/metrics", make_aiohttp_handler(disable_compression=True))
```
