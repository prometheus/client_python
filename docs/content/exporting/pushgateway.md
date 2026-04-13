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

# Compressing data before sending to pushgateway
Pushgateway (version >= 1.5.0) supports gzip and snappy compression (v > 1.6.0). This can help in network constrained environments.
To compress a push request, set the `compression` argument to `'gzip'` or `'snappy'`:
```python
push_to_gateway(
    'localhost:9091',
    job='batchA',
    registry=registry,
    handler=my_auth_handler,
    compression='gzip',
)
```
Snappy compression requires the optional [`python-snappy`](https://github.com/andrix/python-snappy) package.

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

## API Reference

### `push_to_gateway(gateway, job, registry, grouping_key=None, timeout=30, handler=default_handler, compression=None)`

Pushes metrics to the pushgateway, replacing all metrics with the same job and grouping key.
Uses the HTTP `PUT` method.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gateway` | `str` | required | URL of the pushgateway. If no scheme is provided, `http://` is assumed. |
| `job` | `str` | required | Value for the `job` label attached to all pushed metrics. |
| `registry` | `Collector` | required | Registry whose metrics are pushed. Typically a `CollectorRegistry` instance. |
| `grouping_key` | `Optional[Dict[str, Any]]` | `None` | Additional labels to identify the group. See the [Pushgateway documentation](https://github.com/prometheus/pushgateway/blob/master/README.md) for details. |
| `timeout` | `Optional[float]` | `30` | Seconds before the request is aborted. Pass `None` for no timeout. |
| `handler` | `Callable` | `default_handler` | Function that performs the HTTP request. See [Handlers](#handlers) below. |
| `compression` | `Optional[str]` | `None` | Compress the payload before sending. Accepts `'gzip'` or `'snappy'`. Snappy requires the [`python-snappy`](https://github.com/andrix/python-snappy) package. |

### `pushadd_to_gateway(gateway, job, registry, grouping_key=None, timeout=30, handler=default_handler, compression=None)`

Pushes metrics to the pushgateway, replacing only metrics with the same name, job, and grouping key.
Uses the HTTP `POST` method.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gateway` | `str` | required | URL of the pushgateway. |
| `job` | `str` | required | Value for the `job` label attached to all pushed metrics. |
| `registry` | `Optional[Collector]` | required | Registry whose metrics are pushed. Pass `None` to use the default `REGISTRY`. |
| `grouping_key` | `Optional[Dict[str, Any]]` | `None` | Additional labels to identify the group. |
| `timeout` | `Optional[float]` | `30` | Seconds before the request is aborted. Pass `None` for no timeout. |
| `handler` | `Callable` | `default_handler` | Function that performs the HTTP request. |
| `compression` | `Optional[str]` | `None` | Compress the payload. Accepts `'gzip'` or `'snappy'`. |

### `delete_from_gateway(gateway, job, grouping_key=None, timeout=30, handler=default_handler)`

Deletes metrics from the pushgateway for the given job and grouping key.
Uses the HTTP `DELETE` method. Has no `registry` or `compression` parameters.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gateway` | `str` | required | URL of the pushgateway. |
| `job` | `str` | required | Value for the `job` label identifying the group to delete. |
| `grouping_key` | `Optional[Dict[str, Any]]` | `None` | Additional labels to identify the group. |
| `timeout` | `Optional[float]` | `30` | Seconds before the request is aborted. Pass `None` for no timeout. |
| `handler` | `Callable` | `default_handler` | Function that performs the HTTP request. |

### `instance_ip_grouping_key()`

Returns a grouping key dict with the `instance` label set to the IP address of the current host.
Takes no parameters.

```python
from prometheus_client.exposition import instance_ip_grouping_key

push_to_gateway('localhost:9091', job='batchA', registry=registry,
                grouping_key=instance_ip_grouping_key())
```

## Handlers

A handler is a callable with the signature:

```python
def my_handler(url, method, timeout, headers, data):
    # url: str — full request URL
    # method: str — HTTP method (PUT, POST, DELETE)
    # timeout: Optional[float] — seconds before aborting, or None
    # headers: List[Tuple[str, str]] — HTTP headers to include
    # data: bytes — request body
    ...
    return callable_that_performs_the_request
```

The handler must return a no-argument callable that performs the actual HTTP request and raises
an exception (e.g. `IOError`) on failure. Three built-in handlers are available in
`prometheus_client.exposition`:

### `default_handler`

Standard HTTP/HTTPS handler. Used by default in all push functions.

### `basic_auth_handler(url, method, timeout, headers, data, username=None, password=None)`

Wraps `default_handler` and adds an HTTP Basic Auth header.

| Extra parameter | Type | Default | Description |
|----------------|------|---------|-------------|
| `username` | `Optional[str]` | `None` | HTTP Basic Auth username. |
| `password` | `Optional[str]` | `None` | HTTP Basic Auth password. |

### `tls_auth_handler(url, method, timeout, headers, data, certfile, keyfile, cafile=None, protocol=ssl.PROTOCOL_TLS_CLIENT, insecure_skip_verify=False)`

Performs the request over HTTPS using TLS client certificate authentication.

| Extra parameter | Type | Default | Description |
|----------------|------|---------|-------------|
| `certfile` | `str` | required | Path to the client certificate PEM file. |
| `keyfile` | `str` | required | Path to the client private key PEM file. |
| `cafile` | `Optional[str]` | `None` | Path to a CA certificate file for server verification. Uses system defaults if not set. |
| `protocol` | `int` | `ssl.PROTOCOL_TLS_CLIENT` | SSL/TLS protocol version. |
| `insecure_skip_verify` | `bool` | `False` | Skip server certificate verification. Use only in controlled environments. |

### `passthrough_redirect_handler`

Like `default_handler` but automatically follows redirects for all HTTP methods, including `PUT`
and `POST`. Use only when you control or trust the source of redirect responses.
