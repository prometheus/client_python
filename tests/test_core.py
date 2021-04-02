from __future__ import unicode_literals

from concurrent.futures import ThreadPoolExecutor
import time

import pytest

from prometheus_client.core import (
    CollectorRegistry, Counter, CounterMetricFamily, Enum, Gauge,
    GaugeHistogramMetricFamily, GaugeMetricFamily, Histogram,
    HistogramMetricFamily, Info, InfoMetricFamily, Metric, Sample,
    StateSetMetricFamily, Summary, SummaryMetricFamily, UntypedMetricFamily,
)
from prometheus_client.decorator import getargspec

try:
    import unittest2 as unittest
except ImportError:
    import unittest


class TestCounter(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.counter = Counter('c_total', 'help', registry=self.registry)

    def test_increment(self):
        self.assertEqual(0, self.registry.get_sample_value('c_total'))
        self.counter.inc()
        self.assertEqual(1, self.registry.get_sample_value('c_total'))
        self.counter.inc(7)
        self.assertEqual(8, self.registry.get_sample_value('c_total'))
    
    def test_repr(self):
        self.assertEqual(repr(self.counter), "prometheus_client.metrics.Counter(c)")

    def test_negative_increment_raises(self):
        self.assertRaises(ValueError, self.counter.inc, -1)
    

    def test_function_decorator(self):
        @self.counter.count_exceptions(ValueError)
        def f(r):
            if r:
                raise ValueError
            else:
                raise TypeError

        self.assertEqual((["r"], None, None, None), getargspec(f))

        try:
            f(False)
        except TypeError:
            pass
        self.assertEqual(0, self.registry.get_sample_value('c_total'))

        try:
            f(True)
        except ValueError:
            pass
        self.assertEqual(1, self.registry.get_sample_value('c_total'))

    def test_block_decorator(self):
        with self.counter.count_exceptions():
            pass
        self.assertEqual(0, self.registry.get_sample_value('c_total'))

        raised = False
        try:
            with self.counter.count_exceptions():
                raise ValueError
        except:
            raised = True
        self.assertTrue(raised)
        self.assertEqual(1, self.registry.get_sample_value('c_total'))

    def test_count_exceptions_not_observable(self):
        counter = Counter('counter', 'help', labelnames=('label',), registry=self.registry)

        try:
            counter.count_exceptions()
        except ValueError as e:
            self.assertIn('missing label values', str(e))


class TestGauge(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.gauge = Gauge('g', 'help', registry=self.registry)
    
    def test_repr(self):
        self.assertEqual(repr(self.gauge), "prometheus_client.metrics.Gauge(g)")

    def test_gauge(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))
        self.gauge.inc()
        self.assertEqual(1, self.registry.get_sample_value('g'))
        self.gauge.dec(3)
        self.assertEqual(-2, self.registry.get_sample_value('g'))
        self.gauge.set(9)
        self.assertEqual(9, self.registry.get_sample_value('g'))

    def test_inprogress_function_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))

        @self.gauge.track_inprogress()
        def f():
            self.assertEqual(1, self.registry.get_sample_value('g'))

        self.assertEqual(([], None, None, None), getargspec(f))

        f()
        self.assertEqual(0, self.registry.get_sample_value('g'))

    def test_inprogress_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))
        with self.gauge.track_inprogress():
            self.assertEqual(1, self.registry.get_sample_value('g'))
        self.assertEqual(0, self.registry.get_sample_value('g'))

    def test_gauge_function(self):
        x = {}
        self.gauge.set_function(lambda: len(x))
        self.assertEqual(0, self.registry.get_sample_value('g'))
        self.gauge.inc()
        self.assertEqual(0, self.registry.get_sample_value('g'))
        x['a'] = None
        self.assertEqual(1, self.registry.get_sample_value('g'))

    def test_time_function_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))

        @self.gauge.time()
        def f():
            time.sleep(.001)

        self.assertEqual(([], None, None, None), getargspec(f))

        f()
        self.assertNotEqual(0, self.registry.get_sample_value('g'))

    def test_function_decorator_multithread(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))
        workers = 2
        pool = ThreadPoolExecutor(max_workers=workers)

        @self.gauge.time()
        def f(duration):
            time.sleep(duration)

        expected_duration = 1
        pool.submit(f, expected_duration)
        time.sleep(0.7 * expected_duration)
        pool.submit(f, expected_duration * 2)
        time.sleep(expected_duration)

        rounding_coefficient = 0.9
        adjusted_expected_duration = expected_duration * rounding_coefficient
        self.assertLess(adjusted_expected_duration, self.registry.get_sample_value('g'))
        pool.shutdown(wait=True)

    def test_time_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))
        with self.gauge.time():
            time.sleep(.001)
        self.assertNotEqual(0, self.registry.get_sample_value('g'))

    def test_track_in_progress_not_observable(self):
        g = Gauge('test', 'help', labelnames=('label',), registry=self.registry)

        try:
            g.track_inprogress()
        except ValueError as e:
            self.assertIn('missing label values', str(e))

    def test_timer_not_observable(self):
        g = Gauge('test', 'help', labelnames=('label',), registry=self.registry)

        try:
            g.time()
        except ValueError as e:
            self.assertIn('missing label values', str(e))


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.summary = Summary('s', 'help', registry=self.registry)

    def test_repr(self):
        self.assertEqual(repr(self.summary), "prometheus_client.metrics.Summary(s)")

    def test_summary(self):
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        self.assertEqual(0, self.registry.get_sample_value('s_sum'))
        self.summary.observe(10)
        self.assertEqual(1, self.registry.get_sample_value('s_count'))
        self.assertEqual(10, self.registry.get_sample_value('s_sum'))

    def test_function_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('s_count'))

        @self.summary.time()
        def f():
            pass

        self.assertEqual(([], None, None, None), getargspec(f))

        f()
        self.assertEqual(1, self.registry.get_sample_value('s_count'))

    def test_function_decorator_multithread(self):
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        summary2 = Summary('s2', 'help', registry=self.registry)

        workers = 3
        duration = 0.1
        pool = ThreadPoolExecutor(max_workers=workers)

        @self.summary.time()
        def f():
            time.sleep(duration / 2)
            # Testing that different instances of timer do not interfere
            summary2.time()(lambda: time.sleep(duration / 2))()

        jobs = workers * 3
        for i in range(jobs):
            pool.submit(f)
        pool.shutdown(wait=True)

        self.assertEqual(jobs, self.registry.get_sample_value('s_count'))

        rounding_coefficient = 0.9
        total_expected_duration = jobs * duration * rounding_coefficient
        self.assertLess(total_expected_duration, self.registry.get_sample_value('s_sum'))
        self.assertLess(total_expected_duration / 2, self.registry.get_sample_value('s2_sum'))

    def test_function_decorator_reentrancy(self):
        self.assertEqual(0, self.registry.get_sample_value('s_count'))

        iterations = 2
        sleep = 0.1

        @self.summary.time()
        def f(i=1):
            time.sleep(sleep)
            if i == iterations:
                return
            f(i + 1)

        f()

        self.assertEqual(iterations, self.registry.get_sample_value('s_count'))

        # Arithmetic series with d == a_1
        total_expected_duration = sleep * (iterations ** 2 + iterations) / 2
        rounding_coefficient = 0.9
        total_expected_duration *= rounding_coefficient
        self.assertLess(total_expected_duration, self.registry.get_sample_value('s_sum'))

    def test_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        with self.summary.time():
            pass
        self.assertEqual(1, self.registry.get_sample_value('s_count'))

    def test_timer_not_observable(self):
        s = Summary('test', 'help', labelnames=('label',), registry=self.registry)

        try:
            s.time()
        except ValueError as e:
            self.assertIn('missing label values', str(e))


class TestHistogram(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.histogram = Histogram('h', 'help', registry=self.registry)
        self.labels = Histogram('hl', 'help', ['l'], registry=self.registry)

    def test_repr(self):
        self.assertEqual(repr(self.histogram), "prometheus_client.metrics.Histogram(h)")
        self.assertEqual(repr(self.labels), "prometheus_client.metrics.Histogram(hl)")

    def test_histogram(self):
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '1.0'}))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '2.5'}))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        self.assertEqual(0, self.registry.get_sample_value('h_sum'))

        self.histogram.observe(2)
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '1.0'}))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '2.5'}))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        self.assertEqual(1, self.registry.get_sample_value('h_count'))
        self.assertEqual(2, self.registry.get_sample_value('h_sum'))

        self.histogram.observe(2.5)
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '1.0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '2.5'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        self.assertEqual(2, self.registry.get_sample_value('h_count'))
        self.assertEqual(4.5, self.registry.get_sample_value('h_sum'))

        self.histogram.observe(float("inf"))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '1.0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '2.5'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        self.assertEqual(3, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        self.assertEqual(3, self.registry.get_sample_value('h_count'))
        self.assertEqual(float("inf"), self.registry.get_sample_value('h_sum'))

    def test_setting_buckets(self):
        h = Histogram('h', 'help', registry=None, buckets=[0, 1, 2])
        self.assertEqual([0.0, 1.0, 2.0, float("inf")], h._upper_bounds)

        h = Histogram('h', 'help', registry=None, buckets=[0, 1, 2, float("inf")])
        self.assertEqual([0.0, 1.0, 2.0, float("inf")], h._upper_bounds)

        self.assertRaises(ValueError, Histogram, 'h', 'help', registry=None, buckets=[])
        self.assertRaises(ValueError, Histogram, 'h', 'help', registry=None, buckets=[float("inf")])
        self.assertRaises(ValueError, Histogram, 'h', 'help', registry=None, buckets=[3, 1])

    def test_labels(self):
        self.assertRaises(ValueError, Histogram, 'h', 'help', registry=None, labelnames=['le'])

        self.labels.labels('a').observe(2)
        self.assertEqual(0, self.registry.get_sample_value('hl_bucket', {'le': '1.0', 'l': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('hl_bucket', {'le': '2.5', 'l': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('hl_bucket', {'le': '5.0', 'l': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('hl_bucket', {'le': '+Inf', 'l': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('hl_count', {'l': 'a'}))
        self.assertEqual(2, self.registry.get_sample_value('hl_sum', {'l': 'a'}))

    def test_function_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))

        @self.histogram.time()
        def f():
            pass

        self.assertEqual(([], None, None, None), getargspec(f))

        f()
        self.assertEqual(1, self.registry.get_sample_value('h_count'))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))

    def test_function_decorator_multithread(self):
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        workers = 3
        duration = 0.1
        pool = ThreadPoolExecutor(max_workers=workers)

        @self.histogram.time()
        def f():
            time.sleep(duration)

        jobs = workers * 3
        for i in range(jobs):
            pool.submit(f)
        pool.shutdown(wait=True)

        self.assertEqual(jobs, self.registry.get_sample_value('h_count'))

        rounding_coefficient = 0.9
        total_expected_duration = jobs * duration * rounding_coefficient
        self.assertLess(total_expected_duration, self.registry.get_sample_value('h_sum'))

    def test_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        with self.histogram.time():
            pass
        self.assertEqual(1, self.registry.get_sample_value('h_count'))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))


class TestInfo(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.info = Info('i', 'help', registry=self.registry)
        self.labels = Info('il', 'help', ['l'], registry=self.registry)

    def test_repr(self):
        self.assertEqual(repr(self.info), "prometheus_client.metrics.Info(i)")
        self.assertEqual(repr(self.labels), "prometheus_client.metrics.Info(il)")

    def test_info(self):
        self.assertEqual(1, self.registry.get_sample_value('i_info', {}))
        self.info.info({'a': 'b', 'c': 'd'})
        self.assertEqual(None, self.registry.get_sample_value('i_info', {}))
        self.assertEqual(1, self.registry.get_sample_value('i_info', {'a': 'b', 'c': 'd'}))

    def test_labels(self):
        self.assertRaises(ValueError, self.labels.labels('a').info, {'l': ''})

        self.labels.labels('a').info({'foo': 'bar'})
        self.assertEqual(1, self.registry.get_sample_value('il_info', {'l': 'a', 'foo': 'bar'}))


class TestEnum(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.enum = Enum('e', 'help', states=['a', 'b', 'c'], registry=self.registry)
        self.labels = Enum('el', 'help', ['l'], states=['a', 'b', 'c'], registry=self.registry)

    def test_enum(self):
        self.assertEqual(1, self.registry.get_sample_value('e', {'e': 'a'}))
        self.assertEqual(0, self.registry.get_sample_value('e', {'e': 'b'}))
        self.assertEqual(0, self.registry.get_sample_value('e', {'e': 'c'}))

        self.enum.state('b')
        self.assertEqual(0, self.registry.get_sample_value('e', {'e': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('e', {'e': 'b'}))
        self.assertEqual(0, self.registry.get_sample_value('e', {'e': 'c'}))

        self.assertRaises(ValueError, self.enum.state, 'd')
        self.assertRaises(ValueError, Enum, 'e', 'help', registry=None)

    def test_labels(self):
        self.labels.labels('a').state('c')
        self.assertEqual(0, self.registry.get_sample_value('el', {'l': 'a', 'el': 'a'}))
        self.assertEqual(0, self.registry.get_sample_value('el', {'l': 'a', 'el': 'b'}))
        self.assertEqual(1, self.registry.get_sample_value('el', {'l': 'a', 'el': 'c'}))
        self.assertRaises(ValueError, self.labels.state, 'a')

    def test_overlapping_labels(self):
        with pytest.raises(ValueError):
            Enum('e', 'help', registry=None, labelnames=['e'])


class TestMetricWrapper(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.counter = Counter('c_total', 'help', labelnames=['l'], registry=self.registry)
        self.two_labels = Counter('two', 'help', labelnames=['a', 'b'], registry=self.registry)

    def test_child(self):
        self.counter.labels('x').inc()
        self.assertEqual(1, self.registry.get_sample_value('c_total', {'l': 'x'}))
        self.two_labels.labels('x', 'y').inc(2)
        self.assertEqual(2, self.registry.get_sample_value('two_total', {'a': 'x', 'b': 'y'}))

    def test_remove(self):
        self.counter.labels('x').inc()
        self.counter.labels('y').inc(2)
        self.assertEqual(1, self.registry.get_sample_value('c_total', {'l': 'x'}))
        self.assertEqual(2, self.registry.get_sample_value('c_total', {'l': 'y'}))
        self.counter.remove('x')
        self.assertEqual(None, self.registry.get_sample_value('c_total', {'l': 'x'}))
        self.assertEqual(2, self.registry.get_sample_value('c_total', {'l': 'y'}))

    def test_clear(self):
        self.counter.labels('x').inc()
        self.counter.labels('y').inc(2)
        self.assertEqual(1, self.registry.get_sample_value('c_total', {'l': 'x'}))
        self.assertEqual(2, self.registry.get_sample_value('c_total', {'l': 'y'}))
        self.counter.clear()
        self.assertEqual(None, self.registry.get_sample_value('c_total', {'l': 'x'}))
        self.assertEqual(None, self.registry.get_sample_value('c_total', {'l': 'y'}))

    def test_incorrect_label_count_raises(self):
        self.assertRaises(ValueError, self.counter.labels)
        self.assertRaises(ValueError, self.counter.labels, 'a', 'b')
        self.assertRaises(ValueError, self.counter.remove)
        self.assertRaises(ValueError, self.counter.remove, 'a', 'b')

    def test_labels_on_labels(self):
        with pytest.raises(ValueError):
            self.counter.labels('a').labels('b')

    def test_labels_coerced_to_string(self):
        self.counter.labels(None).inc()
        self.counter.labels(l=None).inc()
        self.assertEqual(2, self.registry.get_sample_value('c_total', {'l': 'None'}))

        self.counter.remove(None)
        self.assertEqual(None, self.registry.get_sample_value('c_total', {'l': 'None'}))

    def test_non_string_labels_raises(self):
        class Test(object):
            __str__ = None

        self.assertRaises(TypeError, self.counter.labels, Test())
        self.assertRaises(TypeError, self.counter.labels, l=Test())

    def test_namespace_subsystem_concatenated(self):
        c = Counter('c_total', 'help', namespace='a', subsystem='b', registry=self.registry)
        c.inc()
        self.assertEqual(1, self.registry.get_sample_value('a_b_c_total'))

    def test_labels_by_kwarg(self):
        self.counter.labels(l='x').inc()
        self.assertEqual(1, self.registry.get_sample_value('c_total', {'l': 'x'}))
        self.assertRaises(ValueError, self.counter.labels, l='x', m='y')
        self.assertRaises(ValueError, self.counter.labels, m='y')
        self.assertRaises(ValueError, self.counter.labels)
        self.two_labels.labels(a='x', b='y').inc()
        self.assertEqual(1, self.registry.get_sample_value('two_total', {'a': 'x', 'b': 'y'}))
        self.assertRaises(ValueError, self.two_labels.labels, a='x', b='y', c='z')
        self.assertRaises(ValueError, self.two_labels.labels, a='x', c='z')
        self.assertRaises(ValueError, self.two_labels.labels, b='y', c='z')
        self.assertRaises(ValueError, self.two_labels.labels, c='z')
        self.assertRaises(ValueError, self.two_labels.labels)
        self.assertRaises(ValueError, self.two_labels.labels, {'a': 'x'}, b='y')

    def test_invalid_names_raise(self):
        self.assertRaises(ValueError, Counter, '', 'help')
        self.assertRaises(ValueError, Counter, '^', 'help')
        self.assertRaises(ValueError, Counter, '', 'help', namespace='&')
        self.assertRaises(ValueError, Counter, '', 'help', subsystem='(')
        self.assertRaises(ValueError, Counter, 'c_total', '', labelnames=['^'])
        self.assertRaises(ValueError, Counter, 'c_total', '', labelnames=['a:b'])
        self.assertRaises(ValueError, Counter, 'c_total', '', labelnames=['__reserved'])
        self.assertRaises(ValueError, Summary, 'c_total', '', labelnames=['quantile'])

    def test_empty_labels_list(self):
        Histogram('h', 'help', [], registry=self.registry)
        self.assertEqual(0, self.registry.get_sample_value('h_sum'))

    def test_unit_appended(self):
        Histogram('h', 'help', [], registry=self.registry, unit="seconds")
        self.assertEqual(0, self.registry.get_sample_value('h_seconds_sum'))

    def test_unit_notappended(self):
        Histogram('h_seconds', 'help', [], registry=self.registry, unit="seconds")
        self.assertEqual(0, self.registry.get_sample_value('h_seconds_sum'))

    def test_no_units_for_info_enum(self):
        self.assertRaises(ValueError, Info, 'foo', 'help', unit="x")
        self.assertRaises(ValueError, Enum, 'foo', 'help', unit="x")

    def test_name_cleanup_before_unit_append(self):
        c = Counter('b_total', 'help', unit="total", labelnames=['l'], registry=self.registry)
        self.assertEqual(c._name, 'b_total')


class TestMetricFamilies(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()

    def custom_collector(self, metric_family):
        class CustomCollector(object):
            def collect(self):
                return [metric_family]

        self.registry.register(CustomCollector())

    def test_untyped(self):
        self.custom_collector(UntypedMetricFamily('u', 'help', value=1))
        self.assertEqual(1, self.registry.get_sample_value('u', {}))

    def test_untyped_labels(self):
        cmf = UntypedMetricFamily('u', 'help', labels=['a', 'c'])
        cmf.add_metric(['b', 'd'], 2)
        self.custom_collector(cmf)
        self.assertEqual(2, self.registry.get_sample_value('u', {'a': 'b', 'c': 'd'}))

    def test_untyped_unit(self):
        self.custom_collector(UntypedMetricFamily('u', 'help', value=1, unit='unit'))
        self.assertEqual(1, self.registry.get_sample_value('u_unit', {}))

    def test_counter(self):
        self.custom_collector(CounterMetricFamily('c_total', 'help', value=1))
        self.assertEqual(1, self.registry.get_sample_value('c_total', {}))

    def test_counter_total(self):
        self.custom_collector(CounterMetricFamily('c_total', 'help', value=1))
        self.assertEqual(1, self.registry.get_sample_value('c_total', {}))

    def test_counter_labels(self):
        cmf = CounterMetricFamily('c_total', 'help', labels=['a', 'c_total'])
        cmf.add_metric(['b', 'd'], 2)
        self.custom_collector(cmf)
        self.assertEqual(2, self.registry.get_sample_value('c_total', {'a': 'b', 'c_total': 'd'}))

    def test_gauge(self):
        self.custom_collector(GaugeMetricFamily('g', 'help', value=1))
        self.assertEqual(1, self.registry.get_sample_value('g', {}))

    def test_gauge_labels(self):
        cmf = GaugeMetricFamily('g', 'help', labels=['a'])
        cmf.add_metric(['b'], 2)
        self.custom_collector(cmf)
        self.assertEqual(2, self.registry.get_sample_value('g', {'a': 'b'}))

    def test_summary(self):
        self.custom_collector(SummaryMetricFamily('s', 'help', count_value=1, sum_value=2))
        self.assertEqual(1, self.registry.get_sample_value('s_count', {}))
        self.assertEqual(2, self.registry.get_sample_value('s_sum', {}))

    def test_summary_labels(self):
        cmf = SummaryMetricFamily('s', 'help', labels=['a'])
        cmf.add_metric(['b'], count_value=1, sum_value=2)
        self.custom_collector(cmf)
        self.assertEqual(1, self.registry.get_sample_value('s_count', {'a': 'b'}))
        self.assertEqual(2, self.registry.get_sample_value('s_sum', {'a': 'b'}))

    def test_histogram(self):
        self.custom_collector(HistogramMetricFamily('h', 'help', buckets=[('0', 1), ('+Inf', 2)], sum_value=3))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        self.assertEqual(2, self.registry.get_sample_value('h_count', {}))
        self.assertEqual(3, self.registry.get_sample_value('h_sum', {}))

    def test_histogram_labels(self):
        cmf = HistogramMetricFamily('h', 'help', labels=['a'])
        cmf.add_metric(['b'], buckets=[('0', 1), ('+Inf', 2)], sum_value=3)
        self.custom_collector(cmf)
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'a': 'b', 'le': '0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'a': 'b', 'le': '+Inf'}))
        self.assertEqual(2, self.registry.get_sample_value('h_count', {'a': 'b'}))
        self.assertEqual(3, self.registry.get_sample_value('h_sum', {'a': 'b'}))

    def test_gaugehistogram(self):
        self.custom_collector(GaugeHistogramMetricFamily('h', 'help', buckets=[('0', 1), ('+Inf', 2)]))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))

    def test_gaugehistogram_labels(self):
        cmf = GaugeHistogramMetricFamily('h', 'help', labels=['a'])
        cmf.add_metric(['b'], buckets=[('0', 1), ('+Inf', 2)], gsum_value=3)
        self.custom_collector(cmf)
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'a': 'b', 'le': '0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'a': 'b', 'le': '+Inf'}))
        self.assertEqual(2, self.registry.get_sample_value('h_gcount', {'a': 'b'}))
        self.assertEqual(3, self.registry.get_sample_value('h_gsum', {'a': 'b'}))

    def test_info(self):
        self.custom_collector(InfoMetricFamily('i', 'help', value={'a': 'b'}))
        self.assertEqual(1, self.registry.get_sample_value('i_info', {'a': 'b'}))

    def test_info_labels(self):
        cmf = InfoMetricFamily('i', 'help', labels=['a'])
        cmf.add_metric(['b'], {'c': 'd'})
        self.custom_collector(cmf)
        self.assertEqual(1, self.registry.get_sample_value('i_info', {'a': 'b', 'c': 'd'}))

    def test_stateset(self):
        self.custom_collector(StateSetMetricFamily('s', 'help', value={'a': True, 'b': True, }))
        self.assertEqual(1, self.registry.get_sample_value('s', {'s': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('s', {'s': 'b'}))

    def test_stateset_labels(self):
        cmf = StateSetMetricFamily('s', 'help', labels=['foo'])
        cmf.add_metric(['bar'], {'a': False, 'b': False, })
        self.custom_collector(cmf)
        self.assertEqual(0, self.registry.get_sample_value('s', {'foo': 'bar', 's': 'a'}))
        self.assertEqual(0, self.registry.get_sample_value('s', {'foo': 'bar', 's': 'b'}))

    def test_bad_constructors(self):
        self.assertRaises(ValueError, UntypedMetricFamily, 'u', 'help', value=1, labels=[])
        self.assertRaises(ValueError, UntypedMetricFamily, 'u', 'help', value=1, labels=['a'])

        self.assertRaises(ValueError, CounterMetricFamily, 'c_total', 'help', value=1, labels=[])
        self.assertRaises(ValueError, CounterMetricFamily, 'c_total', 'help', value=1, labels=['a'])

        self.assertRaises(ValueError, GaugeMetricFamily, 'g', 'help', value=1, labels=[])
        self.assertRaises(ValueError, GaugeMetricFamily, 'g', 'help', value=1, labels=['a'])

        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', sum_value=1)
        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', count_value=1)
        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', count_value=1, labels=['a'])
        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', sum_value=1, labels=['a'])
        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', count_value=1, sum_value=1, labels=['a'])

        self.assertRaises(ValueError, HistogramMetricFamily, 'h', 'help', sum_value=1)
        self.assertRaises(KeyError, HistogramMetricFamily, 'h', 'help', buckets={})
        self.assertRaises(ValueError, HistogramMetricFamily, 'h', 'help', sum_value=1, labels=['a'])
        self.assertRaises(ValueError, HistogramMetricFamily, 'h', 'help', buckets={}, labels=['a'])
        self.assertRaises(ValueError, HistogramMetricFamily, 'h', 'help', buckets={}, sum_value=1, labels=['a'])
        self.assertRaises(KeyError, HistogramMetricFamily, 'h', 'help', buckets={}, sum_value=1)

        self.assertRaises(ValueError, InfoMetricFamily, 'i', 'help', value={}, labels=[])
        self.assertRaises(ValueError, InfoMetricFamily, 'i', 'help', value={}, labels=['a'])

        self.assertRaises(ValueError, StateSetMetricFamily, 's', 'help', value={'a': True}, labels=[])
        self.assertRaises(ValueError, StateSetMetricFamily, 's', 'help', value={'a': True}, labels=['a'])

    def test_labelnames(self):
        cmf = UntypedMetricFamily('u', 'help', labels=iter(['a']))
        self.assertEqual(('a',), cmf._labelnames)
        cmf = CounterMetricFamily('c_total', 'help', labels=iter(['a']))
        self.assertEqual(('a',), cmf._labelnames)
        gmf = GaugeMetricFamily('g', 'help', labels=iter(['a']))
        self.assertEqual(('a',), gmf._labelnames)
        smf = SummaryMetricFamily('s', 'help', labels=iter(['a']))
        self.assertEqual(('a',), smf._labelnames)
        hmf = HistogramMetricFamily('h', 'help', labels=iter(['a']))
        self.assertEqual(('a',), hmf._labelnames)


class TestCollectorRegistry(unittest.TestCase):
    def test_duplicate_metrics_raises(self):
        registry = CollectorRegistry()
        Counter('c_total', 'help', registry=registry)
        self.assertRaises(ValueError, Counter, 'c_total', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'c_total', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'c_created', 'help', registry=registry)

        Gauge('g_created', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'g_created', 'help', registry=registry)
        self.assertRaises(ValueError, Counter, 'g', 'help', registry=registry)

        Summary('s', 'help', registry=registry)
        self.assertRaises(ValueError, Summary, 's', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 's_created', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 's_sum', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 's_count', 'help', registry=registry)
        # We don't currently expose quantiles, but let's prevent future
        # clashes anyway.
        self.assertRaises(ValueError, Gauge, 's', 'help', registry=registry)

        Histogram('h', 'help', registry=registry)
        self.assertRaises(ValueError, Histogram, 'h', 'help', registry=registry)
        # Clashes aggaint various suffixes.
        self.assertRaises(ValueError, Summary, 'h', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'h_count', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'h_sum', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'h_bucket', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'h_created', 'help', registry=registry)
        # The name of the histogram itself is also taken.
        self.assertRaises(ValueError, Gauge, 'h', 'help', registry=registry)

        Info('i', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'i_info', 'help', registry=registry)

    def test_unregister_works(self):
        registry = CollectorRegistry()
        s = Summary('s', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 's_count', 'help', registry=registry)
        registry.unregister(s)
        Gauge('s_count', 'help', registry=registry)

    def custom_collector(self, metric_family, registry):
        class CustomCollector(object):
            def collect(self):
                return [metric_family]

        registry.register(CustomCollector())

    def test_autodescribe_disabled_by_default(self):
        registry = CollectorRegistry()
        self.custom_collector(CounterMetricFamily('c_total', 'help', value=1), registry)
        self.custom_collector(CounterMetricFamily('c_total', 'help', value=1), registry)

        registry = CollectorRegistry(auto_describe=True)
        self.custom_collector(CounterMetricFamily('c_total', 'help', value=1), registry)
        self.assertRaises(ValueError, self.custom_collector, CounterMetricFamily('c_total', 'help', value=1), registry)

    def test_restricted_registry(self):
        registry = CollectorRegistry()
        Counter('c_total', 'help', registry=registry)
        Summary('s', 'help', registry=registry).observe(7)

        m = Metric('s', 'help', 'summary')
        m.samples = [Sample('s_sum', {}, 7)]
        self.assertEqual([m], registry.restricted_registry(['s_sum']).collect())

    def test_target_info_injected(self):
        registry = CollectorRegistry(target_info={'foo': 'bar'})
        self.assertEqual(1, registry.get_sample_value('target_info', {'foo': 'bar'}))

    def test_target_info_duplicate_detected(self):
        registry = CollectorRegistry(target_info={'foo': 'bar'})
        self.assertRaises(ValueError, Info, 'target', 'help', registry=registry)

        registry.set_target_info({})
        i = Info('target', 'help', registry=registry)
        registry.set_target_info({})
        self.assertRaises(ValueError, Info, 'target', 'help', registry=registry)
        self.assertRaises(ValueError, registry.set_target_info, {'foo': 'bar'})
        registry.unregister(i)
        registry.set_target_info({'foo': 'bar'})

    def test_target_info_restricted_registry(self):
        registry = CollectorRegistry(target_info={'foo': 'bar'})
        Summary('s', 'help', registry=registry).observe(7)

        m = Metric('s', 'help', 'summary')
        m.samples = [Sample('s_sum', {}, 7)]
        self.assertEqual([m], registry.restricted_registry(['s_sum']).collect())

        m = Metric('target', 'Target metadata', 'info')
        m.samples = [Sample('target_info', {'foo': 'bar'}, 1)]
        self.assertEqual([m], registry.restricted_registry(['target_info']).collect())


if __name__ == '__main__':
    unittest.main()
