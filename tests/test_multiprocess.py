import os
import tempfile
import unittest

from prometheus_client.multiprocess import MultiProcessCollector

from prometheus_client.registry import CollectorRegistry


class TestUnsetEnv(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        fp, self.tmpfl = tempfile.mkstemp()
        os.close(fp)

    def test_unset_syncdir_env(self):
        self.assertRaises(
            ValueError, MultiProcessCollector, self.registry)

    def test_file_syncpath(self):
        registry = CollectorRegistry()
        self.assertRaises(
            ValueError, MultiProcessCollector, registry, self.tmpfl)

    def tearDown(self):
        os.remove(self.tmpfl)
