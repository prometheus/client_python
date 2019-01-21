from __future__ import unicode_literals

import unittest

from prometheus_client.multiprocess.sqlite import SqliteMultiProcessCollector, SqliteValue
from tests.common_multiprocess_tests import CommonMultiprocessTests


class TestSqliteMultiProcess(CommonMultiprocessTests, unittest.TestCase):
    _value_class = staticmethod(SqliteValue)
    _collector_class = staticmethod(SqliteMultiProcessCollector)
    _multiprocess_backend = 'sqlite'
