"""Unit tests for the fine-tuning OOM cleanup helper in
apps/fb_monitoring/src/monitoring/monitoring_service.py.

The helper `_ensure_fine_tuning_pod_deleted` owns the "after OOM, make sure
the Pod is actually gone from the cluster" responsibility.
Contract:
  - Call delete_helm_resource(helm_name, workspace_id).
  - If it returns ok=True, return (True, "helm").
  - If it returns ok=False, log a warning, then fall back to **both**
    K8s delete_namespaced_pod **and** deletion of Helm release-metadata
    Secrets. Only report (True, "k8s-fallback") when both succeed;
    otherwise return (False, "all-failed") with an ERROR log. Deleting
    only the Pod without the Helm release Secrets would leave the
    release name blocked for re-use — see P2 in the plan.
  - Never raises — monitoring loop continues regardless.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def helper():
    """Import the helper lazily so tests fail clearly when it's not yet defined."""
    from monitoring import monitoring_service

    return monitoring_service._ensure_fine_tuning_pod_deleted


def test_helm_uninstall_success_returns_true_and_skips_k8s(helper):
    with patch("monitoring.monitoring_service._invoke_delete_helm_resource", return_value=(True, "ok")) as mock_helm, \
         patch("monitoring.monitoring_service._invoke_k8s_delete_pod") as mock_pod, \
         patch("monitoring.monitoring_service._invoke_k8s_delete_helm_release_secrets") as mock_secrets:
        ok, path = helper(
            pod_name="ft-pod-abc",
            helm_name="ft-release-1",
            workspace_id=42,
        )

    assert ok is True
    assert path == "helm"
    mock_helm.assert_called_once_with(helm_name="ft-release-1", workspace_id=42)
    mock_pod.assert_not_called()
    mock_secrets.assert_not_called()


def test_helm_uninstall_failure_triggers_full_k8s_fallback(helper):
    """Both Pod and Helm release-Secret deletions must happen and both must
    succeed for the orchestrator to report k8s-fallback success.
    """
    with patch("monitoring.monitoring_service._invoke_delete_helm_resource", return_value=(False, "context deadline exceeded")), \
         patch("monitoring.monitoring_service._invoke_k8s_delete_pod", return_value=(True, "deleted")) as mock_pod, \
         patch("monitoring.monitoring_service._invoke_k8s_delete_helm_release_secrets", return_value=(True, "helm-release-secrets-deleted")) as mock_secrets:
        ok, path = helper(
            pod_name="ft-pod-abc",
            helm_name="ft-release-1",
            workspace_id=42,
        )

    assert ok is True
    assert path == "k8s-fallback"
    mock_pod.assert_called_once_with(pod_name="ft-pod-abc", workspace_id=42)
    mock_secrets.assert_called_once_with(helm_name="ft-release-1", workspace_id=42)


def test_pod_deleted_but_helm_secrets_fail_reports_failure(helper, caplog):
    """Regression for Codex P2: if only the Pod is deleted but the Helm
    release Secrets remain, the next `helm install {same_name}` will hit
    'cannot re-use a name that is still in use' and the scheduler silently
    strands the model in `installing`. The orchestrator must NOT claim
    success in that case and must log at ERROR level with details.
    """
    import logging

    caplog.set_level(logging.ERROR)
    with patch("monitoring.monitoring_service._invoke_delete_helm_resource", return_value=(False, "timeout")), \
         patch("monitoring.monitoring_service._invoke_k8s_delete_pod", return_value=(True, "deleted")), \
         patch("monitoring.monitoring_service._invoke_k8s_delete_helm_release_secrets", return_value=(False, "Forbidden: secrets")):
        ok, path = helper(
            pod_name="ft-pod-abc",
            helm_name="ft-release-1",
            workspace_id=42,
        )

    assert ok is False
    assert path == "all-failed"
    # ERROR log must mention the pod name and the partial-failure nature.
    assert any(
        "ft-pod-abc" in rec.getMessage()
        and rec.levelno >= logging.ERROR
        and "silently fail" in rec.getMessage()
        for rec in caplog.records
    )


def test_both_paths_fail_returns_false_and_logs(helper, caplog):
    import logging

    caplog.set_level(logging.ERROR)
    with patch("monitoring.monitoring_service._invoke_delete_helm_resource", return_value=(False, "timeout")), \
         patch("monitoring.monitoring_service._invoke_k8s_delete_pod", side_effect=RuntimeError("api server 500")), \
         patch("monitoring.monitoring_service._invoke_k8s_delete_helm_release_secrets", side_effect=RuntimeError("api server 500")):
        ok, path = helper(
            pod_name="ft-pod-abc",
            helm_name="ft-release-1",
            workspace_id=42,
        )

    assert ok is False
    assert path == "all-failed"
    # helper must not raise; it must log at ERROR level.
    assert any(
        "ft-pod-abc" in rec.getMessage() and rec.levelno >= logging.ERROR
        for rec in caplog.records
    )


def test_helper_never_raises(helper):
    # Defensive: even if all three injected hooks raise, the helper swallows.
    with patch("monitoring.monitoring_service._invoke_delete_helm_resource", side_effect=ValueError("boom")), \
         patch("monitoring.monitoring_service._invoke_k8s_delete_pod", side_effect=ValueError("boom2")), \
         patch("monitoring.monitoring_service._invoke_k8s_delete_helm_release_secrets", side_effect=ValueError("boom3")):
        ok, path = helper(
            pod_name="ft-pod-abc",
            helm_name="ft-release-1",
            workspace_id=42,
        )

    assert ok is False
    assert path == "all-failed"


def test_k8s_config_is_lazy_not_loaded_at_import():
    """Regression: tests must be able to import the module without a live
    cluster. The config loader is gated by `_ensure_k8s_config_loaded`, not
    called at import time.
    """
    from monitoring import monitoring_service

    # The flag exists but hasn't been forced True purely from importing.
    assert hasattr(monitoring_service, "_K8S_CONFIG_LOADED")
    # We don't assert the value — if another test has already exercised the
    # fallback path, it may be True. Just prove the attribute is present and
    # the module imported clean.
