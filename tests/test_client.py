import unittest

from prometheus_client import Gauge, Counter, Summary
from prometheus_client import CollectorRegistry, generate004

class TestCounter(unittest.TestCase):
  def setUp(self):
    self.registry = CollectorRegistry()
    self.counter = Counter('c', 'help', registry=self.registry)

  def test_increment(self):
    self.assertEquals(0, self.registry.get_sample_value('c'))
    self.counter.inc()
    self.assertEquals(1, self.registry.get_sample_value('c'))
    self.counter.inc(7)
    self.assertEquals(8, self.registry.get_sample_value('c'))
 
  def test_negative_increment_raises(self):
    self.assertRaises(ValueError, self.counter.inc, -1)

  def test_function_decorator(self):
    @self.counter.countFunctionExceptions
    def f(r):
      if r:
        raise Exception
    f(False)
    self.assertEquals(0, self.registry.get_sample_value('c'))
    raised = False
    try:
      f(True)
    except:
      raised = True
    self.assertTrue(raised)
    self.assertEquals(1, self.registry.get_sample_value('c'))

  def test_block_decorator(self):
    with self.counter.countBlockExceptions():
      pass
    self.assertEquals(0, self.registry.get_sample_value('c'))
    raised = False
    try:
      with self.counter.countBlockExceptions():
        raise Exception
    except:
      raised = True
    self.assertTrue(raised)
    self.assertEquals(1, self.registry.get_sample_value('c'))

class TestGauge(unittest.TestCase):
  def setUp(self):
    self.registry = CollectorRegistry()
    self.gauge = Gauge('g', 'help', registry=self.registry)

  def test_gauge(self):
    self.assertEquals(0, self.registry.get_sample_value('g'))
    self.gauge.inc()
    self.assertEquals(1, self.registry.get_sample_value('g'))
    self.gauge.dec(3)
    self.assertEquals(-2, self.registry.get_sample_value('g'))
    self.gauge.set(9)
    self.assertEquals(9, self.registry.get_sample_value('g'))

  def test_function_decorator(self):
    self.assertEquals(0, self.registry.get_sample_value('g'))
    @self.gauge.trackFunctionInprogress
    def f():
      self.assertEquals(1, self.registry.get_sample_value('g'))
    f()
    self.assertEquals(0, self.registry.get_sample_value('g'))

  def test_block_decorator(self):
    self.assertEquals(0, self.registry.get_sample_value('g'))
    with self.gauge.trackBlockInprogress():
      self.assertEquals(1, self.registry.get_sample_value('g'))
    self.assertEquals(0, self.registry.get_sample_value('g'))

class TestSummary(unittest.TestCase):
  def setUp(self):
    self.registry = CollectorRegistry()
    self.summary = Summary('s', 'help', registry=self.registry)

  def test_summary(self):
    self.assertEquals(0, self.registry.get_sample_value('s_count'))
    self.assertEquals(0, self.registry.get_sample_value('s_sum'))
    self.summary.observe(10)
    self.assertEquals(1, self.registry.get_sample_value('s_count'))
    self.assertEquals(10, self.registry.get_sample_value('s_sum'))

  def test_function_decorator(self):
    self.assertEquals(0, self.registry.get_sample_value('s_count'))
    @self.summary.timeFunction
    def f():
      pass
    f()
    self.assertEquals(1, self.registry.get_sample_value('s_count'))

  def test_block_decorator(self):
    self.assertEquals(0, self.registry.get_sample_value('s_count'))
    with self.summary.timeBlock():
      pass
    self.assertEquals(1, self.registry.get_sample_value('s_count'))

class TestMetricWrapper(unittest.TestCase):
  def setUp(self):
    self.registry = CollectorRegistry()
    self.counter = Counter('c', 'help', labelnames=['l'], registry=self.registry)
    self.two_labels = Counter('two', 'help', labelnames=['a', 'b'], registry=self.registry)

  def test_child(self):
    self.counter.labels('x').inc()
    self.assertEquals(1, self.registry.get_sample_value('c', {'l': 'x'}))
    self.two_labels.labels('x', 'y').inc(2)
    self.assertEquals(2, self.registry.get_sample_value('two', {'a': 'x', 'b': 'y'}))

  def test_remove(self):
    self.counter.labels('x').inc()
    self.counter.labels('y').inc(2)
    self.assertEquals(1, self.registry.get_sample_value('c', {'l': 'x'}))
    self.assertEquals(2, self.registry.get_sample_value('c', {'l': 'y'}))
    self.counter.remove('x')
    self.assertEquals(None, self.registry.get_sample_value('c', {'l': 'x'}))
    self.assertEquals(2, self.registry.get_sample_value('c', {'l': 'y'}))

  def test_incorrect_label_count_raises(self):
    self.assertRaises(ValueError, self.counter.labels)
    self.assertRaises(ValueError, self.counter.labels, 'a', 'b')
    self.assertRaises(ValueError, self.counter.remove)
    self.assertRaises(ValueError, self.counter.remove, 'a', 'b')

  def test_namespace_subsystem_concatenated(self):
    c = Counter('c', 'help', namespace='a', subsystem='b', registry=self.registry)
    c.inc()
    self.assertEquals(1, self.registry.get_sample_value('a_b_c'))

  def test_invalid_names_raise(self):
    self.assertRaises(ValueError, Counter, '', 'help')
    self.assertRaises(ValueError, Counter, '^', 'help')
    self.assertRaises(ValueError, Counter, '', 'help', namespace='&')
    self.assertRaises(ValueError, Counter, '', 'help', subsystem='(')
    self.assertRaises(ValueError, Counter, 'c', '', labelnames=['^'])
    self.assertRaises(ValueError, Counter, 'c', '', labelnames=['__reserved'])

class TestGenerateText(unittest.TestCase):
  def setUp(self):
    self.registry = CollectorRegistry()

  def test_counter(self):
    c = Counter('cc', 'A counter', registry=self.registry)
    c.inc()
    self.assertEquals('# HELP cc A counter\n# TYPE cc counter\ncc 1.0\n', generate004(self.registry))

  def test_gauge(self):
    g = Gauge('gg', 'A gauge', registry=self.registry)
    g.set(17)
    self.assertEquals('# HELP gg A gauge\n# TYPE gg gauge\ngg 17.0\n', generate004(self.registry))

  def test_summary(self):
    s = Summary('ss', 'A summary', ['a', 'b'], registry=self.registry)
    s.labels('c', 'd').observe(17)
    self.assertEquals('# HELP ss A summary\n# TYPE ss summary\nss_count{a="c",b="d"} 1.0\nss_sum{a="c",b="d"} 17.0\n', generate004(self.registry))

  def test_escaping(self):
    c = Counter('cc', 'A\ncount\\er', ['a'], registry=self.registry)
    c.labels('\\x\n').inc(1)
    self.assertEquals('# HELP cc A\\ncount\\\\er\n# TYPE cc counter\ncc{a="\\\\x\\n"} 1.0\n', generate004(self.registry))


if __name__ == '__main__':
   unittest.main()
