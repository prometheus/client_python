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
app.mount("/metrics", metrics_app)
```

For Multiprocessing support, use this modified code snippet. Full multiprocessing instructions are provided [here](https://prometheus.github.io/client_python/multiprocess/).

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app

app = FastAPI(debug=False)

# Using multiprocess collector for registry
def make_metrics_app():
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return make_asgi_app(registry=registry)


metrics_app = make_metrics_app()
app.mount("/metrics", metrics_app)
```

Run the example web application like this

```bash
# Install gunicorn if you do not have it
pip install gunicorn
# If using multiple workers, add `--workers n` parameter to the line below
gunicorn -b 127.0.0.1:8000 myapp:app -k uvicorn.workers.UvicornWorker
```

Visit http://localhost:8000/metrics to see the metrics
