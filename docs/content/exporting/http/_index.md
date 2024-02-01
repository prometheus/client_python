---
title: HTTP/HTTPS
weight: 1
---

# HTTP

Metrics are usually exposed over HTTP, to be read by the Prometheus server.

The easiest way to do this is via `start_http_server`, which will start a HTTP
server in a daemon thread on the given port:

```python
from prometheus_client import start_http_server

start_http_server(8000)
```

Visit [http://localhost:8000/](http://localhost:8000/) to view the metrics.

The function will return the HTTP server and thread objects, which can be used
to shutdown the server gracefully:

```python
server, t = start_http_server(8000)
server.shutdown()
t.join()
```

To add Prometheus exposition to an existing HTTP server, see the `MetricsHandler` class
which provides a `BaseHTTPRequestHandler`. It also serves as a simple example of how
to write a custom endpoint.

# HTTPS

By default, the prometheus client will accept only HTTP requests from Prometheus.
To enable HTTPS, `certfile` and `keyfile` need to be provided. The certificate is
presented to Prometheus as a server certificate during the TLS handshake, and
the private key in the key file must belong to the public key in the certificate.

When HTTPS is enabled, you can enable mutual TLS (mTLS) by setting `client_auth_required=True`
(i.e. Prometheus is required to present a client certificate during TLS handshake) and the
client certificate including its hostname is validated against the CA certificate chain.

`client_cafile` can be used to specify a certificate file containing a CA certificate
chain that is used to validate the client certificate. `client_capath` can be used to
specify a certificate directory containing a CA certificate chain that is used to
validate the client certificate. If neither of them is provided, a default CA certificate
chain is used (see Python [ssl.SSLContext.load_default_certs()](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.load_default_certs))

```python
from prometheus_client import start_http_server

start_http_server(8000, certfile="server.crt", keyfile="server.key")
```