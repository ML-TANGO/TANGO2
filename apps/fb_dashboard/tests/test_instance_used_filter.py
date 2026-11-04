"""Regression tests for the fine-tuning error-status filter used by
get_workspace_instance_used in apps/fb_dashboard/src/dashboard/service.py.

Scenario: after an OOMKilled fine-tuning Pod, the monitoring service writes
status="error" into Redis WORKSPACE_PODS_STATUS. The workspace dashboard graph
must exclude those pods from resource summation, matching the (already zero)
usage percentage computed from K8s ResourceQuota.
"""
from __future__ import annotations

import pytest


def test_error_status_pod_does_not_claim_resources():
    from dashboard.service import _fine_tuning_pod_claims_resources

    assert _fine_tuning_pod_claims_resources("error") is False


def test_running_status_pod_claims_resources():
    from dashboard.service import _fine_tuning_pod_claims_resources

    assert _fine_tuning_pod_claims_resources("running") is True


def test_installing_status_pod_claims_resources():
    from dashboard.service import _fine_tuning_pod_claims_resources

    assert _fine_tuning_pod_claims_resources("installing") is True


@pytest.mark.parametrize(
    "status",
    ["stop", "pending", "done", "scheduling", "expired", "reserved"],
)
def test_not_running_statuses_do_not_claim_resources(status):
    from dashboard.service import _fine_tuning_pod_claims_resources

    assert _fine_tuning_pod_claims_resources(status) is False
