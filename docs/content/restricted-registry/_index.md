---
title: Restricted registry
weight: 7
---

Registries support restriction to only return specific metrics.
If you’re using the built-in HTTP server, you can use the GET parameter "name[]", since it’s an array it can be used multiple times.
If you’re directly using `generate_latest`, you can use the function `restricted_registry()`.

```python
curl --get --data-urlencode "name[]=python_gc_objects_collected_total" --data-urlencode "name[]=python_info" http://127.0.0.1:9200/metrics
```

```python
from prometheus_client import generate_latest

generate_latest(REGISTRY.restricted_registry(['python_gc_objects_collected_total', 'python_info']))
```

```python
# HELP python_info Python platform information
# TYPE python_info gauge
python_info{implementation="CPython",major="3",minor="9",patchlevel="3",version="3.9.3"} 1.0
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 73129.0
python_gc_objects_collected_total{generation="1"} 8594.0
python_gc_objects_collected_total{generation="2"} 296.0
```