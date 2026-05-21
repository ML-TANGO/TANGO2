"""External container helm-install trigger.

Forks the `apps/fb_scheduler/src/scheduler/llm_run.py` pattern
(`create_fine_tuning_pod`) for partner-supplied images that conform to
docs/external-container-spec.md (SP-1 v2).

Why a values file instead of `--set` flags:
SP-Ext review (2026-05-19, codex CRITICAL #C1) flagged that building
`helm install ... --set env.{key}={val}` from partner-controlled dict
keys allows Helm strvals injection — a malicious manifest could splice
in extra `--set securityContext.runAsUser=0` via a comma in a key.
Dumping ExternalPodInfo as a YAML values file and passing it with
`-f` eliminates the entire class: every value lands in a pre-parsed
nested map, never on the shell command line.

Companion uninstall lives in `helm_run.py` as `delete_helm_external`.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from typing import Tuple

import yaml

from scheduler.dto import ExternalPodInfo

logger = logging.getLogger(__name__)

# Where the chart lives inside the fb_scheduler image. fb_scheduler runs in
# /app and bundles all helm charts under /app/helm_chart/<chart_name>/. This
# matches `llm_run.create_fine_tuning_pod` and `helm_run.create_project_tool_pod`.
_HELM_CHART_ROOT = "/app/helm_chart"
_HELM_CHART_NAME = "external_container"

# Keys whose values we never print at INFO/DEBUG. Any logging of the helm
# command itself goes through `_redact_command_for_log` to keep secrets out
# of kubectl-visible stderr (SP-Ext review MEDIUM #C5).
_SENSITIVE_TOP_LEVEL_KEYS: frozenset[str] = frozenset({"secrets", "env", "jf_env"})


def create_external_pod(pod_info: ExternalPodInfo) -> Tuple[bool, str]:
    """Run `helm install` for the external container described by pod_info.

    Returns:
        (True, stdout) on success or when the release name is already in use
        (idempotent re-launch). (False, stderr) on real failure.

    Side-effects:
        Writes a values YAML file (perm 600) under /tmp and removes it in
        the `finally` block. ConfigMap rendering happens inside helm during
        template expansion, so the file is only needed for the install call.
    """
    values_file = _write_values_file(pod_info)
    command: list[str] = []
    try:
        os.chdir(_HELM_CHART_ROOT)
        command = [
            "helm", "install",
            pod_info.helm_release,
            f"{_HELM_CHART_NAME}/",
            "-n", pod_info.namespace,
            "-f", values_file,
        ]
        logger.info(
            "helm install %s -n %s -f <values redacted, %d keys>",
            pod_info.helm_release, pod_info.namespace,
            len(pod_info.model_dump(exclude={"secrets", "env", "jf_env"})),
        )
        result = subprocess.run(
            command,
            shell=False,                      # no shell — argv list only
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = (e.stderr or "").strip()
        # Idempotency: a duplicate release name means a prior launch already
        # placed the pod. Same convention as create_fine_tuning_pod.
        if "cannot re-use a name that is still in use" in err_msg:
            return True, ""
        # Log without secrets — the values file path goes to the log; the
        # contents do not. tempfile perms are 0600 so on-disk inspection is
        # limited to the scheduler container's own UID.
        logger.error(
            "helm install failed for %s in %s: %s",
            pod_info.helm_release, pod_info.namespace, err_msg,
        )
        return False, err_msg
    finally:
        if values_file and os.path.exists(values_file):
            try:
                os.remove(values_file)
            except OSError as cleanup_exc:
                logger.warning(
                    "failed to remove helm values tempfile %s: %s",
                    values_file, cleanup_exc,
                )


# ── Helpers ──────────────────────────────────────────────────────────────


def _write_values_file(pod_info: ExternalPodInfo) -> str:
    """Persist ExternalPodInfo to a tmp YAML for `helm install -f`.

    Validating params_json here surfaces partner-side `/input/params.json`
    typos at helm-install time rather than once the container starts and
    crashes mid-read.

    `tempfile.mkstemp` defaults to mode 0600, which is what we want for
    a file that may carry partner-supplied secret env values.
    """
    data = _model_dump(pod_info)

    raw_params = (data.get("inputs") or {}).get("params_json") or "{}"
    try:
        json.loads(raw_params)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"inputs.params_json is not valid JSON for helm release "
            f"{pod_info.helm_release}: {exc}"
        ) from exc

    fd, path = tempfile.mkstemp(
        prefix=f"{pod_info.helm_release}-values-",
        suffix=".yaml",
    )
    with os.fdopen(fd, "w") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, default_flow_style=False)
    return path


def _model_dump(pod_info: ExternalPodInfo) -> dict:
    """Pydantic v2 model_dump with v1 fallback.

    fb_scheduler currently mixes v1 (`class Config`) and v2 (`ConfigDict`)
    syntax in dto.py; ExternalPodInfo is plain BaseModel so both `dict()`
    and `model_dump()` work. Prefer v2 to silence pydantic deprecation
    warnings (SP-Ext review HIGH #L3).
    """
    if hasattr(pod_info, "model_dump"):
        return pod_info.model_dump()
    return pod_info.dict()  # pydantic v1 fallback


def _redact_command_for_log(cmd: list[str]) -> str:
    """Render an argv command for logs, eliding the values file path."""
    parts: list[str] = []
    skip_next = False
    for token in cmd:
        if skip_next:
            parts.append("<values-file>")
            skip_next = False
            continue
        if token == "-f":
            parts.append(token)
            skip_next = True
            continue
        parts.append(token)
    return " ".join(parts)
