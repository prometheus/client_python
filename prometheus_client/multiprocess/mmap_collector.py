import glob
import json
import os

from prometheus_client.multiprocess.collector_utils import populate_metrics, postprocess_metrics
from prometheus_client.multiprocess.mmap_dict import MmapedDict


class MmapMultiProcessCollector(object):
    """Collector for files for mmap multi-process mode."""

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
            parts = os.path.basename(f).split('_')  # e.g. gauge_liveall_1234.db, counter_1234.db, histogram_1234.db
            typ = parts.pop(0)  # grab type (remaining e.g. ['liveall', '1234.db'] or ['1234.db'])
            pid = parts.pop(-1)[:-3]  # grab pid off end (remaining e.g. ['liveall'] or [])
            multiprocess_mode = (parts.pop(0) if parts else None)  # must be the remaining multiprocess mode bit
            assert not parts  # make sure nothing was unread
            d = MmapedDict(f, read_mode=True)
            for key, value in d.read_all_values():
                metric_name, name, labels = json.loads(key)
                populate_metrics(
                    metrics,
                    pid=pid,
                    metric_name=metric_name,
                    name=name,
                    labels=labels,
                    multiprocess_mode=multiprocess_mode,
                    type=typ,
                    value=value,
                )
            d.close()

        postprocess_metrics(metrics, accumulate)
        return metrics.values()
