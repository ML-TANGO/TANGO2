"""Manifest persistence — Protocol + in-memory + MariaDB implementations.

Lifecycle and router code talks only to the Protocol so swapping
implementations is transparent. The MariaDB implementation is the
production target; the in-memory one is the fallback for development
(no DB env vars set) and unit tests.

Why a fallback instead of failing closed: SP-Ext.10 mock validation,
local dev, and the very first onboarding session (before the DB
migration is run) all need a working service. A WARN-level log
surfaces the degraded mode without blocking work.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from .schema import ExternalContainerManifest

logger = logging.getLogger(__name__)


class RegistryConflictError(RuntimeError):
    """Raised when (name, version) is already registered."""


@dataclass(frozen=True)
class ManifestRow:
    """Lightweight projection — what we surface in listings / responses.

    ``description`` is sourced from ``metadata.description`` in the raw
    manifest JSON; it is optional and may be ``None`` when the partner
    did not provide one.
    """

    name: str
    version: str
    job_type: str
    execution_mode: str
    image: str
    service_family: Optional[str]
    contract_version: Optional[str]
    pair_id: Optional[str]
    description: Optional[str] = None


# ── Protocol ──────────────────────────────────────────────────────────────


class ManifestRegistry(Protocol):
    async def add(
        self,
        manifest: ExternalContainerManifest,
        raw_yaml: str,
        pair_id: Optional[str] = None,
    ) -> None:
        ...

    async def add_pair(
        self,
        infer: ExternalContainerManifest,
        infer_yaml: str,
        train: ExternalContainerManifest,
        train_yaml: str,
    ) -> str:
        """Register two paired manifests atomically. Returns the shared pair_id."""

    async def get(
        self, name: str, version: str
    ) -> Optional[ExternalContainerManifest]:
        ...

    async def list_all(self) -> list[ManifestRow]:
        ...

    async def remove(self, name: str, version: str) -> bool:
        ...


# ── In-memory implementation (dev / tests / fallback) ─────────────────────


class InMemoryManifestRegistry:
    """Dict-backed registry — same contract, no persistence."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], tuple[ExternalContainerManifest, Optional[str]]] = {}

    @staticmethod
    def _key(name: str, version: str) -> tuple[str, str]:
        return (name, version)

    async def add(
        self,
        manifest: ExternalContainerManifest,
        raw_yaml: str,
        pair_id: Optional[str] = None,
    ) -> None:
        key = self._key(manifest.metadata.name, manifest.metadata.version)
        if key in self._rows:
            raise RegistryConflictError(
                f"manifest {manifest.metadata.name}@{manifest.metadata.version} already exists"
            )
        self._rows[key] = (manifest, pair_id)

    async def add_pair(
        self,
        infer: ExternalContainerManifest,
        infer_yaml: str,
        train: ExternalContainerManifest,
        train_yaml: str,
    ) -> str:
        pair_id = str(uuid.uuid4())
        # Pre-check both to fail atomically.
        for m in (infer, train):
            key = self._key(m.metadata.name, m.metadata.version)
            if key in self._rows:
                raise RegistryConflictError(
                    f"manifest {m.metadata.name}@{m.metadata.version} already exists"
                )
        self._rows[self._key(infer.metadata.name, infer.metadata.version)] = (infer, pair_id)
        self._rows[self._key(train.metadata.name, train.metadata.version)] = (train, pair_id)
        return pair_id

    async def get(
        self, name: str, version: str
    ) -> Optional[ExternalContainerManifest]:
        entry = self._rows.get(self._key(name, version))
        return entry[0] if entry else None

    async def list_all(self) -> list[ManifestRow]:
        return [_row_from_manifest(m, pid) for (m, pid) in self._rows.values()]

    async def remove(self, name: str, version: str) -> bool:
        return self._rows.pop(self._key(name, version), None) is not None


def _row_from_manifest(m: ExternalContainerManifest, pair_id: Optional[str]) -> ManifestRow:
    return ManifestRow(
        name=m.metadata.name,
        version=m.metadata.version,
        job_type=m.spec.job_type,
        execution_mode=m.spec.execution_mode,
        image=m.spec.image,
        service_family=m.spec.service_family,
        contract_version=m.spec.contract_version,
        pair_id=pair_id,
        description=m.metadata.description,
    )


# ── MariaDB implementation (production) ───────────────────────────────────


class MariaDBManifestRegistry:
    """aiomysql-backed persistence.

    Pool is owned by the FastAPI lifespan; this class only acquires
    connections, never opens new ones.
    """

    _TABLE = "external_container_manifest"

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def add(
        self,
        manifest: ExternalContainerManifest,
        raw_yaml: str,
        pair_id: Optional[str] = None,
    ) -> None:
        row = (
            manifest.metadata.name,
            manifest.metadata.version,
            manifest.apiVersion,
            manifest.spec.job_type,
            manifest.spec.execution_mode,
            manifest.spec.image,
            manifest.spec.service_family,
            manifest.spec.contract_version,
            pair_id,
            raw_yaml,
            manifest.model_dump_json(),
        )
        await self._insert_rows([row])

    async def add_pair(
        self,
        infer: ExternalContainerManifest,
        infer_yaml: str,
        train: ExternalContainerManifest,
        train_yaml: str,
    ) -> str:
        pair_id = str(uuid.uuid4())
        rows = [
            (
                infer.metadata.name, infer.metadata.version, infer.apiVersion,
                infer.spec.job_type, infer.spec.execution_mode, infer.spec.image,
                infer.spec.service_family, infer.spec.contract_version,
                pair_id, infer_yaml, infer.model_dump_json(),
            ),
            (
                train.metadata.name, train.metadata.version, train.apiVersion,
                train.spec.job_type, train.spec.execution_mode, train.spec.image,
                train.spec.service_family, train.spec.contract_version,
                pair_id, train_yaml, train.model_dump_json(),
            ),
        ]
        await self._insert_rows(rows)
        return pair_id

    async def get(
        self, name: str, version: str
    ) -> Optional[ExternalContainerManifest]:
        query = f"SELECT raw_json FROM {self._TABLE} WHERE name=%s AND version=%s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (name, version))
                row = await cur.fetchone()
        if row is None:
            return None
        raw_json = row[0]
        # JSON column can come back as str or already-decoded dict depending
        # on the driver build; normalize both.
        data = json.loads(raw_json) if isinstance(raw_json, (str, bytes, bytearray)) else raw_json
        return ExternalContainerManifest.model_validate(data)

    async def list_all(self) -> list[ManifestRow]:
        # description 은 raw_json.metadata.description 에서 추출 (전용 컬럼 없음).
        # JSON_UNQUOTE(JSON_EXTRACT(...)) 로 NULL 도 자연스럽게 처리.
        query = (
            f"SELECT name, version, job_type, execution_mode, image, "
            f"service_family, contract_version, pair_id, "
            f"JSON_UNQUOTE(JSON_EXTRACT(raw_json, '$.metadata.description')) "
            f"FROM {self._TABLE} "
            f"ORDER BY service_family, name, version"
        )
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                rows = await cur.fetchall()
        return [
            ManifestRow(
                name=r[0], version=r[1], job_type=r[2], execution_mode=r[3],
                image=r[4], service_family=r[5], contract_version=r[6], pair_id=r[7],
                description=(r[8] if r[8] not in (None, "null") else None),
            )
            for r in rows
        ]

    async def remove(self, name: str, version: str) -> bool:
        query = f"DELETE FROM {self._TABLE} WHERE name=%s AND version=%s"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                affected = await cur.execute(query, (name, version))
            await conn.commit()
        return bool(affected)

    # ── Internals ──────────────────────────────────────────────────────

    async def _insert_rows(self, rows: list[tuple]) -> None:
        # 11-column INSERT (matches migrations/001_initial.sql columns).
        query = (
            f"INSERT INTO {self._TABLE} "
            f"(name, version, api_version, job_type, execution_mode, image, "
            f"service_family, contract_version, pair_id, raw_yaml, raw_json) "
            f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        async with self._pool.acquire() as conn:
            await conn.begin()
            try:
                async with conn.cursor() as cur:
                    await cur.executemany(query, rows)
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                if _is_duplicate_key(e):
                    raise RegistryConflictError(str(e)) from e
                raise


def _is_duplicate_key(exc: BaseException) -> bool:
    """Detect MariaDB ER_DUP_ENTRY (1062) across aiomysql exception variants."""
    code = getattr(exc, "args", (None,))[0]
    if code == 1062:
        return True
    msg = str(exc).lower()
    return "duplicate entry" in msg or "1062" in msg
