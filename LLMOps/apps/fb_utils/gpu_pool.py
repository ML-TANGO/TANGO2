"""GPU 풀 가용량 집계 — **할당기와 조회가 공유하는 단일 정본**.

왜 fb_utils 인가: 이 숫자를 세는 곳이 둘이다. 하나는 실제로 GPU 를 선점하는
fb_scheduler(실패 진단 문구), 다른 하나는 화면에 현황을 내주는 fb_resource. 두 곳이
각자 세면 반드시 갈린다 — 실제로 갈렸었다. 예전 진단 문구는 `used_info` 만 보고
"free buckets: 2" 라고 말하면서 1장도 claim 하지 못했는데, external 잡이 잡은 GPU 는
`used_info` 가 아니라 **예약 키**(SETNX)로 표시되기 때문이다. 화면이 그 계산을
따라 하면 "가용 3장" 이라 해 놓고 실행은 실패하는, 같은 거짓말을 사용자에게 한다.

그래서 두 술어를 여기 한 곳에 묶는다:
    in_use   — `used_info` 있음. 플랫폼 배포/학습이 점유(모니터링이 채운다).
    reserved — `used_info` 는 비었지만 예약 키가 있음. external 잡이 claim 한 상태.
    free     — 둘 다 아님 = 지금 실제로 claim 할 수 있는 장수.

⚠️ 이 값은 **보장이 아니라 사전 안내**다. 조회와 실행 사이에 다른 잡이 claim 할 수 있다
   (TOCTOU). 최종 판정은 언제나 fb_scheduler 의 원자적 SETNX claim 이다.
"""

import json

from utils.redis_key import (
    GPU_INFO_RESOURCE, GPU_RESERVE_KEY, WORKSPACE_RESOURCE_QUOTA)


def snapshot(redis_client, workspace_id=None) -> dict:
    """클러스터 풀 + (workspace_id 주면) 그 워크스페이스 몫을 함께 돌려준다.

    두 축을 **함께** 내는 이유는 둘이 서로 다른 것을 말하고, 어느 하나만으로는 화면이
    정직할 수 없기 때문이다:
      · workspace — 사용자가 '내 몫' 으로 이해하는 값(할당 N장 중 M장 사용). 플랫폼의
        다른 화면도 이 축으로 말한다. **다만 실행을 막지 못한다** — external 경로는 이
        쿼터를 읽지 않고, 차트도 nvidia.com/gpu 를 요청하지 않아(SP-Ext.4 에서 중복 할당
        사고로 제거) K8s ResourceQuota 의 GPU 항목은 증가조차 하지 않는다.
      · cluster — 스케줄러가 실제로 claim 하는 풀. **실행 가능 여부를 정하는 유일한 축.**
    그래서 화면은 workspace 로 말하되 차단은 둘 중 빡빡한 쪽을 따라야 한다.

    ⚠️ workspace.used 는 모니터링이 used_info.used_workspace 로만 세므로
    (monitoring_service.get_workspace_gpu_usage_map) **external 잡의 예약은 빠진다.**
    그 누락은 cluster.reserved 가 잡으므로 두 축을 함께 봐야 구멍이 없다.

    redis_client 를 인자로 받는 이유: 호출자(앱)마다 클라이언트 수명 관리가 다르고,
    여기서 새로 열면 앱의 연결 정책을 우회하게 된다.
    Redis 키가 아예 없으면 예외를 올린다 — 0 으로 접으면 "GPU 없음" 과 "모름" 이 구분되지
    않아, 화면이 멀쩡한 클러스터에서 실행을 막는다.
    """
    raw = redis_client.get(GPU_INFO_RESOURCE)
    if not raw:
        raise RuntimeError(f"redis key {GPU_INFO_RESOURCE} missing — node_init not run?")
    gpu_info = json.loads(raw) or {}

    nodes = {}
    total = in_use = reserved = free = 0
    for node_name, gpus in gpu_info.items():
        if not isinstance(gpus, dict):
            continue
        bucket = {"total": 0, "in_use": 0, "reserved": 0, "free": 0}
        for gpu_uuid, gpu in gpus.items():
            if not isinstance(gpu, dict):
                continue
            bucket["total"] += 1
            if gpu.get("used_info"):
                bucket["in_use"] += 1
                continue
            try:
                held = redis_client.get(GPU_RESERVE_KEY.format(uuid=gpu_uuid))
            except Exception:
                # 조회 실패는 **보수적으로 예약됨** 취급 — 없는 가용량을 있다고 말하는 것보다
                # 있는 것을 없다고 말하는 편이 안전하다(실행 실패를 만들지 않는다).
                held = True
            if held:
                bucket["reserved"] += 1
            else:
                bucket["free"] += 1
        nodes[node_name] = bucket
        total += bucket["total"]
        in_use += bucket["in_use"]
        reserved += bucket["reserved"]
        free += bucket["free"]
    result = {"total": total, "in_use": in_use, "reserved": reserved,
              "free": free, "nodes": nodes}
    if workspace_id is not None:
        result["workspace"] = _workspace_quota(redis_client, workspace_id)
    return result


def _workspace_quota(redis_client, workspace_id):
    """워크스페이스 GPU 몫 {hard, used, free}. 정본은 모니터링이 채우는
    resource:workspace:quota 해시(workspace_id -> {cpu,ram,gpu:{hard,used}}).

    여기서 다시 계산하지 않는다 — 대시보드·워크스페이스 화면이 이미 그 값을 쓰고 있어,
    평가 화면만 따로 세면 같은 워크스페이스가 화면마다 다른 숫자를 갖게 된다.
    값이 없거나 깨졌으면 None 을 돌려준다(0 으로 접으면 "할당 없음" 과 "모름" 이 구분되지
    않아 화면이 멀쩡한 워크스페이스의 실행을 막는다).
    """
    try:
        raw = redis_client.hget(WORKSPACE_RESOURCE_QUOTA, str(workspace_id))
        if not raw:
            return None
        gpu = (json.loads(raw) or {}).get("gpu") or {}
        hard, used = int(gpu.get("hard") or 0), int(gpu.get("used") or 0)
    except Exception:
        return None
    return {"hard": hard, "used": used, "free": max(0, hard - used)}
