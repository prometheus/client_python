---
title: Custom Collectors
weight: 1
---

Sometimes it is not possible to directly instrument code, as it is not
in your control. This requires you to proxy metrics from other systems.

To do so you need to create a custom collector, for example:

```python
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY
from prometheus_client.registry import Collector

class CustomCollector(Collector):
    def collect(self):
        yield GaugeMetricFamily('my_gauge', 'Help text', value=7)
        c = CounterMetricFamily('my_counter_total', 'Help text', labels=['foo'])
        c.add_metric(['bar'], 1.7)
        c.add_metric(['baz'], 3.8)
        yield c

REGISTRY.register(CustomCollector())
```

`SummaryMetricFamily`, `HistogramMetricFamily` and `InfoMetricFamily` work similarly.

A collector may implement a `describe` method which returns metrics in the same
format as `collect` (though you don't have to include the samples). This is
used to predetermine the names of time series a `CollectorRegistry` exposes and
thus to detect collisions and duplicate registrations.

Usually custom collectors do not have to implement `describe`. If `describe` is
not implemented and the CollectorRegistry was created with `auto_describe=True`
(which is the case for the default registry) then `collect` will be called at
registration time instead of `describe`. If this could cause problems, either
implement a proper `describe`, or if that's not practical have `describe`
return an empty list.

## Collector protocol

A collector is any object that implements a `collect` method. Optionally it
can also implement `describe`.

### `collect()`

Returns an iterable of metric family objects (`GaugeMetricFamily`,
`CounterMetricFamily`, etc.). Called every time the registry is scraped.

Using `yield` is the idiomatic way to implement `collect()` — it turns the method
into a generator, which the registry iterates lazily without building an intermediate
list first. Each scrape calls `collect()` fresh, so no state carries over between
scrapes.

### `describe()`

Returns an iterable of metric family objects used only to determine the metric
names the collector produces. Samples on the returned objects are ignored. If
not implemented and the registry has `auto_describe=True`, `collect` is called
at registration time instead.

## value vs labels

Every metric family constructor accepts either inline data or `labels`, but not
both. The inline data parameter name varies by type: `value` for Gauge, Counter,
and Info; `count_value`/`sum_value` for Summary; `buckets` for Histogram.

- Pass inline data to emit a single unlabelled metric directly from the constructor.
- Pass `labels` (a sequence of label names) and then call `add_metric` one or
  more times to emit labelled metrics.

```python
# single unlabelled value
GaugeMetricFamily('my_gauge', 'Help text', value=7)

# labelled metrics via add_metric
g = GaugeMetricFamily('my_gauge', 'Help text', labels=['region'])
g.add_metric(['us-east-1'], 3)
g.add_metric(['eu-west-1'], 5)
```

## API Reference

The examples below show usage inside a `collect()` method body. Each snippet is
meant to be placed within a custom collector class as shown in the example at the
top of this page.

### GaugeMetricFamily

```python
GaugeMetricFamily(name, documentation, value=None, labels=None, unit='')
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. |
| `documentation` | `str` | required | Help text shown in the `/metrics` output. |
| `value` | `float` | `None` | Emit a single unlabelled sample with this value. Mutually exclusive with `labels`. |
| `labels` | `Sequence[str]` | `None` | Label names. Use with `add_metric`. Mutually exclusive with `value`. |
| `unit` | `str` | `''` | Optional unit suffix appended to the metric name. |

#### `add_metric(labels, value, timestamp=None)`

Add a labelled sample to the metric family.

| Parameter | Type | Description |
|-----------|------|-------------|
| `labels` | `Sequence[str]` | Label values in the same order as the `labels` constructor argument. |
| `value` | `float` | The gauge value. |
| `timestamp` | `float` or `Timestamp` | Optional Unix timestamp for the sample. |

```python
g = GaugeMetricFamily('temperature_celsius', 'Temperature by location', labels=['location'])
g.add_metric(['living_room'], 21.5)
g.add_metric(['basement'], 18.0)
yield g
```

### CounterMetricFamily

```python
CounterMetricFamily(name, documentation, value=None, labels=None, created=None, unit='', exemplar=None)
```

If `name` ends with `_total`, the suffix is stripped automatically so the
metric is stored without it and the `_total` suffix is added on exposition.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. A trailing `_total` is stripped and re-added on exposition. |
| `documentation` | `str` | required | Help text. |
| `value` | `float` | `None` | Emit a single unlabelled sample. Mutually exclusive with `labels`. |
| `labels` | `Sequence[str]` | `None` | Label names. Use with `add_metric`. Mutually exclusive with `value`. |
| `created` | `float` | `None` | Unix timestamp the counter was created at. Only used when `value` is set. |
| `unit` | `str` | `''` | Optional unit suffix. |
| `exemplar` | `Exemplar` | `None` | Exemplar for the single-value form. Only used when `value` is set. |

#### `add_metric(labels, value, created=None, timestamp=None, exemplar=None)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `labels` | `Sequence[str]` | Label values. |
| `value` | `float` | The counter value. |
| `created` | `float` | Optional Unix timestamp the counter was created at. |
| `timestamp` | `float` or `Timestamp` | Optional Unix timestamp for the sample. |
| `exemplar` | `Exemplar` | Optional exemplar. See [Exemplars](../../instrumenting/exemplars/). |

```python
c = CounterMetricFamily('http_requests_total', 'HTTP requests by status', labels=['status'])
c.add_metric(['200'], 1200)
c.add_metric(['404'], 43)
c.add_metric(['500'], 7)
yield c
```

### SummaryMetricFamily

```python
SummaryMetricFamily(name, documentation, count_value=None, sum_value=None, labels=None, unit='')
```

`count_value` and `sum_value` must always be provided together or not at all.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. |
| `documentation` | `str` | required | Help text. |
| `count_value` | `int` | `None` | Observation count for a single unlabelled metric. Must be paired with `sum_value`. |
| `sum_value` | `float` | `None` | Observation sum for a single unlabelled metric. Must be paired with `count_value`. |
| `labels` | `Sequence[str]` | `None` | Label names. Use with `add_metric`. Mutually exclusive with `count_value`/`sum_value`. |
| `unit` | `str` | `''` | Optional unit suffix. |

#### `add_metric(labels, count_value, sum_value, timestamp=None)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `labels` | `Sequence[str]` | Label values. |
| `count_value` | `int` | The number of observations. |
| `sum_value` | `float` | The sum of all observed values. |
| `timestamp` | `float` or `Timestamp` | Optional Unix timestamp for the sample. |

```python
s = SummaryMetricFamily('rpc_duration_seconds', 'RPC duration', labels=['method'])
s.add_metric(['get'], count_value=1000, sum_value=53.2)
s.add_metric(['put'], count_value=400, sum_value=28.7)
yield s
```

### HistogramMetricFamily

```python
HistogramMetricFamily(name, documentation, buckets=None, sum_value=None, labels=None, unit='')
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. |
| `documentation` | `str` | required | Help text. |
| `buckets` | `Sequence` | `None` | Bucket data for a single unlabelled metric. Each entry is a `(le, value)` pair or `(le, value, exemplar)` triple. Must include a `+Inf` bucket. Mutually exclusive with `labels`. |
| `sum_value` | `float` | `None` | Observation sum. Cannot be set without `buckets`. Omitted for histograms with negative buckets. |
| `labels` | `Sequence[str]` | `None` | Label names. Use with `add_metric`. Mutually exclusive with `buckets`. |
| `unit` | `str` | `''` | Optional unit suffix. |

#### `add_metric(labels, buckets, sum_value, timestamp=None)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `labels` | `Sequence[str]` | Label values. |
| `buckets` | `Sequence` | Bucket data. Each entry is a `(le, value)` pair or `(le, value, exemplar)` triple. Must be sorted and include `+Inf`. |
| `sum_value` | `float` or `None` | The sum of all observed values. Pass `None` for histograms with negative buckets. |
| `timestamp` | `float` or `Timestamp` | Optional Unix timestamp. |

```python
h = HistogramMetricFamily('request_size_bytes', 'Request sizes', labels=['handler'])
h.add_metric(
    ['api'],
    buckets=[('100', 5), ('1000', 42), ('+Inf', 50)],
    sum_value=18350.0,
)
yield h
```

### InfoMetricFamily

```python
InfoMetricFamily(name, documentation, value=None, labels=None)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. The `_info` suffix is added automatically on exposition. |
| `documentation` | `str` | required | Help text. |
| `value` | `Dict[str, str]` | `None` | Key-value label pairs for a single unlabelled info metric. Mutually exclusive with `labels`. |
| `labels` | `Sequence[str]` | `None` | Label names for the outer grouping. Use with `add_metric`. Mutually exclusive with `value`. |

#### `add_metric(labels, value, timestamp=None)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `labels` | `Sequence[str]` | Outer label values (from the `labels` constructor argument). |
| `value` | `Dict[str, str]` | Key-value label pairs that form the info payload. |
| `timestamp` | `float` or `Timestamp` | Optional Unix timestamp. |

Single unlabelled info metric:

```python
yield InfoMetricFamily('build', 'Build metadata', value={'version': '1.2.3', 'commit': 'abc123'})
```

Labelled — one info metric per service:

```python
i = InfoMetricFamily('service_build', 'Per-service build info', labels=['service'])
i.add_metric(['auth'], {'version': '2.0.1', 'commit': 'def456'})
i.add_metric(['api'], {'version': '1.9.0', 'commit': 'ghi789'})
yield i
```

## Real-world example

Proxying metrics from an external source:

```python
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, REGISTRY
from prometheus_client.registry import Collector
from prometheus_client import start_http_server

# Simulated external data source
_QUEUE_STATS = {
    'orders': {'depth': 14, 'processed': 9821},
    'notifications': {'depth': 3, 'processed': 45210},
}

class QueueCollector(Collector):
    def collect(self):
        depth = GaugeMetricFamily(
            'queue_depth',
            'Current number of messages waiting in the queue',
            labels=['queue'],
        )
        processed = CounterMetricFamily(
            'queue_messages_processed_total',
            'Total messages processed from the queue',
            labels=['queue'],
        )
        for name, stats in _QUEUE_STATS.items():
            depth.add_metric([name], stats['depth'])
            processed.add_metric([name], stats['processed'])
        yield depth
        yield processed

REGISTRY.register(QueueCollector())

if __name__ == '__main__':
    start_http_server(8000)
    import time
    while True:
        time.sleep(1)
```
