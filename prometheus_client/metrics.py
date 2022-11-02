import os
from threading import Lock
import time
import types
from typing import (
    Any, Callable, Dict, Iterable, List, Optional, Sequence, Type, TypeVar,
    Union,
)

from . import values  # retain this import style for testability
from .context_managers import ExceptionCounter, InprogressTracker, Timer
from .metrics_core import (
    Metric, METRIC_LABEL_NAME_RE, METRIC_NAME_RE,
    RESERVED_METRIC_LABEL_NAME_RE,
)
from .registry import Collector, CollectorRegistry, REGISTRY
from .samples import Exemplar, Sample
from .utils import append_docstring, floatToGoString, INF

T = TypeVar('T', bound='MetricWrapperBase')
F = TypeVar("F", bound=Callable[..., Any])


def _build_full_name(metric_type, name, namespace, subsystem, unit):
    full_name = ''
    if namespace:
        full_name += namespace + '_'
    if subsystem:
        full_name += subsystem + '_'
    full_name += name
    if metric_type == 'counter' and full_name.endswith('_total'):
        full_name = full_name[:-6]  # Munge to OpenMetrics.
    if unit and not full_name.endswith("_" + unit):
        full_name += "_" + unit
    if unit and metric_type in ('info', 'stateset'):
        raise ValueError('Metric name is of a type that cannot have a unit: ' + full_name)
    return full_name


def _validate_labelname(l):
    if not METRIC_LABEL_NAME_RE.match(l):
        raise ValueError('Invalid label metric name: ' + l)
    if RESERVED_METRIC_LABEL_NAME_RE.match(l):
        raise ValueError('Reserved label metric name: ' + l)


def _validate_labelnames(cls, labelnames):
    labelnames = tuple(labelnames)
    for l in labelnames:
        _validate_labelname(l)
        if l in cls._reserved_labelnames:
            raise ValueError('Reserved label metric name: ' + l)
    return labelnames


def _validate_exemplar(exemplar):
    runes = 0
    for k, v in exemplar.items():
        _validate_labelname(k)
        runes += len(k)
        runes += len(v)
    if runes > 128:
        raise ValueError('Exemplar labels have %d UTF-8 characters, exceeding the limit of 128')


def _get_use_created() -> bool:
    return os.environ.get("PROMETHEUS_DISABLE_CREATED_SERIES", 'False').lower() not in ('true', '1', 't')


_use_created = _get_use_created()


class MetricWrapperBase(Collector):
    """
    ``MetricWrapperBase`` is the base class for all metric types.
    ``MetricWrapperBase`` is not meant to be instantiated directly.

    Each metric types inherits from ``MetricWrapperBase`` must implement
    ``_metric_init`` and ``_child_samples`` methods.

    Args:
        name: The name of the metric.
        documentation: A documentation string.
        labelnames: A tuple of strings specifying the label names
                    for the metric. Defaults to ``()``.
        namespace: The namespace of the metric. Defaults to an empty string.
        subsystem: The subsystem of the metric. Defaults to an empty string.
        unit: The unit of the metric. Defaults to an empty string.
        registry: The registry to register the metric to. Defaults to ``REGISTRY``.
    """  # noqa: LN001
    _type: Optional[str] = None
    _reserved_labelnames: Sequence[str] = ()

    def _is_observable(self):
        # Whether this metric is observable, i.e.
        # * a metric without label names and values, or
        # * the child of a labelled metric.
        return not self._labelnames or (self._labelnames and self._labelvalues)

    def _raise_if_not_observable(self):
        # Functions that mutate the state of the metric, for example incrementing
        # a counter, will fail if the metric is not observable, because only if a
        # metric is observable will the value be initialized.
        if not self._is_observable():
            raise ValueError('%s metric is missing label values' % str(self._type))

    def _is_parent(self):
        return self._labelnames and not self._labelvalues

    def _get_metric(self):
        return Metric(self._name, self._documentation, self._type, self._unit)

    def describe(self) -> Iterable[Metric]:
        return [self._get_metric()]

    def collect(self) -> Iterable[Metric]:
        metric = self._get_metric()
        for suffix, labels, value, timestamp, exemplar in self._samples():
            metric.add_sample(self._name + suffix, labels, value, timestamp, exemplar)
        return [metric]

    def __str__(self) -> str:
        return f"{self._type}:{self._name}"

    def __repr__(self) -> str:
        metric_type = type(self)
        return f"{metric_type.__module__}.{metric_type.__name__}({self._name})"

    def __init__(self: T,
                 name: str,
                 documentation: str,
                 labelnames: Iterable[str] = (),
                 namespace: str = '',
                 subsystem: str = '',
                 unit: str = '',
                 registry: Optional[CollectorRegistry] = REGISTRY,
                 _labelvalues: Optional[Sequence[str]] = None,
                 ) -> None:
        self._name = _build_full_name(self._type, name, namespace, subsystem, unit)
        self._labelnames = _validate_labelnames(self, labelnames)
        self._labelvalues = tuple(_labelvalues or ())
        self._kwargs: Dict[str, Any] = {}
        self._documentation = documentation
        self._unit = unit

        if not METRIC_NAME_RE.match(self._name):
            raise ValueError('Invalid metric name: ' + self._name)

        if self._is_parent():
            # Prepare the fields needed for child metrics.
            self._lock = Lock()
            self._metrics: Dict[Sequence[str], T] = {}

        if self._is_observable():
            self._metric_init()

        if not self._labelvalues:
            # Register the multi-wrapper parent metric, or if a label-less metric, the whole shebang.
            if registry:
                registry.register(self)

    def labels(self: T, *labelvalues: Any, **labelkwargs: Any) -> T:
        """
        All metrics can have labels, allowing grouping of related time series.

        For example:

        .. code-block:: python

            from prometheus_client import Counter

            c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
            c.labels('get', '/').inc()
            c.labels('post', '/submit').inc()

        Labels can also be provided as keyword arguments:

        .. code-block:: python

            from prometheus_client import Counter

            c = Counter('my_requests_total', 'HTTP Failures', ['method', 'endpoint'])
            c.labels(method='get', endpoint='/').inc()
            c.labels(method='post', endpoint='/submit').inc()

        See the best practices on `naming <http://prometheus.io/docs/practices/naming/>`_
        and `labels <http://prometheus.io/docs/practices/instrumentation/#use-labels>`_.

        .. note::

            Either ``*labelvalues`` or ``**labelkwargs`` must be provided, but not both.

        Args:
            *labelvalues: The label values as args to use for the child.
            **labelkwargs: The label values as kwargs to use for the child.

        Returns:
            The child metric for given labelset.

        Raises:
            ValueError: The following scenarios will raise ``ValueError``:

                        * If the child does not have a label names.
                        * If the child's label values are already set.
                        * If both ``*labelvalues`` and ``**labelkwargs`` are provided.
                        * If ``**labelkwargs`` contains an invalid keyname
                        * If ``*labelvalues`` has incorrect number of values
        """  # noqa: LN001
        if not self._labelnames:
            raise ValueError('No label names were set when constructing %s' % self)

        if self._labelvalues:
            raise ValueError('{} already has labels set ({}); can not chain calls to .labels()'.format(
                self,
                dict(zip(self._labelnames, self._labelvalues))
            ))

        if labelvalues and labelkwargs:
            raise ValueError("Can't pass both *args and **kwargs")

        if labelkwargs:
            if sorted(labelkwargs) != sorted(self._labelnames):
                raise ValueError('Incorrect label names')
            labelvalues = tuple(str(labelkwargs[l]) for l in self._labelnames)
        else:
            if len(labelvalues) != len(self._labelnames):
                raise ValueError('Incorrect label count')
            labelvalues = tuple(str(l) for l in labelvalues)
        with self._lock:
            if labelvalues not in self._metrics:
                self._metrics[labelvalues] = self.__class__(
                    self._name,
                    documentation=self._documentation,
                    labelnames=self._labelnames,
                    unit=self._unit,
                    _labelvalues=labelvalues,
                    **self._kwargs
                )
            return self._metrics[labelvalues]

    def remove(self, *labelvalues: Any) -> None:
        """
        Remove the given labelset from the metric.

        Args:
            *labelvalues: The label values to remove.

        Raises:
            ValueError: The following scenarios will raise ``ValueError``:

                        * If no label names were set.
                        * If the number of ``*labelvalues`` does not match the number of label names.
        """  # noqa: LN001
        if not self._labelnames:
            raise ValueError('No label names were set when constructing %s' % self)

        if len(labelvalues) != len(self._labelnames):
            raise ValueError('Incorrect label count (expected %d, got %s)' % (len(self._labelnames), labelvalues))
        labelvalues = tuple(str(l) for l in labelvalues)
        with self._lock:
            del self._metrics[labelvalues]

    def clear(self) -> None:
        """Remove all labelsets from the metric"""
        with self._lock:
            self._metrics = {}

    def _samples(self) -> Iterable[Sample]:
        if self._is_parent():
            return self._multi_samples()
        else:
            return self._child_samples()

    def _multi_samples(self) -> Iterable[Sample]:
        with self._lock:
            metrics = self._metrics.copy()
        for labels, metric in metrics.items():
            series_labels = list(zip(self._labelnames, labels))
            for suffix, sample_labels, value, timestamp, exemplar in metric._samples():
                yield Sample(suffix, dict(series_labels + list(sample_labels.items())), value, timestamp, exemplar)

    def _child_samples(self) -> Iterable[Sample]:  # pragma: no cover
        # NOTE: For all metrics implementation, this method must be implemented.
        #       to return an iterable of Sample objects.
        raise NotImplementedError('_child_samples() must be implemented by %r' % self)

    def _metric_init(self):  # pragma: no cover
        """
        Initialize the metric object as a child, i.e. when it has labels (if any) set.

        This is factored as a separate function to allow for deferred initialization.
        """
        raise NotImplementedError('_metric_init() must be implemented by %r' % self)


METRICS_WRAPPER_DOCS = """\
    :class:`prometheus_client.%s` inherits from :class:`prometheus_client.MetricWrapperBase`.
    Refer to the documentation of :class:`prometheus_client.MetricWrapperBase` for more details
    on initialization parameters.
"""


@append_docstring(METRICS_WRAPPER_DOCS % 'Counter')
class Counter(MetricWrapperBase):
    """
    A Counter tracks counts of events or running totals.

    .. epigraph::

        It is a cumulative metric that represents a single
        `monotonically increasing counter <https://prometheus.io/docs/concepts/metric_types/#counter>`_
        whose value can only increase or be reset to zero on restart.

    Some notable examples include:

    * Number of requests processed
    * Number of items that were inserted into a queue
    * Total amount of data that a system has processed

    If you need to go down, uses :class:`prometheus_client.Gauge` instead.

    A quick example of a Counter:

    .. code-block:: python

        from prometheus_client import Counter

        c = Counter('my_failures_total', 'Description of counter')
        c.inc()
    """  # noqa: LN001
    _type = 'counter'

    def _metric_init(self) -> None:
        self._value = values.ValueClass(self._type, self._name, self._name + '_total', self._labelnames,
                                        self._labelvalues)
        self._created = time.time()

    def inc(self, amount: float = 1, exemplar: Optional[Dict[str, str]] = None) -> None:
        """
        Increment any given counter by the given amount.

        Args:
            amount: The amount to increment the counter by. Defaults to ``1``.
            exemplar: An optional dictionary of string key-value pairs to
                      attach to the metric as an exemplar. The definition can be
                      found `here <https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md#exemplars>`_.

        Examples:

        .. tab-set::

            .. tab-item:: Simple use case

                .. code-block:: python

                    from prometheus_client import Counter
                    c = Counter('failures', 'Total number of failures requests')
                    c.inc()

            .. tab-item:: Custom amount

                .. code-block:: python

                    from prometheus_client import Counter
                    c = Counter('failures', 'Total number of failures requests')
                    c.inc(1.6)

            .. tab-item:: Exemplar

                .. code-block:: python

                    from prometheus_client import Counter
                    c = Counter('failures', 'Total number of failures requests')
                    c.inc(1.6, exemplar={"trace_id":"oHg5SJYRHA0"})

        Raises:
            ValueError: The following scenarios will raise ``ValueError``:

                        * If given metrics are not observable
                        * If the given amount is negative.
                        * If given exemplar labels are invalid.
        """
        self._raise_if_not_observable()
        if amount < 0:
            raise ValueError('Counters can only be incremented by non-negative amounts.')
        self._value.inc(amount)
        if exemplar:
            _validate_exemplar(exemplar)
            self._value.set_exemplar(Exemplar(exemplar, amount, time.time()))

    def count_exceptions(self, exception: Type[BaseException] = Exception) -> ExceptionCounter:
        """
        Count exceptions in a block of code or function.

        ``count_exceptions()`` can be used as both a decorator and context manager to count exceptions raised.

        .. tab-set::

            .. tab-item:: Decorator

                .. code-block:: python

                    from __future__ import annotations

                    from prometheus_client import Counter

                    c = Counter('failures', 'Total number of failures requests')
                    @c.count_exceptions()
                    def foo(input_data: dict[str, str]):
                        ...

            .. tab-item:: Context Manager

                .. code-block:: python

                    from __future__ import annotations

                    from prometheus_client import Counter

                    c = Counter('failures', 'Total number of failures requests')

                    def foo(input_data: dict[str, str]):
                        with c.count_exceptions():
                            ...

        ``count_exceptions()`` will optionally take in an exception to only track specific exceptions.

        .. code-block:: python

            ...
            with c.count_exceptions(RuntimeError):
                if input_data['output'] is None:
                    raise RuntimeError("Given pre-processing logic is invalid")

        Args:
            exception: The exception to track. Defaults to ``Exception``.

        Returns:
            An :class:`ExceptionCounter` object.

        Raises:
            ValueError: If given metrics are not observable.
        """
        self._raise_if_not_observable()
        return ExceptionCounter(self, exception)

    def _child_samples(self) -> Iterable[Sample]:
        sample = Sample('_total', {}, self._value.get(), None, self._value.get_exemplar())
        if _use_created:
            return (
                sample,
                Sample('_created', {}, self._created, None, None)
            )
        return (sample,)


@append_docstring(METRICS_WRAPPER_DOCS % 'Gauge')
class Gauge(MetricWrapperBase):
    """
    Gauge represents a single numerical value that can arbitrarily go up and down.

    Gauges are typically used to for report instantaneous values.
    One can think of Gauge as a :class:`prometheus_client.Counter` that can go up and down.

    Some notable examples include:

    * Inprogress requests
    * Number of items in a queue
    * Free memory
    * Total memory
    * Temperature

    A quick example of a Gauge:

    .. code-block:: python

        from prometheus_client import Gauge

        g = Gauge('my_inprogress_requests', 'Description of gauge')
        g.inc()      # Increment by 1
        g.dec(10)    # Decrement by given value
        g.set(4.2)   # Set to a given value

    In addition to all :class:`prometheus_client.MetricWrapperBase`
    init arguments, ``Gauge`` also accepts a ``multiprocess_mode`` argument.
    By default, ``multiprocess_mode`` is set to ``all``.

    ``multiprocess_mode`` accepts the following values:

    * ``'all'``: Default. Return a timeseries per process (alive or dead),
                 labelled by the process's `pid` (the label is added internally).
    * ``'min'``: Return a single timeseries that is the minimum of the values
                 of all processes (alive or dead).
    * ``'max'``: Return a single timeseries that is the maximum of the values
                 of all processes (alive or dead).
    * ``'sum'``: Return a single timeseries that is the sum of the values of
                 all processes (alive or dead).

    Prepend 'live' to the beginning of the mode to return the same result
    but only considering living processes
    (e.g., ``'liveall'``, ``'livesum'``, ``'livemax'``, ``'livemin'``).

    Raises:
        ValueError: If given ``multiprocess_mode`` is invalid.
    """  # noqa: LN001
    _type = 'gauge'
    _MULTIPROC_MODES = frozenset(('all', 'liveall', 'min', 'livemin', 'max', 'livemax', 'sum', 'livesum'))

    def __init__(self,
                 name: str,
                 documentation: str,
                 labelnames: Iterable[str] = (),
                 namespace: str = '',
                 subsystem: str = '',
                 unit: str = '',
                 registry: Optional[CollectorRegistry] = REGISTRY,
                 _labelvalues: Optional[Sequence[str]] = None,
                 multiprocess_mode: str = 'all',
                 ):
        self._multiprocess_mode = multiprocess_mode
        if multiprocess_mode not in self._MULTIPROC_MODES:
            raise ValueError('Invalid multiprocess mode: ' + multiprocess_mode)
        super().__init__(
            name=name,
            documentation=documentation,
            labelnames=labelnames,
            namespace=namespace,
            subsystem=subsystem,
            unit=unit,
            registry=registry,
            _labelvalues=_labelvalues,
        )
        self._kwargs['multiprocess_mode'] = self._multiprocess_mode

    def _metric_init(self) -> None:
        self._value = values.ValueClass(
            self._type, self._name, self._name, self._labelnames, self._labelvalues,
            multiprocess_mode=self._multiprocess_mode
        )

    def inc(self, amount: float = 1) -> None:
        """
        Increment gauge by the given amount.

        Args:
            amount: The amount to increment the gauge by. Defaults to 1.

        Raises:
            ValueError: If given metrics are not observable.
        """  # noqa: LN001
        self._raise_if_not_observable()
        self._value.inc(amount)

    def dec(self, amount: float = 1) -> None:
        """
        Decrement gauge by the given amount.

        Args:
            amount: The amount to decrement the gauge by. Defaults to 1.

        Raises:
            ValueError: If given metrics are not observable.
        """  # noqa: LN001
        self._raise_if_not_observable()
        self._value.inc(-amount)

    def set(self, value: float) -> None:
        """
        Set gauge to the given value.

        Args:
            value: The value to set the gauge to.

        Raises:
            ValueError: If given metrics are not observable.
        """  # noqa: LN001
        self._raise_if_not_observable()
        self._value.set(float(value))

    def set_to_current_time(self) -> None:
        """Set gauge to the current unixtime."""
        self.set(time.time())

    def track_inprogress(self) -> InprogressTracker:
        """
        Track inprogress blocks of code or functions.

        Can be used as a function decorator or context manager.
        Increments the gauge when the code is entered,
        and decrements when it is exited.

        .. tab-set::

           .. tab-item:: Example

              .. code-block:: python

                  from __future__ import annotations

                  from prometheus_client import Gauge

                  g = Gauge('inprogress_request', 'Request inprogress')

                  @g.track_inprogress()
                  def foo(input_data: dict[str, str]):
                      ...

           .. tab-item:: Context Manager

              .. code-block:: python

                  from __future__ import annotations

                  from prometheus_client import Gauge

                  g = Gauge('inprogress_request', 'Request inprogress')

                  def foo(input_data: dict[str, str]):
                      with g.track_inprogress():
                          ...

        Raises:
            ValueError: If given metrics are not observable.
        """  # noqa: LN001
        self._raise_if_not_observable()
        return InprogressTracker(self)

    def time(self) -> Timer:
        """
        Time a block of code or function, and set the duration in seconds.

        Can be used as a function decorator or context manager.

        .. tab-set::

           .. tab-item:: Example

              .. code-block:: python

                  from __future__ import annotations

                  from prometheus_client import Gauge

                  g = Gauge('inprogress_request', 'Request inprogress')

                  @g.time()
                  def foo(input_data: dict[str, str]):
                      ...

           .. tab-item:: Context Manager

              .. code-block:: python

                  from __future__ import annotations

                  from prometheus_client import Gauge

                  g = Gauge('inprogress_request', 'Request inprogress')

                  def foo(input_data: dict[str, str]):
                      with g.time():
                          ...

        Returns:
            A :class:`prometheus_client.context_managers.Timer` instance.
        """  # noqa: LN001
        return Timer(self, 'set')

    def set_function(self, f: Callable[[], float]) -> None:
        """Call the provided function to return the Gauge value.

        The callback must return a float, and may be called from
        multiple threads.

        .. note::
            All other methods of the Gauge become NOOPs if a given callback
            is set.

        Example:

        .. code-block:: python

            from prometheus_client import Gauge

            d = Gauge('data_objects', 'Number of objects')
            my_dict = {}
            d.set_function(lambda: len(my_dict))

        Args:
            f: A callable that takes no arguments and returns a float.

        Raises:
            ValueError: If given metrics are not observable.
        """

        self._raise_if_not_observable()

        def samples(_: Gauge) -> Iterable[Sample]:
            return (Sample('', {}, float(f()), None, None),)

        self._child_samples = types.MethodType(samples, self)  # type: ignore

    def _child_samples(self) -> Iterable[Sample]:
        return (Sample('', {}, self._value.get(), None, None),)


@append_docstring(METRICS_WRAPPER_DOCS % 'Summary')
class Summary(MetricWrapperBase):
    """
    A Summary tracks the size and number of events.

    While it also provides a total count of observations and a sum of all observed values,
    it calculates configurable quantiles over a sliding time window.

    Notable examples include request latency and response size.

    * Response latency
    * Request size

    A quick example of a Summary:

    .. code-block:: python

        from __future__ import annotations

        from prometheus_client import Summary

        s = Summary('request_size_bytes', 'Request size (bytes)')

        def foo(input_data: dict[str, str]):
            s.observe(512)  # Observe 512 (bytes)
            ...
    """
    _type = 'summary'
    _reserved_labelnames = ['quantile']

    def _metric_init(self) -> None:
        self._count = values.ValueClass(self._type, self._name, self._name + '_count', self._labelnames,
                                        self._labelvalues)
        self._sum = values.ValueClass(self._type, self._name, self._name + '_sum', self._labelnames, self._labelvalues)
        self._created = time.time()

    def observe(self, amount: float) -> None:
        """
        Observe the given amount.

        The amount is usually positive or zero. Negative values are
        accepted but prevent current versions of Prometheus from
        properly detecting counter resets in the sum of
        observations. See
        https://prometheus.io/docs/practices/histograms/#count-and-sum-of-observations
        for details.

        .. code-block:: python

            from prometheus_client import Summary

            request_size = Summary('request_size_bytes', 'Request size (bytes)')
            request_size.observe(512)  # Observe 512 (bytes)

        Args:
            amount: The amount to observe.

        Raises:
            ValueError: If given metrics are not observable.
        """
        self._raise_if_not_observable()
        self._count.inc(1)
        self._sum.inc(amount)

    def time(self) -> Timer:
        """
        Time a block of code or function, and observe the duration in seconds.

        Can be used as a function decorator or context manager.

        .. tab-set::

            .. tab-item:: Example

                .. code-block:: python

                    from prometheus_client import Summary

                    REQUEST_TIME = Summary('response_latency_seconds', 'Response latency (seconds)')

                    @REQUEST_TIME.time()
                    def foo(request):
                        ...

            .. tab-item:: Context Manager

                .. code-block:: python

                    from prometheus_client import Summary

                    REQUEST_TIME = Summary('response_latency_seconds', 'Response latency (seconds)')

                    def create_response(request):
                        with REQUEST_TIME.time():
                            ...

        Returns:
            A :class:`prometheus_client.context_managers.Timer` instance.
        """  # noqa: LN001
        return Timer(self, 'observe')

    def _child_samples(self) -> Iterable[Sample]:
        samples = [
            Sample('_count', {}, self._count.get(), None, None),
            Sample('_sum', {}, self._sum.get(), None, None),
        ]
        if _use_created:
            samples.append(Sample('_created', {}, self._created, None, None))
        return tuple(samples)


@append_docstring(METRICS_WRAPPER_DOCS % 'Histogram')
class Histogram(MetricWrapperBase):
    """
    A Histogram tracks the size and number of events in a given bucket.
    Histograms are often used to aggregatable calculation of quantiles.

    Some notable examples include:

    * Response latency
    * Request size

    Example for a Histogram:

    .. code-block:: python

        from prometheus_client import Histogram

        request_size = Histogram('request_size_bytes', 'Request size (bytes)')
        request_size.observe(512)  # Observe 512 (bytes)

    In addition to all :class:`prometheus_client.MetricWrapperBase` init arguments,
    ``Histogram`` also accepts a ``buckets`` argument.

    ``buckets`` is a list of floats that defines the range in which the events are counted.
    The default buckets are intended to cover a typical web/rpc request from milliseconds to
    seconds. The default buckets can be found at
    :attr:``prometheus_client.Histogram.DEFAULT_BUCKETS``.

    .. note::

        If ``labelnames`` is provided, it must not contain ``le``, as this label is reserved internally.

    .. note::

        If ``buckets`` is provided, it must be sorted in ascending order. Additionally, ``buckets`` must
        contains at least two buckets.

    Raises:
        ValueError: The following scenarios will raise a ``ValueError``:

                    * ``buckets`` is not sorted correctly.
                    * ``buckets`` are less than 2.
    """  # noqa: LN001
    _type = 'histogram'
    _reserved_labelnames = ['le']
    DEFAULT_BUCKETS = (.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, INF)

    def __init__(self,
                 name: str,
                 documentation: str,
                 labelnames: Iterable[str] = (),
                 namespace: str = '',
                 subsystem: str = '',
                 unit: str = '',
                 registry: Optional[CollectorRegistry] = REGISTRY,
                 _labelvalues: Optional[Sequence[str]] = None,
                 buckets: Sequence[Union[float, str]] = DEFAULT_BUCKETS,
                 ):
        self._prepare_buckets(buckets)
        super().__init__(
            name=name,
            documentation=documentation,
            labelnames=labelnames,
            namespace=namespace,
            subsystem=subsystem,
            unit=unit,
            registry=registry,
            _labelvalues=_labelvalues,
        )
        self._kwargs['buckets'] = buckets

    def _prepare_buckets(self, source_buckets: Sequence[Union[float, str]]) -> None:
        buckets = [float(b) for b in source_buckets]
        if buckets != sorted(buckets):
            # This is probably an error on the part of the user,
            # so raise rather than sorting for them.
            raise ValueError('Buckets not in sorted order')
        if buckets and buckets[-1] != INF:
            buckets.append(INF)
        if len(buckets) < 2:
            raise ValueError('Must have at least two buckets')
        self._upper_bounds = buckets

    def _metric_init(self) -> None:
        self._buckets: List[values.ValueClass] = []
        self._created = time.time()
        bucket_labelnames = self._labelnames + ('le',)
        self._sum = values.ValueClass(self._type, self._name, self._name + '_sum', self._labelnames, self._labelvalues)
        for b in self._upper_bounds:
            self._buckets.append(values.ValueClass(
                self._type,
                self._name,
                self._name + '_bucket',
                bucket_labelnames,
                self._labelvalues + (floatToGoString(b),))
            )

    def observe(self, amount: float, exemplar: Optional[Dict[str, str]] = None) -> None:
        """
        Observe the given amount.

        The amount is usually positive or zero. Negative values are
        accepted but prevent current versions of Prometheus from
        properly detecting counter resets in the sum of
        observations. See
        https://prometheus.io/docs/practices/histograms/#count-and-sum-of-observations
        for details.

        Args:
            amount: The amount to observe.
            exemplar: An optional dictionary of string key-value pairs to
                      attach to the metric as an exemplar. The definition can be
                      found `here <https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md#exemplars>`_.

        Examples:

        .. tab-set::

            .. tab-item:: Simple use case

                .. code-block:: python

                    from prometheus_client import Histogram
                    request_size = Histogram('request_size_bytes', 'Request size (bytes)')
                    request_size.observe(512)  # Observe 512 (bytes)

            .. tab-item:: Exemplar

                .. code-block:: python

                    from prometheus_client import Histogram
                    request_size = Histogram('request_size_bytes', 'Request size (bytes)')
                    request_size.observe(1.6, exemplar={"trace_id":"oHg5SJYRHA0"})

        Raises:
            ValueError: The following scenarios will raise ``ValueError``:

                        * If given metrics are not observable
                        * If the given amount is negative.
                        * If given exemplar labels are invalid.

        """  # noqa: LN001
        self._raise_if_not_observable()
        self._sum.inc(amount)
        for i, bound in enumerate(self._upper_bounds):
            if amount <= bound:
                self._buckets[i].inc(1)
                if exemplar:
                    _validate_exemplar(exemplar)
                    self._buckets[i].set_exemplar(Exemplar(exemplar, amount, time.time()))
                break

    def time(self) -> Timer:
        """
        Time a block of code or function, and observe the duration in seconds.

        Can be used as a function decorator or context manager.

        .. tab-set::

            .. tab-item:: Example

                .. code-block:: python

                    from prometheus_client import Histogram

                    REQUEST_TIME = Histogram('response_latency_seconds', 'Response latency (seconds)')

                    @REQUEST_TIME.time()
                    def foo(request):
                        ...

            .. tab-item:: Context Manager

                .. code-block:: python

                    from prometheus_client import Histogram

                    REQUEST_TIME = Histogram('response_latency_seconds', 'Response latency (seconds)')

                    def create_response(request):
                        with REQUEST_TIME.time():
                            ...

        Returns:
            A :class:`prometheus_client.context_managers.Timer` instance.
        """  # noqa: LN001
        return Timer(self, 'observe')

    def _child_samples(self) -> Iterable[Sample]:
        samples = []
        acc = 0.0
        for i, bound in enumerate(self._upper_bounds):
            acc += self._buckets[i].get()
            samples.append(Sample('_bucket', {'le': floatToGoString(bound)}, acc, None, self._buckets[i].get_exemplar()))
        samples.append(Sample('_count', {}, acc, None, None))
        if self._upper_bounds[0] >= 0:
            samples.append(Sample('_sum', {}, self._sum.get(), None, None))
        if _use_created:
            samples.append(Sample('_created', {}, self._created, None, None))
        return tuple(samples)


@append_docstring(METRICS_WRAPPER_DOCS % "Info")
class Info(MetricWrapperBase):
    """
    Info metric, as key-value pairs.

    Some notable examples include:

    * Build information
    * Version information
    * Potential target metadata

    Example for a Info:

    .. code-block:: python

        from prometheus_client import Info

        i = Info('my_build', 'Description of info')
        i.info({'version': '1.2.3', 'buildhost': 'foo@bar'})

    .. note::

        :class:`prometheus_client.Info` **DO NOT WORK** in multiprocess mode.
    """
    _type = 'info'

    def _metric_init(self):
        self._labelname_set = set(self._labelnames)
        self._lock = Lock()
        self._value = {}

    def info(self, val: Dict[str, str]) -> None:
        """
        Set info metric.

        Args:
            val: A dictionary of string key-value pairs to attach to the metric.

        Raises:
            ValueError: If keys overlaps with given labelnames.
        """
        if self._labelname_set.intersection(val.keys()):
            raise ValueError('Overlapping labels for Info metric, metric: {} child: {}'.format(
                self._labelnames, val))
        with self._lock:
            self._value = dict(val)

    def _child_samples(self) -> Iterable[Sample]:
        with self._lock:
            return (Sample('_info', self._value, 1.0, None, None),)


@append_docstring(METRICS_WRAPPER_DOCS % "Enum")
class Enum(MetricWrapperBase):
    """
    Enum metric, which of a set of states is true.

    Example for a Enum:

    .. code-block:: python

        from prometheus_client import Enum

        e = Enum('task_state', 'Description of enum', states=['starting', 'running', 'stopped'])
        e.state('running')

    .. note::

        The first listed state will be the default.

    In addition to all :class:`prometheus_client.MetricWrapperBase` init arguments,
    ``Enum`` also accepts a ``states`` argument, which is a sequence of strings determining
    the possible states of the enum.

    .. note::

        :class:`prometheus_client.Enum` **DO NOT WORK** in multiprocess mode.

    Raises:
        ValueError: The following scenarios will raise ``ValueError``:

                    * If ``states`` are not given.
                    * If given ``name`` exists in ``labelnames``.
    """  # noqa: LN001
    _type = 'stateset'

    def __init__(self,
                 name: str,
                 documentation: str,
                 labelnames: Sequence[str] = (),
                 namespace: str = '',
                 subsystem: str = '',
                 unit: str = '',
                 registry: Optional[CollectorRegistry] = REGISTRY,
                 _labelvalues: Optional[Sequence[str]] = None,
                 states: Optional[Sequence[str]] = None,
                 ):
        super().__init__(
            name=name,
            documentation=documentation,
            labelnames=labelnames,
            namespace=namespace,
            subsystem=subsystem,
            unit=unit,
            registry=registry,
            _labelvalues=_labelvalues,
        )
        if name in labelnames:
            raise ValueError(f'Overlapping labels for Enum metric: {name}')
        if not states:
            raise ValueError(f'No states provided for Enum metric: {name}')
        self._kwargs['states'] = self._states = states

    def _metric_init(self) -> None:
        self._value = 0
        self._lock = Lock()

    def state(self, state: str) -> None:
        """
        Set enum metric state.

        Args:
            state: The state to set the enum to.

        Raises:
            ValueError: If metrics is not observable.
        """
        self._raise_if_not_observable()
        with self._lock:
            self._value = self._states.index(state)

    def _child_samples(self) -> Iterable[Sample]:
        with self._lock:
            return [
                Sample('', {self._name: s}, 1 if i == self._value else 0, None, None)
                for i, s
                in enumerate(self._states)
            ]
