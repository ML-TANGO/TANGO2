"""Unit tests for scheduler.py::_fine_tuning_node_budget_guard."""
from unittest.mock import patch


def _budget(mem_free, cpu_mc_free=48_000, gpu_free=2, alloc_mem=134_734_434_304):
    from utils.kube import NodeBudget
    return NodeBudget(
        node_name="n1",
        memory_free_bytes=mem_free,
        cpu_free_millicores=cpu_mc_free,
        gpu_free=gpu_free,
        memory_allocatable_bytes=alloc_mem,
        memory_used_bytes=alloc_mem - mem_free,
        cpu_allocatable_millicores=48_000,
        cpu_used_millicores=48_000 - cpu_mc_free,
    )


def _pod_info(ram_gb=40.0, cpu_cores=19.0, gpu_count=1, pod_count=1,
              available_gpus=None, available_node=None):
    info = {
        "pod_type": "fine_tuning",
        "resource": {"cpu": cpu_cores, "ram": ram_gb},
        "gpu_count": gpu_count,
        "pod_count": pod_count,
    }
    if available_gpus is not None:
        info["available_gpus"] = available_gpus
    if available_node is not None:
        info["available_node"] = available_node
    return info


@patch("scheduler.scheduler.get_node_request_budget")
def test_single_gpu_pod_allows_when_budget_sufficient(mock_get):
    mock_get.return_value = _budget(mem_free=50_000_000_000)
    from scheduler.scheduler import _fine_tuning_node_budget_guard
    ok, _ = _fine_tuning_node_budget_guard(_pod_info(
        available_gpus=[{"node_name": "n1", "gpu_uuids": ["GPU-a"]}],
    ))
    assert ok


@patch("scheduler.scheduler.get_node_request_budget")
def test_single_gpu_pod_pends_when_memory_short(mock_get):
    # 남은 30 GB < 필요 40 GB
    mock_get.return_value = _budget(mem_free=30_000_000_000)
    from scheduler.scheduler import _fine_tuning_node_budget_guard
    ok, reason = _fine_tuning_node_budget_guard(_pod_info(
        available_gpus=[{"node_name": "n1", "gpu_uuids": ["GPU-a"]}],
    ))
    assert not ok
    assert "memory insufficient" in reason


@patch("scheduler.scheduler.get_node_request_budget")
def test_available_node_path(mock_get):
    mock_get.return_value = _budget(mem_free=50_000_000_000)
    from scheduler.scheduler import _fine_tuning_node_budget_guard
    ok, _ = _fine_tuning_node_budget_guard(_pod_info(
        gpu_count=0, available_node="n1",
    ))
    assert ok


@patch("scheduler.scheduler.get_node_request_budget")
def test_multi_node_all_must_pass(mock_get):
    # 2 pods, 20 GB each; n1 has plenty, n2 has only 19 GB → n2 fails
    def fake(node):
        return _budget(mem_free=(50_000_000_000 if node == "n1" else 19_000_000_000))
    mock_get.side_effect = fake
    from scheduler.scheduler import _fine_tuning_node_budget_guard
    ok, reason = _fine_tuning_node_budget_guard(_pod_info(
        ram_gb=40.0, pod_count=2,
        available_gpus=[
            {"node_name": "n1", "gpu_uuids": ["GPU-a"]},
            {"node_name": "n2", "gpu_uuids": ["GPU-b"]},
        ],
    ))
    assert not ok
    assert "n2" in reason


@patch("scheduler.scheduler.get_node_request_budget")
def test_gpu_shortage_blocks(mock_get):
    mock_get.return_value = _budget(mem_free=100_000_000_000, gpu_free=0)
    from scheduler.scheduler import _fine_tuning_node_budget_guard
    ok, _ = _fine_tuning_node_budget_guard(_pod_info(
        available_gpus=[{"node_name": "n1", "gpu_uuids": ["GPU-a"]}],
    ))
    assert not ok


@patch("scheduler.scheduler.get_node_request_budget")
def test_api_exception_returns_fail(mock_get):
    from kubernetes.client.rest import ApiException
    mock_get.side_effect = ApiException(status=403, reason="Forbidden")
    from scheduler.scheduler import _fine_tuning_node_budget_guard
    ok, reason = _fine_tuning_node_budget_guard(_pod_info(
        available_gpus=[{"node_name": "n1", "gpu_uuids": ["GPU-a"]}],
    ))
    assert not ok
    assert "ApiException" in reason


@patch("scheduler.scheduler.get_node_request_budget")
def test_no_node_info_bypasses_guard(mock_get):
    """NPU 등 특정 노드 pinning 없는 경로는 ok 반환(워크스페이스 쿼터만 신뢰)."""
    from scheduler.scheduler import _fine_tuning_node_budget_guard
    ok, reason = _fine_tuning_node_budget_guard(_pod_info())  # no available_gpus, no available_node
    assert ok
    assert "no specific node binding" in reason
    mock_get.assert_not_called()


@patch("scheduler.scheduler.get_node_request_budget")
def test_missing_node_name_in_gpus_returns_fail(mock_get):
    from scheduler.scheduler import _fine_tuning_node_budget_guard
    ok, reason = _fine_tuning_node_budget_guard(_pod_info(
        available_gpus=[{"gpu_uuids": ["GPU-a"]}],  # node_name 누락
    ))
    assert not ok
    assert "missing node_name" in reason
    mock_get.assert_not_called()
