"""Pytest configuration for apps/fb_dashboard tests.

Adds src/ to sys.path so tests can import dashboard modules without installing
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

# Minimal env vars to allow importing `utils.settings` at test collection time.
_SETTINGS_DEFAULTS = {
    "SYSTEM_DOCKER_REGISTRY_URL": "localhost:5000/",
    "JF_SYSTEM_NAMESPACE": "test-ns",
    "JF_DB_HOST": "localhost",
    "JF_DB_PORT": "3306",
    "JF_REDIS_PROT": "6379",
    "JF_KAFKA_DNS": "localhost:9092",
    "JF_KONG_ADMIN_DNS": "localhost",
}
for _key, _val in _SETTINGS_DEFAULTS.items():
    os.environ.setdefault(_key, _val)
