import traceback, json, subprocess, os, asyncio, aiofiles, httpx, base64, re, time, uuid
from huggingface_hub import login, model_info, HfApi, hf_hub_download
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
from datetime import datetime
from requests.exceptions import HTTPError, ConnectionError, Timeout

from utils import topic_key
from utils.settings import JF_KAFKA_DNS
from utils.kube import PodName
from utils import TYPE
from utils import settings
from utils import redis_key
from utils import PATH
from utils import common

from utils.common import is_good_name
from utils.llm_db import db_items as db
from utils.msa_db import db_dataset
from utils import deployment_envelope
from utils import deployment_api  # 게시(D6) 공용 teardown — stop/delete 시 Kong 정리(3b-2)
from fastapi.concurrency import run_in_threadpool
from utils.crypt import front_cipher
from utils import llm_deployment
from utils.redis import get_redis_client_async
from utils.workspace_resource import get_workspace_instance_total_info
from utils.msa_db import db_dashboard
from playground import dual_metrics
from utils.external_client import (
    start_infer_job, cancel_infer_job, run_inference, get_job_status,
    get_paired_manifest, ExternalInferError, MANIFEST_JOB_TYPE_INFER,
)

DUAL_SHELL_NAME_MAX_LENGTH = 20
DUAL_PROMPT_CHILD_SUFFIX = "-promptgen"


def _dual_shell_names(name):
    """부모/파생 child 이름을 절단 없이 만든다."""
    if not name or not isinstance(name, str) or not name.strip():
        raise Exception("이중모델 배포 이름을 입력해 주세요.")
    shell_name = name.strip()
    if len(shell_name) > DUAL_SHELL_NAME_MAX_LENGTH:
        # DB VARCHAR(32)에 child 접미사까지 온전히 저장해야 하므로 부모를 미리 잘라서는 안 된다.
        raise Exception("이중모델 배포 이름은 20자 이하로 입력해 주세요.")
    return shell_name, f"{shell_name}{DUAL_PROMPT_CHILD_SUFFIX}"


async def _workspace_playground_names(workspace_id, exclude_ids=None):
    """배포 유형과 무관하게 워크스페이스의 playground 이름을 비교 가능한 형태로 읽는다."""
    excluded = set(exclude_ids or [])
    rows = await db.get_playground_list(workspace_id=workspace_id)
    # MariaDB의 일반적인 대소문자 비구분 collation보다 느슨해지지 않도록 casefold로 선차단한다.
    return {
        str(row.get("name") or "").casefold()
        for row in rows
        if row.get("id") not in excluded
    }


async def _ensure_dual_names_available(workspace_id, shell_name, child_name,
                                       check_shell=True, exclude_ids=None):
    existing_names = await _workspace_playground_names(
        workspace_id=workspace_id, exclude_ids=exclude_ids)
    if check_shell and shell_name.casefold() in existing_names:
        raise Exception("같은 워크스페이스에 동일한 배포 이름이 이미 존재합니다.")
    if child_name.casefold() in existing_names:
        raise Exception(
            f"파생 프롬프트 생성 배포 이름({child_name})이 같은 워크스페이스에 이미 존재합니다.")


# TODO status
async def get_playground_list(workspace_id, user_id):
    result = []
    try:
        item_list = await db.get_playground_list(workspace_id=workspace_id)

        # bookmark
        user_playground_bookmark_list = [playground_bookmark["playground_id"]
            for playground_bookmark in await db.get_user_playground_bookmark_list(user_id=user_id)]


        for item in item_list:
            # Dual 세션: 자식(프롬프트생성) playground 는 목록에서 숨김, 부모(추론)만 세션으로 노출.
            _dual = {}
            try:
                _dual = (json.loads(item.get("model") or "{}") or {}).get("dual") or {}
            except Exception:
                _dual = {}
            if _dual.get("role") == "prompt_child":
                continue
            status = await get_playground_status(playground_id=item.get("id"))
            # users
            if item.get("access") == 1:
                users=[]
            else:
                users = await db.get_user_playground_list(playground_id=item.get("id"))
            row = {
                "id" : item.get("id"),
                "name" : item.get("name"),
                "description" : item.get("description"),
                "create_datetime" : item.get("create_datetime"),
                "update_datetime" : item.get("update_datetime"),
                "access" : item.get("access"),
                "deploy_type" : item.get("deploy_type") or "cluster",
                "owner" : db.get_user(user_id=item.get("create_user_id")).get("name"),
                # 소유자 id. FE 는 owner 이름 문자열 대신 이걸로 소유자를 식별한다
                # (이름 매칭은 동명이인·개명에 취약하고, 미매치 시 수정 모달이
                #  undefined.name 접근으로 아예 열리지 않았다).
                "create_user_id" : item.get("create_user_id"),
                "status" : status.get("status") if status else TYPE.KUBE_POD_STATUS_STOP,
                "bookmark" : 1 if item.get("id") in user_playground_bookmark_list else 0,
                "users":  users,
            }
            # 이중 세션 부모면 FE 배지/모델태그용 메타 동봉.
            if _dual.get("mode") == "dual":
                row["mode"] = "dual"
                row["prompt_gen_playground_id"] = _dual.get("prompt_gen_playground_id")
                _pg_mid = _dual.get("prompt_gen_model_id")
                row["prompt_gen_model_id"] = _pg_mid
                # 카드 모델명 태그(📝/🤖) — best-effort(실패해도 목록 반환)
                try:
                    _model_json = json.loads(item.get("model") or "{}") or {}
                    _inf_mid = _model_json.get("model_allm_id")
                    _pg_row = await db.get_model(model_id=int(_pg_mid)) if _pg_mid else None
                    _inf_row = await db.get_model(model_id=int(_inf_mid)) if _inf_mid else None
                    row["prompt_gen_model_name"] = (_pg_row or {}).get("name")
                    row["inference_model_name"] = (_inf_row or {}).get("name")
                except Exception:
                    traceback.print_exc()
            result.append(row)
        result.sort(key=lambda x: x['id'], reverse=True)
    except Exception as e:
        traceback.print_exc()
    return result

# 배포 후보 조회에서 한 번에 상태를 물을 최대 행 수. get_playground_status 는 redis·kube·
# 외부 잡 트래커를 두드리므로 전부 동시에 던지면 그쪽이 먼저 무너진다. 목록 응답에 status 를
# 붙이는 게 목적이라 호출 자체를 없앨 수는 없고, 동시성만 묶는다.
RUNNING_DEPLOYMENT_STATUS_CONCURRENCY = 8


async def get_running_deployments(workspace_id, model_id=None, commit_id=None):
    """실행 중(running)인 배포만, 모델·커밋으로 걸러 반환한다.

    평가(생성용 배포 빌리기 / 원격 심판 고르기)처럼 "지금 답할 수 있는 배포"만 필요한
    소비자를 위한 read-model. 종전엔 화면이 전체 목록을 받아 status==='running' 으로
    걸렀는데, 그 목록은 행마다 상태를 실측하므로 워크스페이스가 커질수록 느려지고 모델
    기준 필터는 아예 없었다.

    N+1 은 두 단계로 다룬다.
      1) 후보를 SQL 에서 줄인다 — 워크스페이스 + model_allm_id/model_allm_commit_id +
         한 번도 배포 안 한 행 제외 + dual 자식 제외(db.get_running_playground_candidates).
         model_id 를 주면 보통 후보가 한 자릿수로 떨어진다.
      2) 남은 후보의 상태만 동시에 실측한다(세마포어로 상한).
    상태 실측 자체를 없애지는 못한다 — 배포 중지는 playground 행에 남지 않고(deployment
    JSON 이 재배포용으로 보존된다) 파드 실측으로만 알 수 있기 때문이다. 캐시를 두려면
    상태 조회 계층(get_playground_status)에 둬야 하고 그건 이 변경의 범위 밖이다.
    """
    rows = await db.get_running_playground_candidates(
        workspace_id=workspace_id, model_id=model_id, commit_id=commit_id) or []
    sem = asyncio.Semaphore(RUNNING_DEPLOYMENT_STATUS_CONCURRENCY)

    async def _status(pid):
        async with sem:
            try:
                return (await get_playground_status(playground_id=pid) or {}).get("status")
            except Exception:
                # 한 행의 상태 실측 실패가 목록 전체를 죽이지 않게(후보에서 빠질 뿐).
                traceback.print_exc()
                return None

    statuses = await asyncio.gather(*(_status(r.get("id")) for r in rows))
    result = []
    for row, status in zip(rows, statuses):
        if status != TYPE.KUBE_POD_STATUS_RUNNING:
            continue
        try:
            model_json = json.loads(row.get("model") or "{}") or {}
        except (TypeError, ValueError):
            model_json = {}
        dual = model_json.get("dual") or {}
        item = {
            "id": row.get("id"),
            "name": row.get("name"),
            "description": row.get("description"),
            "workspace_id": row.get("workspace_id"),
            "deploy_type": row.get("deploy_type") or "cluster",
            "access": row.get("access"),
            "status": status,
            "create_datetime": row.get("create_datetime"),
            "update_datetime": row.get("update_datetime"),
            # 무엇이 올라가 있는지 — 호출자가 되묻지 않아도 되게 함께 내린다.
            # 값은 model JSON 원본(문자열)이라 int 로 정규화한다. HF 직접 배포는 None.
            "model_id": _as_int_or_none(model_json.get("model_allm_id")),
            "commit_id": _as_int_or_none(model_json.get("model_allm_commit_id")),
            "model_type": model_json.get("model_type"),
            "model_huggingface_id": model_json.get("model_huggingface_id"),
            "serving_system": model_json.get("serving_system") or "vllm",
        }
        if dual.get("mode") == "dual":
            item["mode"] = "dual"
            item["prompt_gen_playground_id"] = dual.get("prompt_gen_playground_id")
        result.append(item)
    return result


def _as_int_or_none(value):
    """model JSON 의 id 는 문자열(str(model_id))로 저장된다 — 경계에서 int 로 되돌린다."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def get_deployment_targets(workspace_id, user_id):
    """배포 타겟 통합 read-model — cluster/edge/standalone 3종을 정규화 envelope 로 반환.
    3종 모두 playground row(deploy_type 판별자)이며 workspace 스코프 — deploy_type 로 envelope 디스패치.
    edge 도 별도 playground 배포(deploy_type='edge')이며, 실제 배포 디바이스(edge_worker)는
    상세 '배포' 탭에서 선택하는 타겟이지 목록 항목이 아니다. 별도 admin 게이트 없음(workspace 스코프 목록)."""
    targets = []
    try:
        # cluster (활성 = Playground, llm>0). 기존 목록 서비스 재사용 → status 재파생 안 함.
        # workspace_id 는 목록 행에 없어 파라미터로 주입(target_details 정합).
        cluster_list = await get_playground_list(workspace_id=workspace_id, user_id=user_id)
        # deploy_type 로 cluster/edge/standalone envelope 디스패치 — 3종 모두 playground row(workspace 스코프).
        #   edge 도 별도 playground 로 관리(배포 디바이스=edge_worker 는 상세 '배포' 탭에서 선택하는 타겟, 목록 항목 아님).
        for dep in cluster_list:
            dt = dep.get("deploy_type") or "cluster"
            if dt == deployment_envelope.TARGET_STANDALONE:
                targets.append(deployment_envelope.standalone_envelope(dep, workspace_id=workspace_id))
            elif dt == deployment_envelope.TARGET_EDGE:
                targets.append(deployment_envelope.edge_deploy_envelope(dep, workspace_id=workspace_id))
            else:
                targets.append(deployment_envelope.cluster_envelope(dep, workspace_id=workspace_id))
    except Exception as e:
        traceback.print_exc()
    return targets

async def get_playground_info(playground_id):
    """
    플레이그라운드 목록에서 수정시 쓰는 info
    """
    result = dict()
    try:
        item = await db.get_playground(playground_id=playground_id)
        if item.get("access") == 1:
            users=[]
        else:
            users = await db.get_user_playground_list(playground_id=playground_id)
        result = {
            "id" : item.get("id"),
            "workspace_id" : item.get("workspace_id"),
            "name" : item.get("name"),
            "description" : item.get("description"),
            "owner" : db.get_user(user_id=item.get("create_user_id")).get("name"),
            # 목록 응답과 동일하게 소유자 id 를 함께 내려 FE 가 이름이 아닌 id 로 식별하게 한다.
            "create_user_id" : item.get("create_user_id"),
            "access" : item.get("access"),
            "create_datetime" : item.get("create_datetime"),
            "update_datetime" : item.get("update_datetime"),
            "users":  users,
        }
    except:
        traceback.print_exc()
    return result


async def create_playground(workspace_id, name, description, access, user_name=None, owner_id=None, users_id=[], deploy_type='cluster'):
    try:
        owner_id = owner_id if owner_id else db.get_user(user_name=user_name).get("id")
        # playground
        res, playground_id = await db.insert_playground(workspace_id=workspace_id, name=name, description=description, create_user_id=owner_id, access=access, deploy_type=deploy_type)
        if not res:
            return False 

        # user_playground
        users_id.append(owner_id)
        playgrounds_id = [playground_id]*len(users_id)
        insert_user_playground_result, message = await db.insert_user_playground_list(
            playgrounds_id=playgrounds_id, users_id=users_id)
        # 생성 id 반환 — FE 가 목록 재조회+이름매칭(동명 경합 시 타 배포로 진입) 없이 바로 상세 이동.
        return {"playground_id": playground_id}
    except Exception as e:
        traceback.print_exc()
        return False

async def _resolve_deploy_instance(workspace_id, min_vram_gb, model_gpu_count):
    """호출자가 인스턴스 표를 몰라도 되게, 이 배포를 감당할 인스턴스를 서버가 고른다.

    학습 데이터 파이프라인의 자동 배포는 "이 모델을 띄워라"만 알지 인스턴스 id 를 모른다.
    거절은 **띄우기 전에** 해야 한다 — 배포가 올라간 뒤 OOM 으로 죽으면 사용자에게는
    "실패"만 보이고 원인(VRAM 부족)이 남지 않는다.

    고르는 기준:
      1. GPU 인스턴스만 — CPU 인스턴스에 vLLM 을 올릴 수 없다.
      2. `gpu_allocate x GPU 한 장 VRAM x 할당 장수` 가 min_vram_gb 이상.
      3. 조건을 만족하는 것 중 **가장 작은 것** — 큰 인스턴스를 먼저 먹으면 뒤이어 올
         큰 모델이 갈 곳을 잃는다(생성+심사 2개를 연달아 띄운다).
      4. 그중 지금 여유가 있는 것.
    """
    rows = await db_dashboard.get_workspace_instance_capacity(workspace_id) or []
    gpu_rows = [r for r in rows if r.get("instance_type") == TYPE.INSTANCE_TYPE_GPU]
    if not gpu_rows:
        raise Exception("워크스페이스에 GPU 인스턴스가 없습니다 — 관리자에게 할당을 요청하세요")

    gpu_count = max(int(model_gpu_count or 1), 1)
    scored = []
    for r in gpu_rows:
        per_gpu_gb = float(r.get("gpu_memory_mb") or 0) / 1024.0
        # gpu_allocate 는 인스턴스 한 개당 장수. 여러 장을 요청하면 그만큼 합산된다.
        total_gb = per_gpu_gb * float(r.get("gpu_allocate") or 0) * gpu_count
        scored.append((total_gb, r))
    scored.sort(key=lambda x: x[0])

    need = float(min_vram_gb or 0)
    fits = [(gb, r) for gb, r in scored if gb >= need] if need else scored
    if not fits:
        best_gb, best = scored[-1]
        raise Exception(
            f"이 모델은 VRAM {int(need)}GB 가 필요한데 워크스페이스에서 가장 큰 인스턴스가 "
            f"{best.get('instance_name')} (GPU {gpu_count}장 합산 {best_gb:.0f}GB)입니다. "
            f"더 작은 모델을 고르거나 GPU 할당을 늘리세요")

    last_reason = None
    for gb, r in fits:
        info = await get_workspace_instance_total_info(
            instance_id=r["id"], workspace_id=workspace_id,
            instance_allocate=r.get("instance_allocate") or 0)
        if info.get("gpu_available"):
            return r["id"]
        last_reason = f"{r.get('instance_name')} 는 지금 GPU 여유가 없습니다"
    raise Exception(
        (last_reason or "가용 인스턴스가 없습니다")
        + " — 다른 배포가 끝나기를 기다리거나 실행 중인 배포를 정리하세요")


async def pipeline_deploy(workspace_id, model_id, user_name, model_instance_id,
                          model_commit_id=None, name=None,
                          model_instance_count=1, model_gpu_count=1,
                          prompt_system_message=None,
                          model_huggingface_id=None, min_vram_gb=None):
    """파이프라인(통합 파이프라인 llm_deploy 노드)의 s2s 클러스터 배포(spec #4).
    create → 옵션(모델 바인딩 + deployment_run) → start 를 원자적으로 수행한다.
    배포 로직 자체는 기존 서비스 함수(update_playground_options / start_playground)를
    그대로 재사용(재구현 X) — FE 수동 배포와 동일 경로(internal helm / external 분기 포함).
    반환: {"playground_id": ...}. 상태는 호출측이 GET /playgrounds/status/{id} 로 폴링."""
    user = db.get_user(user_name=user_name)
    if not user:
        raise Exception(f"deploy user not found: {user_name}")
    owner_id = user.get("id")

    # 배포 대상은 학습완료 모델(allm commit) 또는 huggingface 저장소 둘 중 하나.
    # 라우터 DTO 가 택일을 강제하지만, 서비스 함수를 직접 부르는 경로도 막아 둔다.
    is_hf = bool(model_huggingface_id)
    if is_hf == bool(model_id):
        raise Exception("model_id 와 model_huggingface_id 중 정확히 하나를 지정하세요")

    if not is_hf:
        # commit 미지정 시 모델 latest_commit_id 로 해석 — internal helm 배포 경로
        # (utils.llm_deployment)는 model_type=commit 에서 commit 을 무조건 deref 하므로
        # None 이면 크래시. external 경로는 자체 폴백이 있으나 양쪽 안전하게 여기서 채운다.
        if model_commit_id is None:
            model_row = await db.get_model(model_id=model_id)
            model_commit_id = (model_row or {}).get("latest_commit_id")
        if model_commit_id is None:
            raise Exception(f"model {model_id} has no commit to deploy")

    # 인스턴스 미지정(자동 배포 호출자)이면 서버가 고른다. VRAM 이 모자라면 여기서 끊긴다
    # — playground 를 만들기 전에 끊어야 정리할 찌꺼기가 남지 않는다.
    if not model_instance_id:
        model_instance_id = await _resolve_deploy_instance(
            workspace_id, min_vram_gb, model_gpu_count)

    deploy_name = name or (f"pipeline-deploy-hf-{model_huggingface_id.split('/')[-1]}"[:60]
                           if is_hf else f"pipeline-deploy-model{model_id}")
    res, playground_id = await db.insert_playground(
        workspace_id=workspace_id, name=deploy_name,
        description="pipeline auto-deploy", create_user_id=owner_id, access=1)
    if not res:
        raise Exception("create playground failed")

    # 옵션/start 부분 실패 시 orphan playground 방지 — 보상 정리(delete_playground 재사용).
    try:
        await db.insert_user_playground_list(playgrounds_id=[playground_id], users_id=[owner_id])
        # 모델 바인딩 + deployment_run 세팅(start 전제) — 기존 옵션 저장 경로 재사용.
        await update_playground_options(
            playground_id=playground_id, is_rag=False,
            # 시스템 프롬프트가 주어지면 run_prompt=True 로 서빙이 chat template 에 반영(없으면 현행 False).
            is_prompt=bool(prompt_system_message), accelerator=False,
            model_type="huggingface" if is_hf else "commit",
            model_huggingface_id=model_huggingface_id if is_hf else None,
            model_huggingface_token=None,
            model_allm_id=None if is_hf else str(model_id),
            model_allm_commit_id=None if is_hf else str(model_commit_id),
            # 샘플링 파라미터 기본값 — None 이면 배포 파드가 0 으로 vLLM SamplingParams 에 넘겨
            # ValueError(repetition_penalty>0, top_p in (0,1]) 로 서빙 lifespan 크래시. 유효 기본값 고정.
            model_info=None, model_temperature=0.7, model_top_p=1.0, model_top_k=-1,
            model_repetition_penalty=1.0, model_max_new_tokens=512,
            rag_id=None, rag_chunk_max=0, prompt_id=None, prompt_name=None,
            prompt_commit_name=None, prompt_system_message=prompt_system_message,
            prompt_user_message=None)
        # 서빙 시작(자원 할당) — 기존 start 경로 재사용.
        await start_playground(
            user_name=user_name, playground_id=playground_id,
            model_instance_id=model_instance_id, model_instance_count=model_instance_count,
            model_gpu_count=model_gpu_count,
            embedding_instance_id=0, embedding_instance_count=0, embedding_gpu_count=0,
            reranker_instance_id=0, reranker_instance_count=0, reranker_gpu_count=0,
            restart=False)
    except Exception:
        try:
            await delete_playground(id_list=[playground_id])
        except Exception:
            traceback.print_exc()
        raise

    return {"playground_id": playground_id}

async def _link_dual_session(parent_playground_id, child_playground_id, prompt_gen_model_id):
    """이중 세션 링크 — 부모(추론) playground.model.dual ← 자식(프롬프트생성) 참조,
    자식 playground.model.dual ← 부모 참조. 기존 model 바인딩은 보존(dual 키만 병합).
    prompt_gen 은 여기서 서버 파생 링크로 고정 → 추론 시 request-supplied 벡터 제거."""
    parent = await db.get_playground(playground_id=parent_playground_id)
    child = await db.get_playground(playground_id=child_playground_id)
    if not parent or not child:
        raise Exception("dual session link: playground not found")
    parent_model = json.loads(parent.get("model") or "{}")
    parent_model["dual"] = {
        "mode": "dual",
        "prompt_gen_playground_id": child_playground_id,
        "prompt_gen_model_id": prompt_gen_model_id,
    }
    if not await db.update_playground(playground_id=parent_playground_id, model=json.dumps(parent_model)):
        raise Exception("dual session link failed (parent)")
    child_model = json.loads(child.get("model") or "{}")
    child_model["dual"] = {"role": "prompt_child", "parent_playground_id": parent_playground_id}
    if not await db.update_playground(playground_id=child_playground_id, model=json.dumps(child_model)):
        raise Exception("dual session link failed (child)")

async def create_dual_session(workspace_id, name, user_name,
                              prompt_gen_model_id, inference_model_id, model_instance_id,
                              prompt_gen_commit_id=None, inference_commit_id=None,
                              model_instance_count=1, model_gpu_count=1,
                              prompt_gen_gpu_count=None, inference_gpu_count=None):
    """이중모델 추론 세션 co-provision(WBS 추론 4.2). 프롬프트생성 모델(LLM1)+추론 모델(LLM2)을
    각각 기존 배포 경로(pipeline_deploy: create→bind→start, external/internal 분기 포함)로 올리고
    부모(추론)-자식(프롬프트생성) playground 를 링크한다. 부분실패 시 이미 만든 것 롤백.
    자원 블록은 두 모델에 각각 적용하되 GPU 는 모델별 개별 지정(prompt_gen/inference_gpu_count,
    생략 시 model_gpu_count 폴백). 반환: {session_playground_id, prompt_gen_playground_id}."""
    if not name or not isinstance(name, str) or not name.strip():
        raise Exception("Error: session name is required")
    if prompt_gen_model_id == inference_model_id:
        # 같은 모델을 LLM1/LLM2 양쪽으로 = 자원 낭비 + 자기체인(의미 없음). 명시 차단.
        raise Exception("Error: prompt-gen and inference model must differ")
    # 자원값 정합
    if model_instance_count is not None and model_instance_count < 1:
        raise Exception("Error: model_instance_count must be >= 1")
    if model_gpu_count is not None and model_gpu_count < 0:
        raise Exception("Error: model_gpu_count must be >= 0")
    # 모델별 GPU 오버라이드(회의결정: LLM1/LLM2 각각 독립 GPU 수). 생략 시 공통 model_gpu_count 폴백(하위호환).
    gpu1 = prompt_gen_gpu_count if prompt_gen_gpu_count is not None else model_gpu_count
    gpu2 = inference_gpu_count if inference_gpu_count is not None else model_gpu_count
    for _g in (gpu1, gpu2):
        if _g is not None and _g < 0:
            raise Exception("Error: per-model gpu count must be >= 0")
    # LLM1(프롬프트 생성)=텍스트 출력 필요 → 내부 텍스트만. LLM2(추론)=외부 SDS(VLM) 허용(text→SDS).
    #   교차테넌트 모델 배포 차단(워크스페이스 일치). 메시지 통합(존재/타워크스페이스 열거 오라클 회피).
    for _mid, _is_prompt in ((prompt_gen_model_id, True), (inference_model_id, False)):
        _m = await db.get_model(model_id=_mid)
        if not _m or _m.get("workspace_id") != workspace_id:
            raise Exception("Error: invalid model selection")
        if _is_prompt and (_m.get("training_type") or "") == "external":
            raise Exception("Error: prompt-gen model(LLM1) must be an internal text model")

    # playground.name 은 VARCHAR(32) → 자식 배포명이 초과하지 않게 base 를 절단(-promptgen/-infer 접미사 여유).
    _base = name.strip()[:20]

    # 1) 프롬프트 생성 모델(LLM1) 배포 — pipeline_deploy 가 자체 원자성/롤백 보유
    pg1 = (await pipeline_deploy(
        workspace_id=workspace_id, model_id=prompt_gen_model_id, user_name=user_name,
        model_instance_id=model_instance_id, model_commit_id=prompt_gen_commit_id,
        name=f"{_base}-promptgen", model_instance_count=model_instance_count,
        model_gpu_count=gpu1)).get("playground_id")

    # 2) 추론 모델(LLM2) 배포 — 실패 시 LLM1 롤백
    try:
        pg2 = (await pipeline_deploy(
            workspace_id=workspace_id, model_id=inference_model_id, user_name=user_name,
            model_instance_id=model_instance_id, model_commit_id=inference_commit_id,
            name=f"{_base}-infer", model_instance_count=model_instance_count,
            model_gpu_count=gpu2)).get("playground_id")
    except Exception:
        traceback.print_exc()
        try:
            await delete_playground(id_list=[pg1])
        except Exception:
            traceback.print_exc()
        raise

    # 3) 부모(추론)-자식(프롬프트생성) 링크 — 실패 시 양쪽 롤백
    try:
        await _link_dual_session(parent_playground_id=pg2, child_playground_id=pg1,
                                 prompt_gen_model_id=prompt_gen_model_id)
    except Exception:
        traceback.print_exc()
        try:
            await delete_playground(id_list=[pg1, pg2])
        except Exception:
            traceback.print_exc()
        raise

    return {"session_playground_id": pg2, "prompt_gen_playground_id": pg1}

async def _create_dual_shell_with_metadata(workspace_id, name, user_name, description,
                                           access, owner_id, users_id):
    """이중모델 세션 '셸' 생성(단일 create_playground 대칭) — 모델/자원 없이 부모 playground 행만
    만들고 model.dual={"mode":"dual"} 마커를 스탬프한다(deployment 미설정 → 미프로비저닝 상태).
    단일과 같은 playground 행이므로 설명/공개범위/소유자/접근 사용자를 같은 시점에 저장한다."""
    shell_name, child_name = _dual_shell_names(name)
    # 단일/edge/standalone/dual 모두 같은 playground 테이블을 쓰므로 유형 필터 없이 검사한다.
    # UNIQUE migration 없이도 대부분의 충돌을 생성 전에 사용자 친화적 오류로 돌려주기 위한 선검사다.
    await _ensure_dual_names_available(
        workspace_id=workspace_id, shell_name=shell_name, child_name=child_name)
    user = db.get_user(user_name=user_name)
    if not user:
        raise Exception(f"deploy user not found: {user_name}")
    owner_id = owner_id if owner_id else user.get("id")
    res, playground_id = await db.insert_playground(
        workspace_id=workspace_id, name=shell_name, description=description or "",
        create_user_id=owner_id, access=access, deploy_type='cluster')
    if not res:
        raise Exception("create dual shell failed")
    try:
        # 소유자는 private 사용자 선택에서 빠져도 항상 접근 가능해야 한다.
        member_ids = list(dict.fromkeys([*(users_id or []), owner_id]))
        await db.insert_user_playground_list(
            playgrounds_id=[playground_id] * len(member_ids), users_id=member_ids)
        # dual 마커 스탬프 — 상세(구성/배포)가 이중 셸임을 인지하는 신호. deployment 미설정 = 미프로비저닝.
        if not await db.update_playground(playground_id=playground_id,
                                          model=json.dumps({"dual": {"mode": "dual"}})):
            raise Exception("dual shell mark failed")
    except Exception:
        traceback.print_exc()
        try:
            await delete_playground(id_list=[playground_id])
        except Exception:
            traceback.print_exc()
        raise
    return {"session_playground_id": playground_id}

async def create_dual_shell(workspace_id, name, user_name, access=1, owner_id=None):
    """기존 서비스 호출자의 시그니처를 보존하는 이중 셸 생성 어댑터."""
    return await _create_dual_shell_with_metadata(
        workspace_id=workspace_id, name=name, user_name=user_name,
        description="", access=access, owner_id=owner_id, users_id=[])

# 이중 역할별 생성 파라미터 기본값 — 종전 하드코딩과 동일(미지정 시 동작 불변).
DUAL_DEFAULT_MODEL_PARAMS = {
    "temperature": 0.7, "top_p": 1.0, "top_k": -1,
    "repetition_penalty": 1.0, "max_new_tokens": 512,
}

def _resolve_dual_model_params(params):
    """dto.DualModelParams | dict | None → 5종 파라미터 dict. None 필드는 기본값 유지.
    이 값은 추론 요청이 아니라 배포 시점에 llm_deployment 의 param_* 로 주입된다."""
    resolved = dict(DUAL_DEFAULT_MODEL_PARAMS)
    if not params:
        return resolved
    raw = params if isinstance(params, dict) else params.dict()
    for key in resolved:
        value = raw.get(key)
        if value is not None:
            resolved[key] = value
    return resolved

async def _save_dual_model_options(playground_id, model_id, commit_id, params=None):
    """단일 PUT /options와 같은 모델 바인딩을 이중 컴포넌트 행에 적용한다.
    파라미터는 역할마다 달라야 하므로 호출부가 LLM1/LLM2 값을 각각 넘긴다(종전엔 양쪽 하드코딩)."""
    p = _resolve_dual_model_params(params)
    saved = await update_playground_options(
        playground_id=playground_id, is_rag=False, is_prompt=False, accelerator=False,
        model_type="commit", model_huggingface_id=None, model_huggingface_token=None,
        model_allm_id=str(model_id), model_allm_commit_id=str(commit_id),
        model_info=None, model_temperature=p["temperature"], model_top_p=p["top_p"],
        model_top_k=p["top_k"], model_repetition_penalty=p["repetition_penalty"],
        model_max_new_tokens=p["max_new_tokens"],
        rag_id=None, rag_chunk_max=0, prompt_id=None, prompt_name=None,
        prompt_commit_name=None, prompt_system_message=None, prompt_user_message=None)
    if not saved:
        raise Exception("dual session model option save failed")

async def configure_dual_session(playground_id, user_name,
                                 prompt_gen_model_id, inference_model_id, model_instance_id,
                                 prompt_gen_commit_id=None, inference_commit_id=None,
                                 model_instance_count=1, model_gpu_count=1,
                                 prompt_gen_gpu_count=None, inference_gpu_count=None,
                                 prompt_gen_params=None, inference_params=None):
    """이중 세션 구성 저장 — child upsert + 양쪽 모델 bind + 링크만 수행하고 배포는 시작하지 않는다.
    prompt_gen_params/inference_params 는 역할별 생성 파라미터(생략 시 기본값)."""
    if prompt_gen_model_id == inference_model_id:
        raise Exception("Error: prompt-gen and inference model must differ")
    if model_instance_count is not None and model_instance_count < 1:
        raise Exception("Error: model_instance_count must be >= 1")
    if model_gpu_count is not None and model_gpu_count < 0:
        raise Exception("Error: model_gpu_count must be >= 0")
    gpu1 = prompt_gen_gpu_count if prompt_gen_gpu_count is not None else model_gpu_count
    gpu2 = inference_gpu_count if inference_gpu_count is not None else model_gpu_count
    for _g in (gpu1, gpu2):
        if _g is not None and _g < 0:
            raise Exception("Error: per-model gpu count must be >= 0")

    parent = await db.get_playground(playground_id=playground_id)
    if not parent:
        raise Exception("Error: dual session not found")
    workspace_id = parent.get("workspace_id")
    parent_model = json.loads(parent.get("model") or "{}")
    parent_dual = parent_model.get("dual") or {}
    if parent_dual.get("mode") != "dual":
        raise Exception("Error: not a dual session shell")

    # 단일 배포 모달이 사용하는 동일 instance 목록의 총량(instance 수 × 장비당 GPU)을
    # 두 컴포넌트가 공유한다. pod 수는 run_worker가 GPU 클러스터링으로 파생하므로 여기서
    # '이중=2 pod'로 가정하지 않고 요청 GPU 합계만 검증한다.
    instance_rows = db.get_workspace_instance_list(workspace_id=workspace_id)
    selected_instance = next(
        (row for row in instance_rows
         if str(row.get("instance_id")) == str(model_instance_id)),
        None,
    )
    if not selected_instance:
        raise Exception("Error: invalid instance selection")
    gpu_capacity = int(selected_instance.get("instance_allocate") or 0) * int(
        selected_instance.get("gpu_allocate") or 0)
    requested_gpu = int(gpu1 or 0) + int(gpu2 or 0)
    if requested_gpu > gpu_capacity:
        raise Exception(
            f"사용 가능한 GPU 수를 초과했습니다 ({requested_gpu}/{gpu_capacity})")

    # UI 플래그와 동일하게 stop에서만 편집 허용한다. 한쪽만 멈춘 저하 상태도
    # installing으로 집계되므로 구성 덮어쓰기 전에 명시적으로 중지해야 한다.
    current_status = await get_playground_status(playground_id=playground_id)
    if current_status.get("status") != TYPE.KUBE_POD_STATUS_STOP:
        raise Exception("배포 중에는 구성을 변경할 수 없습니다")

    model_rows = {}
    for _mid, _is_prompt in ((prompt_gen_model_id, True), (inference_model_id, False)):
        _m = await db.get_model(model_id=_mid)
        if not _m or _m.get("workspace_id") != workspace_id:
            raise Exception("Error: invalid model selection")
        if _is_prompt and (_m.get("training_type") or "") == "external":
            raise Exception("Error: prompt-gen model(LLM1) must be an internal text model")
        model_rows[_mid] = _m

    if prompt_gen_commit_id is None:
        prompt_gen_commit_id = model_rows[prompt_gen_model_id].get("latest_commit_id")
    if inference_commit_id is None:
        inference_commit_id = model_rows[inference_model_id].get("latest_commit_id")
    if prompt_gen_commit_id is None:
        raise Exception(f"model {prompt_gen_model_id} has no commit to deploy")
    if inference_commit_id is None:
        raise Exception(f"model {inference_model_id} has no commit to deploy")

    child_id = parent_dual.get("prompt_gen_playground_id")
    child = await db.get_playground(playground_id=child_id) if child_id else None
    if child_id and (not child or child.get("workspace_id") != workspace_id):
        raise Exception("Error: invalid dual session link")

    created_child = False
    if not child:
        # 최초 구성에서만 child 행을 만든다. 재구성은 반드시 위에서 찾은 기존 id를 재사용한다.
        _, child_name = _dual_shell_names(parent.get("name"))
        # 셸 생성 뒤 구성 전까지 생긴 동명 배포도 child INSERT 직전에 다시 잡는다.
        await _ensure_dual_names_available(
            workspace_id=workspace_id, shell_name=parent.get("name") or "",
            child_name=child_name, check_shell=False, exclude_ids=[playground_id])
        res, child_id = await db.insert_playground(
            workspace_id=workspace_id, name=child_name,
            description=parent.get("description") or "",
            create_user_id=parent.get("create_user_id"), access=parent.get("access"),
            deploy_type='cluster')
        if not res:
            raise Exception("create prompt generator playground failed")
        created_child = True
        parent_members = await db.get_user_playground_list(playground_id=playground_id)
        member_ids = list(dict.fromkeys([
            *[row.get("user_id") for row in parent_members if row.get("user_id")],
            parent.get("create_user_id"),
        ]))
        await db.insert_user_playground_list(
            playgrounds_id=[child_id] * len(member_ids), users_id=member_ids)
        child = await db.get_playground(playground_id=child_id)

    # 기존 stopped 구성을 갱신하다 실패하면 양쪽 모델/배포 설정을 원복한다.
    # 신규 child만 삭제 가능하며, 링크된 기존 child는 어떤 실패 경로에서도 삭제하지 않는다.
    snapshot_columns = ("model", "model_parameter", "rag", "prompt", "deployment", "accelerator")
    parent_snapshot = {key: parent.get(key) for key in snapshot_columns}
    child_snapshot = {key: child.get(key) for key in snapshot_columns}
    try:
        await _save_dual_model_options(
            playground_id=child_id, model_id=prompt_gen_model_id,
            commit_id=prompt_gen_commit_id, params=prompt_gen_params)
        await _save_dual_model_options(
            playground_id=playground_id, model_id=inference_model_id,
            commit_id=inference_commit_id, params=inference_params)
        await _link_dual_session(
            parent_playground_id=playground_id, child_playground_id=child_id,
            prompt_gen_model_id=prompt_gen_model_id)

        # configure/start 사이에도 자원 선택이 유지되도록 기존 model.dual JSON에 저장한다.
        configured_parent = await db.get_playground(playground_id=playground_id)
        configured_model = json.loads(configured_parent.get("model") or "{}")
        configured_dual = configured_model.get("dual") or {}
        configured_dual["resources"] = [
            {
                "role": "prompt_gen", "model_instance_id": model_instance_id,
                "model_instance_count": model_instance_count, "model_gpu_count": gpu1,
            },
            {
                "role": "inference", "model_instance_id": model_instance_id,
                "model_instance_count": model_instance_count, "model_gpu_count": gpu2,
            },
        ]
        configured_model["dual"] = configured_dual
        if not await db.update_playground(
                playground_id=playground_id, model=json.dumps(configured_model)):
            raise Exception("dual session resource save failed")
    except Exception:
        traceback.print_exc()
        await db.update_playground(playground_id=playground_id, **parent_snapshot)
        if created_child:
            # 아직 배포 전인 신규 행만 직접 정리한다. dual-aware delete를 쓰면
            # 부분 링크 상태에서 부모까지 삭제할 수 있으므로 이 보상 경로에는 부적합하다.
            await db.delete_playground(id_list=[child_id])
        else:
            await db.update_playground(playground_id=child_id, **child_snapshot)
        raise

    return {
        "session_playground_id": playground_id,
        "prompt_gen_playground_id": child_id,
    }

async def start_dual_session(playground_id, user_name):
    """저장된 이중 구성을 child(LLM1) → parent(LLM2) 순서로 시작한다."""
    parent = await db.get_playground(playground_id=playground_id)
    if not parent:
        raise Exception("Error: dual session not found")
    parent_dual = (json.loads(parent.get("model") or "{}") or {}).get("dual") or {}
    child_id = parent_dual.get("prompt_gen_playground_id")
    if parent_dual.get("mode") != "dual" or not child_id:
        raise Exception("이중모델 구성을 먼저 저장해 주세요")
    current_status = await get_playground_status(playground_id=playground_id)
    if current_status.get("status") != TYPE.KUBE_POD_STATUS_STOP:
        raise Exception("이미 배포 중인 이중모델 세션입니다")

    resources = {
        row.get("role"): row for row in (parent_dual.get("resources") or [])
        if isinstance(row, dict)
    }
    prompt_resource = resources.get("prompt_gen")
    inference_resource = resources.get("inference")
    if not prompt_resource or not inference_resource:
        raise Exception("이중모델 자원 구성을 먼저 저장해 주세요")

    async def _start(playground_id, resource):
        await start_playground(
            user_name=user_name, playground_id=playground_id,
            model_instance_id=resource.get("model_instance_id"),
            model_instance_count=resource.get("model_instance_count"),
            model_gpu_count=resource.get("model_gpu_count"),
            embedding_instance_id=0, embedding_instance_count=0, embedding_gpu_count=0,
            reranker_instance_id=0, reranker_instance_count=0, reranker_gpu_count=0,
            restart=False)

    try:
        await _start(child_id, prompt_resource)
        await _start(playground_id, inference_resource)
    except Exception as start_error:
        traceback.print_exc()
        # 부분 시작을 성공으로 남기지 않는다. Phase 3의 dual-safe restart는 설계 문서 §5.2에서 별도 구현.
        child_stopped = await stop_playground(playground_id=child_id, _dual_cascaded=True)
        parent_stopped = await stop_playground(playground_id=playground_id, _dual_cascaded=True)
        if not child_stopped or not parent_stopped:
            raise Exception("이중모델 시작 실패 후 배포 중지에도 실패했습니다") from start_error
        raise
    return {
        "session_playground_id": playground_id,
        "prompt_gen_playground_id": child_id,
    }


async def _resolve_dual_parent(playground_id):
    """부모/자식 어느 id를 받아도 저장 링크에서 부모를 먼저 확정한다."""
    requested = await db.get_playground(playground_id=playground_id)
    if not requested:
        raise Exception("Error: dual session not found")
    dual = (json.loads(requested.get("model") or "{}") or {}).get("dual") or {}
    parent_id = dual.get("parent_playground_id") if dual.get("role") == "prompt_child" else playground_id
    parent = await db.get_playground(playground_id=parent_id)
    if not parent:
        raise Exception("Error: dual session parent not found")
    parent_dual = (json.loads(parent.get("model") or "{}") or {}).get("dual") or {}
    child_id = parent_dual.get("prompt_gen_playground_id")
    if parent_dual.get("mode") != "dual" or not child_id:
        raise Exception("Error: not a configured dual session")
    return parent_id, child_id


async def restart_dual_session(playground_id, user_name):
    """이중 세션 전체를 child→parent 순서로 재기동하고 부분 실패는 완전 정지로 보상한다."""
    parent_id, child_id = await _resolve_dual_parent(playground_id)
    if not await stop_playground(playground_id=parent_id):
        raise Exception("이중모델 재시작을 위한 전체 중지에 실패했습니다")
    try:
        return await start_dual_session(playground_id=parent_id, user_name=user_name)
    except Exception as restart_error:
        # start_dual_session도 보상하지만, 예외 경로가 늘어나도 최종 상태가 정직한 stop이도록
        # 두 행을 각각 다시 확인 가능한 동일 stop 경로로 정리한다.
        child_stopped = await stop_playground(
            playground_id=child_id, _dual_cascaded=True)
        parent_stopped = await stop_playground(
            playground_id=parent_id, _dual_cascaded=True)
        if not child_stopped or not parent_stopped:
            raise Exception("이중모델 재시작 실패 후 전체 중지에도 실패했습니다") from restart_error
        raise


async def provision_dual_session(playground_id, user_name,
                                 prompt_gen_model_id, inference_model_id, model_instance_id,
                                 prompt_gen_commit_id=None, inference_commit_id=None,
                                 model_instance_count=1, model_gpu_count=1,
                                 prompt_gen_gpu_count=None, inference_gpu_count=None,
                                 prompt_gen_params=None, inference_params=None):
    """하위호환 래퍼 — 새 configure + start 2단 경로를 순서대로 호출한다."""
    await configure_dual_session(
        playground_id=playground_id, user_name=user_name,
        prompt_gen_model_id=prompt_gen_model_id, inference_model_id=inference_model_id,
        model_instance_id=model_instance_id,
        prompt_gen_commit_id=prompt_gen_commit_id, inference_commit_id=inference_commit_id,
        model_instance_count=model_instance_count, model_gpu_count=model_gpu_count,
        prompt_gen_gpu_count=prompt_gen_gpu_count, inference_gpu_count=inference_gpu_count,
        prompt_gen_params=prompt_gen_params, inference_params=inference_params)
    return await start_dual_session(playground_id=playground_id, user_name=user_name)

async def delete_playground(id_list):
    try:
        # Dual 세션 삭제 시 짝(부모↔자식) playground 도 함께 정리(orphan 방지).
        # 부모/자식 어느 쪽 id 로 지워도 partner 를 편입(2-노드 링크라 1-hop 이면 충분).
        id_list = list(id_list)
        for playground_id in list(id_list):
            try:
                _pg = await db.get_playground(playground_id=playground_id)
                if not _pg:
                    continue
                _dual = (json.loads(_pg.get("model") or "{}") or {}).get("dual") or {}
                _partner = _dual.get("prompt_gen_playground_id") or _dual.get("parent_playground_id")
                if _partner and _partner not in id_list:
                    id_list.append(_partner)
            except Exception:
                traceback.print_exc()
        # 배포 삭제
        # Kong 합성 리소스 정리에 실패한 항목 — 행을 남겨 다음 시도에서 재정리한다(아래 참조).
        _composite_cleanup_failed_ids = []
        for playground_id in id_list:
            playground_info = await db.get_playground(playground_id=playground_id)
            if playground_info is None:
                continue
            _component_dual = (
                json.loads(playground_info.get("model") or "{}") or {}
            ).get("dual") or {}
            _requires_composite_cleanup = (
                _component_dual.get("mode") == "dual"
                or _component_dual.get("role") == "prompt_child"
            )
            playground_deployment_info = playground_info.get("deployment")
            if playground_deployment_info is None:
                continue
            playground_deployment_info = json.loads(playground_deployment_info)

            playground_deployment_id = playground_deployment_info.get("deployment_playground_id")
            playground_embedding_id = playground_deployment_info.get("deployment_embedding_id")
            playground_reranker_id = playground_deployment_info.get("deployment_reranker_id")

            # External partner job 이 살아있으면 cancel 먼저 — 그러지 않으면
            # helm release / partner pod 가 orphan 으로 남는다 (codex High-1).
            external_job_id = playground_deployment_info.get("external_job_id")
            if external_job_id:
                try:
                    await cancel_infer_job(external_job_id)
                except ExternalInferError:
                    # BFF 404 (이미 정리됨) 등은 무시 — best-effort cleanup
                    traceback.print_exc()
            else:
                # 내부 배포: helm 릴리스가 살아있으면 uninstall 먼저 — DB 레코드만 지우면
                # helm 릴리스+GPU 파드가 orphan 으로 남는다(외부 cancel 과 대칭, stop_playground 동형).
                # STOP 없이 실행 중 playground 를 DELETE 하는 경로 방어(GPU 누수 차단). uninstall_worker
                # 는 deployment 레코드를 읽어 helm 이름을 만들므로 반드시 delete_deployments 前에 호출.
                # 이미 stop 된 경우 helm 릴리스가 없어 uninstall 이 no-op(멱등) — best-effort.
                rag_id = None
                if playground_embedding_id or playground_reranker_id:
                    playground_rag_info = playground_info.get("rag")
                    if playground_rag_info is not None:
                        rag_id = json.loads(playground_rag_info).get("rag_id")
                if playground_deployment_id is not None:
                    try:
                        await llm_deployment.uninstall_worker(deployment_id=playground_deployment_id, llm_type="playground", llm_id=playground_id)
                    except Exception:
                        traceback.print_exc()
                if playground_embedding_id is not None:
                    try:
                        await llm_deployment.uninstall_worker(deployment_id=playground_embedding_id, llm_type=TYPE.PLAYGROUND_RAG_EMBEDDING, llm_id=rag_id)
                    except Exception:
                        traceback.print_exc()
                if playground_reranker_id is not None:
                    try:
                        await llm_deployment.uninstall_worker(deployment_id=playground_reranker_id, llm_type=TYPE.PLAYGROUND_RAG_RERANKER, llm_id=rag_id)
                    except Exception:
                        traceback.print_exc()

            deployment_ids = [x for x in [playground_deployment_id, playground_embedding_id, playground_reranker_id] if x]
            # 게시(D6) 자동 취소 — deployment_api row 는 FK cascade 되나 Kong route/consumer/key 는
            # DB-비관리라 orphan → 삭제 대상 배포마다 공용 teardown(3b-2). embedding/reranker 도 직접
            # 게시 가능(엔드포인트가 타입 제한 안 함)하므로 전부 정리. delete_deployments 前 실행
            # (row/api_path 가 아직 있어 결정적 정리 가능). 이중 합성 route/service 정리 실패는
            # 행 삭제 전에 실패로 돌려 결정적 키를 보존한다(재시도 없이 orphan 확정되는 것 방지).
            _composite_cleanup_failed = False
            for _dep_id in deployment_ids:
                try:
                    try:
                        await run_in_threadpool(
                            deployment_api.teardown_deployment_api, _dep_id)
                    finally:
                        await run_in_threadpool(
                            deployment_api.teardown_composite_service, _dep_id)
                except Exception:
                    traceback.print_exc()
                    if _requires_composite_cleanup:
                        _composite_cleanup_failed = True
            if _composite_cleanup_failed:
                # 행 보존 의도(위 주석의 "결정적 키 보존")는 유지하되 **이 항목만** 건너뛴다.
                # 예전엔 raise 로 두 루프를 모두 탈출해, 같은 요청의 무관한 항목이
                # (a) 이미 delete_deployments 된 뒤 playground 행만 남아 dangling 이 되거나
                # (b) 아직 처리 전이라 helm/GPU 가 회수되지 않는 blast radius 가 있었다.
                _composite_cleanup_failed_ids.append(playground_id)
                continue
            db.delete_deployments(deployment_ids=deployment_ids)

        # playground 삭제 — 정리 실패 항목은 제외해 api_path 를 남기고 다음 시도에서 재정리한다.
        _target_ids = [i for i in id_list if i not in _composite_cleanup_failed_ids]
        res = await db.delete_playground(id_list=_target_ids) if _target_ids else True
        if _composite_cleanup_failed_ids:
            return False  # 부분 실패 → 라우트가 status=0 으로 사용자에게 알린다
        return True if res else False
    except:
        traceback.print_exc()
        return False

async def update_playground_description(playground_id, description):
    try:
        res = await db.update_playground(playground_id=playground_id, description=description)
        return True if res else False
    except:
        traceback.print_exc()
        return False

async def _clear_stale_external_job_id(playground_id, job_id):
    """종료된 external job 을 가리키는 dangling external_job_id 제거(self-heal).

    참조를 끊지 않으면 SSE /status 루프(1초 주기)가 매번 BFF GET /jobs/{id} 를
    때려 404 를 무한히 재시도한다 — 폴링을 끝내는 방법은 참조 제거뿐이다.
    쓰기 직전에 행을 다시 읽어 job_id 가 그대로일 때만 지운다: 그사이
    start_playground 가 새 job 을 기록했을 수 있어 blind write 면 방금 뜬 배포를
    지워버린다. deployment_run 등 나머지 배포 설정은 보존(stop_playground 동형).
    """
    try:
        fresh = await db.get_playground(playground_id=playground_id)
        deployment_raw = (fresh or {}).get("deployment")
        if not deployment_raw:
            return False
        deployment = json.loads(deployment_raw) or {}
        if deployment.get("external_job_id") != job_id:
            return False    # 그새 재배포됨 — 새 job_id 를 지우지 않는다
        deployment.pop("external_job_id", None)
        # 위 재조회만으로는 부족하다: 이 read 와 write 사이에도 재배포가 끼어들 수
        # 있어(TOCTOU) blind UPDATE 면 방금 기록된 새 job id 까지 지운다. 같은 조건을
        # SQL WHERE 에 실어 그 창을 닫는다.
        return bool(await db.clear_playground_external_job_id(
            playground_id=playground_id, expected_job_id=job_id,
            deployment_json=json.dumps(deployment)))
    except Exception:
        traceback.print_exc()
        return False


async def get_playground_status(playground_id, _skip_dual=False):
    result = {"status" : "stop", "init_deployment" : False}
    """
    init_deployment
        False일 경우, 초기 배포 시작 안한 상태
        True일 경우, 초기 배포 이미 한 상태
    """
    try:
        # playground deployment info
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            try:
                print(playground_id)
            except:
                pass
            raise Exception("Not Exist Playground")

        # ── Dual 세션(부모=추론 playground) 분기 ──────────────────────────
        # 세션 상태 = 부모(추론)+자식(프롬프트생성) 둘 다 running 일 때만 running.
        # _skip_dual=True 로 재귀하면 부모 자신의 단일 상태(아래 일반 로직)만 계산.
        if not _skip_dual:
            _model_raw = playground_info.get("model")
            _dual = {}
            if _model_raw:
                try:
                    _dual = (json.loads(_model_raw) or {}).get("dual") or {}
                except Exception:
                    _dual = {}
            _child_pg_id = _dual.get("prompt_gen_playground_id")
            if _dual.get("mode") == "dual" and _child_pg_id:
                parent_st = await get_playground_status(playground_id, _skip_dual=True)
                child_st = await get_playground_status(_child_pg_id)
                p_status = parent_st.get("status")
                c_status = child_st.get("status")
                any_init = bool(parent_st.get("init_deployment")) or bool(child_st.get("init_deployment"))
                if p_status == TYPE.KUBE_POD_STATUS_RUNNING and c_status == TYPE.KUBE_POD_STATUS_RUNNING:
                    return {"status": TYPE.KUBE_POD_STATUS_RUNNING, "init_deployment": True}
                if p_status == TYPE.KUBE_POD_STATUS_STOP and c_status == TYPE.KUBE_POD_STATUS_STOP:
                    # 둘 다 정지 — 미배포면 stop/False, 배포됐다 정지면 stop/True(재배포 가능).
                    # (정상 stop 후에도 deployment id 는 남아 init=True → any_init 로 판별)
                    return {"status": TYPE.KUBE_POD_STATUS_STOP, "init_deployment": any_init}
                # 그 외(설치중/보류/한쪽만 정지=부분·저하) = 설치중(Test 버튼 비활성 유지)
                return {"status": TYPE.KUBE_POD_STATUS_INSTALLING, "init_deployment": True}

        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is None: #정보 없을경우 세팅도 안된 상태
            return result
        playground_deployment_info = json.loads(playground_deployment_info)

        # ── External 분기 ────────────────────────────────────────────
        # external_job_id 있으면 일반 deployment_worker_list/redis 경로 안 탐.
        # BFF GET /jobs/{id} 의 pod_ready 가 model load 완료 신호 (partner /health
        # 200 OK). model load 중에는 init_deployment=True (배포는 시작) +
        # status='installing' → frontend 의 Test 버튼은 disabled 유지. ready 면
        # status='running' 으로 전환.
        external_job_id = playground_deployment_info.get("external_job_id")
        if external_job_id:
            try:
                job_detail = await get_job_status(external_job_id)
                # terminal(cancelled/failed/completed) 이면 pod 는 이미 helm
                # uninstall 로 소멸 → pod_ready 값과 무관하게 stop. record 가
                # 아직 BFF in-memory 에 남아 404 가 안 나는 구간에서도 중지가
                # 정확히 반영되도록 result.status 를 먼저 본다. (404 분기와 동일
                # 하게 init_deployment=False → 재배포 가능 상태)
                _job_result = job_detail.get("result") or {}
                if str(_job_result.get("status") or "").lower() in (
                    "cancelled", "failed", "completed",
                ):
                    # 종료 확정 — 이 job 을 더 볼 이유가 없다. dangling id 를
                    # 끊어 SSE 루프가 BFF 를 계속 두드리지 않게 한다.
                    await _clear_stale_external_job_id(playground_id, external_job_id)
                    result["status"] = TYPE.KUBE_POD_STATUS_STOP
                    result["init_deployment"] = False
                    return result
                # job record 가 살아있으면 배포는 시작됨 → init_deployment=True
                result["init_deployment"] = True
                if job_detail.get("pod_ready"):
                    result["status"] = TYPE.KUBE_POD_STATUS_RUNNING
                else:
                    result["status"] = TYPE.KUBE_POD_STATUS_INSTALLING
            except ExternalInferError as e:
                # BFF 가 404 (job 없음 / cancel 됨 / BFF 재시작으로 sync infer
                # 추적 휘발) → stop 으로 환원 + dangling id 제거로 폴링 종료.
                # 404 만 종료다: 5xx·네트워크 오류는 일시장애일 수 있어 id 를
                # 보존하고 installing 을 유지해야 재시도가 가능하다 (아래 else).
                if getattr(e, "status_code", 0) == 404:
                    await _clear_stale_external_job_id(playground_id, external_job_id)
                    result["status"] = TYPE.KUBE_POD_STATUS_STOP
                    result["init_deployment"] = False
                else:
                    # BFF 불안정 — 보수적으로 installing 유지 (test 차단)
                    result["status"] = TYPE.KUBE_POD_STATUS_INSTALLING
                    result["init_deployment"] = True
            except Exception:
                traceback.print_exc()
                result["status"] = TYPE.KUBE_POD_STATUS_INSTALLING
                result["init_deployment"] = True
            return result

        # deployment init
        # deployment_init = playground_deployment_info.get("deployment_init")
        deployment_init = True if playground_deployment_info.get("deployment_playground_id") is not None else None
        result["init_deployment"] = True if deployment_init == True else False

        # deployment status - 중지 (실행안한 상태)
        deployment_id = playground_deployment_info.get("deployment_playground_id")
        if deployment_id is None:
            return result

        # deployment_id
        deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
        deployment_run = playground_deployment_info.get("deployment_run")
        deployment_embedding_id = playground_deployment_info.get("deployment_embedding_id") if deployment_run.get("run_embedding") else None
        deployment_reranker_id = playground_deployment_info.get("deployment_reranker_id") if deployment_run.get("run_reranker") else None

        # installing, stop -> deployment_playground_id, DB로 바로 판단
        playground_worker_list = db.get_deployment_worker_list(deployment_id=deployment_playground_id, running=True)
        if len(playground_worker_list) == 0:
            result["status"] = TYPE.KUBE_POD_STATUS_STOP
            return result
        elif len(playground_worker_list) > 0:
            result["status"] = TYPE.KUBE_POD_STATUS_PENDING
        
        # running -> redis 사용
        redis_client = await get_redis_client_async()
        redis_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, playground_info.get("workspace_id"))
        redis_pod_list = json.loads(redis_workspace_pod_status) if redis_workspace_pod_status else dict()
        deployment_worker_redis_list = redis_pod_list.get('deployment', dict())

        # running playground -> redis 아무것도 없으면 종료(stop or pending인 경우)
        playground_redis_list = deployment_worker_redis_list.get(str(deployment_playground_id))
        if playground_redis_list is None or len(playground_redis_list) == 0:
            return result
        
        # running rag 
        running_status = True 
        for item_id in [deployment_playground_id, deployment_embedding_id, deployment_reranker_id]:
            if item_id is None:
                continue
            print(item_id)
            worker_list = deployment_worker_redis_list.get(str(item_id))

            print(worker_list)
            if worker_list and len(worker_list) > 0:
                status = list(worker_list.values())[0]['status']
                if status != TYPE.KUBE_POD_STATUS_RUNNING:
                    running_status = False
            else:
                running_status = False

        # 여기까지 넘어온경우 Installing or Rudnning
        result['status'] = TYPE.KUBE_POD_STATUS_RUNNING if running_status else TYPE.KUBE_POD_STATUS_INSTALLING

        ### ===== 최초 init deployment 업데이트 =====
        if result["status"] == TYPE.KUBE_POD_STATUS_INSTALLING or result["status"] == "running" and (deployment_init == None or deployment_init == False):
            result["init_deployment"] = True
            playground_deployment_info["deployment_init"] = True
            playground_deployment_info = json.dumps(playground_deployment_info)
            await db.update_playground(playground_id=playground_id, deployment=playground_deployment_info)

        return result
    except:
        traceback.print_exc()
        return result

async def update_playground(playground_id, description, access, owner_id, users_id):
    try:
        res = await db.update_playground(
            playground_id=playground_id, description=description, access=access, create_user_id=owner_id
        )

        if not res:
            raise
        
        # user_playground update --------------------------------------------------------------------------------------------------------
        # org_users_id = [user['user_id'] for user in db.(playground_id)]
        org_users_id = [user['user_id'] for user in await db.get_user_playground_list(playground_id)]

        users_id.append(owner_id)
        del_user = list(set(org_users_id) - set(users_id))
        add_user = list(set(users_id) - set(org_users_id))

        ### Insert User playground
        insert_result, message = await db.insert_user_playground_list(playgrounds_id=[playground_id]*len(add_user), users_id=add_user)
        if not insert_result:
            print("insert user playground error : {}".format(str(message)))
            raise 
        
        ### Delete User playground
        delete_result, message = await db.delete_user_playground(playgrounds_id=[playground_id]*len(del_user), users_id=del_user)
        if not delete_result:
            print("delete user playground error : {}".format(str(message)))
            raise 

        return True
    except:
        traceback.print_exc()
        return False



# bookmark ===================================================================================

async def add_playground_bookmark(playground_id, user_id):
    try:
        res = await db.insert_playground_bookmark(playground_id=playground_id, user_id=user_id)
        return True if res else False
    except:
        traceback.print_exc()
        return False

async def delete_playground_bookmark(playground_id, user_id):
    try:
        res = await db.delete_playground_bookmark(playground_id=playground_id, user_id=user_id)
        return True if res else False
    except:
        traceback.print_exc()
        return False

# 상세페이지 ===================================================================================

async def get_playground(playground_id):
    result = {"info" : None, "info_instance" :None, "info_request" :{"url" : None, "method" : None, "format" : None},
              "model" : None, "model_parameter" :None}
    item = None
    try:
        item = await db.get_playground(playground_id=playground_id)
        deployment = item.get("deployment")
        model = item.get("model")
        model_parameter = item.get("model_parameter")
        try:
            _detail_dual = (json.loads(model or "{}") or {}).get("dual") or {}
        except (TypeError, ValueError):
            _detail_dual = {}
        _is_dual_detail = _detail_dual.get("mode") == "dual"

        # INFO
        result["info"] = dict()
        result['info']['id'] = item["id"]
        result['info']['workspace_id'] = item["workspace_id"]
        result['info']['name'] = item["name"]
        result['info']['access'] = item.get("access")
        result['info']['description'] = item["description"]
        result['info']['create_datetime'] = item["create_datetime"]
        result['info']['update_datetime'] = item["update_datetime"]
        result['info']['owner'] = db.get_user(user_id=item.get("create_user_id")).get("name")
        result['info']['accelerator'] = bool(item.get("accelerator", False))

        # users
        if item.get("access") == 1:
            users=[]
        else:
            users=[item.get("user_name") for item in await db.get_user_playground_list(playground_id=item.get("id"))]
        result['info']['users'] = users
        # 게시(D6) 대상 배포 PK. FE(PlaygroundDetail 외부 API 섹션)가 이 값으로
        # /deployments/{id}/api-publish 를 호출한다. deployment 파싱 블록에서 실제값을
        # 채우고, 배포 없으면 None 유지.
        result['info']['deployment_id'] = None

        # INFO - instance
        try:
            if deployment:
                deployment_playground = json.loads(deployment)
                deployment_playground_id = deployment_playground.get("deployment_playground_id")
                result['info']['deployment_id'] = deployment_playground_id
                deployment_embedding_id = deployment_playground.get("deployment_embedding_id")
                deployment_reranker_id = deployment_playground.get("deployment_reranker_id")

                result["info_instance"] = dict()
                result["info_request"] = dict()

                if deployment_playground_id:
                    deployment_info = db.get_deployment(deployment_id=deployment_playground_id)
                    api_path = deployment_info.get("api_path")
                    url = f"{settings.INGRESS_PROTOCOL}://{settings.EXTERNAL_HOST}/{api_path}"
                    if settings.EXTERNAL_HOST_PORT != 80 or settings.EXTERNAL_HOST_PORT != 443:
                        url = f"{url}:{settings.EXTERNAL_HOST_PORT}/{api_path}"

                    # playground request
                    # playground 배포는 따로 deployment_data_form을 저장하지 않음, 현재 playground 코드는 고정이므로 데이터폼도 고정

                    # 이중 게시 endpoint는 dataset 요청을 의도적으로 거부하므로, 상세 화면도
                    # 실제로 수락하는 question 계약만 광고한다. 단일 형식은 기존 그대로 둔다.
                    request_format = [{
                        "test_type": "question",
                        "session_id": "Optional[int]",
                        "test_question": "str"
                    }] if _is_dual_detail else [{
                        "test_type": "dataset",
                        "session_id": "Optional[int]",
                        "test_dataset_id": "int",
                        "test_dataset_filename": "str"
                    },
                    {
                        "test_type": "question",
                        "session_id": "Optional[int]",
                        "test_question": "str"
                    }]
                    result["info_request"]= {
                        "url" : url,
                        "method" : "POST",
                        "format" : request_format
                    }
                    instance_info = await get_workspace_instance_total_info(instance_id=deployment_info.get("instance_id"), workspace_id=deployment_info.get("workspace_id"),
                                                                            instance_allocate=deployment_info.get("instance_allocate"),
                                                                            resource_limit=[{"cpu_limit" : deployment_info.get("deployment_cpu_limit"), "ram_limit" : deployment_info.get("deployment_ram_limit")}]
                                                                            )
                    # instance.gpu_allocate는 장비 총량이므로 사용자가 선택한 gpu_per_worker를 별도 노출한다.
                    instance_info["gpu_count"] = deployment_info.get("gpu_per_worker")
                    # playground instance
                    result["info_instance"]["model"] = dict()
                    result["info_instance"]["model"] = instance_info
                else:
                    # playground instance
                    result["info_instance"]["model"] = None

                # ==============================================================================================================
                if settings.GITC_USED:
                    deployment_run = deployment_playground.get("deployment_run")
                    if deployment_run:
                        run_embedding = deployment_run.get("run_embedding")
                        run_reranker = deployment_run.get("run_reranker")
                    else:
                        run_embedding = None
                        run_reranker = None

                    if run_embedding and deployment_embedding_id:
                        deployment_info = db.get_deployment(deployment_id=deployment_embedding_id)
                        instance_info = await get_workspace_instance_total_info(instance_id=deployment_info.get("instance_id"), workspace_id=deployment_info.get("workspace_id"),
                                                                                instance_allocate=deployment_info.get("instance_allocate"),
                                                                                resource_limit=[{"cpu_limit" : deployment_info.get("deployment_cpu_limit"), "ram_limit" : deployment_info.get("deployment_ram_limit")}]
                                                                                )
                        result["info_instance"]["embedding"] = dict()
                        result["info_instance"]["embedding"] = instance_info
                    else:
                        result["info_instance"]["embedding"] = None
                    if run_reranker and deployment_reranker_id:
                        deployment_info = db.get_deployment(deployment_id=deployment_reranker_id)
                        instance_info = await get_workspace_instance_total_info(instance_id=deployment_info.get("instance_id"), workspace_id=deployment_info.get("workspace_id"),
                                                                                instance_allocate=deployment_info.get("instance_allocate"),
                                                                                resource_limit=[{"cpu_limit" : deployment_info.get("deployment_cpu_limit"), "ram_limit" : deployment_info.get("deployment_ram_limit")}]
                                                                                )
                        result["info_instance"]["reranker"] = instance_info
                    else:
                        result["info_instance"]["reranker"] = None
                # ==============================================================================================================
                
                result["info_instance"]["immediately_status"] = True # TODO 
        except:
            traceback.print_exc()
            pass

        # MODEL - Parameter
        try:
            if model_parameter:
                model_parameter = json.loads(model_parameter)
                result['model_parameter'] = dict()
                result['model_parameter']['temperature'] = model_parameter.get("temperature")
                result['model_parameter']['top_p'] = model_parameter.get("top_p")
                result['model_parameter']['top_k'] = model_parameter.get("top_k")
                result['model_parameter']['repetition_penalty'] = model_parameter.get("repetition_penalty")
                result['model_parameter']['max_new_tokens'] = model_parameter.get("max_new_tokens")
            else:
                result['model_parameter'] = None
        except:
            pass

        # MODEL
        try:
            if model:
                model = json.loads(model)
                result['model'] = dict()
                result['model']["model_type"] = model.get("model_type")
                result['model']["serving_system"] = model.get("serving_system") or "vllm"
                result['model']["model_hf_id"] = model.get("model_huggingface_id")
                
                db_commit_info = await db.get_commit_model(commit_id=model.get("model_allm_commit_id"))
                result['model']["model_allm_name"] = db_commit_info.get("model_name") if db_commit_info else None
                result['model']["model_allm_id"] = db_commit_info.get("model_id") if db_commit_info else None
                result['model']["model_allm_commit_name"] = db_commit_info.get("name") if db_commit_info else None
                result['model']["model_allm_commit_id"] = db_commit_info.get("id") if db_commit_info else None

                # External 모델 분기 (Test 모달 ExternalTestCom / Deploy 모달 embedding·reranker
                # UI 숨김) 의 isExternal 신호. commit 의 model_id 로 모델 행 조회해서
                # training_type 노출.
                result['model']["training_type"] = ""
                if db_commit_info:
                    _model_id = db_commit_info.get("model_id")
                    if _model_id:
                        try:
                            _model_row = await db.get_model(model_id=int(_model_id))
                            if _model_row:
                                result['model']["training_type"] = _model_row.get("training_type") or ""
                        except Exception:
                            traceback.print_exc()

                model_info = model.get("model_info", {})
                result['model']["commit"] = model_info.get("commit")
                result['model']["access"] = model_info.get("access")
                result['model']["create_datetime"] = model_info.get("create_datetime")
                result['model']["update_datetime"] = model_info.get("update_datetime")
                result['model']["description"] = model_info.get("description")
                result['model']["url"] = model_info.get("url")
            else:
                result['model'] = None
        except:
            pass
        

        # GITC의 경우 사용하는 RAG PROMPT
        if settings.GITC_USED:
            rag = item.get("rag")
            prompt = item.get("prompt")
            tmp = get_rag_prompt_info(rag=rag, prompt=prompt)
            result["rag"] = tmp.get("rag")
            result["prompt"] = tmp.get("prompt")

    except Exception as e:
        traceback.print_exc()

    # DUAL — 이중모델 세션(부모=추론)이면 프롬프트생성 모델 정보 노출(상세 헤더 태그용).
    # 실패해도 상세는 반환(best-effort). 자원은 info_instance 가 이미 제공.
    try:
        _dual = (json.loads((item or {}).get("model") or "{}") or {}).get("dual") or {}
        if _dual.get("mode") == "dual":
            _pgid = _dual.get("prompt_gen_model_id")
            _pg_name = None
            if _pgid:
                _pg_row = await db.get_model(model_id=int(_pgid))
                _pg_name = (_pg_row or {}).get("name")
            _inf_name = (result.get("model") or {}).get("model_allm_name") if isinstance(result.get("model"), dict) else None
            result["dual"] = {
                "mode": "dual",
                "prompt_gen_playground_id": _dual.get("prompt_gen_playground_id"),
                "prompt_gen_model_id": _pgid,
                "prompt_gen_model_name": _pg_name,
                "inference_model_name": _inf_name,
                "resources": _dual.get("resources") or [],
            }
        else:
            result["dual"] = None
    except Exception:
        traceback.print_exc()
        result["dual"] = None
    return result


async def get_playground_status_detail(playground_id):
    """새 상태 계약: 세션 집계와 컴포넌트 실측을 한 응답에 함께 담는다."""
    playground = await db.get_playground(playground_id=playground_id)
    if not playground:
        raise Exception("Not Exist Playground")
    dual = (json.loads(playground.get("model") or "{}") or {}).get("dual") or {}
    if dual.get("role") == "prompt_child":
        parent_id, _ = await _resolve_dual_parent(playground_id)
        playground_id = parent_id
        playground = await db.get_playground(playground_id=parent_id)
        dual = (json.loads(playground.get("model") or "{}") or {}).get("dual") or {}

    aggregate = await get_playground_status(playground_id=playground_id)
    child_id = dual.get("prompt_gen_playground_id")
    if dual.get("mode") == "dual" and child_id:
        child = await get_playground_status(child_id, _skip_dual=True)
        parent = await get_playground_status(playground_id, _skip_dual=True)
        aggregate["components"] = [
            {
                "role": "prompt_gen",
                "playground_id": child_id,
                "status": child.get("status"),
                "init_deployment": child.get("init_deployment", False),
            },
            {
                "role": "inference",
                "playground_id": playground_id,
                "status": parent.get("status"),
                "init_deployment": parent.get("init_deployment", False),
            },
        ]
    else:
        aggregate["components"] = [{
            "role": "single",
            "playground_id": playground_id,
            "status": aggregate.get("status"),
            "init_deployment": aggregate.get("init_deployment", False),
        }]
    return aggregate



async def get_rag_prompt_info(rag, prompt):
    result = {"rag" : None, "prompt" : None}
    try:
        # RAG   
        try:
            rag = json.loads(rag) if rag else None
            if rag and rag.get("rag_id"):
                rag_id = rag.get("rag_id")

                result['rag'] = dict()
                result["rag"]['id'] = rag_id # 플레이그라운드 세팅 값
                result["rag"]['chunk_max'] = rag.get("rag_chunk_max") # 플레이그라운드 세팅 값
                
                # rag db
                rag_info = await db.get_rag(rag_id=rag_id)
                result["rag"]['name'] = rag_info.get("name")
                result["rag"]['chunk_len'] = rag_info.get("chunk_len")
                result["rag"]['embedding_huggingface_model_id'] = rag_info.get("embedding_huggingface_model_id")
                result["rag"]['reranker_huggingface_model_id'] = rag_info.get("reranker_huggingface_model_id")

                # rag docs db
                total_size = 0
                total_count = 0
                doc_list = []
                for doc in await db.get_rag_doc_list(rag_id=rag_id):
                    doc_list = [{"name" : doc.get("doc_name"), "id" : doc.get("doc_id")}]
                    total_count += 1
                    total_size += doc.get("size", 0)
                result["rag"]['rag_doc_list'] = doc_list
                result["rag"]['docs_total_count'] = total_count
                result["rag"]['docs_total_size'] = total_size
            else:
                result["rag"] = None
        except:
            pass

        # PROMPT
        try:
            prompt = json.loads(prompt)
            if prompt and prompt.get("prompt_id"):
                result['prompt'] = dict()
                result['prompt']['id'] = prompt.get("prompt_id")
                result['prompt']['name'] = prompt.get("prompt_name")
                result['prompt']['commit_name'] = prompt.get("prompt_commit_name")
                result['prompt']['system_message'] = prompt.get("system_message")
                result['prompt']['user_message'] = prompt.get("user_message")
            else:
                result['prompt'] = None
        except:
            pass
    except Exception as e:
        traceback.print_exc()
    return result

async def update_playground_options(playground_id, is_rag, is_prompt, accelerator,
                model_type, model_huggingface_id, model_huggingface_token, model_allm_id, model_allm_commit_id, model_info,
                model_temperature, model_top_p, model_top_k, model_repetition_penalty, model_max_new_tokens, 
                rag_id, rag_chunk_max, prompt_id, prompt_name, prompt_commit_name, prompt_system_message, prompt_user_message,
                serving_system="vllm"
            ):
    try:
        # playground
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("check playground id")

        # 서빙 엔진 검증(멀티엔진 Phase 1) — 지원 목록 외 값은 거부(FE gate 넘어 방어).
        serving_system = serving_system or "vllm"
        if serving_system not in settings.SUPPORTED_SERVING_SYSTEMS:
            raise Exception(f"지원하지 않는 서빙 엔진입니다: {serving_system}")

        # model — 기존 dual 링크(이중 세션)는 보존(옵션 저장이 세션 링크를 지우지 않게).
        model_dict = {"model_type": model_type, "model_huggingface_id" : model_huggingface_id, "model_huggingface_token" : model_huggingface_token,
                      "model_allm_id" : model_allm_id, "model_allm_commit_id" : model_allm_commit_id,
                      "model_info": model_info, "serving_system": serving_system}
        try:
            _existing_dual = (json.loads(playground_info.get("model") or "{}") or {}).get("dual")
            if _existing_dual:
                model_dict["dual"] = _existing_dual
        except Exception:
            traceback.print_exc()
        model = json.dumps(model_dict)
        model_parameter = json.dumps({"temperature": model_temperature, "top_p" : model_top_p, "top_k" : model_top_k, "repetition_penalty" : model_repetition_penalty, "max_new_tokens" : model_max_new_tokens})
        
        # rag
        rag = json.dumps({"rag_chunk_max" : rag_chunk_max, "rag_id" : rag_id})
        is_embedding = False
        is_reranker = False
        if rag_id != None:
            rag_info = await db.get_rag(rag_id=rag_id)
            test_embedding_run = rag_info.get("test_embedding_run")
            is_embedding = True if test_embedding_run else False
            test_reranker_run = rag_info.get("test_reranker_run")
            is_reranker = True if test_reranker_run else False

        # prompt
        prompt = json.dumps({"prompt_id" : prompt_id, "prompt_name" : prompt_name, "prompt_commit_name" : prompt_commit_name, "system_message" : prompt_system_message, "user_message" : prompt_user_message})

        # deployment_run: 무조건 들어감
        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is not None:
            playground_deployment_info = json.loads(playground_deployment_info) # 기존정보 유지
            deployment = playground_deployment_info
        else:
            deployment = dict()
        deployment["deployment_run"] = {"run_rag" : is_rag, "run_embedding" : is_embedding,  "run_reranker" : is_reranker,  "run_prompt" : is_prompt}
        deployment = json.dumps(deployment)

        res = await db.update_playground(playground_id=playground_id, deployment=deployment, model=model, model_parameter=model_parameter, rag=rag,  prompt=prompt, accelerator=accelerator)
        return True if res else False
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))

async def get_playground_instance_options(playground_id):
    result = []
    try:
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground")
        workspace_id = playground_info.get("workspace_id")
        result = db.get_workspace_instance_list(workspace_id=workspace_id)
    except:
        traceback.print_exc()
    return result

async def get_playground_deployment_monitoring(playground_id):
    result = {"playground_id" : None, "embedding_id" : None, "reranker_id" : None}
    try:
        # playground -> playground_deployment
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground")
        
        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is None: #정보 없을경우 세팅도 안된 상태
            return result
        
        # init deployment
        playground_deployment_info = json.loads(playground_deployment_info)
        playground_id = playground_deployment_info.get("deployment_playground_id")
        embedding_id = playground_deployment_info.get("deployment_embedding_id")
        reranker_id = playground_deployment_info.get("deployment_reranker_id")
        
        result["playground_id"] = playground_id
        result["embedding_id"] = embedding_id
        result["reranker_id"] = reranker_id
        return result
    except:
        traceback.print_exc()
        return result

# model ===================================================================================
async def get_hugging_face_model(model_name : str = None, huggingface_token : str = None, private : int = 0) -> List[str]:
    """hf_token이 들어오면 private model
    """
    result = []
    try:
        api = HfApi()
        if private:
            huggingface_token = front_cipher.decrypt(huggingface_token)
            models = api.list_models(limit=10, filter=["text-generation", "transformers"], search=model_name, expand=["private"], token=huggingface_token)
        else:
            models = api.list_models(limit=10, filter=["text-generation", "transformers"], search=model_name)

        for model_info in models: 
            # model_info = api.model_info(model.id) # list_models 에서 가져온 정보로 조회가 안되 model_info사용 (author, last_modified...)
            result.append({
                "id" : model_info.id,
                "create_datetime" : model_info.created_at.strftime("%Y-%m-%d %H:%M:%S") if model_info.created_at else None,
                "update_datetime" : model_info.last_modified.strftime("%Y-%m-%d %H:%M:%S") if model_info.last_modified else None,
                "access" : not model_info.private,
                "owner" : model_info.author,
                "commit" : model_info.sha,
                "url" : f"https://huggingface.co/{model_info.id}",
                "description" : None
            })
    except:
        traceback.print_exc()
    return result

async def get_playground_model_list(workspace_id, model_name, is_mine, user_name):
    result = {"hf_model_list" : [], "allm_model_list" : []}
    try:
        try:
            hf_model_list = await get_hugging_face_model(huggingface_token=None, model_name=model_name)
            result["hf_model_list"] = hf_model_list
        except:
            pass
        try:
            # ALLM MODEL
            allm_model_list = await db.get_models_option(workspace_id=workspace_id, model_name=model_name)
            for item in allm_model_list:
                
                if is_mine and item.get("create_user_name") != user_name:
                    continue
                
                result["allm_model_list"].append({
                    "id" : item.get("id"),
                    "name" : item.get("name"),
                    "owner" : item.get("create_user_name"),
                    "training_type" : item.get("training_type") or "",
                    "external_manifest_name" : item.get("external_manifest_name") or "",
                    "external_manifest_version" : item.get("external_manifest_version") or "",
                })
        except:
            pass
    except:
        traceback.print_exc()
    return result

async def get_playground_model_commit_list(model_id, commit_name, is_mine, user_name):
    result = []
    try:
        print(commit_name)
        model_commit_list = await db.get_commit_models_option(model_id=model_id, commit_name=commit_name)
        for item in model_commit_list:
            
            if is_mine and item.get("create_user_name") != user_name:
                continue
            
            result.append({
                "model_name" : item.get("model_name"),
                "model_commit_name" : item.get("name"),
                "model_commit_id" : item.get("id"),
                "owner" : item.get("create_user_name"),
                "create_datetime" : item.get("create_datetime"),
                "update_datetime" : item.get("update_datetime"),
                "access" : item.get("access"),
                "description" : item.get("description"),
                "url" : None,
            })
    except:
        traceback.print_exc()
    return result

async def check_model_access( token: str, model_id: str = None) -> bool:
    """
    해당 Hugging Face 모델에 대해 주어진 토큰으로 접근 권한이 있는지 확인하는 함수 (비동기 버전).

    Parameters:
    model_id (str): 접근하려는 모델의 Hugging Face ID.
    token (str): Hugging Face API 토큰.

    Returns:
    bool: 접근 권한이 있으면 True, 없으면 False.
    """
    loop = asyncio.get_event_loop()
    # token = front_cipher.decrypt(token)
    try:
        # Hugging Face API로 로그인 (토큰 기반)
        await loop.run_in_executor(None, login, token)
        if model_id is not None:
            # 모델 정보 요청 (권한 확인)
            await loop.run_in_executor(None, model_info, model_id)
        return True  # 접근 권한이 있음

    except HTTPError as e:
        # 모델에 접근할 권한이 없거나 존재하지 않음
        print(f"Error: Cannot access the model '{model_id}' with the provided token.")
        print(f"Details: {e}")
        return False

    except Exception as e:
        # 기타 오류
        print(f"An unexpected error occurred while checking access: {e}")
        return False

# rag ===================================================================================
async def get_playground_rag_list(workspace_id, rag_name, is_mine, user_name):
    result = []
    try:
        rag_list = await db.get_rag_list(workspace_id=workspace_id, like_rag_name=rag_name)
        for item in rag_list:
            
            if is_mine and item.get("create_user_name") != user_name:
                continue
            
            if item.get("embedding_huggingface_model_id") is None:
                continue

            # doc list
            doc_list = [{"name" : doc.get("doc_name"), "id" : doc.get("doc_id")} for doc in await db.get_rag_doc_list(rag_id=item.get("id"))]
 
            # result
            result.append({
                "id" : item.get("id"),
                "name" : item.get("name"),
                "owner" : item.get("create_user_name"),
                "chunk_len" : item.get("chunk_len"),
                "docs_total_count" : item.get("docs_total_count"),
                "docs_total_size" : item.get("docs_total_size"),
                "doc_list" : doc_list,
                "embedding_huggingface_model_id" : item.get("embedding_huggingface_model_id"),
                "reranker_huggingface_model_id" : item.get("reranker_huggingface_model_id"),
            })
    except:
        traceback.print_exc()
    return result

# prompt ===================================================================================
async def get_playground_prompt_list(workspace_id, prompt_name, is_mine, user_name):
    result = []
    try:
        prompt_list = await db.get_prompt_list(workspace_id=workspace_id, like_prompt_name=prompt_name)
        prompt_list = await db.get_prompt_list()

        for item in prompt_list:
            
            if is_mine and item.get("create_user_name") != user_name:
                continue
            
            result.append({
                "id" : item.get("id"),
                "name" : item.get("name"),
                "owner" : item.get("create_user_name")
            })
    except:
        traceback.print_exc()
    return result

async def get_playground_prompt_commit_list(prompt_id, commit_name, is_mine, user_name):
    result = []
    try:
        prompt_commit_list = await db.get_commit_prompt_list(prompt_id=prompt_id, like_commit_name=commit_name)
        for item in prompt_commit_list:

            if is_mine and item.get("create_user_name") != user_name:
                continue

            result.append({
                "prompt_id" : prompt_id,
                "prompt_commit_id" : item.get("commit_id"),
                "prompt_name" : item.get("prompt_name"),
                "prompt_commit_name" : item.get("commit_name"),
                "system_message" : item.get("system_message"),
                "user_message" : item.get("user_message"),
                "owner" : item.get("create_user_name")
            })
    except:
        traceback.print_exc()
    return result


# 실행관련 ===================================================================================
# API 요청
async def start_playground(user_name, playground_id, 
            model_instance_id, model_instance_count, model_gpu_count,
            embedding_instance_id, embedding_instance_count, embedding_gpu_count,
            reranker_instance_id, reranker_instance_count, reranker_gpu_count,
            restart=False
        ):
    """
    1. playground 실행, 2. deployment 생성
    TODO 현재는 플레이그라운드 1개만 만든다고 진행 (model, model + prompt)
    """
    try:
        # =============================================================================
        # 재식작일 경우, 중단
        # =============================================================================
        if restart:
            restart_playground_info = await db.get_playground(playground_id=playground_id)
            if restart_playground_info is None:
                raise Exception("Not Exist Playground_id")
            try:
                restart_dual = (json.loads(restart_playground_info.get("model") or "{}") or {}).get("dual") or {}
            except Exception:
                restart_dual = {}
            # 이중은 저장된 양쪽 자원을 쓰는 전용 오케스트레이션으로 넘겨 한쪽만 뜨는 상태를 막는다.
            if restart_dual.get("mode") == "dual" or restart_dual.get("role") == "prompt_child":
                return await restart_dual_session(
                    playground_id=playground_id, user_name=user_name)
            if not await stop_playground(playground_id=playground_id):
                raise Exception("플레이그라운드 재시작을 위한 중지에 실패했습니다")
        # =============================================================================
        # info
        # =============================================================================
        user_id = db.get_user(user_name=user_name).get("id")
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground_id")

        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info:
            playground_deployment_info = json.loads(playground_deployment_info)
            playground_deployment_run = playground_deployment_info.get("deployment_run") # 이 값은 플레이그라운드 저장시 DB에 저장됨
            deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
            deployment_embedding_id = playground_deployment_info.get("deployment_embedding_id")
            deployment_reranker_id = playground_deployment_info.get("deployment_reranker_id")

            # codex High-1: 기존 external_job_id 가 있는데 restart=False 인
            # 경로로 새 start 가 호출되면, 옛 job 의 helm release 가 orphan 으로
            # 남는다. restart=True 가 아니더라도 항상 stop 으로 정리.
            if not restart and playground_deployment_info.get("external_job_id"):
                await stop_playground(playground_id=playground_id)
        else:
            # deployment info가 없다는건, deployment_run이 없다는 의미 -> 세팅이 안되어 있다
            # deployment_run은 update_playground에서 무조건 세팅함
            raise Exception("Not set up playground deployment")

        # =============================================================================
        # 자원 설정
        # =============================================================================
        # playground 의 자원은 모델의 자원을 사용
        playground_instance_id = model_instance_id
        playground_instance_count = model_instance_count
        playground_gpu_count = model_gpu_count

        # =============================================================================
        # External partner container 분기 — internal helm 배포 대신 BFF /jobs launch
        # =============================================================================
        playground_model_info = playground_info.get("model")
        playground_model_allm_id = None
        if playground_model_info:
            try:
                model_json = json.loads(playground_model_info)
                playground_model_allm_id = model_json.get("model_allm_id")
            except Exception:
                traceback.print_exc()

        if playground_model_allm_id:
            try:
                model_row = await db.get_model(model_id=int(playground_model_allm_id))
            except Exception:
                traceback.print_exc()
                model_row = None
            if model_row and model_row.get("training_type") == "external":
                manifest_name = model_row.get("external_manifest_name")
                manifest_version = model_row.get("external_manifest_version")
                # codex Med-2: playground 는 추론용 — model 의 manifest 가
                # train 이면 BFF 의 manifest registry 에서 paired infer 를
                # lookup. 이전엔 ``-train``→``-infer`` + ``1.0.0-acryl-patched-v4``
                # 가 hardcode 돼 있어 다른 partner / 다른 version 에선 404 났음.
                #
                # ⚠️ 실패 시 train manifest 로 진행하면 안 된다. train 은
                # execution_mode=async 라 chart 가 ingress 를 만들지 않고
                # (lifecycle.py: ingress.enabled = mode=="sync"), adapter 가
                # endpoints.run(=/train) 으로 POST 해 422 → cleanup → helm
                # uninstall 로 끝난다. 화면엔 그냥 "중지"로 보여서 원인이
                # 안 드러난다 — 그래서 여기서 명시적으로 실패시킨다.
                if not (manifest_name and manifest_version):
                    raise Exception(
                        "외부 학습 모델에 컨테이너 manifest 정보가 없습니다 "
                        "(external_manifest_name/version 미설정). 모델 등록을 확인하세요."
                    )
                try:
                    paired = await get_paired_manifest(manifest_name, manifest_version)
                except Exception as e:
                    traceback.print_exc()
                    raise Exception(
                        f"추론 manifest 조회에 실패했습니다 "
                        f"(manifest={manifest_name}@{manifest_version}): {e}"
                    )
                if not paired:
                    raise Exception(
                        f"추론 manifest 가 바인딩되지 않았습니다 "
                        f"(manifest={manifest_name}@{manifest_version}). 외부 컨테이너 "
                        f"레지스트리에 학습/추론 manifest 를 pair 로 등록해야 배포할 수 "
                        f"있습니다."
                    )
                # /paired 는 "짝의 반대쪽"을 돌려준다. validator 의 허용 조합은
                # 모두 {infer, train|evaluate|convert} 라 정확히 한 쪽만 infer 다.
                # → 반대쪽이 infer 면 지금 들고 있는 게 workload 쪽이므로 전환하고,
                #   반대쪽이 infer 가 아니면 들고 있는 게 이미 infer 쪽이라 유지.
                if paired.get("job_type") == MANIFEST_JOB_TYPE_INFER:
                    manifest_name = paired["name"]
                    manifest_version = paired["version"]
                workspace_id = playground_info.get("workspace_id")
                gpu_count = playground_gpu_count or 1

                # ── EVA_CHECKPOINT_PATH 동적 주입 ────────────────────────
                # 우선순위: (1) playground 의 model_allm_commit_id (사용자가
                # 명시적으로 선택한 checkpoint 버전), (2) model.latest_commit_id
                # (선택 안 했을 때만 fallback). 플랫폼의 핵심 기능 — commit 별
                # 버전 비교 테스트 — 을 존중.
                env_overrides = {}
                selected_commit_id = model_json.get("model_allm_commit_id")
                # JSON 의 string "69" 또는 int 69 모두 처리
                target_commit_id = None
                try:
                    if selected_commit_id not in (None, "", "null"):
                        target_commit_id = int(selected_commit_id)
                except (TypeError, ValueError):
                    pass
                if not target_commit_id:
                    target_commit_id = model_row.get("latest_commit_id")

                if target_commit_id:
                    try:
                        commit_row = await db.get_commit_model(commit_id=int(target_commit_id))
                        commit_name = commit_row.get("name") if commit_row else None
                        if commit_name:
                            env_overrides["EVA_CHECKPOINT_PATH"] = (
                                f"/models/checkpoints/{commit_name}"
                            )
                    except Exception:
                        traceback.print_exc()

                try:
                    job_resp = await start_infer_job(
                        manifest_name=manifest_name,
                        manifest_version=manifest_version,
                        workspace_id=int(workspace_id),
                        platform_model_id=int(playground_model_allm_id),
                        params={"_base_model": {"name": model_row.get("name") or "external"}},
                        gpu_count=int(gpu_count),
                        env_overrides=env_overrides if env_overrides else None,
                    )
                except ExternalInferError as e:
                    traceback.print_exc()
                    raise Exception(f"External partner start failed [{e.status_code}]: {e}")

                external_job_id = job_resp.get("job_id")
                if not external_job_id:
                    raise Exception(f"External /jobs returned no job_id: {job_resp}")

                playground_deployment = json.dumps({
                    "deployment_playground_id": None,
                    "deployment_embedding_id": None,
                    "deployment_reranker_id": None,
                    "deployment_run": playground_deployment_run,
                    "external_job_id": external_job_id,
                })
                await db.update_playground(playground_id=playground_id, deployment=playground_deployment)
                return True

        # =============================================================================
        # 배포 생성
        # =============================================================================
        run_embedding, run_reranker =  False, False
        # 플레이그라운드 배포
        if deployment_playground_id:
            # 재배포 — playground_id 전달로 serving_system 변경 시 image_id 재계산(엔진 전환 반영).
            await update_deployment(deployment_id=deployment_playground_id, instance_id=playground_instance_id, instance_count=playground_instance_count, gpu_count=playground_gpu_count, playground_id=playground_id)
        else:
            # 초기배포
            deployment_playground_id = await create_deployment(playground_id=playground_id, user_id=user_id, deployment_type="playground",
                                                               instance_id=playground_instance_id, instance_count=playground_instance_count, gpu_count=playground_gpu_count)

        # rag 정보
        rag_id = None
        if (embedding_instance_id and embedding_instance_count > 0) or (reranker_instance_id and reranker_instance_count > 0):
            playground_rag_info = playground_info.get("rag")
            if playground_rag_info:
                rag_info = json.loads(playground_rag_info)
                rag_id = rag_info.get("rag_id")
            else:
                raise Exception("Not Exist Playground RAG")

        # rag embedding 배포
        if embedding_instance_id and embedding_instance_count > 0:
            run_embedding = True
            if deployment_embedding_id:
                await update_deployment(deployment_id=deployment_embedding_id, instance_id=embedding_instance_id, instance_count=embedding_instance_count, gpu_count=embedding_gpu_count)
            else:
                deployment_embedding_id = await create_deployment(playground_id=playground_id, user_id=user_id, deployment_type="embedding",
                                                                  instance_id=embedding_instance_id, instance_count=embedding_instance_count, gpu_count=embedding_gpu_count, rag_id=rag_id)    

        # rag reranker 배포
        if reranker_instance_id and reranker_instance_count > 0:
            run_reranker = True
            if deployment_reranker_id:
                await update_deployment(deployment_id=deployment_reranker_id, instance_id=reranker_instance_id, instance_count=reranker_instance_count, gpu_count=reranker_gpu_count)
            else:
                deployment_reranker_id = await create_deployment(playground_id=playground_id, user_id=user_id, deployment_type="reranker",
                                                                 instance_id=reranker_instance_id, instance_count=reranker_instance_count, gpu_count=reranker_gpu_count, rag_id=rag_id)    

        # 배포 정보 업데이트
        playground_deployment= json.dumps({"deployment_playground_id" : deployment_playground_id, "deployment_embedding_id" : deployment_embedding_id, "deployment_reranker_id" : deployment_reranker_id,
                                           "deployment_run" : playground_deployment_run}) 
        await db.update_playground(playground_id=playground_id, deployment=playground_deployment)

        # =============================================================================
        # 워커 생성
        # =============================================================================
        await run_deployment_playground(playground_id=playground_id, run_embedding=run_embedding, run_reranker=run_reranker)
        return True
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)

# 배포 생성
async def create_deployment(playground_id, user_id, deployment_type, instance_id, instance_count, gpu_count, rag_id=None):
    try:
        print("create_deployment", playground_id, user_id, deployment_type, instance_id, instance_count, gpu_count, rag_id)
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground")
        
        workspace_id = playground_info.get("workspace_id")
        workspace_name = db.get_workspace(workspace_id=workspace_id)["name"]

        instance_info = db.get_instance(instance_id=instance_id)
        instance_type = instance_info.get("instance_type")

        # instance의 실제 cpu/ram allocate 값을 사용
        deployment_cpu_limit = instance_info.get('cpu_allocate', 0)
        deployment_ram_limit = instance_info.get('ram_allocate', 0)
        
        # 서빙 엔진별 배포 이미지(멀티엔진 Phase 1). playground 역할만 엔진 선택 반영(embedding/reranker=vllm).
        #   model JSON 파싱은 playground 에서만 → embedding/reranker 를 model 필드 유효성에 결합하지 않음(회귀 방지).
        if deployment_type == "playground":
            try:
                _model_cfg = json.loads(playground_info.get("model") or "{}") or {}
            except (ValueError, TypeError):
                _model_cfg = {}
            _serving_system = settings.resolve_serving_system(_model_cfg.get("serving_system"))
        else:
            _serving_system = "vllm"
        _serving_image = settings.SERVING_ENGINE_IMAGE_MAP.get(_serving_system, settings.DEPLOYMENT_LLM_IMAGE)
        image_real_name=f"{settings.DOCKER_REGISTRY_URL}{_serving_image}" ### LLM 배포 이미지는 1. main.py에서 image db에 넣음. 2. image build: /jp/libs/fb_image/llm
        # 이미지행 미등록(레지스트리 드리프트 등) 시 None.get() 크래시 방지 → 명시 실패(update_deployment 와 동형).
        _image_row = db.get_image_id_by_real_name(real_name=image_real_name)
        if isinstance(_image_row, tuple):  # 헬퍼가 DB 예외 시 (False, e) 반환 → '미등록'과 구분해 오류 전파(truthy 튜플이 가드 우회 방지)
            raise Exception(f"서빙 이미지 조회 실패: serving_system={_serving_system} "
                            f"({image_real_name}) — {_image_row[1]}")
        if not _image_row:
            raise Exception(f"서빙 이미지 미등록: serving_system={_serving_system} "
                            f"({image_real_name}) — image 테이블 시드 필요")
        image_id = _image_row.get('id')

        # [멀티엔진 Phase 2] llama.cpp = 단일 노드 엔진(크로스팟 병렬 없음) → 멀티팟 배포 금지.
        #   instance_count>1 이면 1 로 클램프(공유 PVC GGUF 동시쓰기 레이스·N중복 다운로드·비결정 라우팅 차단).
        #   vLLM 은 무영향. command.sh 의 index 0 가드와 이중 방어.
        if deployment_type == "playground" and _serving_system in ("llama_cpp", "tgi", "ollama", "triton", "tensorrt") and instance_count and instance_count > 1:
            print(f"[{_serving_system}] instance_count {instance_count} -> 1 클램프(단일 노드 엔진)")
            instance_count = 1

        if deployment_type == "playground":
            deployment_name = f"playground-{playground_id}"
            llm_type=TYPE.LLM_DEPLOYMENT_TYPE_TO_INT.get(TYPE.PLAYGROUND_MODEL)
        elif deployment_type == "embedding":
            deployment_name = f"playground-{playground_id}-rag-{rag_id}-embedding"
            llm_type=TYPE.LLM_DEPLOYMENT_TYPE_TO_INT.get(TYPE.PLAYGROUND_RAG_EMBEDDING)
        elif deployment_type == "reranker":
            deployment_name = f"playground-{playground_id}-rag-{rag_id}-reranker"
            llm_type=TYPE.LLM_DEPLOYMENT_TYPE_TO_INT.get(TYPE.PLAYGROUND_RAG_RERANKER)
        
        # check: 이름 유효성 확인
        if is_good_name(name=deployment_name) == False:
            raise Exception("유효하지 않은 이름입니다.")
        # check: 이름 존재 확인                
        if db.check_workspace_deployment_name(deployment_name=deployment_name, workspace_id=workspace_id):
            raise Exception("이미 존재하는 이름입니다.")
        
        # api 주소 생성
        default_api_path = PodName(workspace_name=workspace_name, item_name=deployment_name, item_type=TYPE.DEPLOYMENT_TYPE).get_base_pod_name()

        # 배포 생성
        insert_deployment_result = db.insert_deployment_llm(workspace_id=workspace_id, user_id=user_id, name=deployment_name, access=1, image_id=image_id,
            instance_type=instance_type, instance_id=instance_id, instance_allocate=instance_count, gpu_per_worker=gpu_count,
            deployment_cpu_limit=deployment_cpu_limit, deployment_ram_limit=deployment_ram_limit, api_path=default_api_path, llm=llm_type)
        
        # 배포 ID
        if not insert_deployment_result["result"]:
            print("Create Deployment DB Insert Error: {}".format(insert_deployment_result["message"]))
            raise "Create Deployment DB Insert Error"
        deployment_id = insert_deployment_result["id"]
        return deployment_id
    except Exception as e:
        # traceback.print_exc()
        raise Exception(e)

# 배포 업데이트
async def update_deployment(deployment_id, instance_id, instance_count, gpu_count, playground_id=None):
    try:
        instance_info = db.get_instance(instance_id=instance_id)
        instance_type = instance_info.get("instance_type")
        # [멀티엔진] 재배포 시 serving_system 이 바뀌었을 수 있어 image_id 를 재계산(엔진 전환 반영).
        #   create_deployment(1388-1393) 과 동일 로직. playground 재배포에만 적용
        #   (embedding/reranker 는 항상 vllm 이라 image_id 불변 → playground_id 미전달 시 재계산 skip).
        image_id = None
        if playground_id is not None:
            playground_info = await db.get_playground(playground_id=playground_id)
            try:
                _model_cfg = json.loads(playground_info.get("model") or "{}") or {}
            except (ValueError, TypeError):
                _model_cfg = {}
            _serving_system = settings.resolve_serving_system(_model_cfg.get("serving_system"))
            # [멀티엔진] 단일 노드 엔진(llama.cpp/tgi/ollama)은 재배포에서도 instance_count>1 금지
            #   (create_deployment 클램프와 동형 — 유휴 비-head 파드가 8555 를 안 여는 문제 차단).
            if _serving_system in ("llama_cpp", "tgi", "ollama", "triton", "tensorrt") and instance_count and instance_count > 1:
                print(f"[{_serving_system}] 재배포 instance_count {instance_count} -> 1 클램프(단일 노드 엔진)")
                instance_count = 1
            _serving_image = settings.SERVING_ENGINE_IMAGE_MAP.get(_serving_system, settings.DEPLOYMENT_LLM_IMAGE)
            _img = db.get_image_id_by_real_name(real_name=f"{settings.DOCKER_REGISTRY_URL}{_serving_image}")
            # 이미지행 미등록 시 조용히 옛 image_id 를 유지하면 엔진 전환이 이전 엔진 이미지로 뜬다(무음 오배포) → 명시 실패.
            if not _img:
                raise Exception(f"서빙 이미지 미등록: serving_system={_serving_system} "
                                f"({settings.DOCKER_REGISTRY_URL}{_serving_image}) — image 테이블 시드 필요")
            image_id = _img.get("id")
        if image_id is not None:
            db.update_deployment(deployment_id=deployment_id, instance_id=instance_id, instance_type=instance_type, instance_allocate=instance_count, gpu_per_worker=gpu_count, image_id=image_id)
        else:
            db.update_deployment(deployment_id=deployment_id, instance_id=instance_id, instance_type=instance_type, instance_allocate=instance_count, gpu_per_worker=gpu_count)
    except Exception as e:
        traceback.print_exc()
        raise(str(e))

# 워커 실행
async def run_deployment_playground(playground_id, run_embedding=False, run_reranker=False):
    """1. deployment 워커 실행, playground pod 만 실행시킴, rag pod는 아님"""
    try:
        playground_info = await db.get_playground(playground_id=playground_id)

        # playground deployment
        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is None:
            raise Exception("배포 정보가 없습니다.")
        playground_deployment_info = json.loads(playground_deployment_info)
        deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
        deployment_embedding_id = playground_deployment_info.get("deployment_embedding_id")
        deployment_reranker_id = playground_deployment_info.get("deployment_reranker_id")

        # playground rag
        playground_rag_info = playground_info.get("rag")
        if playground_rag_info is not None:
            playground_rag_info = json.loads(playground_rag_info)
            rag_id = playground_rag_info.get("rag_id")
            rag_chunk_max = playground_rag_info.get("rag_chunk_max")
        else:
            rag_id = None
            rag_chunk_max = None

        # run worker - playground
        await llm_deployment.run_worker(deployment_id=deployment_playground_id, llm_type="playground", llm_id=playground_id,
                                        playground_run_rag_reranker=run_reranker)

        # run worker - embedding
        if run_embedding:
            await llm_deployment.run_worker(deployment_id=deployment_embedding_id, llm_type=TYPE.PLAYGROUND_RAG_EMBEDDING, llm_id=rag_id)

        # run worker - reranker
        if run_reranker:
            # rag_embedding_run: rag의 경우 embedding을 기다려야하지만 playground에서 굳이 기다릴 필요가 있을까?
            rag_embedding_run = 1 if run_embedding else 0
            await llm_deployment.run_worker(deployment_id=deployment_reranker_id, llm_type=TYPE.PLAYGROUND_RAG_RERANKER, llm_id=rag_id, rag_embedding_run=rag_embedding_run)

        # ===========================================================================================
        # RESULT
        # ===========================================================================================
        print("worker run : ", playground_deployment_info)
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)

# 중단
async def stop_playground(playground_id, _dual_cascaded=False):
    partner_stopped = True
    try:
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            return True
        _component_dual = (
            json.loads(playground_info.get("model") or "{}") or {}
        ).get("dual") or {}
        _requires_composite_cleanup = (
            _component_dual.get("mode") == "dual"
            or _component_dual.get("role") == "prompt_child"
        )
        # workspace_id = playground_info.get("workspace_id")

        # Dual 세션: 파트너(부모↔자식)도 함께 중지. 부모/자식 어느 쪽을 stop 해도 짝을 정리.
        # _dual_cascaded=True 로 파트너를 호출 → 파트너는 재-캐스케이드 안 함(무한루프 방지).
        if not _dual_cascaded:
            try:
                _dual = (json.loads(playground_info.get("model") or "{}") or {}).get("dual") or {}
                _partner = _dual.get("prompt_gen_playground_id") or _dual.get("parent_playground_id")
                if _partner:
                    partner_stopped = await stop_playground(
                        playground_id=_partner, _dual_cascaded=True)
            except Exception as e:
                print(f"이중모델 파트너 중지 실패 (playground_id={playground_id}): {e}")
                traceback.print_exc()
                partner_stopped = False

        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is not None:
            playground_deployment_info = json.loads(playground_deployment_info)

            # External partner container 분기 — helm 없이 BFF cancel
            external_job_id = playground_deployment_info.get("external_job_id")
            if external_job_id:
                try:
                    await cancel_infer_job(external_job_id)
                except ExternalInferError as e:
                    # 404 = BFF 가 그 job 을 모른다(이미 정리됨 / BFF 재시작으로
                    # sync infer 추적 휘발). 중지 목적은 이미 달성됐으므로 성공으로
                    # 취급하고 아래 dangling id 정리로 진행한다 — 예전엔 여기서
                    # return False 라 사용자에게 "cancel returned 404" 가 노출되고
                    # id 가 남아 상태 폴링이 영구 404 를 찍었다.
                    # 5xx·네트워크는 일시장애일 수 있어 실패 유지(id 보존 → 재시도).
                    if getattr(e, "status_code", 0) != 404:
                        print(f"외부 플레이그라운드 중지 실패 (playground_id={playground_id}): {e}")
                        traceback.print_exc()
                        return False
                    print(
                        f"외부 job {external_job_id} 이 BFF 에 없음(404) — "
                        f"이미 중지된 것으로 처리 (playground_id={playground_id})"
                    )
                # 중지된 job 을 계속 가리키는 dangling id 제거. 재배포는
                # start_playground 가 model.training_type=='external' 로 다시
                # 파생해 새 job_id 를 기록하므로 이 키가 없어도 된다.
                # deployment_run 등 나머지 배포 설정은 보존.
                playground_deployment_info.pop("external_job_id", None)
                if not await db.update_playground(
                    playground_id=playground_id,
                    deployment=json.dumps(playground_deployment_info),
                ):
                    raise Exception("외부 플레이그라운드 중지 상태 저장 실패")
                await db.delete_playground_test(playground_id)
                return partner_stopped

            deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
            deployment_embedding_id = playground_deployment_info.get("deployment_embedding_id")
            deployment_reranker_id = playground_deployment_info.get("deployment_reranker_id")


            if deployment_embedding_id or deployment_reranker_id:
                playground_rag_info = playground_info.get("rag")
                if playground_rag_info is not None:
                    playground_rag_info = json.loads(playground_rag_info)
                    rag_id = playground_rag_info.get("rag_id")

            if deployment_playground_id is not None:
                await llm_deployment.uninstall_worker(deployment_id=deployment_playground_id, llm_type="playground", llm_id=playground_id)
            if deployment_embedding_id is not None:
                await llm_deployment.uninstall_worker(deployment_id=deployment_embedding_id, llm_type=TYPE.PLAYGROUND_RAG_EMBEDDING, llm_id=rag_id)
            if deployment_reranker_id is not None:
                print(deployment_reranker_id, rag_id)
                await llm_deployment.uninstall_worker(deployment_id=deployment_reranker_id, llm_type=TYPE.PLAYGROUND_RAG_RERANKER, llm_id=rag_id)

            # 게시(D6) 자동 취소 — 중지 시 helm uninstall 로 Kong service 가 prune 되어 /ext 가
            # dangling 되고 키가 유효 잔존 → 게시 가능한 모든 배포(primary+embedding+reranker) 정리(3b-2).
            # deployment row 는 stop에서 유지한다. 이중 합성 정리 실패는 stop 실패로 전파해
            # route/service가 남았는데 성공으로 오인하는 상태를 막는다.
            for _dep_id in (deployment_playground_id, deployment_embedding_id, deployment_reranker_id):
                if _dep_id is None:
                    continue
                try:
                    try:
                        await run_in_threadpool(
                            deployment_api.teardown_deployment_api, _dep_id)
                    finally:
                        await run_in_threadpool(
                            deployment_api.teardown_composite_service, _dep_id)
                except Exception:
                    traceback.print_exc()
                    if _requires_composite_cleanup:
                        raise

            # DB: playground test 기록 삭제
            await db.delete_playground_test(playground_id)
        return partner_stopped
    except Exception as e:
        print(f"플레이그라운드 중지 실패 (playground_id={playground_id}): {e}")
        traceback.print_exc()
        return False

# 테스트 ===================================================================================
async def get_test_options(playground_id):
    result = {
        "dataset_list": [],
        "test_url": None,
        "prompt_gen_playground_id": None,
    }
    try:
        # 평가 서비스가 같은 호출에서 이중 링크를 판별해야 단일은 기존 direct URL fast path를
        # 유지하고, 이중만 /playgrounds/test 체인으로 보낼 수 있다.
        playground_info = await db.get_playground_inference_target(
            playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground")
        workspace_id = playground_info.get("workspace_id")
        base_api_path = playground_info.get("api_path")
        result["prompt_gen_playground_id"] = playground_info.get(
            "prompt_gen_playground_id")

        # dataset_list
        result["dataset_list"] = await db.get_datasets(workspace_id=workspace_id)

        if settings.EXTERNAL_HOST_REDIRECT:
            api_address = settings.EXTERNAL_HOST
        else:
            api_address = f"{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}"
        result["test_url"] = f"{settings.INGRESS_PROTOCOL}://{api_address}/deployment/{base_api_path}"
    except Exception as e:
        traceback.print_exc()
    return result

async def get_test_dataset_options(dataset_id, user_name):
    result = []
    try:
        dataset_info = db_dataset.get_dataset(dataset_id=dataset_id)
        workspace_id = dataset_info.get("workspace_id")
        workspace_info = db.get_workspace(workspace_id=workspace_id)

        user_id = db.get_user(user_name=user_name).get("id")
        user_uuid = user_id + settings.USER_UUID_SET
        
        storage = PATH.JF_DATA_STORAGE_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"] ,WORKSPACE_NAME=workspace_info["name"])
        directory = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"] ,WORKSPACE_NAME=workspace_info["name"] , ACCESS=dataset_info["access"] , DATASET_NAME=dataset_info["name"])
        pod_playground_dataset_path = "/datasets" + directory.replace(storage, '')
        
        print(directory)
        # Check if directory exists
        if not os.path.exists(directory):
            return result

        # Asynchronously find files and folders
        for item in Path(directory).rglob('*'):
            item_metadata = item.stat()
            item_uuid = item_metadata.st_uid
            owner = common.get_own_user(uuid=item_uuid) if item_uuid != 0 else "admin"

            if item.is_dir():
                continue
            
            if item.is_file() and item.suffix not in ['.arrow', '.csv', '.txt', '.json', '.jsonl', '.zst']:
                continue

            # result.append({
            #     # playground pod은 테스트 전에 실행하므로, 어떤 경로를 데이터셋을 쓸지 모르기때문에, access 경로부터 알려준다.
            #     "file_path": pod_playground_dataset_path + str(item.relative_to(directory)),
            #     "is_owner": user_name, # item_uuid == user_uuid,
            #     "is_folder": True if item.is_dir() else False
            # })
            
            dataset_name_str = str(item)
            try:
                input_list = []
                try:
                    async with aiofiles.open(dataset_name_str, mode='r', encoding='utf-8') as f:
                        lines = await f.readlines()
                        for line in lines:
                            input_list.append(line.strip())
                except:
                    traceback.print_exc()
                    print("파일 내용 읽기 실패")

                result.append({
                    "owner": owner, # item_uuid == user_uuid,
                    "file_name" : dataset_name_str.replace(directory, "").lstrip("/"), # 파일 이름
                    "input_list" : input_list, # 파일 내용
                })
            except:
                traceback.print_exc()
                pass
    except Exception as e:
        traceback.print_exc()
    return result

# async def get_playground_deployment_monitoring(playground_id):
#     result = {"playground_id" : None, "embedding_id" : None, "reranker_id" : None}
#     try:
#         # playground -> playground_deployment
#         playground_info = await db.get_playground(playground_id=playground_id)
#         if playground_info is None:
#             raise Exception("Not Exist Playground")
        
#         playground_deployment_info = playground_info.get("deployment")
#         if playground_deployment_info is None: #정보 없을경우 세팅도 안된 상태
#             return result
        
#         # init deployment
#         playground_deployment_info = json.loads(playground_deployment_info)
#         playground_id = playground_deployment_info.get("deployment_playground_id")
#         embedding_id = playground_deployment_info.get("deployment_embedding_id")
#         reranker_id = playground_deployment_info.get("deployment_reranker_id")
        
#         result["playground_id"] = playground_id
#         result["embedding_id"] = embedding_id
#         result["reranker_id"] = reranker_id
#         return result
#     except:
#         traceback.print_exc()
#         return result

async def get_test_log(playground_id):
    """
    플레이그라운드 종료하면 로그 삭제됨
    """
    result = []
    try:
        test_log_list = await db.get_test_log_list(playground_id=playground_id)
        for item in test_log_list:
            # print(item.get("end_datetime") - item.get("start_datetime"))
            start_datetime = item.get("start_datetime")
            end_datetime = item.get("end_datetime")
            result.append({
                "type" : item.get("type"),
                "input" : item.get("input"),
                "output" : item.get("output"),
                "model" : item.get("model"),
                "rag" : item.get("rag"),
                "prompt" : item.get("prompt"),
                "start_datatime" : start_datetime.strftime("%Y-%m-%d %H:%M:%S"),    
                "end_datatime" : end_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "response_time" : (end_datetime - start_datetime).total_seconds(),    
            })
    except:
        traceback.print_exc()
    return result

async def get_test_download(playground_id):
    result = [["type", "input", "output", "model", "rag", "prompt", "start_datetime", "end_datetime", "response_time"]]
    try:
        playground_info = await db.get_playground(playground_id=playground_id)
        playground_name = playground_info.get("name")
        
        test_log_list = await db.get_test_log_list(playground_id=playground_id)
        for item in test_log_list:
            start_datetime = item.get("start_datetime")
            end_datetime = item.get("end_datetime")
            result.append([item.get("type"), item.get("input"), item.get("output"), item.get("model"), item.get("rag"), item.get("prompt"), 
                           item.get("start_datetime").strftime("%Y-%m-%d %H:%M:%S"), item.get("end_datetime").strftime("%Y-%m-%d %H:%M:%S"),
                           (end_datetime - start_datetime).total_seconds()])
        return common.csv_response_generator(data_list=result, filename=f"playground_{playground_name}_log")
    except:
        traceback.print_exc()
        return None

# ── 이중모델 추론(SP-7 슬라이스) — LLM1(프롬프트 생성기) → LLM2(추론) 체인 ──────────────
# 고려대 LLM1 프롬프트 생성기의 내부 baseline(메타프롬프트). 고려대 컨테이너 수령 전 동작.
_PROMPT_GEN_META = (
    "당신은 프롬프트 엔지니어입니다. 아래 사용자 요청을, AI 어시스턴트가 더 정확하고 구체적으로 "
    "답변할 수 있도록 명확하고 상세한 한국어 프롬프트로 다시 작성하세요. 설명 없이 재작성된 "
    "프롬프트만 출력하세요."
)
_DUAL_PROMPT_MAX = 8000   # LLM1 출력(→LLM2 프롬프트) 길이 cap(폭주 방지)
_DUAL_EXAMPLES_MAX = 10        # 예시기반 최적화(WBS 4.2) — LLM1 에 넣을 few-shot 예시 최대 개수
_DUAL_FIELD_MAX = 2000         # 시스템프롬프트/예시 각 필드 길이 cap(LLM1 프롬프트 폭주 방지)
_DUAL_BATCH_MAX = 10           # 이중 배치 동기 샘플 상한(체인=2N 추론 → 요청 타임아웃 방지)
# 데이터셋 컬럼 자동 감지(evaluate 앱과 동일 후보) — jsonl/json dict 에서 prompt/reference 추출.
_DS_PROMPT_FIELDS = ["prompt", "instruction", "input", "question", "source", "query"]
_DS_REFERENCE_FIELDS = ["reference", "output", "response", "answer", "target", "completion", "label"]
# 이중 batch → 외부 SDS(VLM) 용 per-sample 멀티모달 입력 필드(데이터셋 행이 실어줄 때).
#   image = 데이터셋 디렉터리 하위 상대경로(샌드박스 검증 후 base64). 미지정 시 요청의 공유 payload 폴백.
_DS_IMAGE_FIELDS = ["image", "image_path", "img", "image_file"]
_DS_AIS_FIELDS = ["ais_rows", "ais", "ais_data"]
_DS_IMAGE_MAX_BYTES = 12 * 1024 * 1024   # 샘플 이미지 상한(배치 N장 base64 → 메모리 폭주 방지)
_DS_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def _build_dual_meta(test_question, system_prompt=None, examples=None):
    """LLM1 메타프롬프트 구성 — 예시기반 최적화(WBS 4.2). dual_test/batch 공용."""
    meta_parts = [_PROMPT_GEN_META]
    if system_prompt and str(system_prompt).strip():
        meta_parts.append(f"[시스템 지침]\n{str(system_prompt).strip()[:_DUAL_FIELD_MAX]}")
    if isinstance(examples, list):
        ex_lines = []
        for ex in examples[:_DUAL_EXAMPLES_MAX]:
            if not isinstance(ex, dict):
                continue
            q = str(ex.get("query") or "").strip()[:_DUAL_FIELD_MAX]
            a = str(ex.get("answer") or "").strip()[:_DUAL_FIELD_MAX]
            if q or a:
                ex_lines.append(f"질의: {q}\n답변: {a}")
        if ex_lines:
            meta_parts.append("[예시]\n" + "\n\n".join(ex_lines))
    meta_parts.append(f"[사용자 요청]\n{test_question}")
    return "\n\n".join(meta_parts)


def _dual_optimized_or_fallback(optimized, question):
    """LLM1 재작성 출력이 비었거나 퇴행적이면 원 질문으로 폴백.
    baseline 메타프롬프트(고려대 실 LLM1 컨테이너 수령 前 stopgap)가 약한 모델에서
    '[재작성된 프롬프트]' 같은 헤더만 뱉고 멈추는 케이스 방어 — LLM2 가 그 조각을 이어받아
    딴소리하는 것을 차단한다. 재작성은 '명확하고 상세한' 프롬프트라 원 질문보다 길어야 정상 →
    원 질문보다 길지 않으면(무출력·에코·플레이스홀더) 원 질문 사용(LLM2 가 직접 답변 = 안전 폴백)."""
    opt = (optimized or "").strip()
    q = (question or "").strip()
    if not opt or len(opt) <= len(q):
        return q
    return opt


async def get_stored_dual_prompt_gen(playground_id):
    """저장된 dual LLM1을 엄격히 조회한다. DB/JSON 오류는 호출자에게 전파한다."""
    # 요청 LLM1 허용 여부를 정할 때 조회 실패를 '링크 없음'으로 오인하면 우회가 다시 열리므로,
    # 보안 결정용 경로는 예외를 삼키지 않는다.
    pg = await db.get_playground(playground_id=playground_id)
    if not pg:
        return None
    dual = (json.loads(pg.get("model") or "{}") or {}).get("dual") or {}
    if dual.get("mode") == "dual":
        return dual.get("prompt_gen_playground_id")
    return None


async def resolve_dual_prompt_gen(playground_id):
    """추론 playground 가 이중 세션의 부모면 링크된 프롬프트생성 playground_id, 아니면 None.

    조회 실패는 None 으로 낮추지 않고 그대로 전파한다(위 get_stored_dual_prompt_gen 과 같은 규약).
    호출자(batch_stream·invoke_dual_session)는 None 을 '단독 모드'로 해석하므로, 삼키면 실제
    이중 세션이 일시적 DB 오류만으로 LLM1 을 건너뛰고 LLM2 만 돌린 결과를 이중 결과로 반환한다
    (조용한 품질 저하 + 게시 API 의 LLM1 우회). '이중이 아님'과 '모르겠음'은 구분해야 한다.
    링크가 없는 단독 playground 는 여전히 정상적으로 None 을 받는다."""
    return await get_stored_dual_prompt_gen(playground_id)


async def _playground_test_url(playground_id):
    """배포된 playground 의 추론 test_url 구성(playground_test 와 동일 규칙)."""
    pg = await db.get_playground(playground_id=playground_id)
    if not pg:
        raise Exception(f"playground {playground_id} not found")
    dep = pg.get("deployment")
    if not dep:
        raise Exception(f"playground {playground_id} has no deployment (not running)")
    dep = json.loads(dep)
    dpid = dep.get("deployment_playground_id")
    if not dpid:
        raise Exception(f"playground {playground_id} is not a running internal deployment")
    dinfo = db.get_deployment(deployment_id=dpid)
    api_path = (dinfo or {}).get("api_path")
    if not api_path:
        raise Exception(f"playground {playground_id} deployment has no api_path")
    if settings.EXTERNAL_HOST_REDIRECT:
        return f"{settings.INGRESS_PROTOCOL}://{settings.EXTERNAL_HOST}/deployment/{api_path}"
    return (f"{settings.INGRESS_PROTOCOL}://{settings.EXTERNAL_HOST}:"
            f"{settings.EXTERNAL_HOST_PORT}/deployment/{api_path}")


async def _infer_question(test_url, question, session_id=None, timeout=1800):
    """단일 질문 추론 1건 → 출력 텍스트. (test_url 로 question POST). timeout 은 호출별 지정
    (LLM1 프롬프트 재작성은 짧게)."""
    async with httpx.AsyncClient() as client:
        r = await client.post(test_url, json={
            "test_type": "question", "session_id": session_id,
            "test_dataset_id": None, "test_dataset_filename": None,
            "test_question": question}, timeout=timeout)
    if r.status_code == 401:
        raise Exception("Setting up the playground")
    if r.status_code == 402:
        raise Exception("Playground Model Error")
    if r.status_code != 200:
        # 에러 바디가 JSON 이 아닐 수 있음(nginx 502 HTML, 평문 등) → 원 에러 보존.
        try:
            body = r.json()
        except Exception:
            body = r.text
        raise Exception(f"inference HTTP {r.status_code}: {str(body)[:300]}")
    try:
        data = r.json()
    except Exception:
        return (r.text or "").strip()
    if isinstance(data, list) and data:
        return (data[0] or {}).get("output", "")
    if isinstance(data, dict):
        return data.get("output", "")
    return ""


async def playground_dual_test(playground_id, prompt_gen_playground_id, test_question, session_id=None,
                               system_prompt=None, examples=None, external_payload=None):
    """이중모델 추론 — LLM1(prompt_gen_playground_id) 가 메타프롬프트로 사용자 질문을 최적
    프롬프트로 재작성 → LLM2(playground_id, 현 배포모델) 가 그 프롬프트로 추론. 결과에
    optimized_prompt 동봉(화면에 원질문→최적프롬프트→답변 표시). LLM1 실패 시 원 질문 폴백.
    system_prompt/examples(예시기반 최적화, WBS 4.2) 지정 시 LLM1 메타프롬프트에 주입."""
    if not test_question:
        raise Exception("test_question is required for dual-model inference")
    if not prompt_gen_playground_id:
        raise Exception("prompt_gen_playground_id is required for dual-model inference")
    # 같은 워크스페이스 가드 — request-supplied prompt_gen_playground_id 로 타 워크스페이스
    # 배포모델을 체인(교차테넌트 추론·출력 누출)하는 것을 차단. run_benchmark 등과 동일 패턴.
    pg2 = await db.get_playground(playground_id=playground_id)
    pg1 = await db.get_playground(playground_id=prompt_gen_playground_id)
    # 메시지 통합(존재/타워크스페이스 구분 노출 시 id 열거 오라클) — 동일 generic 에러.
    if not pg1 or not pg2 or pg1.get("workspace_id") != pg2.get("workspace_id"):
        raise Exception("prompt generator(LLM1) not available")
    # 1) LLM1: 프롬프트 재작성 (재작성은 짧으므로 timeout 300s 로 핸들러 점유 제한)
    try:
        gen_url = await _playground_test_url(prompt_gen_playground_id)
    except Exception as e:
        raise Exception(f"프롬프트 생성기(LLM1) 사용 불가: {e}")
    # 예시기반 최적화(WBS 4.2): 시스템 지침 + few-shot 예시를 LLM1 메타프롬프트에 주입.
    meta = _build_dual_meta(test_question, system_prompt, examples)
    # LLM1 재작성 → 퇴행(무출력·플레이스홀더 헤더·에코) 시 원 질문 폴백(LLM2 가 직접 답변)
    optimized = _dual_optimized_or_fallback(
        await _infer_question(gen_url, meta, session_id, timeout=300), test_question)
    if len(optimized) > _DUAL_PROMPT_MAX:
        optimized = optimized[:_DUAL_PROMPT_MAX]    # LLM1 출력(→LLM2 프롬프트) 길이 cap
    # 2) LLM2: 최적 프롬프트로 추론. LLM2 가 외부 SDS(VLM)면 BFF /jobs/{id}/run 경로(text→SDS),
    #    아니면 내부 vLLM 경로. 어느 쪽이든 LLM1 출력(optimized)이 프롬프트로 들어감.
    _pg2_dep = {}
    try:
        _pg2_dep = json.loads(pg2.get("deployment") or "{}") or {}
    except Exception:
        _pg2_dep = {}
    _ext_job_id = _pg2_dep.get("external_job_id")
    if _ext_job_id:
        # 외부 SDS(VLM): optimized 를 custom_prompt 로 연결. image_base64 + ais_rows(my_ship=1) 필수
        #   (SDS 계약 — 텍스트만으로는 추론 불가). playground_test external 분기와 동일 파싱.
        answer, inner = await _infer_sds_sample(_ext_job_id, optimized, external_payload)
        return [{"output": answer, "optimized_prompt": optimized,
                 "original_question": test_question, "result": inner}], None
    try:
        ans_url = await _playground_test_url(playground_id)
    except Exception as e:
        raise Exception(f"추론 모델(LLM2) 사용 불가: {e}")
    answer = await _infer_question(ans_url, optimized, session_id, timeout=1800)
    return [{"output": answer, "optimized_prompt": optimized,
             "original_question": test_question}], None


async def _infer_sds_sample(job_id, optimized_prompt, base_payload, image_b64=None, ais_rows=None):
    """외부 SDS(VLM) 1회 추론 — LLM1 출력을 custom_prompt 로 연결(text→SDS). Direct/Batch 공용.
    SDS 계약상 image_base64 + ais_rows(my_ship=1 포함) 필수(텍스트만으로는 추론 불가).
    응답은 playground_test external 분기와 동일하게 result.result 중첩 파싱. 반환: (text, inner)."""
    payload = dict(base_payload or {})
    payload["custom_prompt"] = optimized_prompt
    if image_b64 is not None:
        payload["image_base64"] = image_b64
    if ais_rows is not None:
        payload["ais_rows"] = ais_rows
    if not payload.get("image_base64"):
        raise Exception("external_payload.image_base64 is required")
    _ais = payload.get("ais_rows") or []

    def _is_my_ship(row):
        # 데이터셋(업로드 JSON)에서 온 값은 임의 타입일 수 있음 → int() 크래시 대신 비매칭 처리.
        try:
            return int(row.get("my_ship", 0)) == 1
        except (TypeError, ValueError):
            return False

    if not _ais or not any(_is_my_ship(r) for r in _ais if isinstance(r, dict)):
        raise Exception("external_payload.ais_rows must contain at least one row with my_ship=1")
    try:
        raw = await run_inference(job_id, params=payload)
    except ExternalInferError as e:
        traceback.print_exc()
        raise Exception(f"External inference failed [{e.status_code}]: {e}")
    outer = raw.get("result") if isinstance(raw, dict) else None
    inner = outer.get("result") if isinstance(outer, dict) and isinstance(outer.get("result"), dict) else outer
    if not isinstance(inner, dict):
        inner = {}
    return inner.get("text", ""), inner


async def _encode_dataset_image(dir_real, rel_path):
    """데이터셋 디렉터리 하위 이미지 → base64. 경로 탈출/심링크 이탈 차단(_read_dataset_samples 동형),
    확장자 allowlist + 크기 상한. 읽기 실패/부적합은 "" 반환(배치 전체 실패 방지 — 호출측이 폴백)."""
    if not rel_path or "\x00" in str(rel_path):
        return ""
    if not str(rel_path).lower().endswith(_DS_IMAGE_EXTS):
        return ""
    target = os.path.realpath(os.path.join(dir_real, str(rel_path)))
    if os.path.commonpath([target, dir_real]) != dir_real:
        return ""
    if not os.path.isfile(target):
        return ""
    try:
        if os.path.getsize(target) > _DS_IMAGE_MAX_BYTES:
            return ""
        async with aiofiles.open(target, mode="rb") as f:
            return base64.b64encode(await f.read()).decode("ascii")
    except Exception:
        traceback.print_exc()
        return ""


_DS_JSON_MAX_BYTES = 64 * 1024 * 1024   # JSON 배열(pretty) 전체 파싱 상한
_LLAVA_IMAGE_TOKEN = "<image>"
# SDS 학습 데이터셋(LLaVA)의 '[선박 AIS 정보]' 라인 — 자선/주변선박 공통 포맷.
_AIS_LINE_RE = re.compile(
    r'^-\s*(?P<kind>자선|주변선박)\s*\(ID:(?P<sid>\d+)\)'
    r'(?:.*?위도:(?P<lat>-?[\d.]+))?'
    r'(?:.*?경도:(?P<lon>-?[\d.]+))?'
    r'(?:.*?속도:(?P<knot>-?[\d.]+))?'
    r'(?:.*?방향:(?P<heading>-?[\d.]+))?'
    r'(?:.*?선체:(?P<length>[\d.]+)m\s*[×x]\s*(?P<width>[\d.]+)m)?'
    r'(?:.*?흘수:(?P<draft>[\d.]+)m)?'
)


def _parse_ais_rows_from_text(text):
    """LLaVA human 발화의 '[선박 AIS 정보]' 블록 → 구조화 ais_rows.
    SDS(EVA VLM)는 ais_rows(자선 my_ship=1 포함)를 필수로 받지만 학습 데이터셋은 AIS를
    텍스트로만 싣는다 → 배치 추론용으로 되살린다. 포맷이 바뀌면 매치 실패([] 반환)."""
    rows = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line.startswith("-"):
            continue
        m = _AIS_LINE_RE.match(line)
        if not m:
            continue
        g = m.groupdict()

        def _num(key, default=0.0):
            try:
                return float(g.get(key)) if g.get(key) is not None else default
            except (TypeError, ValueError):
                return default

        rows.append({
            "ship_id": int(g["sid"]),
            "my_ship": 1 if g["kind"] == "자선" else 0,
            "latitude": _num("lat"), "longitude": _num("lon"),
            "knot": _num("knot"), "heading": _num("heading"),
            "length": _num("length"), "width": _num("width"), "draft": _num("draft"),
        })
    return rows


def _llava_turns(obj):
    """conversations(LLaVA) → (prompt, reference). human=프롬프트(<image> 토큰 제거), gpt=정답."""
    conv = obj.get("conversations")
    if not isinstance(conv, list):
        return "", ""
    prompt = reference = ""
    for turn in conv:
        if not isinstance(turn, dict):
            continue
        who = (turn.get("from") or "").lower()
        val = str(turn.get("value") or "")
        if who == "human" and not prompt:
            prompt = val.replace(_LLAVA_IMAGE_TOKEN, "").strip()
        elif who in ("gpt", "assistant") and not reference:
            reference = val.strip()
    return prompt, reference


def _sample_from_record(obj, fallback_line, with_external):
    """데이터셋 레코드(dict) 또는 plain 라인 → 배치 샘플. JSONL/JSON배열 공용.
    프롬프트/정답은 표준 필드 우선, 없으면 LLaVA conversations. external(SDS)이면
    image 상대경로(image_path) + ais_rows(필드 없으면 발화 텍스트에서 파싱).
    ⚠️ 이미지는 여기서 base64 로 만들지 않는다 — 샘플당 ~2MB 라 N 개를 미리 들고 있으면
    컨테이너 메모리(limit 256M, 앱 상시 ~136M)를 압박한다. 인코딩은 호출측이 추론 직전에 1건씩."""
    prompt, reference = "", ""
    img_rel, ais_val = "", None
    if isinstance(obj, dict):
        lower = {k.lower(): v for k, v in obj.items()}
        prompt = next((str(lower[c]) for c in _DS_PROMPT_FIELDS if lower.get(c) is not None), "")
        reference = next((str(lower[c]) for c in _DS_REFERENCE_FIELDS if lower.get(c) is not None), "")
        if not prompt:
            prompt, conv_ref = _llava_turns(obj)
            reference = reference or conv_ref
        if with_external:
            img_rel = next((str(lower[c]) for c in _DS_IMAGE_FIELDS if lower.get(c)), "")
            ais_val = next((lower[c] for c in _DS_AIS_FIELDS if lower.get(c) is not None), None)
            if not isinstance(ais_val, list):
                # 구조화 AIS 필드가 없는 학습 데이터셋 → 발화 텍스트에서 복원.
                ais_val = _parse_ais_rows_from_text(prompt) or None
    if not prompt:
        prompt = fallback_line
    if not prompt:
        return None
    sample = {"input": prompt, "reference": reference}
    if with_external:
        sample["image_path"] = img_rel or ""
        sample["ais_rows"] = ais_val if isinstance(ais_val, list) else None
    return sample


async def _read_dataset_samples(dataset_id, filename, limit, workspace_id=None, with_external=False):
    """데이터셋 파일에서 최대 limit 샘플 → ([{input, reference, ...}], dir_real). jsonl/json dict 는 prompt/
    reference 컬럼 자동 감지, plain 라인은 input 만(reference 없음). 경로 탈출 차단.
    workspace_id 지정 시 데이터셋이 세션과 같은 워크스페이스인지 검증(교차테넌트 읽기 차단)."""
    if not filename or "\x00" in str(filename):
        raise Exception("Error: invalid dataset file path")
    dataset_info = db_dataset.get_dataset(dataset_id=dataset_id)
    if not dataset_info:
        raise Exception("Error: dataset not found")
    # 워크스페이스 일치(교차테넌트 읽기 차단) — 타입 정규화(int vs str 우회 방지)
    if workspace_id is not None:
        try:
            if int(dataset_info.get("workspace_id") or 0) != int(workspace_id):
                raise Exception("Error: invalid dataset selection")
        except (TypeError, ValueError):
            raise Exception("Error: invalid dataset selection")
    workspace_info = db.get_workspace(workspace_id=dataset_info.get("workspace_id"))
    directory = PATH.JF_DATA_DATASET_PATH.format(
        STORAGE_NAME=workspace_info["data_storage_name"], WORKSPACE_NAME=workspace_info["name"],
        ACCESS=dataset_info["access"], DATASET_NAME=dataset_info["name"])
    dir_real = os.path.realpath(directory)
    target = os.path.realpath(os.path.join(directory, filename))
    # filename 은 반드시 데이터셋 디렉터리 하위(경로 탈출/심링크 이탈 차단)
    if os.path.commonpath([target, dir_real]) != dir_real:
        raise Exception("Error: invalid dataset file path")
    if not os.path.isfile(target):
        raise Exception("Error: dataset file not found")
    samples = []
    # 포맷 판별 — 첫 비공백 문자가 '[' 면 JSON 배열(pretty-printed, SDS 학습셋 형식),
    #   아니면 JSONL 스트리밍(limit 도달 즉시 중단 → 대용량 OOM/hang 방지).
    async with aiofiles.open(target, mode="r", encoding="utf-8") as f:
        head = await f.read(64)
    if head.lstrip().startswith("["):
        if os.path.getsize(target) > _DS_JSON_MAX_BYTES:
            raise Exception("Error: dataset file too large to parse as JSON array")
        async with aiofiles.open(target, mode="r", encoding="utf-8") as f:
            content = await f.read()
        try:
            records = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            raise Exception("Error: dataset file is not valid JSON")
        if not isinstance(records, list):
            records = [records]
        for obj in records:
            sample = _sample_from_record(obj, "", with_external)
            if sample:
                samples.append(sample)
            if len(samples) >= limit:
                break
        return samples, dir_real

    async with aiofiles.open(target, mode="r", encoding="utf-8") as f:
        async for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                obj = None
            sample = _sample_from_record(obj, line, with_external)
            if sample:
                samples.append(sample)
            if len(samples) >= limit:
                break
    return samples, dir_real


async def batch_stream(playground_id, prompt_gen_playground_id=None, dataset_id=None, filename=None,
                       sample_count=5, metrics=None, session_id=None,
                       system_prompt=None, examples=None, external_payload=None):
    """데이터셋 일괄 추론 스트리밍 제너레이터 — 샘플 하나가 끝날 때마다 결과를 yield.
    동기 응답(샘플당 ~16s × N)이 API 게이트웨이 read timeout(60s)에 걸려 504 가 되는 문제 해결.
    이벤트: {"type":"start"|"sample"|"summary"}. dual_batch_test 는 이 제너레이터를 소비(로직 단일화).

    prompt_gen_playground_id 유무로 이중/단독 두 모드를 겸한다(루프·채점·스트리밍 규약 동일):
      - 있으면 이중모델(WBS 4.3): 샘플마다 LLM1 재작성 → LLM2 추론(추론 2N 회).
      - 없으면 단독 배포: 데이터셋 프롬프트를 그대로 추론 모델에 보낸다(추론 N 회).
        SDS(외부 VLM) 단독에서는 이 프롬프트가 custom_prompt 가 되어 데이터셋 조건을 재현하므로
        reference 채점이 의미를 갖는다(빈 프롬프트면 VLM 기본 프롬프트로 돌아 정답과 어긋남).
    reference 있으면 인-프로세스 BLEU/ROUGE 채점. 동기라 N 상한(_DUAL_BATCH_MAX) 고정 —
    SP-5(비동기 K8s 평가)와 별개의 세션 대상 경량 배치. prompt_gen 은 route 가 세션에서 파생."""
    pg2 = await db.get_playground(playground_id=playground_id)
    if not pg2:
        raise Exception("Error: playground not found")
    if prompt_gen_playground_id:
        # 같은 워크스페이스 가드(dual_test 동형) + 메시지 통합(열거 오라클 회피)
        pg1 = await db.get_playground(playground_id=prompt_gen_playground_id)
        if not pg1 or pg1.get("workspace_id") != pg2.get("workspace_id"):
            raise Exception("Error: prompt generator(LLM1) not available")
    try:
        n = max(1, min(int(sample_count), _DUAL_BATCH_MAX))
    except (TypeError, ValueError):
        n = 5
    metric_set = [m for m in (metrics or ["bleu", "rouge"]) if m in dual_metrics.SELF_METRICS] or ["bleu", "rouge"]
    # LLM2 가 외부 SDS(VLM)면 배치도 BFF /jobs/{id}/run 경로(text→SDS). 이미지/AIS 는
    #   데이터셋 행(per-sample) 우선, 없으면 요청의 공유 external_payload 폴백.
    _pg2_dep = {}
    try:
        _pg2_dep = json.loads(pg2.get("deployment") or "{}") or {}
    except Exception:
        _pg2_dep = {}
    _ext_job_id = _pg2_dep.get("external_job_id")
    _shared = dict(external_payload or {})
    _shared_img = _shared.get("image_base64") or ""
    _shared_ais = _shared.get("ais_rows") if isinstance(_shared.get("ais_rows"), list) else None
    # dir_real 을 함께 받는다 — 이미지는 미리 인코딩하지 않고 샘플 직전에 1건씩 만든다.
    samples, ds_dir = await _read_dataset_samples(dataset_id, filename, n, workspace_id=pg2.get("workspace_id"),
                                                 with_external=bool(_ext_job_id))
    if not samples:
        raise Exception("Error: no usable samples in dataset")
    gen_url = await _playground_test_url(prompt_gen_playground_id) if prompt_gen_playground_id else None
    ans_url = None if _ext_job_id else await _playground_test_url(playground_id)
    # 활성 최적화 프롬프트 — 루프 밖에서 1회만 조회한다(샘플마다 DB 를 때리지 않게).
    #   dual 은 LLM1 이 질의마다 프롬프트를 만들므로 주입 대상이 아니다.
    _batch_opt = None if prompt_gen_playground_id else await _active_prompt_text(playground_id)
    rows, preds, refs, has_ref = [], [], [], False
    yield {"type": "start", "total": len(samples)}
    for idx, s in enumerate(samples):
        q = s["input"]
        ref = s.get("reference") or ""
        if gen_url:
            meta = _build_dual_meta(q, system_prompt, examples)
            # LLM1 재작성 → 퇴행 시 원 질문 폴백(playground_dual_test 동형)
            optimized = _dual_optimized_or_fallback(
                await _infer_question(gen_url, meta, session_id, timeout=300), q)
        else:
            # 단독 배포 — LLM1 단계가 없다. 대신 활성 최적화가 있으면 여기서 주입한다.
            #   ⚠️ 데이터셋 배치 경로가 둘이다: /test(test_type=dataset)와 이 /batch/sse.
            #      FE 는 단독 external(SDS)·이중을 전부 이 경로로 보내므로, 저쪽만
            #      고치면 토글이 ON 인데 배치에는 반영되지 않는 상태가 된다.
            #   조립 형식은 대상에 따라 다르다 — internal 은 Query:/Response: 규약,
            #      SDS 는 custom_prompt 가 곧 질문이라 지시문을 앞에 잇기만 한다
            #      (playground_test 의 external 분기와 같은 판단).
            if not _batch_opt:
                optimized = q
            elif _ext_job_id:
                optimized = f"{_batch_opt}\n\n{q}"
            else:
                optimized = f"{_batch_opt}\n\nQuery: {q}\nResponse:"
        if len(optimized) > _DUAL_PROMPT_MAX:
            optimized = optimized[:_DUAL_PROMPT_MAX]
        if _ext_job_id:
            # 이미지는 이 샘플을 보낼 때만 인코딩하고 루프를 벗어나면 버린다 — 샘플당 ~2MB 라
            #   N 개를 상주시키면 컨테이너 메모리(limit 256M)에서 배치가 커질수록 위험해진다.
            _img = await _encode_dataset_image(ds_dir, s["image_path"]) if s.get("image_path") else ""
            answer, _ = await _infer_sds_sample(
                _ext_job_id, optimized, _shared,
                image_b64=(_img or _shared_img),
                ais_rows=(s.get("ais_rows") or _shared_ais))
        else:
            answer = await _infer_question(ans_url, optimized, session_id, timeout=1800)
        row = {"input": q, "optimized_prompt": optimized, "output": answer, "reference": ref}
        if ref:
            has_ref = True
            row.update(dual_metrics.score_pair(answer, ref, metric_set))  # per-sample 점수
            preds.append(answer or "")
            refs.append(ref)
        rows.append(row)
        # 샘플 완료 즉시 스트림 — 3분 배치에서도 게이트웨이가 끊지 않고 부분 결과가 쌓인다.
        yield {"type": "sample", "index": idx + 1, "total": len(samples), **row}
    # 요약은 코퍼스 단위(BLEU 비선형 → per-sample 평균 부정확; evaluate 앱과 동일)
    summary = dual_metrics.corpus_scores(preds, refs, metric_set) if has_ref else {}
    yield {"type": "summary", "summary": summary, "sample_count": len(rows),
           "has_reference": has_ref, "metric_set": metric_set}


async def dual_batch_test(playground_id, prompt_gen_playground_id, dataset_id, filename,
                          sample_count=5, metrics=None, session_id=None,
                          system_prompt=None, examples=None, external_payload=None):
    """배치 동기 응답(하위호환) — batch_stream 을 끝까지 소비해 기존 스키마로 반환.
    prompt_gen_playground_id=None 이면 단독 배포 배치(LLM1 단계 없음)로 동작한다.
    ⚠️ 샘플 수가 많으면 게이트웨이 타임아웃(60s) 위험 → FE 는 SSE(/batch/sse) 사용 권장."""
    rows, final = [], {}
    async for ev in batch_stream(
            playground_id=playground_id, prompt_gen_playground_id=prompt_gen_playground_id,
            dataset_id=dataset_id, filename=filename, sample_count=sample_count,
            metrics=metrics, session_id=session_id, system_prompt=system_prompt,
            examples=examples, external_payload=external_payload):
        if ev.get("type") == "sample":
            rows.append({k: v for k, v in ev.items() if k not in ("type", "index", "total")})
        elif ev.get("type") == "summary":
            final = ev
    return {"samples": rows, "summary": final.get("summary", {}),
            "sample_count": final.get("sample_count", len(rows)),
            "has_reference": final.get("has_reference", False),
            "metric_set": final.get("metric_set", [])}, None


async def playground_test(playground_id, test_type, test_dataset_id, test_dataset_filename, test_question, session_id=None, network_load=0, external_payload: dict = None, images: list = None):
    """
    network_load: 없음 0, 저 1, 중 2, 고3
    external_payload: external partner container 분기 시 /run body params (image_base64, ais_rows 등)
    """
    result = None
    message = None
    try:
        # playground
        playground_info = await db.get_playground(playground_id=playground_id)
        if playground_info is None:
            raise Exception("Not Exist Playground")

        playground_deployment_info = playground_info.get("deployment")
        if playground_deployment_info is None:
            raise Exception("Not Exist Playground Deployment")
        playground_deployment_info = json.loads(playground_deployment_info)
        deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
        external_job_id = playground_deployment_info.get("external_job_id")

        # 중지 상태(external_job_id 정리됨 + internal 배포 없음)에서 테스트가 들어오면
        # 아래 internal 경로가 get_deployment(None) 을 타 모호한 AttributeError 를 낸다.
        if not external_job_id and deployment_playground_id is None:
            raise Exception("Playground is not deployed — 배포를 먼저 시작하세요")

        # ── External partner container 분기 ─────────────────────────────
        if external_job_id:
            payload = external_payload or {}
            if not payload.get("image_base64"):
                raise Exception("external_payload.image_base64 is required")
            ais_rows = payload.get("ais_rows") or []
            if not ais_rows or not any(
                int(r.get("my_ship", 0)) == 1 for r in ais_rows if isinstance(r, dict)
            ):
                raise Exception("external_payload.ais_rows must contain at least one row with my_ship=1")
            # 프롬프트 최적화 주입(SDS) — SDS 는 custom_prompt 가 곧 질문이다:
            #   model_manager.py `question = custom_prompt or PROMPT_MAP[output_type]`.
            #   즉 컨테이너의 PROMPT_MAP 은 기본값일 뿐이라 컨테이너 수정 없이 대체된다.
            #   internal 처럼 Query:/Response: 로 조립하지 않는다 — VLM 은 이미지+AIS 를 보고
            #   이 텍스트를 지시문으로 받으므로 원문이 맞다(따라서 응답 트리밍도 불필요).
            #   요청이 custom_prompt 를 명시했으면 그것을 존중하고 없을 때만 주입한다.
            if not payload.get("custom_prompt"):
                _opt_prompt = await _active_prompt_text(playground_id)
                if _opt_prompt:
                    payload = {**payload, "custom_prompt": _opt_prompt}
            try:
                raw = await run_inference(external_job_id, params=payload)
            except ExternalInferError as e:
                traceback.print_exc()
                raise Exception(f"External inference failed [{e.status_code}]: {e}")
            outer = raw.get("result") if isinstance(raw, dict) else None
            inner = outer.get("result") if isinstance(outer, dict) and isinstance(outer.get("result"), dict) else outer
            if not isinstance(inner, dict):
                inner = {}
            text = inner.get("text", "")
            return [{"output": text, "result": inner}], message
        
        # 테스트 url
        deployment_info = db.get_deployment(deployment_id=deployment_playground_id)
        api_path = deployment_info.get("api_path")
        if settings.EXTERNAL_HOST_REDIRECT:
            test_url = f"{settings.INGRESS_PROTOCOL}://{settings.EXTERNAL_HOST}/deployment/{api_path}"
        else:
            test_url = f"{settings.INGRESS_PROTOCOL}://{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}/deployment/{api_path}"
        
        # TODO test url -> 내부 kubernetes dns로 변경
        # workspace_id = deployment_info.get("workspace_id")
        # test_url = f"http://deployment-llm-playground-{playground_id}--service.{TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)}:18555"

        # 프롬프트 최적화 주입 — 활성 최적화가 있으면 질문 앞에 붙인다. 요청이 프롬프트를
        #   싣지 않는 서버 파생 방식(dual 의 prompt_gen 링크와 동일 posture)이라 추론 DTO·FE
        #   변경이 없다.
        #   question(1건)은 플랫폼이 직접 조립한다. dataset(일괄)은 래퍼가 데이터셋을
        #   직접 읽어 샘플을 만들어 플랫폼에 조립 지점이 없으므로, 원문(system_prompt)만
        #   실어 보내고 **조립은 래퍼가** 한다(래퍼 계약 확장, 두 엔진 모두 동일 규약).
        #   래퍼가 옛 버전이면 이 필드를 무시하므로 최적화만 빠지고 추론은 정상 동작한다.
        prompt_injected = False
        batch_system_prompt = None
        if test_type == "question" and test_question:
            test_question, prompt_injected = await _apply_active_prompt_optimization(
                playground_id, test_question)
        elif test_type == "dataset":
            batch_system_prompt = await _active_prompt_text(playground_id)
            prompt_injected = bool(batch_system_prompt)

        # 테스트 실행
        try:
            async with httpx.AsyncClient() as client:
                # images 는 VLM 배포에서만 의미가 있다. 비어 있으면 키를 아예 넣지 않아
                # 옛 래퍼(이미지 미지원)와도 그대로 호환된다.
                _body = {"test_type": test_type, "session_id": session_id,
                         "test_dataset_id": test_dataset_id, "test_dataset_filename": test_dataset_filename,
                         "test_question": test_question,
                         "system_prompt": batch_system_prompt}
                if images:
                    _body["images"] = images
                response = await client.post(test_url, json=_body, timeout=1800)
                if response.status_code == 401:
                    raise Exception("Setting up the playground")
                elif response.status_code == 402:
                    raise Exception("Playground Model Error")
                elif response.status_code == 400:
                    # 래퍼가 이미지 입력을 거부한 경우(형식 오류 · 텍스트 전용 모델).
                    # 사유를 그대로 전해야 사용자가 무엇을 고칠지 안다.
                    try:
                        _detail = response.json().get("detail")
                    except Exception:
                        _detail = response.text[:200]
                    raise Exception(_detail or "이미지 입력이 거부되었습니다")
                elif response.status_code == 200:
                    result = response.json()
                    # 최적화 프롬프트를 주입한 경우만 few-shot 연속 생성분을 잘라낸다.
                    if prompt_injected:
                        result = _trim_fewshot_continuation(result)
                else:
                    raise Exception(str(response.json()))
        except Exception as e:
            raise Exception(e)

        return result, message
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)

import os, asyncio,subprocess
import traceback
from concurrent.futures import ThreadPoolExecutor

# SSH 비밀번호
PASSWORD = "acryl"

def get_hosts():
    try:
        with open('/app/bg-flow-ip-1', 'r') as file1, open('/app/bg-flow-ip-2', 'r') as file2:
            ip_list = [line.strip() for line in file1] + [line.strip() for line in file2]
        
        if len(ip_list) == 0:
            raise Exception("No hosts found")    
        
        return ip_list
    except Exception as e:
        print(f"Error reading files: {e}")
        return []

def ssh_command_async(host, remote_command):
    """
    SSH 명령어를 실행
    """
    ssh_command = f"sshpass -p {PASSWORD} ssh -o StrictHostKeyChecking=no {host} '{remote_command}' &"
    try:
        # 명령 실행
        ret_code = os.system(ssh_command)
        
    except Exception as e:
        print(f"[{host}] Error occurred: {e}")
        
def ssh_command_sync(host, remote_command):
    """
    SSH 명령어를 실행하고 결과를 반환
    """
    ssh_command = f"sshpass -p {PASSWORD} ssh -o StrictHostKeyChecking=no {host} '{remote_command}'"
    try:
        # 명령 실행 및 출력 캡처
        output = subprocess.check_output(ssh_command, shell=True, encoding="utf-8")
        return output.strip()
    except subprocess.CalledProcessError as e:
        return {"host": host, "success": False, "error": e.output.strip(), "return_code": e.returncode}

def run_parallel_commands(remote_command):
    """
    여러 호스트에 대해 병렬로 명령어 실행
    """
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(ssh_command_async, host, remote_command) for host in get_hosts()]
        for future in futures:
            future.result()  # 각 스레드의 결과를 기다림

def start_bg():
    """
    Background 작업 시작
    """
    try:
        print("start bg")
        remote_command = "cd ~/distributed && ./perftest_run.sh"
        run_parallel_commands(remote_command)
    except Exception as e:
        traceback.print_exc()
        return "fail"
    return "success"

def stop_bg():
    """
    Background 작업 중지
    """
    try:
        print("stop bg")
        remote_command = "pkill ib_; pkill python3; pkill perftest; pkill perf_main;"
        run_parallel_commands(remote_command)
    except Exception as e:
        traceback.print_exc()
        return "fail"
    return "success"

async def start_jonathan_accel():
    """
    Jonathan Acceleration 시작
    """
    try:
        print("start jonathan accel")
        # 확실히 정지 후 시작 (PERF_ENABLE=1)
        if stop_bg() == "success":
            await asyncio.sleep(1)
            perf_main_command = "cd ~/distributed/perf && ./run_perf_main.sh"
            run_parallel_commands(perf_main_command)
            
            perftest_command = "cd ~/distributed && PERF_ENABLE=1 ./perftest_run.sh"
            run_parallel_commands(perftest_command)
            return "success"
        return "fail"
        
    except Exception as e:
        traceback.print_exc()
        return "fail"

async def stop_jonathan_accel():
    """
    Jonathan Acceleration 중지
    """
    try:
        print("stop jonathan accel")
        # 확실히 정지 후 시작 (PERF_ENABLE=0)
        if stop_bg() == "success":
            await asyncio.sleep(1)
            remote_command = "cd ~/distributed && PERF_ENABLE=0 ./perftest_run.sh"
            run_parallel_commands(remote_command)
            return "success"
        
        return "fail"
    except Exception as e:
        traceback.print_exc()
        return "fail"

async def get_jonathan_accel():
    """
    Jonathan Acceleration 상태 가져오기
    """
    try:
        count = 0
        for host in get_hosts():
            output = ssh_command_sync(host, "ps -ef | grep run_perf_main | wc -l")
            if isinstance(output, dict):
                raise TypeError(f"ssh command 실패. Background Pod들의 연결상태 확인 필요!")
            count += int(output)
        
        # 베이스 상태에서 2줄은 검색됨
        status = "running" if count >= 6 else "stopped"
        
        perftest_cnt = 0
        for host in get_hosts():
            output = ssh_command_sync(host, "ps -ef | grep ib_write_bw | wc -l")
            if isinstance(output, dict):
                raise TypeError(f"ssh command 실패. Background Pod들의 연결상태 확인 필요!")
            perftest_cnt += int(output)
        
        if perftest_cnt < 6:
            if stop_bg() == "success":
                await asyncio.sleep(1)
                start_bg()

        return status
    except Exception as e:
        traceback.print_exc()
        return "error"


# ────────────────────────────────────────────────────────────────────────────
# OpenAI 호환 shim (프롬프트 최적화 컨테이너용)
# ────────────────────────────────────────────────────────────────────────────
# fewshot-prompt-optimizer 컨테이너는 llm_url 뒤에 /models·/chat/completions 를
# 붙여 호출하는 OpenAI 호환 클라이언트다(dspy.LM + openai SDK). 서빙 pod 은 vLLM 을
# 라이브러리로 임베드해서(EngineCore 는 내부 IPC 포트만 LISTEN) 앞단에 nginx→플랫폼
# 래퍼만 노출하므로 OpenAI HTTP API 가 존재하지 않는다. 그래서 이중모델 추론으로 이미
# 검증된 경로(_playground_test_url + _infer_question)를 OpenAI 규격으로 감싸 노출한다
# — 서빙 이미지의 내부 포트·path 에 비의존이므로 이미지가 바뀌어도 영향받지 않는다.
#
# authZ 는 플랫폼 posture 그대로(workspace_access_check 비활성) — 대상은 playground_id
# 로만 특정한다. 외부 노출은 Kong 리콘사일러의 /api/* 잠금이 담당하고, 이 경로는 클러스터
# 내부 s2s 호출(최적화 job)만 사용한다.
_SHIM_TIMEOUT = 300   # 최적화는 짧은 생성을 수백 회 → hang 시 job 전체가 멈추는 것 방지


def _deployment_external_job_id(pg):
    """playground 행의 deployment JSON 에서 external_job_id 를 꺼낸다(없으면 None).

    external(협력기관 컨테이너) 배포인지 판별하는 기존 신호 — get_playground_status·
    stop_playground·_clear_stale_external_job_id 가 모두 이 키로 분기한다.
    """
    try:
        return (json.loads(pg.get("deployment") or "{}") or {}).get("external_job_id")
    except Exception:
        traceback.print_exc()
        return None


async def _playground_internal_test_url(playground_id, pg=None):
    """서빙 pod 의 워크스페이스-내부 svc URL — 클러스터 내부(s2s) 추론 경로.

    `_playground_test_url` 은 인그레스(EXTERNAL_HOST:32080 = Kong NodePort)를 경유하는
    브라우저용 URL 이라 내부 호출에 부적합하다 — 실측 결과 Kong 경유 POST 는 405 를
    돌려주고, 같은 요청을 서빙 svc:18555 로 직접 보내면 200 이다. 여기서는 `playground_test`
    (service.py 의 `# TODO test url -> 내부 kubernetes dns로 변경`)에 주석으로 남아 있던
    내부 규칙을 상수 기반으로 실현한다. 브라우저 경로는 인그레스가 맞으므로 그대로 둔다.
    """
    pg = pg or await db.get_playground(playground_id=playground_id)
    if not pg:
        raise Exception(f"playground {playground_id} not found")
    if not pg.get("deployment"):
        raise Exception(f"playground {playground_id} has no deployment (not running)")
    # external(협력기관 컨테이너) 배포에는 이 URL 규칙이 성립하지 않는다 — 실제 pod 은
    # ext-<manifest>-<hash> 이고 deployment-llm-playground-* svc 자체가 없다. 여기서
    # 막지 않으면 shim 호출이 전량 연결 실패로 끝난다.
    if _deployment_external_job_id(pg):
        raise Exception(
            f"playground {playground_id} is an external deployment — "
            "the OpenAI shim only serves internal (vLLM/TGI 등) deployments")
    ws = pg.get("workspace_id")
    if not ws:
        raise Exception(f"playground {playground_id} has no workspace")
    ns = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=ws)
    return (f"http://deployment-llm-playground-{playground_id}--service.{ns}"
            f":{TYPE.DEPLOYMENT_NGINX_DEFAULT_PORT}/")


async def _playground_model_name(playground_id, pg=None):
    """playground 가 서빙하는 모델명 — OpenAI model id 로 노출한다."""
    pg = pg or await db.get_playground(playground_id=playground_id)
    if not pg:
        raise Exception(f"playground {playground_id} not found")
    try:
        _mid = (json.loads(pg.get("model") or "{}") or {}).get("model_allm_id")
        _row = await db.get_model(model_id=int(_mid)) if _mid else None
        name = (_row or {}).get("name")
    except Exception:
        # 모델명은 식별용일 뿐(컨테이너는 data[0].id 를 model 로 되돌려주기만 한다) →
        # 조회 실패가 추론 자체를 막지 않게 폴백.
        traceback.print_exc()
        name = None
    return name or f"playground-{playground_id}"


def _messages_to_prompt(messages):
    """OpenAI messages → 단일 프롬프트 문자열.

    서빙 래퍼는 role 분리를 받지 않고 test_question 문자열만 받는다(dual 의
    _build_dual_meta 와 동일 관행) → 이어 붙인다. 컨테이너가 보내는 것은 실질적으로
    system+user 2턴이라 라벨 없이 연결한다 — 라벨을 덧붙이면 최적화 대상 프롬프트가
    오염된다. assistant 턴이 섞인 경우에만 role 을 보존해 대화 구조를 남긴다.
    """
    if not isinstance(messages, list) or not messages:
        raise Exception("messages must be a non-empty list")
    keep_role = any(isinstance(m, dict) and m.get("role") == "assistant" for m in messages)
    parts = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        content = m.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        parts.append(f"{m.get('role')}: {content.strip()}" if keep_role else content.strip())
    if not parts:
        raise Exception("no textual content in messages")
    return "\n\n".join(parts)


async def openai_models(playground_id):
    """OpenAI GET /v1/models 호환 — 이 playground 가 서빙하는 모델 1건.
    컨테이너의 모델 자동감지는 응답의 data[0].id 만 사용한다."""
    name = await _playground_model_name(playground_id)
    return {"object": "list",
            "data": [{"id": name, "object": "model",
                      "created": int(time.time()), "owned_by": "tango"}]}


async def openai_chat_completions(playground_id, body):
    """OpenAI POST /v1/chat/completions 호환(비스트리밍).

    body 의 model·temperature 등은 무시한다 — 대상 모델은 playground_id 로 확정되고
    생성 파라미터는 배포 시점 설정을 따른다. stream=true 도 지원하지 않는다(컨테이너의
    dspy.LM·openai 호출은 전부 비스트리밍).
    session_id 는 넘기지 않는다 — 최적화는 수백 회 독립 호출이라 대화 히스토리가 누적되면
    holdout 채점이 오염된다.
    """
    prompt = _messages_to_prompt((body or {}).get("messages"))
    # 최적화는 수백 회 호출된다 → playground 행을 1회만 읽어 두 헬퍼에 넘긴다.
    pg = await db.get_playground(playground_id=playground_id)
    _ext_job_id = _deployment_external_job_id(pg)
    if _ext_job_id:
        # 외부 SDS(VLM) 분기 — custom_prompt 가 곧 질문이고 image_base64 + ais_rows 가
        #   필수다. 컨테이너는 텍스트만 보내오므로 예시 등록 때 받아 둔 미디어를
        #   query 로 되찾아 붙인다(컨테이너·계약 무수정).
        media = await _sds_media_for(playground_id, prompt)
        if not media or not media.get("image_base64"):
            raise Exception("SDS 최적화에 쓸 예시 이미지를 찾지 못했습니다 "
                            "— 예시마다 이미지를 등록해 다시 실행하세요")
        answer, _ = await _infer_sds_sample(_ext_job_id, prompt, {},
                                            image_b64=media.get("image_base64"),
                                            ais_rows=media.get("ais_rows"))
    else:
        test_url = await _playground_internal_test_url(playground_id, pg)  # 미배포/미실행이면 예외
        answer = await _infer_question(test_url, prompt, None, timeout=_SHIM_TIMEOUT)
    name = await _playground_model_name(playground_id, pg)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": name,
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": answer or ""},
                     "finish_reason": "stop"}],
        # 서빙 래퍼가 토큰 회계를 보고하지 않으므로 0 고정(컨테이너는 usage 를 쓰지 않는다).
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


# ────────────────────────────────────────────────────────────────────────────
# 프롬프트 최적화 (fewshot-prompt-optimizer, external container)
# ────────────────────────────────────────────────────────────────────────────
# 배포된 모델에 대해 few-shot 예시로 시스템 프롬프트를 최적화한다. 컨테이너는 학습을
# 하지 않고 llm_url(=위 shim)로 추론을 수백 회 던져 프롬프트만 탐색한다(2~10분).
# 산출물(system_prompt)은 활성 지정 후 단일 배포 추론에 주입된다.
#
# ⚠️ 결과 영속이 필수 — 컨테이너는 완료 job 을 TTL 1h 후 폐기하고, 플랫폼
#    external_container 도 terminal 시 helm release 를 teardown 하며 job tracker 가
#    휘발한다. completed 를 본 순간 prompt_optimization 에 저장한다.
_PROMPT_OPT_EXAMPLES_MAX = 10     # dual _DUAL_EXAMPLES_MAX 와 같은 관용구
_PROMPT_OPT_FIELD_MAX = 2000      # 필드당 길이 cap(프롬프트 폭주 방지)
_PROMPT_OPT_TERMINAL = ("completed", "failed", "cancelled")
_PROMPT_OPT_POLL_INTERVAL = 15    # 최적화는 분 단위 — 초 단위 폴링은 BFF 만 두드린다
# manifest capabilities.timeout_seconds(1800)의 2배. 컨테이너가 먼저 죽어 terminal 을
# 돌려주는 것이 정상 경로이고, 이 값은 그마저 안 될 때 태스크가 영원히 남지 않게 하는 상한.
_PROMPT_OPT_POLL_MAX_SECONDS = 3600


# few-shot 형식(`Query:/Response:`)으로 주입하면 모델이 그 패턴을 이어받아 다음 예시를
#   스스로 계속 생성한다. 실측된 두 형태:
#     "A grape is purple.\n\nQuery: What color is an apple? ..."
#     "Paris  \nUser Query: What is the capital city of Australia? ..."
#   모델이 라벨을 변형하므로("User Query:") 고정 문자열로는 놓친다 → 정규식으로 잡는다.
#   정석 해법은 stop sequence 지만 서빙 래퍼 계약은 test_question 문자열만 받아 stop 을
#   실을 수 없다 → 주입한 경우에만 플랫폼이 후처리로 잘라낸다(주입 여부를 플래그로 구분).
#   줄머리 라벨만 잡는다(MULTILINE). 마크다운/인용 접두(`### Query:`, `> Query:`)와
#   출력 첫 줄의 라벨도 포함해야 놓치지 않는다 — `\n` 시작만 보면 둘 다 새어 나간다.
_FEWSHOT_CONTINUATION_RE = re.compile(
    r"^[ \t>#*\-]*(?:user[ \t]+)?(?:query|question)[ \t]*:",
    re.IGNORECASE | re.MULTILINE)
#   우리가 주입한 짝 라벨. 연속 생성이면 Query: 뒤에 반드시 이게 따라온다.
_FEWSHOT_RESPONSE_RE = re.compile(
    r"^[ \t>#*\-]*(?:response|answer)[ \t]*:",
    re.IGNORECASE | re.MULTILINE)


def _fewshot_cut_index(text):
    """few-shot 연속 생성이 시작되는 위치. 자를 필요가 없으면 None.

    **짝 라벨 확인이 핵심이다.** Query:/Question: 만 보고 자르면 정상 답변 안의 Q&A 본문
    ("다음은 FAQ 입니다.\\nQuestion: 환불은 어떻게 하나요?")까지 잘라 사용자 답변을
    파괴한다. 주입 형식이 `Query: …\\nResponse:` 쌍이므로, 라벨 뒤에 Response:/Answer:
    가 이어질 때만 연속 생성으로 판정한다. 잘못 자르는 쪽(파괴적)보다 못 자르는
    쪽(찌꺼기가 남음)이 낫다는 판단.

    매치가 맨 앞(=답변 전체가 연속 생성)이면 자르지 않는다 — 빈 문자열을 돌려주는 것이
    찌꺼기를 보여주는 것보다 나쁘다.
    """
    for m in _FEWSHOT_CONTINUATION_RE.finditer(text):
        if m.start() == 0:
            continue
        if _FEWSHOT_RESPONSE_RE.search(text, m.end()):
            return m.start()
    return None


def _trim_fewshot_continuation(rows):
    """주입 응답에서 모델이 이어 만든 다음 예시를 제거하고 첫 답변만 남긴다."""
    if not isinstance(rows, list):
        return rows
    trimmed = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("output"), str):
            trimmed.append(row)
            continue
        text = row["output"]
        cut = _fewshot_cut_index(text)
        trimmed.append({**row, "output": (text[:cut] if cut is not None else text).strip()})
    return trimmed


async def _apply_active_prompt_optimization(playground_id, question):
    """활성 최적화가 있으면 system_prompt + 질문을 조립한다. 없으면 원문 그대로.

    반환: ``(프롬프트, 주입여부)``. 주입여부는 응답 후처리
    (:func:`_trim_fewshot_continuation`) 적용 판단에 쓴다.

    조립 형식이 결과를 좌우한다 — 컨테이너의 render_system_prompt 산출물이
    instruction + "Here are some examples:" + `Query: …\\nResponse: …` 쌍으로 끝나므로,
    사용자 질문도 같은 형식으로 이어야 모델이 패턴을 따른다. 형식 없이 이어 붙이면
    few-shot 패턴이 깨져 최적화 효과만 사라진다(코드는 정상 동작하므로 조용한 퇴행).

    조회 실패는 추론을 막지 않는다 — 최적화는 부가 기능이므로 원문으로 폴백한다.
    """
    system_prompt = await _active_prompt_text(playground_id)
    if not system_prompt:
        return question, False
    return f"{system_prompt}\n\nQuery: {question}\nResponse:", True


async def _prompt_matches_current_model(playground_id, row, pg=None):
    """활성 프롬프트가 **지금 배포된 모델**을 상대로 탐색된 것인지.

    프롬프트는 특정 모델/commit 의 응답 습관에 맞춰진 산출물이라, 같은 playground 라도
    모델이나 commit 을 바꿔 재배포하면 더 이상 유효하지 않다(오히려 형식을 망가뜨린다).
    실행 시 스냅샷해 둔 model_id/commit_id 와 현재 값을 대조해 어긋나면 주입을 건너뛴다.
    행을 자동 비활성화하지는 않는다 — 모델을 되돌리면 다시 유효해지므로 사용자의
    선택을 지운다.

    판단이 불가능하면(조회 실패, 스냅샷 없는 옛 행) True 로 통과시킨다 — 부가 기능이
    조회 실패 때문에 조용히 꺼지는 편이 더 나쁘다.
    """
    try:
        pg = pg or await db.get_playground(playground_id=playground_id)
        current = json.loads((pg or {}).get("model") or "{}") or {}
    except Exception:
        traceback.print_exc()
        return True
    for row_key, cur_key in (("model_id", "model_allm_id"),
                             ("commit_id", "model_allm_commit_id")):
        saved, now = row.get(row_key), current.get(cur_key)
        if saved is None or now is None:
            continue
        try:
            if int(saved) != int(now):
                print(f"[prompt-opt] playground {playground_id}: 활성 프롬프트는 "
                      f"{row_key}={saved} 로 탐색된 것이고 현재는 {now} → 주입 생략")
                return False
        except (TypeError, ValueError):
            continue
    return True


async def _active_prompt_text(playground_id, pg=None):
    """활성 최적화의 system_prompt 원문(없으면 None).

    internal 은 이 텍스트를 질문과 조립하지만(_apply_active_prompt_optimization),
    외부 SDS(VLM)는 custom_prompt 자체가 질문이므로 원문을 그대로 쓴다.
    조회 실패는 추론을 막지 않는다 — 최적화는 부가 기능.
    """
    try:
        row = await db.get_active_prompt_optimization(playground_id=playground_id)
    except Exception:
        traceback.print_exc()
        return None
    system_prompt = (row or {}).get("system_prompt")
    if not system_prompt or not str(system_prompt).strip():
        return None
    if not await _prompt_matches_current_model(playground_id, row, pg):
        return None
    return str(system_prompt).strip()


def _shim_llm_url(playground_id):
    """최적화 컨테이너가 쓸 OpenAI 호환 base — 플랫폼 shim.

    컨테이너가 이 뒤에 /models·/chat/completions 를 붙여 호출한다. 서빙 pod 은
    OpenAI HTTP API 를 노출하지 않으므로 반드시 shim 을 경유해야 한다.
    """
    return (f"http://{settings.LLM_PLAYGROUND_DNS}:80"
            f"/api/playgrounds/{int(playground_id)}/openai/v1")


def _normalize_examples(examples):
    """예시를 컨테이너 계약 {query, response} 로 정규화.

    플랫폼 dual 은 {query, answer} 를 쓰고 컨테이너는 {query, response} 를 쓴다 →
    여기서 흡수한다(컨테이너 무수정). 개수·길이 cap 도 여기서 적용 — 예시가 늘면
    holdout 이 커지고 대상 모델 추론량이 선형 증가한다.
    """
    out = []
    for ex in (examples or [])[:_PROMPT_OPT_EXAMPLES_MAX]:
        if not isinstance(ex, dict):
            continue
        q = str(ex.get("query") or ex.get("input") or "").strip()[:_PROMPT_OPT_FIELD_MAX]
        r = str(ex.get("response") or ex.get("answer") or ex.get("reference")
                or "").strip()[:_PROMPT_OPT_FIELD_MAX]
        if q and r:
            out.append({"query": q, "response": r})
    return out


# ── SDS(external) 최적화용 예시 미디어 ──────────────────────────────────────
# 컨테이너(fewshot-prompt-optimizer)는 텍스트 {query,response} 만 다루지만 SDS(VLM)는
# image_base64 + ais_rows(my_ship=1) 없이는 추론 자체가 불가하다. 그래서 예시의 미디어는
# **컨테이너로 보내지 않고** 플랫폼이 들고 있다가, 컨테이너가 shim 으로 되돌아올 때
# query 로 되찾아 붙인다. 컨테이너 무수정 + 계약 무변경으로 SDS 를 지원하는 유일한 지점.
_SDS_MEDIA_CACHE = {}   # playground_id -> {"by_query": {query: media}, "default": media}
# 이미지 1건 base64 상한(약 4MB 원본). examples JSON 컬럼과 위 캐시 양쪽에 실리므로
#   여기서 막지 않으면 DB 행 비대화와 워커 메모리 증가가 함께 온다.
_PROMPT_OPT_IMAGE_MAX = 6_000_000
_PROMPT_OPT_AIS_ROWS_MAX = 200


def _forget_sds_media(playground_id):
    """최적화가 terminal 이 되면 캐시를 비운다.

    캐시는 진행 중인 job 의 shim 호출을 위한 것이라 종료 후에는 쓸모가 없다.
    비우지 않으면 SDS 최적화를 돌린 모든 playground 의 base64 가 프로세스 수명 내내
    남는다(건당 최대 _PROMPT_OPT_IMAGE_MAX × 예시 수).
    """
    _SDS_MEDIA_CACHE.pop(playground_id, None)


def _split_example_media(examples):
    """예시에서 SDS 미디어를 분리한다.

    반환: ``(컨테이너로 보낼 [{query,response}], {query: {image_base64, ais_rows}})``.
    미디어가 하나도 없으면 두 번째는 빈 dict — 내부(vLLM) 경로와 동일하게 동작한다.
    """
    media = {}
    for ex in (examples or [])[:_PROMPT_OPT_EXAMPLES_MAX]:
        if not isinstance(ex, dict):
            continue
        q = str(ex.get("query") or ex.get("input") or "").strip()[:_PROMPT_OPT_FIELD_MAX]
        img = ex.get("image_base64")
        if not (q and img):
            continue
        # 크기 상한 — query/response 에는 _PROMPT_OPT_FIELD_MAX 가 걸려 있는데 정작
        #   가장 큰 페이로드인 이미지에는 없었다. 이 값은 그대로 DB(examples JSON)에
        #   영속되고 프로세스 캐시에도 올라가므로, 상한이 없으면 예시 10건만으로
        #   공유 MariaDB 와 워커 메모리를 동시에 압박한다.
        img = str(img)
        if len(img) > _PROMPT_OPT_IMAGE_MAX:
            raise Exception(
                f"예시 이미지가 너무 큽니다(base64 {len(img)//1024}KB) — "
                f"{_PROMPT_OPT_IMAGE_MAX//1024}KB 이하로 줄여 주세요")
        ais = ex.get("ais_rows") or []
        if not isinstance(ais, list) or len(ais) > _PROMPT_OPT_AIS_ROWS_MAX:
            raise Exception(f"AIS 행은 최대 {_PROMPT_OPT_AIS_ROWS_MAX}건까지 허용됩니다")
        # ⚠️ query 를 키로 쓴다 — 같은 질의를 가진 예시가 둘이면 뒤엣것이 앞엣것의
        #    이미지를 덮어써 조용히 잘못된 이미지로 채점된다. 중복은 거부한다.
        if q in media:
            raise Exception("질의가 동일한 예시가 둘 이상입니다 — "
                            "이미지를 질의로 되찾는 구조라 질의는 서로 달라야 합니다")
        media[q] = {"image_base64": img, "ais_rows": ais}
    return _normalize_examples(examples), media


async def _sds_media_for(playground_id, prompt):
    """shim 으로 들어온 프롬프트에 해당하는 예시 미디어를 찾는다.

    컨테이너는 후보 시스템 프롬프트 + 예시 query 를 한 문자열로 보내오므로, 등록된
    query 중 프롬프트에 포함된 것 가운데 **가장 긴 것**을 고른다(짧은 query 가 다른
    query 의 부분문자열일 때 오매칭 방지). 못 찾으면 첫 예시의 미디어로 폴백한다 —
    컨테이너가 합성한 질의(rounds>0)에는 대응하는 이미지가 없기 때문이고, 여기서
    실패시키면 최적화 전체가 죽는다.
    """
    entry = _SDS_MEDIA_CACHE.get(playground_id)
    if entry is None:
        # 프로세스가 재시작했으면 캐시가 비어 있다 → 진행 중인 행의 examples 에서 복원.
        entry = {"by_query": {}, "default": None}
        try:
            rows = await db.get_prompt_optimization_list(playground_id=playground_id) or []
            pending = next((r for r in rows
                            if r.get("status") not in _PROMPT_OPT_TERMINAL), None)
            if pending:
                full = await db.get_prompt_optimization(optimization_id=pending.get("id"))
                saved = json.loads((full or {}).get("examples") or "[]") or []
                _, media = _split_example_media(saved)
                entry = {"by_query": media,
                         "default": next(iter(media.values()), None)}
        except Exception:
            traceback.print_exc()
        _SDS_MEDIA_CACHE[playground_id] = entry

    by_query = entry.get("by_query") or {}
    best = None
    for q, media in by_query.items():
        if q and q in prompt and (best is None or len(q) > len(best[0])):
            best = (q, media)
    return best[1] if best else entry.get("default")


async def _resolve_proposer_llm_url(proposer_playground_id, pg):
    """제안자(메타) LM 의 shim URL 을 만든다. 실패는 전부 같은 메시지로 접는다.

    instruction 제안·reflection·합성예시 생성은 구조화 출력(JSON `proposed_instruction`)을
    요구하는데 VLM(외부 SDS)은 그 계약을 못 지켜 dspy 가 AdapterParseError 로 죽는다
    → 텍스트 배포를 따로 물린다.

    **URL 이 아니라 id 를 받는 이유**: 클라이언트가 준 URL 을 그대로 컨테이너에 넘기면
    SSRF 가 된다. 여기서 워크스페이스·유형·실행상태를 검증하고 서버가 직접 조립한다
    (dual 의 prompt_gen_playground_id 와 동일 규약, 열거 오라클 회피로 메시지 통합).
    """
    pg1 = await db.get_playground(playground_id=proposer_playground_id)
    if not pg1 or pg1.get("workspace_id") != pg.get("workspace_id"):
        raise Exception("제안자(LLM) 배포를 찾을 수 없습니다")
    if _deployment_external_job_id(pg1):
        raise Exception("제안자는 내부 텍스트 배포여야 합니다 — 외부 컨테이너 배포는 지정할 수 없습니다")
    try:
        _st = (await get_playground_status(proposer_playground_id) or {}).get("status")
    except Exception:
        traceback.print_exc()
        _st = None
    if _st != TYPE.KUBE_POD_STATUS_RUNNING:
        raise Exception("제안자 배포가 실행 중이 아닙니다 — 먼저 시작한 뒤 실행하세요")
    return _shim_llm_url(proposer_playground_id)


async def start_prompt_optimization(playground_id, examples=None, dataset_id=None,
                                    dataset_filename=None, sample_count=None,
                                    metric="token_f1", rounds=0,
                                    proposer_playground_id=None):
    """최적화 실행 — external job 을 띄우고 prompt_optimization 행을 만든다.

    예시는 직접 입력(examples) 또는 데이터셋 추출(dataset_id) 중 하나.
    데이터셋 경로는 dual 배치가 쓰는 _read_dataset_samples 를 재사용한다
    (NFS 스트리밍 + 경로탈출/워크스페이스 가드 포함).
    """
    pg = await db.get_playground(playground_id=playground_id)
    if not pg:
        raise Exception(f"playground {playground_id} not found")
    if not pg.get("deployment"):
        raise Exception("배포가 실행 중이 아닙니다 — 최적화는 배포된 모델을 호출합니다")
    # ① external(협력기관 컨테이너) 배포. 종전엔 전면 차단했는데, shim 이 external 분기를
    #    갖게 되어(openai_chat_completions) SDS 도 최적화할 수 있다. 다만 SDS 는
    #    image_base64 + ais_rows 없이는 추론이 불가하므로 예시마다 미디어를 요구한다.
    external_job_id = _deployment_external_job_id(pg)
    # ② 실제 실행 여부 확인. deployment JSON 은 중지 후에도 보존되므로(stop_playground
    #    가 재배포용 설정을 남긴다) 존재만으로는 "실행 중"이 아니다. 확인하지 않으면
    #    job 만 뜨고 호출이 전부 실패해 GPU 와 시간만 소모한다.
    try:
        _status = (await get_playground_status(playground_id) or {}).get("status")
    except Exception:
        traceback.print_exc()
        _status = None
    if _status != TYPE.KUBE_POD_STATUS_RUNNING:
        raise Exception("배포가 실행 중이 아닙니다 — 배포를 시작한 뒤 최적화를 실행하세요")
    # ③ 동시 실행 차단. 최적화 1건이 대상 모델에 수백 회 추론을 던지므로 중복 실행은
    #    서빙 GPU 를 고갈시킨다. FE 버튼 비활성화만으로는 탭 2개·직접 호출을 못 막는다.
    _existing = await db.get_prompt_optimization_list(playground_id=playground_id) or []
    if any(r.get("status") not in _PROMPT_OPT_TERMINAL for r in _existing):
        raise Exception("이미 진행 중인 최적화가 있습니다 — 완료된 뒤에 다시 실행하세요")
    workspace_id = pg.get("workspace_id")

    # 미디어(SDS 이미지·AIS)는 컨테이너로 보내지 않고 여기서 분리해 둔다.
    prepared, example_media = _split_example_media(examples)
    if not prepared and dataset_id:
        n = max(2, min(int(sample_count or _PROMPT_OPT_EXAMPLES_MAX), _PROMPT_OPT_EXAMPLES_MAX))
        samples, _ = await _read_dataset_samples(dataset_id, dataset_filename, n,
                                                workspace_id=workspace_id)
        prepared, example_media = _split_example_media(samples)
    # 컨테이너 계약: 최소 2건(seed 1 + holdout 1). 미달이면 job 을 띄우지 않는다.
    if len(prepared) < 2:
        raise Exception("최적화에는 (질의, 응답) 예시가 최소 2건 필요합니다")
    if external_job_id:
        # SDS 는 이미지 없이는 호출 자체가 실패한다 → job 을 띄우기 전에 막는다.
        #   (띄우고 나서 실패하면 원인이 컨테이너 로그 안쪽에 묻힌다)
        missing = [ex["query"] for ex in prepared if ex["query"] not in example_media]
        if missing:
            raise Exception("외부 SDS 배포의 최적화는 예시마다 이미지가 필요합니다 "
                            f"— {len(missing)}건에 이미지가 없습니다")

    _model_json = {}
    try:
        _model_json = json.loads(pg.get("model") or "{}") or {}
    except Exception:
        traceback.print_exc()

    # 제안자(메타) LM. external(VLM) 대상은 필수 — 대상 모델이 instruction 을 제안할 수
    #   없어 지정하지 않으면 컨테이너가 AdapterParseError 로 죽는다(실측: optimization 14).
    proposer_url = None
    if proposer_playground_id:
        proposer_url = await _resolve_proposer_llm_url(proposer_playground_id, pg)
    elif external_job_id:
        raise Exception("외부 SDS 배포의 최적화에는 제안자(텍스트 LLM) 배포 지정이 필요합니다 "
                        "— 대상 VLM 은 instruction 제안을 수행할 수 없습니다")

    params = {"llm_url": _shim_llm_url(playground_id), "examples": prepared,
              "metric": metric or "token_f1", "rounds": int(rounds or 0)}
    if proposer_url:
        params["proposer_llm_url"] = proposer_url
    if external_job_id:
        # 외부(SDS VLM)는 dspy 의 구조화 출력 계약(`[[ ## response ## ]]`)을 지키지 않고
        #   산문만 낸다 → 단일 출력 Predict + 관대한 파서로 원문을 그대로 채점하게 한다.
        params["raw_task_output"] = True
    body = {"manifest_name": settings.PROMPT_OPT_MANIFEST_NAME,
            "manifest_version": settings.PROMPT_OPT_MANIFEST_VERSION,
            "workspace_id": int(workspace_id), "params": params}
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{settings.FB_EXTERNAL_CONTAINER_URL}/api/v1/jobs",
                              json=body, timeout=120)
    if r.status_code not in (200, 202):
        raise Exception(f"최적화 job 등록 실패({r.status_code}): {r.text[:300]}")
    job_id = (r.json() or {}).get("job_id")
    if not job_id:
        raise Exception("최적화 job 등록 응답에 job_id 가 없습니다")

    # 미디어를 예시와 함께 영속한다 — 파드가 재시작해도 shim 이 이미지를 되찾아야
    #   진행 중인 최적화가 이어진다(_sds_media_for 의 DB 폴백 경로).
    persisted = [{**ex, **(example_media.get(ex["query"]) or {})} for ex in prepared]
    if external_job_id:
        _SDS_MEDIA_CACHE[playground_id] = {
            "by_query": example_media,
            "default": next(iter(example_media.values()), None)}
    ok, opt_id = await db.insert_prompt_optimization(
        workspace_id=workspace_id, playground_id=playground_id, job_id=job_id,
        model_id=_model_json.get("model_allm_id"),
        commit_id=_model_json.get("model_allm_commit_id"),
        metric=params["metric"], examples=persisted, status="running")
    if not ok:
        # job 은 이미 떴는데 이력 행이 없다 = 결과를 회수할 수도, 사용자가 취소할 수도
        # 없는 orphan 이다. 그대로 두면 대상 GPU 에 수백 회 추론을 던지며 끝까지 돈다
        # → 만들어 둔 job 을 되돌린 뒤에 실패를 알린다.
        try:
            await cancel_infer_job(job_id)
        except Exception:
            traceback.print_exc()
        raise Exception(f"최적화 job({job_id}) 은 시작됐으나 이력 저장에 실패해 취소했습니다")
    # 결과 영속을 사용자 폴링에 의존하지 않는다 — 화면을 닫거나 FE 가 폴링하지 않으면
    # 컨테이너 TTL(1h) 과 함께 산출물이 영구 유실된다. terminal 까지 백그라운드로 따라간다.
    _spawn_prompt_optimization_poller(opt_id, playground_id)
    return {"optimization_id": opt_id, "job_id": job_id, "n_examples": len(prepared)}


async def get_prompt_optimization(optimization_id, playground_id=None):
    """상세 조회 — 비종료 상태면 external job 을 폴링해 갱신·영속한다(lazy).

    별도 워커를 두지 않는다: 조회 시점에 당겨오면 충분하고, completed 를 본 순간
    산출물을 DB 에 넣어 휘발을 막는다.

    playground_id 를 주면 소속을 검증한다 — system_prompt 는 사용자 데이터라
    id 만으로 타 배포 산출물을 읽지 못하게 한다. 존재하지 않는 id 와 타 배포의 id 를
    같은 메시지로 응답해 열거 오라클을 만들지 않는다(set_active 와 동일 규약).
    """
    row = await db.get_prompt_optimization(optimization_id=optimization_id)
    if not row or (playground_id is not None
                   and int(row.get("playground_id") or 0) != int(playground_id)):
        raise Exception("optimization not available")
    if row.get("status") in _PROMPT_OPT_TERMINAL or not row.get("job_id"):
        return row

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.FB_EXTERNAL_CONTAINER_URL}/api/v1/jobs/{row['job_id']}", timeout=30)
        if r.status_code == 404:
            # BFF 가 그 job 을 모른다 = 기록이 사라졌다(BFF 재시작으로 in-memory
            # 휘발 등). 더 폴링해도 영원히 404 이므로 failed 로 확정해 폴링을
            # 끝낸다 (_PROMPT_OPT_TERMINAL 진입 → 다음 조회는 BFF 를 안 부름).
            # 404 만 종료다 — 아래 5xx/네트워크는 상태 유지 후 재시도.
            await db.update_prompt_optimization_result(
                optimization_id=optimization_id, status="failed", result=None,
                finished=True,
                error_message="job record not found (BFF lost it) — 결과를 회수할 수 없습니다")
            return await db.get_prompt_optimization(optimization_id=optimization_id)
        if r.status_code != 200:
            return row      # 일시장애(5xx/네트워크)는 상태 유지(다음 폴링에서 재시도)
        job = r.json() or {}
    except Exception:
        traceback.print_exc()
        return row

    res = job.get("result") or {}
    status = res.get("status") or row.get("status")
    payload = res.get("result") if isinstance(res.get("result"), dict) else None
    # 실패 원인 — FewshotPromptAdapter._build_result 가 컨테이너의 top-level
    # code/message 를 여기까지 복원해 준다. 저장하지 않으면 어댑터를 만든 이유가
    # 사라지고 UI 에는 원인 없는 'failed' 만 남는다.
    _err = res.get("error") if isinstance(res.get("error"), dict) else None
    error_message = " ".join(
        str(v) for v in (_err.get("code"), _err.get("message")) if v) if _err else None
    # BFF 재시작 후 응답은 DB tombstone 기반이라 lifecycle status 만 있고 파트너
    # 산출물은 없다. 산출물 없는 completed 를 그대로 확정하면 "완료인데 프롬프트가
    # 빈" 행이 남아 활성 지정까지 가능해지므로, 유실된 사실대로 failed 로 닫는다.
    if status == "completed" and not payload and not row.get("system_prompt"):
        status = "failed"
        error_message = error_message or "완료 보고에 산출물이 없습니다 (결과 유실)"
    if status != row.get("status") or payload or error_message:
        await db.update_prompt_optimization_result(
            optimization_id=optimization_id, status=status, result=payload,
            finished=status in _PROMPT_OPT_TERMINAL, error_message=error_message)
        # terminal 이면 SDS 미디어 캐시를 비운다 — 이 캐시는 진행 중 shim 호출용이라
        #   종료 후엔 쓸모가 없고, 남겨두면 base64 가 워커 메모리에 무기한 누적된다.
        if status in _PROMPT_OPT_TERMINAL and playground_id:
            _forget_sds_media(playground_id)
        row = await db.get_prompt_optimization(optimization_id=optimization_id)
    return row


async def list_prompt_optimizations(playground_id):
    """한 배포의 최적화 이력. 비종료 행은 조회 시 갱신해 목록이 굳지 않게 한다."""
    rows = await db.get_prompt_optimization_list(playground_id=playground_id) or []
    if any(r.get("status") not in _PROMPT_OPT_TERMINAL for r in rows):
        for r in rows:
            if r.get("status") not in _PROMPT_OPT_TERMINAL:
                try:
                    await get_prompt_optimization(r.get("id"), playground_id=playground_id)
                except Exception:
                    traceback.print_exc()
        rows = await db.get_prompt_optimization_list(playground_id=playground_id) or []
    return rows


def _spawn_prompt_optimization_poller(optimization_id, playground_id):
    """terminal 까지 따라가는 백그라운드 폴러를 띄운다(fire-and-forget)."""
    if not optimization_id:
        return
    try:
        asyncio.create_task(_poll_prompt_optimization(optimization_id, playground_id))
    except RuntimeError:
        # 실행 중인 이벤트 루프가 없는 컨텍스트 — 조용히 포기한다. 조회 시 갱신
        # (get_prompt_optimization) 이 여전히 백업 경로로 남아 기능이 죽지는 않는다.
        traceback.print_exc()


async def _poll_prompt_optimization(optimization_id, playground_id):
    """상태가 terminal 이 될 때까지 주기적으로 당겨와 저장한다.

    **왜 필요한가**: 결과 영속은 "완료를 본 쪽이 저장한다" 구조인데, 그 주체가 사용자
    조회뿐이면 화면을 닫는 순간 아무도 저장하지 않는다. 컨테이너는 TTL(1h) 후 job 을
    폐기하고 플랫폼도 terminal 시 helm release 를 teardown 하므로, 그 사이 아무도
    보지 않으면 system_prompt 는 영구 유실된다.

    갱신·영속 로직은 get_prompt_optimization 이 이미 갖고 있으므로 그대로 재사용한다
    (이원화하면 두 경로가 갈린다). 워커 프로세스가 여러 개면 폴러도 여러 개지만
    같은 값을 쓰는 멱등 UPDATE 라 무해하다.
    """
    deadline = time.time() + _PROMPT_OPT_POLL_MAX_SECONDS
    while time.time() < deadline:
        await asyncio.sleep(_PROMPT_OPT_POLL_INTERVAL)
        try:
            row = await get_prompt_optimization(optimization_id,
                                                playground_id=playground_id)
        except Exception:
            traceback.print_exc()
            continue
        if (row or {}).get("status") in _PROMPT_OPT_TERMINAL:
            return
    print(f"[prompt-opt] optimization {optimization_id}: 폴링 상한({_PROMPT_OPT_POLL_MAX_SECONDS}s) "
          "도달 — 상태를 확정하지 못했습니다")


async def recover_prompt_optimizations():
    """기동 시 비종료 행의 폴링을 재개한다 (external_container startup_recovery 관행).

    파드가 재시작하면 진행 중이던 폴러가 사라지고, 그 job 의 산출물은 아무도 저장하지
    않는다. 기동 때 한 번 훑어 폴러를 다시 붙여 그 구멍을 막는다.
    실패해도 절대 기동을 막지 않는다 — 부가 기능이다.
    """
    try:
        rows = await db.get_pending_prompt_optimizations() or []
    except Exception:
        traceback.print_exc()
        return
    for r in rows:
        _spawn_prompt_optimization_poller(r.get("id"), r.get("playground_id"))
    if rows:
        print(f"[prompt-opt] 미완료 최적화 {len(rows)} 건 폴링 재개")


async def get_prompt_optimization_state(playground_id):
    """추론 화면 토글용 read-model — "지금 켜져 있나 / 실제로 먹고 있나"를 한 번에 답한다.

    **왜 별도 엔드포인트인가**: FE 가 목록+상세를 둘 다 불러도 알 수 없는 상태가 하나
    있다 — *활성인데 주입은 안 되는* 상태. 프롬프트는 특정 model/commit 을 상대로
    탐색된 산출물이라 배포 모델을 바꾸면 _active_prompt_text 가 조용히 주입을 건너뛴다
    (_prompt_matches_current_model). 목록에는 is_active=1 만 보이므로 토글은 ON 인데
    추론에는 안 먹는다. 설정 화면에서는 각주였지만 추론 화면에서는 **토글이 곧 기능**
    이라 그대로 두면 UI 가 거짓말을 한다 → effective/stale_reason 으로 드러낸다.
    supported(외부 컨테이너 배포 여부)도 BE 의 실행 차단 규칙과 같은 판정을 써야
    FE 가 규칙을 복제하지 않는다.

    비종료 행 갱신은 list_prompt_optimizations 가 이미 하므로 그대로 재사용한다 —
    패널 폴링이 이 호출 하나로 끝난다(목록·상세 분리 호출 불필요).

    조회 실패는 화면을 막지 않는다 — 최적화는 부가 기능이므로 보수적 기본값으로 답한다.
    """
    pg = None
    try:
        pg = await db.get_playground(playground_id=playground_id)
    except Exception:
        traceback.print_exc()
    # start_prompt_optimization 과 같은 판정 — 배포 JSON 이 있으면 내부·외부 모두 지원.
    #   external(SDS)은 shim 이 이미지·AIS 를 붙여 호출하므로 예시에 미디어가 필요하다.
    supported = bool(pg and pg.get("deployment"))
    requires_media = bool(pg and _deployment_external_job_id(pg))

    deployment_running = False
    if supported:
        try:
            _status = (await get_playground_status(playground_id) or {}).get("status")
            deployment_running = _status == TYPE.KUBE_POD_STATUS_RUNNING
        except Exception:
            traceback.print_exc()

    # 조회 실패를 조용히 빈 목록으로 접지 않는다 — 스키마 드리프트(예: 002 미적용으로
    #   error_message 컬럼 부재)면 "이력 없음"과 구분이 안 돼 원인이 화면에서 사라진다.
    #   추론을 막지는 않되(부가 기능) 사유는 history_error 로 올려보낸다.
    history_error = None
    try:
        rows = await list_prompt_optimizations(playground_id) or []
    except Exception as e:
        traceback.print_exc()
        rows = []
        history_error = str(e)[:300]
    # 목록은 id DESC — rows[0] 이 최신 실행이다(패널의 진행 카드가 이걸 쓴다).
    #   전체를 history 로 함께 내려 이력 표를 별도 호출 없이 그린다. _LIST_COLS 가
    #   큰 텍스트(system_prompt/demos/examples)를 이미 제외하므로 페이로드는 작다.
    running = any(r.get("status") not in _PROMPT_OPT_TERMINAL for r in rows)
    latest_completed = next((r for r in rows if r.get("status") == "completed"), None)

    active_row = None
    try:
        active_row = await db.get_active_prompt_optimization(playground_id=playground_id)
    except Exception:
        traceback.print_exc()

    effective, stale_reason = False, None
    if active_row:
        effective = await _prompt_matches_current_model(playground_id, active_row, pg)
        if not effective:
            stale_reason = "model_changed"

    return {
        "supported": supported,
        # true 면 예시마다 이미지(+AIS)를 받아야 한다 — SDS 는 텍스트만으로 추론 불가.
        "requires_media": requires_media,
        "deployment_running": deployment_running,
        # 토글의 표시 상태 = 활성 행 존재 여부(적용됨). effective 는 "실제 주입 여부".
        "enabled": bool(active_row),
        "active_optimization_id": (active_row or {}).get("id"),
        "active_system_prompt": (active_row or {}).get("system_prompt"),
        "effective": effective,
        "stale_reason": stale_reason,
        "running": running,
        # 이력 전체(최신순). 표에서 과거 산출물을 골라 적용할 수 있어야 한다 —
        # 토글은 "최신 완료본" 만 적용하므로 그것만으로는 되돌릴 방법이 없다.
        "history": rows,
        # 목록 조회가 실패한 사유(정상이면 None). "이력 없음"과 "조회 실패"를 구분한다.
        "history_error": history_error,
        # 토글 ON 이 적용할 대상 — 가장 최근 완료본.
        "latest_completed_id": (latest_completed or {}).get("id"),
    }


async def set_prompt_optimization_active(playground_id, optimization_id):
    """활성 지정/해제. optimization_id=None 이면 해제(최적화 미적용으로 복귀)."""
    if optimization_id is not None:
        row = await db.get_prompt_optimization(optimization_id=optimization_id)
        # 존재/타 playground 구분을 노출하지 않는다(id 열거 오라클) — dual 과 동일 규약.
        if not row or int(row.get("playground_id") or 0) != int(playground_id):
            raise Exception("optimization not available")
        if row.get("status") != "completed":
            raise Exception("완료된 최적화만 적용할 수 있습니다")
    ok = await db.set_active_prompt_optimization(playground_id=playground_id,
                                                 optimization_id=optimization_id)
    if not ok:
        raise Exception("활성 최적화 변경에 실패했습니다")
    return {"playground_id": playground_id, "active_optimization_id": optimization_id}
