# A simple client that serves random gauges. 
# usage: uvicorn tools.simple_client:app --reload

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from prometheus_client.asgi import make_asgi_app
from prometheus_client.core import GaugeMetricFamily, REGISTRY
import random


class CustomCollector:
    def collect(self):
        g = GaugeMetricFamily('my.random.utf8.metric', 'Random value', labels=['label.1'])
        g.add_metric(['value.1'], random.random())
        g.add_metric(['value.2'], random.random())
        yield g


app = FastAPI()


@app.get("/")
async def root():
    return RedirectResponse(url="/metrics")


REGISTRY.register(CustomCollector())
app.mount("/metrics", make_asgi_app(REGISTRY))
