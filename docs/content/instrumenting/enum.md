---
title: Enum
weight: 6
---

Enum tracks which of a set of states something is currently in.

```python
from prometheus_client import Enum
e = Enum('my_task_state', 'Description of enum',
        states=['starting', 'running', 'stopped'])
e.state('running')
```