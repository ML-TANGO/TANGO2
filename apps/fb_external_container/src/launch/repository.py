"""SP-Ext.3: Persistent state for external jobs.

BFF (fb_external_container) restart 시 JobTracker 의 in-memory ``self._jobs``
가 휘발되는 문제를 해결하기 위한 영구 저장소. Active job (PENDING/RUNNING) 은
``list_active`` 로 복구되고, terminal 상태 (COMPLETED/FAILED/CANCELLED) 는
**row 를 지우지 않고 status 만 갱신**해 tombstone 으로 남긴다 — 그래야 재시작
후 조회가 404 (= 존재한 적 없음) 대신 그 터미널 상태를 반환해 호출자가 폴링을
멈춘다. tombstone 은 ``prune_terminal`` 이 startup 때 보존기간 지난 것만 정리.

테이블: ``external_job_state`` (DB = ``JF_DB_NAME``, 운영 기준 ``msa_jfb``) —
schema 는 ``apps/fb_external_container/migrations/002_external_job_state.sql``.

호출 규약:
- Repository 는 pool 만 받음 (lifespan-owned). 새 connection 만들지 않음.
- 모든 method 는 async. autocommit=False 라 명시적으로 commit.
- DB 실패는 caller 가 알아채야 하므로 예외를 raise (조용히 삼키지 않음).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


_TABLE = "external_job_state"

# ExternalContainerStatus(str, Enum) 의 terminal value 들 (normalize/status.py 의
# _TERMINAL_STATES 와 동일 집합). repository 는 normalize 를 import 하지 않는
# 규약(raw JSON/문자열만 다룸)이라 SQL 리터럴로 둔다 — enum 에 terminal 값이
# 추가되면 여기도 같이 고쳐야 한다.
_TERMINAL_STATUS_SQL = "'completed', 'failed', 'cancelled'"

# Terminal tombstone 보존기간. 재시작 후에도 "이 job 은 이렇게 끝났다"를 답할 수
# 있어야 호출자가 폴링을 멈추는데, 영구 보존은 테이블(manifest_json LONGTEXT)을
# 무한 성장시킨다. 운영상 며칠이면 모든 소비자가 종료를 관측하고 자기 상태를
# 확정하므로 1주로 자른다.
_TOMBSTONE_RETENTION_DAYS = 7


# ── Snapshot DTO ──────────────────────────────────────────────────────────


class JobStateSnapshot:
    """Plain holder for a single row read from external_job_state.

    JobTracker 의 startup_recovery 가 이걸 받아서 JobRecord 를 재구성한다.
    dataclass 안 쓴 이유: lifecycle.py 와의 순환 import 회피용 (lifecycle 이
    ExternalContainerManifest 를 가지고 있고, repository 는 raw JSON 만 다룸).
    """

    __slots__ = (
        "job_id",
        "model_id",
        "workspace_id",
        "manifest_name",
        "manifest_version",
        "manifest_json",
        "namespace",
        "pod_name",
        "helm_release",
        "service_url",
        "timeout_seconds",
        "params_json",
        "partner_job_id",
        "status",
        "output_subdir",
        "effective_gpu",
        "started_at",
    )

    def __init__(self, **kwargs: Any) -> None:
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))

    @property
    def manifest_dict(self) -> dict[str, Any]:
        return json.loads(self.manifest_json) if self.manifest_json else {}

    @property
    def params_dict(self) -> dict[str, Any]:
        return json.loads(self.params_json) if self.params_json else {}


# ── Repository ────────────────────────────────────────────────────────────


class JobStateRepository:
    """aiomysql-backed persistence for active external jobs.

    Pool is owned by the FastAPI lifespan; we only acquire connections.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def insert(
        self,
        *,
        job_id: str,
        model_id: Optional[int],
        workspace_id: int,
        manifest_name: str,
        manifest_version: str,
        manifest_json: str,
        namespace: str,
        pod_name: str,
        helm_release: str,
        service_url: str,
        timeout_seconds: int,
        params_json: str,
        status: str,
        started_at: datetime,
        effective_gpu: int = 0,
        output_subdir: Optional[str] = None,
    ) -> None:
        sql = (
            f"INSERT INTO `{_TABLE}` "
            "(job_id, model_id, workspace_id, manifest_name, manifest_version, "
            "manifest_json, namespace, pod_name, helm_release, service_url, "
            "timeout_seconds, params_json, status, output_subdir, "
            "effective_gpu, started_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        row = (
            job_id, model_id, workspace_id, manifest_name, manifest_version,
            manifest_json, namespace, pod_name, helm_release, service_url,
            timeout_seconds, params_json, status, output_subdir,
            effective_gpu, _to_naive_utc(started_at),
        )
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, row)
            await conn.commit()

    async def update_status(self, job_id: str, status: str) -> None:
        sql = f"UPDATE `{_TABLE}` SET status=%s WHERE job_id=%s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (status, job_id))
            await conn.commit()

    async def update_partner_job_id(self, job_id: str, partner_job_id: str) -> None:
        sql = f"UPDATE `{_TABLE}` SET partner_job_id=%s WHERE job_id=%s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (partner_job_id, job_id))
            await conn.commit()

    async def finalize(self, job_id: str, status: str) -> None:
        """Terminal 상태 도달 시 호출 — row 를 지우지 않고 tombstone 으로 남긴다.

        예전엔 DELETE 했다. 그러면 재시작 후 그 job 을 조회하는 호출자가 404 를
        받고 "아직 모른다"로 오해해 영구 재시도한다 (playground SSE 가 1초마다
        GET /jobs/{id} 를 때리던 사고). status 만 terminal 로 갱신해 두면
        ``list_active`` 는 여전히 걸러내고(복구 대상 아님) 조회는 터미널 상태를
        돌려줄 수 있다. ``updated_at`` 은 ON UPDATE CURRENT_TIMESTAMP 로 자동
        갱신되어 ``prune_terminal`` 의 보존기간 기준이 된다.
        """
        await self.update_status(job_id, status)

    async def prune_terminal(
        self, retention_days: int = _TOMBSTONE_RETENTION_DAYS,
    ) -> int:
        """보존기간 지난 terminal tombstone 삭제. 반환 = 삭제된 row 수.

        startup 에서 1회 호출. 비교는 DB 서버 시각(``NOW()``) 안에서만 하므로
        BFF 프로세스의 timezone 과 섞이지 않는다.
        """
        sql = (
            f"DELETE FROM `{_TABLE}` "
            f"WHERE status IN ({_TERMINAL_STATUS_SQL}) "
            "AND updated_at IS NOT NULL "
            "AND updated_at < (NOW() - INTERVAL %s DAY)"
        )
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (int(retention_days),))
                removed = cur.rowcount or 0
            await conn.commit()
        return removed

    async def get(self, job_id: str) -> Optional[JobStateSnapshot]:
        sql = f"SELECT * FROM `{_TABLE}` WHERE job_id=%s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (job_id,))
                row = await cur.fetchone()
                cols = [d[0] for d in cur.description] if cur.description else []
        if row is None:
            return None
        return JobStateSnapshot(**dict(zip(cols, row)))

    async def list_active(self) -> list[JobStateSnapshot]:
        """Startup recovery 대상 = non-terminal row 만.

        terminal row 는 tombstone 으로 남아 있으므로(``finalize``) 이 필터가
        복구 정확성의 핵심이다 — 없으면 끝난 job 의 polling task 를 되살린다.
        """
        # status 는 ExternalContainerStatus enum value (str, Enum 의 lowercase).
        sql = (
            f"SELECT * FROM `{_TABLE}` "
            f"WHERE status NOT IN ({_TERMINAL_STATUS_SQL}) "
            "ORDER BY started_at ASC"
        )
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
        return [JobStateSnapshot(**dict(zip(cols, r))) for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────────


def _to_naive_utc(dt: datetime) -> datetime:
    """MariaDB DATETIME 컬럼은 timezone 없음. tz-aware datetime 을 UTC naive 로 변환."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
