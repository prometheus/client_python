import os
import warnings
from collections.abc import Callable, Sequence
from datetime import timedelta
from threading import Lock
from typing import Any, Protocol, Literal

from .mmap_dict import mmap_key, MmapedDict
from .redis import redis_client, _keep_key_from_expiring, _key_expiry
from .samples import Exemplar

MULTIPROCESS_MODE_T = Literal[
    "all",
    "liveall",
    "min",
    "livemin",
    "max",
    "livemax",
    "sum",
    "livesum",
    "mostrecent",
    "livemostrecent",
    "",
]


class Value(Protocol):
    """Prometheus Client Metric implementation."""

    _multiprocess: bool

    def __init__(
        self,
        typ: str,
        metric_name: str,
        name: str,
        labelnames: Sequence[str],
        labelvalues: Sequence[str],
        help_text: str,
        **kwargs: Any,
    ) -> None:
        """Initialize a metric."""

    def inc(self, amount: float) -> None:
        """Increment the metric by amount."""

    def set(self, value: float, timestamp: float | None = None) -> None:
        """Set the metric to value."""

    def get(self) -> float:
        """Get the current metric value."""

    def set_exemplar(self, exemplar: Exemplar) -> None:
        """Set an exemplar value."""
        exemplar  # For vulture

    def get_exemplar(self) -> Exemplar | None:
        """Get any set exemplar value."""


class MutexValue(Value):
    """A float protected by a mutex."""

    _multiprocess = False

    def __init__(self, typ, metric_name, name, labelnames, labelvalues, help_text, **kwargs):
        self._value = 0.0
        self._exemplar = None
        self._lock = Lock()

    def inc(self, amount):
        with self._lock:
            self._value += amount

    def set(self, value, timestamp=None):
        with self._lock:
            self._value = value

    def set_exemplar(self, exemplar):
        with self._lock:
            self._exemplar = exemplar

    def get(self):
        with self._lock:
            return self._value

    def get_exemplar(self):
        with self._lock:
            return self._exemplar


def MultiProcessValue(process_identifier=os.getpid):
    """Returns a MmapedValue class based on a process_identifier function.

    The 'process_identifier' function MUST comply with this simple rule:
    when called in simultaneously running processes it MUST return distinct values.

    Using a different function than the default 'os.getpid' is at your own risk.
    """
    files = {}
    values = []
    pid = {'value': process_identifier()}
    # Use a single global lock when in multi-processing mode
    # as we presume this means there is no threading going on.
    # This avoids the need to also have mutexes in __MmapDict.
    lock = Lock()

    class MmapedValue(Value):
        """A float protected by a mutex backed by a per-process mmaped file."""

        _multiprocess = True

        def __init__(self, typ, metric_name, name, labelnames, labelvalues, help_text, multiprocess_mode='', **kwargs):
            self._params = typ, metric_name, name, labelnames, labelvalues, help_text, multiprocess_mode
            # This deprecation warning can go away in a few releases when removing the compatibility
            if 'prometheus_multiproc_dir' in os.environ and 'PROMETHEUS_MULTIPROC_DIR' not in os.environ:
                os.environ['PROMETHEUS_MULTIPROC_DIR'] = os.environ['prometheus_multiproc_dir']
                warnings.warn("prometheus_multiproc_dir variable has been deprecated in favor of the upper case naming PROMETHEUS_MULTIPROC_DIR", DeprecationWarning)
            with lock:
                self.__check_for_pid_change()
                self.__reset()
                values.append(self)

        def __reset(self):
            typ, metric_name, name, labelnames, labelvalues, help_text, multiprocess_mode = self._params
            if typ == 'gauge':
                file_prefix = typ + '_' + multiprocess_mode
            else:
                file_prefix = typ
            if file_prefix not in files:
                filename = os.path.join(
                    os.environ.get('PROMETHEUS_MULTIPROC_DIR'),
                    '{}_{}.db'.format(file_prefix, pid['value']))

                files[file_prefix] = MmapedDict(filename)
            self._file = files[file_prefix]
            self._key = mmap_key(metric_name, name, labelnames, labelvalues, help_text)
            self._value, self._timestamp = self._file.read_value(self._key)

        def __check_for_pid_change(self):
            actual_pid = process_identifier()
            if pid['value'] != actual_pid:
                pid['value'] = actual_pid
                # There has been a fork(), reset all the values.
                for f in files.values():
                    f.close()
                files.clear()
                for value in values:
                    value.__reset()

        def inc(self, amount):
            with lock:
                self.__check_for_pid_change()
                self._value += amount
                self._timestamp = 0.0
                self._file.write_value(self._key, self._value, self._timestamp)

        def set(self, value, timestamp=None):
            with lock:
                self.__check_for_pid_change()
                self._value = value
                self._timestamp = timestamp or 0.0
                self._file.write_value(self._key, self._value, self._timestamp)

        def set_exemplar(self, exemplar):
            # TODO: Implement exemplars for multiprocess mode.
            return

        def get(self):
            with lock:
                self.__check_for_pid_change()
                return self._value

        def get_exemplar(self):
            # TODO: Implement exemplars for multiprocess mode.
            return None

    return MmapedValue


def RedisValue(process_identifier: Callable[[], str | int] = os.getpid) -> type[Value]:

    class RedisValueImpl(Value):
        """
        A value implementation that stores data in a redis/valkey database.

        Key scheme:
        * value:typ:MMAP_KEY

        When a live multiprocess_mode is used, we set the key to expire after
        PROMETHEUS_REDIS_REFRESH_TTL seconds. We launch a daemon thread that
        extends the expiry of all our process' keys every
        PROMETHEUS_REDIS_REFRESH_FREQUENCY.
        """

        _multiprocess: bool = True

        _typ: str
        _metric_name: str
        _name: str
        _labelnames: list[str]
        _labelvalues: list[str]
        _help_text: str
        _multiprocess_mode: MULTIPROCESS_MODE_T
        _expiry: timedelta | None

        _key: str

        def __init__(
            self,
            typ: str,
            metric_name: str,
            name: str,
            labelnames: Sequence[str],
            labelvalues: Sequence[str],
            help_text: str,
            multiprocess_mode: MULTIPROCESS_MODE_T = "",
            **kwargs: Any,
        ) -> None:
            self._typ = typ
            self._metric_name = metric_name
            self._name = name
            self._labelnames = list(labelnames)
            self._labelvalues = list(labelvalues)
            self._help_text = help_text
            self._multiprocess_mode = multiprocess_mode
            self._expiry = None
            if multiprocess_mode:
                if multiprocess_mode in ("mostrecent", "livemostrecent"):
                    raise NotImplementedError(
                        "The 'mostrecent' modes are not supported in RedisValue"
                    )
                assert typ in ("gauge", "gaugehistogram")
                self._labelnames.append("pid")
                self._labelvalues.append("")
                if multiprocess_mode.startswith("live"):
                    self._expiry = _key_expiry()
            self._update_key(True)
            redis_client().set(self._key, 0.0, ex=self._expiry, nx=True)

        def _update_key(self, update: bool = False) -> None:
            if self._multiprocess_mode:
                assert self._labelnames[-1] == "pid"
                new_id = str(process_identifier())
                if new_id != self._labelvalues[-1]:
                    self._labelvalues[-1] = new_id
                    update = True

            if update:
                key = mmap_key(
                    self._metric_name,
                    self._name,
                    self._labelnames,
                    self._labelvalues,
                    self._help_text,
                )
                self._key = f"value:{self._typ}:{self._multiprocess_mode}:{key}"

            if self._expiry and update:
                _keep_key_from_expiring(self._labelvalues[-1], self._key)

        def inc(self, amount: float) -> None:
            self._update_key()
            client = redis_client()
            client.incrbyfloat(self._key, amount)
            if self._expiry:
                client.expire(self._key, self._expiry)

        def set(self, value: float, timestamp: float | None = None) -> None:
            self._update_key()
            # TODO: Implement timestamps
            redis_client().set(self._key, value, ex=self._expiry)

        def get(self) -> float:
            self._update_key()
            value = redis_client().get(self._key)
            if value is None:
                return 0.0
            return float(value)

        def set_exemplar(self, exemplar: Exemplar) -> None:
            # TODO: Implement exemplars for redis.
            raise NotImplementedError("Exemplars are not implemented for Redis.")

        def get_exemplar(self) -> Exemplar | None:
            # TODO: Implement exemplars for redis.
            return None

    return RedisValueImpl


def get_value_class() -> type[Value]:
    # Should we enable multi-process mode?
    # This needs to be chosen before the first metric is constructed,
    # and as that may be in some arbitrary library the user/admin has
    # no control over we use an environment variable.
    if "PROMETHEUS_REDIS_URL" in os.environ:
        return RedisValue()
    elif (
        "prometheus_multiproc_dir" in os.environ
        or "PROMETHEUS_MULTIPROC_DIR" in os.environ
    ):
        return MultiProcessValue()
    else:
        return MutexValue


ValueClass = get_value_class()
