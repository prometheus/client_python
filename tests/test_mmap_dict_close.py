import gc
import os
import tempfile
import unittest
import warnings

import prometheus_client.mmap_dict as mmap_dict
from prometheus_client.mmap_dict import MmapedDict


class TestMmapedDictClose(unittest.TestCase):
    def test_discarded_dict_does_not_warn_about_an_open_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "metrics.db")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ResourceWarning)
                store = MmapedDict(path)
                store.write_value("one", 1.0, 2.0)
                del store
                gc.collect()
        self.assertEqual(
            [w for w in caught if issubclass(w.category, ResourceWarning)],
            [],
        )

    def test_growth_keeps_written_values(self):
        mmap_dict._INITIAL_MMAP_SIZE = 128
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "metrics.db")
                store = MmapedDict(path)
                for i in range(40):
                    store.write_value("k" * 20 + str(i), float(i), 1.0)
                store.close()
                values = {
                    key: value
                    for key, value, _, _ in MmapedDict.read_all_values_from_file(path)
                }
        finally:
            mmap_dict._INITIAL_MMAP_SIZE = 1 << 16
        self.assertEqual(values["k" * 20 + "0"], 0.0)
        self.assertEqual(values["k" * 20 + "39"], 39.0)
        self.assertEqual(len(values), 40)


if __name__ == "__main__":
    unittest.main()
