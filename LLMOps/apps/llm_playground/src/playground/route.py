from fastapi import APIRouter, Request, Depends, Header, Body
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional
import traceback, asyncio, json, logging
from datetime import datetime, timedelta
from playground import service as svc
from playground import dto
from utils.resource import response, get_user_id, get_auth
from utils.msa_db import db_user


logger = logging.getLogger(__name__)


TAG_LIST = ['List']
TAG_PLAYGROUND = ['Playground']
TAG_DEPLOYMENT = ['Deployment']
TAG_TEST = ['TEST']
TAG_ACCEL = ['ACCEL']


playgrounds = APIRouter(
    prefix = "/playgrounds"
)


def _log_safe(value):
    """로그 한 줄 위조(CWE-117) 차단 — CR/LF 를 치환하고 길이를 제한한다.

    아래 식별자는 전부 클라이언트가 헤더로 넣을 수 있어, 개행이 남으면 감사 로그를
    여러 줄로 쪼개 가짜 이벤트를 심을 수 있다. 감사 자체가 목적인 로그라 차단 필수.
    """
    return str(value).replace("\r", "_").replace("\n", "_")[:128]


def _deprecation_caller(request: Request):
    """민감한 인증값 없이 호출자 식별에 쓸 수 있는 사용자/IP만 반환한다."""
    user = request.headers.get("jf-user")
    if user and user != "login":
        return _log_safe(user)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # x-forwarded-for 는 위조 가능해 값 자체를 신뢰하지 않되(식별 힌트로만 사용),
        # 로그 줄 쪼개기만은 막는다.
        return _log_safe(forwarded.split(",", 1)[0].strip())
    return _log_safe(request.client.host) if request.client else "unknown"


def _log_deprecation(request: Request, path: str, surface=None):
    # 외부 호출자가 없다는 증거가 아직 없으므로 제거하지 않고, 호출 감사에 필요한 한 줄만 남긴다.
    caller = _deprecation_caller(request)
    if surface:
        logger.warning(
            "event=deprecated_api_call path=%s caller=%s surface=%s",
            path,
            caller,
            surface,
        )
    else:
        logger.warning(
            "event=deprecated_api_call path=%s caller=%s",
            path,
            caller,
        )


async def _resolve_request_prompt_gen(
    playground_id, requested_prompt_gen_id, manual_request=None
):
    """저장 링크가 있으면 고정하고, 링크가 없는 수동 체인만 요청 LLM1을 허용한다."""
    stored_prompt_gen_id = await svc.get_stored_dual_prompt_gen(playground_id)
    if stored_prompt_gen_id is not None:
        if (
            requested_prompt_gen_id is not None
            and requested_prompt_gen_id != stored_prompt_gen_id
        ):
            # 배포된 LLM1과 다른 모델을 실행하면 optimized_prompt가 배포 쌍을 대표하지 않으므로 거부한다.
            raise Exception(
                "요청한 프롬프트 생성 플레이그라운드가 저장된 이중 세션의 LLM1과 일치하지 않습니다."
            )
        return stored_prompt_gen_id
    if requested_prompt_gen_id is not None and manual_request is not None:
        _log_deprecation(
            manual_request,
            manual_request.url.path,
            surface="manual_unlinked_chaining",
        )
    return requested_prompt_gen_id


from utils.redis import get_redis_client_async
from utils.redis_key import WORKSPACE_PODS_STATUS
@playgrounds.post("/start-bg", summary='', tags=TAG_ACCEL)
def start_bg():
    try:
        res = svc.start_bg()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
    
@playgrounds.post("/stop-bg", summary='', tags=TAG_ACCEL)
def stop_bg():
    try:
        res = svc.stop_bg()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

# jonathan accel 시연용    
@playgrounds.post("/start-accel", summary='엑셀러레이터 시작', tags=TAG_ACCEL)
async def start_jonathan_accel():
    try:
        res = await svc.start_jonathan_accel()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
    
@playgrounds.post("/stop-accel", summary='엑셀러레이터 중지', tags=TAG_ACCEL)
async def stop_jonathan_accel():
    try:
        res = await svc.stop_jonathan_accel()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.get("/check-accel", summary='엑셀러레이터 상태 확인', tags=TAG_ACCEL)
async def get_jonathan_accel():
    """
    동작중, 삭제중, ... 레퍼런스?
    """
    try:
        res = await svc.get_jonathan_accel()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.get("/healthz")
async def healthz():
    try:
        redis_client = await get_redis_client_async()
        await redis_client.hgetall(WORKSPACE_PODS_STATUS)
    
        return JSONResponse(status_code=200, content={"status": "healthy"})
    except:
        return JSONResponse(status_code=500, content={"status": "not healthy"})

@playgrounds.get("", summary='목록페이지 - 전체 목록 조회', tags=TAG_LIST)
async def get_playground_list(workspace_id: int=None):
    """
    목록페이지 - 전체 목록 조회
    """
    try:
        user_id = get_user_id()
        res = await svc.get_playground_list(workspace_id=workspace_id, user_id=user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.get("/targets", summary='배포 타겟 통합 목록(cluster+edge) 정규화 read-model', tags=TAG_LIST)
async def get_deployment_targets(workspace_id: int=None):
    """배포 타겟 디스패치 read-model — cluster(Playground)+edge 를 정규화 envelope 로 통합 반환."""
    try:
        user_id = get_user_id()
        res = await svc.get_deployment_targets(workspace_id=workspace_id, user_id=user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.post("",summary='목록페이지 - 목록 페이지에서 생성', tags=TAG_LIST)
async def create_playground(body: dto.CreatePlaygroundInput):
    """
    목록페이지 - 목록 페이지에서 생성
    """
    try:
        res = await svc.create_playground(workspace_id=body.workspace_id, name=body.name, description=body.description, owner_id=body.owner_id, access=body.access, users_id=body.users_id, deploy_type=body.deploy_type)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.put("",summary='목록페이지 - 수정', tags=TAG_LIST)
async def update_playground(body: dto.UpdatePlaygroundInput):
    try:
        res = await svc.update_playground(playground_id=body.playground_id, description=body.description,
                                          access=body.access, owner_id=body.owner_id, users_id=body.users_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.put("/description",summary='목록페이지 - description 수정', tags=TAG_LIST)
async def update_playground_description(body: dto.UpdatePlaygroundDescriptionInput):
    try:
        res = await svc.update_playground_description(playground_id=body.playground_id, description=body.description)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.post("/bookmark", summary='목록페이지 - 북마크 추가', tags=TAG_LIST)
async def add_deployment_bookmark(body: dto.PlaygroundIdInput):
    try:
        user_id = get_user_id()
        res = await svc.add_playground_bookmark(playground_id=body.playground_id, user_id=user_id)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))

@playgrounds.delete("/bookmark", summary='목록페이지 - 북마크 삭제', tags=TAG_LIST)
async def delete_deployment_bookmark(body: dto.PlaygroundIdInput):
    try:
        user_id = get_user_id()
        res = await svc.delete_playground_bookmark(playground_id=body.playground_id, user_id=user_id)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))

# options ===================================================================================
@playgrounds.put('/options', summary='상세페이지 - Option 저장(model, rag, prompt 전체)', tags=TAG_PLAYGROUND)
async def update_playground_options(body: dto.UpdatePlaygroundOptionsInput):
    """
    ## INPUT
    ### Togle: 활성화 버튼, required   
        is_rag: bool
        is_prompt: bool
        accelerator: Optional[bool] = Field(default=False, description="jonathan accelerator")

    ### model
        model_type: huggingface or commit  
        model_huggingface_id: huggingface일때 model id 입력 (GET /model)
        model_allm_name: allm일때 model name 입력 (GET /model)
        model_allm_commit_name: allm일때 model commit name 입력 (GET /model/commit)

    ### model parameter: 모델 아래 파라미터 입력값   
        model_temperature
        model_top_p
        model_top_k
        model_repetition_penalty
        model_max_new_tokens  
        
    ### rag
        rag_id : GET /options에서 가져옴  
        rag_chunck_max: 최대 청크 수
        
    ### prompt
        prompt_id: int, prompt id
        prompt_name : GET /options에서 가져옴    
        prompt_commit_name : GET /prompt/commit에서 가져옴  
        prompt_system_message : 프롬프트 system에 들어간 값  
        prompt_system_message : 프롬프트 user에 들어간 값  
    """
    try:
        res = await svc.update_playground_options(playground_id=body.playground_id,
                is_rag=body.is_rag, is_prompt=body.is_prompt, accelerator=body.accelerator,
                # model
                model_type=body.model_type, model_huggingface_id=body.model_huggingface_id, model_huggingface_token=body.model_huggingface_token,
                model_allm_id=body.model_allm_id, model_allm_commit_id=body.model_allm_commit_id, model_info=body.model_info,
                # serving engine
                serving_system=body.serving_system,
                # model_parameter
                model_temperature=body.model_temperature, model_top_p=body.model_top_p, model_top_k=body.model_top_k,
                model_repetition_penalty=body.model_repetition_penalty, model_max_new_tokens=body.model_max_new_tokens,
                # rag
                rag_id=body.rag_id, rag_chunk_max=body.rag_chunk_max,
                # prompt
                prompt_id=body.prompt_id, prompt_name=body.prompt_name, prompt_commit_name=body.prompt_commit_name,
                prompt_system_message=body.prompt_system_message, prompt_user_message=body.prompt_user_message 
            )
        return response(status=1, result=res)
    except Exception as e:
        return response(status=0, message=str(e), result=None)

@playgrounds.get("/users", summary='목록페이지 - Options 생성시 유저리스트 조회', tags=TAG_LIST)
async def get_user_list(workspace_id: int):
    try:
        res = db_user.get_user_list_in_workspace(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        return response(status=0, message=str(e), result=[])


# model ===================================================================================
@playgrounds.get("/model", summary='상세페이지 - Options model 불러오기: huggingface model, allm model', tags=TAG_PLAYGROUND)
async def get_playground_model_list(workspace_id: int, search: str = None, is_mine: bool = False):
    """
    ### OUTPUT
        {
            # 허깅페이스 모델 리스트
            "hf_model_list": [
                string, string, ....
            ],
            # ALLM 모델 리스트
            "allm_model_list" : [
                {
                    "name": "Llama3",
                    "id": 1,
                    "owner": "daniel"
                },{},{},...
            ]
        }
    """
    try:
        user_name, _ = get_auth()
        res = await svc.get_playground_model_list(workspace_id=workspace_id, model_name=search, is_mine=is_mine, user_name=user_name)
        return response(status=1, result=res)
    except Exception as e:
        return response(status=0, message=str(e), result=[])

@playgrounds.post("/option/huggingface-token-check", summary='상세페이지 - Options model 불러오기 - huggingface private 토큰 체크', tags=TAG_PLAYGROUND)
async def check_huggingface_token(huggingface_token : str = Body(...)):
    try:
        res = None
        res = await svc.check_model_access(token=huggingface_token)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@playgrounds.post("/model/huggingface", summary='상세페이지 - Options model 불러오기 - huggingface private 모델', tags=TAG_PLAYGROUND)
async def get_playground_model_hf_private_list(body: dto.PosHuggingfaceModelInput):
    """
    ### !!! token은 Login 방식처럼 프론트 암호화 해서 전달부탁드립니다!!!
    """
    try:
        res = await svc.get_hugging_face_model(model_name=body.model_name, huggingface_token=body.huggingface_token, private=body.private)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@playgrounds.get("/model/commit", summary='상세페이지 - Options model 불러오기 - allm -> commit list', tags=TAG_PLAYGROUND)
async def get_playground_model_commit_list(model_id: int, search: str = None, is_mine: bool = False):
    """
    """
    try:
        user_name, _ = get_auth()
        res = await svc.get_playground_model_commit_list(model_id=model_id, commit_name=search, is_mine=is_mine, user_name=user_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# rag ===================================================================================
@playgrounds.get("/rag", summary='상세페이지 - Options rag 불러오기', tags=TAG_PLAYGROUND)
async def get_playground_rag_list(workspace_id: int, search: str = None, is_mine: bool = False):
    """
    # TODO rag 저장할때 어떤 값들을 저장할지는 아직 미정, 기획이 크게 바뀌지 않는한 전달하는 파라미터만 추가될 것 같음
    """
    try:
        user_name, _ = get_auth()
        res = await svc.get_playground_rag_list(workspace_id=workspace_id, rag_name=search, is_mine=is_mine, user_name=user_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# prompt ===================================================================================
@playgrounds.get("/prompt", summary='상세페이지 - Options prompt 불러오기', tags=TAG_PLAYGROUND)
async def get_playground_prompt_list(workspace_id: int, search: str = None, is_mine: bool = False):
    """
    """
    try:
        user_name, _ = get_auth()
        res = await svc.get_playground_prompt_list(workspace_id=workspace_id, prompt_name=search, is_mine=is_mine, user_name=user_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@playgrounds.get("/prompt/commit", summary='상세페이지 - Options prompt 불러오기 - prompt -> commit list', tags=TAG_PLAYGROUND)
async def get_playground_prompt_commit_list(prompt_id: int, search: str = None, is_mine: bool = False):
    """
    """
    try:
        user_name, _ = get_auth()
        res = await svc.get_playground_prompt_commit_list(prompt_id=prompt_id, commit_name=search, is_mine=is_mine, user_name=user_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# 실행 관련 기능 ==========================================================
# - 배포, 중지, 모니터링 deployment id

@playgrounds.get("/instance", summary='배포 - options, 인스턴스 리스트', tags=TAG_DEPLOYMENT)
async def get_playground_deployment_options(playground_id: int):
    """
    ### OUTPUT
        [
            {
                "instance_id": 18, # instance_id
                "instance_allocate": 3, # instance 총 개수
                "cpu_allocate": 12.0,
                "ram_allocate": 50.0,
                "gpu_allocate": 1.0,
                "resource_name": "NVIDIA TITAN RTX",
                "instance_type": "GPU",
                "instance_name": "TITAN RTX.1.12.50"
            }, {}, {}, ...
        ]
    """
    try:
        res = await svc.get_playground_instance_options(playground_id=playground_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.get("/monitoring", summary='배포 - options, 모니터링 ID LIST', tags=TAG_DEPLOYMENT)
async def get_playground_deployment_monitoring(playground_id: int):
    """
    모니터링 페이지 -> /user/workspace/4/deployments/{deployment_id}/dashboard 에서 사용하는 API 호출   
    out으로 나오는 deployment_id를 통해 API 호출

    init_deployment
        False일 경우, 초기 배포 시작 안한 상태
        True일 경우, 초기 배포 이미 한 상태
    ---
    ### OUTPUT
        {
            "playground_id": int, playground 배포 id
            "embedding_id": int, 임베딩 배포 id
            "reranker_id": int, 리랭커 배포 id
        }
    """
    try:
        res = await svc.get_playground_deployment_monitoring(playground_id=playground_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.post("/start", summary='배포 - 배포 실행, 재시작', tags=TAG_DEPLOYMENT)
async def run_playground(body: dto.RunPlaygroundInput):
    """
    배포 실행
    ---
    ### INPUT
        playground_id: int
        ---
        model_instance_id: Optional[int], 모델 인스턴스 id
        model_instance_count: Optional[int], 모델 인스턴스 할당량
        model_gpu_count: Optional[int], 모델 GPU 할당량
        ---
        embedding_instance_id: Optional[int], 임베딩 인스턴스 id
        embedding_instance_count: Optional[int], 임베딩 인스턴스 할당량
        embedding_gpu_count: Optional[int], 임베딩 GPU 할당량
        ---
        reranker_instance_id: Optional[int], 리랭커 인스턴스 id
        reranker_instance_count: Optional[int], 리랭커 인스턴스 할당량
        reranker_gpu_count: Optional[int], 리랭커 GPU 할당량
    """
    try:
        user_name, _ = get_auth()
        res = await svc.start_playground(user_name=user_name, playground_id=body.playground_id, 
            # 모델 자원할당
            model_instance_id=body.model_instance_id, model_instance_count=body.model_instance_count, model_gpu_count=body.model_gpu_count,
            # 임베딩 자원할당
            embedding_instance_id=body.embedding_instance_id, embedding_instance_count=body.embedding_instance_count, embedding_gpu_count=body.embedding_gpu_count,
            # 리랭커 자원할당
            reranker_instance_id=body.reranker_instance_id, reranker_instance_count=body.reranker_instance_count, reranker_gpu_count=body.reranker_gpu_count,
            # 재시작
            restart=body.restart
        )
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.post("/pipeline-deploy", summary='배포 - 파이프라인 s2s 클러스터 배포(#4)', tags=TAG_DEPLOYMENT)
async def pipeline_deploy(body: dto.PipelineDeployInput):
    """통합 파이프라인 llm_deploy 노드의 클러스터 배포 — create+모델바인딩+start 원자 수행.
    fb_pipeline executor 전용 s2s. 상태는 GET /status/{playground_id} 로 폴링."""
    try:
        res = await svc.pipeline_deploy(
            workspace_id=body.workspace_id, model_id=body.model_id,
            user_name=body.user_name, model_instance_id=body.model_instance_id,
            model_commit_id=body.model_commit_id, name=body.name,
            model_instance_count=body.model_instance_count,
            model_gpu_count=body.model_gpu_count,
            prompt_system_message=body.prompt_system_message)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.post("/dual-session", summary='추론 - 이중모델 세션 동시 배포(4.2)', tags=TAG_DEPLOYMENT)
async def create_dual_session(body: dto.CreateDualSessionInput, request: Request):
    """이중모델 추론 세션 생성 — 프롬프트생성 모델(LLM1)+추론 모델(LLM2)을 동시 배포(co-provision).
    각 모델은 기존 배포 경로로 올라가고 부모(추론)-자식(프롬프트생성) playground 를 링크한다.
    상태는 GET /status/{session_playground_id} 로 폴링(부모+자식 둘 다 running 시 running)."""
    _log_deprecation(request, request.url.path)
    try:
        user_name, _ = get_auth()
        res = await svc.create_dual_session(
            workspace_id=body.workspace_id, name=body.name, user_name=user_name,
            prompt_gen_model_id=body.prompt_gen_model_id, inference_model_id=body.inference_model_id,
            model_instance_id=body.model_instance_id,
            prompt_gen_commit_id=body.prompt_gen_commit_id, inference_commit_id=body.inference_commit_id,
            model_instance_count=body.model_instance_count, model_gpu_count=body.model_gpu_count,
            prompt_gen_gpu_count=body.prompt_gen_gpu_count, inference_gpu_count=body.inference_gpu_count)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.post("/dual-session/shell", summary='추론 - 이중모델 세션 셸 생성(구성 전)', tags=TAG_DEPLOYMENT)
async def create_dual_shell(body: dto.CreateDualShellInput):
    """이중모델 세션 셸 생성 — 모델/자원 없이 세션 행만(단일 POST /playgrounds 대칭).
    LLM1/LLM2·GPU 선택과 실제 배포는 상세의 POST /playgrounds/dual-session/provision 에서."""
    try:
        user_name, _ = get_auth()
        res = await svc._create_dual_shell_with_metadata(
            workspace_id=body.workspace_id, name=body.name, user_name=user_name,
            description=body.description, access=body.access, owner_id=body.owner_id,
            users_id=body.users_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.put("/dual-session/options", summary='추론 - 이중모델 세션 구성 저장', tags=TAG_DEPLOYMENT)
async def configure_dual_session(body: dto.ProvisionDualInput):
    """child upsert + 양쪽 모델 bind + 링크만 수행한다. 실제 배포는 POST /dual-session/start가 담당한다."""
    try:
        user_name, _ = get_auth()
        res = await svc.configure_dual_session(
            playground_id=body.playground_id, user_name=user_name,
            prompt_gen_model_id=body.prompt_gen_model_id, inference_model_id=body.inference_model_id,
            model_instance_id=body.model_instance_id,
            prompt_gen_commit_id=body.prompt_gen_commit_id, inference_commit_id=body.inference_commit_id,
            model_instance_count=body.model_instance_count, model_gpu_count=body.model_gpu_count,
            prompt_gen_gpu_count=body.prompt_gen_gpu_count, inference_gpu_count=body.inference_gpu_count,
            prompt_gen_params=body.prompt_gen_params, inference_params=body.inference_params)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.post("/dual-session/start", summary='추론 - 이중모델 세션 시작', tags=TAG_DEPLOYMENT)
async def start_dual_session(body: dto.PlaygroundIdInput):
    """저장된 구성을 LLM1(child) → LLM2(parent) 순서로 시작한다."""
    try:
        user_name, _ = get_auth()
        res = await svc.start_dual_session(
            playground_id=body.playground_id, user_name=user_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@playgrounds.post("/dual-session/restart", summary='추론 - 이중모델 세션 전체 재시작', tags=TAG_DEPLOYMENT)
async def restart_dual_session(body: dto.PlaygroundIdInput):
    """부모/자식 어느 id든 저장 링크의 부모로 정규화한 뒤 양쪽을 함께 재시작한다."""
    try:
        user_name, _ = get_auth()
        res = await svc.restart_dual_session(
            playground_id=body.playground_id, user_name=user_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@playgrounds.post("/dual-session/provision", summary='추론 - 이중모델 세션 배포 실행', tags=TAG_DEPLOYMENT)
async def provision_dual_session(body: dto.ProvisionDualInput):
    """하위호환 배포 실행 — PUT options + POST start를 한 호출로 이어 실행한다."""
    try:
        user_name, _ = get_auth()
        res = await svc.provision_dual_session(
            playground_id=body.playground_id, user_name=user_name,
            prompt_gen_model_id=body.prompt_gen_model_id, inference_model_id=body.inference_model_id,
            model_instance_id=body.model_instance_id,
            prompt_gen_commit_id=body.prompt_gen_commit_id, inference_commit_id=body.inference_commit_id,
            model_instance_count=body.model_instance_count, model_gpu_count=body.model_gpu_count,
            prompt_gen_gpu_count=body.prompt_gen_gpu_count, inference_gpu_count=body.inference_gpu_count,
            prompt_gen_params=body.prompt_gen_params, inference_params=body.inference_params)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.post("/stop", summary='배포 - 중지', tags=TAG_DEPLOYMENT)
async def stop_playground(body: dto.PlaygroundIdInput):
    """
    """
    try:
        res = await svc.stop_playground(playground_id=body.playground_id)
        if not res:
            return response(status=0, message="플레이그라운드 중지에 실패했습니다", result=res)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

# 실행 관련 기능 ==========================================================
@playgrounds.get("/test/options", summary='테스트 - 옵션: 데이터셋 리스트, 테스트 URL', tags=TAG_TEST)
async def get_test_options(playground_id: int):
    """
    ### 테스트 실행방법
        테스트실행: POST, 테스트 URL로 요청
        테스트입력 파라미터: 
            input_type: str, 질문일때 "question", 데이터셋일때 "dataset"
            input: 질문일때 str, 데이터셋일때 input
            session_id: 세션아이디 JF-session
    ---            
    ### OUTPUT
        {
            # 데이터셋 리스트
            
            "dataset_list": [
                {
                    "id": 3,
                    "name": "llm-dataset",
                    "access": 1,
                    "create_user_name": "daniel",
                    "workspace_id": 4
                },{},{}, ....
            ],
            # 테스트 URL
            "test_url": "http://192.168.0.150/deployment/h617edfe2b5a0518cd985bc593cf4e69e"
        }
    """
    try:
        res = await svc.get_test_options(playground_id=playground_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.get("/test/dataset", summary='테스트 - 옵션: 데이터셋 - 학습 데이터', tags=TAG_TEST)
async def get_test_dataset_options(dataset_id: int):
    """
    ### OUTPUT
        [
            {
                "name": "/datasets/1/llm-datasetwikimedia___wikipedia/dataset_info.json",
                "input": "파일 내용",
                "owner": "생성자"
            }, {}, {}, ...
        ]
    """
    try:
        user_name, _ = get_auth()
        res = await svc.get_test_dataset_options(dataset_id=dataset_id, user_name=user_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.get("/test/log", summary='테스트 - 테스트기록, 시스템로그', tags=TAG_TEST)
async def get_test_log(playground_id: int):
    """
    플레이그라운드 실행관련 - 테스트 - 테스트 기록, 시스템 로그 조회  
    플레이그라운드 종료하면 로그 삭제됨
    
    ### OUTPUT
        [
            {
                "type": "question",
                "input": "나는 프로그래머야",
                "output": "훌륭하십니다! 프로그래머로서 어떤 분야에 특히 관심이 있으신가요? 도움이 필요하신 부분이 있으면 언제든지 물어보세요.",
                "model": "client=<openai.resources.chat.completions.Completions object at 0x7fd5075eca10> async_client=<openai.resources.chat.completions.AsyncCompletions object at 0x7fd508ab7490> openai_api_key=SecretStr('**********') openai_proxy=''",
                "rag": null,
                "prompt": "input_variables=['input'] optional_variables=['history'] input_types={'history': typing.List[typing.Union[langchain_core.messages.ai.AIMessage, langchain_core.messages.human.HumanMessage, langchain_core.messages.chat.ChatMessage, langchain_core.messages.system.SystemMessage, langchain_core.messages.function.FunctionMessage, langchain_core.messages.tool.ToolMessage]]} partial_variables={'history': []} messages=[SystemMessagePromptTemplate(prompt=PromptTemplate(input_variables=[], template='You are a knowledgeable assistant that provides clear.')), HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=['input'], template='{input}')), MessagesPlaceholder(variable_name='history', optional=True)]",
                "start_datatime": "2024-11-18 09:51:55",
                "end_datatime": "2024-11-18 09:51:56",
                "response_time": 1.0
            }, {}, {}, ...
        ]
    """
    try:
        res = await svc.get_test_log(playground_id=playground_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
    
@playgrounds.get("/test/download", summary='테스트 - 결과 다운로드', tags=TAG_TEST)
async def get_test_result(playground_id: int):
    """
    플레이그라운드 실행관련 - 테스트 기록 csv 다운로드
    """
    try:
        res = await svc.get_test_download(playground_id=playground_id)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.post("/test", summary='테스트 - 테스트 실행', tags=TAG_TEST)
async def post_test(body: dto.PlaygroundTestInput, request: Request):
    """
    network_load: 없음 0, 저 1, 중 2, 고3
    """
    try:
        # 이중모델 추론: question 타입에서 LLM1→LLM2 체인.
        #  - 저장 링크가 있으면 그 LLM1만 허용하고, 요청값 충돌은 배포 쌍 오염을 막기 위해 거부.
        #  - 링크가 없는 단일 세션만 PromptCom 수동 체인의 요청 LLM1을 하위호환으로 허용.
        if (body.test_type or "question") == "question":
            prompt_gen_id = await _resolve_request_prompt_gen(
                body.playground_id,
                body.prompt_gen_playground_id,
                manual_request=request,
            )
            if prompt_gen_id:
                res, message = await svc.playground_dual_test(
                    playground_id=body.playground_id,
                    prompt_gen_playground_id=prompt_gen_id,
                    test_question=body.test_question, session_id=body.session_id,
                    system_prompt=body.system_prompt, examples=body.dual_examples,
                    external_payload=body.external_payload)
                return response(status=1, result=res, message=message)
        res, message = await svc.playground_test(playground_id=body.playground_id, test_type=body.test_type,
                                        test_dataset_id=body.test_dataset_id, test_dataset_filename=body.test_dataset_filename,
                                        test_question=body.test_question, session_id=body.session_id,
                                        network_load=body.network_load,
                                        external_payload=body.external_payload)
        return response(status=1, result=res, message=message)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@playgrounds.post("/dual-session/{playground_id}/invoke", summary='게시 이중모델 합성 추론', tags=TAG_TEST)
async def invoke_dual_session(playground_id: int, body: dto.DualInvokeInput):
    """Kong 외부 게시용 합성 진입점 — LLM1 id는 요청이 아니라 저장된 세션 링크에서만 파생한다."""
    try:
        if (body.test_type or "question") != "question":
            raise Exception("dual published API supports test_type=question")
        prompt_gen_id = await svc.resolve_dual_prompt_gen(playground_id)
        if not prompt_gen_id:
            raise Exception("configured dual session not found")
        res, message = await svc.playground_dual_test(
            playground_id=playground_id,
            prompt_gen_playground_id=prompt_gen_id,
            test_question=body.test_question,
            session_id=body.session_id,
            external_payload=body.external_payload)
        return response(status=1, result=res, message=message)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@playgrounds.post("/dual-batch", summary='추론 - 이중모델 데이터셋 일괄(4.3)', tags=TAG_TEST)
async def dual_batch_test(body: dto.DualBatchInput, request: Request):
    """이중모델 세션의 데이터셋 일괄 추론 — N 샘플에 LLM1→LLM2 체인 + BLEU/ROUGE 채점.
    prompt_gen 미지정 시 세션 링크에서 서버 파생(교차테넌트 벡터 회피)."""
    _log_deprecation(request, request.url.path)
    try:
        prompt_gen_id = await _resolve_request_prompt_gen(
            body.playground_id, body.prompt_gen_playground_id)
        res, message = await svc.dual_batch_test(
            playground_id=body.playground_id, prompt_gen_playground_id=prompt_gen_id,
            dataset_id=body.test_dataset_id, filename=body.test_dataset_filename,
            sample_count=body.sample_count, metrics=body.metrics, session_id=body.session_id,
            system_prompt=body.system_prompt, examples=body.dual_examples,
            external_payload=body.external_payload)
        return response(status=1, result=res, message=message)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

# path parmater ==========================================================
@playgrounds.get("/status/{playground_id}", summary='플레이그라운드 상세페이지 상태 (오른쪽 상단)', tags=TAG_PLAYGROUND)
async def get_playground_status(playground_id: int, request: Request):
    """
    """
    async def event_generator():
        old_history = None
        last_sent_time = datetime.now()
        try:
            while True:
                await asyncio.sleep(1)
                if await request.is_disconnected():
                    break
                result = await svc.get_playground_status(playground_id)
                current_time = datetime.now()

                if result != old_history:
                    old_history = result
                    yield f"data: {json.dumps(result)}\n\n"
                elif (current_time - last_sent_time).total_seconds() >= 30:
                    # 45초가 지나면 프론트에서 끊어지므로 계속 연결을 유지하기 위해 30초마다 보내줌
                    last_sent_time = current_time
                    yield f"data: \n\n"
        except Exception as e:
            # 예외 처리 및 로그 남기기
            traceback.print_exc()
            print(f"Exception in SSE stream: {e}")
        finally:
            # 연결이 끊어졌을 때의 후속 처리
            print(f"Connection closed for playground {playground_id}")
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@playgrounds.get("/batch/sse", summary='추론 - 데이터셋 일괄(스트리밍, 단독·이중 공용)', tags=TAG_TEST)
@playgrounds.get("/dual-batch/sse", include_in_schema=False, tags=TAG_TEST)  # 구 경로(하위호환)
async def batch_sse(request: Request, playground_id: int, test_dataset_id: int,
                    test_dataset_filename: str, sample_count: int = 5,
                    metrics: str = None, output_type: str = None):
    """데이터셋 일괄 추론을 SSE 로 스트리밍 — 샘플 완료마다 event 를 보낸다.
    동기 POST /dual-batch 는 샘플당 ~16s × N 이라 게이트웨이 read timeout(60s)에서 504 가 됨.
    EventSource 는 GET 만 가능해 파라미터는 query 로 받고, 외부 SDS 출력 옵션은 output_type 만 노출
    (이미지/AIS 는 데이터셋 행에서 per-sample 로 읽음).
    단독·이중 공용 — resolve_dual_prompt_gen 이 이중 세션이면 LLM1 을 파생하고 단독이면 None 을
    주며, batch_stream 이 그 유무로 LLM1 단계를 켜고 끈다(단독 SDS 도 같은 경로로 배치 가능).
    session_id 는 query 로 받지 않는다 — 세션 자격증명이 URL(액세스로그/브라우저 히스토리)에
    남으므로, 다른 SSE 와 동일하게 jf-Session 헤더에서 읽는다."""
    if request.url.path.rstrip("/").endswith("/dual-batch/sse"):
        _log_deprecation(request, request.url.path)
    session_id = request.headers.get("jf-session")
    metric_list = [m.strip() for m in (metrics or "").split(",") if m.strip()] or None
    ext_payload = {"output_type": output_type} if output_type else None

    async def event_generator():
        agen = None
        try:
            # 이중이면 LLM1 id, 단독이면 None → batch_stream 이 모드를 결정한다.
            prompt_gen_id = await svc.resolve_dual_prompt_gen(playground_id)
            agen = svc.batch_stream(
                playground_id=playground_id, prompt_gen_playground_id=prompt_gen_id,
                dataset_id=test_dataset_id, filename=test_dataset_filename,
                sample_count=sample_count, metrics=metric_list, session_id=session_id,
                external_payload=ext_payload).__aiter__()
            while True:
                # 다음 이벤트를 기다리는 동안 keepalive 를 보낸다 — 샘플 1건이 60s 를 넘으면
                #   (SDS 지연 등) 게이트웨이 유휴 타임아웃이 스트림을 끊기 때문. status SSE 동형.
                #   대기 중 disconnect 도 확인 → 끊긴 클라이언트에 다음 샘플 추론을 낭비하지 않음.
                nxt = asyncio.ensure_future(agen.__anext__())
                while True:
                    done, _ = await asyncio.wait({nxt}, timeout=20)
                    if nxt in done:
                        break
                    if await request.is_disconnected():
                        nxt.cancel()
                        return
                    yield "data: \n\n"
                try:
                    ev = nxt.result()
                except StopAsyncIteration:
                    break
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if await request.is_disconnected():
                    break
        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            # 제너레이터 확정 종료(중단 시 in-flight 정리를 GC 에 맡기지 않음)
            if agen is not None:
                try:
                    await agen.aclose()
                except Exception:
                    traceback.print_exc()
            print(f"dual-batch SSE closed for playground {playground_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@playgrounds.get("/status-sync/{playground_id}", summary='배포 상태 단건 JSON(s2s 폴링용)', tags=TAG_DEPLOYMENT)
async def get_playground_status_sync(
    playground_id: int, request: Request, skip_dual: bool = False
):
    """SSE /status 와 동일 상태를 단건 JSON 으로 반환 — fb_pipeline executor 폴링용
    (SSE 스트림은 executor 의 response.json() 으로 파싱 불가).
    skip_dual=true: 이중 세션에서 부모(LLM2) 단독 상태만 반환하는 구 계약 호환용.
    기본 응답은 aggregate status와 LLM1/LLM2 components를 함께 반환한다."""
    if skip_dual:
        _log_deprecation(
            request, request.url.path, surface="skip_dual_true")
    try:
        # skip_dual은 기존 호출자 의미를 그대로 보존한다. 새 계약은 기본 호출에서
        # aggregate+components를 함께 내려 별도 parent/child 요청이 필요 없다.
        res = (
            await svc.get_playground_status(playground_id, _skip_dual=True)
            if skip_dual
            else await svc.get_playground_status_detail(playground_id)
        )
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.get("/info/{playground_id}", summary='플레이그라운드 목록에서 수정할때 사용', tags=TAG_LIST)
async def get_playground_info(playground_id: int):
    try:
        res = await svc.get_playground_info(playground_id=playground_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.get("/{playground_id}", summary='플레이그라운드 상세페이지 조회', tags=TAG_PLAYGROUND)
async def get_playground(playground_id: int):
    """
    """
    try:
        res = await svc.get_playground(playground_id=playground_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@playgrounds.delete("/{id_list}", summary='목록페이지 - 플레이그라운드 삭제', tags=TAG_LIST)
async def delete_playground(id_list):
    """
    INPUT  
        id_list: str = 1,2,3
    """
    try:
        # path param 은 타입이 없으므로 여기서 int 로 좁힌다(DB 레이어 placeholder 바인딩과 2중 방어).
        # 비정수가 섞이면 삭제를 아예 시도하지 않고 검증 실패로 돌려준다.
        try:
            id_list = [int(x) for x in id_list.split(',') if x.strip() != '']
        except (TypeError, ValueError):
            return response(status=0, message="id_list must be comma-separated integers", result=None)
        if not id_list:
            return response(status=0, message="id_list is empty", result=None)
        res = await svc.delete_playground(id_list=id_list)
        if not res:
            # stop 과 동일 규약 — teardown/합성 Kong 정리 실패 시 서비스가 False 를 돌려준다.
            #   status=1 로 감싸면 "삭제됨"으로 보이는데 행·Kong 리소스가 남아 재시도 단서가 사라진다.
            return response(status=0, message="플레이그라운드 삭제에 실패했습니다", result=res)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
