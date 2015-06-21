#!/usr/bin/python

from __future__ import unicode_literals

import copy
import re
import os
import time
import threading
import types
try:
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
except ImportError:
    # Python 3
    unicode = str
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer
try:
  import resource
  _PAGESIZE = resource.getpagesize()
except ImportError:
  # Not Unix
  _PAGESIZE = 4096

from functools import wraps
from threading import Lock

__all__ = ['Counter', 'Gauge', 'Summary', 'Histogram']
# http://stackoverflow.com/questions/19913653/no-unicode-in-all-for-a-packages-init
__all__ = [n.encode('ascii') for n in __all__]

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


CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4; charset=utf-8'
'''Content type of the latest text format'''


def generate_latest(registry=REGISTRY):
    '''Returns the metrics from the registry in latest text format as a string.'''
    output = []
    for metric in registry.collect():
        output.append('# HELP {0} {1}'.format(
            metric._name, metric._documentation.replace('\\', r'\\').replace('\n', r'\n')))
        output.append('\n# TYPE {0} {1}\n'.format(metric._name, metric._type))
        for name, labels, value in metric._samples:
            if labels:
                labelstr = '{{{0}}}'.format(','.join(
                    ['{0}="{1}"'.format(
                     k, v.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"'))
                     for k, v in sorted(labels.items())]))
            else:
                labelstr = ''
            output.append('{0}{1} {2}\n'.format(name, labelstr, _floatToGoString(value)))
    return ''.join(output).encode('utf-8')


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(generate_latest(REGISTRY))

    def log_message(self, format, *args):
        return


def start_http_server(port, addr=''):
    """Starts a HTTP server for prometheus metrics as a daemon thread."""
    class PrometheusMetricsServer(threading.Thread):
        def run(self):
            httpd = HTTPServer((addr, port), MetricsHandler)
            httpd.serve_forever()
    t = PrometheusMetricsServer()
    t.daemon = True
    t.start()


def write_to_textfile(path, registry):
    '''Write metrics to the given path.

    This is intended for use with the Node exporter textfile collector.
    The path must end in .prom for the textfile collector to process it.'''
    tmppath = '%s.%s.%s' % (path, os.getpid(), threading.current_thread().ident)
    with open(tmppath, 'wb') as f:
        f.write(generate_latest(registry))
    # rename(2) is atomic.
    os.rename(tmppath, path)


class ProcessCollector(object):
    """Collector for Standard Exports such as cpu and memory."""
    def __init__(self, namespace='', pid=lambda: 'self', proc='/proc', registry=REGISTRY):
        self._namespace = namespace
        self._pid = pid
        self._proc = proc
        if namespace:
            self._prefix = namespace + '_process_'
        else:
            self._prefix = 'process_'
        self._ticks = 100.0
        try:
            self._ticks = os.sysconf('SC_CLK_TCK')
        except (ValueError, TypeError, AttributeError):
            pass

        # This is used to test if we can access /proc.
        self._btime = 0
        try:
            self._btime = self._boot_time()
        except IOError:
            pass
        if registry:
          registry.register(self)

    def _boot_time(self):
        with open(os.path.join(self._proc, 'stat')) as stat:
            for line in stat:
                if line.startswith('btime '):
                    return float(line.split()[1])

    def collect(self):
        if not self._btime:
            return []

        try:
          pid = os.path.join(self._proc, str(self._pid()).strip())
        except:
          # File likely didn't exist, fail silently.
          raise
          return []

        result = []
        try:
            with open(os.path.join(pid, 'stat')) as stat:
                parts = (stat.read().split(')')[-1].split())
            vmem = Metric(self._prefix + 'virtual_memory_bytes', 'Virtual memory size in bytes', 'gauge')
            vmem.add_sample(self._prefix + 'virtual_memory_bytes', {}, float(parts[20]))
            rss = Metric(self._prefix + 'resident_memory_bytes', 'Resident memory size in bytes', 'gauge')
            rss.add_sample(self._prefix + 'resident_memory_bytes', {}, float(parts[21]) * _PAGESIZE)
            start_time = Metric(self._prefix + 'start_time_seconds',
                                'Start time of the process since unix epoch in seconds.', 'gauge')
            start_time_secs = float(parts[19]) / self._ticks
            start_time.add_sample(self._prefix + 'start_time_seconds',{} , start_time_secs + self._btime)
            utime = float(parts[11]) / self._ticks
            stime = float(parts[12]) / self._ticks
            cpu = Metric(self._prefix + 'cpu_seconds_total',
                         'Total user and system CPU time spent in seconds.', 'counter')
            cpu.add_sample(self._prefix + 'cpu_seconds_total', {}, utime + stime)
            result.extend([vmem, rss, start_time, cpu])
        except IOError:
            pass

        try:
            max_fds = Metric(self._prefix + 'max_fds', 'Maximum number of open file descriptors.', 'gauge')
            with open(os.path.join(pid, 'limits')) as limits:
                for line in limits:
                    if line.startswith('Max open file'):
                        max_fds.add_sample(self._prefix + 'max_fds', {}, float(line.split()[3]))
                        break
            open_fds = Metric(self._prefix + 'open_fds', 'Number of open file descriptors.', 'gauge')
            open_fds.add_sample(self._prefix + 'open_fds', {}, len(os.listdir(os.path.join(pid, 'fd'))))
            result.extend([open_fds, max_fds])
        except IOError:
            pass

        return result


PROCESS_COLLECTOR = ProcessCollector()
"""Default ProcessCollector in default Registry REGISTRY."""


if __name__ == '__main__':
    c = Counter('cc', 'A counter')
    c.inc()

    g = Gauge('gg', 'A gauge')
    g.set(17)

    s = Summary('ss', 'A summary', ['a', 'b'])
    s.labels('c', 'd').observe(17)

    h = Histogram('hh', 'A histogram')
    h.observe(.6)

    from BaseHTTPServer import HTTPServer
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, MetricsHandler)
    httpd.serve_forever()
