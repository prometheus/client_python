import math

INF = float("inf")
MINUS_INF = float("-inf")


def floatToGoString(d):
    if d == INF:
        return '+Inf'
    elif d == MINUS_INF:
        return '-Inf'
    elif math.isnan(d):
        return 'NaN'
    else:
        return repr(float(d))
