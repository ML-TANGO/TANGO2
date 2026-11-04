"""Boot-time manifest seeding — ship-with-the-service YAML → registry.

Registration is otherwise runtime-only (``POST /api/v1/manifests``), so a
freshly installed instance boots with an empty registry: the SDS 학습 화면
resolves no manifest (FE silently falls back to a recipe-less raw-params
panel) and every external job 404s until an operator remembers to POST the
YAML by hand. Seeding the files that ship in ``manifests/`` closes that gap
on every boot.

Two properties this must have, both load-bearing:

* **Idempotent** — a (name, version) already in the registry is skipped, so
  running on every startup *and* again on the background DB retry is free.
* **Never fatal** — a malformed seed file logs and is skipped. A manifest
  typo must not turn into a CrashLoop for the whole BFF, same philosophy as
  the in-memory registry fallback in ``main.py``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from .registry import ManifestRegistry, RegistryConflictError
from .schema import ExternalContainerManifest
from .validator import (
    HybridPairValidationError,
    ManifestValidationError,
    validate_hybrid_pair,
    validate_manifest,
)

logger = logging.getLogger(__name__)

# Seed files sit next to the service code — `/app/manifests` both in the image
# (Dockerfile COPY) and on the NFS src mount — so onboarding a partner
# container is a file drop plus `kubectl rollout restart`, no DB surgery.
DEFAULT_SEED_DIR = Path(__file__).resolve().parents[2] / "manifests"


def _load(path: Path) -> Optional[tuple[ExternalContainerManifest, str]]:
    """Parse + validate one seed file → (manifest, raw_yaml).

    None (with a WARN) on anything bad. The raw text is carried along rather
    than re-read at registration time: the registry stores it verbatim, and
    one read keeps the parsed manifest and the stored YAML the same revision.
    """
    try:
        raw = path.read_text()
        manifest = ExternalContainerManifest.model_validate_yaml(raw)
        validate_manifest(manifest)
        return manifest, raw
    except (yaml.YAMLError, ValueError, ManifestValidationError, OSError) as e:
        logger.warning("manifest seed: skipping %s — %s", path.name, e)
        return None


def _pairable(group: list[ExternalContainerManifest]) -> bool:
    """True when the group is exactly the two halves of a Hybrid pair.

    Pair registration is not cosmetic: `/{name}/{version}/paired` resolves the
    inference half through the shared pair_id, which is how a finished training
    run reloads the serving pod via `/deploy`. Seeding the halves separately
    would leave pair_id NULL and silently break that chain.
    """
    if len(group) != 2:
        return False
    try:
        validate_hybrid_pair(group[0], group[1])
    except HybridPairValidationError as e:
        logger.warning(
            "manifest seed: %s / %s share service_family but do not form a "
            "valid pair (%s) — registering individually",
            group[0].metadata.name, group[1].metadata.name, e.errors,
        )
        return False
    return True


async def seed_manifests(
    registry: ManifestRegistry,
    seed_dir: Optional[Path] = None,
) -> dict[str, int]:
    """Register every unregistered manifest under ``seed_dir``.

    Returns a count summary; callers log it. Missing directory is a no-op —
    an instance that ships no seed files is a valid configuration.
    """
    directory = Path(seed_dir) if seed_dir else DEFAULT_SEED_DIR
    counts = {"seeded": 0, "paired": 0, "skipped": 0, "invalid": 0}
    if not directory.is_dir():
        logger.debug("manifest seed: no seed dir at %s — nothing to do", directory)
        return counts

    files = sorted(p for p in directory.iterdir() if p.suffix in (".yaml", ".yml"))
    parsed = [loaded for p in files if (loaded := _load(p)) is not None]
    counts["invalid"] = len(files) - len(parsed)

    existing = {(r.name, r.version) for r in await registry.list_all()}

    # Group by service_family so paired manifests register atomically. A
    # manifest without service_family (single-container partners) is its own
    # group, keyed by name so two of them never collide.
    groups: dict[str, list[tuple[ExternalContainerManifest, str]]] = {}
    for manifest, raw in parsed:
        key = manifest.spec.service_family or f"_single:{manifest.metadata.name}"
        groups.setdefault(key, []).append((manifest, raw))

    for key, members in groups.items():
        missing = [
            (m, raw) for (m, raw) in members
            if (m.metadata.name, m.metadata.version) not in existing
        ]
        counts["skipped"] += len(members) - len(missing)
        if not missing:
            continue

        # Only a fully-absent pair can be registered as a pair; if one half is
        # already there, add_pair would conflict on it, so fall back to singles.
        if len(missing) == len(members) and _pairable([m for (m, _) in missing]):
            (a, ay), (b, by) = missing
            # add_pair names its first argument `infer`; order only affects
            # readability (both rows get the same pair_id), so pass infer first.
            if a.spec.job_type != "infer":
                a, b, ay, by = b, a, by, ay
            try:
                await registry.add_pair(a, ay, b, by)
            except RegistryConflictError as e:
                logger.warning("manifest seed: pair %s conflicted — %s", key, e)
                counts["skipped"] += len(missing)
                continue
            counts["paired"] += 1
            counts["seeded"] += len(missing)
            continue

        for manifest, raw in missing:
            try:
                await registry.add(manifest, raw)
            except RegistryConflictError:
                # Another replica won the race — the row exists, which is the
                # outcome we wanted.
                counts["skipped"] += 1
            else:
                counts["seeded"] += 1

    return counts
