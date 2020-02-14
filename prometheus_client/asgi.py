from urllib.parse import parse_qs

from .exposition import choose_encoder
from .registry import REGISTRY


def make_asgi_app(registry=REGISTRY):
    """Create a ASGI app which serves the metrics from a registry."""

    async def prometheus_app(scope, receive, send):
        assert scope.get("type") == "http"
        params = parse_qs(scope.get('query_string', b''))
        r = registry
        accept_header = "Accept: " + ",".join([
            value.decode("utf8") for (name, value) in scope.get('headers')
            if name.decode("utf8") == 'accept'
        ])
        encoder, content_type = choose_encoder(accept_header)
        if 'name[]' in params:
            r = r.restricted_registry(params['name[]'])
        output = encoder(r)

        payload = await receive()
        if payload.get("type") == "http.request":
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"Content-Type", content_type.encode('utf8')]],
                }
            )
            await send({"type": "http.response.body", "body": output})

    return prometheus_app
