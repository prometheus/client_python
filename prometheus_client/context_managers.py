from timeit import default_timer
from types import TracebackType
from typing import (
    Any, Callable, Literal, Optional, Type, TYPE_CHECKING, TypeVar,
)

from .decorator import decorate

if TYPE_CHECKING:
    from . import Counter
    F = TypeVar("F", bound=Callable[..., Any])


class ExceptionCounter:
    def __init__(self, counter: "Counter", exception: Type[BaseException]) -> None:
        self._counter = counter
        self._exception = exception

    def __enter__(self) -> None:
        pass

    def __exit__(self, typ: Optional[Type[BaseException]], value: Optional[BaseException], traceback: Optional[TracebackType]) -> Literal[False]:
        if isinstance(value, self._exception):
            self._counter.inc()
        return False

    def __call__(self, f: "F") -> "F":
        def wrapped(func, *args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return decorate(f, wrapped)


class InprogressTracker:
    def __init__(self, gauge):
        self._gauge = gauge

    def __enter__(self):
        self._gauge.inc()

    def __exit__(self, typ, value, traceback):
        self._gauge.dec()

    def __call__(self, f):
        def wrapped(func, *args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return decorate(f, wrapped)


class Timer:
    def __init__(self, callback):
        self._callback = callback

    def _new_timer(self):
        return self.__class__(self._callback)

    def __enter__(self):
        self._start = default_timer()

    def __exit__(self, typ, value, traceback):
        # Time can go backwards.
        duration = max(default_timer() - self._start, 0)
        self._callback(duration)

    def __call__(self, f):
        def wrapped(func, *args, **kwargs):
            # Obtaining new instance of timer every time
            # ensures thread safety and reentrancy.
            with self._new_timer():
                return func(*args, **kwargs)

        return decorate(f, wrapped)
