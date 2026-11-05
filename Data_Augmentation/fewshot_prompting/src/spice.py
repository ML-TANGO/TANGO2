"""SPICE metric (Anderson et al., ECCV 2016) through a long-running Java process.

SPICE parses the candidate and the reference into scene graphs with Stanford
CoreNLP and scores the F1 of their (object, attribute, relation) tuples.
Starting a JVM and loading CoreNLP costs ~5 s, so one ``spice/SpiceServer.java``
process stays up and scores batches sent over stdin.

English only: CoreNLP's English parser finds no tuples in Korean text, so a
Korean pair scores 0.

Files under ``SPICE_HOME`` (``/opt/spice`` in the Docker image, ``spice/dist``
for a local run — see ``spice/setup.sh``):
    spice-1.0.jar, lib/*.jar                  from the pycocoevalcap wheel
    lib/stanford-corenlp-3.6.0[-models].jar   Stanford CoreNLP, fetched on first use
    server/edu/anu/spice/SpiceServer.class    the compiled server
"""

from __future__ import annotations

import atexit
import collections
import json
import math
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import urllib.request
import zipfile
from collections.abc import Sequence
from pathlib import Path

SPICE_HOME = Path(os.environ.get("SPICE_HOME") or Path(__file__).resolve().parents[1] / "spice" / "dist")
SPICE_XMX = os.environ.get("SPICE_XMX", "3g")
# LMDB cache of parsed tuples (speeds up repeated captions; lmdbjni is x86_64-only).
SPICE_CACHE_DIR = os.environ.get("SPICE_CACHE_DIR")
# Optional on-disk cache of pair scores shared by processes (e.g. jobs restarted from their LM
# cache would otherwise re-parse every pair). Off unless set.
SPICE_SCORE_CACHE = os.environ.get("SPICE_SCORE_CACHE")
# Processors the JVM may use (GC and parser threads); SPICE's own default is every core.
SPICE_CPUS = os.environ.get("SPICE_CPUS", os.environ.get("SPICE_THREADS", "4"))

_CORENLP = "stanford-corenlp-full-2015-12-09"
_CORENLP_URL = f"https://nlp.stanford.edu/software/{_CORENLP}.zip"
_CORENLP_JARS = ("stanford-corenlp-3.6.0.jar", "stanford-corenlp-3.6.0-models.jar")


def spice_installed() -> bool:
    """Java, the SPICE jars and the compiled server are present (CoreNLP is
    fetched on first use)."""
    return (
        shutil.which("java") is not None
        and (SPICE_HOME / "spice-1.0.jar").is_file()
        and (SPICE_HOME / "server" / "edu" / "anu" / "spice" / "SpiceServer.class").is_file()
    )


def ensure_corenlp() -> None:
    """Download the two Stanford CoreNLP 3.6.0 jars SPICE needs (~370 MB), once."""
    lib = SPICE_HOME / "lib"
    if all((lib / jar).is_file() for jar in _CORENLP_JARS):
        return
    lib.mkdir(parents=True, exist_ok=True)
    print(f"[spice] downloading Stanford CoreNLP from {_CORENLP_URL} ...")
    with tempfile.TemporaryDirectory(dir=lib) as tmp:
        archive = os.path.join(tmp, "corenlp.zip")
        urllib.request.urlretrieve(_CORENLP_URL, archive)
        with zipfile.ZipFile(archive) as z:
            for jar in _CORENLP_JARS:
                with z.open(f"{_CORENLP}/{jar}") as src, open(os.path.join(tmp, jar), "wb") as dst:
                    shutil.copyfileobj(src, dst)
        for jar in _CORENLP_JARS:  # moved in only once complete
            os.replace(os.path.join(tmp, jar), lib / jar)
    print("[spice] Stanford CoreNLP ready")


class _SpiceServer:
    """One SpiceServer JVM. SPICE scores one batch at a time, so requests are
    serialized; a dead process is restarted on the next request."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue[str] = queue.Queue()
        self._stderr_tail: collections.deque[str] = collections.deque(maxlen=30)
        self._work: tempfile.TemporaryDirectory | None = None
        self._lock = threading.Lock()
        self._n = 0

    def start(self) -> None:
        with self._lock:
            self._ensure_running()

    def _ensure_running(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        if not spice_installed():
            raise RuntimeError(f"SPICE is not installed (java on PATH and SPICE_HOME={SPICE_HOME} needed)")
        ensure_corenlp()
        classpath = os.pathsep.join(
            [str(SPICE_HOME / "server"), str(SPICE_HOME / "spice-1.0.jar"), str(SPICE_HOME / "lib" / "*")]
        )
        cmd = ["java", f"-Xmx{SPICE_XMX}", f"-XX:ActiveProcessorCount={SPICE_CPUS}", "-cp", classpath, "edu.anu.spice.SpiceServer"]
        if SPICE_CACHE_DIR:
            cmd.append(SPICE_CACHE_DIR)
        self._work = tempfile.TemporaryDirectory(prefix="spice-")
        self._lines = queue.Queue()
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        threading.Thread(target=self._pump_stdout, args=(self._proc.stdout, self._lines), daemon=True).start()
        threading.Thread(target=self._pump_stderr, args=(self._proc.stderr, self._stderr_tail), daemon=True).start()
        if json.loads(self._readline(timeout=300)).get("event") != "ready":
            raise RuntimeError(f"SPICE server did not start: {list(self._stderr_tail)[-5:]}")

    @staticmethod
    def _pump_stdout(stream, lines: queue.Queue) -> None:
        for line in stream:
            lines.put(line.rstrip("\n"))
        lines.put('{"event":"error","msg":"SPICE server exited"}')  # unblock a waiting reader

    @staticmethod
    def _pump_stderr(stream, tail: collections.deque) -> None:
        for line in stream:
            tail.append(line.rstrip("\n"))

    def _readline(self, timeout: float) -> str:
        try:
            return self._lines.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(f"SPICE server: no reply in {timeout:.0f}s") from None

    def close(self) -> None:
        """Stop the JVM (also registered at interpreter exit)."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.stdin.write("EXIT\n")
                    self._proc.stdin.flush()
                    self._proc.wait(timeout=10)
                except Exception:  # noqa: BLE001 — best effort
                    self._proc.kill()
            self._proc = None
            if self._work is not None:
                self._work.cleanup()
                self._work = None

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        """SPICE F of each (reference, candidate) pair, in order."""
        with self._lock:
            try:
                return self._score(pairs)
            except Exception as e:
                if self._proc is not None and self._proc.poll() is None:
                    raise  # the server is alive: this batch itself failed
                print(f"[spice] server died ({e}); restarting once. stderr tail: {list(self._stderr_tail)[-3:]}")
                self._proc = None
                return self._score(pairs)

    def _score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        self._ensure_running()
        self._n += 1
        in_path = os.path.join(self._work.name, f"req{self._n}.json")
        out_path = os.path.join(self._work.name, f"res{self._n}.json")
        with open(in_path, "w", encoding="utf-8") as f:
            json.dump([{"image_id": i, "test": c, "refs": [r]} for i, (r, c) in enumerate(pairs)], f, ensure_ascii=False)
        self._proc.stdin.write(f"{in_path}\t{out_path}\n")
        self._proc.stdin.flush()
        reply = json.loads(self._readline(timeout=600))
        if reply.get("event") != "done":
            raise ValueError(f"SPICE error: {reply.get('msg')}")
        with open(out_path, encoding="utf-8") as f:
            results = json.load(f)
        os.remove(in_path)
        os.remove(out_path)
        by_id = {r["image_id"]: r["scores"]["All"]["f"] for r in results}
        return [_finite(by_id.get(i)) for i in range(len(pairs))]


def _finite(value) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) else 0.0


_server = _SpiceServer()
atexit.register(lambda: _server.close())
_memo: dict[tuple[str, str], float] = {}
_memo_lock = threading.Lock()


def start() -> None:
    """Fetch CoreNLP if needed and start the server (blocking). Raises if SPICE
    cannot run here."""
    _server.start()


_disk = None


def _score_cache():
    global _disk
    if SPICE_SCORE_CACHE and _disk is None:
        import diskcache

        _disk = diskcache.Cache(SPICE_SCORE_CACHE)
    return _disk


def spice_scores(pairs: Sequence[tuple[str, str]]) -> list[float]:
    """SPICE F of each (reference, candidate) pair, in one server request for all
    pairs not seen before. Empty strings score 0."""
    keys = [(r.strip(), c.strip()) for r, c in pairs]
    with _memo_lock:
        todo = list(dict.fromkeys(k for k in keys if k[0] and k[1] and k not in _memo))
    disk = _score_cache()
    if todo and disk is not None:
        found = {k: disk.get(k) for k in todo}
        with _memo_lock:
            _memo.update({k: v for k, v in found.items() if v is not None})
        todo = [k for k in todo if found[k] is None]
    if todo:
        scores = _server.score(todo)
        with _memo_lock:
            _memo.update(zip(todo, scores))
        if disk is not None:
            for k, v in zip(todo, scores):
                disk.set(k, v)
    with _memo_lock:
        return [_memo[k] if (k[0] and k[1]) else 0.0 for k in keys]


def preload_spice() -> threading.Thread | None:
    """Start CoreNLP download + server start in the background at service start,
    so the first job does not wait. No-op when SPICE is not installed or
    ``SPICE_PRELOAD=false``."""
    if os.environ.get("SPICE_PRELOAD", "true").lower() in ("0", "false", "no") or not spice_installed():
        return None

    def run() -> None:
        try:
            start()
            print("[spice] SPICE server ready")
        except Exception as e:  # noqa: BLE001 — e.g. offline; spice jobs fall back to token_f1
            print(f"[spice] preload failed ({type(e).__name__}: {e})")

    thread = threading.Thread(target=run, name="spice-preload", daemon=True)
    thread.start()
    return thread
