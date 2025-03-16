---
title: client_python
weight: 1
---

This tutorial shows the quickest way to get started with the Prometheus Python library.

**One**: Install the client:

```shell
pip install prometheus-client
```

**Two**: Paste the following into a Python interpreter:

```python
from prometheus_client import start_http_server, Summary
import random
import time

# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')

# Decorate function with metric.
@REQUEST_TIME.time()
def process_request(t):
    """A dummy function that takes some time."""
    time.sleep(t)

if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(8000)
    # Generate some requests.
    while True:
        process_request(random.random())
```

**Three**: Visit [http://localhost:8000/](http://localhost:8000/) to view the metrics.

From one easy to use decorator you get:

* `request_processing_seconds_count`: Number of times this function was called.
* `request_processing_seconds_sum`: Total amount of time spent in this function.

Prometheus's `rate` function allows calculation of both requests per second,
and latency over time from this data.

In addition if you're on Linux the `process` metrics expose CPU, memory and
other information about the process for free!
