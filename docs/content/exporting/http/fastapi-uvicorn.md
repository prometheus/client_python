---
title: FastAPI + Uvicorn
weight: 6
---

This guide demonstrates how to integrate Prometheus metrics into a [FastAPI](https://fastapi.tiangolo.com/) application using the native [Uvicorn](https://www.uvicorn.org/) ASGI server with production-ready multiprocess support.

### Basic Implementation
Save the following in a `myapp.py` file:

```python
import os
from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter, Gauge, CollectorRegistry, multiprocess
from fastapi.responses import JSONResponse
import psutil

app = FastAPI()

Define metrics with multiprocess aggregation
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests by endpoint",
    ["endpoint"],
    registry=CollectorRegistry()  # Isolated registry
)
CPU_USAGE = Gauge(
    "system_cpu_usage_percent",
    "Current CPU utilization percentage (aggregated)",
    multiprocess_mode='livesum'  # Critical for worker aggregation
)

def create_metrics_app():
    """Create multiprocess-aware metrics endpoint"""
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(
        registry,
        path=os.environ.get(  # Explicit path handling
            'PROMETHEUS_MULTIPROC_DIR', 
            '/tmp/prometheus'  # Fallback path
        )
    )
    return make_asgi_app(registry=registry)

Mount endpoint with trailing slash
app.mount("/metrics/", create_metrics_app())

@app.get("/")
async def home():
    REQUEST_COUNT.labels(endpoint="/").inc()
    CPU_USAGE.set(psutil.cpu_percent(interval=None))  # System-wide measurement
    return JSONResponse({"status": "ok"})
```

### Key Configuration
1. **Multiprocess Aggregation**  
   Required for gauge metrics in worker environments:
   ```python
   # Supported modes: livesum/max/liveall
   Gauge(..., multiprocess_mode='livesum')
   ```

2. **Registry Isolation**  
   Prevents metric conflicts between components:
   ```python
   REQUEST_COUNT = Counter(..., registry=CollectorRegistry())
   ```

### Running the Application
```bash
1. Install dependencies with psutil
pip install fastapi uvicorn prometheus-client psutil

2. Single-process mode (development)
uvicorn myapp:app --port 8000

3. Multiprocess mode (production)
export PROMETHEUS_MULTIPROC_DIR=./metrics_data  # Persistent storage
mkdir -p $PROMETHEUS_MULTIPROC_DIR
uvicorn myapp:app --port 8000 --workers 4

4. Generate load for verification
for i in {1..100}; do curl -s http://localhost:8000/ & done

5. Verify aggregated metrics
curl -s http://localhost:8000/metrics/ | grep -E 'http_requests_total|system_cpu_usage_percent'
```

### Expected Output
```text
TYPE http_requests_total counter
http_requests_total{endpoint="/"} 100.0

TYPE system_cpu_usage_percent gauge
system_cpu_usage_percent 68.5  # Aggregated across workers
```

### Production Checklist
1. **Directory Configuration**  
   ```bash
   chmod 750 ./metrics_data  # Secure write permissions
   ```
2. **Storage Management**  
   - Use dedicated volume for `PROMETHEUS_MULTIPROC_DIR`
   - Implement cleanup cron job:
     ```bash
     0 * * * * find /path/to/metrics_data -name '*.db' -mtime +7 -delete
     ```
3. **Validation Tools**  
   ```bash
   # Check active worker count
   ps aux | grep -c '[u]vicorn.*worker'

   # Monitor data files
   watch -n 5 'ls -lh $PROMETHEUS_MULTIPROC_DIR | grep .db'
   ```

### Troubleshooting
| Symptom                | Solution                      | Verification Command             |
|------------------------|-------------------------------|-----------------------------------|
| PID labels in metrics  | Add `multiprocess_mode` param | `grep 'multiprocess_mode' myapp.py` |
| Missing .db files      | Check directory permissions   | `ls -ld $PROMETHEUS_MULTIPROC_DIR` |
| Stale values           | Verify endpoint activation    | `curl -I http://localhost:8000/`   |
