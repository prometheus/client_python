from __future__ import unicode_literals

import os
from threading import Lock

from .mmap_dict import mmap_key, MmapedDict


class MutexValue(object):
    '''A float protected by a mutex.'''

    _multiprocess = False

    def __init__(self, typ, metric_name, name, labelnames, labelvalues, **kwargs):
        self._value = 0.0
        self._lock = Lock()

    def inc(self, amount):
        with self._lock:
            self._value += amount

    def set(self, value):
        with self._lock:
            self._value = value

    def get(self):
        with self._lock:
            return self._value


def MultiProcessValue(_pidFunc=os.getpid):
    files = {}
    values = []
    pid = {'value': _pidFunc()}
    # Use a single global lock when in multi-processing mode
    # as we presume this means there is no threading going on.
    # This avoids the need to also have mutexes in __MmapDict.
    lock = Lock()

    class MmapedValue(object):
        '''A float protected by a mutex backed by a per-process mmaped file.'''

        _multiprocess = True

        def __init__(self, typ, metric_name, name, labelnames, labelvalues, multiprocess_mode='', **kwargs):
            self._params = typ, metric_name, name, labelnames, labelvalues, multiprocess_mode
            with lock:
                self.__check_for_pid_change()
                self.__reset()
                values.append(self)

        def __reset(self):
            typ, metric_name, name, labelnames, labelvalues, multiprocess_mode = self._params
            if typ == 'gauge':
                file_prefix = typ + '_' + multiprocess_mode
            else:
                file_prefix = typ
            if file_prefix not in files:
                filename = os.path.join(
                    os.environ['prometheus_multiproc_dir'],
                    '{0}_{1}.db'.format(file_prefix, pid['value']))

                files[file_prefix] = MmapedDict(filename)
            self._file = files[file_prefix]
            self._key = mmap_key(metric_name, name, labelnames, labelvalues)
            self._value = self._file.read_value(self._key)

        def __check_for_pid_change(self):
            actual_pid = _pidFunc()
            if pid['value'] != actual_pid:
                pid['value'] = actual_pid
                # There has been a fork(), reset all the values.
                for f in files.values():
                    f.close()
                files.clear()
                for value in values:
                    value.__reset()

        def inc(self, amount):
            with lock:
                self.__check_for_pid_change()
                self._value += amount
                self._file.write_value(self._key, self._value)

        def set(self, value):
            with lock:
                self.__check_for_pid_change()
                self._value = value
                self._file.write_value(self._key, self._value)

        def get(self):
            with lock:
                self.__check_for_pid_change()
                return self._value

    return MmapedValue


def get_value_class():
    # Should we enable multi-process mode?
    # This needs to be chosen before the first metric is constructed,
    # and as that may be in some arbitrary library the user/admin has
    # no control over we use an environment variable.
    if 'prometheus_multiproc_dir' in os.environ:
        return MultiProcessValue()
    else:
        return MutexValue


ValueClass = get_value_class()
