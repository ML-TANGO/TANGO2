

import os
import re
import json
import asyncio
import aiofiles
import traceback
import shutil
import uuid
import math
import datetime
import subprocess
import time
import numpy as np

from fastapi import File, UploadFile, Request
from huggingface_hub import login, model_info, HfApi
from requests.exceptions import HTTPError, ConnectionError, Timeout
from typing import List, Union, Optional, Tuple
from pathlib import Path
from aiokafka import AIOKafkaProducer
from confluent_kafka.admin import AdminClient
from tensorboard.backend.event_processing import event_accumulator
from aiopath import AsyncPath

from utils import redis_key, TYPE, PATH, settings, common, topic_key, workspace_resource
from utils.redis import get_redis_client_async
from utils.llm_db import db_model
from utils.msa_db import db_workspace, db_user, db_instance
from model.dto import FineTuningConfig, FineTuningPodInfo
from utils.crypt import session_cipher, front_cipher
# from utils.mongodb_async import urls_collection
from utils.kube import PodName, create_or_replace_secret, delete_secret
from utils.access_check import is_workspace_user


def _redact_secrets(cmd: str) -> str:
    """helm 명령 로깅 시 토큰/시크릿 마스킹. HF 토큰은 저장은 암호화돼 있으나
    helm --set command.token=... 에는 복호화된 평문이 들어가므로 stdout/EFK 유출 방지."""
    return re.sub(r'(command\.token=)"[^"]*"', r'\1"***"', cmd)


async def is_folder_empty(folder_path):
    path = AsyncPath(folder_path)
    return await path.is_dir() and not any([child async for child in path.iterdir()])

async def check_healthz():
    redis_client = await get_redis_client_async()
    await redis_client.hgetall(redis_key.WORKSPACE_PODS_STATUS)
    return True

# async def shorten_url(original_url):
#     existing_url = await urls_collection.find_one({"original_url":  f"http://{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}/{original_url}"})
#     if existing_url:
#         return existing_url['short_id']
    
#     short_id = str(uuid.uuid4())[:8]
#     await urls_collection.insert_one({
#         "short_id": short_id,
#         "original_url": f"http://{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}/{original_url}",
#         "clicks": 0,
#         "last_accessed": None
#     })
#     return short_id

# async def get_origin_url(short_id):
#     url_data = await urls_collection.find_one({"short_id": short_id})
#     if url_data:
#         await urls_collection.update_one(
#             {"short_id": short_id},
#             {"$inc": {"clicks": 1}, "$set": {"last_accessed": datetime.datetime.now()}}
#         )
#         return url_data
#     return None
    

# ── SSE tfevents 읽기 캐시 (NFS 과부하 완화, SP-Ext) ──────────────────────
# sse-graph/sse-time 은 3s(외부)·1s(내부) 루프에서 매 틱 tfevents 파일 전체를
# EventAccumulator.Reload() 로 재파싱한다. 학습 중 events 파일은 계속 커지고,
# 뷰를 연 클라이언트마다 독립 파싱하므로 NFS 읽기가 (파일크기 × 빈도 × 클라이언트)
# 로 증폭된다. events 파일의 (경로, 크기, mtime) 서명이 바뀔 때만 재파싱하고 결과를
# 프로세스 전역으로 공유해(같은 job 을 보는 N 클라이언트가 1회 파싱을 공유) 완화한다.
_TFEVENTS_MEMO: dict = {}
_TFEVENTS_MEMO_MAX = 128


def tfevents_signature(log_dir):
    """log_dir 내 모든 events.out.tfevents.* 의 집계 지문 (파일수, 총 size, 최신 mtime).

    EventAccumulator.Reload() 는 디렉토리의 events 파일 전체를 병합해 읽으므로,
    '최신 파일 하나'가 아니라 파일 집합 전체를 지문으로 삼아야 한 run 에 events
    파일이 여러 개 공존해도(스테이지 전환/학습 재개) 갱신을 놓치지 않는다. events 는
    append-only 라 어떤 파일이 커지거나 새 파일이 생기면 총 size 또는 최신 mtime 이
    반드시 바뀐다. 파일이 없거나 log_dir 접근 불가면 None (호출부는 빈 결과로 처리).
    """
    try:
        count = 0
        total_size = 0
        latest_m = -1.0
        for name in os.listdir(log_dir):
            if "tfevents" not in name:
                continue
            p = os.path.join(log_dir, name)
            try:
                st = os.stat(p)
            except OSError:
                continue
            count += 1
            total_size += st.st_size
            if st.st_mtime > latest_m:
                latest_m = st.st_mtime
        if count == 0:
            return None
        return (count, total_size, latest_m)
    except OSError:
        return None


def tfevents_memo_get(key, sig):
    """서명이 일치하면 캐시값, 아니면 None."""
    hit = _TFEVENTS_MEMO.get(key)
    if hit is not None and hit[0] == sig:
        return hit[1]
    return None


def tfevents_memo_put(key, sig, value):
    """캐시 저장(간단 FIFO 상한 — 동시 학습 job 수 방어)."""
    if key not in _TFEVENTS_MEMO and len(_TFEVENTS_MEMO) >= _TFEVENTS_MEMO_MAX:
        _TFEVENTS_MEMO.pop(next(iter(_TFEVENTS_MEMO)), None)
    _TFEVENTS_MEMO[key] = (sig, value)


async def parse_tensorboard_scalars_async(log_dir, max_steps=20):
    """
    TensorBoard 로그 디렉토리에서 스칼라 태그들을 파싱하여 각 태그의 x, y 데이터를 딕셔너리 형태로 반환합니다 (async 버전).
    또한 각 에포크 당 스텝 수 (steps_per_epoch)를 계산하여 반환합니다.
    
    Args:
        log_dir (str): TensorBoard 로그 디렉토리 경로.
        max_steps (int, optional): 출력할 최대 스텝의 개수. 기본값은 100입니다.
    """
    # NFS 부하 완화: events 파일 서명이 직전 파싱과 같으면 재파싱 없이 공유 캐시 반환
    # (학습 중 커지는 tfevents 를 3s/1s 루프 × 클라이언트마다 재읽던 것을 제거).
    sig = await asyncio.to_thread(tfevents_signature, log_dir)
    if sig is None:
        return {}, 0
    memo_key = ("scalars", log_dir, max_steps)
    cached = tfevents_memo_get(memo_key, sig)
    if cached is not None:
        return cached

    # 이벤트 어큐뮬레이터 로드
    ea = event_accumulator.EventAccumulator(log_dir)
    await asyncio.to_thread(ea.Reload)

    # 스칼라 태그들을 추출
    scalar_tags = ea.Tags()['scalars']
    parsed_data = {}
    latest_steps = 0
    train_steps_per_second = None  # 초당 스텝 수
    # 필요한 스칼라 태그 데이터 추출
    for tag in scalar_tags:
        # 특정 태그 값을 저장
        if tag not in TYPE.FINE_TUNING_LOG_TAGS:
            continue
        events = ea.Scalars(tag)
        steps = [event.step for event in events]
        values = [
            0.0 if event.value is None or (isinstance(event.value, float) and math.isnan(event.value)) 
            else event.value 
            for event in events
        ]
       
        # 태그별 max step 의 최댓값(eval/loss 등 희소 태그가 마지막에 처리돼도 진행률이 역행하지 않게).
        latest_steps = max(latest_steps, steps[-1])

        # 스텝 수를 최대 max_steps로 제한하고 평균값 계산
        if len(steps) > max_steps:
            indices = np.linspace(0, len(steps) - 1, max_steps, dtype=int)
            steps = [steps[i] for i in indices]
            values = [
                np.mean(values[indices[j]:indices[j + 1]]) if j + 1 < len(indices) else np.mean(values[indices[j]:])
                for j in range(len(indices))
            ]

        parsed_data[tag] = {'steps': steps, 'values': values}

    result = (parsed_data, latest_steps)
    tfevents_memo_put(memo_key, sig, result)
    return result


# ── SP-5 ⑩ 체크포인트 점 마킹 ────────────────────────────────────────────────
# Trainer 는 체크포인트를 `checkpoint-<step>` 디렉토리로 저장(HF 관례). 학습 그래프
# 위에 그 step 을 점으로 표시(best 강조)하기 위해 step 목록을 해석한다.
_CHECKPOINT_DIR_RE = re.compile(r"^checkpoint-(\d+)$")


def _scan_checkpoint_steps_sync(checkpoint_root: str) -> list:
    steps = []
    try:
        for name in os.listdir(checkpoint_root):
            m = _CHECKPOINT_DIR_RE.match(name)
            if m and os.path.isdir(os.path.join(checkpoint_root, name)):
                steps.append(int(m.group(1)))
    except OSError:
        pass
    return sorted(set(steps))


async def _resolve_checkpoint_steps(checkpoint_root: str, save_steps=None, latest_step=None) -> list:
    """⑩ — 저장된 체크포인트 step 목록. `checkpoint-<step>` 디렉토리 스캔(실제 저장분).
    디렉토리가 없으면 save_steps 배수로 추정(학습 진행 중 아직 미저장)."""
    if checkpoint_root:
        steps = await asyncio.to_thread(_scan_checkpoint_steps_sync, checkpoint_root)
        if steps:
            return steps
    try:
        save_steps = int(save_steps) if save_steps else 0
        latest_step = int(latest_step) if latest_step else 0
    except (TypeError, ValueError):
        save_steps = latest_step = 0
    if save_steps > 0 and latest_step > 0:
        return list(range(save_steps, latest_step + 1, save_steps))
    return []


async def _model_checkpoint_steps(model_info: dict, workspace_info: dict, latest_step) -> list:
    """내부 학습 모델의 체크포인트 step — latest_checkpoint 디렉토리 스캔 + save_steps 추정."""
    try:
        ckpt_root = PATH.JF_MODEL_LATEST_CHECKPOINT_PATH.format(
            STORAGE_NAME=workspace_info["main_storage_name"],
            WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"],
        )
    except Exception:
        ckpt_root = None
    save_steps = None
    try:
        cfg = json.loads(model_info.get("latest_fine_tuning_config") or "{}")
        save_steps = cfg.get("save_steps")
    except (TypeError, json.JSONDecodeError):
        pass
    # save_total_limit=1 이라 디스크엔 최신 ckpt 디렉토리 1개만 남는다 → 스캔만으론
    # 마커가 1개뿐. 저장이 일어난 위치(save_steps 배수)를 추정치로 합쳐(union) 모든
    # 저장 시점을 표시한다.
    scanned = await asyncio.to_thread(_scan_checkpoint_steps_sync, ckpt_root) if ckpt_root else []
    steps = set(scanned)
    try:
        ss = int(save_steps) if save_steps else 0
        ls = int(latest_step) if latest_step else 0
    except (TypeError, ValueError):
        ss = ls = 0
    if ss > 0 and ls > 0:
        steps.update(range(ss, ls + 1, ss))
    return sorted(steps)



async def check_model_files(directory_path):
    # Define required file sets
    adapter_files = ["adapter_model.safetensors", "adapter_config.json"]
    model_files = ["model.safetensors", "config.json"]
    
    # List all files in the directory asynchronously
    try:
        items_in_directory = set(await asyncio.to_thread(os.listdir, directory_path))
    except FileNotFoundError:
        return False  # Return False if the directory doesn't exist
     # Filter out only the files in the directory
    files_in_directory = [item for item in items_in_directory if await asyncio.to_thread(os.path.isfile, os.path.join(directory_path, item))]

    # Check if either set of required files is present in the directory
    if adapter_files in files_in_directory or model_files in files_in_directory:
        return True
    else:
        return False

async def delete_helm_repo(
    helm_repo_name: str, workspace_id: int
) -> Tuple[bool, str]:
    namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
    # --wait: 리소스 실제 삭제까지 블록
    # --timeout 90s: Pod grace period(60s)보다 30s 여유
    command = f"helm uninstall {helm_repo_name} -n {namespace} --wait --timeout 90s"

    print(command)
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        out = stdout.decode() if stdout else ""
        err = stderr.decode().strip() if stderr else ""

        if process.returncode == 0:
            return True, out

        # 이미 삭제된 release는 성공으로 간주 (재시도/중복 호출 멱등)
        if "release not found" in err.lower():
            return True, "release already absent"

        print(out)
        print(err)
        return False, err
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, str(e)

async def create_model_helm(workspace_id : int, model_id : int, model_name:str, commit_model : str = None , commit_name : str = None,\
    huggingface_model_id : str = None, huggingface_token : str = None, save_commit_name : str = None,
    compose_vlm : bool = False, compose_dtype : str = "bfloat16") -> Tuple[bool, str]:
    """
    model_name : commit 되는 모델이 저장되는 모델
    commit_model : commit 하려는 모델 이름
    
    
    """
    try:
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        # 셸 인젝션·경로 탈출 방어(보안리뷰) — 모델명/커밋명은 아래 helm --set f-string(shell=True) + NFS
        # 경로 세그먼트로 들어간다. create_model/create_commit_model 에서 이미 allowlist 를 걸지만, 모든 호출
        # 경로(compose/커스텀 체크포인트 ingestion 등)를 셸 경계에서 재차 봉쇄(promote_model_helm 동일 패턴).
        # '..'·셸 메타문자 차단. (save_commit_name=source_model 도 통과.) 주의: huggingface_model_id 는 HF repo
        # id('/'·','·'@' 포함)라 별도 charset 필요 → 이번 범위 외(별도 처리 권장).
        for _seg, _label in ((model_name, "model_name"), (commit_model, "commit_model"),
                             (commit_name, "commit_name"), (save_commit_name, "save_commit_name")):
            if _seg is None:
                continue
            if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', _seg) or '..' in _seg:
                print(f"Error: invalid {_label} for helm launch: {_seg!r}")
                return False, f"invalid {_label}"
        # huggingface_model_id 는 --set command.model_id 로 셸 f-string 에 보간됨(download·compose). HF repo id
        # 라 '/'(namespace)·','(compose '{vision},{llm}') 허용하되 셸 메타문자($ ` " ; | & 공백 등)·'..' 차단.
        # create_model 진입부에서 이미 검증하지만(다운로드 1440·compose 1394), 셸 경계에서 재봉쇄(defense-in-depth,
        # model_name 과 동일 패턴; 미래 호출자 대비). 콤마는 셸 메타문자 아님(helm --set 용 이스케이프는 아래서 처리).
        if huggingface_model_id is not None:
            if not re.fullmatch(r'[A-Za-z0-9._/,-]{1,200}', huggingface_model_id) or '..' in huggingface_model_id:
                print(f"Error: invalid huggingface_model_id for helm launch: {huggingface_model_id!r}")
                return False, "invalid huggingface_model_id"
        command = ""
        mode = ""
        # HF 토큰을 helm --set(release secret)·pod command 평문 대신 사전 생성 K8s Secret→env(HF_TOKEN)
        # 으로 주입(보안리뷰 C-4). 토큰 없으면(offline/nexus) Secret 미생성 → tokenSecretName="".
        token_secret_name = ""
        if huggingface_token:
            token_secret_name = f"hf-token-{model_id}".lower()
            try:
                create_or_replace_secret(namespace=namespace, name=token_secret_name,
                                         string_data={"token": huggingface_token})
            except Exception as e:
                print(f"Error: failed to create HF token secret: {e}")
                return False, "HF 토큰 시크릿 생성 실패"
        command += f' --set command.tokenSecretName="{token_secret_name}"'
        command += f' --set command.latest_checkpoint_path="{PATH.JF_POD_MODEL_LATEST_CHECKPOINT_PATH.format(MODEL_NAME=model_name)}"'
        if compose_vlm:
            # 멀티모달: 비전+LLM 두 HF id("{vision},{llm}") → LLaVA 조립(projector 자동생성).
            mode = "compose_vlm"
            # helm --set 는 콤마를 key 구분자로 해석 → "{vision},{llm}" 의 콤마를 \, 로 이스케이프
            # (HF repo id 자체엔 콤마 없음). 안 하면 "key has no value" 로 helm install 실패.
            escaped_id = (huggingface_model_id or '').replace(',', '\\,')
            command += f' --set command.model_id="{escaped_id}"'
            # command.token 평문 --set 제거 — 토큰은 tokenSecretName Secret→env(HF_TOKEN)로 주입(C-4).
            command += f' --set command.dst_model_path="{PATH.JF_POD_MODEL_SOURCE_MODEL_PATH.format(MODEL_NAME=model_name)}"'
            command += f' --set command.dtype="{compose_dtype}"'
            # 두 모델 RAM 적재(최대 ~8B) → 다운로드 기본 한도(6Gi) 초과. compose 전용 상향.
            command += ' --set resources.limits.memory=32Gi --set resources.requests.memory=24Gi'
            command += ' --set resources.limits.cpu=2 --set resources.requests.cpu=1'
        elif commit_model:
            mode = "copy_commit_model"
            
            if save_commit_name is None: # model 생성
                save_commit_name = TYPE.MODEL_FIRST_COMMIT_NAME # copy 하려는 commit model path
                command += f' --set command.dst_model_path="{PATH.JF_POD_MODEL_SOURCE_MODEL_PATH.format(MODEL_NAME=model_name)}"'
                command += f' --set command.src_model_path="{PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(MODEL_NAME=commit_model, COMMIT_NAME=commit_name)}"'
                # command += f' --set command.src_tokenizer_path="{PATH.JF_POD_MODEL_TOKENIZER_PATH.format(MODEL_NAME=commit_model)}"'
                # command += f' --set command.dst_tokenizer_dir="{PATH.JF_POD_MODEL_TOKENIZER_PATH.format(MODEL_NAME=model_name)}"'
                command += f' --set command.is_commit=1'
            else: # commit model 생성
                command += f' --set command.dst_model_path="{PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(MODEL_NAME=model_name, COMMIT_NAME=save_commit_name)}"'
                command += f' --set command.dst_log_dir="{PATH.JF_POD_MODEL_COMMIT_LOG_PATH.format(MODEL_NAME=model_name, COMMIT_NAME=save_commit_name)}"'
                command += f' --set command.src_model_log_path="{PATH.JF_POD_MODEL_LATEST_LOG_PATH.format(MODEL_NAME=model_name)}"'
                command += f' --set command.is_commit=0'
            
        elif huggingface_model_id:
            mode = "download_model"
            command += f' --set command.model_id="{huggingface_model_id}"'
            # command.token 평문 --set 제거 — 토큰은 tokenSecretName Secret→env(HF_TOKEN)로 주입(C-4).
            command += f' --set command.dst_model_path="{PATH.JF_POD_MODEL_SOURCE_MODEL_PATH.format(MODEL_NAME=model_name)}"'
            # command += f' --set command.tokenizer_dir="{PATH.JF_POD_MODEL_TOKENIZER_PATH.format(MODEL_NAME=model_name)}"'
            

        os.chdir("/app/helm/")
        if save_commit_name is None:
            save_commit_name = TYPE.MODEL_FIRST_COMMIT_NAME

        helm_name = TYPE.MODEL_COMMIT_JOB_HELM_NAME.format(MODEL_ID=model_id)
        # compose_vlm 은 transformers/torch 가 필요 → FT 이미지(transformers 4.52.4) 사용(경량 다운로드 이미지 X).
        image = settings.FINE_TUNING_IMAGE if compose_vlm else settings.SYSTEM_DOCKER_REGISTRY_URL + "acrylaaai/llm-finetune:dev"
        helm_command = f"""helm install {helm_name} ./model_download \
            -n {namespace}  \
            --set namespace="{namespace}" \
            --set image="{image}" \
            --set labels.model_id={model_id} \
            --set labels.workspace_id={workspace_id} \
            --set labels.model_commit_type="{mode}" \
            --set labels.helm_name={helm_name} \
            --set labels.pod_type={TYPE.FINE_TUNING_TYPE} \
            --set labels.work_func_type="commit" \
            --set command.mode="{mode}" \
            {command} \
        """

        print(_redact_secrets(helm_command))
        process = await asyncio.create_subprocess_shell(
            helm_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return 1, stdout
        else:
            err_msg = stderr.decode().strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            print(stdout)
            print(err_msg)
            print(_redact_secrets(command))
            return False, err_msg
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, str(e)

async def promote_model_helm(workspace_id: int, model_id: int, model_name: str, src_commit_name: str,
                             best_step: int, target_step: int, new_commit_name: str) -> Tuple[bool, str]:
    """Phase 2-C promote 잡 런치 — 커밋의 step 체크포인트를 새 버전으로 재머지(LoRA cat 델타 산술).
    입력: commit_models/<src>(merged=base+best_delta) + commit_checkpoints/<src>/adapters/{best,target}.
    출력: commit_models/<new>(=base+target_delta) + commit_logs/<new>. 서빙(latest_checkpoint) 미변경(비파괴).
    peft 필요 → FT 이미지. create_model_helm 과 동일 subprocess/멱등 처리."""
    try:
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        mode = "promote_checkpoint"
        # 셸 인젝션·경로 탈출 차단(보안리뷰) — 이 값들은 helm --set f-string(subprocess_shell) + NFS 경로
        # 세그먼트로 들어간다. model_name 은 플랫폼 차원 allowlist 미적용(create_model)이고, src_commit_name
        # 은 구 커밋이 비검증일 수 있어 여기서 재검증(C-1/C-2·commit_name 하드닝 동일 클래스). best/target 은
        # 아래 f-string 에서 int() 강제라 안전.
        for _seg, _label in ((model_name, "model_name"), (src_commit_name, "src_commit_name"),
                             (new_commit_name, "new_commit_name")):
            if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', _seg or '') or '..' in (_seg or ''):
                print(f"Error: invalid {_label} for promote: {_seg!r}")
                return False, f"invalid {_label}"
        ckpt_adapters = PATH.JF_POD_MODEL_COMMIT_CHECKPOINT_PATH.format(MODEL_NAME=model_name) + f"/{src_commit_name}/adapters"
        command = ""
        # 새 커밋만 생성(비파괴) → latest_checkpoint 빈 값 = 엔진이 서빙 복사 skip.
        command += ' --set command.latest_checkpoint_path=""'
        command += f' --set command.src_model_path="{PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(MODEL_NAME=model_name, COMMIT_NAME=src_commit_name)}"'
        command += f' --set command.best_adapter_path="{ckpt_adapters}/checkpoint-{int(best_step)}"'
        command += f' --set command.target_adapter_path="{ckpt_adapters}/checkpoint-{int(target_step)}"'
        command += f' --set command.dst_model_path="{PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(MODEL_NAME=model_name, COMMIT_NAME=new_commit_name)}"'
        command += f' --set command.dst_log_dir="{PATH.JF_POD_MODEL_COMMIT_LOG_PATH.format(MODEL_NAME=model_name, COMMIT_NAME=new_commit_name)}"'
        command += f' --set command.src_model_log_path="{PATH.JF_POD_MODEL_COMMIT_LOG_PATH.format(MODEL_NAME=model_name, COMMIT_NAME=src_commit_name)}"'

        os.chdir("/app/helm/")
        helm_name = TYPE.MODEL_COMMIT_JOB_HELM_NAME.format(MODEL_ID=model_id)
        image = settings.FINE_TUNING_IMAGE   # promote = 모델 로드+PEFT merge → FT 이미지
        helm_command = f"""helm install {helm_name} ./model_download \
            -n {namespace}  \
            --set namespace="{namespace}" \
            --set image="{image}" \
            --set labels.model_id={model_id} \
            --set labels.workspace_id={workspace_id} \
            --set labels.model_commit_type="{mode}" \
            --set labels.helm_name={helm_name} \
            --set labels.pod_type={TYPE.FINE_TUNING_TYPE} \
            --set labels.work_func_type="commit" \
            --set command.mode="{mode}" \
            --set resources.limits.memory=32Gi --set resources.requests.memory=24Gi \
            --set resources.limits.cpu=2 --set resources.requests.cpu=1 \
            {command} \
        """
        print(_redact_secrets(helm_command))    # create_model_helm 과 동일 마스킹(로그 위생, 리뷰 HIGH)
        process = await asyncio.create_subprocess_shell(
            helm_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            return 1, stdout
        err_msg = stderr.decode().strip()
        # promote 맥락: release 이미 존재 = 다른 커밋/promote 잡 실행 중 → 실패로 처리(호출부 롤백). create_model_helm
        # 의 멱등(True) 처리와 다름 — promote 는 commit_status 게이트로 재시도가 막히므로 collision=경쟁 상황.
        if "cannot re-use a name that is still in use" in err_msg:
            return False, "another commit/promote job is running"
        print(stdout)
        print(err_msg)
        return False, err_msg
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, str(e)


async def load_or_stop_helm(workspace_id : int, model_id: int, latest_checkpoint_path : str, tmp_model_path: str = None, load_commit_model_path : str = None):
    try:
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        command = ""
        mode = ""
        command += f' --set command.latest_checkpoint_path="{latest_checkpoint_path}"'
        if tmp_model_path:
            mode = "stop_fine_tuning"
            command += f' --set command.tmp_model_path="{tmp_model_path}"'
            
        elif load_commit_model_path:
            mode = "load_commit_model"
            command += f' --set command.load_commit_model_path="{load_commit_model_path}"'
            

        os.chdir("/app/helm/")

        helm_name = TYPE.MODEL_COMMIT_JOB_HELM_NAME.format(MODEL_ID=model_id)
        image = settings.SYSTEM_DOCKER_REGISTRY_URL + "acrylaaai/llm-finetune:dev"
        helm_command = f"""helm install {helm_name} ./model_download \
            -n {namespace}  \
            --set namespace="{namespace}" \
            --set image="{image}" \
            --set labels.model_id={model_id} \
            --set labels.workspace_id={workspace_id} \
            --set labels.model_commit_type="{mode}" \
            --set command.mode="{mode}" \
            {command} \
        """

        print(_redact_secrets(helm_command))
        process = await asyncio.create_subprocess_shell(
            helm_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return 1, stdout
        else:
            err_msg = stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            print(stdout)
            print(err_msg)
            print(_redact_secrets(command))
            return False, err_msg
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, str(e)
    
    pass

async def create_model_folder(storage_name : str, workspace_name : str , model_name : str) -> bool:
    model_commit_dir = PATH.JF_MODEL_COMMIT_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_source_dir = PATH.JF_MODEL_TMP_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_config_dir = PATH.JF_MODEL_CONFIGURATION_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_log_dir = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_commit_log_dir = PATH.JF_MODEL_COMMIT_LOG_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    model_latest_checkpoint_dir = PATH.JF_MODEL_LATEST_CHECKPOINT_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    # 체크포인트 레지스트리(Phase1) 디렉터리 — fine_tuning 차트의 /checkpoints subPath 가 마운트되므로
    # 모델 생성 시 미리 생성(subPath 자동생성 안 되는 클러스터에서 마운트 실패 방지, codex MEDIUM).
    model_checkpoints_dir = os.path.join(os.path.dirname(model_latest_checkpoint_dir), "checkpoints")
    paths = [model_commit_dir, model_source_dir, model_config_dir, model_log_dir, model_commit_log_dir, model_latest_checkpoint_dir, model_checkpoints_dir]
    
    # mkdir
    for path in paths:
        try:
            # 디렉터리 생성 작업을 비동기적으로 처리
            await asyncio.to_thread(os.makedirs, path)
        except Exception:
            # 예외 처리도 비동기적으로 수행
            await asyncio.to_thread(traceback.print_exc)
            await asyncio.to_thread(common.rm_rf, path)
            await asyncio.to_thread(os.makedirs, path)
        
    return True


async def delete_model_folder(storage_name: str, workspace_name: str, model_name: str) -> bool:
    model_dir_path = PATH.JF_MAIN_MODEL_PATH.format(
        STORAGE_NAME=storage_name,
        WORKSPACE_NAME=workspace_name,
        MODEL_NAME=model_name
    )

    # rm -rf 전 경로 가드 — DB 값(storage/workspace/model_name)에 ../ 나 절대경로가
    # 섞이면 임의 경로 삭제. 반드시 워크스페이스 models 루트 하위로 한정.
    models_root = os.path.realpath(PATH.JF_MAIN_MODEL_PATH.format(
        STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME="",
    ).rstrip("/"))
    real_target = os.path.realpath(model_dir_path)
    if (not model_name or "/" in model_name or model_name in (".", "..")
            or os.path.commonpath([real_target, models_root]) != models_root
            or real_target == models_root):
        print(f"refusing rm -rf on unsafe model path: {model_dir_path!r}")
        return False

    try:
        # subprocess를 사용하여 rm -rf 실행
        result = await asyncio.create_subprocess_exec(
            'rm', '-rf', model_dir_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            print(f"Error deleting folder: {stderr.decode().strip()}")
            return False

    except Exception as e:
        traceback.print_exc()
        return False

    return True

async def delete_commit_model_folder(storage_name : str, workspace_name : str, model_name : str, commit_name: str) -> bool:
    commit_model_dir_path = PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name, COMMIT_NAME=commit_name)
    try:
        await common.async_rmtree(commit_model_dir_path)
    except Exception as e:
        traceback.print_exc()
        return False
    return True


def _commit_checkpoints_dir(storage_name: str, workspace_name: str, model_name: str, commit_name: str) -> Tuple[str, str]:
    """(base, dst) — commit_checkpoints 베이스와 그 하위 <commit_name> 스냅샷 경로. commit_name 은
    create_commit_model 의 allowlist(영문/숫자/._-, '..' 금지)를 이미 통과하지만, 베이스 이탈은
    방어적으로 호출부에서 _is_under 로 재확인."""
    base = PATH.JF_MODEL_COMMIT_CHECKPOINT_PATH.format(
        STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name)
    return base, os.path.join(base, commit_name)


async def snapshot_commit_checkpoints(storage_name: str, workspace_name: str, model_name: str, commit_name: str) -> bool:
    """커밋 시점에 학습 체크포인트(어댑터 레지스트리)를 커밋(버전)에 귀속 — models/<name>/checkpoints/
    전체(adapters/ + VLM _projector.pt 등)를 commit_checkpoints/<commit>/ 로 서버측 스냅샷.
    어댑터가 작아(LoRA 수MB×N + projector) 커밋당 ~50MB. 별도 top-level 디렉터리라 커밋 헬름 잡
    (commit_models, latest_checkpoint→merged)과 레이스 없음. 체크포인트 부재/빈 경우 graceful skip
    (커밋 자체는 성공). 경로는 commit_checkpoints 베이스 하위로 봉쇄."""
    model_root = os.path.dirname(PATH.JF_MODEL_LATEST_CHECKPOINT_PATH.format(
        STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_name))
    src = os.path.join(model_root, "checkpoints")
    base, dst = _commit_checkpoints_dir(storage_name, workspace_name, model_name, commit_name)
    # src·dst 모두 베이스 하위로 봉쇄(방어적 일관성, 리뷰 MEDIUM). commit_name 은 호출부 allowlist 통과본.
    if "/" in commit_name or commit_name in (".", "..") or not _is_under(dst, base) or not _is_under(src, model_root):
        raise Exception("Error: invalid commit checkpoint path")
    # 어댑터 디렉터리가 없으면 스냅샷할 게 없음(외부/구 모델, full-merge-only 등) → graceful skip.
    if not await asyncio.to_thread(os.path.isdir, os.path.join(src, "adapters")):
        return False
    await asyncio.to_thread(os.makedirs, base, exist_ok=True)
    if await asyncio.to_thread(os.path.isdir, dst):    # 중복 커밋명은 상위에서 막지만 방어적 정리.
        await asyncio.to_thread(common.rm_rf, dst)
    # symlinks=True: src 내 심링크를 (대상 내용 복제 대신) 링크로 보존 → 학습 파드가 심어둔 심링크를 통한
    # NFS 임의 파일 내용 유출 차단(보안리뷰 H-2). ignore_dangling_symlinks: 끊긴 링크는 무시(복사 실패 방지).
    await asyncio.to_thread(shutil.copytree, src, dst, symlinks=True, ignore_dangling_symlinks=True)
    return True


async def delete_commit_checkpoints_folder(storage_name: str, workspace_name: str, model_name: str, commit_name: str) -> bool:
    """커밋 롤백/삭제 시 commit_checkpoints/<commit> 스냅샷 정리. 베이스 이탈 차단."""
    base, dst = _commit_checkpoints_dir(storage_name, workspace_name, model_name, commit_name)
    if "/" in commit_name or commit_name in (".", "..") or not _is_under(dst, base):
        return False
    try:
        if await asyncio.to_thread(os.path.isdir, dst):
            await asyncio.to_thread(common.rm_rf, dst)
    except Exception:
        traceback.print_exc()
        return False
    return True


async def check_file_exists(file_path: str) -> bool:
    """
    비동기적으로 파일이 존재하는지 확인하는 함수.
    
    :param file_path: 확인하려는 파일의 경로
    :return: 파일이 존재하면 True, 존재하지 않으면 False
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, os.path.exists, file_path)


def _is_under(path: str, root: str) -> bool:
    """path 가 root 디렉터리 내부인지(traversal 차단). SSE TB 로그 경로 봉쇄용(보안리뷰 M-4)."""
    try:
        rp, rr = os.path.realpath(path), os.path.realpath(root)
        return os.path.commonpath([rp, rr]) == rr
    except (ValueError, OSError):
        return False


async def user_can_access_model(user_id: int, model_id: int) -> bool:
    """모델 카드 접근 권한 — 소유자 OR (공유(access=1) → 워크스페이스 멤버). 비공개(access!=1)는 소유자만.
    SSE(학습 그래프/시간/상태) 구독 게이팅(보안리뷰 H-3). model/route.py 의 기존 get_user_id() 패턴과
    동형(데코레이터 아님). is_workspace_user 는 db_workspace.get_user_workspace 로 멤버십 확인."""
    if not user_id:
        return False
    model = await db_model.get_model(model_id=model_id)
    if not model:
        return False
    if model.get("create_user_id") == user_id:
        return True
    if model.get("access") == 1:
        return is_workspace_user(user_id=user_id, workspace_id=model["workspace_id"])
    return False


async def move_checkpoint_files_to_parent(path):
    """
    Checks if the specified path contains any subdirectories that start with 'checkpoint'.
    If such directories are found, moves all files from the one with the highest numerical suffix to the parent directory,
    and deletes the remaining checkpoint directories. Ensures that no 'checkpoint' folder remains in the path.

    Args:
        path (str): Path to the directory to search.

    Returns:
        bool: True if a checkpoint folder was found and files were moved, False otherwise.
    """
    # Check if the specified path is a directory
    if not await asyncio.to_thread(os.path.isdir, path):
        print(f"Error: The specified path '{path}' does not exist or is not a directory.")
        return False

    # Get list of items in the directory asynchronously
    try:
        items = await asyncio.to_thread(os.listdir, path)
    except Exception as e:
        print(f"Error accessing directory '{path}': {e}")
        return False

    # Find all 'checkpoint-*' directories and determine the one with the highest suffix
    checkpoint_dirs = []
    for item in items:
        if item.startswith('checkpoint-') and await asyncio.to_thread(os.path.isdir, os.path.join(path, item)):
            try:
                suffix = int(item.split('-')[-1])
                checkpoint_dirs.append((suffix, os.path.join(path, item)))
            except ValueError:
                continue

    if not checkpoint_dirs:
        print("No checkpoint folder found.")
        return False

    # Sort checkpoint directories by suffix in descending order
    checkpoint_dirs.sort(reverse=True, key=lambda x: x[0])

    # The directory with the highest suffix
    latest_checkpoint_dir = checkpoint_dirs[0][1]
    print(f"Found latest checkpoint folder: '{latest_checkpoint_dir}'")

    # Move each file in the latest checkpoint folder to the parent directory
    for file_name in await asyncio.to_thread(os.listdir, latest_checkpoint_dir):
        file_path = os.path.join(latest_checkpoint_dir, file_name)
        
        # Ensure it's a file before moving
        if await asyncio.to_thread(os.path.isfile, file_path):
            destination_path = os.path.join(path, file_name)
            
            try:
                await asyncio.to_thread(shutil.move, file_path, destination_path)
                print(f"Moved '{file_path}' to '{destination_path}'")
            except Exception as e:
                print(f"Error moving file '{file_path}': {e}")

    # Remove all checkpoint directories
    for _, checkpoint_dir in checkpoint_dirs:
        try:
            await asyncio.to_thread(shutil.rmtree, checkpoint_dir)
            print(f"Removed checkpoint folder: '{checkpoint_dir}'")
        except Exception as e:
            print(f"Error removing checkpoint folder '{checkpoint_dir}': {e}")

    # Ensure no 'checkpoint' folder remains in the path
    remaining_items = await asyncio.to_thread(os.listdir, path)
    if any(item.startswith('checkpoint') for item in remaining_items):
        print("Error: 'checkpoint' folder still exists in the path.")
        return False

    return True  # Return True if a checkpoint folder was found and files were moved

#==========
# OPTION
#==========

async def get_model_update(model_id : int):
    model_info = await db_model.get_model_simple(model_id=model_id)
    user_list = await db_model.get_model_user_list(model_id=model_id)
    model_info["user_list"] = user_list 
    return model_info

async def get_workspace_user(workspace_id : int) -> dict:
    workspace_info = db_user.get_user_list_in_workspace(workspace_id=workspace_id)
    return workspace_info

async def get_models_option(workspace_id : int, model_name : str = None, header_user_id : int = None, is_mine : bool = False):
    if is_mine:
        models = await db_model.get_models_option(workspace_id=workspace_id, model_name=model_name, create_user_id=header_user_id)
    else:
        models = await db_model.get_models_option(workspace_id=workspace_id, model_name=model_name)
    return models

async def get_commit_models_option(model_id : int, commit_name: str = None):
    
    commit_models = await db_model.get_commit_models_option(model_id=model_id, commit_name=commit_name)
    for commit_model in commit_models:
        commit_model["fine_tuning_config"]=json.loads(commit_model["fine_tuning_config"]) 
    return commit_models

async def get_dataset_list(workspace_id : int, create_user_id : int = None, dataset_name : str = None) -> List[dict]:
    
    datasets = await db_model.get_datasets(workspace_id=workspace_id, create_user_id=create_user_id, dataset_name=dataset_name)
    
    return datasets

async def get_instance_list(workspace_id : int) -> List[dict]:
    instance_list = await db_model.get_instance_list(workspace_id=workspace_id)
    for instance in instance_list:
        #TODO
        # allm 에서 사용중인 인스턴스 수 빼기 
        instance["available_instance"] = instance["instance_allocate"]
    return instance_list

async def get_models_by_huggingface(model_name : str = None, huggingface_token : str = None, private : int = 0, model_kind : str = 'text') -> List[str]:
    api = HfApi()

    # model_kind 별 HF pipeline_tag 필터 — 멀티모달(VLM) 비전 인코더 슬롯은 CLIP/SigLIP
    # (zero-shot-image-classification) 를 검색해야 한다(text-generation 필터로는 안 잡힘).
    # 그 외(단일 모델 / LLM 슬롯)는 기존대로 text-generation transformers.
    if (model_kind or 'text').strip().lower() == 'vision':
        hf_filter = ["zero-shot-image-classification"]
    else:
        hf_filter = ["text-generation", "transformers"]

    if private:
        huggingface_token = front_cipher.decrypt(huggingface_token)
        models = api.list_models(limit=10, filter=hf_filter, search=model_name, expand=["private"], token=huggingface_token)
    else:
        models = api.list_models(limit=10, filter=hf_filter, search=model_name)
    parse_model_ids = [ model.id for model in models]
    return parse_model_ids

async def check_model_access( token: str, model_id: str = None, model_create : bool = False) -> bool:
    """
    해당 Hugging Face 모델에 대해 주어진 토큰으로 접근 권한이 있는지 확인하는 함수 (비동기 버전).

    Parameters:
    model_id (str): 접근하려는 모델의 Hugging Face ID.
    token (str): Hugging Face API 토큰.

    Returns:
    bool: 접근 권한이 있으면 True, 없으면 False.
    """
    loop = asyncio.get_event_loop()
    if not model_create:
        token = front_cipher.decrypt(token)
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
    
async def get_dataset_files_and_folders(dataset_id : int, search_user_id : int, search : str = None)-> List[dict]:
    dataset_info = await db_model.get_dataset_model(dataset_id=dataset_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=dataset_info["workspace_id"])
    dataset_path = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"] ,WORKSPACE_NAME=workspace_info["name"] , \
            ACCESS=dataset_info["access"] , DATASET_NAME=dataset_info["name"])
    files_and_folders = await find_files_and_folders_by_extension(directory=dataset_path, extensions=TYPE.MODEL_DATA_EXTENSIONS, search_user_id=search_user_id, search=search)
    
    return files_and_folders

async def find_files_and_folders_by_extension(directory: str, extensions: list, search_user_id: int, search: str = None) -> List[dict]:
    result = []

    # Check if directory exists
    if not os.path.exists(directory):
        return result

    # Generate user UUID
    user_uuid = search_user_id + settings.USER_UUID_SET

    # Asynchronously find files and folders
    loop = asyncio.get_event_loop()
    tasks = []
    
    for item in Path(directory).rglob('*'):
        tasks.append(loop.run_in_executor(None, item.stat))

    stats = await asyncio.gather(*tasks)
    
    for item, item_metadata in zip(Path(directory).rglob('*'), stats):
        item_uuid = item_metadata.st_uid

        # If search term is provided, filter by file or folder name
        if search is not None and search not in item.name:
            continue

        # Check if item is a file with the correct extension
        if item.is_file() and any(item.suffix == ext for ext in extensions):
            result.append({
                "file_path": str(item.relative_to(directory)),
                "is_owner": item_uuid == user_uuid,
                "is_folder": False  # Indicate it's a file
            })

        # If item is a folder
        elif item.is_dir():
            result.append({
                "file_path": str(item.relative_to(directory)),
                "is_owner": item_uuid == user_uuid,
                "is_folder": True  # Indicate it's a folder
            })

    return result

async def add_dataset(model_id: int, dataset_id : int, training_data_path : str):
    
    dataset_info = await db_model.get_dataset_model(dataset_id=dataset_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=dataset_info["workspace_id"])
    training_data_full_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"] ,WORKSPACE_NAME=workspace_info["name"] , \
            ACCESS=dataset_info["access"] , DATASET_NAME=dataset_info["name"], DATA_PATH=training_data_path)
    # training_data_path traversal(`../`) 차단 — 데이터셋 루트 내부로 봉쇄(codex: 검증이 no-op 였음).
    dataset_root = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"], WORKSPACE_NAME=workspace_info["name"],
            ACCESS=dataset_info["access"], DATASET_NAME=dataset_info["name"])
    _real_full = os.path.realpath(training_data_full_path)
    _real_root = os.path.realpath(dataset_root)
    if os.path.commonpath([_real_full, _real_root]) != _real_root:
        return False
    # ⚠️ check_file_exists 는 async — await 누락 시 코루틴이 항상 truthy 가 되어 검증이 무력화됐음(codex).
    if await check_file_exists(file_path=training_data_full_path):
        await db_model.create_fine_tuning_dataset(training_data_path=training_data_path, dataset_id=dataset_id, model_id=model_id)

        return True
    return False
#==========
    

async def get_models(workspace_id : int, header_user_id : int) -> List[dict]:

    models = await db_model.get_models(workspace_id=workspace_id)

    models_parse = []   

    redis_client = await get_redis_client_async()


    model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, workspace_id)

    if model_pod_status:
        model_pod_status = json.loads(model_pod_status)
    else:
        model_pod_status = {}

    favorites_model = await db_model.get_favorite_models(header_user_id)

    favorites_model_id = [model["model_id"] for model in favorites_model]
    
    async def process_model(model):
        private_users  = await db_model.get_model_user_list(model_id=model["id"])
        res = {
            "id" : model["id"],
            "name" : model["name"],
            "bookmark" : model["id"] in favorites_model_id,
            "is_access" :  True if model["access"] == 1 or header_user_id in [user["user_id"] for user in private_users]  else False,
            "users" : private_users,
            "status" : {
                "fine_tuning" : model["latest_fine_tuning_status"],
                "commit" : model["commit_status"]
                },
            "create_user_name" : model["create_user_name"],
            "update_datetime" : model["update_datetime"],
            "create_datetime" : model["create_datetime"],
            "description" : model["description"]
        }
        if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
            if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model["id"]),{}):
                res["status"]["fine_tuning"] = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model["id"])]["status"]
        
        return res
        

    models_parse = await asyncio.gather(*(process_model(model) for model in models))

    return models_parse

async def get_commit_models(model_id : int) -> List[dict]:
    
    model_info = await db_model.get_model(model_id=model_id)
    
    commit_models = await db_model.get_commit_models(model_id=model_id)
    
          
    return {
        "list" : commit_models,
        "model_name" : model_info["name"]
    }

async def get_commit_model(commit_model_id : int):
    commit_model_info = await db_model.get_commit_model(commit_id=commit_model_id)
    model_info = await db_model.get_model(model_id=commit_model_info["model_id"])
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    config = json.loads(commit_model_info.get("fine_tuning_config", "{}"))
    if commit_model_info["name"] != "source_model":
        try:
            commit_log_path = PATH.JF_MODEL_COMMIT_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
                    WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"]) + "/{}".format(commit_model_info["name"])
            log_parser, _ = await parse_tensorboard_scalars_async(log_dir=commit_log_path)
            commit_model_info["result_log"] = log_parser
        except Exception as e:
            commit_model_info["result_log"] = {}
    return commit_model_info    


async def load_commit_model(commit_model_id : int) -> dict:
    commit_model_info = await db_model.get_commit_model(commit_id=commit_model_id)
    if commit_model_info:
        model_id = commit_model_info["model_id"]
        model_info = await db_model.get_model(model_id=model_id)
        # workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
        # TODO
        # latest_checkpoint 에 있는 모델 삭제 후 해당 모델 copy
        latest_checkpoint_path = PATH.JF_POD_MODEL_LATEST_CHECKPOINT_PATH.format(MODEL_NAME=model_info["name"])
        load_model_path = PATH.JF_POD_MODEL_COMMIT_MODEL_PATH.format(MODEL_NAME=model_info["name"], COMMIT_NAME=commit_model_info["name"])
        
        res , message = await load_or_stop_helm(workspace_id=model_info["workspace_id"], model_id=model_id, latest_checkpoint_path=latest_checkpoint_path, load_commit_model_path=load_model_path)
        if res :
            await db_model.update_model_commit_status(commit_status=TYPE.KUBE_POD_STATUS_RUNNING, model_id=model_id, latest_commit_id=commit_model_id, commit_type=TYPE.COMMIT_TYPE_LOAD)
        return res
    return False

async def update_model_description(model_id : int, description : str):
    res = await db_model.update_model_description(model_id=model_id, description=description)
    return res

async def update_model(model_id :int , description : str, access : int, create_user_id : int, user_list : List[int]) -> bool:
    
    try:
        res = await db_model.update_model(model_id=model_id, description=description, access=access, create_user_id=create_user_id)
        print(res)
        old_user_list = await db_model.get_model_user_list(model_id=model_id)
        old_user_list = [user["user_id"] for user in old_user_list]
        insert_user_list = list(set(user_list) - set(old_user_list))
        delete_user_list = list(set(old_user_list) - set(user_list))
        for user_id in delete_user_list:
            await db_model.delete_model_user_list(model_id=model_id, user_id=user_id)
        if insert_user_list:
            await db_model.create_model_user_list(model_id=model_id, user_list=insert_user_list)
        
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def set_bookmark_model(model_id : int, header_user_id : int):
    try:
        is_favorite_model = await db_model.get_favorite_model(model_id=model_id, user_id=header_user_id)
        if is_favorite_model:
            # 삭제
            await db_model.delete_favorite_model(model_id=model_id, user_id=header_user_id)
        else:
            # 추가 
            await db_model.create_favorite_model(model_id=model_id, user_id=header_user_id)
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def get_model_summary(model_id: int):
    model_info = await db_model.get_model(model_id=model_id)
    return {
        "name" : model_info["name"],
        "description" : model_info["description"],
        "huggingface_model_id" : model_info["huggingface_model_id"],
        "commit_model_name" : model_info["commit_model_name"],
        "create_user_name" : model_info["create_user_name"],
        "create_datetime" : model_info["create_datetime"],
        "update_datetime" : model_info["update_datetime"]
    }

async def create_commit_model(commit_name : str, commit_message : str, model_id : int, create_user_id : int) -> bool:
    
    model_info = await db_model.get_model(model_id=model_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    tmp_path = PATH.JF_MODEL_TMP_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
    if not model_info:
        raise Exception(f"Error: not exist model")

    # commit_name 은 create_model_helm 의 helm --set f-string(shell=True 실행) + NFS 경로
    # (commit_models/<name>, commit_logs/<name>)에 그대로 들어간다. FE 정규식이 일부 특수문자만
    # 막고 '/'·'..' 는 통과(직접 API 호출은 FE 우회) → 서버측 allowlist 로 셸 인젝션·경로 탈출 차단
    # (보안리뷰 Finding1; C-1/C-2 RCE 하드닝과 동일 클래스). 영문/숫자/._- 1~50자, '..' 금지.
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,50}', commit_name or '') or '..' in (commit_name or ''):
        raise Exception("Error: invalid commit name (영문/숫자/._- 1~50자, '..' 불가)")

    # duplicate check
    if await db_model.check_commit_model_by_name(model_id=model_id, commit_name=commit_name):
        raise Exception(f"Error: duplicate commit model name")
    
    redis_client = await get_redis_client_async()
    model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, model_info["workspace_id"]) 
    if model_pod_status:
        model_pod_status = json.loads(model_pod_status)
    else:
        model_pod_status = {}
    fine_tuning_status = TYPE.KUBE_POD_STATUS_DONE
    if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
        if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model_id),{}):
            fine_tuning_status = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model_id)]["status"]
    
    # model status check
    if model_info["latest_fine_tuning_status"] not in [TYPE.KUBE_POD_STATUS_DONE, TYPE.KUBE_POD_STATUS_STOP]:
    # if any(status not in [TYPE.KUBE_POD_STATUS_DONE, TYPE.KUBE_POD_STATUS_STOP] 
    #    for status in [fine_tuning_status, model_info["latest_fine_tuning_status"]]):
        raise Exception(f"Error: incomplete model")
    # adapter_model.safetensors, model.safetensors, adapter_config.json, config.json이 있는지 조사 
    if await check_model_files(tmp_path):
        raise Exception(f"Error: Invalid model")
    
    try:       
        commit_model_id = await db_model.create_commit_model(model_id=model_id, workspace_id=model_info["workspace_id"], create_user_id=create_user_id, fine_tuning_config=model_info["latest_fine_tuning_config"],
                                        commit_message=commit_message, name=commit_name, model_description=model_info["description"], steps_per_epoch=model_info["steps_per_epoch"]) 
        if commit_model_id:
            # TODO
            # model 이동
            res , message = await create_model_helm(workspace_id=model_info["workspace_id"], model_id=model_id, model_name=model_info["name"], commit_model=model_info["name"], \
                    save_commit_name=commit_name)
            if res:
                await db_model.update_model_commit_status(commit_status=TYPE.KUBE_POD_STATUS_RUNNING, model_id=model_id, latest_commit_id=commit_model_id, commit_type=TYPE.COMMIT_TYPE_COMMIT)
                # 학습 체크포인트(어댑터 레지스트리)를 이 커밋(버전)에 귀속(Phase 2-C) — best-effort.
                # 스냅샷 실패는 커밋을 막지 않음(commit_models 머티리얼라이즈가 핵심 경로). 체크포인트
                # 부재(외부/구 모델)는 graceful skip.
                try:
                    await snapshot_commit_checkpoints(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"], commit_name=commit_name)
                except Exception:
                    traceback.print_exc()

            return res
        return False

    except Exception as e:
        if commit_model_id:
            await db_model.delete_commit_model(commit_model_id=commit_model_id)
            workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
            await delete_commit_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"], commit_name=commit_name)
            await delete_commit_checkpoints_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"], commit_name=commit_name)
        return False
            
def _ckpt_metric(log_history, step, field):
    """log_history(체크포인트 trainer_state.json)에서 step 이하 최신 non-None field 값.
    train loss/grad 는 logging_steps 주기라 save 주기와 어긋남 → nearest-prior. eval_loss 는 보통 save
    주기와 일치(정확). 작은 리스트라 선형 스캔."""
    found = None
    for h in (log_history or []):
        s = h.get("step")
        if s is None or s > step:
            continue
        v = h.get(field)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            found = v
    return found


def _read_text_capped(path: str, cap: int = 4 * 1024 * 1024) -> str:
    """trainer_state.json 등 파드-기록 파일 읽기 — context-manager(FD 누수 방지, 리뷰 MEDIUM) +
    크기 cap(악성/거대 출력 메모리 DoS 차단, 보안 LOW; 정상 trainer_state 는 수 KB). 초과 시 예외."""
    with open(path, encoding="utf-8") as f:
        data = f.read(cap + 1)
    if len(data) > cap:
        raise ValueError("file too large")
    return data


async def list_checkpoints(model_id: int, commit_name: str = None) -> dict:
    """체크포인트 레지스트리 — checkpoint-{step} 어댑터 나열. commit_name 없으면 라이브 학습본
    (models/{name}/checkpoints/adapters), 있으면 커밋 스냅샷(commit_checkpoints/{commit}/adapters,
    Phase 2-C — 커밋=버전에 귀속). 메트릭/best 는 최고 step 체크포인트의 trainer_state.json
    (가장 완전한 log_history + best_model_checkpoint)에서 추출. 크기=adapter 가중치(실 산출물)."""
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception("Error: not exist model")
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    model_root = os.path.dirname(PATH.JF_MODEL_LATEST_CHECKPOINT_PATH.format(
        STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"],
        MODEL_NAME=model_info["name"]))
    empty = {"list": [], "best_step": None, "steps_per_epoch": model_info.get("steps_per_epoch") or 0}
    if commit_name:
        # Phase 2-C: 커밋별 스냅샷. commit_name 은 라우트에서 DB(get_commit_model)로 해소되지만 방어적 봉쇄.
        if "/" in commit_name or commit_name in (".", ".."):
            return empty
        _ckpt_base, _commit_dir = _commit_checkpoints_dir(workspace_info["main_storage_name"], workspace_info["name"],
                                                          model_info["name"], commit_name)
        adapters_dir = os.path.join(_commit_dir, "adapters")
        _containment_root = _ckpt_base    # 커밋 스냅샷은 commit_checkpoints 베이스 하위로 봉쇄(의도 명확)
    else:
        adapters_dir = os.path.join(model_root, "checkpoints", "adapters")
        _containment_root = model_root
    if not _is_under(adapters_dir, _containment_root):    # 경로 봉쇄(방어)
        return empty
    try:
        entries = await asyncio.to_thread(os.listdir, adapters_dir)
    except (FileNotFoundError, NotADirectoryError):
        return empty
    ckpt_names = sorted(
        [e for e in entries if e.startswith("checkpoint-") and e[len("checkpoint-"):].isdigit()],
        key=lambda e: int(e[len("checkpoint-"):]))
    if not ckpt_names:
        return empty
    best_step, log_history = None, []
    ts_path = os.path.join(adapters_dir, ckpt_names[-1], "trainer_state.json")
    try:
        ts = json.loads(await asyncio.to_thread(_read_text_capped, ts_path))
        bmc = ts.get("best_model_checkpoint") or ""
        base = os.path.basename(bmc)
        if base.startswith("checkpoint-") and base[len("checkpoint-"):].isdigit():
            best_step = int(base[len("checkpoint-"):])
        log_history = ts.get("log_history") or []
    except Exception:
        pass
    out = []
    for name in ckpt_names:
        step = int(name[len("checkpoint-"):])
        fpath = os.path.join(adapters_dir, name)
        try:
            saved_at = int(await asyncio.to_thread(os.path.getmtime, fpath))
        except OSError:
            saved_at = None
        try:
            size_bytes = await asyncio.to_thread(os.path.getsize, os.path.join(fpath, "adapter_model.safetensors"))
        except OSError:
            size_bytes = None    # full-FT 는 adapter 파일 없음 → None(FE 가 폴더 표기)
        out.append({
            "step": step,
            "epoch": _ckpt_metric(log_history, step, "epoch"),
            "loss": _ckpt_metric(log_history, step, "loss"),
            "grad_norm": _ckpt_metric(log_history, step, "grad_norm"),
            "learning_rate": _ckpt_metric(log_history, step, "learning_rate"),
            "eval_loss": _ckpt_metric(log_history, step, "eval_loss"),
            "size_bytes": size_bytes,
            "saved_at": saved_at,    # epoch seconds
            "is_best": (best_step is not None and step == best_step),
        })
    return {"list": out, "best_step": best_step, "steps_per_epoch": model_info.get("steps_per_epoch") or 0}


async def delete_checkpoint(model_id: int, step: int, commit_name: str = None) -> bool:
    """체크포인트(어댑터) 폴더 삭제 — 경로는 adapters_dir 봉쇄, step int 강제(인젝션 차단).
    라이브 학습본(commit_name 없음)은 학습/커밋 active 중 거부(trainer rotation 레이스 회피).
    커밋 스냅샷(commit_name)은 frozen(트레이너 미관여)이라 active-gate 불요(Phase 2-C)."""
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception("Error: not exist model")
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    model_root = os.path.dirname(PATH.JF_MODEL_LATEST_CHECKPOINT_PATH.format(
        STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"],
        MODEL_NAME=model_info["name"]))
    if commit_name:
        if "/" in commit_name or commit_name in (".", ".."):
            raise Exception("Error: invalid commit name")
        _, _commit_dir = _commit_checkpoints_dir(workspace_info["main_storage_name"], workspace_info["name"],
                                                 model_info["name"], commit_name)
        adapters_dir = os.path.join(_commit_dir, "adapters")
    else:
        # active(학습/커밋 진행) 중 삭제 차단 — trainer rotation 과 레이스 회피. scheduling 까지 포함(현재
        # FT 가 안 쓰지만 방어; error/done/stop 은 허용=정리 가능, 그래서 인라인 set 사용·KUBER_RUNNING_STATUS X).
        _active = (TYPE.KUBE_POD_STATUS_RUNNING, TYPE.KUBE_POD_STATUS_PENDING,
                   TYPE.KUBE_POD_STATUS_INSTALLING, TYPE.KUBE_POD_STATUS_SCHEDULING)
        if model_info.get("latest_fine_tuning_status") in _active \
           or model_info.get("commit_status") == TYPE.KUBE_POD_STATUS_RUNNING:
            raise Exception("Error: cannot delete checkpoint while training/commit is active")
        adapters_dir = os.path.join(model_root, "checkpoints", "adapters")
    target = os.path.join(adapters_dir, "checkpoint-{}".format(int(step)))    # int 강제 → 경로 인젝션 차단
    if not _is_under(target, adapters_dir):
        raise Exception("Error: invalid checkpoint path")
    if not await asyncio.to_thread(os.path.isdir, target):
        raise Exception("Error: checkpoint not found")
    await asyncio.to_thread(common.rm_rf, target)
    return True


async def _resolve_commit_name(model_id: int, commit_id: int) -> str:
    """commit_id → commit_name 해소 + commit 이 해당 model 소속인지 검증(교차참조 차단). Phase 2-C."""
    commit = await db_model.get_commit_model(commit_id=commit_id)
    if not commit or commit.get("model_id") != model_id:
        raise Exception("Error: commit not found for model")
    return commit["name"]


async def list_commit_checkpoints(model_id: int, commit_id: int) -> dict:
    """커밋(버전)에 귀속된 체크포인트 스냅샷 나열(Phase 2-C)."""
    commit_name = await _resolve_commit_name(model_id=model_id, commit_id=commit_id)
    return await list_checkpoints(model_id=model_id, commit_name=commit_name)


async def delete_commit_checkpoint(model_id: int, commit_id: int, step: int) -> bool:
    """커밋 스냅샷에서 체크포인트 삭제(Phase 2-C) — 커밋 frozen 이라 active-gate 불요."""
    commit_name = await _resolve_commit_name(model_id=model_id, commit_id=commit_id)
    return await delete_checkpoint(model_id=model_id, step=step, commit_name=commit_name)


async def promote_commit_checkpoint(model_id: int, commit_id: int, step: int, create_user_id: int) -> bool:
    """커밋의 특정 step 체크포인트를 새 버전으로 promote(Phase 2-C, "수동 best 적용").

    base 스냅샷 없이 LoRA 델타 산술(스파이크 검증, cat): 새 commit_model `<src>-step<step>` row 생성 →
    promote 잡(commit_models/<src> + adapters{best,target} → cat[-best,+target] merge → commit_models/<new>).
    비파괴(서빙 latest_checkpoint 미변경). 실패 시 row+폴더 롤백. commit_status RUNNING 중엔 거부."""
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception("Error: not exist model")
    if model_info.get("commit_status") == TYPE.KUBE_POD_STATUS_RUNNING:
        raise Exception("Error: commit/promote already running")
    commit = await db_model.get_commit_model(commit_id=commit_id)
    if not commit or commit.get("model_id") != model_id:
        raise Exception("Error: commit not found for model")
    src_commit_name = commit["name"]

    # 커밋 스냅샷에서 best/target step 검증.
    ck = await list_checkpoints(model_id=model_id, commit_name=src_commit_name)
    best_step = ck.get("best_step")
    steps = {c["step"] for c in ck.get("list", [])}
    if best_step is None:
        raise Exception("Error: 이 커밋엔 best 체크포인트가 없어 promote 할 수 없습니다")
    if int(best_step) not in steps:
        # trainer_state 가 가리키는 best 어댑터가 스냅샷에서 삭제됨 → 재머지 불가(엔진이 best adapter 로드 실패).
        raise Exception("Error: best 체크포인트 어댑터가 스냅샷에 없어 promote 할 수 없습니다")
    if int(step) not in steps:
        raise Exception("Error: target step 이 커밋 스냅샷에 없습니다")
    if int(step) == int(best_step):
        raise Exception("Error: 이미 best 인 체크포인트입니다")

    new_commit_name = "{}-step{}".format(src_commit_name, int(step))
    # create_commit_model 과 동일 allowlist(셸/경로 하드닝) — src + 접미사가 50자/charset 넘으면 거부.
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,50}', new_commit_name) or '..' in new_commit_name:
        raise Exception("Error: promote 커밋명 '{}'이 유효하지 않습니다({}자, 영문/숫자/._- 50자 이내). "
                        "원본 커밋명을 짧게 만들거나 step 을 확인하세요.".format(new_commit_name, len(new_commit_name)))
    if await db_model.check_commit_model_by_name(model_id=model_id, commit_name=new_commit_name):
        raise Exception("Error: 이미 promote 된 버전이 있습니다")

    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    new_commit_id = None
    try:
        new_commit_id = await db_model.create_commit_model(
            model_id=model_id, workspace_id=model_info["workspace_id"], create_user_id=create_user_id,
            fine_tuning_config=commit.get("fine_tuning_config") or "{}",
            commit_message="promote step {} (from '{}')".format(int(step), src_commit_name),
            name=new_commit_name, model_description=model_info["description"],
            steps_per_epoch=model_info["steps_per_epoch"])
        if not new_commit_id:
            return False
        res, message = await promote_model_helm(
            workspace_id=model_info["workspace_id"], model_id=model_id, model_name=model_info["name"],
            src_commit_name=src_commit_name, best_step=int(best_step), target_step=int(step),
            new_commit_name=new_commit_name)
        if res:
            await db_model.update_model_commit_status(commit_status=TYPE.KUBE_POD_STATUS_RUNNING,
                model_id=model_id, latest_commit_id=new_commit_id, commit_type=TYPE.COMMIT_TYPE_COMMIT)
            return res
        # 잡 런치 실패(False 반환) → 고아 row/폴더 롤백(throw 경로와 동일; 재시도 차단·목록 노출 방지, 리뷰 HIGH).
        await db_model.delete_commit_model(commit_model_id=new_commit_id)
        await delete_commit_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"], commit_name=new_commit_name)
        await delete_commit_checkpoints_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"], commit_name=new_commit_name)
        return False
    except Exception as e:
        if new_commit_id:
            await db_model.delete_commit_model(commit_model_id=new_commit_id)
            await delete_commit_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"], commit_name=new_commit_name)
            await delete_commit_checkpoints_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"], commit_name=new_commit_name)
        traceback.print_exc()
        return False


async def create_model(workspace_id : int, model_name : str, description : str, create_user_id : int, private : int, huggingface_model_id : str = None, \
    commit_model_id : int = None, huggingface_token : str = None, access : int = 0, users_id : List[int] = [], \
    training_type : str = 'internal', external_manifest_name : str = None, external_manifest_version : str = None,
    domain : str = None, load_type : str = None) -> bool:
    commit_model_info = {}
    model_id = None
    huggingface_git = None
    workspace_info = {}  # except 핸들러에서 미바인딩(NameError) 방지(리뷰 HIGH)
    try:
        # ── domain(3.5) 분류 → 학습 백엔드 라우팅. SDS=외부컨테이너(고정 manifest),
        # SDM/SDF=현재 비활성. 사용자는 domain 만 고르고 버전은 안 고른다 → 여기서
        # settings 상수로 manifest 바인딩을 해석(단일 지점, FE 미관여).
        if domain:
            domain = str(domain).strip().upper()
            if domain == 'SDS':
                training_type = 'external'
                external_manifest_name = settings.SDS_MANIFEST_NAME
                external_manifest_version = settings.SDS_MANIFEST_VERSION
            elif domain in ('SDM', 'SDF'):
                raise Exception(f"Error: domain '{domain}' is not yet supported")
            else:
                raise Exception(f"Error: unknown domain '{domain}'")
        # model_name 은 이후 create_model_helm 의 helm --set f-string(shell=True) + NFS 경로 세그먼트에
        # 그대로 들어간다. FE 우회 직접 API 호출로 `$(...)`·백틱 등을 이름에 넣으면 helm 잡 런치 파드(kube/helm
        # 자격증명)에서 RCE. 생성 시점에 차단(commit_name allowlist·C-1/C-2 와 동일 클래스). 영문/숫자/._- 1~50자.
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,50}', model_name or '') or '..' in (model_name or ''):
            raise Exception("Error: invalid model name (영문/숫자/._- 1~50자, '..' 불가)")
        # check duplicate model name
        if await db_model.check_model_by_model_name(model_name=model_name, workspace_id=workspace_id):
            raise Exception(f"Error: model name duplicated")

        workspace_info = await db_model.get_workspace_model(workspace_id=workspace_id)

        # ── External partner-container training model.
        # Metadata-only row: helm/serve/commit pipelines belong to the partner
        # pod (ETRI eva-vlm etc.), so the platform skips them here. The user
        # opens the model detail → 외부 학습 탭 → "학습 시작" 버튼 which calls
        # POST /api/external/jobs and then PATCH /models/{id}/external-job to
        # bind the resulting job_id back.
        if training_type == 'external':
            if not external_manifest_name or not external_manifest_version:
                raise Exception("Error: external_manifest_name/version required for external training_type")
            model_id = await db_model.create_model(
                workspace_id=workspace_id,
                name=model_name,
                create_user_id=create_user_id,
                description=description,
                huggingface_git='',  # NOT NULL column on legacy schema
                access=access,
                training_type='external',
                external_manifest_name=external_manifest_name,
                external_manifest_version=external_manifest_version,
                domain=domain,  # SDS 등(없으면 None=NULL). legacy 직접 manifest 선택은 domain 미전송.
            )
            if model_id and users_id:
                await db_model.create_model_user_list(model_id=model_id, user_list=users_id)
            return bool(model_id)

        # ── Multimodal(VLM) — 비전 인코더 + LLM 두 HF 모델. 텍스트 모델과 동일하게 생성 시
        # NFS 에 받아둠: 메타행 생성(load_type='multimodal', hf_id="{vision},{llm}") → compose_vlm
        # 잡(둘 다 다운로드 + LLaVA 조립, projector 자동생성) → NFS source/latest_checkpoint 적재
        # → 초기 커밋. FT 가 /model(=latest_checkpoint) 로 읽음. 조립=llm_model_download.py
        # compose_vlm 서브커맨드(FT 이미지=transformers 4.52.4).
        if (load_type or '').strip().lower() == 'multimodal':
            # 정확히 2개 모델 id("{vision},{llm}") 강제 — partition(첫 콤마)은 "a,b,c" 를
            # 통과시켜 llm_id="b,c" 로 오파싱하므로 split 로 part 개수까지 검증(리뷰 MED).
            parts = [p.strip() for p in (huggingface_model_id or '').split(',')]
            if len(parts) != 2 or not all(parts):
                raise Exception("Error: multimodal requires huggingface_model_id='{vision},{llm}' (정확히 2개)")
            vision_id, llm_id = parts
            # 셸/helm 인젝션 차단 — HF repo id 는 'org/name'(안전 문자만)만 허용(리뷰 CRITICAL).
            # 이후 helm --set / bash -c 로 보간되므로 $()·백틱·공백 등 메타문자 원천 차단.
            _hf_id_re = re.compile(r'^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$')
            if not (_hf_id_re.match(vision_id) and _hf_id_re.match(llm_id)):
                raise Exception("Error: invalid HF model id — expected 'org/name' for each of {vision},{llm}")
            normalized_hf_id = f"{vision_id},{llm_id}"
            # 토큰 resolve — 단일-HF 경로와 동형. public=회사 토큰, private=복호화.
            # (Phase 3 base pull 대비 저장. 슬롯별 private 토큰 분리는 후속 — FE 가 병합 전송.)
            if not private:
                resolved_token = settings.HUGGINGFACE_TOKEN
            else:
                resolved_token = front_cipher.decrypt(huggingface_token)
            model_id = await db_model.create_model(
                workspace_id=workspace_id,
                name=model_name,
                create_user_id=create_user_id,
                huggingface_model_id=normalized_hf_id,  # "{vision},{llm}" (정규화)
                huggingface_token=resolved_token,
                huggingface_git='',  # NOT NULL — 실제 git/다운로드는 학습 시점 해석
                description=description,
                access=access,
                load_type='multimodal',
            )
            if model_id and users_id:
                await db_model.create_model_user_list(model_id=model_id, user_list=users_id)
            # 텍스트 흐름과 동일: 폴더 생성 → compose_vlm 잡(비전+LLM→LLaVA) → 초기 커밋.
            await create_model_folder(storage_name=workspace_info["main_storage_name"],
                                      workspace_name=workspace_info["name"], model_name=model_name)
            res, message = await create_model_helm(
                workspace_id=workspace_id, model_id=model_id, model_name=model_name,
                huggingface_model_id=normalized_hf_id, huggingface_token=resolved_token,
                compose_vlm=True)
            if res == False:
                import sys
                print(f"Error: {message}", file=sys.stderr)
                raise Exception
            commit_id = await db_model.create_commit_model(
                model_id=model_id, create_user_id=create_user_id, workspace_id=workspace_id,
                fine_tuning_config=FineTuningConfig().model_dump_json(), commit_message="",
                name=TYPE.MODEL_FIRST_COMMIT_NAME, model_description=description)
            await db_model.update_model_commit_status(
                commit_status=TYPE.KUBE_POD_STATUS_RUNNING, model_id=model_id,
                latest_commit_id=commit_id, commit_type=TYPE.COMMIT_TYPE_DOWNLOAD)
            return bool(model_id)

        if huggingface_model_id: # huggingface model download
            # repo-id 형식 검증(보안 M-3) — 멀티모달 경로와 동형이되, 단일 HF id 는 'name' 또는
            # 'org/name' 둘 다 유효(예: gpt2 / Qwen/Qwen2.5)하므로 슬래시는 선택. 셸/경로 인젝션 방어.
            if not re.fullmatch(r'[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)?', huggingface_model_id or ''):
                raise Exception(f"Error: invalid huggingface_model_id '{huggingface_model_id}'")
            # 유효한 token인지 확인하는 작업 필요
            if not private: # 퍼블릭일 경우 회사 계정을 사용
                huggingface_token = settings.HUGGINGFACE_TOKEN
            else:
                huggingface_token = front_cipher.decrypt(huggingface_token)
                # huggingface_token = huggingface_token
            if await check_model_access(model_id=huggingface_model_id, token=huggingface_token, model_create=True):
                huggingface_git = TYPE.HUGGINGFACE_MODEL_GIT.format(MODEL_ID=huggingface_model_id)
                model_id = await db_model.create_model(workspace_id=workspace_id, name=model_name, create_user_id=create_user_id, \
                    huggingface_model_id=huggingface_model_id, huggingface_token=huggingface_token, description=description, huggingface_git=huggingface_git, access=access)
            else:
                raise Exception(f"Error: Cannot access the model '{huggingface_model_id}' with the provided token.")
            
        elif commit_model_id: # workspace commit model copy 
            commit_model_info = await db_model.get_commit_model(commit_id=commit_model_id)
            huggingface_git = commit_model_info["huggingface_git"]
            model_id = await db_model.create_model(workspace_id=workspace_id, name=model_name, create_user_id=create_user_id, latest_fine_tuning_config=commit_model_info["fine_tuning_config"], \
                commit_model_name="{}/{}".format(commit_model_info["model_name"], commit_model_info["name"]) , description=description, huggingface_git=huggingface_git, huggingface_model_id=commit_model_info["huggingface_model_id"], access=access)
            
        if model_id:
            # 사용자 추가 
            # print(users_id)
            if users_id:
                await db_model.create_model_user_list(model_id=model_id, user_list=users_id)
            # mkdir commit_model, source_model
            await create_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_name)
            # model copy or download
            # create helm 
            res , message = await create_model_helm(workspace_id=workspace_id, model_id=model_id, model_name=model_name, commit_model=commit_model_info.get("model_name",None), \
                commit_name=commit_model_info.get("name", None), huggingface_model_id=huggingface_model_id, huggingface_token=huggingface_token)
            if res == False:
                import sys
                print(f"Error: {message}", file=sys.stderr)
                raise Exception
            # create commit model 
            commit_id = await db_model.create_commit_model(model_id=model_id, create_user_id=create_user_id, workspace_id=workspace_id, fine_tuning_config=FineTuningConfig().model_dump_json(),
                                               commit_message="", name=TYPE.MODEL_FIRST_COMMIT_NAME, model_description=description)
            await db_model.update_model_commit_status(commit_status=TYPE.KUBE_POD_STATUS_RUNNING, model_id=model_id, latest_commit_id=commit_id, commit_type=TYPE.COMMIT_TYPE_DOWNLOAD)
            
            
            return res
        return False
    except Exception as e:
        traceback.print_exc()
        if model_id:
            await db_model.delete_model(model_id=model_id)
            # rm model dir
            await delete_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_name)
        return False

async def get_model_summary(model_id : int) -> dict:
    """Lightweight single-model fetch for ModelDetailPage's redirect logic.

    Returns the raw db_model.get_model row (id/name/training_type/external_*
    /huggingface_*). The frontend uses training_type to decide whether to
    redirect into the 외부 학습 탭 or the default Information 탭.
    """
    return await db_model.get_model(model_id=model_id)


async def bind_external_job(model_id : int, external_job_id : str) -> bool:
    """Persist the partner-container job_id onto the model row.

    Called right after the frontend's "학습 시작" button triggers
    POST /api/external/jobs and the BFF returns a job_id. The detail page
    reads model.external_job_id to drive the existing SSE/log endpoints.
    """
    await db_model.update_model_external_job(model_id=model_id, external_job_id=external_job_id)
    return True


async def quantize_model(model_id : int, target_quant : str,
                         target_device : Optional[str] = None,
                         prune : bool = False) -> dict:
    """학습 완료 모델을 GGUF 로 양자화하는 convert job 을 띄운다 (SP-4 / 3.9).

    Why
    ---
    ⑫ 양자화 + ⑬ 포팅은 `job_type=convert` 외부 컨테이너에 위임한다
    (fb_porting 신규 서비스 회피, SP-4 J-1). 명시 버튼 트리거 — auto-chain 아님.

    How
    ---
    merged 모델(`models/<name>/latest_checkpoint`)을 컨테이너 `/model` 로 주입해야
    하는데, 이는 lifecycle 의 reserved param `_base_model={"name": ...}` 가
    `inputs.base_model.name` 으로 들어올려지면 pod chart 가 자동 마운트한다
    (SP-Ext launch/lifecycle 재사용 — fb_external_container 코드 변경 0).
    convert 는 가중치 commit 이 아니므로 auto-commit(train/batch) 게이트와
    자연히 분리된다 (SP-4 §4.3).

    결과 포팅 패키지(GGUF + inference.py + run.sh + config.json)는
    `jobs/<job_id>/output/` 에 떨어지고, FE 는 반환된 job_id 로 기존
    `GET /api/external/jobs/{job_id}` 폴링 + 패키지 다운로드를 한다.
    """
    from external.proxy import ExternalContainerClient, ExternalContainerError
    import httpx

    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    model_name = model_info["name"]
    workspace_id = int(model_info["workspace_id"])

    # reserved key `_base_model` → lifecycle 가 /model = models/<name>/latest_checkpoint
    # 마운트. target_quant/model_name 은 convert 컨테이너가 /input/params.json 으로 수신.
    params = {
        "_base_model": {"name": model_name},
        "target_quant": target_quant,
        "model_name": model_name,
    }
    if target_device:
        params["target_device"] = target_device
    # 4.7 프루닝 placeholder — 실제 프루닝은 엣지 convert 컨테이너 도착 시. 지금은
    # 계약(params 전달 + lineage 기록)만 둔다. mock-convert 는 이 키를 무시한다.
    if prune:
        params["prune"] = True

    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            client = ExternalContainerClient(
                base_url=settings.FB_EXTERNAL_CONTAINER_URL,
                client=http,
            )
            raw = await client.start_job(
                manifest_name=settings.CONVERT_MANIFEST_NAME,
                manifest_version=settings.CONVERT_MANIFEST_VERSION,
                workspace_id=workspace_id,
                params=params,
            )
    except ExternalContainerError as e:
        raise Exception(f"convert job launch failed ({e.status_code}): {e}") from e

    # start_job 응답은 fb_external_container 의 {"job_id": ...} (202). envelope 변종 방어.
    job_id = raw.get("job_id") or (raw.get("result") or {}).get("job_id")
    if not job_id:
        # job_id 없으면 launch 실패로 간주 — status=1 성공으로 위장하면 FE 가
        # /jobs/null 을 무한 폴링한다. 명시적 실패로 올린다.
        raise Exception(f"convert job launched but no job_id in response: {raw!r}")

    # 4.6 lineage — 양자화 시도 기록(launch 시점, status=running). 완료 시
    # list_quantize_package 가 gguf 경로로 마감. DB 실패가 launch 를 막지 않도록 guard.
    if job_id:
        try:
            await db_model.insert_quantize_lineage(
                source_model_id=model_id, workspace_id=workspace_id,
                job_str_id=job_id, quantization_type=target_quant,
                target_device=target_device, prune=prune,
            )
        except Exception:
            traceback.print_exc()

    return {
        "model_id": model_id,
        "model_name": model_name,
        "workspace_id": workspace_id,
        "target_quant": target_quant,
        "target_device": target_device,
        "prune": prune,
        "manifest_name": settings.CONVERT_MANIFEST_NAME,
        "manifest_version": settings.CONVERT_MANIFEST_VERSION,
        "job_id": job_id,
    }


# convert job_id 는 외부 컨테이너가 발급(uuid/hex). 경로 조작 방지: 형식 검증 + base 이탈 차단.
_QUANTIZE_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


async def _quantize_output_dir(model_id: int, job_id: str) -> str:
    """convert job 의 포팅 패키지 디렉토리(`jobs/<job_id>/output`)를 안전하게 해석.

    model_id → workspace 로 storage 경로를 잡고(commit_external_artifacts 와 동일
    패턴), job_id 는 화이트리스트 정규식 + commonpath 로 base(jobs) 이탈을 막는다.
    """
    if not job_id or not _QUANTIZE_JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    ws = await db_model.get_workspace_model(workspace_id=int(model_info["workspace_id"]))
    if not ws:
        raise Exception(f"workspace for model {model_id} not found")
    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
    )
    jobs_base = os.path.realpath(os.path.join(main_root, "jobs"))
    output_dir = os.path.join(jobs_base, job_id, "output")
    if os.path.commonpath([os.path.realpath(output_dir), jobs_base]) != jobs_base:
        raise ValueError("output path escapes jobs base")
    return output_dir


async def list_quantize_package(model_id: int, job_id: str) -> dict:
    """포팅 패키지 파일 목록(name/bytes). 미완료 시 ready=False.

    패키지가 준비되면 4.6 lineage 를 lazy 마감(status=completed + gguf 경로).
    FE 가 완료 시 이 호출을 하므로 별도 완료 hook 없이 idempotent 하게 기록된다.
    """
    output_dir = await _quantize_output_dir(model_id, job_id)
    if not os.path.isdir(output_dir):
        return {"job_id": job_id, "files": [], "ready": False}
    out_real = os.path.realpath(output_dir)
    files = []
    gguf_name = None
    for fn in sorted(os.listdir(output_dir)):
        fp = os.path.join(output_dir, fn)
        # 심링크가 output_dir 밖을 가리키면 제외(악의적/손상 산출물이 임의 파일을
        # listing/zip 으로 유출하는 것 차단).
        if os.path.commonpath([os.path.realpath(fp), out_real]) != out_real:
            continue
        if os.path.isfile(fp):
            files.append({"name": fn, "bytes": os.path.getsize(fp)})
            if fn.endswith(".gguf"):
                gguf_name = fn
    ready = len(files) > 0
    if ready:
        try:
            gguf_path = f"jobs/{job_id}/output/{gguf_name}" if gguf_name else f"jobs/{job_id}/output"
            await db_model.complete_quantize_lineage(
                job_str_id=job_id, gguf_path=gguf_path, source_model_id=model_id)
        except Exception:
            traceback.print_exc()
    return {"job_id": job_id, "files": files, "ready": ready}


async def mark_quantize_lineage(model_id: int, job_id: str, status: str) -> dict:
    """convert 실패/취소를 lineage 에 반영 — 4.6 정확성. FE 가 terminal(failed/cancelled)
    감지 시 호출(완료는 list_quantize_package 가 lazy 마감). 화이트리스트 검증 +
    source_model_id 바인딩(다른 모델 job 마킹 차단)."""
    if status not in ("failed", "cancelled"):
        raise ValueError(f"invalid lineage status: {status!r}")
    await db_model.update_quantize_lineage_status(
        job_str_id=job_id, status=status, source_model_id=model_id)
    return {"job_id": job_id, "status": status}


async def list_quantize_lineage(model_id: int) -> dict:
    """원본 모델의 양자화 이력(원본+양자화 파라미터) 조회 — 4.6."""
    rows = await db_model.list_quantize_lineage(source_model_id=model_id)
    return {
        "model_id": model_id,
        "lineage": [
            {
                "id": r["id"],
                "job_id": r["job_str_id"],
                "quantization_type": r["quantization_type"],
                "target_device": r["target_device"],
                "prune": bool(r["prune"]),
                "gguf_path": r["gguf_path"],
                "status": r["status"],
                "create_datetime": r["create_datetime"],
            }
            for r in rows
        ],
    }


# 4.5 타겟 디바이스 → 권장 양자화 매핑. device(ORIN/RPi+Hailo/PC) → 권장 Q.
# 비트수↓ = 용량↓·디바이스 친화↑·정확도↓. (SP-6/Runtime edge spec 정합)
_DEVICE_QUANT_MAP = [
    {"key": "jetson-orin", "label": "Jetson Orin", "recommended": "q4",
     "reason": "엣지 GPU·제한 메모리 — 작은 용량 우선"},
    {"key": "rpi-hailo", "label": "Raspberry Pi + Hailo", "recommended": "q4",
     "reason": "초경량 엣지 — 최소 용량"},
    {"key": "rtx-3090", "label": "PC (RTX/GPU)", "recommended": "q6",
     "reason": "여유 메모리 — 정확도 우선"},
    {"key": "server", "label": "Server", "recommended": "q6",
     "reason": "충분한 메모리 — 정확도 우선"},
]


def get_quantize_device_recommendations() -> dict:
    """device→권장 Q 매핑 (FE 배지/자동제안용). 알 수 없는 device 는 q5 기본."""
    return {"default": "q5", "devices": _DEVICE_QUANT_MAP}


# ── SP-5 자동평가 (v0.4 3.8) ────────────────────────────────────────────────

# params 로 들어온 metric_set 정제용 화이트리스트(주입/오타 방지).
_EVAL_METRICS = ("bleu", "rouge", "perplexity")
# evaluate job_id 는 외부 컨테이너 발급(uuid/hex). 경로조작 방지: 형식 검증.
_EVAL_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# 모델/데이터셋 이름은 pod subPath(/dataset/<name>, models/<name>/...) 의 단일 segment 로
# 들어가므로 path 조작 문자를 거부(잘못된 마운트/이탈 방지). 플랫폼 생성 이름은 통과.
_EVAL_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


async def evaluate_model(model_id: int, dataset_id: int,
                         metric_set: Optional[List[str]] = None,
                         max_samples: Optional[int] = None) -> dict:
    """학습 완료 모델을 평가 데이터셋으로 채점하는 evaluate job 을 띄운다 (SP-5 / 3.8).

    convert(SP-4)와 동형 — `job_type=evaluate` 외부 컨테이너에 위임(fb_evaluate 신규
    서비스 회피). 명시 버튼 트리거. reserved `_base_model`→/model(평가 대상),
    `_dataset`→/dataset/<name>(평가셋). 결과 metrics.json 은 jobs/<job_id>/output/
    에 떨어지고 get_eval_result 가 lazy 로 eval_result 를 마감(quantize 패키지와
    동형 — fb_external_container 코드 변경 0).
    """
    from external.proxy import ExternalContainerClient, ExternalContainerError
    import httpx

    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    model_name = model_info["name"]
    workspace_id = int(model_info["workspace_id"])

    dataset_info = await db_model.get_dataset_model(dataset_id=dataset_id)
    if not dataset_info:
        raise Exception(f"dataset {dataset_id} not found")
    # 평가셋이 모델과 같은 워크스페이스인지 — 교차 워크스페이스 마운트 차단(ACL).
    if int(dataset_info["workspace_id"]) != workspace_id:
        raise Exception("dataset and model belong to different workspaces")
    # name 은 pod subPath 의 단일 segment(/dataset/<name>, models/<name>) 로 들어가므로
    # path 조작 문자를 거부(잘못된 경로 마운트/이탈 방지). access 는 traversal 만 차단.
    ds_name = str(dataset_info["name"])
    if not _EVAL_SAFE_SEGMENT_RE.match(ds_name) or not _EVAL_SAFE_SEGMENT_RE.match(model_name):
        raise Exception("model/dataset name has unsafe characters for container mount")
    if ".." in str(dataset_info.get("access") or ""):
        raise Exception("dataset access path is unsafe")

    metrics = [m for m in (metric_set or list(_EVAL_METRICS)) if m in _EVAL_METRICS] or list(_EVAL_METRICS)
    metric_csv = ",".join(metrics)

    # reserved key → lifecycle 가 /model + /dataset/<name> 마운트.
    # metric_set/max_samples 는 evaluate 컨테이너가 /input/params.json 으로 수신.
    params = {
        "_base_model": {"name": model_name},
        "_dataset": {"name": dataset_info["name"], "access": dataset_info["access"]},
        "metric_set": metrics,
    }
    if max_samples:
        params["max_samples"] = int(max_samples)

    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            client = ExternalContainerClient(
                base_url=settings.FB_EXTERNAL_CONTAINER_URL, client=http)
            raw = await client.start_job(
                manifest_name=settings.EVALUATE_MANIFEST_NAME,
                manifest_version=settings.EVALUATE_MANIFEST_VERSION,
                workspace_id=workspace_id, params=params)
    except ExternalContainerError as e:
        raise Exception(f"evaluate job launch failed ({e.status_code}): {e}") from e

    job_id = raw.get("job_id") or (raw.get("result") or {}).get("job_id")
    if not job_id:
        # job_id 없으면 launch 실패로 간주(FE 가 /jobs/null 무한 폴링 방지).
        # raw 응답(내부 URL/스택 가능)을 API 로 누출하지 않고 서버 로그로만.
        print(f"evaluate launch: no job_id in response: {raw!r}")
        raise Exception("evaluate job launched but no job_id in response")

    # 평가 시도 기록(launch 시점, status=running). 완료 시 get_eval_result 가
    # metrics 로 마감. DB 실패가 launch 를 막지 않도록 guard.
    try:
        await db_model.insert_eval_result(
            source_model_id=model_id, workspace_id=workspace_id,
            job_str_id=job_id, dataset_id=dataset_id,
            dataset_name=dataset_info["name"], metric_set=metric_csv)
    except Exception:
        traceback.print_exc()

    return {
        "model_id": model_id, "model_name": model_name, "workspace_id": workspace_id,
        "dataset_id": dataset_id, "dataset_name": dataset_info["name"],
        "metric_set": metrics,
        "manifest_name": settings.EVALUATE_MANIFEST_NAME,
        "manifest_version": settings.EVALUATE_MANIFEST_VERSION,
        "job_id": job_id,
    }


async def _eval_output_dir(model_id: int, job_id: str) -> str:
    """evaluate job 의 결과 디렉토리(jobs/<job_id>/output)를 안전 해석(_quantize_output_dir 동형)."""
    if not job_id or not _EVAL_JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    ws = await db_model.get_workspace_model(workspace_id=int(model_info["workspace_id"]))
    if not ws:
        raise Exception(f"workspace for model {model_id} not found")
    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
    )
    jobs_base = os.path.realpath(os.path.join(main_root, "jobs"))
    output_dir = os.path.join(jobs_base, job_id, "output")
    if os.path.commonpath([os.path.realpath(output_dir), jobs_base]) != jobs_base:
        raise ValueError("output path escapes jobs base")
    return output_dir


async def get_eval_result(model_id: int, job_id: str) -> dict:
    """평가 job 의 metrics.json 을 읽어 반환 + 완료 시 eval_result lazy 마감.

    FE 가 폴링하다 ready=True 면 eval_result.status=completed + metrics 기록(별도
    완료 hook 없이 idempotent). metrics.json 미존재(미완료/실패)면 ready=False.
    """
    output_dir = await _eval_output_dir(model_id, job_id)
    out_real = os.path.realpath(output_dir)
    metrics_path = os.path.join(output_dir, "metrics.json")
    # 심링크가 output_dir 밖을 가리키면 거부(임의 파일 읽기 차단).
    if os.path.commonpath([os.path.realpath(metrics_path), out_real]) != out_real:
        raise ValueError("metrics path escapes output dir")
    if not os.path.isfile(metrics_path):
        return {"job_id": job_id, "metrics": None, "ready": False}
    # 크기 가드 — metrics dict 은 수 KB. NFS 산출물이라 (손상/악의적) 대용량 파일을
    # json.load 로 통째로 메모리에 올리면 OOM + DB JSON 컬럼 폭증. 1MB 초과 거부.
    try:
        if os.path.getsize(metrics_path) > 1 * 1024 * 1024:
            raise ValueError(f"metrics.json too large for job {job_id}")
    except OSError:
        return {"job_id": job_id, "metrics": None, "ready": False}
    try:
        with open(metrics_path, encoding="utf-8") as f:
            metrics = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"job_id": job_id, "metrics": None, "ready": False}
    try:
        await db_model.complete_eval_result(
            job_str_id=job_id, metrics_json=json.dumps(metrics), source_model_id=model_id)
    except Exception:
        traceback.print_exc()
    return {"job_id": job_id, "metrics": metrics, "ready": True}


async def mark_eval_status(model_id: int, job_id: str, status: str) -> dict:
    """평가 실패/취소를 eval_result 에 반영(완료는 get_eval_result 가 lazy 마감).
    화이트리스트 검증 + source_model_id 바인딩(다른 모델 job 마킹 차단)."""
    if status not in ("failed", "cancelled"):
        raise ValueError(f"invalid eval status: {status!r}")
    # get_eval_result 와 대칭으로 job_id 형식 검증(과대 길이/비정상 입력 차단).
    if not job_id or not _EVAL_JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    await db_model.update_eval_result_status(
        job_str_id=job_id, status=status, source_model_id=model_id)
    return {"job_id": job_id, "status": status}


async def list_eval_results(model_id: int) -> dict:
    """모델의 평가 이력 + 메트릭별 best 마킹(비교표 ⑪). SDM 도메인 키(AUC/Dice 등)는
    자유 dict 그대로 노출(고정 스키마 X — normalize/dto 자유 result 정합, 4.6).
    벤치마크(llm_evaluation) 런도 동일 eval_result 에 누적 → 공용 빌더로 nested averages
    평탄화 포함(§14.12, llm_evaluation 과 동일 shape)."""
    rows = await db_model.list_eval_results(source_model_id=model_id)
    return {"model_id": model_id, **db_model.build_eval_comparison(rows)}


async def get_quantize_package_path(model_id: int, job_id: str,
                                    filename: Optional[str] = None) -> Tuple[str, str, str]:
    """다운로드용 (절대경로, 다운로드 파일명, media_type) 반환.

    filename 지정 → 해당 파일 1개(FileResponse 가 대용량 gguf 도 stream).
    filename 생략 → 패키지 전체 zip(ZIP_STORED — gguf 는 이미 압축돼 무의미).
    호출측이 zip 임시파일을 전송 후 삭제(BackgroundTask)한다.
    """
    import zipfile
    import tempfile

    output_dir = await _quantize_output_dir(model_id, job_id)
    if not os.path.isdir(output_dir):
        raise Exception("quantize package not found (convert job not completed?)")
    out_real = os.path.realpath(output_dir)

    if filename:
        if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
            raise ValueError(f"invalid filename: {filename!r}")
        fp = os.path.realpath(os.path.join(output_dir, filename))
        if os.path.commonpath([fp, out_real]) != out_real:
            raise ValueError("file path escapes package dir")
        if not os.path.isfile(fp):
            raise Exception(f"file not found in package: {filename}")
        return fp, filename, "application/octet-stream"

    model_info = await db_model.get_model(model_id=model_id)
    model_name = (model_info or {}).get("name", "model")
    # 요청별 unique 임시 zip (동시 다운로드가 같은 파일을 덮어쓰지/지우지 않게).
    fd, tmp_zip = tempfile.mkstemp(prefix=f"quantize-{model_id}-{job_id[:8]}-", suffix=".zip")
    os.close(fd)

    def _build_zip() -> None:
        # ZIP_STORED — gguf 는 이미 압축돼 무의미. 심링크 escape 제외.
        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_STORED) as zf:
            for fn in sorted(os.listdir(output_dir)):
                fp = os.path.join(output_dir, fn)
                if os.path.commonpath([os.path.realpath(fp), out_real]) != out_real:
                    continue
                if os.path.isfile(fp):
                    zf.write(fp, arcname=fn)

    # 대용량 gguf zip 은 이벤트루프 블로킹 → thread 로.
    await asyncio.to_thread(_build_zip)
    return tmp_zip, f"{model_name}-{job_id[:8]}-package.zip", "application/zip"


async def commit_external_artifacts(model_id : int, job_id : str,
                                    output_subdir : str,
                                    partner_metadata : dict = None,
                                    commit_name : str = None,
                                    commit_message : str = None) -> dict:
    """External 학습 종료 후 결과물을 platform 의 commit_model 패턴에 통합한다.

    Why
    ---
    Internal LLM 학습은 model_helm + commit_model row 를 자동 생성하지만,
    external (협력기관 컨테이너) 학습은 partner pod 의 /output/<ckpt> 에 결과를
    남기고 끝낸다. operator UX 통일을 위해 그 결과를 internal 과 동일한 layout
    (`workspace/models/<external_name>/commit_models/<commit>/`) 으로 옮기고
    `commit_model` 테이블 row 를 만들어 frontend Commit List 탭이 자동 표시되게.

    Steps
    -----
    1. model row 조회 + training_type='external' 검증
    2. src : `JF_MAIN_STORAGE_PATH/jobs/<job_id>/output/<output_subdir>/`
       dst : `JF_MAIN_MODEL_PATH/commit_models/<commit_name>/`
       (parent mkdir + shutil.move)
    3. `commit_model` row insert (fine_tuning_config = partner_metadata json)
    4. `model.latest_commit_id` update

    fb_external_container 의 JobTracker terminal=COMPLETED hook 에서 호출된다.
    수동 호출도 가능 (검증용).
    """
    import shutil
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    if (model_info.get("training_type") or "internal") != "external":
        raise Exception(f"model {model_id} is not training_type='external'")

    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    storage_name = workspace_info["main_storage_name"]
    workspace_name = workspace_info["name"]

    # commit_name: 사용자 지정 또는 job_id 앞 8자 + output_subdir 조합
    if not commit_name:
        # suffix: random job_id 대신 timestamp — 시간 순 자연 정렬 + 가독성.
        # 동일 output_subdir 의 동시 학습은 운영상 거의 없으니 sec 단위로 충분.
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        commit_name = f"{output_subdir}-{ts}"

    # NFS path resolve (llm_model pod 안 mount = /jf-data/<storage>/main/<workspace>)
    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
        STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name,
    )
    src_dir = os.path.join(main_root, "jobs", job_id, "output", output_subdir)
    model_root = PATH.JF_MAIN_MODEL_PATH.format(
        STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name,
        MODEL_NAME=model_info["name"],
    )
    commit_dir = os.path.join(model_root, "commit_models", commit_name)

    # 경로조작 방지 — job_id/output_subdir/commit_name 에 ../ 절대경로가 섞이면
    # shutil.move 가 다른 워크스페이스 디렉토리를 이동(교차테넌트 유출/파괴). 화이트리스트
    # + commonpath 로 jobs/commit_models 베이스 이탈 차단.
    if not job_id or not _QUANTIZE_JOB_ID_RE.match(job_id):
        raise Exception(f"invalid job_id: {job_id!r}")
    for _seg, _label in ((output_subdir, "output_subdir"), (commit_name, "commit_name")):
        if not _seg or "/" in _seg or "\\" in _seg or _seg in (".", ".."):
            raise Exception(f"invalid {_label}: {_seg!r}")
    _jobs_base = os.path.realpath(os.path.join(main_root, "jobs"))
    _commits_base = os.path.realpath(os.path.join(model_root, "commit_models"))
    if os.path.commonpath([os.path.realpath(src_dir), _jobs_base]) != _jobs_base:
        raise Exception("source path escapes jobs base")
    if os.path.commonpath([os.path.realpath(commit_dir), _commits_base]) != _commits_base:
        raise Exception("commit path escapes commit_models base")

    if not os.path.exists(src_dir):
        raise Exception(f"source artifacts not found at {src_dir}")
    if os.path.exists(commit_dir):
        raise Exception(f"commit dir already exists: {commit_dir}")

    # parent dirs (models/<name>/commit_models/) 가 외부 모델은 처음엔 없을 수 있다.
    os.makedirs(os.path.dirname(commit_dir), exist_ok=True)
    shutil.move(src_dir, commit_dir)

    # fine_tuning_config 에 partner metadata 보존 (manifest 의 partner-specific
    # 구조를 그대로 JSON 으로 — internal LLM 의 FineTuningConfig 와 schema 다르지만
    # frontend Commit List 탭은 read-only 라 호환).
    ft_config_json = json.dumps(partner_metadata or {}, ensure_ascii=False)

    commit_id = await db_model.create_commit_model(
        name=commit_name,
        model_id=model_id,
        workspace_id=model_info["workspace_id"],
        create_user_id=model_info["create_user_id"],
        fine_tuning_config=ft_config_json,
        commit_message=(commit_message or f"external training {job_id[:8]}"),
        model_description=(model_info.get("description") or ""),
    )

    # update model 의 latest_commit_id (model.update_model_commit_id 사용)
    await db_model.update_model_commit_id(latest_commit_id=commit_id, model_id=model_id)

    return {
        "commit_id": commit_id,
        "commit_name": commit_name,
        "commit_dir": commit_dir,
        "src_dir": src_dir,
    }


# ── 3.6 Custom 모델: by-reference 체크포인트 ingestion (런타임-바운드) ──────────
# 기관(예: 에이브노틱스)이 Nexus/HF 에 올린 커스텀 체크포인트를 레퍼런스로 당겨와
# 검증 후 commit_models 에 머티리얼라이즈한다. **사용자 파일 업로드 X(운영자 매개)** —
# 플랫폼 no-code/'정해진 모델만' 본질 유지. commit_external_artifacts 와 동일 layout
# 으로 떨어져 이후 eval(SP-5)/quantize(SP-4)/edge-deploy(SP-6/8) 가 그대로 동작.
# 1차 타깃 런타임 = EVA infer 호환(LoRA adapter + projector). 범용 loader 는 후속.
_CKPT_REF_TYPES = ("hf", "url")
_CKPT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
# EVA 로더 계약 — 각 그룹에서 하나라도 없으면 EVA 가 로드 못 함 → 등록 거부(controlled).
_EVA_REQUIRED_GROUPS = (
    ("adapter_config.json",),
    ("adapter_model.safetensors", "adapter_model.bin", "pytorch_model.bin"),
)


def _validate_eva_checkpoint_layout(root: str) -> None:
    """EVA infer 로더가 기대하는 최소 아티팩트 존재 검증. 미충족 시 예외(등록 거부)."""
    present = set(os.listdir(root)) if os.path.isdir(root) else set()
    missing = [
        " | ".join(group)
        for group in _EVA_REQUIRED_GROUPS
        if not any(f in present for f in group)
    ]
    if missing:
        raise Exception(
            "custom checkpoint does not match EVA loader contract; "
            f"missing required artifact(s): {missing}; found={sorted(present)[:20]}"
        )


# 리소스/DoS 가드 (untrusted 아티팩트). 운영 정책에 맞게 조정 가능.
_MAX_INGEST_BYTES = 50 * 1024 ** 3      # 단일 ingestion 총량 상한(NFS 보호)
_MAX_ARCHIVE_FILES = 50000              # decompression-bomb(파일수) 가드
# EVA 가 로드하는 파일만 받도록 HF allow_patterns — 불필요 대용량 동반파일 차단.
_EVA_ALLOW_PATTERNS = ["*.json", "*.safetensors", "*.bin", "*.model", "*.txt", "projector*", "*.py"]


def _check_pull_url_safe(url: str) -> None:
    """SSRF 가드 — http/https 만 허용 + 호스트가 사설/루프백/링크로컬/메타데이터/
    예약 IP 로 해석되면 거부(DNS 해석 후 검사). admin-gated 이나 심층방어."""
    import ipaddress, socket
    from urllib.parse import urlparse
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise Exception(f"url scheme not allowed: {p.scheme!r} (http/https only)")
    host = p.hostname or ""
    if not host:
        raise Exception("url has no host")
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80))
    except Exception:
        raise Exception(f"cannot resolve url host: {host!r}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise Exception(f"url resolves to blocked address {ip} (SSRF guard)")


def _sanitize_ref_for_storage(ref: str, ref_type: str) -> str:
    """provenance 저장용 ref 정제 — URL 의 userinfo(creds) + query(서명토큰) 제거."""
    if ref_type != "url":
        return ref
    from urllib.parse import urlparse, urlunparse
    try:
        p = urlparse(ref)
        netloc = p.hostname or ""
        if p.port:
            netloc += f":{p.port}"
        return urlunparse((p.scheme, netloc, p.path, "", "", ""))
    except Exception:
        return ref


def _safe_extract_archive(archive_path: str, dest: str) -> None:
    """Zip-slip/Tar-slip + decompression-bomb 방지 추출 — untrusted 아카이브.
    모든 멤버(디렉터리 포함) 경로가 dest 안에 머무는지 검증 + 절대경로/`..`/링크/
    비정규 파일 거부 + 압축해제 총량·파일수 상한. (shutil.unpack_archive 사용 금지.)"""
    import tarfile, zipfile
    dest_real = os.path.realpath(dest)

    def _within(name: str) -> bool:
        target = os.path.realpath(os.path.join(dest, name))
        return target == dest_real or target.startswith(dest_real + os.sep)

    def _check_name(name: str, label: str) -> None:
        if os.path.isabs(name) or ".." in name.replace("\\", "/").split("/") or not _within(name):
            raise Exception(f"unsafe archive member ({label}): {name!r}")

    if archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            infos = zf.infolist()
            if len(infos) > _MAX_ARCHIVE_FILES:
                raise Exception("archive has too many entries (decompression-bomb guard)")
            total = 0
            for zi in infos:
                _check_name(zi.filename, "zip-slip")  # 디렉터리 엔트리도 검사
                total += zi.file_size
                if total > _MAX_INGEST_BYTES:
                    raise Exception("archive uncompressed size exceeds limit (bomb guard)")
            zf.extractall(dest)
    else:
        with tarfile.open(archive_path) as tf:
            members = tf.getmembers()
            if len(members) > _MAX_ARCHIVE_FILES:
                raise Exception("archive has too many entries (decompression-bomb guard)")
            total = 0
            for m in members:
                if not (m.isfile() or m.isdir()):  # 링크/디바이스/FIFO 등 비정규 거부
                    raise Exception(f"archive contains non-regular member (rejected): {m.name!r}")
                _check_name(m.name, "tar-slip")
                total += m.size
                if total > _MAX_INGEST_BYTES:
                    raise Exception("archive uncompressed size exceeds limit (bomb guard)")
            try:
                tf.extractall(dest, filter="data")  # Python 3.12+ 추가 방어
            except TypeError:
                tf.extractall(dest)


async def ingest_external_checkpoint(
    workspace_id: int, model_id: int,
    target_manifest_name: str, target_manifest_version: str,
    ref_type: str, ref: str, token: str = None,
    commit_name: str = None, description: str = None, metadata: dict = None,
) -> dict:
    """기관 제공 커스텀 체크포인트를 by-reference pull → 검증 → commit_models 머티리얼.

    런타임-바운드(모델은 training_type='external' + 그 모델에 묶인 manifest 에만).
    토큰은 pull 에만 쓰고 절대 저장/로그하지 않는다(provenance 엔 정제된 ref 만).
    """
    if ref_type not in _CKPT_REF_TYPES:
        raise Exception(f"unsupported ref_type: {ref_type!r} (allowed: {_CKPT_REF_TYPES})")
    if not ref:
        raise Exception("ref (checkpoint reference) is required")

    model_row = await db_model.get_model(model_id=model_id)
    if not model_row:
        raise Exception(f"model {model_id} not found")
    if (model_row.get("training_type") or "internal") != "external":
        raise Exception(f"model {model_id} is not training_type='external' (runtime-bound only)")
    # 테넌트 격리 — 경로/소유 workspace 는 caller body 가 아니라 model row 가 권위.
    model_ws = model_row.get("workspace_id")
    if workspace_id != model_ws:
        raise Exception(f"workspace_id {workspace_id} does not match model {model_id} workspace {model_ws}")
    # 런타임 바인딩 강제 — 모델에 묶인 manifest 와 타깃 런타임이 일치해야 한다.
    if model_row.get("external_manifest_name") and target_manifest_name != model_row.get("external_manifest_name"):
        raise Exception(
            f"target_manifest {target_manifest_name!r} != model's bound runtime "
            f"{model_row.get('external_manifest_name')!r}"
        )

    workspace_info = await db_model.get_workspace_model(workspace_id=model_ws)
    storage_name = workspace_info["main_storage_name"]
    workspace_name = workspace_info["name"]

    if not commit_name:
        commit_name = "custom-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if not _CKPT_NAME_RE.match(commit_name):
        raise Exception(f"invalid commit_name (slug required): {commit_name!r}")
    # DB 레벨 중복 사전 체크(파일시스템 race 완화; 최종 arbitration 은 DB unique).
    if await db_model.check_commit_model_by_name(commit_name=commit_name, model_id=model_id):
        raise Exception(f"commit_name already registered: {commit_name!r}")

    if ref_type == "url":
        _check_pull_url_safe(ref)  # SSRF 가드

    main_root = PATH.JF_MAIN_STORAGE_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name)
    model_root = PATH.JF_MAIN_MODEL_PATH.format(
        STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, MODEL_NAME=model_row["name"],
    )
    commit_dir = os.path.join(model_root, "commit_models", commit_name)
    _commits_base = os.path.realpath(os.path.join(model_root, "commit_models"))
    if os.path.commonpath([os.path.realpath(commit_dir), _commits_base]) != _commits_base:
        raise Exception("commit path escapes commit_models base")
    if os.path.exists(commit_dir):
        raise Exception(f"commit dir already exists: {commit_dir}")

    # staging 으로 pull → 검증 → commit_dir 이동(부분 산출물이 commit_models 에 안 남게).
    staging = os.path.join(main_root, "jobs", f"_ingest-{commit_name}-{uuid.uuid4().hex[:8]}")
    commit_id = None
    try:
        os.makedirs(staging, exist_ok=True)
        if ref_type == "hf":
            def _pull_hf():
                from huggingface_hub import snapshot_download
                snapshot_download(repo_id=ref, local_dir=staging, token=token or None,
                                  allow_patterns=_EVA_ALLOW_PATTERNS)
                # 다운로드 총량 상한 검사(NFS 보호).
                total = 0
                for r_, _d, fs in os.walk(staging):
                    for fn in fs:
                        total += os.path.getsize(os.path.join(r_, fn))
                if total > _MAX_INGEST_BYTES:
                    raise Exception("hf download exceeds size limit")
            await asyncio.to_thread(_pull_hf)
        elif ref_type == "url":
            def _pull_url():
                import requests, re as _re
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                # allow_redirects=False — 리다이렉트로 내부 타깃 우회 차단(직접 URL 권장).
                with requests.get(ref, headers=headers, stream=True, timeout=600,
                                  allow_redirects=False) as r:
                    if r.is_redirect or r.status_code in (301, 302, 303, 307, 308):
                        raise Exception("url redirect not allowed (provide a direct URL)")
                    r.raise_for_status()
                    cd = r.headers.get("content-disposition", "")
                    mt = _re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
                    fname = (mt.group(1).strip() if mt
                             else (ref.split("?")[0].rstrip("/").split("/")[-1] or "artifact.bin"))
                    fname = os.path.basename(fname) or "artifact.bin"
                    dest = os.path.join(staging, fname)
                    total = 0
                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1 << 20):
                            if chunk:
                                total += len(chunk)
                                if total > _MAX_INGEST_BYTES:
                                    raise Exception("download exceeds size limit")
                                f.write(chunk)
                    if fname.endswith((".tar", ".tar.gz", ".tgz", ".zip")):
                        _safe_extract_archive(dest, staging)  # zip/tar-slip + bomb 방어
                        os.remove(dest)
            await asyncio.to_thread(_pull_url)

        # 중첩 단일 디렉터리(예: HF repo 폴더)면 그 안을 검사/이동. symlink 면 거부.
        _root = staging
        entries = [e for e in os.listdir(staging) if not e.startswith(".")]
        if len(entries) == 1 and os.path.isdir(os.path.join(staging, entries[0])):
            cand = os.path.join(staging, entries[0])
            if os.path.islink(cand):
                raise Exception("top-level entry is a symlink — rejected")
            _root = cand
        _validate_eva_checkpoint_layout(_root)  # 검증 게이트 — 미충족 시 예외

        provenance = {
            "source": "custom_checkpoint_by_reference",
            "ref_type": ref_type,
            "ref": _sanitize_ref_for_storage(ref, ref_type),  # creds/query 제거, 토큰 저장 X
            "target_manifest": f"{target_manifest_name}@{target_manifest_version}",
            "validated": "eva_loader_contract",
        }
        if isinstance(metadata, dict):
            for k, v in metadata.items():
                provenance.setdefault(k, v)

        os.makedirs(os.path.dirname(commit_dir), exist_ok=True)
        # move + DB insert 를 한 단위로 — DB 실패 시 commit_dir orphan/이름 블랙리스트 방지.
        try:
            shutil.move(_root, commit_dir)
            commit_id = await db_model.create_commit_model(
                name=commit_name, model_id=model_id, workspace_id=model_ws,
                create_user_id=model_row.get("create_user_id"),
                fine_tuning_config=json.dumps(provenance, ensure_ascii=False),
                commit_message=(description or f"custom checkpoint ({ref_type})"),
                model_description=(model_row.get("description") or ""),
            )
            await db_model.update_model_commit_id(latest_commit_id=commit_id, model_id=model_id)
        except Exception:
            if os.path.isdir(commit_dir):
                shutil.rmtree(commit_dir, ignore_errors=True)
            raise
    finally:
        if os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)

    return {"commit_id": commit_id, "commit_name": commit_name, "commit_dir": commit_dir, "validated": True}


async def ingest_external_checkpoint_safe(**kwargs) -> None:
    """BackgroundTask 래퍼 — 예외를 삼키지 않고 로깅(운영자가 commit 목록으로 결과 확인)."""
    try:
        res = await ingest_external_checkpoint(**kwargs)
        print(f"[ingest_external_checkpoint] ok: {res.get('commit_name')}")
    except Exception as e:
        print(f"[ingest_external_checkpoint] FAILED model_id={kwargs.get('model_id')} "
              f"ref_type={kwargs.get('ref_type')} error={e!r}")
        traceback.print_exc()


async def delete_model(model_id : int) -> bool:
    
    model_info = await db_model.get_model(model_id=model_id)
    
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    
    # 현재 동작 중인지 확인
    redis_client = await get_redis_client_async()
    model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, model_info["workspace_id"]) 
    if model_pod_status:
        model_pod_status = json.loads(model_pod_status)
    else:
        model_pod_status = {}
    if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
        if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model_id),{}):
            raise Exception(f"현재 파인튜닝중입니다. 해당 작업을 종료 후 진행해 주세요.")

    # 해당 모델을 다운 받고 있을 경우
    model_commit_helm_repo_name = TYPE.MODEL_COMMIT_JOB_HELM_NAME.format(MODEL_ID=model_id)
    await delete_helm_repo(helm_repo_name=model_commit_helm_repo_name, workspace_id=model_info["workspace_id"])

    # compose/download 때 만든 HF 토큰 Secret(C-4) 정리 — 모델 삭제 시 함께 제거(누적 방지, 없으면 무시).
    try:
        delete_secret(namespace=TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=model_info["workspace_id"]),
                      name=f"hf-token-{model_id}")
    except Exception as e:
        print(f"Warning: failed to delete HF token secret for model {model_id}: {e}")

    await db_model.delete_model(model_id=model_id)
    await delete_model_folder(storage_name=workspace_info["main_storage_name"], workspace_name=workspace_info["name"], model_name=model_info["name"])
    
    return True

async def delete_model_dataset(model_dataset_id : int) -> bool:
    
    res = await db_model.delete_model_dataset(model_dataset_id=model_dataset_id)
    return res

async def delete_model_configuration(model_config_id : int) -> bool:
    
    model_config_file_info = await db_model.get_fine_tuning_config_file(model_config_id=model_config_id)
    model_info = await db_model.get_model(model_id=model_config_file_info["model_id"])
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    config_file_path = PATH.JF_MODEL_CONFIGURATION_FILE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"], FILE_NAME=model_config_file_info["file_name"])
    if await common.async_delete_file(file_path=config_file_path):
        await db_model.delete_model_configuration(model_config_id=model_config_id)
        return True
    return False

async def _resolve_external_steps_per_epoch(model_info: dict, job_id: str) -> int:
    """External training 의 total_steps 추정 — frontend "1 Epoch = N steps" 표시용.

    Source priority:
      1) fb_external_container detail 의 partner total_steps (학습 active 일 때)
      2) commit_models 의 events.out.tfevents 의 train/loss last step (cleanup 후)
      3) 둘 다 없으면 0
    """
    import os, glob as _glob
    from utils import settings, PATH
    import httpx

    # 1. fb_external_container detail 시도 (tracker active)
    try:
        url = f"{settings.FB_EXTERNAL_CONTAINER_URL.rstrip('/')}/api/v1/jobs/{job_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            detail = resp.json()
            r = (detail.get("result") or {}).get("result") or {}
            total = r.get("total_steps") or 0
            if total and int(total) > 0:
                return int(total)
    except Exception:
        pass

    # 2. commit_models events fallback
    try:
        workspace_info = await db_model.get_workspace_model(
            workspace_id=int(model_info["workspace_id"]),
        )
        if workspace_info and model_info.get("latest_commit_id"):
            commit_row = await db_model.get_commit_model(commit_id=model_info["latest_commit_id"])
            if commit_row:
                main_root = PATH.JF_MAIN_STORAGE_PATH.format(
                    STORAGE_NAME=workspace_info["main_storage_name"],
                    WORKSPACE_NAME=workspace_info["name"],
                )
                runs_dir = (
                    f"{main_root}/models/{model_info['name']}/commit_models/"
                    f"{commit_row['name']}/runs"
                )
                if os.path.exists(runs_dir):
                    run_paths = sorted(
                        _glob.glob(os.path.join(runs_dir, "*")),
                        key=os.path.getmtime,
                        reverse=True,
                    )
                    if run_paths:
                        parsed, latest_step = await parse_tensorboard_scalars_async(
                            log_dir=run_paths[0], max_steps=50,
                        )
                        if latest_step and int(latest_step) > 0:
                            return int(latest_step)
    except Exception:
        pass

    return 0


async def get_model_fine_tuning(model_id : int) -> dict:

    model_info = await db_model.get_model(model_id=model_id)

    # 외부 학습 모델은 dataset/commit/configuration 파이프라인이 없다.
    # FineTuning 탭은 진입 시 frontend 에서 외부 학습 탭으로 redirect 하지만,
    # backend 호출이 leakage 로 들어와도 minimal payload 만 반환해 IndexError/
    # TypeError 를 회피한다.
    if (model_info or {}).get("training_type") == "external":
        # steps_per_epoch — frontend FineTuningGraph 의 "1 Epoch = N steps" 표시용.
        # partner /train/status 의 total_steps (학습 시작 시 정확) 우선,
        # tracker cleanup 후엔 events.out.tfevents 의 train/loss last step fallback.
        steps_per_epoch = 0
        job_id = model_info.get("external_job_id")
        if job_id:
            steps_per_epoch = await _resolve_external_steps_per_epoch(model_info, job_id)
        return {
            "model_id" : model_info["id"],
            "model_name" : model_info["name"],
            "training_type" : "external",
            "external_manifest_name" : model_info.get("external_manifest_name"),
            "external_manifest_version" : model_info.get("external_manifest_version"),
            "external_job_id" : model_info.get("external_job_id"),
            "steps_per_epoch" : steps_per_epoch,
            "commit_model_count" : 0,
            "model_datasets" : [],
            "model_config_file_list" : [],
            "latest_commit_info" : None,
            "resource_info" : None,
            "fine_tuning_config" : None,
        }

    # 멀티모달(VLM) 모델은 메타데이터-only 행(commit/folder 없음, training_type='internal').
    # 내부 FT 경로가 latest_commit_id(=NULL) 를 deref 하면 TypeError(리뷰 CRITICAL) →
    # external 과 동형으로 minimal payload 조기 반환. (Phase 2 에서 Multimodal 탭 전용 surface)
    if (model_info or {}).get("load_type") == "multimodal":
        # 데이터셋 바인딩은 commit deref 와 무관 → 실제 조회해 surface(스텁이 []로 하드코딩해
        # 바인딩돼도 "없음"으로 보이던 버그 수정). commit/folder 의존 필드만 None 유지.
        mm_datasets = await db_model.get_model_datasets(model_id=model_id)
        mm_dataset_parse = []
        for md in mm_datasets:
            dpath = md["training_data_path"]
            full = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=md["data_storage_name"],
                WORKSPACE_NAME=md["workspace_name"], ACCESS=md["access"],
                DATASET_NAME=md["dataset_name"], DATA_PATH=dpath)
            mm_dataset_parse.append({
                "id": md["id"], "dataset_name": md["dataset_name"],
                "model_file_path": dpath, "data_exist": await check_file_exists(file_path=full),
            })
        return {
            "model_id" : model_info["id"],
            "model_name" : model_info["name"],
            "training_type" : "internal",
            "load_type" : "multimodal",
            "huggingface_model_id" : model_info.get("huggingface_model_id"),
            # 엔진이 update_steps_per_epoch 로 기록한 실값(=샘플수). FineTuningGraph "1 Epoch = N steps"
            # + sse-time 진행률 분모. 스텁 0 하드코딩이 "1 Epoch = 0 steps" 로 보이던 버그 수정.
            "steps_per_epoch" : model_info.get("steps_per_epoch") or 0,
            "commit_model_count" : 0,
            "model_datasets" : mm_dataset_parse,
            "model_config_file_list" : [],
            "latest_commit_info" : None,
            "resource_info" : None,
            "fine_tuning_config" : None,
        }

    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    if model_info["latest_fine_tuning_config"] is None:
        fine_tuning_config = FineTuningConfig().model_dump()
    else:
        fine_tuning_config = json.loads(model_info["latest_fine_tuning_config"])
    model_datasets = await db_model.get_model_datasets(model_id=model_id)
    config_file_list = await db_model.get_fine_tuning_config_files(model_id=model_id)
    commit_list = await db_model.get_commit_models(model_id=model_id)
    # TODO
    # 1. latest_fine_tuning_status 에 따라 graph 보여주고 말고 추가
    # 2. model_dataset 이 실제로 존재하는지 check
    # 3. fine tuning 중인지 확인 (db에 있는걸로 할까 싶음)
    
    model_dataset_parse = []
    
    for model_dataset in model_datasets:
        data_path = model_dataset["training_data_path"]
        data_full_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=model_dataset["data_storage_name"] ,WORKSPACE_NAME=model_dataset["workspace_name"] , \
            ACCESS=model_dataset["access"] , DATASET_NAME=model_dataset["dataset_name"], DATA_PATH=data_path)
        data_exist = await check_file_exists(file_path=data_full_path)
        model_dataset_parse.append({
            "id" : model_dataset["id"],
            "dataset_name" : model_dataset["dataset_name"],
            "model_file_path" : data_path,
            "data_exist" : data_exist
        })
        
    config_file_parse = []
    
    for config_file in config_file_list:
        file_name = config_file["file_name"]
        config_file_path = PATH.JF_MODEL_CONFIGURATION_FILE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"], FILE_NAME=file_name)
        file_exist = await check_file_exists(file_path=config_file_path)
        config_file_parse.append({
            "id" : config_file["id"],
            "file_name" : file_name,
            "file_size" : config_file["size"],
            "file_exist" : file_exist
        })
    
    # log_path = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
    #     WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
    # log_parser = await parse_tensorboard_scalars_async(log_dir=log_path)
    instance_info = db_instance.get_instance(instance_id=model_info["instance_id"])
    
    resource_info = await workspace_resource.get_workspace_instance_total_info(instance_id=model_info["instance_id"], workspace_id=model_info["workspace_id"], instance_allocate=model_info["instance_count"], resource_limit=[{
        "cpu_limit" : instance_info["cpu_allocate"]*model_info["instance_count"],
        "ram_limit" : instance_info["ram_allocate"]*model_info["instance_count"],
    }]) if  model_info["instance_id"] else {}
    
    # resource_info = {
    #     "instance_id" : model_info["instance_id"],
    #     "instance_count" : model_info["instance_count"],
    #     "instance_name" : model_info["instance_name"],
    #     "gpu_count" : model_info["gpu_count"],
    #     "pod_count" : model_info["pod_count"],
    #     "cluster_type" : "auto"
    # } if  model_info["instance_id"] else {}
    
    latest_commit_info = await db_model.get_commit_model(commit_id=model_info["latest_commit_id"])
    
    return {
        "commit_model_count" : len(commit_list),
        "model_id" : model_info["id"],
        "model_name" : model_info["name"],
        "steps_per_epoch" : model_info["steps_per_epoch"],
        "huggingface_git" : model_info["huggingface_git"],
        "huggingface_mode_id" : model_info["huggingface_model_id"],
        "commit_model_name" : model_info["commit_model_name"],
        "resource_info" : resource_info,
        "fine_tuning_config" : fine_tuning_config,
        "model_datasets" : model_dataset_parse,
        "model_config_file_list" : config_file_parse,
        "latest_commit_info" : {
            "id" : latest_commit_info["id"],
            "name" : latest_commit_info["name"]
        },
        # External training marker — FineTuning 탭의 frontend 가 이 값을 보고
        # 외부 학습 모델이면 안내 + 외부 학습 탭으로 redirect 한다.
        "training_type" : model_info.get("training_type") or "internal",
        "external_manifest_name" : model_info.get("external_manifest_name"),
        "external_manifest_version" : model_info.get("external_manifest_version"),
        "external_job_id" : model_info.get("external_job_id"),
        # "fine_tuning_log" : log_parser
    }

async def get_fine_tuning_status(model_id : int) -> dict:
    # GenAI 통합 파이프라인 런타임의 internal FT 진행 폴링용 경량 s2s 조회.
    # latest_fine_tuning_status (pending/running/done/stop/error) 만 반환.
    model_info = await db_model.get_model(model_id=model_id)
    return {"status": (model_info or {}).get("latest_fine_tuning_status")}

async def running_fine_tuning(model_id : int, model_dataset_id : int, instance_id : int, instance_count : int,\
    gpu_count : int, fine_tuning_config : FineTuningConfig = FineTuningConfig()) -> True:
    
    # TODO
    # 1. 현재 commit 중인지 fine tuning 중인지 확인 
    
    # 2. cluster auto case 로 실행 할 수 있는 리스트 받아서 해당 case 로 pod info 생성 
    
    # 3. pod info에 추가 
    redis_client = await get_redis_client_async()
    model_info = await db_model.get_model(model_id=model_id)
    # 멀티모달(VLM): 생성 시 compose_vlm 잡이 비전+LLM 을 LLaVA 로 조립해 NFS(latest_checkpoint)
    # 적재 + 초기 커밋 생성 → 일반 FT 경로 진입 가능. VLM 2-stage 엔진을 타도록 vlm=1 강제
    # (FE config 누락 방어; 스케줄러가 vlm=1 → VLM 스크립트 디스패치).
    if (model_info or {}).get("load_type") == "multimodal":
        fine_tuning_config.vlm = 1
        # vlm_stage1_epochs=0 은 FE 의 "stage1(projector) 스킵" 의도 → 보존. 미전송(None)만 기본값.
        if getattr(fine_tuning_config, "vlm_stage1_epochs", None) is None:
            fine_tuning_config.vlm_stage1_epochs = 1.0
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])

    model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, model_info["workspace_id"])
    if model_pod_status:
        model_pod_status = json.loads(model_pod_status)
    else:
        model_pod_status = {}
    fine_tuning_status = None
    if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
        if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model_id),{}):
            fine_tuning_status = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model_id)]["status"]
    
    # redis 에서 상태값 가져와서 확인 없으면 db 값으로 진행 
    # TODO 
    # 추후 redis 상태값으로 변경
    if model_info["commit_status"] == TYPE.KUBE_POD_STATUS_RUNNING:
        raise Exception(f"Error: Model is commit")
    
    # if any(status not in [TYPE.KUBE_POD_STATUS_DONE, TYPE.KUBE_POD_STATUS_STOP, TYPE.KUBE_POD_STATUS_ERROR] 
    #    for status in [fine_tuning_status, model_info["latest_fine_tuning_status"]]):
    if  model_info["latest_fine_tuning_status"] not in [TYPE.KUBE_POD_STATUS_DONE, TYPE.KUBE_POD_STATUS_STOP, TYPE.KUBE_POD_STATUS_ERROR] :
        raise Exception(f"Error: Model is already running")
    
    commit_model_info = await db_model.get_commit_model(commit_id=model_info["latest_commit_id"])
    
    #  latest_checkpoint가 비어 있는지 확인 
    latest_checkpoint_path = PATH.JF_MODEL_LATEST_CHECKPOINT_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
    if await is_folder_empty(latest_checkpoint_path):
        commit_model_path = PATH.JF_MODEL_COMMIT_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])\
            + "/{}".format(commit_model_info["name"])
        await common.async_copy_directory_contents(commit_model_path, latest_checkpoint_path)
    
    # model_dataset_info = await db_model.get_model_dataset(model_dataset_id=model_dataset_id)
    
    used_cluster_case = dict()
    gpu_cluster_auto = False
    if gpu_count > 1:
        gpu_cluster_auto = True
        gpu_cluster_info = await common.get_gpu_cluster_info(instance_id=instance_id, redis_client=redis_client)
        gpu_cluster_cases = await common.get_auto_gpu_cluster(redis_client=redis_client, instance_id=instance_id, gpu_count=gpu_count, gpu_cluster_info=gpu_cluster_info)
        # gpu_cluster_cases = sorted(gpu_cluster_cases, key=lambda x:x["gpu_count"])
        used_cluster_case = gpu_cluster_cases[0] # TODO 가장 좋은 cluster 유형만 선택
    
    pod_info = FineTuningPodInfo(
        model_id=model_id,
        model_name=model_info["name"],
        commit_id=model_info["latest_commit_id"],
        commit_name=commit_model_info["name"],
        workspace_id=model_info["workspace_id"],
        workspace_name=model_info["workspace_name"],
        instance_count=instance_count,
        model_dataset_id=model_dataset_id,
        image_name=settings.FINE_TUNING_IMAGE, #"192.168.1.150:30500/jfb-system/fine_tuning:0.2.0",
        owner_id=model_info["create_user_id"],
        gpu_count=gpu_count,
        gpu_cluster_auto=gpu_cluster_auto,
        gpu_auto_cluster_case=used_cluster_case,
        instance_id=instance_id,
        resource_type=TYPE.RESOURCE_TYPE_GPU,
        pod_type=TYPE.FINE_TUNING_TYPE,
        fine_tuning_config=fine_tuning_config,
    )
    # Model 상태값 수정
    await db_model.update_model_fine_tuning_status(status=TYPE.KUBE_POD_STATUS_PENDING, model_id=model_id, steps_per_epoch=0)
    await db_model.update_model_fine_tuning_instance(instance_id=instance_id, instance_count=instance_count, \
        gpu_count=gpu_count, model_id=model_id, fine_tuning_config=fine_tuning_config.model_dump_json())
    
    print(pod_info)
    topic = topic_key.SCHEDULER_TOPIC
    # if project_tool_info.gpu_count > 0:
    #     topic = topic_key.PROJECT_TOPIC.format(project_info["id"], "GPU")
    # else:
    #     topic = topic_key.PROJECT_TOPIC.format(project_info["id"], "CPU")
    
    producer = AIOKafkaProducer(
    bootstrap_servers=settings.JF_KAFKA_DNS,
    value_serializer=lambda v: v.encode('utf-8'),  # 문자열 값을 바이트로 직렬화
    # key_serializer=lambda v: v.encode('utf-8')    # 문자열 키를 바이트로 직렬화
    )
    # 프로듀서 시작
    await producer.start()
    try:
        # 메시지 보내기
        message = pod_info.model_dump_json()
        await producer.send_and_wait(topic, value=message)
    finally:
        # 프로듀서 종료
        await producer.stop()
    
    return True

async def _uninstall_fine_tuning_with_retry(
    repo: str,
    workspace_id: int,
    max_attempts: int = 2,
    retry_delay_s: float = 3.0,
) -> Tuple[bool, str]:
    """Helm uninstall with bounded retry for transient failures.

    Returns (ok, last_message). Does not sleep after the final attempt.

    Only (False, message) returns from delete_helm_repo trigger a retry —
    exceptions raised by delete_helm_repo propagate to the caller
    (delete_helm_repo already wraps subprocess errors in its own try/except
    and returns (False, ...), so exception propagation is not expected).
    """
    last_msg = ""
    for attempt in range(1, max_attempts + 1):
        ok, msg = await delete_helm_repo(
            helm_repo_name=repo, workspace_id=workspace_id
        )
        if ok:
            return True, msg
        last_msg = msg
        if attempt < max_attempts:
            await asyncio.sleep(retry_delay_s)
    return False, last_msg


async def stop_fine_tuning(model_id: int):
    model_info = await db_model.get_model(model_id)
    workspace_info = await db_model.get_workspace_model(
        workspace_id=model_info["workspace_id"]
    )
    fine_tuning_repo = TYPE.FINE_TUNING_REPO_NAME.format(model_id)

    # 1) Helm uninstall (재시도 포함)
    #    이 시점의 latest_fine_tuning_status는 INSTALLING/RUNNING/PENDING —
    #    service.py의 재실행 가드가 자연스럽게 차단 중.
    uninstall_ok, uninstall_msg = await _uninstall_fine_tuning_with_retry(
        repo=fine_tuning_repo,
        workspace_id=model_info["workspace_id"],
    )
    if not uninstall_ok:
        # 거짓 STOP 대신 error 기록 (error는 재실행 허용 상태이므로
        # 사용자가 재시도 가능 — 의도된 동작).
        await db_model.update_model_fine_tuning_status(
            status=TYPE.KUBE_POD_STATUS_ERROR, model_id=model_id
        )
        return False, f"helm uninstall failed: {uninstall_msg}"

    # 2) 체크포인트 후처리.
    #    중요: 여기서도 아직 STOP을 기록하지 않는다. 재실행 가드 유지.
    tmp_path = PATH.JF_MODEL_TMP_PATH.format(
        STORAGE_NAME=workspace_info["main_storage_name"],
        WORKSPACE_NAME=workspace_info["name"],
        MODEL_NAME=model_info["name"],
    )
    if not await move_checkpoint_files_to_parent(tmp_path):
        # 체크포인트가 없는 경우 — commit job도 건너뛰고 종료.
        # 재실행 가드를 풀어주기 위해 STOP 기록.
        await db_model.update_model_fine_tuning_status(
            status=TYPE.KUBE_POD_STATUS_STOP, model_id=model_id
        )
        return False, "not exist checkpoint"

    # 3) commit job 설치 (load_or_stop_helm은 별도 Helm release).
    latest_checkpoint_path = PATH.JF_POD_MODEL_LATEST_CHECKPOINT_PATH.format(
        MODEL_NAME=model_info["name"]
    )
    tmp_model_path = PATH.JF_POD_MODEL_TMP_MODEL_PATH.format(
        MODEL_NAME=model_info["name"]
    )
    res, message = await load_or_stop_helm(
        workspace_id=model_info["workspace_id"],
        model_id=model_id,
        latest_checkpoint_path=latest_checkpoint_path,
        tmp_model_path=tmp_model_path,
    )
    if res:
        # 4) commit job 설치 성공 — 재실행 차단 권한을 commit_status로 이관.
        #    순서 중요: commit_status를 먼저 RUNNING으로 올리고,
        #    그 다음 latest_fine_tuning_status를 STOP으로 전이.
        #    commit_status=RUNNING은 fb_monitoring이 commit pod 종료 시
        #    DONE/ERROR로 전이 (monitoring_service.py 참조).
        await db_model.update_model_commit_status(
            commit_status=TYPE.KUBE_POD_STATUS_RUNNING,
            model_id=model_id,
            latest_commit_id=model_info["latest_commit_id"],
            commit_type=TYPE.COMMIT_TYPE_STOP,
        )
        await db_model.update_model_fine_tuning_status(
            status=TYPE.KUBE_POD_STATUS_STOP, model_id=model_id
        )
        return True, "success"

    # commit job 설치 실패 — 가드 해제 위해 ERROR 기록.
    await db_model.update_model_fine_tuning_status(
        status=TYPE.KUBE_POD_STATUS_ERROR, model_id=model_id
    )
    return False, message

async def get_efk_fine_tuning_logs(model_id : int, pod_name : str, count : int = 100, is_all : bool = True):
    request_log_data = {
            "modelId" : model_id,
            "podName" : pod_name,
            "count" : count, # 최근 1000개,
            "offset" : 0
        }
    logs = {}
    if is_all:
        # logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/finetuning/all", data=request_log_data)
        logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/finetuning/all", data=request_log_data)
        
    else: 
        logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/finetuning/figure", data=request_log_data)
    return logs 

async def get_fine_tuning_system_log(model_id : int, count : int = 100, is_download : bool = False):
    model_info = await db_model.get_model(model_id=model_id)
    if model_info["start_datetime"]:
        base_pod_name, unique_pod_name, container_name = PodName(workspace_name=model_info["workspace_id"], item_name=model_id, \
            item_type=TYPE.FINE_TUNING_TYPE, start_datetime=model_info["start_datetime"]).get_all()
        logs = await get_efk_fine_tuning_logs(model_id=model_id, pod_name=unique_pod_name, count=count)
        if logs:
            logs_line = [log['fields']['log'] for log in logs["logs"]] 
            if is_download:
                return await common.text_response_generator_async(data_str="\n".join(logs_line) , filename="[FINETUNING]{}_system.log".format(model_info["name"]))
            return "\n".join(logs_line) 
    return ""

async def upload_fine_tuning_configuration(file: UploadFile, model_id : int):
    
    model_info = await db_model.get_model(model_id=model_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    sanitize_filename = common.sanitize_filename(filename=file.filename)
    model_config_path = PATH.JF_MODEL_CONFIGURATION_FILE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"], FILE_NAME=sanitize_filename)
    file_size = 0
    with open(model_config_path, "wb") as f:
        contents = await file.read()
        file_size = len(contents)
        f.write(contents)
    
    await db_model.create_fine_tuning_config_file(file_name=sanitize_filename, model_id=model_id, size=file_size)
    
    
    return True


async def get_fine_tuning_result_logs(model_id : int):
    model_info = await db_model.get_model(model_id=model_id)
    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
    log_path = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
    log_parser, _ = await parse_tensorboard_scalars_async(log_dir=log_path)
    return log_parser

def calculate_remaining_time_with_ema(
    start_time, current_time, current_step, total_steps, ema_factor=0.9, last_time_per_step=None
):
    """
    지수 이동 평균(EMA)을 사용하여 스텝당 소요 시간을 계산하고 잔여 시간을 추정합니다.

    Args:
        start_time (datetime.datetime): 학습 시작 시간 (datetime 객체).
        current_time (float): 현재 시간 (UNIX timestamp).
        current_step (int): 현재까지 완료된 스텝 수.
        total_steps (int): 학습 전체 스텝 수.
        ema_factor (float, optional): EMA 계수 (0.0 ~ 1.0). 기본값은 0.9.
        last_time_per_step (float, optional): 이전 스텝당 소요 시간.

    Returns:
        tuple: (잔여 시간, 새로운 EMA 기반 스텝당 소요 시간)
    """
    if current_step <= 0 or total_steps <= current_step:
        raise ValueError("현재 스텝은 0보다 커야 하며, 총 스텝보다 작아야 합니다.")

    # datetime 객체를 UNIX timestamp로 변환
    start_time_unix = start_time.timestamp()

    # 경과 시간 계산
    elapsed_time = current_time - start_time_unix

    # 스텝당 소요 시간 계산 (EMA 적용)
    current_time_per_step = elapsed_time / current_step
    if last_time_per_step is not None:
        time_per_step = ema_factor * last_time_per_step + (1 - ema_factor) * current_time_per_step
    else:
        time_per_step = current_time_per_step

    # 잔여 스텝 계산
    remaining_steps = total_steps - current_step

    # 잔여 시간 계산
    remaining_time = remaining_steps * time_per_step

    return remaining_time, time_per_step



async def sse_get_fine_tuning_result_graph(model_id : int, request : Request):
        old_history = None
        old_datetime = datetime.datetime.now()
        try:
            while True:
                if await request.is_disconnected():
                    break
                current_datetime = datetime.datetime.now()
                try:
                    model_info = await db_model.get_model(model_id=model_id)
                    workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
                    log_path = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
                        WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
                    # 모델명 traversal 방어 — 로그 경로가 워크스페이스 models 루트 밖이면 거부(보안 M-4).
                    _models_root = PATH.JF_MAIN_STORAGE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"]) + "/models"
                    if not _is_under(log_path, _models_root):
                        break

                    result = None
                    if model_info["steps_per_epoch"]:
                        try:
                            log_parser, latest_step = await parse_tensorboard_scalars_async(log_dir=log_path)
                            # 파싱 결과가 비어있지 않은 경우에만 사용
                            if log_parser and len(log_parser) > 0:
                                # ⑩ 체크포인트 step 점 마킹(저장 디렉토리 스캔 + save_steps 추정).
                                ckpt_steps = await _model_checkpoint_steps(model_info, workspace_info, latest_step)
                                result = {
                                    "graph" : log_parser,
                                    "checkpoints" : ckpt_steps,
                                }
                            else:
                                # 파싱 결과가 비어있으면 이전 결과 유지
                                result = None
                        except Exception as parse_error:
                            # 파싱 실패 시 로그만 남기고 이전 결과 유지
                            traceback.print_exc()
                            print(f"Failed to parse tensorboard logs: {parse_error}")
                            result = None
                    
                    # result가 None이면 이전 결과 유지
                    if result is None:
                        if old_history is not None:
                            # 이전 결과가 있으면 유지
                            result = old_history
                        else:
                            # 이전 결과도 없으면 빈 그래프 반환
                            result = {
                                "graph" : {}
                            }
                    
                    # 결과가 변경된 경우에만 전송 (빈 데이터와 데이터 사이의 불필요한 전환 방지)
                    if result != old_history:
                        old_history = result
                        old_datetime = current_datetime
                        yield f"data: {json.dumps(result)}\n\n"
                    elif (current_datetime - old_datetime).total_seconds() >=30:
                        # 30초마다 하트비트 전송 (이전 결과 전송)
                        old_datetime = current_datetime
                        if old_history is not None:
                            yield f"data: {json.dumps(old_history)}\n\n"
                    
                except Exception as loop_error:
                    # 루프 내부 예외 처리 (DB 조회 실패 등)
                    traceback.print_exc()
                    print(f"Exception in SSE loop: {loop_error}")
                    # 예외 발생 시 이전 결과 유지 또는 빈 결과 반환
                    if old_history is None:
                        old_history = {
                            "graph" : {}
                        }
                
                await asyncio.sleep(1)
        except Exception as e:
            # 예외 처리 및 로그 남기기
            traceback.print_exc()
            print(f"Exception in SSE stream: {e}")
        finally:
            # 연결이 끊어졌을 때의 후속 처리
            pass


async def sse_get_fine_tuning_time(model_id : int, request : Request):
    old_history = None
    last_time_per_step = None
    old_datetime = datetime.datetime.now()
    try:
        while True:
            if await request.is_disconnected():
                break
            current_datetime = datetime.datetime.now()
            model_info = await db_model.get_model(model_id=model_id)
            workspace_info = await db_model.get_workspace_model(workspace_id=model_info["workspace_id"])
            log_path = PATH.JF_MODEL_LOG_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], \
                WORKSPACE_NAME=workspace_info["name"], MODEL_NAME=model_info["name"])
            # 모델명 traversal 방어 — 로그 경로가 워크스페이스 models 루트 밖이면 거부(보안 M-4).
            _models_root = PATH.JF_MAIN_STORAGE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"]) + "/models"
            if not _is_under(log_path, _models_root):
                break
            config_json =model_info.get("latest_fine_tuning_config") if model_info.get("latest_fine_tuning_config") else "{}"
            config = json.loads(config_json)
            
            if model_info["steps_per_epoch"]:
                spe = model_info["steps_per_epoch"]
                # VLM 2-stage 는 stage1(projector)+stage2(LM) 가 단일 연속 step 타임라인(엔진이 step
                # 누적 기록) → 전체 epoch = stage2(num_train_epochs) + stage1(vlm_stage1_epochs).
                # 텍스트 FT(vlm 미설정)는 num_train_epochs 그대로 → 동작 불변.
                total_epochs = config.get("num_train_epochs", 0) or 0
                if config.get("vlm"):
                    s1 = config.get("vlm_stage1_epochs", 0) or 0
                    if s1 and s1 > 0:
                        total_epochs += s1
                total_step = spe * total_epochs if total_epochs else spe
                _, latest_steps = await parse_tensorboard_scalars_async(log_dir=log_path)
                latest_step = latest_steps
                if latest_steps and total_step and latest_step >= total_step:
                    # 완료 도달 — calculate_remaining_time_with_ema 는 total<=current 에서 ValueError 를
                    # 던져 SSE 스트림이 100% 직전에 끊겼음(codex). EMA 호출 없이 완료 페이로드 반환.
                    result = {
                        "total_epoch" : total_epochs,
                        "start_datetime" : model_info["start_datetime"],
                        "progress_epoch" : total_epochs,
                        "percent" : 100,
                        "remaining_time" : 0,
                    }
                elif latest_steps:
                    remaining_time, new_time_per_step = calculate_remaining_time_with_ema(
                        start_time=datetime.datetime.strptime(model_info["start_datetime"], TYPE.TIME_DATE_FORMAT),
                        current_time=datetime.datetime.now().timestamp(),
                        current_step=latest_step,
                        total_steps=total_step,
                        ema_factor=0.9,
                        last_time_per_step=last_time_per_step  # 이전 EMA 값
                    )
                    last_time_per_step = new_time_per_step
                    result = {
                        "total_epoch" : total_epochs,
                        "start_datetime" : model_info["start_datetime"],
                        # 완료 epoch 수(기존 latest_step//total_step 은 완료 직전까지 0 인 버그) → //spe.
                        "progress_epoch" : min(total_epochs, latest_step // spe) if spe else 0,
                        "percent" : round(min(100.0, (latest_step / total_step) * 100), 2) if total_step else 0,
                        "remaining_time" : remaining_time,
                    }
                else:
                    result = {
                        "total_epoch" : total_epochs,
                        "start_datetime" : model_info["start_datetime"],
                        "progress_epoch" : 0,
                        "percent" : 0,
                        "remaining_time" : None
                    }
            else:
                result = {
                    "total_epoch" : config.get("num_train_epochs", 0),
                    "start_datetime" : model_info["start_datetime"],
                    "progress_epoch" : 0,
                    "percent" : 0,
                    "remaining_time" : None
                }
            if result != old_history:
                old_history = result
                old_datetime = current_datetime
                yield f"data: {json.dumps(result)}\n\n"
            elif (current_datetime - old_datetime).total_seconds() >=30:
                old_datetime = current_datetime
                yield f"data: {json.dumps(old_history)}\n\n"
            await asyncio.sleep(1)
    except Exception as e:
        # 예외 처리 및 로그 남기기
        traceback.print_exc()
        print(f"Exception in SSE stream: {e}")
    finally:
        # 연결이 끊어졌을 때의 후속 처리
        pass


async def sse_get_fine_tuning_status(model_id : int, request : Request):
        old_history = None
        old_datetime = datetime.datetime.now()
        try:
            redis_client = await get_redis_client_async()
            while True:
                current_datetime = datetime.datetime.now()
                model_info = await db_model.get_model(model_id=model_id)
                if await request.is_disconnected():
                    break
                model_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, model_info["workspace_id"]) 
                if model_pod_status:
                    model_pod_status = json.loads(model_pod_status)
                else:
                    model_pod_status = {}
                fine_tuning_status = None
                fine_tuning_reason = None
                if model_pod_status.get(TYPE.FINE_TUNING_TYPE, {}):
                    if model_pod_status[TYPE.FINE_TUNING_TYPE].get(str(model_id),{}):
                        fine_tuning_status = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model_id)]["status"]
                        fine_tuning_reason = model_pod_status[TYPE.FINE_TUNING_TYPE][str(model_id)]["reason"]
                    if model_info["latest_fine_tuning_status"] == TYPE.KUBE_POD_STATUS_STOP:
                        fine_tuning_status = TYPE.KUBE_POD_STATUS_STOP
                        fine_tuning_reason = "User stop"
                res = {
                    "fine_tuning_status" : {
                        "status" :   fine_tuning_status if fine_tuning_status else model_info["latest_fine_tuning_status"],
                        "reason" : fine_tuning_reason,
                    },
                    "commit_status" : {
                        "status" : model_info["commit_status"],
                        "type" : model_info["commit_type"],
                        "reason" : "",
                    },
                }
                if res != old_history:
                    old_history = res
                    old_datetime = current_datetime
                    yield f"data: {json.dumps(res)}\n\n"
                elif (current_datetime - old_datetime).total_seconds() >=30:
                    old_datetime = current_datetime
                    yield f"data: {json.dumps(old_history)}\n\n"
                
                await asyncio.sleep(1)
        except Exception as e:
            # 예외 처리 및 로그 남기기
            traceback.print_exc()
            print(f"Exception in SSE stream: {e}")
        finally:
            # 연결이 끊어졌을 때의 후속 처리
            pass