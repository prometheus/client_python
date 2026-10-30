import unittest

from prometheus_client import samples


class TestSamples(unittest.TestCase):
    def test_negative_timestamp_string(self):
        for nsec, expected in [
            (0, '-123.000000000'),
            (1, '-123.000000001'),
            (456000000, '-123.456000000'),
            (999999999, '-123.999999999'),
        ]:
            with self.subTest(nsec=nsec):
                timestamp = samples.Timestamp(-123, nsec)
                self.assertEqual(str(timestamp), expected)
                self.assertEqual(float(str(timestamp)), float(timestamp))

    def test_negative_timestamp_string_with_zero_seconds(self):
        timestamp = samples.Timestamp(-0.5, 500000000)
        self.assertEqual(str(timestamp), '-0.500000000')
        self.assertEqual(float(str(timestamp)), float(timestamp))

    def test_gt(self):
        self.assertEqual(samples.Timestamp(1, 1) > samples.Timestamp(1, 1), False)
        self.assertEqual(samples.Timestamp(1, 1) > samples.Timestamp(1, 2), False)
        self.assertEqual(samples.Timestamp(1, 1) > samples.Timestamp(2, 1), False)
        self.assertEqual(samples.Timestamp(1, 1) > samples.Timestamp(2, 2), False)
        self.assertEqual(samples.Timestamp(1, 2) > samples.Timestamp(1, 1), True)
        self.assertEqual(samples.Timestamp(2, 1) > samples.Timestamp(1, 1), True)
        self.assertEqual(samples.Timestamp(2, 2) > samples.Timestamp(1, 1), True)
        self.assertEqual(samples.Timestamp(0, 2) > samples.Timestamp(1, 1), False)
        self.assertEqual(samples.Timestamp(2, 0) > samples.Timestamp(1, 1), True)

    def test_lt(self):
        self.assertEqual(samples.Timestamp(1, 1) < samples.Timestamp(1, 1), False)
        self.assertEqual(samples.Timestamp(1, 1) < samples.Timestamp(1, 2), True)
        self.assertEqual(samples.Timestamp(1, 1) < samples.Timestamp(2, 1), True)
        self.assertEqual(samples.Timestamp(1, 1) < samples.Timestamp(2, 2), True)
        self.assertEqual(samples.Timestamp(1, 2) < samples.Timestamp(1, 1), False)
        self.assertEqual(samples.Timestamp(2, 1) < samples.Timestamp(1, 1), False)
        self.assertEqual(samples.Timestamp(2, 2) < samples.Timestamp(1, 1), False)
        self.assertEqual(samples.Timestamp(0, 2) < samples.Timestamp(1, 1), True)
        self.assertEqual(samples.Timestamp(2, 0) < samples.Timestamp(1, 1), False)


if __name__ == '__main__':
    unittest.main()
