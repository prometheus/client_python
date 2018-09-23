from __future__ import absolute_import, unicode_literals
from .. import REGISTRY, exposition

import tornado.web


class MetricsHandler(tornado.web.RequestHandler):
    """
    Tornado ``Handler`` that serves prometheus metrics.
    """
    def initialize(self, registry=REGISTRY):
        self.registry = registry

    def get(self):
        encoder, content_type = exposition.choose_encoder(self.request.headers.get('Accept'))
        self.set_header('Content-Type', content_type)
        self.write(encoder(self.registry))
