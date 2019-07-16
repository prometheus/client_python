import os
import shutil
import sys
import tempfile

from prometheus_client import values
from prometheus_client.core import Counter
from prometheus_client.values import MultiProcessValue, Pidprovider

if sys.version_info < (2, 7):
    # We need the skip decorators from unittest2 on Python 2.6.
    import unittest2 as unittest
else:
    import unittest


class TestPidprovider(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        os.environ['prometheus_multiproc_dir'] = self.tempdir
        self.originalValueClass = values.ValueClass
        self.originalPidproviderSource = Pidprovider.source
        values.ValueClass = MultiProcessValue()

    def tearDown(self):
        del os.environ['prometheus_multiproc_dir']
        shutil.rmtree(self.tempdir)
        values.ValueClass = self.originalValueClass
        Pidprovider.source = self.originalPidproviderSource

    # can not inspect the files cache directly, as it's a closure, so we
    # check for the actual files themselves
    def _files(self):
        fs = os.listdir(self.tempdir)
        fs.sort()
        return fs

    def test_with_default_pidprovider(self):
        Counter('c1', 'c1', registry=None)
        self.assertEqual(self._files(), ['counter_{}.db'.format(os.getpid())])

    def test_with_user_defined_pidprovider(self):
        Pidprovider.source = lambda: 1234
        Counter('c1', 'c1', registry=None)
        self.assertEqual(self._files(), ['counter_1234.db'.format(os.getpid())])
