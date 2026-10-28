"""Pytest configuration for apps/fb_ingress_management tests.

`ingress_manager.manager` imports `ingress_manager.admin_api` and `from utils
import ...`. In runtime this resolves because the app's `src/` holds both the
`ingress_manager` package and a `utils -> ../../fb_utils/` symlink. We add that
same `src/` to sys.path so imports resolve exactly as in production — no new
symlinks, no renaming.
"""
from __future__ import annotations

import os
import sys

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(APP_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# Minimal env vars so transitively-imported `utils.settings` /
# `ingress_manager.admin_api` (which builds KONG_ADMIN_URL at import) do not
# explode at import time.
_SETTINGS_DEFAULTS = {
    "SYSTEM_DOCKER_REGISTRY_URL": "localhost:5000/",
    "JF_SYSTEM_NAMESPACE": "test-ns",
    "JF_DB_HOST": "localhost",
    "JF_DB_PORT": "3306",
    "JF_REDIS_PROT": "6379",
    "JF_KAFKA_DNS": "localhost:9092",
    "JF_KONG_ADMIN_DNS": "localhost",
    "JF_KONG_ADMIN_HTTP_PORT": "8001",
}
for _key, _val in _SETTINGS_DEFAULTS.items():
    os.environ.setdefault(_key, _val)
