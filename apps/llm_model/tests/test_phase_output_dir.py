"""Unit tests for SDS recipe phase output resolution in apps/llm_model/src/external/route.py.

모델은 job 이 끝난 뒤에도 external_job_id 를 유지한다. 취소·실패한 재실행의 잡 폴더가
같은 phase 의 완료 커밋을 가리지 않는지, 그러면서도 실행 중·커밋 전 산출물은 잃지 않는지 본다.
"""
from __future__ import annotations

import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.asyncio

JOB = "7e4ab06615c24d30ae413f9f5aad595a"
COMMIT = "lora_sds-20261005-163204"


def _age(path, seconds):
    """파일·폴더 mtime 을 seconds 만큼 과거로 — 오래전에 멈춘 잡 폴더를 흉내 낸다."""
    t = time.time() - seconds
    os.utime(path, (t, t))


@pytest.fixture
def storage(tmp_path):
    """잡 폴더(짧은 재실행 로그)와 같은 phase 의 완료 커밋이 함께 있는 워크스페이스."""
    main = tmp_path / "local" / "main" / "SDS"
    job_dir = main / "jobs" / JOB / "output" / "lora_sds"
    job_dir.mkdir(parents=True)
    (job_dir / "train.log").write_text("0%| 189/45000\n")
    commit_root = main / "models" / "ETRI-SDS-VLM" / "commit_models"
    commit_dir = commit_root / COMMIT
    commit_dir.mkdir(parents=True)
    (commit_dir / "train.log").write_text("[Train] Done.\n")
    return {"root": tmp_path, "job_dir": job_dir, "commit_dir": commit_dir,
            "commit_root": commit_root}


@pytest.fixture
def route(storage):
    from external import route as external_route
    from utils import PATH

    client = MagicMock()
    client.get_job = AsyncMock(return_value={"result": {"status": "running"}})
    model_row = {"id": 38, "workspace_id": 2, "name": "ETRI-SDS-VLM", "external_job_id": JOB}
    main_path = str(storage["root"]) + "/{STORAGE_NAME}/main/{WORKSPACE_NAME}"

    external_route._job_state_cache.clear()
    with patch("utils.llm_db.db_base_async.select_query", AsyncMock(return_value=[model_row])), \
         patch("utils.llm_db.db_model.get_workspace_model",
               AsyncMock(return_value={"main_storage_name": "local", "name": "SDS"})), \
         patch.object(PATH, "JF_MAIN_STORAGE_PATH", main_path), \
         patch.object(external_route, "_get_client", AsyncMock(return_value=client)):
        external_route._test_client = client
        yield external_route
    external_route._job_state_cache.clear()


@pytest.mark.parametrize("status", ["cancelled", "failed"])
async def test_cancelled_or_failed_rerun_shows_phase_commit(route, storage, status):
    route._test_client.get_job.return_value = {"result": {"status": status}}

    out = await route._resolve_phase_output_dir(38, "lora_sds")

    assert out == str(storage["commit_dir"])


@pytest.mark.parametrize("status", ["cancelled", "failed"])
async def test_ended_first_run_without_commit_keeps_job_output(route, storage, status):
    # 첫 실행이 끝난 phase — 커밋이 없으니 잡 폴더가 유일한 산출물이다(빈 화면이면 안 된다).
    route._test_client.get_job.return_value = {"result": {"status": status}}
    os.rename(storage["commit_dir"], storage["commit_root"] / "other-20261005-163204")

    out = await route._resolve_phase_output_dir(38, "lora_sds")

    assert out == str(storage["job_dir"])


async def test_completed_job_before_auto_commit_keeps_job_output(route, storage):
    # 자동 커밋은 완료 상태가 된 뒤에 돈다 — 그 사이에 옛 커밋으로 바뀌어 보이면 안 된다.
    route._test_client.get_job.return_value = {"result": {"status": "completed"}}

    out = await route._resolve_phase_output_dir(38, "lora_sds")

    assert out == str(storage["job_dir"])


@pytest.mark.parametrize("result", [{"status": "running"}, {"status": "pending"}, None])
async def test_live_job_keeps_job_output_dir(route, storage, result):
    route._test_client.get_job.return_value = {"result": result}

    out = await route._resolve_phase_output_dir(38, "lora_sds")

    assert out == str(storage["job_dir"])


async def test_job_forgotten_by_tracker_falls_back_to_commit(route, storage):
    route._test_client.get_job.side_effect = route.ExternalContainerError(404, "not found")
    _age(storage["job_dir"] / "train.log", 3600)
    _age(storage["job_dir"], 3600)

    out = await route._resolve_phase_output_dir(38, "lora_sds")

    assert out == str(storage["commit_dir"])


async def test_tracker_404_with_fresh_writes_keeps_job_output(route, storage):
    # in-memory 레지스트리로 버티는 동안 도는 job 도 404 가 난다 — 로그가 방금 쓰였으면 도는 것.
    route._test_client.get_job.side_effect = route.ExternalContainerError(404, "not found")

    out = await route._resolve_phase_output_dir(38, "lora_sds")

    assert out == str(storage["job_dir"])


@pytest.mark.parametrize("error", [Exception("x"), ValueError("not json")])
async def test_unexpected_lookup_error_keeps_job_output(route, storage, error):
    route._test_client.get_job.side_effect = error

    out = await route._resolve_phase_output_dir(38, "lora_sds")

    assert out == str(storage["job_dir"])


async def test_tracker_unreachable_keeps_job_output_dir(route, storage):
    route._test_client.get_job.side_effect = route.ExternalContainerError(0, "unreachable")

    out = await route._resolve_phase_output_dir(38, "lora_sds")

    assert out == str(storage["job_dir"])


async def test_job_state_lookup_is_reused_within_ttl(route, storage):
    route._test_client.get_job.return_value = {"result": {"status": "cancelled"}}

    await route._resolve_phase_output_dir(38, "lora_sds")
    await route._resolve_phase_output_dir(38, "lora_sds")

    assert route._test_client.get_job.await_count == 1


async def test_other_phase_without_job_dir_skips_tracker_lookup(route, storage):
    out = await route._resolve_phase_output_dir(38, "lora")

    assert out is None
    route._test_client.get_job.assert_not_awaited()


async def test_phase_system_log_reads_commit_log_after_cancel(route, storage):
    route._test_client.get_job.return_value = {"result": {"status": "cancelled"}}

    res = await route.get_phase_system_log(38, "lora_sds")
    log = json.loads(res.body)["result"]

    assert "[Train] Done." in log
    assert "189/45000" not in log
