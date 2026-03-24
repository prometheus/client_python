import importlib
import os
from threading import Lock
import warnings

from .mmap_dict import mmap_key, MmapedDict


class MutexValue:
    """A float protected by a mutex."""

    _multiprocess = False

    def __init__(self, typ, metric_name, name, labelnames, labelvalues, help_text, **kwargs):
        self._value = 0.0
        self._exemplar = None
        self._lock = Lock()

    def inc(self, amount):
        with self._lock:
            self._value += amount

    def set(self, value, timestamp=None):
        with self._lock:
            self._value = value

    def set_exemplar(self, exemplar):
        with self._lock:
            self._exemplar = exemplar

    def get(self):
        with self._lock:
            return self._value

    def get_exemplar(self):
        with self._lock:
            return self._exemplar


class MmapedValue:
    """A float protected by a mutex backed by a per-process mmaped file."""

    _multiprocess = True
    _files = {}
    _values = []
    _pid = {'value': os.getpid()}
    _lock = Lock()
    _process_identifier = staticmethod(os.getpid)

    def __init__(self, typ, metric_name, name, labelnames, labelvalues, help_text, multiprocess_mode='', **kwargs):
        self._params = typ, metric_name, name, labelnames, labelvalues, help_text, multiprocess_mode
        # This deprecation warning can go away in a few releases when removing the compatibility
        if 'prometheus_multiproc_dir' in os.environ and 'PROMETHEUS_MULTIPROC_DIR' not in os.environ:
            os.environ['PROMETHEUS_MULTIPROC_DIR'] = os.environ['prometheus_multiproc_dir']
            warnings.warn("prometheus_multiproc_dir variable has been deprecated in favor of the upper case naming PROMETHEUS_MULTIPROC_DIR", DeprecationWarning)
        with self._lock:
            self.__check_for_pid_change()
            self.__reset()
            self._values.append(self)

    def __reset(self):
        typ, metric_name, name, labelnames, labelvalues, help_text, multiprocess_mode = self._params
        if typ == 'gauge':
            file_prefix = typ + '_' + multiprocess_mode
        else:
            file_prefix = typ
        if file_prefix not in self._files:
            filename = os.path.join(
                os.environ.get('PROMETHEUS_MULTIPROC_DIR'),
                '{}_{}.db'.format(file_prefix, self._pid['value']))

            self._files[file_prefix] = MmapedDict(filename)
        self._file = self._files[file_prefix]
        self._key = mmap_key(metric_name, name, labelnames, labelvalues, help_text)
        self._value, self._timestamp = self._file.read_value(self._key)

    def __check_for_pid_change(self):
        actual_pid = self._process_identifier()
        if self._pid['value'] != actual_pid:
            self._pid['value'] = actual_pid
            # There has been a fork(), reset all the values.
            for f in self._files.values():
                f.close()
            self._files.clear()
            for value in self._values:
                value.__reset()

    def inc(self, amount):
        with self._lock:
            self.__check_for_pid_change()
            self._value += amount
            self._timestamp = 0.0
            self._file.write_value(self._key, self._value, self._timestamp)

    def set(self, value, timestamp=None):
        with self._lock:
            self.__check_for_pid_change()
            self._value = value
            self._timestamp = timestamp or 0.0
            self._file.write_value(self._key, self._value, self._timestamp)

    def set_exemplar(self, exemplar):
        # TODO: Implement exemplars for multiprocess mode.
        return

    def get(self):
        with self._lock:
            self.__check_for_pid_change()
            return self._value

    def get_exemplar(self):
        # TODO: Implement exemplars for multiprocess mode.
        return None


def MultiProcessValue(process_identifier=os.getpid):
    """Returns a MmapedValue class based on a process_identifier function.

    The 'process_identifier' function MUST comply with this simple rule:
    when called in simultaneously running processes it MUST return distinct values.

    Using a different function than the default 'os.getpid' is at your own risk.
    """
    class _MmapedValue(MmapedValue):
        _files = {}
        _values = []
        _pid = {'value': process_identifier()}
        _lock = Lock()
        _process_identifier = staticmethod(process_identifier)

    return _MmapedValue


def get_value_class():
    # Should we enable multi-process mode?
    # This needs to be chosen before the first metric is constructed,
    # and as that may be in some arbitrary library the user/admin has
    # no control over we use an environment variable.
    value_class_path = os.environ.get('PROMETHEUS_VALUE_CLASS')
    if value_class_path:
        if '.' not in value_class_path:
            raise ImportError(f"PROMETHEUS_VALUE_CLASS must be a full python path (e.g. module.ClassName), got '{value_class_path}'")
        try:
            module_path, class_name = value_class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Could not import PROMETHEUS_VALUE_CLASS '{value_class_path}': {e}") from None

    if 'prometheus_multiproc_dir' in os.environ or 'PROMETHEUS_MULTIPROC_DIR' in os.environ:
        return MmapedValue
    return MutexValue


ValueClass = get_value_class()
