"""스토리지 등록 회귀 테스트 (실 helm·DB 불요 — subprocess·get_db monkeypatch).

실행(fb_resource pod 내부, import 경로 정합 — pytest 는 이미지에 없어 /tmp 에 임시 설치):
    pip install -q --target /tmp/pt pytest
    cd /app/src && PYTHONPATH=/tmp/pt python -m pytest storage/test_storage_registration.py -v
"""
import json
from contextlib import contextmanager
from types import SimpleNamespace

from storage import helm_run, storage_service
from utils import kube
from utils.msa_db import db_storage

# helm 3.22 실측 문구 (common-app 이 가진 storage-<name> PVC 와 같은 이름으로 설치할 때)
COMMON_APP_PVC_CONFLICT = (
    'Error: INSTALLATION FAILED: Unable to continue with install: PersistentVolumeClaim "storage-local" '
    'in namespace "jonathan-system" exists and cannot be imported into the current release: invalid ownership '
    'metadata; annotation validation error: key "meta.helm.sh/release-name" must equal "storage-local": '
    'current value is "common-app"'
)


def _fake_helm(stderr, returncode=1):
    def run(*args, **kwargs):
        return SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)
    return run


def _existing_pv(monkeypatch, server, path):
    monkeypatch.setattr(kube, "get_pvc_info", lambda **kw: {"spec": {"volume_name": "pv-storage-local-ns"}})
    monkeypatch.setattr(kube, "get_pv_info", lambda name: {"spec": {"nfs": {"server": server, "path": path}}})


def _create_pvc(monkeypatch, stderr):
    monkeypatch.setenv("JF_SYSTEM_NAMESPACE", "jonathan-system")
    monkeypatch.setattr(helm_run.subprocess, "run", _fake_helm(stderr))
    return helm_run.create_storage_pvc(ip="10.0.0.1", name="storage-local", mountpoint="/data", type="nfs")


def test_existing_platform_pvc_is_reused(monkeypatch):
    _existing_pv(monkeypatch, "10.0.0.1", "/data/")
    ok, _ = _create_pvc(monkeypatch, COMMON_APP_PVC_CONFLICT)
    assert ok


def test_existing_platform_pvc_on_another_export_fails(monkeypatch):
    _existing_pv(monkeypatch, "10.0.0.1", "/elsewhere")
    ok, msg = _create_pvc(monkeypatch, COMMON_APP_PVC_CONFLICT)
    assert not ok
    assert "different server/path" in msg


def test_conflict_on_another_pvc_still_fails(monkeypatch):
    ok, msg = _create_pvc(monkeypatch, COMMON_APP_PVC_CONFLICT.replace('"storage-local" in', '"storage-other" in'))
    assert not ok
    assert "storage-other" in msg


def test_same_name_pvc_not_owned_by_common_app_still_fails(monkeypatch):
    ok, _ = _create_pvc(monkeypatch, COMMON_APP_PVC_CONFLICT.replace('"common-app"', '"someone-else"'))
    assert not ok


def test_other_helm_error_still_fails(monkeypatch):
    ok, _ = _create_pvc(monkeypatch, "Error: INSTALLATION FAILED: timed out waiting for the condition")
    assert not ok


def _record_sql(monkeypatch):
    calls = []

    class Cursor:
        def execute(self, sql, params=None):
            calls.append((sql, params))

    class Conn:
        def cursor(self):
            return Cursor()

        def commit(self):
            pass

    @contextmanager
    def fake_db():
        yield Conn()

    monkeypatch.setattr(db_storage, "get_db", fake_db)
    return calls


def test_delete_storage_by_name_binds_parameter(monkeypatch):
    calls = _record_sql(monkeypatch)
    assert db_storage.delete_storage(name="storage-local")
    assert calls == [("DELETE FROM storage where name = %s", ("storage-local",))]


def test_delete_storage_by_id_keeps_id_query(monkeypatch):
    calls = _record_sql(monkeypatch)
    assert db_storage.delete_storage(storage_id_list="3,4")
    assert calls == [("DELETE FROM storage where id in (3,4)", None)]


def test_delete_storage_without_target_deletes_nothing(monkeypatch):
    calls = _record_sql(monkeypatch)
    assert not db_storage.delete_storage()
    assert calls == []


def _stub_create_storage(monkeypatch, insert, pvc_ok=True):
    deleted = []
    monkeypatch.setattr(storage_service.storage_db, "insert_storage", insert)
    monkeypatch.setattr(storage_service.storage_db, "delete_storage",
                        lambda **kw: deleted.append(kw) or True)
    monkeypatch.setattr(storage_service, "create_storage_pvc", lambda **kw: (pvc_ok, "" if pvc_ok else "pvc fail"))
    monkeypatch.setattr(storage_service, "delete_helm", lambda **kw: None)
    return deleted


def test_duplicate_registration_keeps_existing_row(monkeypatch):
    def insert(**kw):
        raise Exception("DB insert fail")   # UNIQUE(name) 위반
    deleted = _stub_create_storage(monkeypatch, insert)
    res = storage_service.create_storage(ip="10.0.0.1", mountpoint="/data", type="nfs", name="local")
    assert json.loads(res.body)["status"] == 0
    assert deleted == []


def test_failed_registration_removes_only_its_own_row(monkeypatch):
    deleted = _stub_create_storage(monkeypatch, lambda **kw: 7, pvc_ok=False)
    res = storage_service.create_storage(ip="10.0.0.1", mountpoint="/data", type="nfs", name="local")
    assert json.loads(res.body)["status"] == 0
    assert deleted == [{"storage_id_list": 7}]
