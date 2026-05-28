"""Pytest configuration for apps/fb_scheduler tests.

`scheduler/scheduler.py` imports `from utils import TYPE, PATH, settings, ...`
and `from utils.kube import get_node_request_budget`. In normal runtime this
works because every app has a `src/utils` symlink that points back to
`apps/fb_utils/`. For the `fb_scheduler` tests we rely on that existing
symlink at `apps/fb_scheduler/src/utils -> ../../fb_utils/`, matching the
approach in `apps/fb_utils/tests/conftest.py` — no new symlinks, just reuse
the existing layout.
"""
from __future__ import annotations

import os
import sys

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_SRC = os.path.join(APP_ROOT, "src")
FB_UTILS_ROOT = os.path.abspath(os.path.join(APP_ROOT, "..", "fb_utils"))

# `APP_SRC` contains both the `scheduler/` package and the `utils` symlink
# pointing back to `apps/fb_utils/`, so a single sys.path entry unlocks both
# `from scheduler.scheduler import ...` and `from utils.kube import ...`.
for path in (APP_SRC, APP_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

# Minimal env vars so that transitively-imported `utils.settings` (pulled in
# via `utils.common` / `utils.TYPE` / `utils.kube`) does not explode at import
# time. Mirrors `apps/fb_utils/tests/conftest.py`.
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


def _prime_scheduler_submodule() -> None:
    """Eagerly import `scheduler.scheduler` so that `@patch("scheduler.scheduler.X")`
    decorators can resolve `getattr(scheduler, 'scheduler')` at decoration time.

    `apps/fb_scheduler/src/scheduler/` has no `__init__.py`, so it behaves as a
    namespace package. Under namespace-package semantics the submodule must be
    imported before it appears as an attribute on the parent. In combined pytest
    runs (e.g. `fb_utils` + `fb_scheduler`), `apps/fb_utils/` ends up on
    `sys.path` via `fb_utils`'s own conftest, which causes plain `import redis`
    inside `utils.redis` to pick up the local `apps/fb_utils/redis.py` module
    instead of the installed `redis` PyPI package, breaking the transitive
    import chain. We sidestep that by temporarily hiding `apps/fb_utils` from
    `sys.path`, pre-importing the real `redis` (and `redis.asyncio`) so they
    are cached in `sys.modules`, and restoring `sys.path` afterwards. Later
    `import redis` statements then resolve to the cached installed package.
    """
    # Pre-import the installed `redis` package with `apps/fb_utils` temporarily
    # removed from sys.path to avoid the local `redis.py` shadowing it.
    saved_path = list(sys.path)
    sys.path[:] = [p for p in sys.path if os.path.abspath(p) != FB_UTILS_ROOT]
    try:
        import redis  # noqa: F401  (installed PyPI package)
        import redis.asyncio  # noqa: F401
    finally:
        sys.path[:] = saved_path

    import scheduler.scheduler  # noqa: F401


_prime_scheduler_submodule()
