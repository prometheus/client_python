#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

import prometheus_client
from flask import request, Response, Flask
from prometheus_client import Counter, Gauge, Summary, Histogram
from prometheus_client.core import  CollectorRegistry
from string import ascii_letters
from random import choice

REGISTRY = CollectorRegistry(auto_describe=False)


requests_total = Counter("app:requests_total", "Total count of requests", ["method", "url_rule", "env_role"], registry=REGISTRY)
inprogress_total = Gauge("app:inprogress_total", "Total count of requests in progress", ["method", "url_rule", "env_role"], registry=REGISTRY)
request_duration_summary_sec = Summary("app:request_duration_summary_sec", "Request duration in seconds", ["method", "url_rule", "env_role", "rnd"], registry=REGISTRY)
request_duration_historam_sec = Histogram("app:request_duration_histogram_sec", "Request duration in seconds", ["method", "url_rule", "env_role", "rnd"], registry=REGISTRY)

random_counter = Counter("random_counter", "random counter", ["rnd"], registry=REGISTRY)

APP_ENV_ROLE = os.environ.get('APP_ROLE', 'unknown')

app = Flask(__name__)
app.debug = True


@app.route("/metrics")
def metrics():
    text = "# Process in {0}\n".format(os.getpid())

    return Response(text + prometheus_client.generate_latest(REGISTRY), mimetype="text/plain")


@app.route('/<path:path>')
@app.route('/')
def index(path='/'):
    requests_total.labels(method=request.method, url_rule=path, env_role=APP_ENV_ROLE).inc()

    #requests_total.labels(method=request.method, url_rule=path, env_role=APP_ENV_ROLE).inc()

    rnd = ''.join([choice(ascii_letters) for x in xrange(10)])

    text = "# Process in {0} rnd={1}\n".format(os.getpid(), rnd)

    #random_counter.labels(rnd=rnd).inc()

    #with request_duration_summary_sec.labels(method=request.method, url_rule=path, env_role=APP_ENV_ROLE, rnd=rnd).time():#, \
        #request_duration_historam_sec.labels(method=request.method, url_rule=path, env_role=APP_ENV_ROLE, rnd=rnd).time():

    return Response(text, mimetype="text/plain")

application = app
print("Debug app init")
