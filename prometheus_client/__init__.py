#!/usr/bin/python

import copy
import re
from BaseHTTPServer import BaseHTTPRequestHandler
from threading import Lock

__all__ = ['Counter', 'Gauge', 'Summary']

_METRIC_NAME_RE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$')
_METRIC_LABEL_NAME_RE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$')
_RESERVED_METRIC_LABEL_NAME_RE = re.compile(r'^__.*$')



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

  def unregister(self, metric):
    '''Remove a collector from the registry.'''
    with self._lock:
      self._collectors.remove(collector)

  def collect(self):
    """Yields metrics from the collectors in the registry."""
    collectors = None
    with self._lock:
      collectors = copy.copy(self._collectors)
    for collector in collectors:
      for metric in collector.collect():
        yield metric

  def get_sample_value(self, name, labels=None):
    """Returns the sample value, or None if not found.
    
    This is inefficient, and intended only for use in unittests.
    """
    if labels is None:
      labels = {}
    for metric in self.collect():
      for n, l, value in metric._samples:
        if n == name and l == labels:
          return value
    return None


REGISTRY = CollectorRegistry()
'''The default registry.'''

_METRIC_TYPES = ('counter', 'gauge', 'summary', 'untyped')

class Metric(object):
  '''A single metric and it's samples.'''
  def __init__(self, name, documentation, typ):
    self._name = name
    self._documentation = documentation
    if typ not in _METRIC_TYPES:
      raise ValueError("Invalid metric type: " + typ)
    self._type = typ
    self._samples = []

  '''Add a sample to the metric'''
  def add_sample(self, name, labels, value):
    self._samples.append((name, labels, value))


class _LabelWrapper(object):
  '''Handles labels for the wrapped metric.'''
  def __init__(self, wrappedClass, labelnames):
    self._wrappedClass = wrappedClass
    self._type = wrappedClass._type
    self._labelnames = labelnames
    self._lock = Lock()
    self._metrics = {}

    for l in labelnames:
      if l.startswith('__'):
        raise InvalidLabelName(l)

  def labels(self, *labelvalues):
    """Return the child for the given labelset."""
    if len(labelvalues) != len(self._labelnames):
      raise ValueError("Incorrect label count")
    labelvalues = tuple(labelvalues)
    with self._lock:
      if labelvalues not in self._metrics:
        self._metrics[labelvalues] = self._wrappedClass()
      return self._metrics[labelvalues]

  def remove(self, *labelvalues):
    """Remove the given labelset from the metric."""
    if len(labelvalues) != len(self._labelnames):
      raise ValueError("Incorrect label count")
    labelvalues = tuple(labelvalues)
    with self._lock:
      del self._metrics[labelvalues]

  def _samples(self):
    with self._lock:
      metrics = self._metrics.copy()
    for labels, metric in metrics.iteritems():
      for suffix, _, value in metric._samples():
        yield (suffix, dict(zip(self._labelnames, labels)), value)


def _MetricWrapper(cls):
  '''Provides common functionality for metrics.'''
  def init(name, documentation, labelnames=(), namespace='', subsystem='', registry=REGISTRY):
    if labelnames:
      for l in labelnames:
        if not _METRIC_LABEL_NAME_RE.match(l):
          raise ValueError("Invalid label metric name: " + l)
        if _RESERVED_METRIC_LABEL_NAME_RE.match(l):
          raise ValueError("Reserved label metric name: " + l)
      collector = _LabelWrapper(cls, labelnames)
    else:
      collector = cls()

    full_name = ''
    if namespace:
      full_name += namespace + '_'
    if subsystem:
      full_name += subsystem + '_'
    full_name += name

    if not _METRIC_NAME_RE.match(full_name):
      raise ValueError("Invalid metric name: " + full_name)

    def collect():
      metric = Metric(full_name, documentation, cls._type)
      for suffix, labels, value in collector._samples():
        metric.add_sample(full_name + suffix, labels, value)
      return [metric]
    collector.collect = collect

    registry.register(collector)
    return collector

  return init

@_MetricWrapper
class Counter(object):
  _type = 'counter'
  def __init__(self):
    self._value = 0.0
    self._lock = Lock()

  def inc(self, amount=1):
    """Increment counter by the given amount."""
    if amount < 0:
      raise ValueError("Counters can only be incremented by non-negative amounts.")
    with self._lock:
      self._value += amount

  def _samples(self):
    with self._lock:
      return (('', {}, self._value), )

@_MetricWrapper
class Gauge(object):
  _type = 'gauge'
  def __init__(self):
    self._value = 0.0
    self._lock = Lock()

  def inc(self, amount=1):
    """Increment gauge by the given amount."""
    with self._lock:
      self._value += amount

  def dec(self, amount=1):
    """Decrement gauge by the given amount."""
    with self._lock:
      self._value -= amount

  def set(self, value):
    """Set gauge to the given amount."""
    with self._lock:
      self._value = float(value)

  def _samples(self):
    with self._lock:
      return (('', {}, self._value), )

@_MetricWrapper
class Summary(object):
  _type = 'summary'
  def __init__(self):
    self._count = 0.0
    self._sum = 0.0
    self._lock = Lock()

  def observe(self, amount):
    """Observe the given amount."""
    with self._lock:
      self._count += 1
      self._sum += amount

  def _samples(self):
    with self._lock:
      return (
          ('_count', {}, self._count),
          ('_sum', {}, self._sum))


      
CONTENT_TYPE_004 = 'text-plain; version=0.0.4; charset=utf-8'
'''Content type of the text format v0.0.4'''

def generate004(registry=REGISTRY):
    '''Returns the metrics from the registry in text format v0.0.4 as a string.'''
    output = []
    for metric in registry.collect():
      output.append(u'# HELP %s %s' % (
        metric._name, metric._documentation.replace('\\', r'\\').replace('\n', r'\n')))
      output.append(u'\n# TYPE %s %s\n' % (metric._name, metric._type))
      for name, labels, value in metric._samples:
        if labels:
          labelstr = u'{%s}' % ','.join(
              [u'%s="%s"' % (
                  k, v.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"'))
               for k, v in labels.items()])
        else:
          labelstr = u''
        output.append(u'%s%s %s\n' % (name, labelstr, value))
    return ''.join(output).encode('utf-8')


class MetricsHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    self.send_response(200)
    self.send_header('Content-Type', CONTENT_TYPE_004)
    self.end_headers()
    self.wfile.write(generate004(REGISTRY))


if __name__ == '__main__':
  c = Counter('cc', 'A counter')
  c.inc()
 
  g = Gauge('gg', 'A gauge')
  g.set(17)
 
  s = Summary('ss', 'A summary', ['a', 'b'])
  s.labels('c', 'd').observe(17)
 
 
  from BaseHTTPServer import HTTPServer
  server_address = ('', 8000)
  httpd = HTTPServer(server_address, MetricsHandler)
  httpd.serve_forever()
