---
title: FastAPI + Gunicorn
weight: 5
---

To use Prometheus with [FastAPI](https://fastapi.tiangolo.com/) and [Gunicorn](https://gunicorn.org/) we need to serve metrics through a Prometheus ASGI application.

Save the snippet below in a `myapp.py` file

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app

# Create app
app = FastAPI(debug=False)

# Add prometheus asgi middleware to route /metrics requests
metrics_app = make_asgi_app()
app.add_route("/metrics", metrics_app)
```

`add_route` serves the metrics at exactly `/metrics`. Alternatively, the app can
be mounted with `app.mount("/metrics", metrics_app)`. A mount is a path prefix,
so FastAPI serves the metrics at `/metrics/` and redirects requests for
`/metrics` there with a `307 Temporary Redirect`.

Using `make_asgi_app()` with `add_route` requires a `prometheus_client` release
newer than 0.26.0. On 0.26.0 and earlier, `add_route` fails with a `TypeError`,
so use `app.mount("/metrics", metrics_app)` instead.

For Multiprocessing support, use this modified code snippet. Full multiprocessing instructions are provided [here]({{< ref "/multiprocess" >}}).

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app, CollectorRegistry, multiprocess

app = FastAPI(debug=False)

# Using multiprocess collector for registry
def make_metrics_app():
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return make_asgi_app(registry=registry)


metrics_app = make_metrics_app()
app.add_route("/metrics", metrics_app)
```

Run the example web application like this

```bash
# Install gunicorn if you do not have it
pip install gunicorn
# If using multiple workers, add `--workers n` parameter to the line below
gunicorn -b 127.0.0.1:8000 myapp:app -k uvicorn.workers.UvicornWorker
```

Visit http://localhost:8000/metrics to see the metrics
