from collections import namedtuple


class Timestamp(object):
    """A nanosecond-resolution timestamp."""

    def __init__(self, sec, nsec):
        if nsec < 0 or nsec >= 1e9:
            raise ValueError("Invalid value for nanoseconds in Timestamp: {0}".format(nsec))
        if sec < 0:
            nsec = -nsec
        self.sec = int(sec)
        self.nsec = int(nsec)

    def __str__(self):
        return "{0}.{1:09d}".format(self.sec, self.nsec)

    def __repr__(self):
        return "Timestamp({0}, {1})".format(self.sec, self.nsec)

    def __float__(self):
        return float(self.sec) + float(self.nsec) / 1e9

    def __eq__(self, other):
        return type(self) == type(other) and self.sec == other.sec and self.nsec == other.nsec

    def __ne__(self, other):
        return not self == other

    def __gt__(self, other):
        return self.sec > other.sec or self.nsec > other.nsec


# Timestamp and exemplar are optional.
# Value can be an int or a float.
# Timestamp can be a float containing a unixtime in seconds,
# a Timestamp object, or None.
# Exemplar can be an Exemplar object, or None.
sample = namedtuple('Sample', ['name', 'labels', 'value', 'timestamp', 'exemplar'])


# Wrap the namedtuple to provide eager type-checking that value is a float.
def Sample(name, labels, value, timestamp=None, exemplar=None):
    # Preserve ints, convert anything else to float.
    if type(value) != int:
        value = float(value)

    return sample(name, labels, value, timestamp, exemplar)


Exemplar = namedtuple('Exemplar', ['labels', 'value', 'timestamp'])
Exemplar.__new__.__defaults__ = (None,)
