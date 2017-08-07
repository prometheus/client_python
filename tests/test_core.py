from __future__ import unicode_literals

import inspect
import os
import threading
import time
import unittest

from prometheus_client.core import *

class TestCounter(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.counter = Counter('c', 'help', registry=self.registry)

    def test_increment(self):
        self.assertEqual(0, self.registry.get_sample_value('c'))
        self.counter.inc()
        self.assertEqual(1, self.registry.get_sample_value('c'))
        self.counter.inc(7)
        self.assertEqual(8, self.registry.get_sample_value('c'))

    def test_negative_increment_raises(self):
        self.assertRaises(ValueError, self.counter.inc, -1)

    def test_function_decorator(self):
        @self.counter.count_exceptions(ValueError)
        def f(r):
            if r:
                raise ValueError
            else:
                raise TypeError

        self.assertEqual((["r"], None, None, None), inspect.getargspec(f))

        try:
            f(False)
        except TypeError:
            pass
        self.assertEqual(0, self.registry.get_sample_value('c'))

        try:
            f(True)
        except ValueError:
            raised = True
        self.assertEqual(1, self.registry.get_sample_value('c'))

    def test_block_decorator(self):
        with self.counter.count_exceptions():
            pass
        self.assertEqual(0, self.registry.get_sample_value('c'))

        raised = False
        try:
            with self.counter.count_exceptions():
                raise ValueError
        except:
            raised = True
        self.assertTrue(raised)
        self.assertEqual(1, self.registry.get_sample_value('c'))


class TestGauge(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.gauge = Gauge('g', 'help', registry=self.registry)

    def test_gauge(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))
        self.gauge.inc()
        self.assertEqual(1, self.registry.get_sample_value('g'))
        self.gauge.dec(3)
        self.assertEqual(-2, self.registry.get_sample_value('g'))
        self.gauge.set(9)
        self.assertEqual(9, self.registry.get_sample_value('g'))

    def test_function_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))

        @self.gauge.track_inprogress()
        def f():
            self.assertEqual(1, self.registry.get_sample_value('g'))

        self.assertEqual(([], None, None, None), inspect.getargspec(f))

        f()
        self.assertEqual(0, self.registry.get_sample_value('g'))

    def test_block_decorator(self):
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

    def test_function_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))

        @self.gauge.time()
        def f():
            time.sleep(.001)

        self.assertEqual(([], None, None, None), inspect.getargspec(f))

        f()
        self.assertNotEqual(0, self.registry.get_sample_value('g'))

    def test_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))
        with self.gauge.time():
            time.sleep(.001)
        self.assertNotEqual(0, self.registry.get_sample_value('g'))


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.summary = Summary('s', 'help', registry=self.registry)

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

        self.assertEqual(([], None, None, None), inspect.getargspec(f))

        f()
        self.assertEqual(1, self.registry.get_sample_value('s_count'))

    def test_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        with self.summary.time():
            pass
        self.assertEqual(1, self.registry.get_sample_value('s_count'))


class TestHistogram(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.histogram = Histogram('h', 'help', registry=self.registry)
        self.labels = Histogram('hl', 'help', ['l'], registry=self.registry)

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

        self.assertEqual(([], None, None, None), inspect.getargspec(f))

        f()
        self.assertEqual(1, self.registry.get_sample_value('h_count'))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))

    def test_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        with self.histogram.time():
            pass
        self.assertEqual(1, self.registry.get_sample_value('h_count'))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))


class TestMetricWrapper(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.counter = Counter('c', 'help', labelnames=['l'], registry=self.registry)
        self.two_labels = Counter('two', 'help', labelnames=['a', 'b'], registry=self.registry)

    def test_child(self):
        self.counter.labels('x').inc()
        self.assertEqual(1, self.registry.get_sample_value('c', {'l': 'x'}))
        self.two_labels.labels('x', 'y').inc(2)
        self.assertEqual(2, self.registry.get_sample_value('two', {'a': 'x', 'b': 'y'}))

    def test_remove(self):
        self.counter.labels('x').inc()
        self.counter.labels('y').inc(2)
        self.assertEqual(1, self.registry.get_sample_value('c', {'l': 'x'}))
        self.assertEqual(2, self.registry.get_sample_value('c', {'l': 'y'}))
        self.counter.remove('x')
        self.assertEqual(None, self.registry.get_sample_value('c', {'l': 'x'}))
        self.assertEqual(2, self.registry.get_sample_value('c', {'l': 'y'}))

    def test_incorrect_label_count_raises(self):
        self.assertRaises(ValueError, self.counter.labels)
        self.assertRaises(ValueError, self.counter.labels, 'a', 'b')
        self.assertRaises(ValueError, self.counter.remove)
        self.assertRaises(ValueError, self.counter.remove, 'a', 'b')

    def test_labels_coerced_to_string(self):
        self.counter.labels(None).inc()
        self.counter.labels(l=None).inc()
        self.assertEqual(2, self.registry.get_sample_value('c', {'l': 'None'}))

        self.counter.remove(None)
        self.assertEqual(None, self.registry.get_sample_value('c', {'l': 'None'}))

    def test_non_string_labels_raises(self):
        class Test(object):
            __str__ = None
        self.assertRaises(TypeError, self.counter.labels, Test())
        self.assertRaises(TypeError, self.counter.labels, l=Test())

    def test_namespace_subsystem_concatenated(self):
        c = Counter('c', 'help', namespace='a', subsystem='b', registry=self.registry)
        c.inc()
        self.assertEqual(1, self.registry.get_sample_value('a_b_c'))

    def test_labels_by_kwarg(self):
        self.counter.labels(l='x').inc()
        self.assertEqual(1, self.registry.get_sample_value('c', {'l': 'x'}))
        self.assertRaises(ValueError, self.counter.labels, l='x', m='y')
        self.assertRaises(ValueError, self.counter.labels, m='y')
        self.assertRaises(ValueError, self.counter.labels)
        self.two_labels.labels(a='x', b='y').inc()
        self.assertEqual(1, self.registry.get_sample_value('two', {'a': 'x', 'b': 'y'}))
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
        self.assertRaises(ValueError, Counter, 'c', '', labelnames=['^'])
        self.assertRaises(ValueError, Counter, 'c', '', labelnames=['a:b'])
        self.assertRaises(ValueError, Counter, 'c', '', labelnames=['__reserved'])
        self.assertRaises(ValueError, Summary, 'c', '', labelnames=['quantile'])

    def test_empty_labels_list(self):
        h = Histogram('h', 'help', [], registry=self.registry)
        self.assertEqual(0, self.registry.get_sample_value('h_sum'))

    def test_wrapped_original_class(self):
        self.assertEqual(Counter.__wrapped__, Counter('foo', 'bar').__class__)


class TestMetricFamilies(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()

    def custom_collector(self, metric_family):
        class CustomCollector(object):
            def collect(self):
                return [metric_family]
        self.registry.register(CustomCollector())

    def test_counter(self):
        self.custom_collector(CounterMetricFamily('c', 'help', value=1))
        self.assertEqual(1, self.registry.get_sample_value('c', {}))

    def test_counter_labels(self):
        cmf = CounterMetricFamily('c', 'help', labels=['a', 'c'])
        cmf.add_metric(['b', 'd'], 2)
        self.custom_collector(cmf)
        self.assertEqual(2, self.registry.get_sample_value('c', {'a': 'b', 'c': 'd'}))

    def test_gauge(self):
        self.custom_collector(GaugeMetricFamily('g', 'help', value=1))
        self.assertEqual(1, self.registry.get_sample_value('g', {}))

    def test_gauge_labels(self):
        cmf = GaugeMetricFamily('g', 'help', labels=['a'])
        cmf.add_metric(['b'], 2)
        self.custom_collector(cmf)
        self.assertEqual(2, self.registry.get_sample_value('g', {'a':'b'}))

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

    def test_bad_constructors(self):
        self.assertRaises(ValueError, CounterMetricFamily, 'c', 'help', value=1, labels=[])
        self.assertRaises(ValueError, CounterMetricFamily, 'c', 'help', value=1, labels=['a'])

        self.assertRaises(ValueError, GaugeMetricFamily, 'g', 'help', value=1, labels=[])
        self.assertRaises(ValueError, GaugeMetricFamily, 'g', 'help', value=1, labels=['a'])

        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', sum_value=1)
        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', count_value=1)
        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', count_value=1, labels=['a'])
        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', sum_value=1, labels=['a'])
        self.assertRaises(ValueError, SummaryMetricFamily, 's', 'help', count_value=1, sum_value=1, labels=['a'])

        self.assertRaises(ValueError, HistogramMetricFamily, 'h', 'help', sum_value=1)
        self.assertRaises(ValueError, HistogramMetricFamily, 'h', 'help', buckets={})
        self.assertRaises(ValueError, HistogramMetricFamily, 'h', 'help', sum_value=1, labels=['a'])
        self.assertRaises(ValueError, HistogramMetricFamily, 'h', 'help', buckets={}, labels=['a'])
        self.assertRaises(ValueError, HistogramMetricFamily, 'h', 'help', buckets={}, sum_value=1, labels=['a'])
        self.assertRaises(KeyError, HistogramMetricFamily, 'h', 'help', buckets={}, sum_value=1)

    def test_labelnames(self):
        cmf = CounterMetricFamily('c', 'help', labels=iter(['a']))
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
        Counter('c', 'help', registry=registry)
        self.assertRaises(ValueError, Counter, 'c', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'c', 'help', registry=registry)

        Gauge('g', 'help', registry=registry)
        self.assertRaises(ValueError, Gauge, 'g', 'help', registry=registry)
        self.assertRaises(ValueError, Counter, 'g', 'help', registry=registry)

        Summary('s', 'help', registry=registry)
        self.assertRaises(ValueError, Summary, 's', 'help', registry=registry)
        # We don't currently expose quantiles, but let's prevent future
        # clashes anyway.
        self.assertRaises(ValueError, Gauge, 's', 'help', registry=registry)

        Histogram('h', 'help', registry=registry)
        self.assertRaises(ValueError, Histogram, 'h', 'help', registry=registry)
        # Clashes aggaint various suffixes.
        self.assertRaises(ValueError, Summary, 'h', 'help', registry=registry)
        self.assertRaises(ValueError, Counter, 'h_count', 'help', registry=registry)
        self.assertRaises(ValueError, Counter, 'h_sum', 'help', registry=registry)
        self.assertRaises(ValueError, Counter, 'h_bucket', 'help', registry=registry)
        # The name of the histogram itself isn't taken.
        Counter('h', 'help', registry=registry)

    def test_unregister_works(self):
        registry = CollectorRegistry()
        s = Summary('s', 'help', registry=registry)
        self.assertRaises(ValueError, Counter, 's_count', 'help', registry=registry)
        registry.unregister(s)
        Counter('s_count', 'help', registry=registry)

    def custom_collector(self, metric_family, registry):
        class CustomCollector(object):
            def collect(self):
                return [metric_family]
        registry.register(CustomCollector())

    def test_autodescribe_disabled_by_default(self):
        registry = CollectorRegistry()
        self.custom_collector(CounterMetricFamily('c', 'help', value=1), registry)
        self.custom_collector(CounterMetricFamily('c', 'help', value=1), registry)

        registry = CollectorRegistry(auto_describe=True)
        self.custom_collector(CounterMetricFamily('c', 'help', value=1), registry)
        self.assertRaises(ValueError, self.custom_collector, CounterMetricFamily('c', 'help', value=1), registry)

    def test_restricted_registry(self):
        registry = CollectorRegistry()
        Counter('c', 'help', registry=registry)
        Summary('s', 'help', registry=registry).observe(7)

        m = Metric('s', 'help', 'summary')
        m.samples = [('s_sum', {}, 7)]
        self.assertEquals([m], registry.restricted_registry(['s_sum']).collect())


if __name__ == '__main__':
    unittest.main()
