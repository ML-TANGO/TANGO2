"""Unit tests for apps/fb_utils/kube.py::get_node_request_budget."""
from unittest.mock import MagicMock, patch

import pytest


def _node_obj(allocatable_mem="131576596Ki", allocatable_cpu="48", allocatable_gpu="2"):
    node = MagicMock()
    node.status.allocatable = {
        "memory": allocatable_mem,
        "cpu": allocatable_cpu,
        "nvidia.com/gpu": allocatable_gpu,
    }
    return node


def _pod(ns, name, phase, node_name, mem, cpu, gpu=0):
    p = MagicMock()
    p.metadata.namespace = ns
    p.metadata.name = name
    p.status.phase = phase
    p.spec.node_name = node_name
    container = MagicMock()
    container.resources.requests = {"memory": mem, "cpu": cpu}
    if gpu:
        container.resources.requests["nvidia.com/gpu"] = str(gpu)
    p.spec.containers = [container]
    return p


@patch("utils.kube.client.CoreV1Api")
def test_free_budget_basic(mock_api_cls):
    api = mock_api_cls.return_value
    api.read_node.return_value = _node_obj()
    api.list_pod_for_all_namespaces.return_value.items = [
        _pod("a", "p1", "Running", "n1", "40G", "19"),
        _pod("b", "p2", "Running", "n1", "8Gi", "2"),
        _pod("c", "p3", "Succeeded", "n1", "100Gi", "40"),   # 완료된 건 제외
        _pod("d", "p4", "Running", "other-node", "1000Gi", "30"),  # 다른 노드 제외
    ]
    from utils.kube import get_node_request_budget
    b = get_node_request_budget("n1")
    # used: 40G=40,000,000,000 + 8Gi=8,589,934,592 = 48,589,934,592
    # alloc: 131,576,596 * 1024 = 134,734,434,304
    assert b.memory_free_bytes == 134_734_434_304 - 48_589_934_592
    assert b.cpu_free_millicores == 48_000 - 21_000
    assert b.gpu_free == 2


@patch("utils.kube.client.CoreV1Api")
def test_pending_pod_counted(mock_api_cls):
    """kubelet이 admit한 뒤 Pending 상태도 노드 예산을 차지한다."""
    api = mock_api_cls.return_value
    api.read_node.return_value = _node_obj()
    api.list_pod_for_all_namespaces.return_value.items = [
        _pod("a", "p1", "Pending", "n1", "40G", "19"),
    ]
    from utils.kube import get_node_request_budget
    b = get_node_request_budget("n1")
    assert b.memory_free_bytes == 134_734_434_304 - 40_000_000_000


@patch("utils.kube.client.CoreV1Api")
def test_missing_requests_treated_as_zero(mock_api_cls):
    api = mock_api_cls.return_value
    api.read_node.return_value = _node_obj()
    p = MagicMock()
    p.metadata.namespace = "a"; p.metadata.name = "p1"
    p.status.phase = "Running"; p.spec.node_name = "n1"
    c = MagicMock(); c.resources.requests = None
    p.spec.containers = [c]
    api.list_pod_for_all_namespaces.return_value.items = [p]
    from utils.kube import get_node_request_budget
    b = get_node_request_budget("n1")
    assert b.memory_free_bytes == 134_734_434_304
    assert b.cpu_free_millicores == 48_000


@patch("utils.kube.client.CoreV1Api")
def test_api_exception_propagates(mock_api_cls):
    from kubernetes.client.rest import ApiException
    api = mock_api_cls.return_value
    api.read_node.side_effect = ApiException(status=403, reason="Forbidden")
    from utils.kube import get_node_request_budget
    with pytest.raises(ApiException):
        get_node_request_budget("n1")
