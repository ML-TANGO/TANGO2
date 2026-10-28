from fastapi import APIRouter, Query, Header, HTTPException, Path
from fastapi.responses import Response, StreamingResponse
from starlette.concurrency import run_in_threadpool
from typing import Optional
import os
import re

from edge import model
from edge import edge_service
from utils.resource import response
from utils.access_check import admin_access_check
import traceback

# SP-8 / 수용계획서 3.1 — Edge 워커 노드 + 커스텀 레이블. 노드 관리와 동일하게 admin.
# edge_service 는 sync(requests + pymysql) — async 라우트에서 직접 호출하면 이벤트루프를
# 막으므로(특히 register→refresh 의 최대 5s 폴링) run_in_threadpool 로 오프로드.
edge = APIRouter(prefix="/edge")


@edge.post('/workers')
@admin_access_check()
async def register_worker(body: model.RegisterEdgeWorkerModel):
    try:
        res = await run_in_threadpool(edge_service.register_edge_worker, body)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.get('/workers')
# [authZ] 목록 조회 = 일반 사용자 개방 (등록/관리만 admin). 엣지 워커는 전역 디바이스.
async def list_workers():
    try:
        res = await run_in_threadpool(edge_service.list_edge_workers)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.get('/workers/{worker_id}')
# [authZ] 단건 조회 = 일반 사용자 개방.
async def get_worker(worker_id: int):
    try:
        res = await run_in_threadpool(edge_service.get_edge_worker, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.post('/workers/{worker_id}/refresh')
# [authZ] 상태/자원 갱신(모니터링) = 일반 사용자 개방.
async def refresh_worker(worker_id: int):
    # remoteManager /metrics 폴링 → 연결상태/자원/배포 갱신 (blocking → threadpool).
    try:
        res = await run_in_threadpool(edge_service.refresh_edge_worker, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.post('/workers/{worker_id}/deploy')
# [authZ] 배포 실행 = 일반 사용자 개방 (등록/관리만 admin).
async def deploy_worker(worker_id: int, body: model.DeployEdgeModel):
    # SP-6 / 3.10 — 양자화 패키지를 Edge 워커에 remoteManager /ops 로 배포 (blocking → threadpool).
    try:
        res = await run_in_threadpool(edge_service.deploy_edge_worker, worker_id, body)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.post('/workers/{worker_id}/stop')
# [authZ] 배포 중지 = 배포 실행과 동일 게이트(일반 사용자 개방, 등록/토큰만 admin).
async def stop_worker(worker_id: int):
    # 배포된 컨테이너를 remoteManager /ops op:"stop" 으로 제거 (blocking → threadpool).
    # 디바이스 쪽 stop 은 원래 구현돼 있었고 플랫폼의 호출 경로만 없었다.
    try:
        res = await run_in_threadpool(edge_service.stop_edge_worker, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.post('/workers/{worker_id}/token')
@admin_access_check()
async def issue_worker_token(worker_id: int):
    # 노드별 Bearer 토큰 발급/rotation — 평문은 응답 1회만.
    try:
        res = await run_in_threadpool(edge_service.issue_device_token, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


# ── 통합 파이프라인 s2s (llm_deploy edge 노드) ────────────────────────────────
# fb_pipeline 런타임이 호출 — admin 세션이 없으므로 admin_access_check 미적용.
# 위 admin deploy/get 과 동일 서비스 함수를 재사용하되 게이트만 s2s 로 연다
# (llm_playground pipeline-deploy 선례와 동형). 클러스터 내부 DNS 전용.
@edge.post('/workers/{worker_id}/pipeline-deploy')
async def pipeline_deploy_worker(worker_id: int, body: model.DeployEdgeModel):
    try:
        res = await run_in_threadpool(edge_service.deploy_edge_worker, worker_id, body)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.get('/workers/{worker_id}/pipeline-status')
async def pipeline_status_worker(worker_id: int):
    # 배포 노드 폴러용 — refresh 가 remoteManager /metrics 를 폴링해 deploying→running/error
    # 를 확정한다(deploy 가 202 async 면 deploy_state=deploying 으로 남으므로).
    try:
        res = await run_in_threadpool(edge_service.refresh_edge_worker, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


# ── device-facing (기관 디바이스가 호출) ─────────────────────────────────────
# 세션 없음 → admin_access_check 미적용(s2s 선례와 동형). 노드별 Bearer 토큰 자체 검증.
# 경로는 /edge/devices/... 로 /workers·/labels 세그먼트와 분리(라우팅 충돌 회피).
@edge.post('/devices/{device_id}/heartbeat')
async def device_heartbeat(body: model.HeartbeatModel,
                           device_id: str = Path(..., max_length=128, pattern=r"^[A-Za-z0-9._\-]+$"),
                           authorization: str = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[len("Bearer "):]
    valid = await run_in_threadpool(edge_service.verify_device_token, device_id, token)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid device token")
    try:
        res = await run_in_threadpool(edge_service.record_heartbeat, device_id, body)
        return response(status=1, result=res)
    except edge_service.HeartbeatThrottled:
        # SP-8 §5.1 — 30초 미만 재수신. 게이트웨이 rate-limit 과 별개인 앱-레벨 백스톱.
        raise HTTPException(status_code=429, detail="heartbeat too frequent")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


# GGUF 는 수 GB 라 전송이 끊기면 처음부터 다시 받는 비용이 크다. 이 런타임의
# Starlette(0.27) FileResponse 는 Range 를 구현하지 않으므로(실측), 이어받기에 실제로
# 필요한 최소형 `bytes=<start>-` 만 직접 처리하고 그 외 형식은 전체 전송으로 떨어뜨린다.
# 자릿수 상한을 둔다 — 인증 뒤 경로이긴 하나 무제한 int 변환은 방어해 둔다.
_RANGE_RE = re.compile(r"^bytes=(\d{1,20})-$")
_CHUNK = 1024 * 1024


def _artifact_response(path: str, range_header: Optional[str], device_id: str):
    """전체/부분 모두 직접 스트리밍한다.

    ⚠️ 정리(cleanup)를 제너레이터 수명에 의존하지 않는다. 클라이언트가 먼저 끊으면
    그 finally 가 실행되지 않는다(실측). 그래서 '반납해야 하는 자원' 을 만들지 않고,
    보낼 양을 **시작 시점에 선반영**한다(동시 연결로 예산을 우회하지 못하게).

    ⚠️ 이 함수는 NFS 위의 수 GB 파일을 stat·open 한다. 반드시 스레드풀에서 호출할 것
    — 이벤트루프에서 돌면 NFS 가 느려질 때 같은 프로세스의 모든 요청(heartbeat·노드·
    스토리지 API)이 함께 멈춘다.
    """
    try:
        size = os.path.getsize(path)
        start = 0
        if range_header:
            m = _RANGE_RE.match(range_header.strip())
            if m:
                start = int(m.group(1))
                if start >= size:
                    raise HTTPException(status_code=416, detail="range not satisfiable")
        ok, budget_err = edge_service.artifact_budget_reserve(device_id, size - start)
        if not ok:
            raise HTTPException(status_code=429, detail=budget_err)
        fh = open(path, "rb")          # 여기서 열어 TOCTOU(해석 후 삭제)를 응답 전에 드러낸다
    except HTTPException:
        raise
    except OSError:
        raise HTTPException(status_code=404, detail="artifact unavailable")

    def _iter():
        try:
            fh.seek(start)
            while True:
                chunk = fh.read(_CHUNK)
                if not chunk:
                    break
                yield chunk
        finally:
            fh.close()

    headers = {"Accept-Ranges": "bytes",
               "Content-Length": str(size - start),
               "Content-Disposition": f'attachment; filename="{os.path.basename(path)}"'}
    if start:
        headers["Content-Range"] = f"bytes {start}-{size - 1}/{size}"
    return StreamingResponse(_iter(), status_code=206 if start else 200,
                             media_type="application/octet-stream", headers=headers)


def _artifact_auth(device_id, authorization, kind="model", lineage=None):
    """device-facing 공통 게이트 → 절대경로. 실패는 HTTPException 으로 올린다."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[len("Bearer "):]
    path, code, err = edge_service.resolve_device_artifact(device_id, token, kind, lineage)
    if path is None:
        raise HTTPException(status_code=code, detail=err)
    return path


async def _artifact_head(device_id, authorization, kind, lineage):
    # 에이전트는 이미 받아 둔 파일을 건너뛰려고 HEAD 로 크기를 먼저 묻는다. GET 만
    # 등록하면 405 가 돌아가 크기 확인이 실패하고, 그러면 매 배포마다 수 GB 를 다시
    # 받는다(스킵·이어받기가 통째로 무력화된다).
    path = await run_in_threadpool(_artifact_auth, device_id, authorization, kind, lineage)
    ok, budget_err = edge_service.artifact_budget_check(device_id)
    if not ok:
        raise HTTPException(status_code=429, detail=budget_err)
    try:
        size = await run_in_threadpool(os.path.getsize, path)   # NFS stat → 스레드풀
    except OSError:
        raise HTTPException(status_code=404, detail="artifact unavailable")
    return Response(status_code=200, headers={
        "Accept-Ranges": "bytes",
        "Content-Length": str(size),
        "Content-Disposition": f'attachment; filename="{os.path.basename(path)}"',
    })


async def _artifact_get(device_id, authorization, range_header, kind, lineage):
    path = await run_in_threadpool(_artifact_auth, device_id, authorization, kind, lineage)
    # 예산 선반영과 파일 stat·open 이 모두 이 안에서 일어난다 — NFS 블로킹을
    # 이벤트루프에 올리지 않도록 스레드풀로 넘긴다.
    return await run_in_threadpool(_artifact_response, path, range_header, device_id)


@edge.head('/devices/{device_id}/artifact')
async def device_artifact_head(
        device_id: str = Path(..., max_length=128, pattern=r"^[A-Za-z0-9._\-]+$"),
        authorization: str = Header(default=None),
        lineage: Optional[int] = Query(default=None, ge=1)):
    return await _artifact_head(device_id, authorization, "model", lineage)


@edge.get('/devices/{device_id}/artifact')
async def device_artifact(device_id: str = Path(..., max_length=128, pattern=r"^[A-Za-z0-9._\-]+$"),
                          authorization: str = Header(default=None),
                          range: str = Header(default=None),
                          lineage: Optional[int] = Query(default=None, ge=1)):
    # 계약 v1 — 디바이스가 배포 지시의 model_url 로 GGUF 를 받아간다. 인증은 heartbeat
    # 와 **같은** 디바이스 Bearer 토큰이고(경로도 같은 /edge/devices/* 라 Kong
    # ALLOWED_PATH 에 이미 포함 → 게이트웨이 변경 0), 무엇을 줄지는 서버가 워커의
    # deploy_lineage_id 로 정한다. 응답 본문이 파일이라 공통 envelope 를 쓰지 않는다.
    return await _artifact_get(device_id, authorization, range, "model", lineage)


# 계약 1.2 — SDS(VLM) 패키지의 mmproj(비전) GGUF. 배포 지시의 mmproj_url 이 여기를 가리킨다.
# 같은 디바이스 토큰·같은 lineage 인가·같은 전송 예산을 쓴다.
@edge.head('/devices/{device_id}/artifact/mmproj')
async def device_mmproj_head(
        device_id: str = Path(..., max_length=128, pattern=r"^[A-Za-z0-9._\-]+$"),
        authorization: str = Header(default=None),
        lineage: Optional[int] = Query(default=None, ge=1)):
    return await _artifact_head(device_id, authorization, "mmproj", lineage)


@edge.get('/devices/{device_id}/artifact/mmproj')
async def device_mmproj(device_id: str = Path(..., max_length=128, pattern=r"^[A-Za-z0-9._\-]+$"),
                        authorization: str = Header(default=None),
                        range: str = Header(default=None),
                        lineage: Optional[int] = Query(default=None, ge=1)):
    return await _artifact_get(device_id, authorization, range, "mmproj", lineage)


@edge.delete('/workers/{worker_id}')
@admin_access_check()
async def delete_worker(worker_id: int):
    try:
        res = await run_in_threadpool(edge_service.delete_edge_worker, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


# ── ops 토큰 (플랫폼 ↔ 디바이스 공유 키) ─────────────────────────────────────
# 전 디바이스 공통 값이라 admin 전용이다. 디바이스별 토큰(/workers/{id}/token)과 달리
# **조회를 허용**한다 — 1회 표시 방식이면 디바이스를 추가할 때마다 전체 재발급이 된다.

@edge.get('/ops-token')
@admin_access_check()
async def get_ops_token():
    try:
        return response(status=1, result=await run_in_threadpool(edge_service.get_ops_token))
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.post('/ops-token/rotate')
@admin_access_check()
async def rotate_ops_token():
    # 재발급 즉시 플랫폼은 새 키만 보낸다. 교체 전 디바이스는 401 이 된다(하드 컷오버).
    # prev 는 보관용일 뿐 인증에 쓰이지 않는다.
    try:
        return response(status=1, result=await run_in_threadpool(edge_service.rotate_ops_token))
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.post('/ops-token/retire-prev')
@admin_access_check()
async def retire_prev_ops_token():
    # 옛 키 폐기. 이 시점부터 교체하지 않은 디바이스는 401 이 된다.
    try:
        return response(status=1,
                        result=await run_in_threadpool(edge_service.retire_prev_ops_token))
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


# ── 커스텀 레이블 (노드 + 엣지워커 공용) ──────────────────────────────────────

@edge.post('/labels')
@admin_access_check()
async def upsert_label(body: model.CustomLabelModel):
    try:
        res = await run_in_threadpool(edge_service.upsert_label, body)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.get('/labels')
@admin_access_check()
async def list_labels(target_type: Optional[str] = Query(default=None),
                      target_id: Optional[str] = Query(default=None)):
    try:
        res = await run_in_threadpool(edge_service.list_labels, target_type, target_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.delete('/labels/{label_id}')
@admin_access_check()
async def delete_label(label_id: int):
    try:
        res = await run_in_threadpool(edge_service.delete_label, label_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
