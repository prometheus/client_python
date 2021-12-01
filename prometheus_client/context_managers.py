from timeit import default_timer

from .decorator import decorate


class ExceptionCounter:
    def __init__(self, counter, exception):
        self._counter = counter
        self._exception = exception

    def __enter__(self):
        pass

    def __exit__(self, typ, value, traceback):
        if isinstance(value, self._exception):
            self._counter.inc()

    def __call__(self, f):
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
        return self

    def __exit__(self, typ, value, traceback):
        # Time can go backwards.
        duration = max(default_timer() - self._start, 0)
        instance = self._callback.__self__
        instance._raise_if_not_observable()
        self._callback(duration)

    def labels(self, *args, **kw):
        instance = self._callback.__self__
        self._callback = getattr(
            instance.labels(*args, **kw),
            self._callback.__name__)

    def __call__(self, f):
        def wrapped(func, *args, **kwargs):
            # Obtaining new instance of timer every time
            # ensures thread safety and reentrancy.
            with self._new_timer():
                return func(*args, **kwargs)

        return decorate(f, wrapped)
