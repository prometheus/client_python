import os
import unittest
import warnings
from collections.abc import Sequence
from datetime import timedelta
from time import time
from threading import Event
from typing import Any
from unittest import mock

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
from prometheus_client.redis import (
    mark_process_dead,
    redis_client,
    _daemon_threads,
    _keep_key_from_expiring,
    _live_metrics,
)
from prometheus_client.redis_collector import RedisCollector
from prometheus_client.samples import Exemplar
from prometheus_client.values import (
    MULTIPROCESS_MODE_T,
    MutexValue,
    RedisValue,
    Value,
    get_value_class,
)

pytest.importorskip("redis")


class RedisTestCase(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PROMETHEUS_REDIS_URL"] = "fakeredis://localhost/42"
        values.ValueClass = RedisValue(lambda: 123)

    def tearDown(self) -> None:
        for identifier in list(_daemon_threads):
            mark_process_dead(identifier)
        redis_client().flushdb()
        del os.environ["PROMETHEUS_REDIS_URL"]
        values.ValueClass = MutexValue


class ValueTestCase(RedisTestCase):
    def create_value(
        self,
        metric_name: str = "test",
        name: str | None = None,
        type_: str = "counter",
        labelnames: list[str] | None = None,
        labelvalues: list[str] | None = None,
        multiprocess_mode: MULTIPROCESS_MODE_T = "",
    ) -> Value:
        return values.ValueClass(
            type_,
            metric_name,
            name or metric_name + "_total",
            labelnames or [],
            labelvalues or [],
            "Help Text",
            multiprocess_mode=multiprocess_mode,
        )

    def test_initializes_value(self) -> None:
        value = self.create_value()
        self.assertEqual(value.get(), 0.0)

    def test_sets_and_gets_value(self) -> None:
        value = self.create_value()
        value.set(5)
        self.assertEqual(value.get(), 5.0)

    def test_inc_value(self) -> None:
        value = self.create_value()
        value.inc(3)
        value.inc(5)
        self.assertEqual(value.get(), 8.0)

    def test_get_missing_value(self) -> None:
        value = self.create_value()
        redis_client().delete(value._key)
        self.assertEqual(value.get(), 0.0)

    def test_exemplars_not_implemented(self) -> None:
        value = self.create_value("test4")
        with self.assertRaises(NotImplementedError):
            value.set_exemplar(Exemplar(labels={}, value=0.0, timestamp=0.0))
        self.assertIsNone(value.get_exemplar())

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

    def test_multiprocess_mode_mostrecent(self) -> None:
        with self.assertRaises(NotImplementedError):
            self.create_value(type_="gauge", multiprocess_mode="mostrecent")

    def test_multiprocess_mode_counter(self) -> None:
        with self.assertRaises(AssertionError):
            self.create_value(type_="counter", multiprocess_mode="liveall")

    def test_multiprocess_mode(self) -> None:
        value = self.create_value(type_="gauge", multiprocess_mode="all")
        self.assertEqual(value._labelnames, ["pid"])
        self.assertEqual(value._labelvalues[-1], "123")
        self.assertIsNone(value._expiry)
        self.assertLess(redis_client().expiretime(value._key), 0)

    def test_multiprocess_mode_live(self) -> None:
        value = self.create_value(type_="gauge", multiprocess_mode="liveall")
        unixtime = time()
        self.assertEqual(value._labelnames, ["pid"])
        self.assertEqual(value._labelvalues[-1], "123")
        self.assertEqual(value._expiry, timedelta(seconds=20))
        expiretime = redis_client().expiretime(value._key)
        self.assertGreater(expiretime, unixtime)
        self.assertLessEqual(expiretime, unixtime + 20)

        self.assertIn("123", _daemon_threads)
        self.assertIn("123", _live_metrics)
        self.assertIn(value._key, _live_metrics["123"])

    def test_live_inc_updates_expiry(self) -> None:
        value = self.create_value(type_="gauge", multiprocess_mode="liveall")
        unixtime = time()
        redis_client().persist(value._key)
        self.assertLess(redis_client().expiretime(value._key), 0)

        value.inc(1)
        self.assertGreater(redis_client().expiretime(value._key), unixtime)

    def test_live_set_updates_expiry(self) -> None:
        value = self.create_value(type_="gauge", multiprocess_mode="liveall")
        unixtime = time()
        redis_client().persist(value._key)
        self.assertLess(redis_client().expiretime(value._key), 0)

        value.set(1)
        self.assertGreater(redis_client().expiretime(value._key), unixtime)

    def test_multiprocess_pid_change(self) -> None:
        pid = 1
        values.ValueClass = RedisValue(lambda: pid)

        value = self.create_value(type_="gauge", multiprocess_mode="all")
        self.assertEqual(value._labelnames[-1], "pid")
        self.assertEqual(value._labelvalues[-1], "1")
        value.inc(1)
        self.assertEqual(value.get(), 1.0)

        pid = 2
        value.inc(1)
        self.assertEqual(value._labelvalues[-1], "2")
        self.assertEqual(value.get(), 1.0)


class KeepMetricsAliveTestCase(RedisTestCase):
    """Test KeepMetricsAliveThread and friends."""

    def setUp(self):
        super().setUp()
        self.stop_event = Event()

    def tearDown(self):
        super().tearDown()
        self.stop_event.set()

    def mock_loop(self) -> None:
        self.loop_event = Event()
        self.waiting_event = Event()
        patcher = mock.patch(
            "prometheus_client.redis.KeepMetricsAliveThread.loop_wait",
            side_effect=self.loop_wait,
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def loop_wait(self, _timeout: float) -> bool:
        self.waiting_event.set()
        self.waiting_event = Event()
        assert self.loop_event.wait(5) is True
        return self.stop_event.is_set()

    def run_loop_once(self, stop: bool=False) -> None:
        if stop:
            self.stop_event.set()
        self.loop_event.set()
        if not stop:
            self.loop_event = Event()
            assert self.waiting_event.wait() is True

    def test_mark_unknown_process_dead(self) -> None:
        mark_process_dead("unknown")

    def test_mark_known_process_dead(self) -> None:
        client = redis_client()
        client.set("key", "hello")
        _keep_key_from_expiring("identifier", "key")
        self.assertIn("identifier", _daemon_threads)
        mark_process_dead("identifier")
        self.assertNotIn("identifier", _daemon_threads)

    def test_live_daemon_updates_expiry(self) -> None:
        """Exercise the full lifecycle of the daemon thread."""
        self.mock_loop()
        client = redis_client()
        client.set("key", "hello")
        _keep_key_from_expiring("identifier", "key")
        self.assertLess(client.expiretime("key"), 0)

        unixtime = time()
        self.run_loop_once()
        self.assertGreater(client.expiretime("key"), unixtime)
        self.run_loop_once(stop=True)


class TestRedisCollector(RedisTestCase):
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
        values.ValueClass = RedisValue(lambda: 456)
        s2 = Summary("s", "help", registry=None)
        self.assertEqual(0, self.registry.get_sample_value("s_count"))
        self.assertEqual(0, self.registry.get_sample_value("s_sum"))
        s1.observe(1)
        s2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value("s_count"))
        self.assertEqual(3, self.registry.get_sample_value("s_sum"))

    def test_histogram_adds(self) -> None:
        h1 = Histogram("h", "help", registry=None)
        values.ValueClass = RedisValue(lambda: 456)
        h2 = Histogram("h", "help", registry=None)
        self.assertEqual(0, self.registry.get_sample_value("h_count"))
        self.assertEqual(0, self.registry.get_sample_value("h_sum"))
        self.assertEqual(0, self.registry.get_sample_value("h_bucket", {"le": "5.0"}))
        h1.observe(1)
        h2.observe(2)
        self.assertEqual(2, self.registry.get_sample_value("h_count"))
        self.assertEqual(3, self.registry.get_sample_value("h_sum"))
        self.assertEqual(2, self.registry.get_sample_value("h_bucket", {"le": "5.0"}))

    def test_gauge_all(self) -> None:
        g1 = Gauge("g", "help", registry=None)
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None)
        self.assertEqual(0, self.registry.get_sample_value("g", {"pid": "123"}))
        self.assertEqual(0, self.registry.get_sample_value("g", {"pid": "456"}))
        g1.set(1)
        g2.set(2)
        mark_process_dead(123)
        self.assertEqual(1, self.registry.get_sample_value("g", {"pid": "123"}))
        self.assertEqual(2, self.registry.get_sample_value("g", {"pid": "456"}))

    def test_gauge_liveall(self) -> None:
        g1 = Gauge("g", "help", registry=None, multiprocess_mode="liveall")
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None, multiprocess_mode="liveall")
        self.assertEqual(0, self.registry.get_sample_value("g", {"pid": "123"}))
        self.assertEqual(0, self.registry.get_sample_value("g", {"pid": "456"}))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value("g", {"pid": "123"}))
        self.assertEqual(2, self.registry.get_sample_value("g", {"pid": "456"}))
        mark_process_dead(123)
        self.assertEqual(None, self.registry.get_sample_value("g", {"pid": "123"}))
        self.assertEqual(2, self.registry.get_sample_value("g", {"pid": "456"}))

    def test_gauge_min(self) -> None:
        g1 = Gauge("g", "help", registry=None, multiprocess_mode="min")
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None, multiprocess_mode="min")
        self.assertEqual(0, self.registry.get_sample_value("g"))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value("g"))

    def test_gauge_livemin(self):
        g1 = Gauge("g", "help", registry=None, multiprocess_mode="livemin")
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None, multiprocess_mode="livemin")
        self.assertEqual(0, self.registry.get_sample_value("g"))
        g1.set(1)
        g2.set(2)
        self.assertEqual(1, self.registry.get_sample_value("g"))
        mark_process_dead(123)
        self.assertEqual(2, self.registry.get_sample_value("g"))

    def test_gauge_max(self) -> None:
        g1 = Gauge("g", "help", registry=None, multiprocess_mode="max")
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None, multiprocess_mode="max")
        self.assertEqual(0, self.registry.get_sample_value("g"))
        g1.set(1)
        g2.set(2)
        self.assertEqual(2, self.registry.get_sample_value("g"))

    def test_gauge_livemax(self) -> None:
        g1 = Gauge("g", "help", registry=None, multiprocess_mode="livemax")
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None, multiprocess_mode="livemax")
        self.assertEqual(0, self.registry.get_sample_value("g"))
        g1.set(2)
        g2.set(1)
        self.assertEqual(2, self.registry.get_sample_value("g"))
        mark_process_dead(123)
        self.assertEqual(1, self.registry.get_sample_value("g"))

    def test_gauge_sum(self) -> None:
        g1 = Gauge("g", "help", registry=None, multiprocess_mode="sum")
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None, multiprocess_mode="sum")
        self.assertEqual(0, self.registry.get_sample_value("g"))
        g1.set(1)
        g2.set(2)
        self.assertEqual(3, self.registry.get_sample_value("g"))
        mark_process_dead(123)
        self.assertEqual(3, self.registry.get_sample_value("g"))

    def test_gauge_livesum(self) -> None:
        g1 = Gauge("g", "help", registry=None, multiprocess_mode="livesum")
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None, multiprocess_mode="livesum")
        self.assertEqual(0, self.registry.get_sample_value("g"))
        g1.set(1)
        g2.set(2)
        self.assertEqual(3, self.registry.get_sample_value("g"))
        mark_process_dead(123)
        self.assertEqual(2, self.registry.get_sample_value("g"))

    def xxx_test_gauge_mostrecent(self) -> None:
        g1 = Gauge("g", "help", registry=None, multiprocess_mode="mostrecent")
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None, multiprocess_mode="mostrecent")
        g2.set(2)
        g1.set(1)
        self.assertEqual(1, self.registry.get_sample_value("g"))
        mark_process_dead(123)
        self.assertEqual(1, self.registry.get_sample_value("g"))

    def xxx_test_gauge_livemostrecent(self) -> None:
        g1 = Gauge("g", "help", registry=None, multiprocess_mode="livemostrecent")
        values.ValueClass = RedisValue(lambda: 456)
        g2 = Gauge("g", "help", registry=None, multiprocess_mode="livemostrecent")
        g2.set(2)
        g1.set(1)
        self.assertEqual(1, self.registry.get_sample_value("g"))
        mark_process_dead(123)
        self.assertEqual(2, self.registry.get_sample_value("g"))

    def test_namespace_subsystem(self) -> None:
        c1 = Counter("c", "help", registry=None, namespace="ns", subsystem="ss")
        c1.inc(1)
        self.assertEqual(1, self.registry.get_sample_value("ns_ss_c_total"))

    def test_counter_across_forks(self) -> None:
        pid = 0
        values.ValueClass = RedisValue(lambda: pid)
        c1 = Counter("c", "help", registry=None)
        self.assertEqual(0, self.registry.get_sample_value("c_total"))
        c1.inc(1)
        c1.inc(1)
        pid = 1
        c1.inc(1)
        self.assertEqual(3, self.registry.get_sample_value("c_total"))
        # Unlike MultiProcessValue, we don't store any local state
        self.assertEqual(3, c1._value.get())

    def test_collect(self) -> None:
        pid = 0
        values.ValueClass = RedisValue(lambda: pid)
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

        pid = 1

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)
        h.labels(**labels).observe(5)

        metrics = {m.name: m for m in self.collector.collect()}

        self.assertEqual(metrics["c"].samples, [Sample("c_total", labels, 2.0)])
        metrics["g"].samples.sort(key=lambda x: x[1]["pid"])
        self.assertEqual(
            metrics["g"].samples,
            [
                Sample("g", add_label("pid", "0"), 1.0),
                Sample("g", add_label("pid", "1"), 1.0),
            ],
        )

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
        pid = 0
        values.ValueClass = RedisValue(lambda: pid)

        h = Histogram("h", "help", labelnames=["view"], registry=None)

        h.labels(view="view1").observe(1)

        pid = 1

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
        pid = 0
        values.ValueClass = RedisValue(lambda: pid)
        labels = {i: i for i in "abcd"}

        c = Counter("c", "help", labelnames=labels.keys(), registry=None)
        g = Gauge("g", "help", labelnames=labels.keys(), registry=None)

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)

        pid = 1

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)

        metrics = {
            m.name: m for m in self.registry.restricted_registry(["c_total"]).collect()
        }

        self.assertEqual(metrics.keys(), {"c"})

        self.assertEqual(metrics["c"].samples, [Sample("c_total", labels, 2.0)])

    def test_collect_preserves_help(self) -> None:
        pid = 0
        values.ValueClass = RedisValue(lambda: pid)
        labels = {i: i for i in "abcd"}

        c = Counter("c", "c help", labelnames=labels.keys(), registry=None)
        g = Gauge("g", "g help", labelnames=labels.keys(), registry=None)
        h = Histogram("h", "h help", labelnames=labels.keys(), registry=None)

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)
        h.labels(**labels).observe(1)

        pid = 1

        c.labels(**labels).inc(1)
        g.labels(**labels).set(1)
        h.labels(**labels).observe(5)

        metrics = {m.name: m for m in self.collector.collect()}

        self.assertEqual(metrics["c"].documentation, "c help")
        self.assertEqual(metrics["g"].documentation, "g help")
        self.assertEqual(metrics["h"].documentation, "h help")

    def test_remove_clear_warning(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            values.ValueClass = get_value_class()
            registry = CollectorRegistry()
            collector = RedisCollector(registry)
            counter = Counter("c", "help", labelnames=["label"], registry=None)
            counter.labels("label").inc()
            counter.remove("label")
            counter.clear()
            assert issubclass(w[0].category, UserWarning)
            assert "Removal of labels has not been implemented" in str(w[0].message)
            assert issubclass(w[-1].category, UserWarning)
            assert "Clearing of labels has not been implemented" in str(w[-1].message)

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
