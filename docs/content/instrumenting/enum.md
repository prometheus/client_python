---
title: Enum
weight: 6
---

Enum tracks which of a fixed set of states something is currently in. Only one state is active at a time. Use it for things like task state machines or lifecycle phases.

```python
from prometheus_client import Enum
e = Enum('my_task_state', 'Description of enum',
        states=['starting', 'running', 'stopped'])
e.state('running')
```

Enum exposes one time series per state:
- `<name>{<name>="<state>"}` — 1 if this is the current state, 0 otherwise

The first listed state is the default.

You can also pass a Python `enum.Enum` class. The member **names** become label
values; the underlying values may be strings, integers, or other objects.
Set the current state using a member of that class or its name:

```python
import enum
from prometheus_client import Enum

class TaskState(enum.Enum):
    starting = 1
    running = 2
    stopped = 3

e = Enum('task_state', 'Task lifecycle', states=TaskState)
e.state(TaskState.running)  # exports task_state{task_state="running"} 1.0
e.state('stopped')
```

The first member is the default. Aliases refer to the same state and do not
create additional time series. An empty enum class raises `ValueError`.

Note: Enum metrics do not work in multiprocess mode.

## Constructor

```python
Enum(name, documentation, labelnames=(), namespace='', subsystem='', unit='', registry=REGISTRY, states=[])
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Metric name. |
| `documentation` | `str` | required | Help text shown in the `/metrics` output and Prometheus UI. |
| `labelnames` | `Iterable[str]` | `()` | Names of labels for this metric. See [Labels](../labels/). The metric name itself cannot be used as a label name. |
| `namespace` | `str` | `''` | Optional prefix. |
| `subsystem` | `str` | `''` | Optional middle component. |
| `unit` | `str` | `''` | Not supported — raises `ValueError`. Enum metrics cannot have a unit. |
| `registry` | `CollectorRegistry` | `REGISTRY` | Registry to register with. Pass `None` to skip registration, which is useful in tests where you create metrics without wanting them in the global registry. |
| `states` | `Sequence[str]` or `Type[enum.Enum]` | required | The complete set of valid states. Must be non-empty. The first entry or member is the initial state. |

`namespace`, `subsystem`, and `name` are joined with underscores to form the full metric name:

```python
# namespace='myapp', subsystem='worker', name='state'
# produces: myapp_worker_state
Enum('state', 'Worker state', states=['idle', 'running', 'error'], namespace='myapp', subsystem='worker')
```

## Methods

### `state(state)`

Set the current state. The value must be one of the strings passed in the `states`
sequence. When `states` is a Python enum class, use a member of that class or its
name. A member of a different enum class is rejected, even if it has the same
name or value. Raises `ValueError` if the state is not recognized.

```python
e.state('running')
e.state('stopped')
```

## Labels

See [Labels](../labels/) for how to use `.labels()`, `.remove()`, `.remove_by_labels()`, and `.clear()`.

## Real-world example

Tracking the lifecycle state of a background worker:

```python
from prometheus_client import Enum, start_http_server

WORKER_STATE = Enum(
    'worker_state',
    'Current state of the background worker',
    states=['idle', 'running', 'error'],
    namespace='myapp',
)

def process_job():
    WORKER_STATE.state('running')
    try:
        # ... do work ...
        pass
    except Exception:
        WORKER_STATE.state('error')
        raise
    finally:
        WORKER_STATE.state('idle')

if __name__ == '__main__':
    start_http_server(8000)  # exposes metrics at http://localhost:8000/metrics
    # ... start your application ...
```

This produces:
```
myapp_worker_state{myapp_worker_state="idle"} 0.0
myapp_worker_state{myapp_worker_state="running"} 1.0
myapp_worker_state{myapp_worker_state="error"} 0.0
```
