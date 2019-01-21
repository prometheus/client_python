import glob
import json
import os
from collections import defaultdict

from prometheus_client.metrics_core import Metric
from prometheus_client.multiprocess.mmap_dict import MmapedDict
from prometheus_client.samples import Sample
from prometheus_client.utils import floatToGoString


class MmapMultiProcessCollector(object):
    """Collector for files for multi-process mode."""

    def __init__(self, registry, path):
        self._path = path
        if registry:
            registry.register(self)

    def collect(self):
        files = glob.glob(os.path.join(self._path, '*.db'))
        return self.merge(files, accumulate=True)

    def merge(self, files, accumulate=True):
        """Merge metrics from given mmap files.

        By default, histograms are accumulated, as per prometheus wire format.
        But if writing the merged data back to mmap files, use
        accumulate=False to avoid compound accumulation.
        """
        metrics = {}
        for f in files:
            parts = os.path.basename(f).split('_')
            typ = parts[0]
            d = MmapedDict(f, read_mode=True)
            for key, value in d.read_all_values():
                metric_name, name, labels = json.loads(key)
                labels_key = tuple(sorted(labels.items()))

                metric = metrics.get(metric_name)
                if metric is None:
                    metric = Metric(metric_name, 'Multiprocess metric', typ)
                    metrics[metric_name] = metric

                if typ == 'gauge':
                    pid = parts[2][:-3]
                    metric._multiprocess_mode = parts[1]
                    metric.add_sample(name, labels_key + (('pid', pid), ), value)
                else:
                    # The duplicates and labels are fixed in the next for.
                    metric.add_sample(name, labels_key, value)
            d.close()

        for metric in metrics.values():
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
                            labels + (('le', floatToGoString(bucket)), ),
                        )
                        if accumulate:
                            acc += value
                            samples[sample_key] = acc
                        else:
                            samples[sample_key] = value
                    if accumulate:
                        samples[(metric.name + '_count', labels)] = acc

            # Convert to correct sample format.
            metric.samples = [Sample(name, dict(labels), value) for (name, labels), value in samples.items()]
        return metrics.values()
