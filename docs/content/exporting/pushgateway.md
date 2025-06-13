---
title: Pushgateway
weight: 3
---

The [Pushgateway](https://github.com/prometheus/pushgateway)
allows ephemeral and batch jobs to expose their metrics to Prometheus.
Since Prometheus may not be able to scrape such a target, the targets can
push their metrics to a separate instance of the Pushgateway,
which then exposes these metrics to Prometheus.

```python
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

registry = CollectorRegistry()
g = Gauge('job_last_success_unixtime', 'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
push_to_gateway('localhost:9091', job='batchA', registry=registry)
```

A separate registry is used, as the default registry may contain other metrics
such as those from the Process Collector.

Pushgateway functions take a grouping key.
1. `push_to_gateway` replaces metrics
with the same grouping key.
2. `pushadd_to_gateway` only replaces metrics with the
same name and grouping key.
3. `delete_from_gateway` deletes metrics with the
given job and grouping key.
4. `instance_ip_grouping_key` returns a grouping key with the instance label set
to the host's IP address.

See the
[Pushgateway documentation](https://github.com/prometheus/pushgateway/blob/master/README.md)
for more information.

# Handlers for authentication

If the push gateway you are connecting to is protected with HTTP Basic Auth,
you can use a special handler to set the Authorization header.

```python
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from prometheus_client.exposition import basic_auth_handler

def my_auth_handler(url, method, timeout, headers, data):
    username = 'foobar'
    password = 'secret123'
    return basic_auth_handler(url, method, timeout, headers, data, username, password)
registry = CollectorRegistry()
g = Gauge('job_last_success_unixtime', 'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
push_to_gateway('localhost:9091', job='batchA', registry=registry, handler=my_auth_handler)
```

TLS Auth is also supported when using the push gateway with a special handler.

```python
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from prometheus_client.exposition import tls_auth_handler


def my_auth_handler(url, method, timeout, headers, data):
    certfile = 'client-crt.pem'
    keyfile = 'client-key.pem'
    return tls_auth_handler(url, method, timeout, headers, data, certfile, keyfile)

registry = CollectorRegistry()
g = Gauge('job_last_success_unixtime', 'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
push_to_gateway('localhost:9091', job='batchA', registry=registry, handler=my_auth_handler)
```
