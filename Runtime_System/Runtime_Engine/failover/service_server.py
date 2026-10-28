#!/usr/bin/env python3

import json
import os
import signal
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


INSTANCE_ID = os.environ["INSTANCE_ID"]
PORT = int(os.environ.get("PORT", "8080"))
BOOT_ID = str(uuid.uuid4())


class WorkerPoolHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, workers=8):
        self.executor = ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="tango2-http",
        )
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        self.executor.submit(
            self.process_request_thread, request, client_address
        )

    def server_close(self):
        super().server_close()
        self.executor.shutdown(wait=True, cancel_futures=True)


class ServiceHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_payload(self):
        payload = json.dumps(
            {
                "boot_id": BOOT_ID,
                "event_id": self.headers.get("X-TANGO2-Event", ""),
                "instance_id": INSTANCE_ID,
            },
            sort_keys=True,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path not in ("/readyz", "/service"):
            self.send_error(404)
            return
        self.send_payload()

    def log_message(self, format_string, *args):
        return


def exit_for_cleanup(signum, frame):
    # This disposable server owns no evidence or persistent application state.
    # Cleanup must not wait for unfinished HTTP workers or executor atexit joins.
    os._exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, exit_for_cleanup)
    WorkerPoolHTTPServer(("0.0.0.0", PORT), ServiceHandler).serve_forever()
