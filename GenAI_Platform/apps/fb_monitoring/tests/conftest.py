"""Pytest configuration for apps/fb_monitoring tests."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(APP_ROOT, "src")

for path in (SRC_ROOT, APP_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

_SETTINGS_DEFAULTS = {
    "SYSTEM_DOCKER_REGISTRY_URL": "localhost:5000/",
    "JF_SYSTEM_NAMESPACE": "test-ns",
    "JF_DB_HOST": "localhost",
    "JF_DB_PORT": "3306",
    "JF_REDIS_PROT": "6379",
    "JF_KAFKA_DNS": "localhost:9092",
    "JF_KONG_ADMIN_DNS": "localhost",
    "PROMETHEUS_DNS": "localhost:9090",
    "JF_MONGODB_USER": "test",
    "JF_MONGODB_PASSWORD": "test",
    "JF_MONGODB_DNS": "localhost",
    "JF_MONGODB_PORT": "27017",
}
for _key, _val in _SETTINGS_DEFAULTS.items():
    os.environ.setdefault(_key, _val)

# `apps/fb_monitoring/src/helm_run.py` calls `get_redis_client()` at module
# import time. Importing `monitoring.monitoring_service` therefore tries to
# open a live Redis connection during test collection. Neutralize it by
# pre-populating `utils.redis.get_redis_client` with a no-op stub before any
# downstream module gets a chance to import it.
import importlib  # noqa: E402

_utils_redis = importlib.import_module("utils.redis")
_utils_redis.get_redis_client = lambda *args, **kwargs: MagicMock(name="fake_redis_client")
_utils_redis.get_redis_client_async = lambda *args, **kwargs: MagicMock(name="fake_redis_client_async")
