"""Offline test setup: no LLM endpoint and no network access needed.

Puts the service root on ``sys.path`` and points textgrad / DSPy / litellm at
throwaway or local resources, so importing the app never writes into the repo
(textgrad creates ``./logs`` on import) or into ``~/.dspy_cache``.
"""

from __future__ import annotations

import base64
import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="fewshot-tests-")
os.environ.setdefault("TEXTGRAD_LOG_DIR", os.path.join(_TMP, "textgrad_logs"))
os.environ.setdefault("DSPY_CACHEDIR", os.path.join(_TMP, "dspy_cache"))
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
os.environ.setdefault("BERTSCORE_PRELOAD", "false")  # never download models from tests
os.environ["SPICE_PRELOAD"] = "false"
# Unit tests never start Java: SPICE looks "not installed", so spice jobs fall back
# to token_f1. tests/test_spice.py points at the real files for its integration test.
REAL_SPICE_HOME = os.environ.get("SPICE_HOME") or str(Path(__file__).resolve().parents[1] / "spice" / "dist")
os.environ["SPICE_HOME"] = os.path.join(_TMP, "no-spice")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def png_data_uri(rgb: tuple[int, int, int]) -> str:
    """A valid 1x1 PNG of the given color as a base64 data URI (no PIL needed)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00" + bytes(rgb)))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode()
