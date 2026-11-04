"""Unit tests for stop fine-tuning flow in apps/llm_model/src/model/service.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_subprocess_shell():
    """Patch asyncio.create_subprocess_shell used by service.delete_helm_repo."""
    with patch("model.service.asyncio.create_subprocess_shell") as m:
        yield m


def _make_process(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


async def test_delete_helm_repo_success(mock_subprocess_shell):
    from model import service

    mock_subprocess_shell.return_value = _make_process(
        returncode=0, stdout=b"release uninstalled", stderr=b""
    )

    ok, msg = await service.delete_helm_repo(helm_repo_name="ft-1", workspace_id=10)

    assert ok is True
    assert "uninstalled" in msg
    invoked_cmd = mock_subprocess_shell.call_args.args[0]
    assert "--wait" in invoked_cmd
    assert "--timeout 90s" in invoked_cmd
    assert "helm uninstall ft-1" in invoked_cmd


async def test_delete_helm_repo_not_found_is_success(mock_subprocess_shell):
    from model import service

    mock_subprocess_shell.return_value = _make_process(
        returncode=1, stdout=b"", stderr=b"Error: uninstall: Release not found: ft-1"
    )

    ok, msg = await service.delete_helm_repo(helm_repo_name="ft-1", workspace_id=10)

    assert ok is True
    assert msg == "release already absent"


async def test_delete_helm_repo_failure_returns_false(mock_subprocess_shell):
    from model import service

    mock_subprocess_shell.return_value = _make_process(
        returncode=1, stdout=b"", stderr=b"Error: context deadline exceeded"
    )

    ok, msg = await service.delete_helm_repo(helm_repo_name="ft-1", workspace_id=10)

    assert ok is False
    assert "context deadline exceeded" in msg


async def test_delete_helm_repo_does_not_misclassify_cannot_reuse(mock_subprocess_shell):
    """Regression: 'cannot re-use a name' is an install error, not an uninstall success."""
    from model import service

    mock_subprocess_shell.return_value = _make_process(
        returncode=1,
        stdout=b"",
        stderr=b"Error: cannot re-use a name that is still in use",
    )

    ok, msg = await service.delete_helm_repo(helm_repo_name="ft-1", workspace_id=10)

    assert ok is False


async def test_delete_helm_repo_exception_returns_false(mock_subprocess_shell):
    from model import service

    mock_subprocess_shell.side_effect = OSError("helm: command not found")

    ok, msg = await service.delete_helm_repo(helm_repo_name="ft-1", workspace_id=10)

    assert ok is False
    assert "helm: command not found" in msg


async def test_uninstall_with_retry_success_on_first_attempt(mocker):
    from model import service

    delete_mock = mocker.patch(
        "model.service.delete_helm_repo",
        new=AsyncMock(side_effect=[(True, "ok")]),
    )

    ok, msg = await service._uninstall_fine_tuning_with_retry(
        repo="ft-1", workspace_id=10
    )

    assert ok is True
    assert msg == "ok"
    assert delete_mock.await_count == 1


async def test_uninstall_with_retry_recovers_on_second_attempt(mocker):
    from model import service

    sleep_mock = mocker.patch("model.service.asyncio.sleep", new=AsyncMock())
    delete_mock = mocker.patch(
        "model.service.delete_helm_repo",
        new=AsyncMock(side_effect=[(False, "transient"), (True, "ok")]),
    )

    ok, msg = await service._uninstall_fine_tuning_with_retry(
        repo="ft-1", workspace_id=10, max_attempts=2, retry_delay_s=3.0
    )

    assert ok is True
    assert msg == "ok"
    assert delete_mock.await_count == 2
    sleep_mock.assert_awaited_once_with(3.0)


async def test_uninstall_with_retry_gives_up_after_all_attempts(mocker):
    from model import service

    mocker.patch("model.service.asyncio.sleep", new=AsyncMock())
    delete_mock = mocker.patch(
        "model.service.delete_helm_repo",
        new=AsyncMock(
            side_effect=[(False, "first fail"), (False, "second fail")]
        ),
    )

    ok, msg = await service._uninstall_fine_tuning_with_retry(
        repo="ft-1", workspace_id=10, max_attempts=2, retry_delay_s=3.0
    )

    assert ok is False
    assert msg == "second fail"
    assert delete_mock.await_count == 2


async def test_uninstall_with_retry_single_attempt(mocker):
    """Verify max_attempts=1 does not sleep and fails immediately."""
    from model import service

    sleep_mock = mocker.patch("model.service.asyncio.sleep", new=AsyncMock())
    delete_mock = mocker.patch(
        "model.service.delete_helm_repo",
        new=AsyncMock(return_value=(False, "failed")),
    )

    ok, msg = await service._uninstall_fine_tuning_with_retry(
        repo="ft-1", workspace_id=10, max_attempts=1
    )

    assert ok is False
    assert msg == "failed"
    assert delete_mock.await_count == 1
    sleep_mock.assert_not_awaited()


@pytest.fixture
def stop_flow_mocks(mocker):
    """Patch every collaborator of stop_fine_tuning with AsyncMocks.

    Returns a SimpleNamespace with attributes matching the patched names so
    each test can adjust side effects directly.
    """
    from types import SimpleNamespace

    ns = SimpleNamespace(
        get_model=mocker.patch(
            "model.service.db_model.get_model",
            new=AsyncMock(
                return_value={
                    "workspace_id": 10,
                    "name": "m1",
                    "latest_commit_id": 7,
                }
            ),
        ),
        get_workspace_model=mocker.patch(
            "model.service.db_model.get_workspace_model",
            new=AsyncMock(
                return_value={"main_storage_name": "s1", "name": "w1"}
            ),
        ),
        uninstall=mocker.patch(
            "model.service._uninstall_fine_tuning_with_retry",
            new=AsyncMock(return_value=(True, "ok")),
        ),
        update_ft_status=mocker.patch(
            "model.service.db_model.update_model_fine_tuning_status",
            new=AsyncMock(return_value=True),
        ),
        update_commit_status=mocker.patch(
            "model.service.db_model.update_model_commit_status",
            new=AsyncMock(return_value=True),
        ),
        move_chkpt=mocker.patch(
            "model.service.move_checkpoint_files_to_parent",
            new=AsyncMock(return_value=True),
        ),
        load_or_stop=mocker.patch(
            "model.service.load_or_stop_helm",
            new=AsyncMock(return_value=(True, "ok")),
        ),
    )
    return ns


def _status_calls(mock_async_call) -> list[str]:
    """Extract the `status` kwarg from every invocation of update_model_fine_tuning_status."""
    return [call.kwargs["status"] for call in mock_async_call.await_args_list]


async def test_stop_happy_path_defers_stop_status_until_after_commit_job(
    stop_flow_mocks,
):
    """latest_fine_tuning_status=STOP은 commit_status=RUNNING 이후에 기록되어야 함."""
    from model import service
    from fb_utils import TYPE

    result = await service.stop_fine_tuning(model_id=1)

    assert result == (True, "success")

    # update_model_fine_tuning_status가 정확히 한 번 호출되고 그 값이 STOP
    assert stop_flow_mocks.update_ft_status.await_count == 1
    assert (
        stop_flow_mocks.update_ft_status.await_args.kwargs["status"]
        == TYPE.KUBE_POD_STATUS_STOP
    )

    assert stop_flow_mocks.update_commit_status.await_count == 1
    commit_status_kwargs = stop_flow_mocks.update_commit_status.await_args.kwargs
    assert commit_status_kwargs["commit_status"] == TYPE.KUBE_POD_STATUS_RUNNING
    assert commit_status_kwargs["commit_type"] == TYPE.COMMIT_TYPE_STOP


async def test_stop_uninstall_failure_records_error(stop_flow_mocks):
    from model import service
    from fb_utils import TYPE

    stop_flow_mocks.uninstall.return_value = (False, "timeout")

    ok, msg = await service.stop_fine_tuning(model_id=1)

    assert ok is False
    assert "helm uninstall failed" in msg
    assert "timeout" in msg

    # 정확히 ERROR만 기록 (STOP 기록 금지)
    statuses = _status_calls(stop_flow_mocks.update_ft_status)
    assert statuses == [TYPE.KUBE_POD_STATUS_ERROR]

    # commit_status 업데이트는 호출되지 않아야 함
    stop_flow_mocks.update_commit_status.assert_not_awaited()

    # 체크포인트/후처리도 호출되지 않아야 함
    stop_flow_mocks.move_chkpt.assert_not_awaited()
    stop_flow_mocks.load_or_stop.assert_not_awaited()


async def test_stop_without_checkpoint_releases_guard_via_stop(stop_flow_mocks):
    from model import service
    from fb_utils import TYPE

    stop_flow_mocks.move_chkpt.return_value = False

    ok, msg = await service.stop_fine_tuning(model_id=1)

    assert ok is False
    assert msg == "not exist checkpoint"

    # 이 경로는 STOP으로 가드 해제 (commit job 없으므로 race 없음)
    statuses = _status_calls(stop_flow_mocks.update_ft_status)
    assert statuses == [TYPE.KUBE_POD_STATUS_STOP]

    # commit_status는 건드리지 않음
    stop_flow_mocks.update_commit_status.assert_not_awaited()

    # load_or_stop_helm도 호출되지 않음
    stop_flow_mocks.load_or_stop.assert_not_awaited()


async def test_stop_load_or_stop_failure_records_error(stop_flow_mocks):
    from model import service
    from fb_utils import TYPE

    stop_flow_mocks.load_or_stop.return_value = (False, "helm install failed")

    ok, msg = await service.stop_fine_tuning(model_id=1)

    assert ok is False
    assert msg == "helm install failed"

    # 가드 해제를 위해 ERROR 기록 (STOP 기록 금지)
    statuses = _status_calls(stop_flow_mocks.update_ft_status)
    assert statuses == [TYPE.KUBE_POD_STATUS_ERROR]

    # commit_status도 RUNNING으로 올라가면 안됨 (commit job 실패했으므로)
    stop_flow_mocks.update_commit_status.assert_not_awaited()


async def test_stop_happy_path_commit_status_updated_before_ft_status(mocker):
    """commit_status=RUNNING이 fine_tuning_status=STOP보다 먼저 호출되어야 두 업데이트 사이 어느 시점에도 최소 하나의 가드가 재실행을 차단한다."""
    from model import service
    from fb_utils import TYPE

    call_order: list[str] = []

    async def track_ft_status(**kwargs):
        call_order.append(f"ft_status={kwargs['status']}")
        return True

    async def track_commit_status(**kwargs):
        call_order.append(f"commit_status={kwargs['commit_status']}")
        return True

    mocker.patch(
        "model.service.db_model.get_model",
        new=AsyncMock(
            return_value={"workspace_id": 10, "name": "m1", "latest_commit_id": 7}
        ),
    )
    mocker.patch(
        "model.service.db_model.get_workspace_model",
        new=AsyncMock(return_value={"main_storage_name": "s1", "name": "w1"}),
    )
    mocker.patch(
        "model.service._uninstall_fine_tuning_with_retry",
        new=AsyncMock(return_value=(True, "ok")),
    )
    mocker.patch(
        "model.service.move_checkpoint_files_to_parent",
        new=AsyncMock(return_value=True),
    )
    mocker.patch(
        "model.service.load_or_stop_helm",
        new=AsyncMock(return_value=(True, "ok")),
    )
    mocker.patch(
        "model.service.db_model.update_model_fine_tuning_status",
        new=AsyncMock(side_effect=track_ft_status),
    )
    mocker.patch(
        "model.service.db_model.update_model_commit_status",
        new=AsyncMock(side_effect=track_commit_status),
    )

    ok, _ = await service.stop_fine_tuning(model_id=1)

    assert ok is True
    assert call_order == [
        f"commit_status={TYPE.KUBE_POD_STATUS_RUNNING}",
        f"ft_status={TYPE.KUBE_POD_STATUS_STOP}",
    ], f"update 순서가 잘못됨: {call_order}"
