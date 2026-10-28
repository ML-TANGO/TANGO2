#!/usr/bin/env python3

import json
import socket


def http_json_request(
    host,
    port,
    event_id,
    timeout_ms,
    path="/service",
    method="GET",
    headers=None,
):
    request_headers = {
        "Connection": "close",
        "Host": host,
        "X-TANGO2-Event": event_id,
        **(headers or {}),
    }
    lines = [f"{method} {path} HTTP/1.1"]
    lines.extend(f"{key}: {value}" for key, value in request_headers.items())
    if method == "POST":
        lines.append("Content-Length: 0")
    request = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")

    with socket.create_connection(
        (host, port), timeout=timeout_ms / 1000
    ) as sock:
        sock.settimeout(timeout_ms / 1000)
        sock.sendall(request)
        chunks = []
        total = 0
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > 65536:
                raise RuntimeError("HTTP response exceeds 64KiB")

    response = b"".join(chunks)
    header, separator, body = response.partition(b"\r\n\r\n")
    if not separator:
        raise RuntimeError("incomplete HTTP response")
    status_line = header.splitlines()[0].decode("ascii", "replace")
    fields = status_line.split()
    if len(fields) < 2 or not fields[1].isdigit():
        raise RuntimeError(f"invalid HTTP status: {status_line}")
    return int(fields[1]), json.loads(body.decode("utf-8"))
