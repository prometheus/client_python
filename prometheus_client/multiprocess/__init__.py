from __future__ import unicode_literals

import os

multiprocess_enabled = bool(os.environ.get('prometheus_multiproc_dir'))
multiprocess_backend = (os.environ.get('prometheus_multiproc_backend') or 'mmap')


def MultiProcessCollector(registry, path=None):
    if path is None:
        path = os.environ.get('prometheus_multiproc_dir')
    if not path or not os.path.isdir(path):
        raise ValueError('env prometheus_multiproc_dir is not set or %s is not a directory' % path)
    if multiprocess_backend == 'mmap':
        from prometheus_client.multiprocess.mmap_collector import MmapMultiProcessCollector
        return MmapMultiProcessCollector(registry=registry, path=path)
    else:
        raise NotImplementedError('unknown multiprocess backend %s' % multiprocess_backend)


def get_multiprocess_value_class():
    if multiprocess_backend == 'mmap':
        from prometheus_client.multiprocess.mmaped_value import MmapedValue
        return MmapedValue()
    else:
        raise NotImplementedError('unknown multiprocess backend %s' % multiprocess_backend)


def mark_process_dead(pid, path=None):
    """Do bookkeeping for when one process dies in a multi-process setup."""
    if path is None:
        path = os.environ.get('prometheus_multiproc_dir')
    if multiprocess_backend == 'mmap':
        from prometheus_client.multiprocess.mmap_utils import mmap_cleanup
        mmap_cleanup(path, pid)
    else:
        raise NotImplementedError('unknown multiprocess backend %s' % multiprocess_backend)
