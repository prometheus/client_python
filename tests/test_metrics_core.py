import pytest

from prometheus_client import core 
from prometheus_client import exceptions
from prometheus_client import exposition


@pytest.fixture
def registry():
    return core.CollectorRegistry()


class Collector:
    def __init__(self, metric_family, *values):
        self.metric_family = metric_family
        self.values = values

    def collect(self):
        self.metric_family.add_metric([], *self.values)
        return [self.metric_family]


def _expect_metric_exception(registry, expected_error):
    try:
        exposition.generate_latest(registry)
    except expected_error as exception:
        assert hasattr(exception, 'metric')
        # Got a valid error as expected, return quietly
        return

    raise RuntimeError('Expected exception not raised')


@pytest.mark.parametrize('MetricFamily', [
    core.CounterMetricFamily,
    core.GaugeMetricFamily,
])
@pytest.mark.parametrize('value,error', [
    (None, exceptions.MetricTypeError),
    ('', exceptions.MetricValueError),
    ('x', exceptions.MetricValueError),
    ([], exceptions.MetricTypeError),
    ({}, exceptions.MetricTypeError),
])
def test_basic_metric_families(registry, MetricFamily, value, error):
    metric_family = MetricFamily(MetricFamily.__name__, 'help')
    registry.register(Collector(metric_family, value))
    _expect_metric_exception(registry, error)


@pytest.mark.parametrize('count_value,sum_value,error', [
    (None, 0, exceptions.MetricTypeError),
    (0, None, exceptions.MetricTypeError),
    ('', 0, exceptions.MetricValueError),
    (0, '', exceptions.MetricValueError),
    ([], 0, exceptions.MetricTypeError),
    (0, [], exceptions.MetricTypeError),
    ({}, 0, exceptions.MetricTypeError),
    (0, {}, exceptions.MetricTypeError),
])
def test_summary_metric_family(registry, count_value, sum_value, error):
    metric_family = core.SummaryMetricFamily('summary', 'help')
    registry.register(Collector(metric_family, count_value, sum_value))
    _expect_metric_exception(registry, error)


@pytest.mark.parametrize('MetricFamily', [
    core.HistogramMetricFamily,
    core.GaugeHistogramMetricFamily,
])
@pytest.mark.parametrize('buckets,sum_value,error', [
    ([('spam', 0), ('eggs', 0)], None, exceptions.MetricTypeError),
    ([('spam', 0), ('eggs', None)], 0, exceptions.MetricTypeError),
    ([('spam', 0), (None, 0)], 0, exceptions.MetricAttributeError),
    ([('spam', None), ('eggs', 0)], 0, exceptions.MetricTypeError),
    ([(None, 0), ('eggs', 0)], 0, exceptions.MetricAttributeError),
    ([('spam', 0), ('eggs', 0)], '', exceptions.MetricValueError),
    ([('spam', 0), ('eggs', '')], 0, exceptions.MetricValueError),
    ([('spam', ''), ('eggs', 0)], 0, exceptions.MetricValueError),
])
def test_histogram_metric_families(MetricFamily, registry, buckets, sum_value, error):
    metric_family = MetricFamily(MetricFamily.__name__, 'help')
    registry.register(Collector(metric_family, buckets, sum_value))
    _expect_metric_exception(registry, error)
