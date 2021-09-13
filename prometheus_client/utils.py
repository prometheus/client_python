import math
import sys

import psutil

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
            mantissa = '{0}.{1}{2}'.format(s[0], s[1:dot], s[dot + 1:]).rstrip('0.')
            return '{0}e+0{1}'.format(mantissa, dot - 1)
        return s

def get_process_data(pid):
    try:
        process = psutil.Process(pid)
        return process.__hash__()
    except psutil.NoSuchProcess:
        print('Calling process {0} is not running'.format(pid), file=sys.stderr)
        raise
    except psutil.AccessDenied:
        print('Not enough permissions to access process {0}'.format(pid), file=sys.stderr)
        raise


