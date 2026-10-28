"""Prepare one iptables-nft-restore transaction without submitting COMMIT.

The stock verbose parser echoes and flushes comment lines after parsing the
preceding rules. Its explicit-COMMIT mode aborts on EOF while a table is open.
No process or transaction is reused across events, and failed commits are never
retried here: the kernel may already have accepted them.
"""

import math
import os
import selectors
import subprocess
import time
import uuid


class PreparedRestore:
    OUTPUT_LIMIT = 65536

    def __init__(self, payload, *, command=("iptables-restore",), timeout=5.0):
        lines = payload.splitlines()
        if ("\x00" in payload or "\r" in payload
                or not payload.endswith("COMMIT\n") or len(lines) < 3
                or lines[0] != "*nat" or lines[-1] != "COMMIT"
                or any(line.startswith("*") or line.strip() == "COMMIT"
                       for line in lines[1:-1])):
            raise ValueError("expected one explicit-COMMIT nat transaction")
        if not command or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("restore command and positive timeout required")
        self.command = tuple(command)
        self.timeout = timeout
        self.marker = ("#TC2_PREPARED_" + uuid.uuid4().hex + "\n").encode("ascii")
        self.preparation = payload[:-len("COMMIT\n")].encode("ascii") + self.marker
        # One small pipe write cannot stall behind a partially consumed batch.
        if len(self.preparation) > 4096:
            raise ValueError("prepared transaction exceeds pipe write limit")
        self.process = None
        self.version = None
        self.state = "new"
        self._stdout = bytearray()
        self._stderr = bytearray()

    @property
    def pid(self):
        return self.process.pid if self.process is not None else None

    def __enter__(self):
        if self.state != "new":
            raise RuntimeError("restore preparation is single-use")
        self.state = "preparing"
        deadline = time.monotonic() + self.timeout
        try:
            version = subprocess.run(
                [*self.command, "--version"], check=True, capture_output=True,
                text=True, timeout=self.timeout,
            )
            self.version = version.stdout.strip()
            if "(nf_tables)" not in self.version:
                raise RuntimeError("prepared restore requires the nf_tables backend")
            self.process = subprocess.Popen(
                [*self.command, "--wait", "1", "--noflush", "--verbose"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=0, close_fds=True,
            )
            for stream in (self.process.stdout, self.process.stderr):
                os.set_blocking(stream.fileno(), False)
            self._write(self.preparation)
            self._read(deadline, marker=self.marker)
            if self.process.poll() is not None:
                raise RuntimeError("restore exited during preparation")
            self.state = "prepared"
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, *_):
        self.close()

    def _write(self, data):
        if self.process.stdin.closed:
            raise RuntimeError("restore input is closed")
        if os.write(self.process.stdin.fileno(), data) != len(data):
            raise RuntimeError("incomplete restore pipe write")

    def _read(self, deadline, marker=None):
        with selectors.DefaultSelector() as selector:
            for stream, output in ((self.process.stdout, self._stdout),
                                   (self.process.stderr, self._stderr)):
                if not stream.closed:
                    selector.register(stream, selectors.EVENT_READ, output)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("iptables-restore response timed out")
                for key, _ in selector.select(remaining):
                    try:
                        chunk = os.read(key.fd, 8192)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    key.data.extend(chunk)
                    if len(self._stdout) + len(self._stderr) > self.OUTPUT_LIMIT:
                        raise RuntimeError("iptables-restore output limit exceeded")
                if marker is not None and marker in self._stdout.splitlines(keepends=True):
                    return
            if marker is not None:
                error = self._stderr.decode(errors="replace")
                raise RuntimeError(f"restore exited before preparation marker: {error}")

    def check_alive(self):
        if self.state != "prepared" or self.process.poll() is not None:
            raise RuntimeError("prepared restore is no longer available")

    def commit(self):
        self.check_alive()
        # Consume the capability before writing: any failure is terminal, even
        # when COMMIT was accepted but the process did not finish successfully.
        self.state = "committing"
        deadline = time.monotonic() + self.timeout
        try:
            self._write(b"COMMIT\n")
            self.process.stdin.close()
            self._read(deadline)
            remaining = max(0, deadline - time.monotonic())
            returncode = self.process.wait(timeout=remaining)
            if returncode:
                raise subprocess.CalledProcessError(
                    returncode, self.process.args,
                    output=self._stdout.decode(errors="replace"),
                    stderr=self._stderr.decode(errors="replace"),
                )
            self.state = "committed"
        except BaseException:
            self.close()
            raise

    def close(self):
        process = self.process
        self.state = "closed"
        if process is None:
            return
        try:
            # EOF is an abort before COMMIT, never a request to apply the batch.
            if not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
        except BaseException:
            # A first termination signal may arrive during ordinary context
            # cleanup, after ExitStack has popped this callback. Reap before
            # propagating it; there will be no second __exit__ invocation.
            process.kill()
            process.wait(timeout=1)
            raise
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
