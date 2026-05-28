from fastapi import APIRouter, Request, Depends, Header, Body
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional
import traceback, asyncio, json
from datetime import datetime, timedelta
from playground import service as svc
from playground import dto
from utils.resource import response, get_user_id, get_auth
from utils.msa_db import db_user



TAG_LIST = ['List']
TAG_PLAYGROUND = ['Playground']
TAG_DEPLOYMENT = ['Deployment']
TAG_TEST = ['TEST']
TAG_ACCEL = ['ACCEL']


playgrounds = APIRouter(
    prefix = "/playgrounds"
)

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

@playgrounds.post("",summary='목록페이지 - 목록 페이지에서 생성', tags=TAG_LIST)
async def create_playground(body: dto.CreatePlaygroundInput):
    """
    목록페이지 - 목록 페이지에서 생성
    """
    try:
        res = await svc.create_playground(workspace_id=body.workspace_id, name=body.name, description=body.description, owner_id=body.owner_id, access=body.access, users_id=body.users_id)
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

@playgrounds.post("/stop", summary='배포 - 중지', tags=TAG_DEPLOYMENT)
async def stop_playground(body: dto.PlaygroundIdInput):
    """
    """
    try:
        res = await svc.stop_playground(playground_id=body.playground_id)
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
async def post_test(body: dto.PlaygroundTestInput):
    """
    network_load: 없음 0, 저 1, 중 2, 고3
    """
    try:
        res, message = await svc.playground_test(playground_id=body.playground_id, test_type=body.test_type,
                                        test_dataset_id=body.test_dataset_id, test_dataset_filename=body.test_dataset_filename,
                                        test_question=body.test_question, session_id=body.session_id,
                                        network_load=body.network_load)
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
    id_list = id_list.split(',')
    try:
        res = await svc.delete_playground(id_list=id_list)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)