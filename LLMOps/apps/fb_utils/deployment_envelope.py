"""배포 타겟 정규화 read-model envelope (배포 타겟 디스패치 설계).

여러 배포 타겟(cluster=Playground / edge=remoteManager 디바이스)의 이질적 상태를
FE/BFF 가 하나의 형태로 소비하도록 **정규화**하는 순수 함수 계층.

- 배치 무관(pure): dict 입력 → envelope dict 출력. 어느 서비스가 엔드포인트를 호스팅해도 재사용.
- 컨트롤플레인 지식(Kong·remoteManager)은 각 어댑터 서비스에 남기고, 여기선 상태 매핑만.
- 상세는 target_details 로 원본 병기(손실적 정규화 방지). phase 는 coarse 5-state.

envelope = {
    "target":          "cluster" | "edge" | "standalone",
    "native_id":       원본 식별자(현 목록: 3종 모두 playground id — edge 도 playground 배포),
    # 주: edge 는 두 생산자 — edge_deploy_envelope(playground row, deploy_type='edge', 현 목록 소스) /
    #     edge_envelope(edge_worker 디바이스 기반, 디바이스 뷰용 — 현재 목록 미사용).
    "phase":           PHASE_* (deploying/running/stopped/failed/unknown),
    "capabilities":    [CAP_*],           # 타겟이 지원하는 동작(publish 등은 cluster 전용)
    "links":           {name: url|path},  # 호출/관리 링크(있을 때만)
    "last_observed_at": ISO 문자열 | None, # freshness(edge=last_seen). cluster=live→None
    "target_details":  {...},             # 타겟 원본 상태(freshness/에러 등 비손실)
}
"""
from typing import Optional

# ── phase (coarse, 타겟 공통) ──
PHASE_DEPLOYING = "deploying"
PHASE_RUNNING = "running"
PHASE_STOPPED = "stopped"
PHASE_FAILED = "failed"
PHASE_UNKNOWN = "unknown"

# ── capability (타겟이 광고하는 동작. publish=cluster 전용) ──
CAP_EXTERNAL_ACCESS = "external_access"      # publish/unpublish/rotate (cluster)
CAP_CREDENTIAL_ROTATION = "credential_rotation"
CAP_LIVE_METRICS = "live_metrics"            # 인클러스터 시계열 (cluster)
CAP_REMOTE_REFRESH = "remote_refresh"        # remoteManager /metrics 폴링 (edge)
CAP_PACKAGE_DOWNLOAD = "package_download"

TARGET_CLUSTER = "cluster"
TARGET_EDGE = "edge"
TARGET_STANDALONE = "standalone"  # 오프라인 번들(playground row, deploy_type='standalone')

# cluster 서빙 상태 문자열 → coarse phase (fb_deployment/llm_playground deployment_status.status).
_CLUSTER_PHASE = {
    "running": PHASE_RUNNING,
    "error": PHASE_FAILED,
    "installing": PHASE_DEPLOYING,
    "pending": PHASE_DEPLOYING,
    "stop": PHASE_STOPPED,
    "stopped": PHASE_STOPPED,
}
# edge_worker.deploy_state → coarse phase. remoteManager 는 deploying 도 보고(pipeline edge 분기).
_EDGE_PHASE = {
    "deploying": PHASE_DEPLOYING,
    "running": PHASE_RUNNING,
    "error": PHASE_FAILED,
    "stopped": PHASE_STOPPED,
}


def normalize_cluster_phase(status: Optional[str]) -> str:
    return _CLUSTER_PHASE.get((status or "").lower(), PHASE_UNKNOWN)


def normalize_edge_phase(conn_status: Optional[str], deploy_state: Optional[str]) -> str:
    # 오프라인(heartbeat 끊김)이면 저장된 deploy_state 는 stale — 라이브 상태를 확신할 수 없으므로
    # running 등으로 오표기하지 않고 unknown(freshness 손실). online 일 때만 deploy_state 로 확정.
    if (conn_status or "").lower() != "online":
        return PHASE_UNKNOWN
    if not deploy_state:
        return PHASE_UNKNOWN
    return _EDGE_PHASE.get(str(deploy_state).lower(), PHASE_UNKNOWN)


def _cluster_status_str(dep: dict) -> Optional[str]:
    """deployment_status 는 {"status": "...", "worker": {...}} 또는 평문 문자열일 수 있어 방어적으로 추출."""
    ds = dep.get("deployment_status")
    if isinstance(ds, dict):
        return ds.get("status")
    if isinstance(ds, str):
        return ds
    return dep.get("status")


def cluster_envelope(dep: dict, workspace_id=None) -> dict:
    """cluster 행 dict → envelope. 소스별 필드 차이 방어:
    - Playground 목록(get_playground_list): flat `status`, workspace_id/api 미포함 → workspace_id 는
      호출측 파라미터로 주입, serving URL(links.api)는 목록에 없어 비움(상세 조회 시 채움 — 후속 Phase).
    - fb_deployment 행: `deployment_status` dict + `api_address` 있으면 그대로 사용."""
    status = _cluster_status_str(dep)
    links = {}
    api = dep.get("api_address") or dep.get("api_path")
    if api:
        links["api"] = api
    return {
        "target": TARGET_CLUSTER,
        "native_id": dep.get("id") or dep.get("playground_id") or dep.get("deployment_id"),
        "name": dep.get("name"),
        "phase": normalize_cluster_phase(status),
        "capabilities": [CAP_EXTERNAL_ACCESS, CAP_LIVE_METRICS, CAP_CREDENTIAL_ROTATION],
        "links": links,
        "last_observed_at": None,  # cluster 상태는 live 조회 → freshness 개념 없음
        "target_details": {
            "workspace_id": dep.get("workspace_id") if dep.get("workspace_id") is not None else workspace_id,
            "llm": dep.get("llm"),
            "raw_status": dep.get("deployment_status") if dep.get("deployment_status") is not None else status,
        },
    }


def edge_envelope(worker: dict) -> dict:
    """edge_worker 행 dict → envelope. deploy_state/conn_status 로 phase, last_seen 로 freshness."""
    links = {}
    rm = worker.get("remote_manager_url")
    if rm:
        links["remote_manager"] = rm
    last_seen = worker.get("last_seen")
    return {
        "target": TARGET_EDGE,
        "native_id": worker.get("id"),
        "name": worker.get("name") or worker.get("device_id"),
        "phase": normalize_edge_phase(worker.get("conn_status"), worker.get("deploy_state")),
        "capabilities": [CAP_REMOTE_REFRESH, CAP_PACKAGE_DOWNLOAD],
        "links": links,
        "last_observed_at": last_seen.isoformat() if hasattr(last_seen, "isoformat") else last_seen,
        "target_details": {
            "device_type": worker.get("device_type"),
            "conn_status": worker.get("conn_status"),
            "deploy_model": worker.get("deploy_model"),
            "deploy_version": worker.get("deploy_version"),
            "deploy_state": worker.get("deploy_state"),
        },
    }


def edge_deploy_envelope(dep: dict, workspace_id=None) -> dict:
    """온디바이스(엣지) 배포 행 dict → envelope. playground row(deploy_type='edge').
    edge 도 별도 playground 로 관리 — 배포 디바이스(edge_worker)는 상세 '배포' 탭에서 선택하는 타겟이지
    목록 항목이 아니다. 여기선 배포(프로젝트) 자체의 상태만."""
    status = _cluster_status_str(dep)
    return {
        "target": TARGET_EDGE,
        "native_id": dep.get("id") or dep.get("playground_id"),
        "name": dep.get("name"),
        "phase": normalize_cluster_phase(status),
        "capabilities": [CAP_REMOTE_REFRESH, CAP_PACKAGE_DOWNLOAD],
        "links": {},
        "last_observed_at": None,
        "target_details": {
            "workspace_id": dep.get("workspace_id") if dep.get("workspace_id") is not None else workspace_id,
        },
    }


def standalone_envelope(dep: dict, workspace_id=None) -> dict:
    """standalone(오프라인 번들) 행 dict → envelope. playground row(deploy_type='standalone').
    러닝 배포가 아니라 번들 산출물 — package_download capability 만, live/publish 없음."""
    status = _cluster_status_str(dep)
    return {
        "target": TARGET_STANDALONE,
        "native_id": dep.get("id") or dep.get("playground_id"),
        "name": dep.get("name"),
        "phase": normalize_cluster_phase(status),
        "capabilities": [CAP_PACKAGE_DOWNLOAD],
        "links": {},
        "last_observed_at": None,
        "target_details": {
            "workspace_id": dep.get("workspace_id") if dep.get("workspace_id") is not None else workspace_id,
        },
    }
