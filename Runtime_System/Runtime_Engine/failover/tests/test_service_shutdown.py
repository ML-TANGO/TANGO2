import http.client
import json
import os
import select
import signal
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path


IMPLEMENTATION = Path(__file__).resolve().parents[1]


class ServiceShutdownTest(unittest.TestCase):
    def stop_process(self, process):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)
        process.stdout.close()
        process.stderr.close()

    def start_server(self):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, str(IMPLEMENTATION / "service_server.py")],
            env={**os.environ, "INSTANCE_ID": "backup", "PORT": str(port)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.stop_process, process)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self.fail(f"server exited during startup: {process.stderr.read()}")
            try:
                self.request(port, "/readyz")
                return process, port
            except OSError:
                time.sleep(0.01)
        self.fail("server did not become ready")

    def request(self, port, path):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            connection.request("GET", path, headers={"X-TANGO2-Event": "e1"})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read())
            self.assertEqual(payload["event_id"], "e1")
            self.assertEqual(payload["instance_id"], "backup")
            self.assertTrue(payload["boot_id"])
            return payload
        finally:
            connection.close()

    def assert_clean_term(self, process):
        process.send_signal(signal.SIGTERM)
        self.assertEqual(process.wait(timeout=1), 0)

    def test_server_serves_identity_and_exits_cleanly_on_term(self):
        process, port = self.start_server()
        self.request(port, "/service")
        self.assert_clean_term(process)

    def test_incomplete_request_does_not_hold_server_shutdown(self):
        process, port = self.start_server()
        unfinished = socket.create_connection(("127.0.0.1", port), timeout=1)
        self.addCleanup(unfinished.close)
        unfinished.sendall(b"GET /service HTTP/1.1\r\nHost: localhost\r\n")
        # A separate complete request proves the serving loop is active while
        # the earlier connection leaves a request worker waiting for headers.
        self.request(port, "/service")
        self.assert_clean_term(process)

    def test_stop_fault_still_suspends_server_until_continued(self):
        process, port = self.start_server()
        identity = self.request(port, "/service")
        process.send_signal(signal.SIGSTOP)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            pid, status = os.waitpid(process.pid, os.WUNTRACED | os.WNOHANG)
            if pid:
                self.assertTrue(os.WIFSTOPPED(status))
                break
            time.sleep(0.01)
        else:
            self.fail("SIGSTOP did not stop the server")
        process.send_signal(signal.SIGCONT)
        self.assertEqual(self.request(port, "/service"), identity)
        self.assert_clean_term(process)

    def test_client_sleeps_and_exits_cleanly_on_term(self):
        process = subprocess.Popen(
            [sys.executable, str(IMPLEMENTATION / "service_client_idle.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.stop_process, process)
        ready, _, _ = select.select([process.stdout], [], [], 5)
        self.assertTrue(ready, "client did not report startup")
        self.assertEqual(process.stdout.readline().strip(), "TC2_CLIENT_IDLE_READY")
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            state = subprocess.check_output(
                ["ps", "-o", "state=", "-p", str(process.pid)], text=True
            ).strip()
            if state.startswith("S"):
                break
            time.sleep(0.01)
        else:
            self.fail("idle client did not enter a sleeping state")
        self.assert_clean_term(process)


if __name__ == "__main__":
    unittest.main()
