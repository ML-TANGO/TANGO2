"""SP-Ext.3: Persistent state for in-flight external jobs.

BFF (fb_external_container) restart 시 JobTracker 의 in-memory ``self._jobs``
가 휘발되는 문제를 해결하기 위한 영구 저장소. Active job 들 (PENDING/POD_READY
/STARTED) 만 row 로 유지하고, terminal 상태 (COMPLETED/FAILED/CANCELED) 에
도달하면 row 를 삭제한다.

테이블: ``jonathan_llm.external_job_state`` — schema 는
``apps/fb_utils/llm_db/schema.sql`` 참조.

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

    async def delete(self, job_id: str) -> None:
        """Terminal 상태 도달 시 호출. active row 만 남기는 게 invariant."""
        sql = f"DELETE FROM `{_TABLE}` WHERE job_id=%s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (job_id,))
            await conn.commit()

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
        """Startup recovery: 모든 active row (즉 row 가 남아 있는 모든 것).

        Terminal 상태 시 row 삭제하는 invariant 덕에 status 필터 불필요하지만,
        예방차원으로 명시적으로 non-terminal 만 가져온다.
        """
        # status 는 ExternalContainerStatus enum value (str, Enum 의 lowercase).
        # terminal 시 row 가 삭제되는 invariant 가 깨지더라도 잘못 register
        # 안 되도록 defense-in-depth 로 명시 필터.
        sql = (
            f"SELECT * FROM `{_TABLE}` "
            "WHERE status NOT IN ('completed', 'failed', 'cancelled') "
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
