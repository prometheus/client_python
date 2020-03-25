import logging
import thread
import time
import traceback

from . import (CollectorRegistry, multiprocess)
from .exposition import make_wsgi_app
from .multiprocess import archive_metrics


CLEANUP_INTERVAL = 5.0

registry = CollectorRegistry()
multiprocess.InMemoryCollector(registry)
app = make_wsgi_app(registry)
log = logging.getLogger(__name__)


def archive_thread():
    while True:
        log.info("startup")
        try:
            log.info("cleaning up")
            archive_metrics()
        except Exception:
            traceback.print_exc()
        time.sleep(CLEANUP_INTERVAL)


def start_archiver_thread():
    thread.start_new_thread(archive_thread, (), {})


def on_starting(server):
    start_archiver_thread()
