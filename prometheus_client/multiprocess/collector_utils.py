from collections import defaultdict

from prometheus_client.metrics_core import Metric
from prometheus_client.samples import Sample
from prometheus_client.utils import floatToGoString


def populate_metrics(metrics, pid, metric_name, name, labels, multiprocess_mode, type, value):
    labels_key = tuple(sorted(labels.items()))
    metric = metrics.get(metric_name)
    if metric is None:
        metric = Metric(metric_name, 'Multiprocess metric', type)
        metrics[metric_name] = metric
    if type == 'gauge':
        metric._multiprocess_mode = multiprocess_mode
        metric.add_sample(name, labels_key + (('pid', pid),), value)
    else:
        # The duplicates and labels are fixed in the next for.
        metric.add_sample(name, labels_key, value)


def postprocess_metrics(metrics, accumulate=True):
    for metric in metrics.values():
        metric.samples = _postprocess_metric(metric, accumulate=accumulate)


def _postprocess_metric(metric, accumulate=True):
    samples = defaultdict(float)
    buckets = {}
    for s in metric.samples:
        name, labels, value = s.name, s.labels, s.value
        if metric.type == 'gauge':
            without_pid = tuple(l for l in labels if l[0] != 'pid')
            if metric._multiprocess_mode == 'min':
                current = samples.setdefault((name, without_pid), value)
                if value < current:
                    samples[(s.name, without_pid)] = value
            elif metric._multiprocess_mode == 'max':
                current = samples.setdefault((name, without_pid), value)
                if value > current:
                    samples[(s.name, without_pid)] = value
            elif metric._multiprocess_mode == 'livesum':
                samples[(name, without_pid)] += value
            else:  # all/liveall
                samples[(name, labels)] = value

        elif metric.type == 'histogram':
            bucket = tuple(float(l[1]) for l in labels if l[0] == 'le')
            if bucket:
                # _bucket
                without_le = tuple(l for l in labels if l[0] != 'le')
                buckets.setdefault(without_le, {})
                buckets[without_le].setdefault(bucket[0], 0.0)
                buckets[without_le][bucket[0]] += value
            else:
                # _sum/_count
                samples[(s.name, labels)] += value

        else:
            # Counter and Summary.
            samples[(s.name, labels)] += value
    # Accumulate bucket values.
    if metric.type == 'histogram':
        for labels, values in buckets.items():
            acc = 0.0
            for bucket, value in sorted(values.items()):
                sample_key = (
                    metric.name + '_bucket',
                    labels + (('le', floatToGoString(bucket)),),
                )
                if accumulate:
                    acc += value
                    samples[sample_key] = acc
                else:
                    samples[sample_key] = value
            if accumulate:
                samples[(metric.name + '_count', labels)] = acc
    # Convert to correct sample format.
    return [Sample(name, dict(labels), value) for (name, labels), value in samples.items()]
