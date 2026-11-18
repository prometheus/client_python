---
title: Celery
weight: 60
---

## Celery

When using Celery, a common approach is to instrument tasks with `prometheus_client` metrics and expose them via a small sidecar exporter process on each node. Prometheus scrapes the sidecar HTTP endpoint.

This keeps metric exporting independent from Django/FastAPI and avoids relying on any web server running inside the Celery worker process.

### 1) Instrument Celery tasks

Define metrics in a module that is imported by your Celery app/tasks:

```python
from prometheus_client import Counter

CELERY_TASKS_TOTAL = Counter(
    "celery_tasks_total",
    "Total number of Celery tasks processed",
    ["task_name", "status"],
)
```

Update them from tasks:

```python
from celery import shared_task
from .metrics import CELERY_TASKS_TOTAL

@shared_task(bind=True)
def example_task(self, *args, **kwargs):
    try:
        # ... task logic ...
        CELERY_TASKS_TOTAL.labels(task_name=self.name, status="success").inc()
    except Exception:
        CELERY_TASKS_TOTAL.labels(task_name=self.name, status="failure").inc()
        raise
```

### 2) Run a sidecar exporter

Run a small process alongside your Celery workers to expose `/metrics`:

```python
from prometheus_client import start_http_server
import time

def main():
    # Expose metrics on http://0.0.0.0:8000/metrics
    start_http_server(8000, addr="0.0.0.0")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
```

Start this exporter on each node (e.g. as a systemd service, container sidecar, or process supervisor entry).

### Notes

- The exporter process does not depend on Django/FastAPI; it simply exposes metrics from the same Python environment where task code runs.
- If you run Celery with multiple worker processes and need aggregation across processes, see [Multiprocess mode]({{< ref "/multiprocess" >}}) and use a dedicated `PROMETHEUS_MULTIPROC_DIR`.