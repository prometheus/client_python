from typing import Callable
from urllib.parse import parse_qs

from .exposition import _bake_output
from .registry import Collector, REGISTRY


def make_asgi_app(registry: Collector = REGISTRY, disable_compression: bool = False) -> Callable:
    """Create a ASGI app which serves the metrics from a registry."""

    async def prometheus_app(scope, receive, send):
        assert scope.get("type") == "http"
        # Prepare parameters
        params = parse_qs(scope.get('query_string', b'').decode("utf8"))
        accept_header = ",".join([
            value.decode("utf8") for (name, value) in scope.get('headers')
            if name.decode("utf8").lower() == 'accept'
        ])
        accept_encoding_header = ",".join([
            value.decode("utf8") for (name, value) in scope.get('headers')
            if name.decode("utf8").lower() == 'accept-encoding'
        ])
        method = scope.get('method', 'GET')
        path = scope.get('path', '')

        # Match make_wsgi_app: only GET serves metrics.
        if method == 'OPTIONS':
            status = '200 OK'
            headers = [('Allow', 'OPTIONS,GET')]
            output = b''
        elif method != 'GET':
            status = '405 Method Not Allowed'
            headers = [('Allow', 'OPTIONS,GET')]
            output = '# HTTP {}: {}; use OPTIONS or GET\n'.format(status, method).encode()
        elif path == '/favicon.ico':
            # Serve empty response for browsers
            status = '200 OK'
            headers = []
            output = b''
        else:
            # Note: For backwards compatibility, the URI path for GET is not
            # constrained to the documented /metrics, but any path is allowed.
            status, headers, output = _bake_output(registry, accept_header, accept_encoding_header, params, disable_compression)
        formatted_headers = []
        for header in headers:
            formatted_headers.append(tuple(x.encode('utf8') for x in header))
        # Return output
        payload = await receive()
        if payload.get("type") == "http.request":
            await send(
                {
                    "type": "http.response.start",
                    "status": int(status.split(' ')[0]),
                    "headers": formatted_headers,
                }
            )
            await send({"type": "http.response.body", "body": output})

    return prometheus_app
