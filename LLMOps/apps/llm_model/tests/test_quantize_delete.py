"""Unit tests for quantize lineage deletion in apps/llm_model/src/model/service.py."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.asyncio

JOB = "56f194251fcb405baf1273f39a522f22"


def _row(status="completed", lineage_id=17):
    return {"id": lineage_id, "source_model_id": 38, "workspace_id": 2, "job_str_id": JOB,
            "quantization_type": "q4", "gguf_path": f"jobs/{JOB}/output/m.q4.gguf", "status": status}


@pytest.fixture
def pkg(tmp_path):
    """jobs/<JOB>/output 에 패키지 파일이 있는 실제 디렉터리."""
    out = tmp_path / "jobs" / JOB / "output"
    out.mkdir(parents=True)
    (out / "m.q4.gguf").write_bytes(b"gguf")
    (out / "run.sh").write_text("#!/bin/sh\n")
    return out


@pytest.fixture
def svc(pkg):
    from model import service

    with patch.object(service, "_quantize_output_dir", AsyncMock(return_value=str(pkg))), \
         patch.object(service.db_model, "get_quantize_lineage_by_job", AsyncMock(return_value=_row())), \
         patch.object(service.db_model, "delete_quantize_lineage", AsyncMock(return_value=True)), \
         patch.object(service.db_edge, "list_edge_workers_by_lineage", MagicMock(return_value=[])), \
         patch.object(service, "_convert_job_active", AsyncMock(return_value=False)):
        yield service


async def test_delete_removes_job_dir_then_row(svc, pkg):
    res = await svc.delete_quantize_lineage(model_id=38, job_id=JOB)

    assert res == {"job_id": JOB, "lineage_id": 17, "deleted": True}
    assert not os.path.exists(os.path.dirname(pkg))          # jobs/<JOB> 통째
    assert os.path.isdir(os.path.dirname(os.path.dirname(pkg)))  # jobs base 는 남는다
    svc.db_model.delete_quantize_lineage.assert_awaited_once_with(lineage_id=17, source_model_id=38)


async def test_delete_unknown_lineage_is_refused(svc, pkg):
    svc.db_model.get_quantize_lineage_by_job.return_value = None

    with pytest.raises(Exception, match="Error: 양자화 이력을 찾을 수 없습니다"):
        await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    assert pkg.is_dir()
    svc.db_model.delete_quantize_lineage.assert_not_awaited()


async def test_delete_running_job_still_active_is_refused(svc, pkg):
    svc.db_model.get_quantize_lineage_by_job.return_value = _row(status="running")
    svc._convert_job_active.return_value = True

    with pytest.raises(Exception, match="진행 중"):
        await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    assert pkg.is_dir()
    svc.db_model.delete_quantize_lineage.assert_not_awaited()


async def test_delete_stale_running_row_is_allowed(svc, pkg):
    # 완료는 lazy 마감이라 BFF 가 끝났다고 하면 running 행도 지울 수 있어야 한다.
    svc.db_model.get_quantize_lineage_by_job.return_value = _row(status="running")
    svc._convert_job_active.return_value = False

    await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    assert not pkg.exists()


@pytest.mark.parametrize("status", ["failed", "cancelled", "completed"])
async def test_row_status_is_not_trusted_bff_is_always_asked(svc, pkg, status):
    # lineage-status 로 진행 중 job 을 failed 로 바꿔 놓고 지우는 우회 차단(리뷰 3-way 합의).
    svc.db_model.get_quantize_lineage_by_job.return_value = _row(status=status)
    svc._convert_job_active.return_value = True

    with pytest.raises(Exception, match="진행 중"):
        await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    svc._convert_job_active.assert_awaited_once_with(JOB)
    assert pkg.is_dir()


async def test_bff_unreachable_blocks_delete_end_to_end(svc, pkg):
    svc._convert_job_active.side_effect = Exception("Error: 양자화 작업 상태를 확인할 수 없습니다")

    with pytest.raises(Exception, match="상태를 확인할 수 없습니다"):
        await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    assert pkg.is_dir()
    svc.db_model.delete_quantize_lineage.assert_not_awaited()


async def test_rm_failure_keeps_row_for_retry(svc, pkg):
    with patch.object(svc.common, "rm_rf", MagicMock(side_effect=PermissionError("busy"))):
        with pytest.raises(PermissionError):
            await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    svc.db_model.delete_quantize_lineage.assert_not_awaited()


@pytest.mark.parametrize("state", ["running", "deploying", "error"])
async def test_delete_refused_while_edge_worker_uses_lineage(svc, pkg, state):
    svc.db_edge.list_edge_workers_by_lineage.return_value = [
        {"id": 21, "name": "edge-test", "device_id": "edge-1", "deploy_state": state}]

    with pytest.raises(Exception, match=r"엣지 디바이스에 배포 중입니다\(edge-test\)"):
        await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    assert pkg.is_dir()
    svc.db_model.delete_quantize_lineage.assert_not_awaited()


async def test_delete_allowed_after_edge_worker_stopped(svc, pkg):
    # stop 은 deploy_lineage_id 를 남긴다 — 상태로 거른다.
    svc.db_edge.list_edge_workers_by_lineage.return_value = [
        {"id": 21, "name": "edge-test", "device_id": "edge-1", "deploy_state": "stopped"}]

    await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    assert not pkg.exists()


async def test_edge_lookup_failure_fails_closed(svc, pkg):
    svc.db_edge.list_edge_workers_by_lineage.side_effect = RuntimeError("db down")

    with pytest.raises(RuntimeError):
        await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    assert pkg.is_dir()
    svc.db_model.delete_quantize_lineage.assert_not_awaited()


async def test_missing_dir_still_deletes_row(svc, pkg):
    # 디렉터리를 먼저 지운 뒤 행 삭제가 실패했던 경우 — 재호출로 이어서 정리된다.
    import shutil
    shutil.rmtree(os.path.dirname(pkg))

    await svc.delete_quantize_lineage(model_id=38, job_id=JOB)
    svc.db_model.delete_quantize_lineage.assert_awaited_once()


async def test_symlinked_job_dir_escaping_base_is_refused(tmp_path):
    from model import service

    outside = tmp_path / "outside"
    (outside / "output").mkdir(parents=True)
    (outside / "keep.txt").write_text("keep")
    base = tmp_path / "local" / "ws" / "jobs"
    base.mkdir(parents=True)
    os.symlink(outside, base / JOB)

    with patch.object(service.PATH, "JF_MAIN_STORAGE_PATH", str(tmp_path / "{STORAGE_NAME}" / "{WORKSPACE_NAME}")), \
         patch.object(service.db_model, "get_model", AsyncMock(return_value={"workspace_id": 2})), \
         patch.object(service.db_model, "get_workspace_model",
                      AsyncMock(return_value={"main_storage_name": "local", "name": "ws"})), \
         patch.object(service.db_model, "get_quantize_lineage_by_job", AsyncMock(return_value=_row())), \
         patch.object(service.db_model, "delete_quantize_lineage", AsyncMock()) as del_row:
        with pytest.raises(ValueError):
            await service.delete_quantize_lineage(model_id=38, job_id=JOB)
    assert (outside / "keep.txt").exists()
    del_row.assert_not_awaited()


@pytest.mark.parametrize("bad", ["../x", "a/b", "", "a" * 129])
async def test_invalid_job_id_is_refused_before_db(bad):
    from model import service

    with patch.object(service.db_model, "get_quantize_lineage_by_job", AsyncMock()) as get_row:
        with pytest.raises(ValueError):
            await service.delete_quantize_lineage(model_id=38, job_id=bad)
    get_row.assert_not_awaited()


class _FakeHttp:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.mark.parametrize("payload,active", [
    ({"result": {"status": "running"}}, True),
    ({"result": {"status": "pending"}}, True),
    ({"result": None}, True),
    ({"result": {"status": "completed"}}, False),
    ({"result": {"status": "failed"}}, False),
    ({"result": {"status": "cancelled"}}, False),
])
async def test_convert_job_active_reads_bff_status(payload, active):
    from model import service
    from external import proxy

    with patch("httpx.AsyncClient", return_value=_FakeHttp()), \
         patch.object(proxy.ExternalContainerClient, "get_job", AsyncMock(return_value=payload)):
        assert await service._convert_job_active(JOB) is active


async def test_convert_job_unknown_to_bff_is_not_active():
    from model import service
    from external import proxy

    with patch("httpx.AsyncClient", return_value=_FakeHttp()), \
         patch.object(proxy.ExternalContainerClient, "get_job",
                      AsyncMock(side_effect=proxy.ExternalContainerError(404, "not found"))):
        assert await service._convert_job_active(JOB) is False


async def test_convert_job_status_unreachable_blocks_delete():
    from model import service
    from external import proxy

    with patch("httpx.AsyncClient", return_value=_FakeHttp()), \
         patch.object(proxy.ExternalContainerClient, "get_job",
                      AsyncMock(side_effect=proxy.ExternalContainerError(0, "unreachable"))):
        with pytest.raises(Exception, match="상태를 확인할 수 없습니다"):
            await service._convert_job_active(JOB)


async def test_delete_model_collects_quantize_dirs_before_cascade(tmp_path):
    from model import service

    job_dir = tmp_path / "jobs" / JOB
    (job_dir / "output").mkdir(parents=True)
    order = []
    redis = MagicMock()
    redis.hget = AsyncMock(return_value=None)

    async def _dirs(model_id):
        order.append("collect")
        return [str(job_dir)]

    async def _delete_row(model_id):
        order.append("db_delete")
        return True

    with patch.object(service.db_model, "get_model",
                      AsyncMock(return_value={"workspace_id": 2, "name": "m"})), \
         patch.object(service.db_model, "get_workspace_model",
                      AsyncMock(return_value={"main_storage_name": "local", "name": "ws"})), \
         patch.object(service, "get_redis_client_async", AsyncMock(return_value=redis)), \
         patch.object(service, "delete_helm_repo", AsyncMock(return_value=(True, ""))), \
         patch.object(service, "delete_secret", MagicMock()), \
         patch.object(service, "_quantize_job_dirs", _dirs), \
         patch.object(service.db_model, "delete_model", _delete_row), \
         patch.object(service, "delete_model_folder", AsyncMock(return_value=True)):
        assert await service.delete_model(model_id=38) is True

    assert order == ["collect", "db_delete"]
    assert not job_dir.exists()


async def test_delete_model_refused_before_any_side_effect_when_quantize_blocked():
    from model import service

    redis = MagicMock()
    redis.hget = AsyncMock(return_value=None)
    rows = [{"id": 17, "job_str_id": JOB}]

    with patch.object(service.db_model, "get_model",
                      AsyncMock(return_value={"workspace_id": 2, "name": "m"})), \
         patch.object(service.db_model, "get_workspace_model",
                      AsyncMock(return_value={"main_storage_name": "local", "name": "ws"})), \
         patch.object(service, "get_redis_client_async", AsyncMock(return_value=redis)), \
         patch.object(service.db_model, "list_quantize_lineage", AsyncMock(return_value=rows)), \
         patch.object(service, "_quantize_delete_blocker",
                      AsyncMock(return_value="엣지 디바이스에 배포 중입니다(edge-test). 배포를 중지한 뒤 삭제하세요")), \
         patch.object(service, "delete_helm_repo", AsyncMock()) as helm, \
         patch.object(service, "delete_secret", MagicMock()) as secret, \
         patch.object(service.db_model, "delete_model", AsyncMock()) as del_model, \
         patch.object(service, "delete_model_folder", AsyncMock()) as del_folder:
        with pytest.raises(Exception, match=r"^Error: .*edge-test"):
            await service.delete_model(model_id=38)

    helm.assert_not_awaited()
    secret.assert_not_called()
    del_model.assert_not_awaited()
    del_folder.assert_not_awaited()
