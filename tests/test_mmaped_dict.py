import os
import tempfile
import unittest

from prometheus_client.mmap_dict import _MmapedDict, _INITIAL_MMAP_SIZE


class TestMmapedDict(unittest.TestCase):
    def setUp(self):
        fd, self.tempfile = tempfile.mkstemp()
        os.close(fd)
        self.d = _MmapedDict(self.tempfile)

    def test_process_restart(self):
        self.d.write_value('abc', 123.0)
        self.d.close()
        self.d = _MmapedDict(self.tempfile)
        self.assertEqual(123, self.d.read_value('abc'))
        self.assertEqual([('abc', 123.0)], list(self.d.read_all_values()))

    def test_expansion(self):
        key = 'a' * _INITIAL_MMAP_SIZE
        self.d.write_value(key, 123.0)
        self.assertEqual([(key, 123.0)], list(self.d.read_all_values()))

    def test_multi_expansion(self):
        key = 'a' * _INITIAL_MMAP_SIZE * 4
        self.d.write_value('abc', 42.0)
        self.d.write_value(key, 123.0)
        self.d.write_value('def', 17.0)
        self.assertEqual(
            [('abc', 42.0), (key, 123.0), ('def', 17.0)],
            list(self.d.read_all_values()))

    def tearDown(self):
        os.unlink(self.tempfile)
