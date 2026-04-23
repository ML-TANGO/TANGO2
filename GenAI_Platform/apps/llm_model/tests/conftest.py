"""Pytest configuration for apps/llm_model tests.

Adds src/ to sys.path so tests can import service modules without installing
the app as a package.
"""
from __future__ import annotations

import os
import sys

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(APP_ROOT, "src")

for path in (SRC_ROOT, APP_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

# Provide minimal env vars required by settings.py at import time so that
# the test suite can run without a live cluster configuration.
_SETTINGS_DEFAULTS = {
    "SYSTEM_DOCKER_REGISTRY_URL": "localhost:5000/",
    "JF_SYSTEM_NAMESPACE": "test-ns",
    "JF_DB_HOST": "localhost",
    "JF_DB_PORT": "3306",
    "JF_REDIS_PROT": "6379",  # matches settings.py key spelling (intentional)
    "JF_KAFKA_DNS": "localhost:9092",
    "JF_KONG_ADMIN_DNS": "localhost",
}
for _key, _val in _SETTINGS_DEFAULTS.items():
    os.environ.setdefault(_key, _val)
