from unittest import skipUnless

from prometheus_client import CollectorRegistry, Counter, generate_latest
from prometheus_client.openmetrics.exposition import ALLOWUTF8

try:
    import django
    from django.test import RequestFactory, TestCase

    from prometheus_client.django import PrometheusDjangoView

    HAVE_DJANGO = True
except ImportError:
    from unittest import TestCase

    HAVE_DJANGO = False

else:
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    'NAME': ':memory:'
                }
            },
            INSTALLED_APPS=[],
        )
        django.setup()


class MetricsResourceTest(TestCase):
    @skipUnless(HAVE_DJANGO, "Don't have django installed.")
    def setUp(self):
        self.registry = CollectorRegistry()
        self.factory = RequestFactory()

    def test_reports_metrics(self):
        c = Counter('cc', 'A counter', registry=self.registry)
        c.inc()

        request = self.factory.get("/metrics")

        response = PrometheusDjangoView.as_view(registry=self.registry)(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, generate_latest(self.registry, ALLOWUTF8))

    def test_restricted_registry(self):
        c = Counter('cc', 'A counter', registry=self.registry)
        c.inc()
        g = Counter('gg', 'Another counter', registry=self.registry)
        g.inc()

        request = self.factory.get("/metrics", {"name[]": ["cc_total"]})

        response = PrometheusDjangoView.as_view(registry=self.registry)(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content,
            generate_latest(self.registry.restricted_registry(["cc_total"]), ALLOWUTF8),
        )
        self.assertNotIn(b"gg_total", response.content)

    def test_restricted_registry_multiple_names(self):
        Counter('aa', 'A counter', registry=self.registry).inc()
        Counter('bb', 'B counter', registry=self.registry).inc()
        Counter('cc', 'C counter', registry=self.registry).inc()

        request = self.factory.get("/metrics", {"name[]": ["aa_total", "bb_total"]})

        response = PrometheusDjangoView.as_view(registry=self.registry)(request)
        self.assertIn(b"aa_total", response.content)
        self.assertIn(b"bb_total", response.content)
        self.assertNotIn(b"cc_total", response.content)
