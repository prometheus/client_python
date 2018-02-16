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
    GaugeMetricFamily,
    HistogramMetricFamily,
    Metric,
    SummaryMetricFamily,
)
from prometheus_client.exposition import (
    generate_latest,
)
from prometheus_client.parser import (
    text_string_to_metric_families,
)


class TestParse(unittest.TestCase):

    def test_simple_counter(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a 1
""")
        self.assertEqual([CounterMetricFamily("a", "help", value=1)], list(families))

    def test_simple_gauge(self):
        families = text_string_to_metric_families("""# TYPE a gauge
# HELP a help
a 1
""")
        self.assertEqual([GaugeMetricFamily("a", "help", value=1)], list(families))

    def test_simple_summary(self):
        families = text_string_to_metric_families("""# TYPE a summary
# HELP a help
a_count 1
a_sum 2
""")

    def test_summary_quantiles(self):
        families = text_string_to_metric_families("""# TYPE a summary
# HELP a help
a_count 1
a_sum 2
a{quantile="0.5"} 0.7
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
""")
        self.assertEqual([HistogramMetricFamily("a", "help", sum_value=2, buckets=[("1", 0.0), ("+Inf", 3.0)])], list(families))

    def test_no_metadata(self):
        families = text_string_to_metric_families("""a 1
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
""")
        m = Metric("redis_connected_clients", "Redis connected clients", "untyped")
        m.samples = [
            ("redis_connected_clients", {"instance": "rough-snowflake-web", "port": "6380"}, 10),
            ("redis_connected_clients", {"instance": "rough-snowflake-web", "port": "6381"}, 12),
        ]
        self.assertEqual([m], list(families))


    def test_type_help_switched(self):
        families = text_string_to_metric_families("""# HELP a help
# TYPE a counter
a 1
""")
        self.assertEqual([CounterMetricFamily("a", "help", value=1)], list(families))

    def test_blank_lines_and_comments(self):
        families = text_string_to_metric_families("""
# TYPE a counter
# FOO a
# BAR b
# HELP a help

a 1
""")
        self.assertEqual([CounterMetricFamily("a", "help", value=1)], list(families))

    def test_tabs(self):
        families = text_string_to_metric_families("""#\tTYPE\ta\tcounter
#\tHELP\ta\thelp
a\t1
""")
        self.assertEqual([CounterMetricFamily("a", "help", value=1)], list(families))

    def test_empty_help(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a
a 1
""")
        self.assertEqual([CounterMetricFamily("a", "", value=1)], list(families))

    def test_labels_and_infinite(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a{foo="bar"} +Inf
a{foo="baz"} -Inf
""")
        metric_family = CounterMetricFamily("a", "help", labels=["foo"])
        metric_family.add_metric(["bar"], float('inf'))
        metric_family.add_metric(["baz"], float('-inf'))
        self.assertEqual([metric_family], list(families))

    def test_spaces(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a{ foo = "bar" } 1
a\t\t{\t\tfoo\t\t=\t\t"baz"\t\t}\t\t2
""")
        metric_family = CounterMetricFamily("a", "help", labels=["foo"])
        metric_family.add_metric(["bar"], 1)
        metric_family.add_metric(["baz"], 2)
        self.assertEqual([metric_family], list(families))

    def test_commas(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a{foo="bar",} 1
# TYPE b counter
# HELP b help
b{,} 2
""")
        a = CounterMetricFamily("a", "help", labels=["foo"])
        a.add_metric(["bar"], 1)
        b = CounterMetricFamily("b", "help", value=2)
        self.assertEqual([a, b], list(families))

    def test_empty_brackets(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a{} 1
""")
        self.assertEqual([CounterMetricFamily("a", "help", value=1)], list(families))

    def test_nan(self):
        families = text_string_to_metric_families("""a NaN
""")
        # Can't use a simple comparison as nan != nan.
        self.assertTrue(math.isnan(list(families)[0].samples[0][2]))

    def test_escaping(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a he\\n\\\\l\\tp
a{foo="b\\"a\\nr"} 1
a{foo="b\\\\a\\z"} 2
""")
        metric_family = CounterMetricFamily("a", "he\n\\l\\tp", labels=["foo"])
        metric_family.add_metric(["b\"a\nr"], 1)
        metric_family.add_metric(["b\\a\\z"], 2)
        self.assertEqual([metric_family], list(families))

    def test_timestamps_discarded(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a{foo="bar"} 1\t000
# TYPE b counter
# HELP b help
b 2  1234567890
""")
        a = CounterMetricFamily("a", "help", labels=["foo"])
        a.add_metric(["bar"], 1)
        b = CounterMetricFamily("b", "help", value=2)
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
# HELP process_cpu_seconds_total Total user and system CPU time spent in seconds.
# TYPE process_cpu_seconds_total counter
process_cpu_seconds_total 29323.4
# HELP process_virtual_memory_bytes Virtual memory size in bytes.
# TYPE process_virtual_memory_bytes gauge
process_virtual_memory_bytes 2478268416.0
# HELP prometheus_build_info A metric with a constant '1' value labeled by version, revision, and branch from which Prometheus was built.
# TYPE prometheus_build_info gauge
prometheus_build_info{branch="HEAD",revision="ef176e5",version="0.16.0rc1"} 1.0
# HELP prometheus_local_storage_chunk_ops_total The total number of chunk operations by their type.
# TYPE prometheus_local_storage_chunk_ops_total counter
prometheus_local_storage_chunk_ops_total{type="clone"} 28.0
prometheus_local_storage_chunk_ops_total{type="create"} 997844.0
prometheus_local_storage_chunk_ops_total{type="drop"} 1345758.0
prometheus_local_storage_chunk_ops_total{type="load"} 1641.0
prometheus_local_storage_chunk_ops_total{type="persist"} 981408.0
prometheus_local_storage_chunk_ops_total{type="pin"} 32662.0
prometheus_local_storage_chunk_ops_total{type="transcode"} 980180.0
prometheus_local_storage_chunk_ops_total{type="unpin"} 32662.0
"""
        families = list(text_string_to_metric_families(text))

        class TextCollector(object):
            def collect(self):
                return families


        registry = CollectorRegistry()
        registry.register(TextCollector())
        self.assertEqual(text.encode('utf-8'), generate_latest(registry))



if __name__ == '__main__':
    unittest.main()
