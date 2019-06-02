from prometheus_client import Gauge,Counter,Histogram

def NewHistogram(metricsname, documentation, labelnames=(), labelvalues=(), bukets=Histogram.DEFAULT_BUCKETS):
    return Histogram(metricsname, documentation, labelnames=labelnames, labelvalues=labelvalues, buckets=bukets)

def NewCounter(metricsname, documentation, labelnames=(), labelvalues=()):
    return Counter(metricsname, documentation, labelnames=labelnames, labelvalues=labelvalues)

def NewGauge(metricsname, documentation, multiprocess_mode, labelnames=(), labelvalues=()):
    return Gauge(metricsname, documentation, labelnames=labelnames, labelvalues=labelvalues, multiprocess_mode=multiprocess_mode)

