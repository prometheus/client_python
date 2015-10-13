from __future__ import absolute_import, unicode_literals
from .. import REGISTRY, generate_latest, CONTENT_TYPE_LATEST

from twisted.web.resource import Resource


class MetricsResource(Resource):
    """
    Twisted ``Resource`` that serves prometheus metrics.
    """
    isLeaf = True

    def __init__(self, registry=REGISTRY):
        self.registry = registry

    def render_GET(self, request):
        request.setHeader(b'Content-Type', CONTENT_TYPE_LATEST.encode('ascii'))
        return generate_latest(self.registry)
