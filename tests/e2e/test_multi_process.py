import os
import sys
import subprocess
import time
import unittest
import shutil
import urllib.request
import tempfile
import json
from prometheus_client.parser import text_string_to_metric_families

class TestMultiProcessAggregate(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.environ['PROMETHEUS_MULTIPROC_DIR'] = self.tmpdir
        self.processes = []

    def tearDown(self):
        for p in self.processes:
            p.terminate()
            p.wait()
        shutil.rmtree(self.tmpdir)

    def start_server(self, port):
        # We need to make sure prometheus_client is in PYTHONPATH
        env = os.environ.copy()
        env['PYTHONPATH'] = os.getcwd()
        print(f"DEBUG: Starting server on port {port} with PROMETHEUS_MULTIPROC_DIR={env.get('PROMETHEUS_MULTIPROC_DIR')}")
        p = subprocess.Popen([sys.executable, 'tests/e2e/server.py', str(port)], env=env)
        self.processes.append(p)
        # Wait for server to start
        max_retries = 10
        for i in range(max_retries):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/metrics', timeout=1)
                break
            except:
                time.sleep(0.5)
        else:
            self.fail(f"Server on port {port} failed to start")
        return p

    def get_metrics(self, port):
        content = urllib.request.urlopen(f'http://127.0.0.1:{port}/metrics').read().decode()
        print(f"DEBUG: Metrics from {port}:\n{content}")
        families = text_string_to_metric_families(content)
        metrics = {}
        for family in families:
            for sample in family.samples:
                # Store by (name, labels_tuple)
                labels = tuple(sorted(sample.labels.items()))
                metrics[(sample.name, labels)] = sample.value
        return metrics

    def call_metric(self, port, action, name, labels, value):
        import urllib.parse
        labels_json = json.dumps(labels)
        labels_encoded = urllib.parse.quote(labels_json)
        url = f'http://127.0.0.1:{port}/{action}?name={name}&labels={labels_encoded}&value={value}'
        return urllib.request.urlopen(url).read()

    def test_aggregation_and_modes(self):
        port1 = 12345
        port2 = 12346
        
        # Start two servers
        p1 = self.start_server(port1)
        p2 = self.start_server(port2)

        labels = '{"l": "v"}'
        labels_dict = {"l": "v"}
        labels_tuple = (("l", "v"),)

        import urllib.parse
        labels_encoded = urllib.parse.quote(labels)

        # 1. Test Counters (Aggregate by sum)
        self.call_metric(port1, 'inc', 'c', labels_dict, 10)
        time.sleep(1)
        self.call_metric(port2, 'inc', 'c', labels_dict, 20)
        time.sleep(1)
        
        # 2. Test Gauges (Various modes)
        # sum
        self.call_metric(port1, 'set', 'g_sum', labels_dict, 10)
        self.call_metric(port2, 'set', 'g_sum', labels_dict, 20)
        # max
        self.call_metric(port1, 'set', 'g_max', labels_dict, 10)
        self.call_metric(port2, 'set', 'g_max', labels_dict, 20)
        # min
        self.call_metric(port1, 'set', 'g_min', labels_dict, 10)
        self.call_metric(port2, 'set', 'g_min', labels_dict, 20)
        # mostrecent
        self.call_metric(port1, 'set', 'g_mostrecent', labels_dict, 10)
        time.sleep(0.1) # Ensure different timestamp if possible (though mmap might not have high res)
        self.call_metric(port2, 'set', 'g_mostrecent', labels_dict, 20)
        
        # 3. Test Histograms
        self.call_metric(port1, 'observe', 'h', labels_dict, 2)
        self.call_metric(port2, 'observe', 'h', labels_dict, 6)

        # Check metrics while both are alive
        m = self.get_metrics(port1)
        self.assertEqual(m[('c_total', labels_tuple)], 30.0)
        self.assertEqual(m[('g_sum', labels_tuple)], 30.0)
        self.assertEqual(m[('g_max', labels_tuple)], 20.0)
        self.assertEqual(m[('g_min', labels_tuple)], 10.0)
        self.assertEqual(m[('g_mostrecent', labels_tuple)], 20.0)
        self.assertEqual(m[('h_count', labels_tuple)], 2.0)
        self.assertEqual(m[('h_sum', labels_tuple)], 8.0)
        self.assertEqual(m[('h_bucket', labels_tuple + (('le', '1.0'),))], 0.0)
        self.assertEqual(m[('h_bucket', labels_tuple + (('le', '5.0'),))], 1.0)
        self.assertEqual(m[('h_bucket', labels_tuple + (('le', '10.0'),))], 2.0)
        self.assertEqual(m[('h_bucket', labels_tuple + (('le', '+Inf'),))], 2.0)

        # Kill port2 server
        p2.terminate()
        p2.wait()
        self.processes.remove(p2)
        
        # Check metrics from surviving server (should be aggregated)
        m = self.get_metrics(port1)
        self.assertEqual(m[('c_total', labels_tuple)], 30.0)
        self.assertEqual(m[('g_sum', labels_tuple)], 30.0)
        self.assertEqual(m[('g_max', labels_tuple)], 20.0)
        self.assertEqual(m[('g_min', labels_tuple)], 10.0)
        self.assertEqual(m[('g_mostrecent', labels_tuple)], 20.0)
        self.assertEqual(m[('h_count', labels_tuple)], 2.0)
        self.assertEqual(m[('h_sum', labels_tuple)], 8.0)
        self.assertEqual(m[('h_bucket', labels_tuple + (('le', '1.0'),))], 0.0)
        self.assertEqual(m[('h_bucket', labels_tuple + (('le', '5.0'),))], 1.0)
        self.assertEqual(m[('h_bucket', labels_tuple + (('le', '10.0'),))], 2.0)
        self.assertEqual(m[('h_bucket', labels_tuple + (('le', '+Inf'),))], 2.0)
        
        # Ensure aggregate.db exists
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, 'aggregate.db')))
        
        # Kill surviving server
        p1.terminate()
        p1.wait()
        self.processes.remove(p1)
        
        # Start new server p3
        port3 = 12347
        p3 = self.start_server(port3)
        
        # Check metrics from p3 (should read from aggregate.db)
        m = self.get_metrics(port3)
        self.assertEqual(m[('c_total', labels_tuple)], 30.0)
        self.assertEqual(m[('g_sum', labels_tuple)], 30.0)
        self.assertEqual(m[('g_max', labels_tuple)], 20.0)
        self.assertEqual(m[('g_min', labels_tuple)], 10.0)
        self.assertEqual(m[('g_mostrecent', labels_tuple)], 20.0)
        self.assertEqual(m[('h_count', labels_tuple)], 2.0)
        
        # Add more to p3
        self.call_metric(port3, 'inc', 'c', labels_dict, 5)
        m = self.get_metrics(port3)
        self.assertEqual(m[('c_total', labels_tuple)], 35.0)

    def test_live_gauges(self):
        # Test various live gauge modes
        modes = {
            'g_livesum': 30.0,
            'g_livemax': 20.0,
            'g_livemin': 10.0,
            'g_livemostrecent': 20.0,
        }
        
        for name, expected_sum in modes.items():
            port1 = 12348
            port2 = 12349
            p1 = self.start_server(port1)
            p2 = self.start_server(port2)

            labels_dict = {"l": "live"}
            labels_tuple = (("l", "live"),)

            # Set live gauges
            self.call_metric(port1, 'set', name, labels_dict, 10)
            if name == 'g_livemostrecent':
                time.sleep(0.1)
            self.call_metric(port2, 'set', name, labels_dict, 20)
            
            m = self.get_metrics(port1)
            self.assertEqual(m[(name, labels_tuple)], expected_sum, f"Failed for {name} with both alive")

            # Kill p2
            p2.terminate()
            p2.wait()
            self.processes.remove(p2)
            
            # Live gauge should only reflect p1 now, as p2 is dead and live gauges are not aggregated into aggregate.db
            m = self.get_metrics(port1)
            self.assertEqual(m[(name, labels_tuple)], 10.0, f"Failed for {name} after p2 death")
            
            # Cleanup for next iteration
            p1.terminate()
            p1.wait()
            self.processes.remove(p1)
            shutil.rmtree(self.tmpdir)
            self.tmpdir = tempfile.mkdtemp()
            os.environ['PROMETHEUS_MULTIPROC_DIR'] = self.tmpdir

    def test_live_all_gauge(self):
        # Test liveall mode separately as it keeps PID labels
        port1 = 12350
        port2 = 12351
        p1 = self.start_server(port1)
        p2 = self.start_server(port2)

        pid1 = str(p1.pid)
        pid2 = str(p2.pid)

        labels_dict = {"l": "liveall"}
        
        self.call_metric(port1, 'set', 'g_liveall', labels_dict, 10)
        self.call_metric(port2, 'set', 'g_liveall', labels_dict, 20)
        
        m = self.get_metrics(port1)
        # Should have two entries with different pids
        expected_metrics = {
            (('l', 'liveall'), ('pid', pid1)): 10.0,
            (('l', 'liveall'), ('pid', pid2)): 20.0,
        }
        for labels, val in expected_metrics.items():
            self.assertEqual(m.get(('g_liveall', labels)), val, f"Missing or incorrect metric for pid {labels}")

        # Kill p2
        p2.terminate()
        p2.wait()
        self.processes.remove(p2)
        
        # Now should only have one entry (p1's)
        m = self.get_metrics(port1)
        self.assertEqual(m.get(('g_liveall', (('l', 'liveall'), ('pid', pid1)))), 10.0)
        self.assertNotIn(('g_liveall', (('l', 'liveall'), ('pid', pid2))), m)

if __name__ == '__main__':
    unittest.main()
