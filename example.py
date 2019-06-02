from prometheus_client import multiprocess, generate_latest, CollectorRegistry
from prometheus_client.collector import NewCounter, NewGauge, NewHistogram
from flask import Response, Flask

app = Flask(__name__)

c = NewCounter("counter_fangjianfeng", 'Description of counter', ('address', 'service', 'function'), ("127.0.0.1", 'social', "register"))# 注册counter
g = NewGauge("guage_fangjianfeng", 'Description of guage', 'livesum', ('address', 'service', 'current_request'), ("127.0.0.1", 'social', "register")) # 注册guage
h = NewHistogram("histogram_fangjianfeng", "Description of histogram", ('address', 'service', 'endpoint'), ("127.0.0.1",'social',"/user")) # 注册histogram

@app.route("/metrics")
def metrics():
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return Response(generate_latest(registry),mimetype="text/plain")

@app.route('/index')
@h.time()
def index():
    c.inc()
    import random
    g.set(random.randint(1,10))
    return "Hello World"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
