---
title: Django
weight: 5
---

To use Prometheus with [Django](https://www.djangoproject.com/) you can use the provided view class 
to add a metrics endpoint to your app.

```python
# urls.py

from django.urls import path
from prometheus_client.django import PrometheusDjangoView

urlpatterns = [
    # ... any other urls that you want
    path("metrics/", PrometheusDjangoView.as_view(), name="prometheus-metrics"),
    # ... still more urls
]
```

By default, Multiprocessing support is activated if environment variable `PROMETHEUS_MULTIPROC_DIR` is set.
You can override this through the view arguments:

```python
from django.conf import settings

urlpatterns = [
    path(
        "metrics/",
        PrometheusDjangoView.as_view(
            multiprocess_mode=settings.YOUR_SETTING  # or any boolean value
        ),
        name="prometheus-metrics",
    ),
]
```

Full multiprocessing instructions are provided [here]({{< ref "/multiprocess" >}}).

# django-prometheus

The included `PrometheusDjangoView` is useful if you want to define your own metrics from scratch.

An external package called [django-prometheus](https://github.com/django-commons/django-prometheus/) 
can be used instead if you want to get a bunch of ready-made monitoring metrics for your Django application
and easily benefit from utilities such as models monitoring.
