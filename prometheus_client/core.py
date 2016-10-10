#!/usr/bin/python

from __future__ import unicode_literals

import copy
import json
import math
import mmap
import os
import re
import struct
import types
from timeit import default_timer

try:
    from BaseHTTPServer import BaseHTTPRequestHandler
except ImportError:
    # Python 3
    unicode = str

from threading import Lock

from .decorator import decorate

_METRIC_NAME_RE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$')
_METRIC_LABEL_NAME_RE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$')
_RESERVED_METRIC_LABEL_NAME_RE = re.compile(r'^__.*$')
_INF = float("inf")
_MINUS_INF = float("-inf")
_INITIAL_MMAP_SIZE = 1024*1024


class CollectorRegistry(object):
    '''Metric collector registry.

    Collectors must have a no-argument method 'collect' that returns a list of
    Metric objects. The returned metrics should be consistent with the Prometheus
    exposition formats.
    '''
    def __init__(self):
        self._collectors = set()
        self._lock = Lock()

    def register(self, collector):
        '''Add a collector to the registry.'''
        with self._lock:
            self._collectors.add(collector)

    def unregister(self, collector):
        '''Remove a collector from the registry.'''
        with self._lock:
            self._collectors.remove(collector)

    def collect(self):
        '''Yields metrics from the collectors in the registry.'''
        collectors = None
        with self._lock:
            collectors = copy.copy(self._collectors)
        for collector in collectors:
            for metric in collector.collect():
                yield metric

    def get_sample_value(self, name, labels=None):
        '''Returns the sample value, or None if not found.

        This is inefficient, and intended only for use in unittests.
        '''
        if labels is None:
            labels = {}
        for metric in self.collect():
            for n, l, value in metric.samples:
                if n == name and l == labels:
                    return value
        return None


REGISTRY = CollectorRegistry()
'''The default registry.'''

_METRIC_TYPES = ('counter', 'gauge', 'summary', 'histogram', 'untyped')


class Metric(object):
    '''A single metric family and its samples.

    This is intended only for internal use by the instrumentation client.

    Custom collectors should use GaugeMetricFamily, CounterMetricFamily
    and SummaryMetricFamily instead.
    '''
    def __init__(self, name, documentation, typ):
        self.name = name
        self.documentation = documentation
        if typ not in _METRIC_TYPES:
            raise ValueError('Invalid metric type: ' + typ)
        self.type = typ
        self.samples = []

    def add_sample(self, name, labels, value):
        '''Add a sample to the metric.

        Internal-only, do not use.'''
        self.samples.append((name, labels, value))

    def __eq__(self, other):
        return (isinstance(other, Metric)
                and self.name == other.name
                and self.documentation == other.documentation
                and self.type == other.type
                and self.samples == other.samples)


class CounterMetricFamily(Metric):
    '''A single counter and its samples.

    For use by custom collectors.
    '''
    def __init__(self, name, documentation, value=None, labels=None):
        Metric.__init__(self, name, documentation, 'counter')
        if labels is not None and value is not None:
            raise ValueError('Can only specify at most one of value and labels.')
        if labels is None:
          labels = []
        self._labelnames = labels
        if value is not None:
          self.add_metric([], value)

    def add_metric(self, labels, value):
        '''Add a metric to the metric family.

        Args:
          labels: A list of label values
          value: The value of the metric.
        '''
        self.samples.append((self.name, dict(zip(self._labelnames, labels)), value))


class GaugeMetricFamily(Metric):
    '''A single gauge and its samples.

    For use by custom collectors.
    '''
    def __init__(self, name, documentation, value=None, labels=None):
        Metric.__init__(self, name, documentation, 'gauge')
        if labels is not None and value is not None:
            raise ValueError('Can only specify at most one of value and labels.')
        if labels is None:
          labels = []
        self._labelnames = labels
        if value is not None:
          self.add_metric([], value)

    def add_metric(self, labels, value):
        '''Add a metric to the metric family.

        Args:
          labels: A list of label values
          value: A float
        '''
        self.samples.append((self.name, dict(zip(self._labelnames, labels)), value))


class SummaryMetricFamily(Metric):
    '''A single summary and its samples.

    For use by custom collectors.
    '''
    def __init__(self, name, documentation, count_value=None, sum_value=None, labels=None):
        Metric.__init__(self, name, documentation, 'summary')
        if (sum_value is None) != (count_value is None):
            raise ValueError('count_value and sum_value must be provided together.')
        if labels is not None and count_value is not None:
            raise ValueError('Can only specify at most one of value and labels.')
        if labels is None:
          labels = []
        self._labelnames = labels
        if count_value is not None:
          self.add_metric([], count_value, sum_value)

    def add_metric(self, labels, count_value, sum_value):
        '''Add a metric to the metric family.

        Args:
          labels: A list of label values
          count_value: The count value of the metric.
          sum_value: The sum value of the metric.
        '''
        self.samples.append((self.name + '_count', dict(zip(self._labelnames, labels)), count_value))
        self.samples.append((self.name + '_sum', dict(zip(self._labelnames, labels)), sum_value))


class HistogramMetricFamily(Metric):
    '''A single histogram and its samples.

    For use by custom collectors.
    '''
    def __init__(self, name, documentation, buckets=None, sum_value=None, labels=None):
        Metric.__init__(self, name, documentation, 'histogram')
        if (sum_value is None) != (buckets is None):
            raise ValueError('buckets and sum_value must be provided together.')
        if labels is not None and buckets is not None:
            raise ValueError('Can only specify at most one of buckets and labels.')
        if labels is None:
          labels = []
        self._labelnames = labels
        if buckets is not None:
          self.add_metric([], buckets, sum_value)

    def add_metric(self, labels, buckets, sum_value):
        '''Add a metric to the metric family.

        Args:
          labels: A list of label values
          buckets: A list of pairs of bucket names and values.
              The buckets must be sorted, and +Inf present.
          sum_value: The sum value of the metric.
        '''
        for bucket, value in buckets:
          self.samples.append((self.name + '_bucket', dict(list(zip(self._labelnames, labels)) + [('le', bucket)]), value))
        # +Inf is last and provides the count value.
        self.samples.append((self.name + '_count', dict(zip(self._labelnames, labels)), buckets[-1][1]))
        self.samples.append((self.name + '_sum', dict(zip(self._labelnames, labels)), sum_value))


class _MutexValue(object):
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

class _MmapedDict(object):
    """A dict of doubles, backed by an mmapped file.

    The file starts with a 4 byte int, indicating how much of it is used.
    Then 4 bytes of padding.
    There's then a number of entries, consisting of a 4 byte int which is the
    side of the next field, a utf-8 encoded string key, padding to a 8 byte
    alignment, and then a 8 byte float which is the value.
    """
    def __init__(self, filename):
        self._lock = Lock()
        self._f = open(filename, 'a+b')
        if os.fstat(self._f.fileno()).st_size == 0:
            self._f.truncate(_INITIAL_MMAP_SIZE)
        self._capacity = os.fstat(self._f.fileno()).st_size
        self._m = mmap.mmap(self._f.fileno(), self._capacity)

        self._positions = {}
        self._used = struct.unpack_from(b'i', self._m, 0)[0]
        if self._used == 0:
            self._used = 8
            struct.pack_into(b'i', self._m, 0, self._used)
        else:
            for key, _, pos in self._read_all_values():
                self._positions[key] = pos

    def _init_value(self, key):
        """Initilize a value. Lock must be held by caller."""
        encoded = key.encode('utf-8')
        # Pad to be 8-byte aligned.
        padded = encoded + (b' ' * (8 - (len(encoded) + 4) % 8))
        value = struct.pack('i{0}sd'.format(len(padded)).encode(), len(encoded), padded, 0.0)
        while self._used + len(value) > self._capacity:
            self._capacity *= 2
            self._f.truncate(self._capacity * 2)
            self._m = mmap.mmap(self._f.fileno(), self._capacity)
        self._m[self._used:self._used + len(value)] = value

        # Update how much space we've used.
        self._used += len(value)
        struct.pack_into(b'i', self._m, 0, self._used)
        self._positions[key] = self._used - 8

    def _read_all_values(self):
        """Yield (key, value, pos). No locking is performed."""
        pos = 8
        while pos < self._used:
            encoded_len = struct.unpack_from(b'i', self._m, pos)[0]
            pos += 4
            encoded = struct.unpack_from('{0}s'.format(encoded_len).encode(), self._m, pos)[0]
            padded_len = encoded_len + (8 - (encoded_len + 4) % 8)
            pos += padded_len
            value = struct.unpack_from(b'd', self._m, pos)[0]
            yield encoded.decode('utf-8'), value, pos
            pos += 8

    def read_all_values(self):
        """Yield (key, value, pos). No locking is performed."""
        for k, v, _ in self._read_all_values():
            yield k, v

    def read_value(self, key):
        with self._lock:
            if key not in self._positions:
                self._init_value(key)
        pos = self._positions[key]
        # We assume that reading from an 8 byte aligned value is atomic
        return struct.unpack_from(b'd', self._m, pos)[0]

    def write_value(self, key, value):
        with self._lock:
            if key not in self._positions:
                self._init_value(key)
        pos = self._positions[key]
        # We assume that writing to an 8 byte aligned value is atomic
        struct.pack_into(b'd', self._m, pos, value)

    def close(self):
        if self._f:
            self._f.close()
            self._f = None


def _MultiProcessValue(__pid=os.getpid()):
    pid = __pid
    files = {}
    files_lock = Lock()

    class _MmapedValue(object):
        '''A float protected by a mutex backed by a per-process mmaped file.'''

        _multiprocess = True

        def __init__(self, typ, metric_name, name, labelnames, labelvalues, multiprocess_mode='', **kwargs):
            if typ == 'gauge':
                file_prefix = typ + '_' +  multiprocess_mode
            else:
                file_prefix = typ
            with files_lock:
                if file_prefix not in files:
                    filename = os.path.join(
                            os.environ['prometheus_multiproc_dir'], '{0}_{1}.db'.format(file_prefix, pid))
                    files[file_prefix] = _MmapedDict(filename)
            self._file = files[file_prefix]
            self._key = json.dumps((metric_name, name, labelnames, labelvalues))
            self._value = self._file.read_value(self._key)
            self._lock = Lock()

        def inc(self, amount):
            with self._lock:
                self._value += amount
                self._file.write_value(self._key, self._value)

        def set(self, value):
            with self._lock:
                self._value = value
                self._file.write_value(self._key, self._value)

        def get(self):
            with self._lock:
                return self._value

    return _MmapedValue


# Should we enable multi-process mode?
# This needs to be chosen before the first metric is constructed,
# and as that may be in some arbitrary library the user/admin has
# no control over we use an enviroment variable.
if 'prometheus_multiproc_dir' in os.environ:
    _ValueClass = _MultiProcessValue()
else:
    _ValueClass = _MutexValue


class _LabelWrapper(object):
    '''Handles labels for the wrapped metric.'''
    def __init__(self, wrappedClass, name, labelnames, **kwargs):
        self._wrappedClass = wrappedClass
        self._type = wrappedClass._type
        self._name = name
        self._labelnames = labelnames
        self._kwargs = kwargs
        self._lock = Lock()
        self._metrics = {}

        for l in labelnames:
            if l.startswith('__'):
                raise ValueError('Invalid label metric name: ' + l)

    def labels(self, *labelvalues, **labelkwargs):
        '''Return the child for the given labelset.

        All metrics can have labels, allowing grouping of related time series.
        Taking a counter as an example:

            from prometheus_client import Counter

            c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
            c.labels('get', '/').inc()
            c.labels('post', '/submit').inc()

        Labels can also be provided as a dict:

            from prometheus_client import Counter

            c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
            c.labels({'method': 'get', 'endpoint': '/'}).inc()
            c.labels({'method': 'post', 'endpoint': '/submit'}).inc()

        See the best practices on [naming](http://prometheus.io/docs/practices/naming/)
        and [labels](http://prometheus.io/docs/practices/instrumentation/#use-labels).
        '''
        if labelvalues and labelkwargs:
            raise ValueError("Can't pass both *args and **kwargs")

        if labelkwargs:
            if sorted(labelkwargs) != sorted(self._labelnames):
                raise ValueError('Incorrect label names')
            labelvalues = tuple([unicode(labelkwargs[l]) for l in self._labelnames])
        else:
            if len(labelvalues) != len(self._labelnames):
                raise ValueError('Incorrect label count')
            labelvalues = tuple([unicode(l) for l in labelvalues])
        with self._lock:
            if labelvalues not in self._metrics:
                self._metrics[labelvalues] = self._wrappedClass(self._name, self._labelnames, labelvalues, **self._kwargs)
            return self._metrics[labelvalues]

    def remove(self, *labelvalues):
        '''Remove the given labelset from the metric.'''
        if len(labelvalues) != len(self._labelnames):
            raise ValueError('Incorrect label count')
        labelvalues = tuple([unicode(l) for l in labelvalues])
        with self._lock:
            del self._metrics[labelvalues]

    def _samples(self):
        with self._lock:
            metrics = self._metrics.copy()
        for labels, metric in metrics.items():
            series_labels = list(dict(zip(self._labelnames, labels)).items())
            for suffix, sample_labels, value in metric._samples():
                yield (suffix, dict(series_labels + list(sample_labels.items())), value)


def _MetricWrapper(cls):
    '''Provides common functionality for metrics.'''
    def init(name, documentation, labelnames=(), namespace='', subsystem='', registry=REGISTRY, **kwargs):
        full_name = ''
        if namespace:
            full_name += namespace + '_'
        if subsystem:
            full_name += subsystem + '_'
        full_name += name

        if labelnames:
            labelnames = tuple(labelnames)
            for l in labelnames:
                if not _METRIC_LABEL_NAME_RE.match(l):
                    raise ValueError('Invalid label metric name: ' + l)
                if _RESERVED_METRIC_LABEL_NAME_RE.match(l):
                    raise ValueError('Reserved label metric name: ' + l)
                if l in cls._reserved_labelnames:
                    raise ValueError('Reserved label metric name: ' + l)
            collector = _LabelWrapper(cls, name, labelnames, **kwargs)
        else:
            collector = cls(name, labelnames, (), **kwargs)

        if not _METRIC_NAME_RE.match(full_name):
            raise ValueError('Invalid metric name: ' + full_name)

        def collect():
            metric = Metric(full_name, documentation, cls._type)
            for suffix, labels, value in collector._samples():
                metric.add_sample(full_name + suffix, labels, value)
            return [metric]
        collector.collect = collect

        if registry:
            registry.register(collector)
        return collector

    return init


@_MetricWrapper
class Counter(object):
    '''A Counter tracks counts of events or running totals.

    Example use cases for Counters:
    - Number of requests processed
    - Number of items that were inserted into a queue
    - Total amount of data that a system has processed

    Counters can only go up (and be reset when the process restarts). If your use case can go down,
    you should use a Gauge instead.

    An example for a Counter:

        from prometheus_client import Counter

        c = Counter('my_failures_total', 'Description of counter')
        c.inc()     # Increment by 1
        c.inc(1.6)  # Increment by given value

    There are utilities to count exceptions raised:

        @c.count_exceptions()
        def f():
            pass

        with c.count_exceptions():
            pass

        # Count only one type of exception
        with c.count_exceptions(ValueError):
            pass
    '''
    _type = 'counter'
    _reserved_labelnames = []

    def __init__(self, name, labelnames, labelvalues):
        self._value = _ValueClass(self._type, name, name, labelnames, labelvalues)

    def inc(self, amount=1):
        '''Increment counter by the given amount.'''
        if amount < 0:
            raise ValueError('Counters can only be incremented by non-negative amounts.')
        self._value.inc(amount)

    def count_exceptions(self, exception=Exception):
        '''Count exceptions in a block of code or function.

        Can be used as a function decorator or context manager.
        Increments the counter when an exception of the given
        type is raised up out of the code.
        '''
        return _ExceptionCounter(self, exception)

    def _samples(self):
        return (('', {}, self._value.get()), )


@_MetricWrapper
class Gauge(object):
    '''Gauge metric, to report instantaneous values.

     Examples of Gauges include:
        - Inprogress requests
        - Number of items in a queue
        - Free memory
        - Total memory
        - Temperature

     Gauges can go both up and down.

        from prometheus_client import Gauge

        g = Gauge('my_inprogress_requests', 'Description of gauge')
        g.inc()      # Increment by 1
        g.dec(10)    # Decrement by given value
        g.set(4.2)   # Set to a given value

     There are utilities for common use cases:

        g.set_to_current_time()   # Set to current unixtime

        # Increment when entered, decrement when exited.
        @g.track_inprogress()
        def f():
            pass

        with g.track_inprogress():
            pass

     A Gauge can also take its value from a callback:

        d = Gauge('data_objects', 'Number of objects')
        my_dict = {}
        d.set_function(lambda: len(my_dict))
    '''
    _type = 'gauge'
    _reserved_labelnames = []

    def __init__(self, name, labelnames, labelvalues, multiprocess_mode='all'):
        if (_ValueClass._multiprocess
                and multiprocess_mode not in ['min', 'max', 'livesum', 'liveall', 'all']):
            raise ValueError('Invalid multiprocess mode: ' + multiprocess_mode)
        self._value = _ValueClass(self._type, name, name, labelnames,
                labelvalues, multiprocess_mode=multiprocess_mode)

    def inc(self, amount=1):
        '''Increment gauge by the given amount.'''
        self._value.inc(amount)

    def dec(self, amount=1):
        '''Decrement gauge by the given amount.'''
        self._value.inc(-amount)

    def set(self, value):
        '''Set gauge to the given value.'''
        self._value.set(float(value))

    def set_to_current_time(self):
        '''Set gauge to the current unixtime.'''
        self.set(default_timer())

    def track_inprogress(self):
        '''Track inprogress blocks of code or functions.

        Can be used as a function decorator or context manager.
        Increments the gauge when the code is entered,
        and decrements when it is exited.
        '''
        return _InprogressTracker(self)

    def time(self):
        '''Time a block of code or function, and set the duration in seconds.

        Can be used as a function decorator or context manager.
        '''
        return _GaugeTimer(self)

    def set_function(self, f):
        '''Call the provided function to return the Gauge value.

        The function must return a float, and may be called from
        multiple threads. All other methods of the Gauge become NOOPs.
        '''
        def samples(self):
            return (('', {}, float(f())), )
        self._samples = types.MethodType(samples, self)

    def _samples(self):
        return (('', {}, self._value.get()), )


@_MetricWrapper
class Summary(object):
    '''A Summary tracks the size and number of events.

    Example use cases for Summaries:
    - Response latency
    - Request size

    Example for a Summary:

        from prometheus_client import Summary

        s = Summary('request_size_bytes', 'Request size (bytes)')
        s.observe(512)  # Observe 512 (bytes)

    Example for a Summary using time:

        from prometheus_client import Summary

        REQUEST_TIME = Summary('response_latency_seconds', 'Response latency (seconds)')

        @REQUEST_TIME.time()
        def create_response(request):
          """A dummy function"""
          time.sleep(1)

    Example for using the same Summary object as a context manager:

        with REQUEST_TIME.time():
            pass  # Logic to be timed
    '''
    _type = 'summary'
    _reserved_labelnames = ['quantile']

    def __init__(self, name, labelnames, labelvalues):
        self._count = _ValueClass(self._type, name, name + '_count', labelnames, labelvalues)
        self._sum = _ValueClass(self._type, name, name + '_sum', labelnames, labelvalues)

    def observe(self, amount):
        '''Observe the given amount.'''
        self._count.inc(1)
        self._sum.inc(amount)

    def time(self):
        '''Time a block of code or function, and observe the duration in seconds.

        Can be used as a function decorator or context manager.
        '''
        return _SummaryTimer(self)

    def _samples(self):
        return (
            ('_count', {}, self._count.get()),
            ('_sum', {}, self._sum.get()))


def _floatToGoString(d):
    if d == _INF:
        return '+Inf'
    elif d == _MINUS_INF:
        return '-Inf'
    elif math.isnan(d):
        return 'NaN'
    else:
        return repr(float(d))


@_MetricWrapper
class Histogram(object):
    '''A Histogram tracks the size and number of events in buckets.

    You can use Histograms for aggregatable calculation of quantiles.

    Example use cases:
    - Response latency
    - Request size

    Example for a Histogram:

        from prometheus_client import Histogram

        h = Histogram('request_size_bytes', 'Request size (bytes)')
        h.observe(512)  # Observe 512 (bytes)

    Example for a Histogram using time:

        from prometheus_client import Histogram

        REQUEST_TIME = Histogram('response_latency_seconds', 'Response latency (seconds)')

        @REQUEST_TIME.time()
        def create_response(request):
          """A dummy function"""
          time.sleep(1)

    Example of using the same Histogram object as a context manager:

        with REQUEST_TIME.time():
            pass  # Logic to be timed

    The default buckets are intended to cover a typical web/rpc request from milliseconds to seconds.
    They can be overridden by passing `buckets` keyword argument to `Histogram`.

    **NB** The Python client doesn't store or expose quantile information at this time.
    '''
    _type = 'histogram'
    _reserved_labelnames = ['histogram']

    def __init__(self, name, labelnames, labelvalues, buckets=(.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, _INF)):
        self._sum = _ValueClass(self._type, name, name + '_sum', labelnames, labelvalues)
        buckets = [float(b) for b in buckets]
        if buckets != sorted(buckets):
            # This is probably an error on the part of the user,
            # so raise rather than sorting for them.
            raise ValueError('Buckets not in sorted order')
        if buckets and buckets[-1] != _INF:
            buckets.append(_INF)
        if len(buckets) < 2:
            raise ValueError('Must have at least two buckets')
        self._upper_bounds = buckets
        self._buckets = []
        bucket_labelnames = labelnames + ('le',)
        for b in buckets:
          self._buckets.append(_ValueClass(self._type, name, name + '_bucket', bucket_labelnames, labelvalues + (_floatToGoString(b),)))

    def observe(self, amount):
        '''Observe the given amount.'''
        self._sum.inc(amount)
        for i, bound in enumerate(self._upper_bounds):
            if amount <= bound:
                self._buckets[i].inc(1)
                break

    def time(self):
        '''Time a block of code or function, and observe the duration in seconds.

        Can be used as a function decorator or context manager.
        '''
        return _HistogramTimer(self)

    def _samples(self):
        samples = []
        acc = 0
        for i, bound in enumerate(self._upper_bounds):
            acc += self._buckets[i].get()
            samples.append(('_bucket', {'le': _floatToGoString(bound)}, acc))
        samples.append(('_count', {}, acc))
        samples.append(('_sum', {}, self._sum.get()))
        return tuple(samples)


class _HistogramTimer(object):
    def __init__(self, histogram):
        self._histogram = histogram

    def __enter__(self):
        self._start = default_timer()

    def __exit__(self, typ, value, traceback):
        # Time can go backwards.
        self._histogram.observe(max(default_timer() - self._start, 0))

    def __call__(self, f):
        def wrapped(func, *args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return decorate(f, wrapped)


class _ExceptionCounter(object):
    def __init__(self, counter, exception):
        self._counter = counter
        self._exception = exception

    def __enter__(self):
        pass

    def __exit__(self, typ, value, traceback):
        if isinstance(value, self._exception):
            self._counter.inc()

    def __call__(self, f):
        def wrapped(func, *args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return decorate(f, wrapped)


class _InprogressTracker(object):
    def __init__(self, gauge):
        self._gauge = gauge

    def __enter__(self):
        self._gauge.inc()

    def __exit__(self, typ, value, traceback):
        self._gauge.dec()

    def __call__(self, f):
        def wrapped(func, *args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return decorate(f, wrapped)


class _SummaryTimer(object):
    def __init__(self, summary):
        self._summary = summary

    def __enter__(self):
        self._start = default_timer()

    def __exit__(self, typ, value, traceback):
        # Time can go backwards.
        self._summary.observe(max(default_timer() - self._start, 0))

    def __call__(self, f):
        def wrapped(func, *args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return decorate(f, wrapped)


class _GaugeTimer(object):
    def __init__(self, gauge):
        self._gauge = gauge

    def __enter__(self):
        self._start = default_timer()

    def __exit__(self, typ, value, traceback):
        # Time can go backwards.
        self._gauge.set(max(default_timer() - self._start, 0))

    def __call__(self, f):
        def wrapped(func, *args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return decorate(f, wrapped)
