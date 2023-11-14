---
title: Info
weight: 5
---

Info tracks key-value information, usually about a whole target.

```python
from prometheus_client import Info
i = Info('my_build_version', 'Description of info')
i.info({'version': '1.2.3', 'buildhost': 'foo@bar'})
```
