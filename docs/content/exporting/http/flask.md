---
title: Flask
weight: 4
---

To use Prometheus with [Flask](http://flask.pocoo.org/) we need to serve metrics through a Prometheus WSGI application. This can be achieved using [Flask's application dispatching](http://flask.pocoo.org/docs/latest/patterns/appdispatch/). Below is a working example.

Save the snippet below in a `myapp.py` file

```python
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app

# Create my app
app = Flask(__name__)

# Add prometheus wsgi middleware to route /metrics requests
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})
```

Run the example web application like this

```bash
# Install uwsgi if you do not have it
pip install uwsgi
uwsgi --http 127.0.0.1:8000 --wsgi-file myapp.py --callable app
```

Visit http://localhost:8000/metrics to see the metrics