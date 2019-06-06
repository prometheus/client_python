import logging
import thread
import time
import traceback

from . import (CollectorRegistry, multiprocess)
from .exposition import make_wsgi_app
from .multiprocess import cleanup_dead_processes


CLEANUP_INTERVAL = 60.0

registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)
prometheus_expoter_app = make_wsgi_app(registry)
log = logging.getLogger(__name__)


def cleanup_thread():
    while True:
        log.info("startup")
        try:
            log.info("cleaning up")
            cleanup_dead_processes()
        except Exception:
            traceback.print_exc()
        time.sleep(CLEANUP_INTERVAL)


def start_cleanup_thread():
    thread.start_new_thread(cleanup_thread, (), {})


def on_starting(server):
    start_cleanup_thread()


def app(req, start_response):
    if req.get("PATH_INFO") == "/healthz":
        body = "OK"
        headers = [("Content-Type", "text/plain"),
                   ("Content-Length", "{:d}".format(len(body)))]
        start_response("200 OK", headers)
        return iter([body])
    else:
        return prometheus_expoter_app(req, start_response)
