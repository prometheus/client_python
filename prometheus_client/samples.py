from typing import Dict, NamedTuple, Optional


class Timestamp:
    """A nanosecond-resolution timestamp."""

    def __init__(self, sec, nsec):
        if nsec < 0 or nsec >= 1e9:
            raise ValueError(f"Invalid value for nanoseconds in Timestamp: {nsec}")
        if sec < 0:
            nsec = -nsec
        self.sec = int(sec)
        self.nsec = int(nsec)

    def __str__(self):
        return f"{self.sec}.{self.nsec:09d}"

    def __repr__(self):
        return f"Timestamp({self.sec}, {self.nsec})"

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
class Exemplar(NamedTuple):
    labels: Dict[str, str]
    value: float
    timestamp: Optional[float] = None


class Sample(NamedTuple):
    name: str
    labels: Dict[str, str]
    value: float
    timestamp: Optional[float] = None
    exemplar: Optional[Exemplar] = None
