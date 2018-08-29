from __future__ import unicode_literals

import math
import sys

if sys.version_info < (2, 7):
    # We need the skip decorators from unittest2 on Python 2.6.
    import unittest2 as unittest
else:
    import unittest

from prometheus_client.core import (
    CollectorRegistry,
    CounterMetricFamily,
    Exemplar,
    GaugeMetricFamily,
    HistogramMetricFamily,
    Metric,
    Sample,
    SummaryMetricFamily,
    Timestamp,
)
from prometheus_client.openmetrics.exposition import (
    generate_latest,
)
from prometheus_client.openmetrics.parser import (
    text_string_to_metric_families,
)


class TestParse(unittest.TestCase):

    def test_simple_counter(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total 1
# EOF
""")
        self.assertEqual([CounterMetricFamily("a", "help", value=1)], list(families))

    def test_uint64_counter(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total 9223372036854775808
# EOF
""")
        self.assertEqual([CounterMetricFamily("a", "help", value=9223372036854775808)], list(families))

    def test_simple_gauge(self):
        families = text_string_to_metric_families("""# TYPE a gauge
# HELP a help
a 1
# EOF
""")
        self.assertEqual([GaugeMetricFamily("a", "help", value=1)], list(families))

    def test_float_gauge(self):
        families = text_string_to_metric_families("""# TYPE a gauge
# HELP a help
a 1.2
# EOF
""")
        self.assertEqual([GaugeMetricFamily("a", "help", value=1.2)], list(families))

    def test_unit_gauge(self):
        families = text_string_to_metric_families("""# TYPE a_seconds gauge
# UNIT a_seconds seconds
# HELP a_seconds help
a_seconds 1
# EOF
""")
        self.assertEqual([GaugeMetricFamily("a_seconds", "help", value=1, unit='seconds')], list(families))

    def test_simple_summary(self):
        families = text_string_to_metric_families("""# TYPE a summary
# HELP a help
a_count 1
a_sum 2
# EOF
""")
        summary = SummaryMetricFamily("a", "help", count_value=1, sum_value=2)
        self.assertEqual([summary], list(families))

    def test_summary_quantiles(self):
        families = text_string_to_metric_families("""# TYPE a summary
# HELP a help
a_count 1
a_sum 2
a{quantile="0.5"} 0.7
# EOF
""")
        # The Python client doesn't support quantiles, but we
        # still need to be able to parse them.
        metric_family = SummaryMetricFamily("a", "help", count_value=1, sum_value=2)
        metric_family.add_sample("a", {"quantile": "0.5"}, 0.7)
        self.assertEqual([metric_family], list(families))

    def test_simple_histogram(self):
        families = text_string_to_metric_families("""# TYPE a histogram
# HELP a help
a_bucket{le="1"} 0
a_bucket{le="+Inf"} 3
a_count 3
a_sum 2
# EOF
""")
        self.assertEqual([HistogramMetricFamily("a", "help", sum_value=2, buckets=[("1", 0.0), ("+Inf", 3.0)])], list(families))

    def test_histogram_exemplars(self):
        families = text_string_to_metric_families("""# TYPE a histogram
# HELP a help
a_bucket{le="1"} 0 # {a="b"} 0.5
a_bucket{le="2"} 2 123 # {a="c"} 0.5
a_bucket{le="+Inf"} 3 # {a="d"} 4 123
# EOF
""")
        hfm = HistogramMetricFamily("a", "help")
        hfm.add_sample("a_bucket", {"le": "1"}, 0.0, None, Exemplar({"a": "b"}, 0.5))
        hfm.add_sample("a_bucket", {"le": "2"}, 2.0, Timestamp(123, 0), Exemplar({"a": "c"}, 0.5)), 
        hfm.add_sample("a_bucket", {"le": "+Inf"}, 3.0, None, Exemplar({"a": "d"}, 4, Timestamp(123, 0)))
        self.assertEqual([hfm], list(families))

    def test_no_metadata(self):
        families = text_string_to_metric_families("""a 1
# EOF
""")
        metric_family = Metric("a", "", "untyped")
        metric_family.add_sample("a", {}, 1)
        self.assertEqual([metric_family], list(families))

    def test_untyped(self):
        # https://github.com/prometheus/client_python/issues/79
        families = text_string_to_metric_families("""# HELP redis_connected_clients Redis connected clients
# TYPE redis_connected_clients untyped
redis_connected_clients{instance="rough-snowflake-web",port="6380"} 10.0
redis_connected_clients{instance="rough-snowflake-web",port="6381"} 12.0
# EOF
""")
        m = Metric("redis_connected_clients", "Redis connected clients", "untyped")
        m.samples = [
            Sample("redis_connected_clients", {"instance": "rough-snowflake-web", "port": "6380"}, 10),
            Sample("redis_connected_clients", {"instance": "rough-snowflake-web", "port": "6381"}, 12),
        ]
        self.assertEqual([m], list(families))

    def test_type_help_switched(self):
        families = text_string_to_metric_families("""# HELP a help
# TYPE a counter
a_total 1
# EOF
""")
        self.assertEqual([CounterMetricFamily("a", "help", value=1)], list(families))

    def test_labels_with_curly_braces(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total{foo="bar",bar="b{a}z"} 1
# EOF
""")
        metric_family = CounterMetricFamily("a", "help", labels=["foo", "bar"])
        metric_family.add_metric(["bar", "b{a}z"], 1)
        self.assertEqual([metric_family], list(families))

    def test_empty_help(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a 
a_total 1
# EOF
""")
        self.assertEqual([CounterMetricFamily("a", "", value=1)], list(families))

    def test_labels_and_infinite(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total{foo="bar"} +Inf
a_total{foo="baz"} -Inf
# EOF
""")
        metric_family = CounterMetricFamily("a", "help", labels=["foo"])
        metric_family.add_metric(["bar"], float('inf'))
        metric_family.add_metric(["baz"], float('-inf'))
        self.assertEqual([metric_family], list(families))

    def test_empty_brackets(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total{} 1
# EOF
""")
        self.assertEqual([CounterMetricFamily("a", "help", value=1)], list(families))

    def test_nan(self):
        families = text_string_to_metric_families("""a NaN
# EOF
""")
        self.assertTrue(math.isnan(list(families)[0].samples[0][2]))

    def test_no_newline_after_eof(self):
        families = text_string_to_metric_families("""# TYPE a gauge
# HELP a help
a 1
# EOF""")
        self.assertEqual([GaugeMetricFamily("a", "help", value=1)], list(families))

    def test_empty_label(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total{foo="bar"} 1
a_total{foo=""} 2
# EOF
""")
        metric_family = CounterMetricFamily("a", "help", labels=["foo"])
        metric_family.add_metric(["bar"], 1)
        metric_family.add_metric([""], 2)
        self.assertEqual([metric_family], list(families))

    def test_label_escaping(self):
        for escaped_val, unescaped_val in [
                ('foo', 'foo'),
                ('\\foo', '\\foo'),
                ('\\\\foo', '\\foo'),
                ('foo\\\\', 'foo\\'),
                ('\\\\', '\\'),
                ('\\n', '\n'),
                ('\\\\n', '\\n'),
                ('\\\\\\n', '\\\n'),
                ('\\"', '"'),
                ('\\\\\\"', '\\"')]:
            families = list(text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total{foo="%s",bar="baz"} 1
# EOF
""" % escaped_val))
            metric_family = CounterMetricFamily(
                "a", "help", labels=["foo", "bar"])
            metric_family.add_metric([unescaped_val, "baz"], 1)
            self.assertEqual([metric_family], list(families))

    def test_help_escaping(self):
        for escaped_val, unescaped_val in [
                ('foo', 'foo'),
                ('\\foo', '\\foo'),
                ('\\\\foo', '\\foo'),
                ('foo\\', 'foo\\'),
                ('foo\\\\', 'foo\\'),
                ('\\n', '\n'),
                ('\\\\n', '\\n'),
                ('\\\\\\n', '\\\n'),
                ('\\"', '"'),
                ('\\\\"', '\\"'),
                ('\\\\\\"', '\\"')]:
            families = list(text_string_to_metric_families("""# TYPE a counter
# HELP a %s
a_total{foo="bar"} 1
# EOF
""" % escaped_val))
            metric_family = CounterMetricFamily("a", unescaped_val, labels=["foo"])
            metric_family.add_metric(["bar"], 1)
            self.assertEqual([metric_family], list(families))

    def test_escaping(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a he\\n\\\\l\\tp
a_total{foo="b\\"a\\nr"} 1
a_total{foo="b\\\\a\\z"} 2
# EOF
""")
        metric_family = CounterMetricFamily("a", "he\n\\l\\tp", labels=["foo"])
        metric_family.add_metric(["b\"a\nr"], 1)
        metric_family.add_metric(["b\\a\\z"], 2)
        self.assertEqual([metric_family], list(families))

    def test_timestamps(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total{foo="1"} 1 000
a_total{foo="2"} 1 0.0
a_total{foo="3"} 1 1.1
a_total{foo="4"} 1 12345678901234567890.1234567890
a_total{foo="5"} 1 1.5e3
# TYPE b counter
# HELP b help
b_total 2 1234567890
# EOF
""")
        a = CounterMetricFamily("a", "help", labels=["foo"])
        a.add_metric(["1"], 1, timestamp=Timestamp(0, 0))
        a.add_metric(["2"], 1, timestamp=Timestamp(0, 0))
        a.add_metric(["3"], 1, timestamp=Timestamp(1, 100000000))
        a.add_metric(["4"], 1, timestamp=Timestamp(12345678901234567890, 123456789))
        a.add_metric(["5"], 1, timestamp=1500.0)
        b = CounterMetricFamily("b", "help")
        b.add_metric([], 2, timestamp=Timestamp(1234567890, 0))
        self.assertEqual([a, b], list(families))

    @unittest.skipIf(sys.version_info < (2, 7), "Test requires Python 2.7+.")
    def test_roundtrip(self):
        text = """# HELP go_gc_duration_seconds A summary of the GC invocation durations.
# TYPE go_gc_duration_seconds summary
go_gc_duration_seconds{quantile="0"} 0.013300656000000001
go_gc_duration_seconds{quantile="0.25"} 0.013638736
go_gc_duration_seconds{quantile="0.5"} 0.013759906
go_gc_duration_seconds{quantile="0.75"} 0.013962066
go_gc_duration_seconds{quantile="1"} 0.021383540000000003
go_gc_duration_seconds_sum 56.12904785
go_gc_duration_seconds_count 7476.0
# HELP go_goroutines Number of goroutines that currently exist.
# TYPE go_goroutines gauge
go_goroutines 166.0
# HELP prometheus_local_storage_indexing_batch_duration_milliseconds Quantiles for batch indexing duration in milliseconds.
# TYPE prometheus_local_storage_indexing_batch_duration_milliseconds summary
prometheus_local_storage_indexing_batch_duration_milliseconds{quantile="0.5"} NaN
prometheus_local_storage_indexing_batch_duration_milliseconds{quantile="0.9"} NaN
prometheus_local_storage_indexing_batch_duration_milliseconds{quantile="0.99"} NaN
prometheus_local_storage_indexing_batch_duration_milliseconds_sum 871.5665949999999
prometheus_local_storage_indexing_batch_duration_milliseconds_count 229.0
# HELP process_cpu_seconds Total user and system CPU time spent in seconds.
# TYPE process_cpu_seconds counter
process_cpu_seconds_total 29323.4
# HELP process_virtual_memory_bytes Virtual memory size in bytes.
# TYPE process_virtual_memory_bytes gauge
process_virtual_memory_bytes 2478268416.0
# HELP prometheus_build_info A metric with a constant '1' value labeled by version, revision, and branch from which Prometheus was built.
# TYPE prometheus_build_info gauge
prometheus_build_info{branch="HEAD",revision="ef176e5",version="0.16.0rc1"} 1.0
# HELP prometheus_local_storage_chunk_ops The total number of chunk operations by their type.
# TYPE prometheus_local_storage_chunk_ops counter
prometheus_local_storage_chunk_ops_total{type="clone"} 28.0
prometheus_local_storage_chunk_ops_total{type="create"} 997844.0
prometheus_local_storage_chunk_ops_total{type="drop"} 1345758.0
prometheus_local_storage_chunk_ops_total{type="load"} 1641.0
prometheus_local_storage_chunk_ops_total{type="persist"} 981408.0
prometheus_local_storage_chunk_ops_total{type="pin"} 32662.0
prometheus_local_storage_chunk_ops_total{type="transcode"} 980180.0
prometheus_local_storage_chunk_ops_total{type="unpin"} 32662.0
# EOF
"""
        families = list(text_string_to_metric_families(text))

        class TextCollector(object):
            def collect(self):
                return families

        registry = CollectorRegistry()
        registry.register(TextCollector())
        self.assertEqual(text.encode('utf-8'), generate_latest(registry))

    def test_invalid_input(self):
        for case in [
                # No EOF.
                (''),
                # Text after EOF.
                ('a 1\n# EOF\nblah'),
                ('a 1\n# EOFblah'),
                # Missing or wrong quotes on label value.
                ('a{a=1} 1\n# EOF\n'),
                ('a{a="1} 1\n# EOF\n'),
                ('a{a=\'1\'} 1\n# EOF\n'),
                # Missing or extra commas.
                ('a{a="1"b="2"} 1\n# EOF\n'),
                ('a{a="1",,b="2"} 1\n# EOF\n'),
                ('a{a="1",b="2",} 1\n# EOF\n'),
                # Missing value.
                ('a\n# EOF\n'),
                ('a \n# EOF\n'),
                # Bad HELP.
                ('# HELP\n# EOF\n'),
                ('# HELP \n# EOF\n'),
                ('# HELP a\n# EOF\n'),
                ('# HELP a\t\n# EOF\n'),
                (' # HELP a meh\n# EOF\n'),
                # Bad TYPE.
                ('# TYPE\n# EOF\n'),
                ('# TYPE \n# EOF\n'),
                ('# TYPE a\n# EOF\n'),
                ('# TYPE a\t\n# EOF\n'),
                ('# TYPE a meh\n# EOF\n'),
                ('# TYPE a meh \n# EOF\n'),
                ('# TYPE a gauge \n# EOF\n'),
                # Bad UNIT.
                ('# UNIT\n# EOF\n'),
                ('# UNIT \n# EOF\n'),
                ('# UNIT a\n# EOF\n'),
                ('# UNIT a\t\n# EOF\n'),
                ('# UNIT a seconds\n# EOF\n'),
                ('# UNIT a_seconds seconds \n# EOF\n'),
                ('# TYPE x_u info\n# UNIT x_u u\n# EOF\n'),
                ('# TYPE x_u stateset\n# UNIT x_u u\n# EOF\n'),
                # Bad metric names.
                ('0a 1\n# EOF\n'),
                ('a.b 1\n# EOF\n'),
                ('a-b 1\n# EOF\n'),
                # Bad value.
                ('a a\n# EOF\n'),
                ('a  1\n# EOF\n'),
                ('a 1\t\n# EOF\n'),
                ('a 1 \n# EOF\n'),
                # Bad timestamp.
                ('a 1 z\n# EOF\n'),
                ('a 1 1z\n# EOF\n'),
                ('a 1 1.1.1\n# EOF\n'),
                # Bad exemplars.
                ('# TYPE a histogram\na_bucket{le="+Inf"} 1 #\n# EOF\n'),
                ('# TYPE a histogram\na_bucket{le="+Inf"} 1# {} 1\n# EOF\n'),
                ('# TYPE a histogram\na_bucket{le="+Inf"} 1 #{} 1\n# EOF\n'),
                ('# TYPE a histogram\na_bucket{le="+Inf"} 1 # {}1\n# EOF\n'),
                ('# TYPE a histogram\na_bucket{le="+Inf"} 1 # {} 1 \n# EOF\n'),
                ('# TYPE a histogram\na_bucket{le="+Inf"} 1 # {} 1 1 \n# EOF\n'),
                ]:
            with self.assertRaises(ValueError):
                list(text_string_to_metric_families(case))


if __name__ == '__main__':
    unittest.main()
