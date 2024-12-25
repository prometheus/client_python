import functools
import sys
from timeit import default_timer
from types import TracebackType
from typing import (
    Callable, Literal, Optional, Tuple, Type, TYPE_CHECKING, TypeVar, Union,
)

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from . import Counter

TParam = ParamSpec("TParam")
TResult = TypeVar("TResult")


class ExceptionCounter:
    def __init__(self, counter: "Counter", exception: Union[Type[BaseException], Tuple[Type[BaseException], ...]]) -> None:
        self._counter = counter
        self._exception = exception

    def __enter__(self) -> None:
        pass

    def __exit__(self, typ: Optional[Type[BaseException]], value: Optional[BaseException], traceback: Optional[TracebackType]) -> Literal[False]:
        if isinstance(value, self._exception):
            self._counter.inc()
        return False

    def __call__(self, f: Callable[TParam, TResult]) -> Callable[TParam, TResult]:
        @functools.wraps(f)
        def wrapped(*args: TParam.args, **kwargs: TParam.kwargs) -> TResult:
            with self:
                return f(*args, **kwargs)
        return wrapped  # type: ignore


class InprogressTracker:
    def __init__(self, gauge):
        self._gauge = gauge

    def __enter__(self):
        self._gauge.inc()

    def __exit__(self, typ, value, traceback):
        self._gauge.dec()

    def __call__(self, f: Callable[TParam, TResult]) -> Callable[TParam, TResult]:
        @functools.wraps(f)
        def wrapped(*args: TParam.args, **kwargs: TParam.kwargs) -> TResult:
            with self:
                return f(*args, **kwargs)
        return wrapped  # type: ignore


class Timer:
    def __init__(self, metric, callback_name):
        self._metric = metric
        self._callback_name = callback_name

    def _new_timer(self):
        return self.__class__(self._metric, self._callback_name)

    def __enter__(self):
        self._start = default_timer()
        return self

    def __exit__(self, typ, value, traceback):
        # Time can go backwards.
        duration = max(default_timer() - self._start, 0)
        callback = getattr(self._metric, self._callback_name)
        callback(duration)

    def labels(self, *args, **kw):
        self._metric = self._metric.labels(*args, **kw)

    def __call__(self, f: Callable[TParam, TResult]) -> Callable[TParam, TResult]:
        @functools.wraps(f)
        def wrapped(*args: TParam.args, **kwargs: TParam.kwargs) -> TResult:
            # Obtaining new instance of timer every time
            # ensures thread safety and reentrancy.
            with self._new_timer():
                return f(*args, **kwargs)
        return wrapped  # type: ignore
