import math
from threading import Lock, RLock

from .errors import PrometheusClientRuntimeError

INF = float("inf")
MINUS_INF = float("-inf")
NaN = float("NaN")


def floatToGoString(d):
    d = float(d)
    if d == INF:
        return '+Inf'
    elif d == MINUS_INF:
        return '-Inf'
    elif math.isnan(d):
        return 'NaN'
    else:
        s = repr(d)
        dot = s.find('.')
        # Go switches to exponents sooner than Python.
        # We only need to care about positive values for le/quantile.
        if d > 0 and dot > 6:
            mantissa = f'{s[0]}.{s[1:dot]}{s[dot + 1:]}'.rstrip('0.')
            return f'{mantissa}e+0{dot - 1}'
        return s


class WarnLock:
    """A wrapper around RLock and Lock that prevents deadlocks.

    Raises a RuntimeError when it detects attempts to re-enter the critical
    section from a single thread. Intended to be used as a context manager.
    """
    error_msg = (
        'Attempt to enter a non reentrant context from a single thread.'
        ' It is possible that the client code is trying to register or update'
        ' metrics from within metric registration code or from a signal handler'
        ' while metrics are being registered or updated.'
        ' This is unsafe and cannot be allowed. It would result in a deadlock'
        ' if this exception was not raised.'
    )

    def __init__(self):
        self._rlock = RLock()
        self._lock = Lock()

    def __enter__(self):
        self._rlock.acquire()
        if not self._lock.acquire(blocking=False):
            self._rlock.release()
            raise PrometheusClientRuntimeError(self.error_msg)

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.release()
        self._rlock.release()

    def _locked(self):
        # For use in tests.
        if self._rlock.acquire(blocking=False):
            self._rlock.release()
            return False
        return True
