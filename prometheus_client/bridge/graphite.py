#!/usr/bin/python
from __future__ import unicode_literals

import re
import socket
import time
import threading

from .. import core

# Roughly, have to keep to what works as a file name.
# We also remove periods, so labels can be distinguished.
_INVALID_GRAPHITE_CHARS = re.compile(r"[^a-zA-Z0-9_-]")

def _sanitize(s):
  return _INVALID_GRAPHITE_CHARS.sub('_', s)
  

class _RegularPush(threading.Thread):

    def __init__(self, pusher, interval):
        super(_RegularPush, self).__init__()
        self._pusher = pusher
        self._interval = interval

    def run(self):
        wait_until = time.time()
        while True:
            while True:
                now = time.time()
                if now >= wait_until:
                   # May need to skip some pushes.
                   while wait_until < now:
                       wait_until += self._interval
                   break
                # time.sleep can return early.
                time.sleep(wait_until - now)
            self._pusher.push()


class GraphiteBridge(object):
    def __init__(self, address, registry=core.REGISTRY, timeout_seconds=30, _time=time):
        self._address = address
        self._registry = registry
        self._timeout = timeout_seconds
        self._time = _time

    def push(self):
          now = int(self._time.time())
          output = []
          for metric in self._registry.collect():
              for name, labels, value in metric._samples:
                  if labels:
                      labelstr = '.' + '.'.join(
                          ['{0}.{1}'.format(
                               _sanitize(k), _sanitize(v))
                               for k, v in sorted(labels.items())])
                  else:
                      labelstr = ''
                  output.append('{0}{1} {2} {3}\n'.format(
                      _sanitize(name), labelstr, float(value), now))

          conn = socket.create_connection(self._address, self._timeout)
          conn.sendall(''.join(output).encode('ascii'))
          conn.close()

    def start(self, interval=60.0):
        t = _RegularPush(self, interval)
        t.daemon = True
        t.start()
        

