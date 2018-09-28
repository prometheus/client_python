#!/usr/bin/python

from __future__ import unicode_literals

import copy
import math
import os
import sys
import time
import types

from threading import Lock

from .metrics import *  # noqa
from .metrics import _METRIC_LABEL_NAME_RE, _METRIC_NAME_RE, _RESERVED_METRIC_LABEL_NAME_RE
from .context_managers import _ExceptionCounter, _InprogressTracker, _Timer

if sys.version_info > (3,):
    unicode = str

_INF = float("inf")
_MINUS_INF = float("-inf")


class CollectorRegistry(object):
    '''Metric collector registry.

    Collectors must have a no-argument method 'collect' that returns a list of
    Metric objects. The returned metrics should be consistent with the Prometheus
    exposition formats.
    '''

    def __init__(self, auto_describe=False):
        self._collector_to_names = {}
        self._names_to_collectors = {}
        self._auto_describe = auto_describe
        self._lock = Lock()

    def register(self, collector):
        '''Add a collector to the registry.'''
        with self._lock:
            names = self._get_names(collector)
            duplicates = set(self._names_to_collectors).intersection(names)
            if duplicates:
                raise ValueError(
                    'Duplicated timeseries in CollectorRegistry: {0}'.format(
                        duplicates))
            for name in names:
                self._names_to_collectors[name] = collector
            self._collector_to_names[collector] = names

    def unregister(self, collector):
        '''Remove a collector from the registry.'''
        with self._lock:
            for name in self._collector_to_names[collector]:
                del self._names_to_collectors[name]
            del self._collector_to_names[collector]

    def _get_names(self, collector):
        '''Get names of timeseries the collector produces.'''
        desc_func = None
        # If there's a describe function, use it.
        try:
            desc_func = collector.describe
        except AttributeError:
            pass
        # Otherwise, if auto describe is enabled use the collect function.
        if not desc_func and self._auto_describe:
            desc_func = collector.collect

        if not desc_func:
            return []

        result = []
        type_suffixes = {
            'counter': ['_total', '_created'],
            'summary': ['', '_sum', '_count', '_created'],
            'histogram': ['_bucket', '_sum', '_count', '_created'],
            'info': ['_info'],
        }
        for metric in desc_func():
            for suffix in type_suffixes.get(metric.type, ['']):
                result.append(metric.name + suffix)
        return result

    def collect(self):
        '''Yields metrics from the collectors in the registry.'''
        collectors = None
        with self._lock:
            collectors = copy.copy(self._collector_to_names)
        for collector in collectors:
            for metric in collector.collect():
                yield metric

    def restricted_registry(self, names):
        '''Returns object that only collects some metrics.

        Returns an object which upon collect() will return
        only samples with the given names.

        Intended usage is:
            generate_latest(REGISTRY.restricted_registry(['a_timeseries']))

        Experimental.'''
        names = set(names)
        collectors = set()
        with self._lock:
            for name in names:
                if name in self._names_to_collectors:
                    collectors.add(self._names_to_collectors[name])
        metrics = []
        for collector in collectors:
            for metric in collector.collect():
                samples = [s for s in metric.samples if s[0] in names]
                if samples:
                    m = Metric(metric.name, metric.documentation, metric.type)
                    m.samples = samples
                    metrics.append(m)

        class RestrictedRegistry(object):
            def collect(self):
                return metrics

        return RestrictedRegistry()

    def get_sample_value(self, name, labels=None):
        '''Returns the sample value, or None if not found.

        This is inefficient, and intended only for use in unittests.
        '''
        if labels is None:
            labels = {}
        for metric in self.collect():
            for s in metric.samples:
                if s.name == name and s.labels == labels:
                    return s.value
        return None


REGISTRY = CollectorRegistry(auto_describe=True)
'''The default registry.'''



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


# Should we enable multi-process mode?
# This needs to be chosen before the first metric is constructed,
# and as that may be in some arbitrary library the user/admin has
# no control over we use an environment variable.
if 'prometheus_multiproc_dir' in os.environ:
    from .multiprocess import _MultiProcessValue

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

        Labels can also be provided as keyword arguments:

            from prometheus_client import Counter

            c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
            c.labels(method='get', endpoint='/').inc()
            c.labels(method='post', endpoint='/submit').inc()

        See the best practices on [naming](http://prometheus.io/docs/practices/naming/)
        and [labels](http://prometheus.io/docs/practices/instrumentation/#use-labels).
        '''
        if labelvalues and labelkwargs:
            raise ValueError("Can't pass both *args and **kwargs")

        if labelkwargs:
            if sorted(labelkwargs) != sorted(self._labelnames):
                raise ValueError('Incorrect label names')
            labelvalues = tuple(unicode(labelkwargs[l]) for l in self._labelnames)
        else:
            if len(labelvalues) != len(self._labelnames):
                raise ValueError('Incorrect label count')
            labelvalues = tuple(unicode(l) for l in labelvalues)
        with self._lock:
            if labelvalues not in self._metrics:
                self._metrics[labelvalues] = self._wrappedClass(self._name, self._labelnames, labelvalues,
                    **self._kwargs)
            return self._metrics[labelvalues]

    def remove(self, *labelvalues):
        '''Remove the given labelset from the metric.'''
        if len(labelvalues) != len(self._labelnames):
            raise ValueError('Incorrect label count')
        labelvalues = tuple(unicode(l) for l in labelvalues)
        with self._lock:
            del self._metrics[labelvalues]

    def _samples(self):
        with self._lock:
            metrics = self._metrics.copy()
        for labels, metric in metrics.items():
            series_labels = list(zip(self._labelnames, labels))
            for suffix, sample_labels, value in metric._samples():
                yield (suffix, dict(series_labels + list(sample_labels.items())), value)


def _MetricWrapper(cls):
    '''Provides common functionality for metrics.'''

    def init(name, documentation, labelnames=(), namespace='', subsystem='', unit='', registry=REGISTRY, **kwargs):
        full_name = ''
        if namespace:
            full_name += namespace + '_'
        if subsystem:
            full_name += subsystem + '_'
        full_name += name

        if unit and not full_name.endswith("_" + unit):
            full_name += "_" + unit
        if unit and cls._type in ('info', 'stateset'):
            raise ValueError('Metric name is of a type that cannot have a unit: ' + full_name)

        if cls._type == 'counter' and full_name.endswith('_total'):
            full_name = full_name[:-6]  # Munge to OpenMetrics.

        if labelnames:
            labelnames = tuple(labelnames)
            for l in labelnames:
                if not _METRIC_LABEL_NAME_RE.match(l):
                    raise ValueError('Invalid label metric name: ' + l)
                if _RESERVED_METRIC_LABEL_NAME_RE.match(l):
                    raise ValueError('Reserved label metric name: ' + l)
                if l in cls._reserved_labelnames:
                    raise ValueError('Reserved label metric name: ' + l)
            collector = _LabelWrapper(cls, full_name, labelnames, **kwargs)
        else:
            collector = cls(full_name, (), (), **kwargs)

        if not _METRIC_NAME_RE.match(full_name):
            raise ValueError('Invalid metric name: ' + full_name)

        def describe():
            return [Metric(full_name, documentation, cls._type)]

        collector.describe = describe

        def collect():
            metric = Metric(full_name, documentation, cls._type, unit)
            for suffix, labels, value in collector._samples():
                metric.add_sample(full_name + suffix, labels, value)
            return [metric]

        collector.collect = collect

        if registry:
            registry.register(collector)
        return collector

    init.__wrapped__ = cls
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
        if name.endswith('_total'):
            name = name[:-6]
        self._value = _ValueClass(self._type, name, name + '_total', labelnames, labelvalues)
        self._created = time.time()

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
        return (('_total', {}, self._value.get()),
        ('_created', {}, self._created))


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
    _MULTIPROC_MODES = frozenset(('min', 'max', 'livesum', 'liveall', 'all'))

    def __init__(self, name, labelnames, labelvalues, multiprocess_mode='all'):
        if (_ValueClass._multiprocess and
            multiprocess_mode not in self._MULTIPROC_MODES):
            raise ValueError('Invalid multiprocess mode: ' + multiprocess_mode)
        self._value = _ValueClass(
            self._type, name, name, labelnames, labelvalues,
            multiprocess_mode=multiprocess_mode)

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
        self.set(time.time())

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
        return _Timer(self.set)

    def set_function(self, f):
        '''Call the provided function to return the Gauge value.

        The function must return a float, and may be called from
        multiple threads. All other methods of the Gauge become NOOPs.
        '''

        def samples(self):
            return (('', {}, float(f())),)

        self._samples = types.MethodType(samples, self)

    def _samples(self):
        return (('', {}, self._value.get()),)


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
        self._created = time.time()

    def observe(self, amount):
        '''Observe the given amount.'''
        self._count.inc(1)
        self._sum.inc(amount)

    def time(self):
        '''Time a block of code or function, and observe the duration in seconds.

        Can be used as a function decorator or context manager.
        '''
        return _Timer(self.observe)

    def _samples(self):
        return (
            ('_count', {}, self._count.get()),
            ('_sum', {}, self._sum.get()),
            ('_created', {}, self._created))


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
    '''
    _type = 'histogram'
    _reserved_labelnames = ['le']

    def __init__(self, name, labelnames, labelvalues,
        buckets=(.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, _INF)):
        self._created = time.time()
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
            self._buckets.append(_ValueClass(self._type, name, name + '_bucket', bucket_labelnames,
                labelvalues + (_floatToGoString(b),)))

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
        return _Timer(self.observe)

    def _samples(self):
        samples = []
        acc = 0
        for i, bound in enumerate(self._upper_bounds):
            acc += self._buckets[i].get()
            samples.append(('_bucket', {'le': _floatToGoString(bound)}, acc))
        samples.append(('_count', {}, acc))
        samples.append(('_sum', {}, self._sum.get()))
        samples.append(('_created', {}, self._created))
        return tuple(samples)


@_MetricWrapper
class Info(object):
    '''Info metric, key-value pairs.

     Examples of Info include:
        - Build information
        - Version information
        - Potential target metadata

     Example usage:
        from prometheus_client import Info

        i = Info('my_build', 'Description of info')
        i.info({'version': '1.2.3', 'buildhost': 'foo@bar'})

     Info metrics do not work in multiprocess mode.
    '''
    _type = 'info'
    _reserved_labelnames = []

    def __init__(self, name, labelnames, labelvalues):
        self._labelnames = set(labelnames)
        self._lock = Lock()
        self._value = {}

    def info(self, val):
        '''Set info metric.'''
        if self._labelnames.intersection(val.keys()):
            raise ValueError('Overlapping labels for Info metric, metric: %s child: %s' % (
                self._labelnames, val))
        with self._lock:
            self._value = dict(val)

    def _samples(self):
        with self._lock:
            return (('_info', self._value, 1.0,),)


@_MetricWrapper
class Enum(object):
    '''Enum metric, which of a set of states is true.

     Example usage:
        from prometheus_client import Enum

        e = Enum('task_state', 'Description of enum',
          states=['starting', 'running', 'stopped'])
        e.state('running')

     The first listed state will be the default.
     Enum metrics do not work in multiprocess mode.
    '''
    _type = 'stateset'
    _reserved_labelnames = []

    def __init__(self, name, labelnames, labelvalues, states=None):
        if name in labelnames:
            raise ValueError('Overlapping labels for Enum metric: %s' % (name,))
        if not states:
            raise ValueError('No states provided for Enum metric: %s' % (name,))
        self._name = name
        self._states = states
        self._value = 0
        self._lock = Lock()

    def state(self, state):
        '''Set enum metric state.'''
        with self._lock:
            self._value = self._states.index(state)

    def _samples(self):
        with self._lock:
            return [('', {self._name: s}, 1 if i == self._value else 0,)
                for i, s in enumerate(self._states)]
