import unittest

from prometheus_client import Counter, CollectorRegistry
from prometheus_client.bridge.newrelic import PrometheusDataSource


class TestPrometheusDataSource(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()

    def get_metrics(self, additional_settings=None):
        settings = {'registry': self.registry}
        if additional_settings:
            settings.update(additional_settings)

        wrapped_data_source = PrometheusDataSource(settings=settings)
        factory = wrapped_data_source['factory']
        data_source = factory(environ={})
        return list(data_source())

    def test_nolabels(self):
        counter = Counter('c', 'help', registry=self.registry)
        counter.inc()

        metrics = self.get_metrics()
        self.assertEqual([('Custom/c', 1.0)], metrics)

    def test_labels(self):
        labels = Counter('labels', 'help', ['a', 'b'], registry=self.registry)
        labels.labels('c', 'd').inc()

        metrics = self.get_metrics()
        self.assertEqual([('Custom/labels.a.c.b.d', 1.0)], metrics)

    def test_prefix(self):
        labels = Counter('labels', 'help', ['a', 'b'], registry=self.registry)
        labels.labels('c', 'd').inc()

        metrics = self.get_metrics(additional_settings={'prefix': 'pre.fix'})
        self.assertEqual([('Custom/pre.fix.labels.a.c.b.d', 1.0)], metrics)
