import math
import unittest

from prometheus_client.core import (
    CollectorRegistry, CounterMetricFamily, Exemplar,
    GaugeHistogramMetricFamily, GaugeMetricFamily, HistogramMetricFamily,
    InfoMetricFamily, Metric, Sample, StateSetMetricFamily,
    SummaryMetricFamily, Timestamp,
)
from prometheus_client.openmetrics.exposition import generate_latest
from prometheus_client.openmetrics.parser import text_string_to_metric_families


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

    def test_leading_zeros_simple_gauge(self):
        families = text_string_to_metric_families("""# TYPE a gauge
# HELP a help
a 0000000000000000000000000000000000000000001
# EOF
""")
        self.assertEqual([GaugeMetricFamily("a", "help", value=1)], list(families))

    def test_leading_zeros_float_gauge(self):
        families = text_string_to_metric_families("""# TYPE a gauge
# HELP a help
a 0000000000000000000000000000000000000000001.2e-1
# EOF
""")
        self.assertEqual([GaugeMetricFamily("a", "help", value=.12)], list(families))

    def test_nan_gauge(self):
        families = text_string_to_metric_families("""# TYPE a gauge
# HELP a help
a NaN
# EOF
""")
        self.assertTrue(math.isnan(list(families)[0].samples[0].value))

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
a{quantile="1"} 0.8
# EOF
""")
        # The Python client doesn't support quantiles, but we
        # still need to be able to parse them.
        metric_family = SummaryMetricFamily("a", "help", count_value=1, sum_value=2)
        metric_family.add_sample("a", {"quantile": "0.5"}, 0.7)
        metric_family.add_sample("a", {"quantile": "1"}, 0.8)
        self.assertEqual([metric_family], list(families))

    def test_simple_histogram(self):
        families = text_string_to_metric_families("""# TYPE a histogram
# HELP a help
a_bucket{le="1.0"} 0
a_bucket{le="+Inf"} 3
a_count 3
a_sum 2
# EOF
""")
        self.assertEqual([HistogramMetricFamily("a", "help", sum_value=2, buckets=[("1.0", 0.0), ("+Inf", 3.0)])],
                         list(families))

    def test_simple_histogram_float_values(self):
        families = text_string_to_metric_families("""# TYPE a histogram
# HELP a help
a_bucket{le="1.0"} 0.0
a_bucket{le="+Inf"} 3.0
a_count 3.0
a_sum 2.0
# EOF
""")
        self.assertEqual([HistogramMetricFamily("a", "help", sum_value=2, buckets=[("1.0", 0.0), ("+Inf", 3.0)])],
                         list(families))

    def test_histogram_noncanonical(self):
        families = text_string_to_metric_families("""# TYPE a histogram
# HELP a help
a_bucket{le="0"} 0
a_bucket{le="0.00000000001"} 0
a_bucket{le="0.0000000001"} 0
a_bucket{le="1e-04"} 0
a_bucket{le="1.1e-4"} 0
a_bucket{le="1.1e-3"} 0
a_bucket{le="1.1e-2"} 0
a_bucket{le="1"} 0
a_bucket{le="1e+05"} 0
a_bucket{le="10000000000"} 0
a_bucket{le="100000000000.0"} 0
a_bucket{le="+Inf"} 3
a_count 3
a_sum 2
# EOF
""")
        list(families)

    def test_negative_bucket_histogram(self):
        families = text_string_to_metric_families("""# TYPE a histogram
# HELP a help
a_bucket{le="-1.0"} 0
a_bucket{le="1.0"} 1
a_bucket{le="+Inf"} 3
# EOF
""")
        self.assertEqual([HistogramMetricFamily("a", "help", buckets=[("-1.0", 0.0), ("1.0", 1.0), ("+Inf", 3.0)])],
                         list(families))

    def test_histogram_exemplars(self):
        families = text_string_to_metric_families("""# TYPE a histogram
# HELP a help
a_bucket{le="1.0"} 0 # {a="b"} 0.5
a_bucket{le="2.0"} 2 # {a="c"} 0.5
a_bucket{le="+Inf"} 3 # {a="2345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678"} 4 123
# EOF
""")
        hfm = HistogramMetricFamily("a", "help")
        hfm.add_sample("a_bucket", {"le": "1.0"}, 0.0, None, Exemplar({"a": "b"}, 0.5))
        hfm.add_sample("a_bucket", {"le": "2.0"}, 2.0, None, Exemplar({"a": "c"}, 0.5)),
        hfm.add_sample("a_bucket", {"le": "+Inf"}, 3.0, None,
                       Exemplar({"a": "2345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678"}, 4,
                                Timestamp(123, 0)))
        self.assertEqual([hfm], list(families))

    def test_simple_gaugehistogram(self):
        families = text_string_to_metric_families("""# TYPE a gaugehistogram
# HELP a help
a_bucket{le="1.0"} 0
a_bucket{le="+Inf"} 3
a_gcount 3
a_gsum 2
# EOF
""")
        self.assertEqual([GaugeHistogramMetricFamily("a", "help", gsum_value=2, buckets=[("1.0", 0.0), ("+Inf", 3.0)])],
                         list(families))

    def test_negative_bucket_gaugehistogram(self):
        families = text_string_to_metric_families("""# TYPE a gaugehistogram
# HELP a help
a_bucket{le="-1.0"} 1
a_bucket{le="1.0"} 2
a_bucket{le="+Inf"} 3
a_gcount 3
a_gsum -5
# EOF
""")
        self.assertEqual([GaugeHistogramMetricFamily("a", "help", gsum_value=-5, buckets=[("-1.0", 1.0), ("1.0", 2.0), ("+Inf", 3.0)])],
                         list(families))

    def test_gaugehistogram_exemplars(self):
        families = text_string_to_metric_families("""# TYPE a gaugehistogram
# HELP a help
a_bucket{le="1.0"} 0 123 # {a="b"} 0.5
a_bucket{le="2.0"} 2 123 # {a="c"} 0.5
a_bucket{le="+Inf"} 3 123 # {a="d"} 4 123
# EOF
""")
        hfm = GaugeHistogramMetricFamily("a", "help")
        hfm.add_sample("a_bucket", {"le": "1.0"}, 0.0, Timestamp(123, 0), Exemplar({"a": "b"}, 0.5))
        hfm.add_sample("a_bucket", {"le": "2.0"}, 2.0, Timestamp(123, 0), Exemplar({"a": "c"}, 0.5)),
        hfm.add_sample("a_bucket", {"le": "+Inf"}, 3.0, Timestamp(123, 0), Exemplar({"a": "d"}, 4, Timestamp(123, 0)))
        self.assertEqual([hfm], list(families))

    def test_counter_exemplars(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total 0 123 # {a="b"} 0.5
# EOF
""")
        cfm = CounterMetricFamily("a", "help")
        cfm.add_sample("a_total", {}, 0.0, Timestamp(123, 0), Exemplar({"a": "b"}, 0.5))
        self.assertEqual([cfm], list(families))

    def test_counter_exemplars_empty_brackets(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total{} 0 123 # {a="b"} 0.5
# EOF
""")
        cfm = CounterMetricFamily("a", "help")
        cfm.add_sample("a_total", {}, 0.0, Timestamp(123, 0), Exemplar({"a": "b"}, 0.5))
        self.assertEqual([cfm], list(families))

    def test_simple_info(self):
        families = text_string_to_metric_families("""# TYPE a info
# HELP a help
a_info{foo="bar"} 1
# EOF
""")
        self.assertEqual([InfoMetricFamily("a", "help", {'foo': 'bar'})], list(families))

    def test_info_timestamps(self):
        families = text_string_to_metric_families("""# TYPE a info
# HELP a help
a_info{a="1",foo="bar"} 1 1
a_info{a="2",foo="bar"} 1 0
# EOF
""")
        imf = InfoMetricFamily("a", "help")
        imf.add_sample("a_info", {"a": "1", "foo": "bar"}, 1, Timestamp(1, 0))
        imf.add_sample("a_info", {"a": "2", "foo": "bar"}, 1, Timestamp(0, 0))
        self.assertEqual([imf], list(families))

    def test_simple_stateset(self):
        families = text_string_to_metric_families("""# TYPE a stateset
# HELP a help
a{a="bar"} 0
a{a="foo"} 1.0
# EOF
""")
        self.assertEqual([StateSetMetricFamily("a", "help", {'foo': True, 'bar': False})], list(families))

    def test_duplicate_timestamps(self):
        families = text_string_to_metric_families("""# TYPE a gauge
# HELP a help
a{a="1",foo="bar"} 1 0.0000000000
a{a="1",foo="bar"} 2 0.0000000001
a{a="1",foo="bar"} 3 0.0000000010
a{a="2",foo="bar"} 4 0.0000000000
a{a="2",foo="bar"} 5 0.0000000001
# EOF
""")
        imf = GaugeMetricFamily("a", "help")
        imf.add_sample("a", {"a": "1", "foo": "bar"}, 1, Timestamp(0, 0))
        imf.add_sample("a", {"a": "1", "foo": "bar"}, 3, Timestamp(0, 1))
        imf.add_sample("a", {"a": "2", "foo": "bar"}, 4, Timestamp(0, 0))
        self.assertEqual([imf], list(families))

    def test_no_metadata(self):
        families = text_string_to_metric_families("""a 1
# EOF
""")
        metric_family = Metric("a", "", "untyped")
        metric_family.add_sample("a", {}, 1)
        self.assertEqual([metric_family], list(families))

    def test_empty_metadata(self):
        families = text_string_to_metric_families("""# HELP a 
# UNIT a 
# EOF
""")
        metric_family = Metric("a", "", "untyped")
        self.assertEqual([metric_family], list(families))

    def test_untyped(self):
        # https://github.com/prometheus/client_python/issues/79
        families = text_string_to_metric_families("""# HELP redis_connected_clients Redis connected clients
# TYPE redis_connected_clients unknown
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
        families = text_string_to_metric_families("""# TYPE a gauge
# HELP a help
a{foo="bar"} +Inf
a{foo="baz"} -Inf
# EOF
""")
        metric_family = GaugeMetricFamily("a", "help", labels=["foo"])
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
        for escaped_val, unescaped_val in [('foo', 'foo'), ('\\foo', '\\foo'), ('\\\\foo', '\\foo'),
                                           ('foo\\\\', 'foo\\'), ('\\\\', '\\'), ('\\n', '\n'),
                                           ('\\\\n', '\\n'), ('\\\\\\n', '\\\n'), ('\\"', '"'), ('\\\\\\"', '\\"')]:
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
a_total{foo="b\\"a\\nr # "} 3
a_total{foo="b\\\\a\\z # "} 4
# EOF
""")
        metric_family = CounterMetricFamily("a", "he\n\\l\\tp", labels=["foo"])
        metric_family.add_metric(["b\"a\nr"], 1)
        metric_family.add_metric(["b\\a\\z"], 2)
        metric_family.add_metric(["b\"a\nr # "], 3)
        metric_family.add_metric(["b\\a\\z # "], 4)
        self.assertEqual([metric_family], list(families))

    def test_null_byte(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a he\0lp
# EOF
""")
        metric_family = CounterMetricFamily("a", "he\0lp")
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

    def test_hash_in_label_value(self):
        families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total{foo="foo # bar"} 1
a_total{foo="} foo # bar # "} 1
# EOF
""")
        a = CounterMetricFamily("a", "help", labels=["foo"])
        a.add_metric(["foo # bar"], 1)
        a.add_metric(["} foo # bar # "], 1)
        self.assertEqual([a], list(families))

    def test_exemplars_with_hash_in_label_values(self):
        families = text_string_to_metric_families("""# TYPE a histogram
# HELP a help
a_bucket{le="1.0",foo="bar # "} 0 # {a="b",foo="bar # bar"} 0.5
a_bucket{le="2.0",foo="bar # "} 2 # {a="c",foo="bar # bar"} 0.5
a_bucket{le="+Inf",foo="bar # "} 3 # {a="d",foo="bar # bar"} 4
# EOF
""")
        hfm = HistogramMetricFamily("a", "help")
        hfm.add_sample("a_bucket", {"le": "1.0", "foo": "bar # "}, 0.0, None, Exemplar({"a": "b", "foo": "bar # bar"}, 0.5))
        hfm.add_sample("a_bucket", {"le": "2.0", "foo": "bar # "}, 2.0, None, Exemplar({"a": "c", "foo": "bar # bar"}, 0.5))
        hfm.add_sample("a_bucket", {"le": "+Inf", "foo": "bar # "}, 3.0, None, Exemplar({"a": "d", "foo": "bar # bar"}, 4))
        self.assertEqual([hfm], list(families))

    def test_fallback_to_state_machine_label_parsing(self):
        from unittest.mock import patch

        from prometheus_client.openmetrics.parser import _parse_sample

        parse_sample_function = "prometheus_client.openmetrics.parser._parse_sample"
        parse_labels_function = "prometheus_client.openmetrics.parser._parse_labels"
        parse_remaining_function = "prometheus_client.openmetrics.parser._parse_remaining_text"
        state_machine_function = "prometheus_client.openmetrics.parser._parse_labels_with_state_machine"

        parse_sample_return_value = Sample("a_total", {"foo": "foo # bar"}, 1)
        with patch(parse_sample_function, return_value=parse_sample_return_value) as mock:
            families = text_string_to_metric_families("""# TYPE a counter
# HELP a help
a_total{foo="foo # bar"} 1
# EOF
""")
            a = CounterMetricFamily("a", "help", labels=["foo"])
            a.add_metric(["foo # bar"], 1)
            self.assertEqual([a], list(families))
            mock.assert_called_once_with('a_total{foo="foo # bar"} 1')

        # First fallback case
        state_machine_return_values = [{"foo": "foo # bar"}, len('foo="foo # bar"}')]
        parse_remaining_values = [1, None, None]
        with patch(parse_labels_function) as mock1:
            with patch(state_machine_function, return_value=state_machine_return_values) as mock2:
                with patch(parse_remaining_function, return_value=parse_remaining_values) as mock3:
                    sample = _parse_sample('a_total{foo="foo # bar"} 1')
                    s = Sample("a_total", {"foo": "foo # bar"}, 1)
                    self.assertEqual(s, sample)
                    mock1.assert_not_called()
                    mock2.assert_called_once_with('foo="foo # bar"} 1')
                    mock3.assert_called_once_with('1')

        # Second fallback case
        state_machine_return_values = [{"le": "1.0"}, len('le="1.0"}')]
        parse_remaining_values = [0.0, Timestamp(123, 0), Exemplar({"a": "b"}, 0.5)]
        with patch(parse_labels_function) as mock1:
            with patch(state_machine_function, return_value=state_machine_return_values) as mock2:
                with patch(parse_remaining_function, return_value=parse_remaining_values) as mock3:
                    sample = _parse_sample('a_bucket{le="1.0"} 0 123 # {a="b"} 0.5')
                    s = Sample("a_bucket", {"le": "1.0"}, 0.0, Timestamp(123, 0), Exemplar({"a": "b"}, 0.5))
                    self.assertEqual(s, sample)
                    mock1.assert_not_called()
                    mock2.assert_called_once_with('le="1.0"} 0 123 # {a="b"} 0.5')
                    mock3.assert_called_once_with('0 123 # {a="b"} 0.5')

        # No need to fallback case
        parse_labels_return_values = {"foo": "foo#bar"}
        parse_remaining_values = [1, None, None]
        with patch(parse_labels_function, return_value=parse_labels_return_values) as mock1:
            with patch(state_machine_function) as mock2:
                with patch(parse_remaining_function, return_value=parse_remaining_values) as mock3:
                    sample = _parse_sample('a_total{foo="foo#bar"} 1')
                    s = Sample("a_total", {"foo": "foo#bar"}, 1)
                    self.assertEqual(s, sample)
                    mock1.assert_called_once_with('foo="foo#bar"')
                    mock2.assert_not_called()
                    mock3.assert_called_once_with('1')

    def test_roundtrip(self):
        text = """# HELP go_gc_duration_seconds A summary of the GC invocation durations.
# TYPE go_gc_duration_seconds summary
go_gc_duration_seconds{quantile="0.0"} 0.013300656000000001
go_gc_duration_seconds{quantile="0.25"} 0.013638736
go_gc_duration_seconds{quantile="0.5"} 0.013759906
go_gc_duration_seconds{quantile="0.75"} 0.013962066
go_gc_duration_seconds{quantile="1.0"} 0.021383540000000003
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
process_virtual_memory_bytes 2.478268416e+09
# HELP prometheus_build_info A metric with a constant '1' value labeled by version, revision, and branch from which Prometheus was built.
# TYPE prometheus_build_info gauge
prometheus_build_info{branch="HEAD",revision="ef176e5",version="0.16.0rc1"} 1.0
# HELP prometheus_local_storage_chunk_ops The total number of chunk operations by their type.
# TYPE prometheus_local_storage_chunk_ops counter
prometheus_local_storage_chunk_ops_total{type="clone"} 28.0
prometheus_local_storage_chunk_ops_total{type="create"} 997844.0
prometheus_local_storage_chunk_ops_total{type="drop"} 1.345758e+06
prometheus_local_storage_chunk_ops_total{type="load"} 1641.0
prometheus_local_storage_chunk_ops_total{type="persist"} 981408.0
prometheus_local_storage_chunk_ops_total{type="pin"} 32662.0
prometheus_local_storage_chunk_ops_total{type="transcode"} 980180.0
prometheus_local_storage_chunk_ops_total{type="unpin"} 32662.0
# HELP foo histogram Testing histogram buckets
# TYPE foo histogram
foo_bucket{le="0.0"} 0.0
foo_bucket{le="1e-05"} 0.0
foo_bucket{le="0.0001"} 0.0
foo_bucket{le="0.1"} 8.0
foo_bucket{le="1.0"} 10.0
foo_bucket{le="10.0"} 17.0
foo_bucket{le="100000.0"} 17.0
foo_bucket{le="1e+06"} 17.0
foo_bucket{le="1.55555555555552e+06"} 17.0
foo_bucket{le="1e+23"} 17.0
foo_bucket{le="+Inf"} 17.0
foo_count 17.0
foo_sum 324789.3
foo_created 1.520430000123e+09
# HELP bar histogram Testing with labels
# TYPE bar histogram
bar_bucket{a="b",le="+Inf"} 0.0
bar_bucket{a="c",le="+Inf"} 0.0
# EOF
"""
        families = list(text_string_to_metric_families(text))

        class TextCollector:
            def collect(self):
                return families

        registry = CollectorRegistry()
        registry.register(TextCollector())
        self.assertEqual(text.encode('utf-8'), generate_latest(registry))

    def test_invalid_input(self):
        for case in [
            # No EOF.
            (''),
            # Blank line
            ('a 1\n\n# EOF\n'),
            # Text after EOF.
            ('a 1\n# EOF\nblah'),
            ('a 1\n# EOFblah'),
            # Missing or wrong quotes on label value.
            ('a{a=1} 1\n# EOF\n'),
            ('a{a="1} 1\n# EOF\n'),
            ('a{a=\'1\'} 1\n# EOF\n'),
            # Missing equal or label value.
            ('a{a} 1\n# EOF\n'),
            ('a{a"value"} 1\n# EOF\n'),
            ('a{a""} 1\n# EOF\n'),
            ('a{a=} 1\n# EOF\n'),
            ('a{a="} 1\n# EOF\n'),
            # Missing or extra commas.
            ('a{a="1"b="2"} 1\n# EOF\n'),
            ('a{a="1",,b="2"} 1\n# EOF\n'),
            ('a{a="1",b="2",} 1\n# EOF\n'),
            # Invalid labels.
            ('a{1="1"} 1\n# EOF\n'),
            ('a{1="1"}1\n# EOF\n'),
            ('a{a="1",a="1"} 1\n# EOF\n'),
            ('a{a="1"b} 1\n# EOF\n'),
            ('a{1=" # "} 1\n# EOF\n'),
            ('a{a=" # ",a=" # "} 1\n# EOF\n'),
            ('a{a=" # "}1\n# EOF\n'),
            ('a{a=" # ",b=}1\n# EOF\n'),
            ('a{a=" # "b}1\n# EOF\n'),
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
            ('# TYPE a untyped\n# EOF\n'),
            # Bad UNIT.
            ('# UNIT\n# EOF\n'),
            ('# UNIT \n# EOF\n'),
            ('# UNIT a\n# EOF\n'),
            ('# UNIT a\t\n# EOF\n'),
            ('# UNIT a seconds\n# EOF\n'),
            ('# UNIT a_seconds seconds \n# EOF\n'),
            ('# TYPE x_u info\n# UNIT x_u u\n# EOF\n'),
            ('# TYPE x_u stateset\n# UNIT x_u u\n# EOF\n'),
            # Metadata in wrong place.
            ('# HELP a x\na 1\n# TYPE a gauge\n# EOF\n'),
            ('# TYPE a gauge\na 1\n# HELP a gauge\n# EOF\n'),
            ('# TYPE a_s gauge\na_s 1\n# UNIT a_s s\n# EOF\n'),
            # Repeated metadata.
            ('# HELP a \n# HELP a \n# EOF\n'),
            ('# HELP a x\n# HELP a x\n# EOF\n'),
            ('# TYPE a untyped\n# TYPE a untyped\n# EOF\n'),
            ('# UNIT a_s s\n# UNIT a_s s\n# EOF\n'),
            # Bad metadata.
            ('# FOO a x\n# EOF\n'),
            # Bad metric names.
            ('0a 1\n# EOF\n'),
            ('a.b 1\n# EOF\n'),
            ('a-b 1\n# EOF\n'),
            # Bad value.
            ('a a\n# EOF\n'),
            ('a  1\n# EOF\n'),
            ('a 1\t\n# EOF\n'),
            ('a 1 \n# EOF\n'),
            ('a 1_2\n# EOF\n'),
            ('a 0x1p-3\n# EOF\n'),
            ('a 0x1P-3\n# EOF\n'),
            ('a 0b1\n# EOF\n'),
            ('a 0B1\n# EOF\n'),
            ('a 0x1\n# EOF\n'),
            ('a 0X1\n# EOF\n'),
            ('a 0o1\n# EOF\n'),
            ('a 0O1\n# EOF\n'),
            # Bad timestamp.
            ('a 1 z\n# EOF\n'),
            ('a 1 1z\n# EOF\n'),
            ('a 1 1_2\n# EOF\n'),
            ('a 1 1.1.1\n# EOF\n'),
            ('a 1 NaN\n# EOF\n'),
            ('a 1 Inf\n# EOF\n'),
            ('a 1 +Inf\n# EOF\n'),
            ('a 1 -Inf\n# EOF\n'),
            ('a 1 0x1p-3\n# EOF\n'),
            # Bad exemplars.
            ('# TYPE a histogram\na_bucket{le="+Inf"} 1 #\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 1# {} 1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 1 #{} 1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 1 # {}1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 1 # {} 1 \n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 1 # {} 1 1 \n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 1 # '
             '{a="23456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789"} 1 1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 1 # {} 0x1p-3\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 1 # {} 1 0x1p-3\n# EOF\n'),
            ('# TYPE a counter\na_total 1 1 # {id="a"}  \n# EOF\n'),
            ('# TYPE a counter\na_total 1 1 # id="a"} 1\n# EOF\n'),
            ('# TYPE a counter\na_total 1 1 #id=" # "} 1\n# EOF\n'),
            ('# TYPE a counter\na_total 1 1 id=" # "} 1\n# EOF\n'),
            # Exemplars on unallowed samples.
            ('# TYPE a histogram\na_sum 1 # {a="b"} 0.5\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_sum 1 # {a="b"} 0.5\n# EOF\n'),
            ('# TYPE a_bucket gauge\na_bucket 1 # {a="b"} 0.5\n# EOF\n'),
            ('# TYPE a counter\na_created 1 # {a="b"} 0.5\n# EOF\n'),
            # Exemplars on unallowed metric types.
            ('# TYPE a gauge\na 1 # {a="b"} 1\n# EOF\n'),
            ('# TYPE a info\na_info 1 # {a="b"} 1\n# EOF\n'),
            ('# TYPE a stateset\na{a="b"} 1 # {c="d"} 1\n# EOF\n'),
            # Bad stateset/info values.
            ('# TYPE a stateset\na 2\n# EOF\n'),
            ('# TYPE a info\na 2\n# EOF\n'),
            ('# TYPE a stateset\na 2.0\n# EOF\n'),
            ('# TYPE a info\na 2.0\n# EOF\n'),
            # Missing or invalid labels for a type.
            ('# TYPE a summary\na 0\n# EOF\n'),
            ('# TYPE a summary\na{quantile="-1"} 0\n# EOF\n'),
            ('# TYPE a summary\na{quantile="foo"} 0\n# EOF\n'),
            ('# TYPE a summary\na{quantile="1.01"} 0\n# EOF\n'),
            ('# TYPE a summary\na{quantile="NaN"} 0\n# EOF\n'),
            ('# TYPE a histogram\na_bucket 0\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket 0\n# EOF\n'),
            ('# TYPE a stateset\na 0\n# EOF\n'),
            # Bad counter values.
            ('# TYPE a counter\na_total NaN\n# EOF\n'),
            ('# TYPE a counter\na_total -1\n# EOF\n'),
            ('# TYPE a histogram\na_sum NaN\n# EOF\n'),
            ('# TYPE a histogram\na_count NaN\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} NaN\n# EOF\n'),
            ('# TYPE a histogram\na_sum -1\n# EOF\n'),
            ('# TYPE a histogram\na_count -1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} -1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="-1.0"} 1\na_bucket{le="+Inf"} 2\na_sum -1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="-1.0"} 1\na_bucket{le="+Inf"} 2\na_sum 1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 0.5\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 0.5\na_count 0.5\na_sum 0\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} NaN\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} -1\na_gcount -1\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} -1\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} 1\na_gsum -1\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} 1\na_gsum NaN\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} 0.5\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} 0.5\na_gsum 0.5\na_gcount 0\n# EOF\n'),
            ('# TYPE a summary\na_sum NaN\n# EOF\n'),
            ('# TYPE a summary\na_count NaN\n# EOF\n'),
            ('# TYPE a summary\na_sum -1\n# EOF\n'),
            ('# TYPE a summary\na_count -1\n# EOF\n'),
            ('# TYPE a summary\na_count 0.5\n# EOF\n'),
            ('# TYPE a summary\na{quantile="0.5"} -1\n# EOF\n'),
            # Bad info and stateset values.
            ('# TYPE a info\na_info{foo="bar"} 2\n# EOF\n'),
            ('# TYPE a stateset\na{a="bar"} 2\n# EOF\n'),
            # Bad histograms.
            ('# TYPE a histogram\na_sum 1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 0\na_sum 0\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 0\na_count 0\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="-1"} 0\na_bucket{le="+Inf"} 0\na_sum 0\na_count 0\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_gsum 1\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} 0\na_gsum 0\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} 0\na_gcount 0\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_bucket{le="+Inf"} 1\na_gsum -1\na_gcount 1\n# EOF\n'),
            ('# TYPE a histogram\na_count 1\na_bucket{le="+Inf"} 0\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+Inf"} 0\na_count 1\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="+INF"} 0\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="2"} 0\na_bucket{le="1"} 0\na_bucket{le="+Inf"} 0\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{le="1"} 1\na_bucket{le="2"} 1\na_bucket{le="+Inf"} 0\n# EOF\n'),
            # Bad grouping or ordering.
            ('# TYPE a histogram\na_sum{a="1"} 0\na_sum{a="2"} 0\na_count{a="1"} 0\n# EOF\n'),
            ('# TYPE a histogram\na_bucket{a="1",le="1"} 0\na_bucket{a="2",le="+Inf""} '
             '0\na_bucket{a="1",le="+Inf"} 0\n# EOF\n'),
            ('# TYPE a gaugehistogram\na_gsum{a="1"} 0\na_gsum{a="2"} 0\na_gcount{a="1"} 0\n# EOF\n'),
            ('# TYPE a summary\nquantile{quantile="0"} 0\na_sum{a="1"} 0\nquantile{quantile="1"} 0\n# EOF\n'),
            ('# TYPE a gauge\na 0 -1\na 0 -2\n# EOF\n'),
            ('# TYPE a gauge\na 0 -1\na 0 -1.1\n# EOF\n'),
            ('# TYPE a gauge\na 0 1\na 0 -1\n# EOF\n'),
            ('# TYPE a gauge\na 0 1.1\na 0 1\n# EOF\n'),
            ('# TYPE a gauge\na 0 1\na 0 0\n# EOF\n'),
            ('# TYPE a gauge\na 0\na 0 0\n# EOF\n'),
            ('# TYPE a gauge\na 0 0\na 0\n# EOF\n'),
            # Clashing names.
            ('# TYPE a counter\n# TYPE a counter\n# EOF\n'),
            ('# TYPE a info\n# TYPE a counter\n# EOF\n'),
            ('# TYPE a_created gauge\n# TYPE a counter\n# EOF\n'),
        ]:
            with self.assertRaises(ValueError, msg=case):
                list(text_string_to_metric_families(case))


if __name__ == '__main__':
    unittest.main()
