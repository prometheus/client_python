import unittest

from prometheus_client.utils import floatToGoString


class TestFloatToGoString(unittest.TestCase):
    def test_exponent_two_digits_has_no_leading_zero(self):
        # floatToGoString mirrors Go's strconv.FormatFloat(f, 'g', -1, 64),
        # which pads the exponent to a minimum of two digits. A two-digit
        # exponent must not gain a spurious leading zero.
        self.assertEqual('1e+10', floatToGoString(1e10))
        self.assertEqual('1e+15', floatToGoString(1e15))
        self.assertEqual('1.234567890123e+12', floatToGoString(1234567890123.0))

    def test_exponent_one_digit_is_zero_padded(self):
        # Single-digit exponents keep the two-digit zero padding.
        self.assertEqual('1e+06', floatToGoString(1e6))
        self.assertEqual('1.234567e+06', floatToGoString(1234567.0))
