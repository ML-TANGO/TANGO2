"""Manifest validation — self-consistency + Hybrid pair consistency.

`ExternalContainerManifest` itself enforces field-level shape via pydantic.
This module adds the cross-field and cross-manifest rules from SP-1 v2:

- §5: HTTP endpoint requirements per execution_mode
- §3: input requirements per job_type
- §1.1 "Hybrid 컨테이너": paired manifests share image identity and contract
  version, and represent a valid (infer + train) style split

Errors collect into a single list so partners get every problem at once,
not one round-trip per fix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from .schema import EndpointMap, ExecutionMode, ExternalContainerManifest, JobType


class ManifestValidationError(ValueError):
    """Raised when a single manifest fails cross-field validation."""

    def __init__(self, manifest_name: str, errors: Sequence[str]) -> None:
        self.manifest_name = manifest_name
        self.errors = list(errors)
        joined = "\n  - ".join(self.errors)
        super().__init__(f"manifest '{manifest_name}' failed validation:\n  - {joined}")


class HybridPairValidationError(ValueError):
    """Raised when two paired manifests disagree on shared metadata."""

    def __init__(self, pair: Tuple[str, str], errors: Sequence[str]) -> None:
        self.pair = pair
        self.errors = list(errors)
        joined = "\n  - ".join(self.errors)
        super().__init__(
            f"Hybrid pair ({pair[0]}, {pair[1]}) failed consistency check:\n  - {joined}"
        )


# ── Required endpoints per execution_mode (SP-1 v2 §5) ────────────────────

_REQUIRED_ENDPOINTS: dict[ExecutionMode, frozenset[str]] = {
    "sync": frozenset({"info", "health", "run"}),
    "async": frozenset({"info", "health", "run", "jobs"}),
    "batch": frozenset(),
}


@dataclass(frozen=True)
class _Issue:
    """A single validation message, collected for batched reporting."""

    message: str


def _check_endpoints(
    execution_mode: ExecutionMode,
    endpoints: EndpointMap | None,
) -> Iterable[_Issue]:
    required = _REQUIRED_ENDPOINTS[execution_mode]

    if execution_mode == "batch":
        if endpoints:
            yield _Issue(
                "spec.endpoints must be omitted or empty for execution_mode=batch "
                "(batch containers have no HTTP server)"
            )
        return

    if not endpoints:
        yield _Issue(
            f"spec.endpoints is required for execution_mode={execution_mode} "
            f"(must define {sorted(required)})"
        )
        return

    missing = required - endpoints.keys()
    if missing:
        yield _Issue(
            f"spec.endpoints missing required keys for execution_mode={execution_mode}: "
            f"{sorted(missing)}"
        )

    # async lifecycle: if a cancel endpoint is declared, it should reference {id}
    # (SP-1 v2 §5.4-5.5). cancel itself remains optional.
    for key in ("jobs", "cancel"):
        url = endpoints.get(key)
        if url is not None and "{id}" not in url:
            yield _Issue(
                f"spec.endpoints.{key} must contain '{{id}}' placeholder for job id "
                f"substitution; got {url!r}"
            )


def _check_inputs_for_job_type(
    job_type: JobType,
    manifest: ExternalContainerManifest,
) -> Iterable[_Issue]:
    inputs = manifest.spec.inputs

    # Heuristic checks driven by job_type. These intentionally stop short of
    # forcing partner-specific input shapes (params is the only universal
    # input — everything else is partner-driven).
    if job_type in ("train", "evaluate"):
        if inputs.dataset is None or not inputs.dataset.required:
            yield _Issue(
                f"spec.inputs.dataset.required=true is expected for job_type={job_type}"
            )

    if job_type == "infer":
        if inputs.base_model is None or not inputs.base_model.required:
            yield _Issue(
                "spec.inputs.base_model.required=true is expected for job_type=infer "
                "(inference needs a model to load)"
            )


def _check_capabilities(manifest: ExternalContainerManifest) -> Iterable[_Issue]:
    spec = manifest.spec
    caps = spec.capabilities

    if spec.execution_mode in ("sync", "async"):
        if caps.estimated_startup_seconds is None:
            yield _Issue(
                "spec.capabilities.estimated_startup_seconds is required for "
                f"execution_mode={spec.execution_mode} (used to size startupProbe)"
            )

    # GPU memory declaration should match resource request when both are present.
    if spec.resources.gpu_memory is None and spec.resources.gpu > 0:
        yield _Issue(
            "spec.resources.gpu_memory must be declared when resources.gpu > 0"
        )


def validate_manifest(manifest: ExternalContainerManifest) -> None:
    """Run all single-manifest cross-field checks.

    Raises:
        ManifestValidationError: with every collected issue (batched).
    """
    spec = manifest.spec
    issues: List[_Issue] = []
    issues.extend(_check_endpoints(spec.execution_mode, spec.endpoints))
    issues.extend(_check_inputs_for_job_type(spec.job_type, manifest))
    issues.extend(_check_capabilities(manifest))

    if issues:
        raise ManifestValidationError(
            manifest_name=manifest.metadata.name,
            errors=[i.message for i in issues],
        )


# ── Hybrid pair consistency (SP-1 v2 §1.1) ────────────────────────────────

# Job-type combinations recognised as a valid Hybrid pair. The first element
# of each tuple is the inference / serving role, the second is the workload
# launch role. Ordering is irrelevant when callers pass the pair.
_HYBRID_PAIRS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"infer", "train"}),
        frozenset({"infer", "evaluate"}),
        frozenset({"infer", "convert"}),
    }
)

_PAIRED_FIELDS: tuple[str, ...] = (
    "service_family",
    "contract_version",
    "model_artifact_format",
    "checkpoint_namespace",
)


def validate_hybrid_pair(
    a: ExternalContainerManifest,
    b: ExternalContainerManifest,
) -> None:
    """Run all Hybrid pair consistency checks across two manifests.

    Raises:
        HybridPairValidationError: with every collected issue (batched).
    """
    issues: List[str] = []
    pair = (a.metadata.name, b.metadata.name)

    if a.metadata.name == b.metadata.name:
        issues.append("paired manifests must have distinct metadata.name")

    # Each manifest must still pass its own validation. Surface upstream
    # caller errors by validating both before pair checks.
    for m in (a, b):
        try:
            validate_manifest(m)
        except ManifestValidationError as exc:
            issues.extend(f"{m.metadata.name}: {e}" for e in exc.errors)

    # Job-type combination must form a recognised Hybrid pair.
    combo = frozenset({a.spec.job_type, b.spec.job_type})
    if combo not in _HYBRID_PAIRS:
        issues.append(
            f"job_type pair {sorted(combo)} is not a recognised Hybrid combination "
            f"(allowed: {[sorted(p) for p in _HYBRID_PAIRS]})"
        )

    # All paired metadata fields must be defined and equal.
    for field in _PAIRED_FIELDS:
        va, vb = getattr(a.spec, field), getattr(b.spec, field)
        if va is None or vb is None:
            issues.append(
                f"spec.{field} is required on both manifests of a Hybrid pair "
                f"(got a={va!r}, b={vb!r})"
            )
            continue
        if va != vb:
            issues.append(
                f"spec.{field} mismatch between paired manifests: "
                f"{a.metadata.name}={va!r} vs {b.metadata.name}={vb!r}"
            )

    # Image identity: if either side declares a digest, both must, and they
    # must match. (Tag-only references are accepted with a soft warning that
    # surfaces as an issue only when the tags themselves differ.)
    if a.spec.image != b.spec.image:
        issues.append(
            f"spec.image mismatch between paired manifests: "
            f"{a.metadata.name}={a.spec.image!r} vs {b.metadata.name}={b.spec.image!r}"
        )

    da, db = a.spec.image_digest, b.spec.image_digest
    if (da is None) != (db is None):
        issues.append(
            "spec.image_digest must be declared on both manifests of a Hybrid pair "
            f"or neither (got a={da!r}, b={db!r})"
        )
    elif da is not None and da != db:
        issues.append(
            f"spec.image_digest mismatch between paired manifests: "
            f"{a.metadata.name}={da} vs {b.metadata.name}={db}"
        )

    if issues:
        raise HybridPairValidationError(pair=pair, errors=issues)
