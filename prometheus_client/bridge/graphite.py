#!/usr/bin/python

import logging
import re
import socket
import threading
import time
from timeit import default_timer

from ..registry import REGISTRY

# Roughly, have to keep to what works as a file name.
# We also remove periods, so labels can be distinguished.

_INVALID_GRAPHITE_CHARS = re.compile(r"[^a-zA-Z0-9_-]")


def _sanitize(s):
    return _INVALID_GRAPHITE_CHARS.sub('_', s)


class _RegularPush(threading.Thread):
    def __init__(self, pusher, interval, prefix):
        super().__init__()
        self._pusher = pusher
        self._interval = interval
        self._prefix = prefix

    def run(self):
        wait_until = default_timer()
        while True:
            while True:
                now = default_timer()
                if now >= wait_until:
                    # May need to skip some pushes.
                    while wait_until < now:
                        wait_until += self._interval
                    break
                # time.sleep can return early.
                time.sleep(wait_until - now)
            try:
                self._pusher.push(prefix=self._prefix)
            except OSError:
                logging.exception("Push failed")


class GraphiteBridge:
    def __init__(self, address, registry=REGISTRY, timeout_seconds=30, _timer=time.time, tags=False):
        self._address = address
        self._registry = registry
        self._tags = tags
        self._timeout = timeout_seconds
        self._timer = _timer

    def push(self, prefix=''):
        now = int(self._timer())
        output = []

        prefixstr = ''
        if prefix:
            prefixstr = prefix + '.'

        for metric in self._registry.collect():
            for s in metric.samples:
                if s.labels:
                    if self._tags:
                        sep = ';'
                        fmt = '{0}={1}'
                    else:
                        sep = '.'
                        fmt = '{0}.{1}'
                    labelstr = sep + sep.join(
                        [fmt.format(
                            _sanitize(k), _sanitize(v))
                            for k, v in sorted(s.labels.items())])
                else:
                    labelstr = ''
                output.append(f'{prefixstr}{_sanitize(s.name)}{labelstr} {float(s.value)} {now}\n')

        conn = socket.create_connection(self._address, self._timeout)
        conn.sendall(''.join(output).encode('ascii'))
        conn.close()

    def start(self, interval=60.0, prefix=''):
        t = _RegularPush(self, interval, prefix)
        t.daemon = True
        t.start()
