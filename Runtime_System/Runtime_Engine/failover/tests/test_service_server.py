import http.client
import json
import os
import sys
import threading
import unittest
from pathlib import Path

os.environ.setdefault("INSTANCE_ID", "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service_server import ServiceHandler, WorkerPoolHTTPServer


class ServiceServerTest(unittest.TestCase):
    def setUp(self):
        self.server = WorkerPoolHTTPServer(("127.0.0.1", 0), ServiceHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, event_id=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=1
        )
        headers = {"X-TANGO2-Event": event_id} if event_id else {}
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        status = response.status
        payload = json.loads(response.read()) if status == 200 else None
        connection.close()
        return status, payload

    def test_both_readiness_and_service_are_always_available(self):
        self.assertEqual(self.request("/readyz")[0], 200)
        status, payload = self.request("/service", "event-001")
        self.assertEqual(status, 200)
        self.assertEqual(payload["event_id"], "event-001")
        self.assertEqual(payload["instance_id"], "test")
        self.assertTrue(payload["boot_id"])
        self.assertNotIn("role", payload)


if __name__ == "__main__":
    unittest.main()
