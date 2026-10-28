from typing import Callable
from urllib.parse import parse_qs

from .exposition import _bake_output
from .registry import Collector, REGISTRY


class _ASGIApp:
    """ASGI application object wrapping the metrics handler.

    Frameworks such as Starlette and FastAPI treat a plain function passed to
    ``add_route`` as a ``request -> response`` endpoint, but any other callable
    as a raw ASGI application. Returning an instance rather than a bare
    function allows ``app.add_route("/metrics", make_asgi_app())`` to serve
    metrics at ``/metrics`` exactly, without the trailing-slash redirect that
    ``app.mount("/metrics", ...)`` produces.
    """

    def __init__(self, app: Callable) -> None:
        self._app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        await self._app(scope, receive, send)


def make_asgi_app(registry: Collector = REGISTRY, disable_compression: bool = False) -> Callable:
    """Create a ASGI app which serves the metrics from a registry."""

    async def prometheus_app(scope, receive, send):
        assert scope.get("type") == "http"
        # Prepare parameters
        params = parse_qs(scope.get('query_string', b'').decode("utf8"))
        accept_header = ",".join([
            value for (name, value) in scope.get('headers')
            if name.lower() == 'accept'
        ])
        accept_encoding_header = ",".join([
            value for (name, value) in scope.get('headers')
            if name.lower() == 'accept-encoding'
        ])
        # Bake output
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

    return _ASGIApp(prometheus_app)
