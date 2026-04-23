"""Pytest configuration for apps/fb_utils tests.

`apps/fb_utils/kube.py` imports `from utils import common, TYPE`. In normal
runtime this works because every app has a `src/utils` symlink that points
back to `apps/fb_utils/`. For the `fb_utils` tests we piggyback on one of
those existing symlinks (the `fb_dashboard` app's `src/`) so that
`from utils.kube import ...` resolves the same way as in production code —
no new symlinks, no renaming, just reuse the existing layout.
"""
from __future__ import annotations

import os
import sys

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APPS_ROOT = os.path.abspath(os.path.join(APP_ROOT, ".."))
# fb_dashboard/src contains a `utils -> ../../fb_utils/` symlink, giving us
# the standard `utils.kube` import path used throughout the codebase.
DASHBOARD_SRC = os.path.join(APPS_ROOT, "fb_dashboard", "src")

for path in (DASHBOARD_SRC, APP_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

# Minimal env vars so that transitively-imported `utils.settings` (pulled in
# via `utils.common` / `utils.TYPE`) does not explode at import time.
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
