#!/usr/bin/python

from __future__ import unicode_literals

import copy
import re
import time
import types

try:
    from BaseHTTPServer import BaseHTTPRequestHandler
except ImportError:
    # Python 3
    unicode = str

from functools import wraps
from threading import Lock

_METRIC_NAME_RE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$')
_METRIC_LABEL_NAME_RE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$')
_RESERVED_METRIC_LABEL_NAME_RE = re.compile(r'^__.*$')
_INF = float("inf")
_MINUS_INF = float("-inf")


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
            for n, l, value in metric._samples:
                if n == name and l == labels:
                    return value
        return None


REGISTRY = CollectorRegistry()
'''The default registry.'''

_METRIC_TYPES = ('counter', 'gauge', 'summary', 'histogram', 'untyped')


class Metric(object):
    '''A single metric and it's samples.'''
    def __init__(self, name, documentation, typ):
        self._name = name
        self._documentation = documentation
        if typ not in _METRIC_TYPES:
            raise ValueError('Invalid metric type: ' + typ)
        self._type = typ
        self._samples = []

    '''Add a sample to the metric'''
    def add_sample(self, name, labels, value):
        self._samples.append((name, labels, value))


class _LabelWrapper(object):
    '''Handles labels for the wrapped metric.'''
    def __init__(self, wrappedClass, labelnames, **kwargs):
        self._wrappedClass = wrappedClass
        self._type = wrappedClass._type
        self._labelnames = labelnames
        self._kwargs = kwargs
        self._lock = Lock()
        self._metrics = {}

        for l in labelnames:
            if l.startswith('__'):
                raise ValueError('Invalid label metric name: ' + l)

    def labels(self, *labelvalues):
        '''Return the child for the given labelset.

        Labels can be provided as a tuple or as a dict:
            c = Counter('c', 'counter', ['l', 'm'])
            # Set labels by position
            c.labels('0', '1').inc()
            # Set labels by name
            c.labels({'l': '0', 'm': '1'}).inc()
        '''
        if len(labelvalues) == 1 and type(labelvalues[0]) == dict:
            if sorted(labelvalues[0].keys()) != sorted(self._labelnames):
                raise ValueError('Incorrect label names')
            labelvalues = tuple([unicode(labelvalues[0][l]) for l in self._labelnames])
        else:
            if len(labelvalues) != len(self._labelnames):
                raise ValueError('Incorrect label count')
            labelvalues = tuple([unicode(l) for l in labelvalues])
        with self._lock:
            if labelvalues not in self._metrics:
                self._metrics[labelvalues] = self._wrappedClass(**self._kwargs)
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
        if labelnames:
            for l in labelnames:
                if not _METRIC_LABEL_NAME_RE.match(l):
                    raise ValueError('Invalid label metric name: ' + l)
                if _RESERVED_METRIC_LABEL_NAME_RE.match(l):
                    raise ValueError('Reserved label metric name: ' + l)
                if l in cls._reserved_labelnames:
                    raise ValueError('Reserved label metric name: ' + l)
            collector = _LabelWrapper(cls, labelnames, **kwargs)
        else:
            collector = cls(**kwargs)

        full_name = ''
        if namespace:
            full_name += namespace + '_'
        if subsystem:
            full_name += subsystem + '_'
        full_name += name

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
    '''
    _type = 'counter'
    _reserved_labelnames = []

    def __init__(self):
        self._value = 0.0
        self._lock = Lock()

    def inc(self, amount=1):
        '''Increment counter by the given amount.'''
        if amount < 0:
            raise ValueError('Counters can only be incremented by non-negative amounts.')
        with self._lock:
            self._value += amount

    def count_exceptions(self, exception=Exception):
        '''Count exceptions in a block of code or function.

        Can be used as a function decorator or context manager.
        Increments the counter when an exception of the given
        type is raised up out of the code.
        '''

        class ExceptionCounter(object):
            def __init__(self, counter):
                self._counter = counter

            def __enter__(self):
                pass

            def __exit__(self, typ, value, traceback):
                if isinstance(value, exception):
                    self._counter.inc()

            def __call__(self, f):
                @wraps(f)
                def wrapped(*args, **kwargs):
                    with self:
                        return f(*args, **kwargs)
                return wrapped

        return ExceptionCounter(self)

    def _samples(self):
        with self._lock:
            return (('', {}, self._value), )


@_MetricWrapper
class Gauge(object):
    _type = 'gauge'
    _reserved_labelnames = []

    def __init__(self):
        self._value = 0.0
        self._lock = Lock()

    def inc(self, amount=1):
        '''Increment gauge by the given amount.'''
        with self._lock:
            self._value += amount

    def dec(self, amount=1):
        '''Decrement gauge by the given amount.'''
        with self._lock:
            self._value -= amount

    def set(self, value):
        '''Set gauge to the given value.'''
        with self._lock:
            self._value = float(value)

    def set_to_current_time(self):
        '''Set gauge to the current unixtime.'''
        self.set(time.time())

    def track_inprogress(self):
        '''Track inprogress blocks of code or functions.

        Can be used as a function decorator or context manager.
        Increments the gauge when the code is entered,
        and decrements when it is exited.
        '''

        class InprogressTracker(object):
            def __init__(self, gauge):
                self._gauge = gauge

            def __enter__(self):
                self._gauge.inc()

            def __exit__(self, typ, value, traceback):
                self._gauge.dec()

            def __call__(self, f):
                @wraps(f)
                def wrapped(*args, **kwargs):
                    with self:
                        return f(*args, **kwargs)
                return wrapped

        return InprogressTracker(self)

    def time(self):
        '''Time a block of code or function, and set the duration in seconds.

        Can be used as a function decorator or context manager.
        '''

        class Timer(object):
            def __init__(self, gauge):
                self._gauge = gauge

            def __enter__(self):
                self._start = time.time()

            def __exit__(self, typ, value, traceback):
                # Time can go backwards.
                self._gauge.set(max(time.time() - self._start, 0))

            def __call__(self, f):
                @wraps(f)
                def wrapped(*args, **kwargs):
                    with self:
                        return f(*args, **kwargs)
                return wrapped

        return Timer(self)

    def set_function(self, f):
        '''Call the provided function to return the Gauge value.

        The function must return a float, and may be called from
        multiple threads.
        All other methods of the Gauge become NOOPs.
        '''
        def samples(self):
            return (('', {}, float(f())), )
        self._samples = types.MethodType(samples, self)

    def _samples(self):
        with self._lock:
            return (('', {}, self._value), )


@_MetricWrapper
class Summary(object):
    '''A Summary tracks the size and number of events.

    Example use cases for Summaries:
    - Response latency
    - Request size

    Example for a Summary:

    from prometheus_client import Summary
    s = Summary('request_size_bytes', 'Request size (bytes)')
    s.observe(512) # Observe 512 (bytes)


    Example for a Summary using time:
    from prometheus_client import Summary
    REQUEST_TIME = Summary('response_latency_seconds', 'Response latency (seconds)')

    @REQUEST_TIME.time()
    def create_response(request):
    """A dummy function"""
      time.sleep(1)

    '''
    _type = 'summary'
    _reserved_labelnames = ['quantile']

    def __init__(self):
        self._count = 0.0
        self._sum = 0.0
        self._lock = Lock()

    def observe(self, amount):
        '''Observe the given amount.'''
        with self._lock:
            self._count += 1
            self._sum += amount

    def time(self):
        '''Time a block of code or function, and observe the duration in seconds.

        Can be used as a function decorator or context manager.
        '''

        class Timer(object):
            def __init__(self, summary):
                self._summary = summary

            def __enter__(self):
                self._start = time.time()

            def __exit__(self, typ, value, traceback):
                # Time can go backwards.
                self._summary.observe(max(time.time() - self._start, 0))

            def __call__(self, f):
                @wraps(f)
                def wrapped(*args, **kwargs):
                    with self:
                        return f(*args, **kwargs)
                return wrapped

        return Timer(self)

    def _samples(self):
        with self._lock:
            return (
                ('_count', {}, self._count),
                ('_sum', {}, self._sum))


def _floatToGoString(d):
    if d == _INF:
        return '+Inf'
    elif d == _MINUS_INF:
        return '-Inf'
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
    h.observe(512) # Observe 512 (bytes)


    Example for a Histogram using time:
    from prometheus_client import Histogram
    REQUEST_TIME = Histogram('response_latency_seconds', 'Response latency (seconds)')

    @REQUEST_TIME.time()
    def create_response(request):
    """A dummy function"""
      time.sleep(1)

    The default buckets are intended to cover a typical web/rpc request from milliseconds to seconds.
    They can be overridden by passing `buckets` keyword argument to `Histogram`.
    '''
    _type = 'histogram'
    _reserved_labelnames = ['histogram']

    def __init__(self, buckets=(.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, _INF)):
        self._sum = 0.0
        self._lock = Lock()
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
        self._buckets = [0.0] * len(buckets)

    def observe(self, amount):
        '''Observe the given amount.'''
        with self._lock:
            self._sum += amount
            for i, bound in enumerate(self._upper_bounds):
                if amount <= bound:
                    self._buckets[i] += 1
                    break

    def time(self):
        '''Time a block of code or function, and observe the duration in seconds.

        Can be used as a function decorator or context manager.
        '''

        class Timer(object):
            def __init__(self, histogram):
                self._histogram = histogram

            def __enter__(self):
                self._start = time.time()

            def __exit__(self, typ, value, traceback):
                # Time can go backwards.
                self._histogram.observe(max(time.time() - self._start, 0))

            def __call__(self, f):
                @wraps(f)
                def wrapped(*args, **kwargs):
                    with self:
                        return f(*args, **kwargs)
                return wrapped

        return Timer(self)

    def _samples(self):
        with self._lock:
            samples = []
            acc = 0
            for i, bound in enumerate(self._upper_bounds):
                acc += self._buckets[i]
                samples.append(('_bucket', {'le': _floatToGoString(bound)}, acc))
            samples.append(('_count', {}, acc))
            samples.append(('_sum', {}, self._sum))
            return tuple(samples)

