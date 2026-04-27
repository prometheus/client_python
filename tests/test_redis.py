import os
import unittest
from collections.abc import Sequence
from typing import Any

import pytest

from prometheus_client import values
from prometheus_client.core import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Sample,
    Summary,
)
from prometheus_client.redis_collector import redis_client, RedisCollector
from prometheus_client.values import MutexValue, RedisValue, Value

pytest.importorskip("redis")

from redis import Redis

class RedisTestCase(unittest.TestCase):
    redis: Redis

    def setUp(self) -> None:
        os.environ["PROMETHEUS_REDIS_URL"] = "redis://localhost/1"
        client = redis_client()
        if client.keys() != []:
            raise pytest.skip(
                "Redis database 1 has existing data. Refusing to clobber it."
            )
        values.ValueClass = RedisValue()

    def tearDown(self) -> None:
        redis_client().flushdb()
        del os.environ["PROMETHEUS_REDIS_URL"]
        values.ValueClass = MutexValue


class ValueTestCase(RedisTestCase):
    def create_value(
        self,
        metric_name: str,
        name: str | None = None,
        type_: str = "counter",
        labelnames: list[str] | None = None,
        labelvalues: list[str] | None = None,
    ) -> Value:
        return values.ValueClass(
            type_,
            metric_name,
            name or metric_name + "_total",
            labelnames or [],
            labelvalues or [],
            "Help Text",
        )

    def test_initializes_value(self) -> None:
        value = self.create_value("test1")
        self.assertEqual(value.get(), 0.0)

    def test_sets_and_gets_value(self) -> None:
        value = self.create_value("test2")
        value.set(5)
        self.assertEqual(value.get(), 5.0)

    def test_inc_value(self) -> None:
        value = self.create_value("test3")
        value.inc(3)
        value.inc(5)
        self.assertEqual(value.get(), 8.0)

    def test_differentiated_by_name(self) -> None:
        v1 = self.create_value("value1")
        v2 = self.create_value("value2")
        v1.set(1)
        v2.set(2)
        self.assertEqual(v1.get(), 1.0)
        self.assertEqual(v2.get(), 2.0)

    def test_differentiated_by_labels(self) -> None:
        v1 = self.create_value("value3", labelnames=["a"], labelvalues=["1"])
        v2 = self.create_value("value3", labelnames=["a"], labelvalues=["2"])
        v1.set(1)
        v2.set(2)
        self.assertEqual(v1.get(), 1.0)
        self.assertEqual(v2.get(), 2.0)


class TestRedis(RedisTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.registry = CollectorRegistry(support_collectors_without_names=True)
        self.collector = RedisCollector(self.registry)

    def test_counter_adds(self) -> None:
        c1 = Counter("c", "help", registry=None)
        c2 = Counter("c", "help", registry=None)
        self.assertEqual(0, self.registry.get_sample_value("c_total"))
        c1.inc(1)
        c2.inc(2)
        self.assertEqual(3, self.registry.get_sample_value("c_total"))

    def test_summary_adds(self) -> None:
        s1 = Summary("s", "help", registry=None)
        s2 = Summary("s", "help", registry=None)
        self.assertEqual(0, self.registry.get_sample_value("s_count"))
        self.assertEqual(0, self.registry.get_sample_value("s_sum"))
        s1.observe(1)
        s2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value("s_count"))
        self.assertEqual(3, self.registry.get_sample_value("s_sum"))

    def test_histogram_adds(self) -> None:
        h1 = Histogram("h", "help", registry=None)
        h2 = Histogram("h", "help", registry=None)
        self.assertEqual(0, self.registry.get_sample_value("h_count"))
        self.assertEqual(0, self.registry.get_sample_value("h_sum"))
        self.assertEqual(0, self.registry.get_sample_value("h_bucket", {"le": "5.0"}))
        h1.observe(1)
        h2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value("h_count"))
        self.assertEqual(3, self.registry.get_sample_value("h_sum"))
        self.assertEqual(2, self.registry.get_sample_value("h_bucket", {"le": "5.0"}))

    def test_namespace_subsystem(self) -> None:
        c1 = Counter("c", "help", registry=None, namespace="ns", subsystem="ss")
        c1.inc(1)
        self.assertEqual(1, self.registry.get_sample_value("ns_ss_c_total"))

    def test_collect(self) -> None:
        labels = {i: i for i in "abcd"}

        def add_label(key: str, value: str) -> dict[str, str]:
            l = labels.copy()
            l[key] = value
            return l

        c = Counter("c", "help", labelnames=labels.keys(), registry=None)
        g = Gauge("g", "help", labelnames=labels.keys(), registry=None)
        h = Histogram("h", "help", labelnames=labels.keys(), registry=None)

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)
        h.labels(**labels).observe(1)

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)
        h.labels(**labels).observe(5)

        metrics = {m.name: m for m in self.collector.collect()}

        self.assertEqual(metrics["c"].samples, [Sample("c_total", labels, 2.0)])

        expected_histogram = [
            Sample("h_bucket", add_label("le", "0.005"), 0.0),
            Sample("h_bucket", add_label("le", "0.01"), 0.0),
            Sample("h_bucket", add_label("le", "0.025"), 0.0),
            Sample("h_bucket", add_label("le", "0.05"), 0.0),
            Sample("h_bucket", add_label("le", "0.075"), 0.0),
            Sample("h_bucket", add_label("le", "0.1"), 0.0),
            Sample("h_bucket", add_label("le", "0.25"), 0.0),
            Sample("h_bucket", add_label("le", "0.5"), 0.0),
            Sample("h_bucket", add_label("le", "0.75"), 0.0),
            Sample("h_bucket", add_label("le", "1.0"), 1.0),
            Sample("h_bucket", add_label("le", "2.5"), 1.0),
            Sample("h_bucket", add_label("le", "5.0"), 2.0),
            Sample("h_bucket", add_label("le", "7.5"), 2.0),
            Sample("h_bucket", add_label("le", "10.0"), 2.0),
            Sample("h_bucket", add_label("le", "+Inf"), 2.0),
            Sample("h_count", labels, 2.0),
            Sample("h_sum", labels, 6.0),
        ]

        self.assertEqual(metrics["h"].samples, expected_histogram)

    def test_collect_histogram_ordering(self) -> None:
        labels = {i: i for i in "abcd"}

        def add_label(key: str, value: str) -> dict[str, str]:
            l = labels.copy()
            l[key] = value
            return l

        h = Histogram("h", "help", labelnames=["view"], registry=None)

        h.labels(view="view1").observe(1)

        h.labels(view="view1").observe(5)
        h.labels(view="view2").observe(1)

        metrics = {m.name: m for m in self.collector.collect()}

        expected_histogram = [
            Sample("h_bucket", {"view": "view1", "le": "0.005"}, 0.0),
            Sample("h_bucket", {"view": "view1", "le": "0.01"}, 0.0),
            Sample("h_bucket", {"view": "view1", "le": "0.025"}, 0.0),
            Sample("h_bucket", {"view": "view1", "le": "0.05"}, 0.0),
            Sample("h_bucket", {"view": "view1", "le": "0.075"}, 0.0),
            Sample("h_bucket", {"view": "view1", "le": "0.1"}, 0.0),
            Sample("h_bucket", {"view": "view1", "le": "0.25"}, 0.0),
            Sample("h_bucket", {"view": "view1", "le": "0.5"}, 0.0),
            Sample("h_bucket", {"view": "view1", "le": "0.75"}, 0.0),
            Sample("h_bucket", {"view": "view1", "le": "1.0"}, 1.0),
            Sample("h_bucket", {"view": "view1", "le": "2.5"}, 1.0),
            Sample("h_bucket", {"view": "view1", "le": "5.0"}, 2.0),
            Sample("h_bucket", {"view": "view1", "le": "7.5"}, 2.0),
            Sample("h_bucket", {"view": "view1", "le": "10.0"}, 2.0),
            Sample("h_bucket", {"view": "view1", "le": "+Inf"}, 2.0),
            Sample("h_count", {"view": "view1"}, 2.0),
            Sample("h_sum", {"view": "view1"}, 6.0),
            Sample("h_bucket", {"view": "view2", "le": "0.005"}, 0.0),
            Sample("h_bucket", {"view": "view2", "le": "0.01"}, 0.0),
            Sample("h_bucket", {"view": "view2", "le": "0.025"}, 0.0),
            Sample("h_bucket", {"view": "view2", "le": "0.05"}, 0.0),
            Sample("h_bucket", {"view": "view2", "le": "0.075"}, 0.0),
            Sample("h_bucket", {"view": "view2", "le": "0.1"}, 0.0),
            Sample("h_bucket", {"view": "view2", "le": "0.25"}, 0.0),
            Sample("h_bucket", {"view": "view2", "le": "0.5"}, 0.0),
            Sample("h_bucket", {"view": "view2", "le": "0.75"}, 0.0),
            Sample("h_bucket", {"view": "view2", "le": "1.0"}, 1.0),
            Sample("h_bucket", {"view": "view2", "le": "2.5"}, 1.0),
            Sample("h_bucket", {"view": "view2", "le": "5.0"}, 1.0),
            Sample("h_bucket", {"view": "view2", "le": "7.5"}, 1.0),
            Sample("h_bucket", {"view": "view2", "le": "10.0"}, 1.0),
            Sample("h_bucket", {"view": "view2", "le": "+Inf"}, 1.0),
            Sample("h_count", {"view": "view2"}, 1.0),
            Sample("h_sum", {"view": "view2"}, 1.0),
        ]

        self.assertEqual(metrics["h"].samples, expected_histogram)

    def test_restrict(self) -> None:
        labels = {i: i for i in "abcd"}

        def add_label(key: str, value: str) -> dict[str, str]:
            l = labels.copy()
            l[key] = value
            return l

        c = Counter("c", "help", labelnames=labels.keys(), registry=None)
        g = Gauge("g", "help", labelnames=labels.keys(), registry=None)

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)

        metrics = {
            m.name: m for m in self.registry.restricted_registry(["c_total"]).collect()
        }

        self.assertEqual(metrics.keys(), {"c"})

        self.assertEqual(metrics["c"].samples, [Sample("c_total", labels, 2.0)])

    def test_collect_preserves_help(self) -> None:
        labels = {i: i for i in "abcd"}

        c = Counter("c", "c help", labelnames=labels.keys(), registry=None)
        g = Gauge("g", "g help", labelnames=labels.keys(), registry=None)
        h = Histogram("h", "h help", labelnames=labels.keys(), registry=None)

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)
        h.labels(**labels).observe(1)

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)
        h.labels(**labels).observe(5)

        metrics = {m.name: m for m in self.collector.collect()}

        self.assertEqual(metrics["c"].documentation, "c help")
        self.assertEqual(metrics["g"].documentation, "g help")
        self.assertEqual(metrics["h"].documentation, "h help")

    def test_child_name_is_built_once_with_namespace_subsystem_unit(self) -> None:
        """
        Repro for #1035:
        In multiprocess mode, child metrics must NOT rebuild the full name
        (namespace/subsystem/unit) a second time. The exported family name should
        be built once, and Counter samples should use "<family>_total".
        """
        from prometheus_client import Counter

        class CustomCounter(Counter):
            def __init__(
                self,
                name: str,
                documentation: str,
                labelnames: Sequence[str] = (),
                namespace: str = "mydefaultnamespace",
                subsystem: str = "mydefaultsubsystem",
                unit: str = "",
                registry: CollectorRegistry | None = None,
                _labelvalues: Sequence[str] | None = None,
            ):
                # Intentionally provide non-empty defaults to trigger the bug path.
                super().__init__(
                    name=name,
                    documentation=documentation,
                    labelnames=labelnames,
                    namespace=namespace,
                    subsystem=subsystem,
                    unit=unit,
                    registry=registry,
                    _labelvalues=_labelvalues,
                )

        # Create a Counter with explicit namespace/subsystem/unit
        c = CustomCounter(
            name="m",
            documentation="help",
            labelnames=("status", "method"),
            namespace="ns",
            subsystem="ss",
            unit="seconds",  # avoid '_total_total' confusion
            registry=None,  # not registered in local registry in multiprocess mode
        )

        # Create two labeled children
        c.labels(status="200", method="GET").inc()
        c.labels(status="404", method="POST").inc()

        # Collect from the multiprocess collector initialized in setUp()
        metrics = {m.name: m for m in self.collector.collect()}

        # Family name should be built once (no '_total' in family name)
        expected_family = "ns_ss_m_seconds"
        self.assertIn(expected_family, metrics, f"missing family {expected_family}")

        # Counter samples must use '<family>_total'
        mf = metrics[expected_family]
        sample_names = {s.name for s in mf.samples}
        self.assertTrue(
            all(name == expected_family + "_total" for name in sample_names),
            f"unexpected sample names: {sample_names}",
        )

        # Ensure no double-built prefix sneaks in (the original bug)
        bad_prefix = "mydefaultnamespace_mydefaultsubsystem_"
        all_names = {mf.name, *sample_names}
        self.assertTrue(
            all(not n.startswith(bad_prefix) for n in all_names),
            f"found double-built name(s): {[n for n in all_names if n.startswith(bad_prefix)]}",
        )

    def test_child_preserves_parent_context_for_subclasses(self) -> None:
        """
        Ensure child metrics preserve parent's namespace/subsystem/unit information
        so that subclasses can correctly use these parameters in their logic.
        """

        class ContextAwareCounter(Counter):
            def __init__(
                self,
                name: str,
                documentation: str,
                labelnames: Sequence[str] = (),
                namespace: str = "",
                subsystem: str = "",
                unit: str = "",
                **kwargs: Any,
            ):
                self.context = {
                    "namespace": namespace,
                    "subsystem": subsystem,
                    "unit": unit,
                }
                super().__init__(
                    name,
                    documentation,
                    labelnames=labelnames,
                    namespace=namespace,
                    subsystem=subsystem,
                    unit=unit,
                    **kwargs,
                )

        parent = ContextAwareCounter(
            "m",
            "help",
            labelnames=["status"],
            namespace="prod",
            subsystem="api",
            unit="seconds",
            registry=None,
        )

        child = parent.labels(status="200")

        # Verify that child retains parent's context
        self.assertEqual(child.context["namespace"], "prod")
        self.assertEqual(child.context["subsystem"], "api")
        self.assertEqual(child.context["unit"], "seconds")
