from prometheus_client.registry import CollectorRegistry
from prometheus_client.metrics import Gauge, PandasGauge, PandasGauge
import pandas as pd

def test_collector_registry_init():
    registry = CollectorRegistry()
    assert registry._collector_to_names == {}
    assert registry._names_to_collectors == {}
    assert registry._auto_describe == False
    assert str(type(registry._lock)) == "<class '_thread.lock'>"
    assert registry._target_info == None

import pytest
@pytest.mark.skip('wip')    
def test_collector_registry_gauge():
    registry = CollectorRegistry()
    g = Gauge('raid_status', '1 if raid array is okay', registry=registry)
    g.set(1)

    assert registry._names_to_collectors['raid_status'] == g
    assert registry._names_to_collectors['raid_status']._documentation == '1 if raid array is okay'
    assert '_metrics' not in vars(registry._names_to_collectors['raid_status'])

    G = Gauge('raid_status2', '1 if raid array is okay', ['label1'], registry=registry)
    #G.labels('a').set(10)
    #G.labels('b').set(11)
    #G.labels('c').set(12)
    #G.labels('c').set(13)

    assert registry._names_to_collectors['raid_status2']._labelnames == ('label1',)
    '_metrics' in vars(registry._names_to_collectors['raid_status2'])

    registry2 = CollectorRegistry()
    GP = PandasGauge('raid_status2', '1 if raid array is okay', ['label1'], registry=registry2)
    assert  type(GP._metrics) == pd.core.frame.DataFrame