from prometheus_client.multiprocess.collector_utils import populate_metrics, postprocess_metrics
import contextlib
import json

import base64
import hashlib
import os
import sqlite3


def sqlite_key(metric_name, name, labelnames, labelvalues, type, multiprocess_mode):
    """Format a key for use in the SQLite file."""
    # ensure labels are in consistent order for identity
    labels = dict(zip(labelnames, labelvalues))
    return json.dumps([metric_name, name, labels, type, multiprocess_mode], sort_keys=True)


def get_database(directory):
    db_filename = os.path.join(directory, 'prometheus_python.sqlite3')
    db = sqlite3.connect(db_filename, isolation_level=None)
    db.executescript("""
    PRAGMA journal_mode = OFF;
    CREATE TABLE IF NOT EXISTS prom_values (
        pid TEXT,
        muid TEXT,
        m_key TEXT,
        multiprocess_mode TEXT NULL,
        value REAL
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ix_value ON prom_values (pid, muid);
    """)
    return db


def sqlite_cleanup(path, pid):
    with contextlib.closing(get_database(path)) as db:
        res = db.execute(
            'DELETE FROM prom_values WHERE pid = ? AND multiprocess_mode IN ("livesum", "liveall")',
            (str(pid),),
        )


class SqliteMultiProcessCollector(object):
    """Collector for files for SQlite multi-process mode."""

    def __init__(self, registry, path):
        self._path = path
        if registry:
            registry.register(self)

    def collect(self):
        metrics = {}
        # type db: sqlite3.Connection
        with contextlib.closing(self.get_database()) as db:
            for pid, key, value in db.execute('SELECT pid, m_key, value FROM prom_values'):
                metric_name, name, labels, type, multiprocess_mode = json.loads(key)
                populate_metrics(
                    metrics,
                    pid=pid,
                    metric_name=metric_name,
                    name=name,
                    labels=labels,
                    multiprocess_mode=multiprocess_mode,
                    type=type,
                    value=value,
                )

        postprocess_metrics(metrics, accumulate=True)
        return metrics.values()

    def get_database(self):
        return get_database(self._path)


class _SqliteValue(object):
    _multiprocess = True

    # Filled in by subclasses:
    database = None  # type: sqlite3.Connection
    pid_func = None  # type: function

    def __init__(self, typ, metric_name, name, labelnames, labelvalues, multiprocess_mode='', **kwargs):
        self.type = typ
        self.metric_name = metric_name
        self.name = name
        self.labelnames = labelnames
        self.labelvalues = labelvalues
        self.multiprocess_mode = multiprocess_mode
        self._key = sqlite_key(
            metric_name=self.metric_name,
            name=self.name,
            labelnames=self.labelnames,
            labelvalues=self.labelvalues,
            type=self.type,
            multiprocess_mode=multiprocess_mode,
        )
        self._muid = base64.b64encode(hashlib.sha256(self._key.encode('UTF-8')).digest()).decode()
        self.set(0)

    def inc(self, amount):
        pid = self.pid_func()
        self.database.execute(
            'INSERT INTO prom_values (pid, muid, m_key, multiprocess_mode, value) VALUES (?, ?, ?, ?, ?) '
            'ON CONFLICT (pid, muid) DO UPDATE SET value = value + ?',
            (pid, self._muid, self._key, self.multiprocess_mode, amount, amount)
        )

    def set(self, value):
        pid = self.pid_func()
        self.database.execute(
            'INSERT INTO prom_values (pid, muid, m_key, multiprocess_mode, value) VALUES (?, ?, ?, ?, ?) '
            'ON CONFLICT (pid, muid) DO UPDATE SET value = ?',
            (pid, self._muid, self._key, self.multiprocess_mode, value, value)
        )

    def get(self):
        pid = self.pid_func()
        result = self.database.execute(
            'SELECT value FROM prom_values WHERE pid = ? AND muid = ? LIMIT 1',
            (pid, self._muid),
        )
        row = result.fetchone()
        return (row[0] if row else 0)


def SqliteValue(_pidFunc=os.getpid, directory=None):
    directory = (directory or os.environ['prometheus_multiproc_dir'])

    class SqliteValue(_SqliteValue):
        database = get_database(directory)
        pid_func = staticmethod(_pidFunc)

    return SqliteValue
