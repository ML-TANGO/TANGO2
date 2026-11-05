import sys, os, traceback, re, uvicorn, aiofiles, os, time, httpx
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
sys.path.append('/addlib')
from deployment_api_deco import api_monitor

file_path = __file__
file_name = os.path.basename(file_path)
file_name = os.path.splitext(file_name)[0]

# vllm 
import torch
from vllm import LLM, AsyncEngineArgs, AsyncLLMEngine, SamplingParams
from peft import PeftModel 
from huggingface_hub import login
from transformers import AutoTokenizer
import ray
from langchain_core.load import dumpd, dumps, load, loads

# global
import settings, db
LLM_ENGINE = None
LLM_SAMPLING_PARAM = None
LIFESPAN_STATUS = False


# # NCCL HANDLING =======================================================================
# os.environ['NCCL_DEBUG'] = 'INFO'
# os.environ['NCCL_IB_GID_INDEX'] = '1'
# os.environ['NCCL_ASYNC_ERROR_HANDLING'] = '1'
# os.environ['NCCL_DEBUG_SUBSYS'] = 'GRAPH'
# os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
# os.environ['CUDA_VISIBLE_DEVICES'] = "0,1"
# os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
# os.environ['PYTHONWARNINGS'] = 'ignore:semaphore_tracker:UserWarning'
# os.environ['VLLM_USE_MODELSCOPE'] = 'True'
# os.environ['TORCH_USE_CUDA_DSA'] = '1'
# os.environ['PYTORCH_USE_CUDA_DSA'] = '1'
# os.environ['CUDA_LAUNCH_BLOCKING'] = '1'



@asynccontextmanager
async def lifespan(app: FastAPI):
    global LIFESPAN_STATUS, LLM_ENGINE, LLM_SAMPLING_PARAM

    # gpu =========================================================
    async def determine_dtype():
        if torch.cuda.is_available():
            # 첫 번째 GPU 디바이스의 Compute Capability 확인
            device_id = 0
            major, minor = torch.cuda.get_device_capability(device=device_id)
            compute_capability = major + minor / 10.0

            # bfloat16 지원 여부 판단 (Compute Capability 8.0 이상 필요)
            if compute_capability >= 8.0:
                return "bfloat16"
            else:
                return "half"
        else:
            # GPU가 없는 경우 기본적으로 half 사용 (혹은 원하는 dtype)
            return "half"
        
    gpu_dtype = await determine_dtype()
    gpu_count = torch.cuda.device_count()

    # ray =========================================================
    ray.init(address="auto")

    # model =========================================================
    model_type = settings.LLM_MODEL_TYPE 
    enable_lora = False
    if model_type == "huggingface":
        input_model = settings.LLM_MODEL_HUGGINGFACE_ID
        input_tokenizer = settings.LLM_MODEL_HUGGINGFACE_ID
        input_auth = settings.LLM_MODEL_HUGGINGFACE_TOKEN
        try:
            try:
                login(token=settings.LLM_HUGGINGFACE_API_TOKEN, add_to_git_credential=True)
            except:
                login(token=input_auth, add_to_git_credential=True)
        except:
            pass
    elif model_type == "commit":
        input_model = "/model"
        input_tokenizer = "/tokenizer"
        input_auth = None

        if os.path.exists("/model/source_model"):
            is_source_model_lora = True
            input_model = "/model/source_model"
            enable_lora = True
    # LLM_TOKENIZER = AutoTokenizer.from_pretrained(input_tokenizer, token=input_auth)

    # lora
    if enable_lora:
        model = PeftModel.from_pretrained(input_model, "/model")
        model = model.merge_and_unload()

    # LLM =========================================================
    # generate 에서 입력
    LLM_SAMPLING_PARAM = SamplingParams(
        temperature=settings.LLM_PARAM_TEMPERATURE,
        top_p=settings.LLM_PARAM_TOP_P,
        top_k=settings.LLM_PARAM_TOP_K,
        repetition_penalty=settings.LLM_PARAM_REPETITION_PENALTY,
        max_tokens=settings.LLM_PARAM_MAX_NEW_TOKENS,
        stop_token_ids=[128001, 128009] # terminators
        # seed=777,
    )

    engine_args = AsyncEngineArgs(
        model=input_model,
        # quantization="AWQ",
        tensor_parallel_size=gpu_count, # gpu device 개수 (물리)
        gpu_memory_utilization=0.80, # gpu 메모리 사용량
        trust_remote_code=True,
        enable_prefix_caching=True,
        dtype=gpu_dtype,
        enable_lora=enable_lora,
        distributed_executor_backend="ray",
        # max_model_len=max_model_len, # Model context length. If unspecified, will be automatically derived from the model config.
    )
    LLM_ENGINE = AsyncLLMEngine.from_engine_args(engine_args)
    LIFESPAN_STATUS = True
    yield


# =======================================================================
# dataset 
# =======================================================================
async def get_dataset_input(dataset_id, filename):
    result = []
    try:
        dataset_info = await db.get_dataset(dataset_id=dataset_id)
        dataset_name = dataset_info.get("name")
        dataset_access = "datasets_rw" if dataset_info.get("access") == 1 else "datasets_ro"
        dataset_path = f"/jf-data/dataset/{dataset_access}/{dataset_name}/{filename}"
        try:
            if os.path.exists(dataset_path):
                print(f"파일이 존재합니다: {dataset_path}")
            else:
                print(f"파일이 존재하지 않습니다: {dataset_path}")

            async with aiofiles.open(dataset_path, mode='r', encoding='utf-8') as f:
                lines = await f.readlines()
                for line in lines:
                    result.append(line.strip())
        except:
            traceback.print_exc()
            print("파일 내용 읽기 실패")
    except:
        traceback.print_exc()
    return result



# =======================================================================
# playground 
# =======================================================================
async def run_playground(test_input, session_id, db_id):
    """result stream 방식?"""
    result = None
    global LLM_ENGINE, LLM_SAMPLING_PARAM
    try:
        # rag
        rag_context=""
        if settings.LLM_RUN_RAG:
            if settings.LLM_RUN_RAG_RERANKER:
                rag_dns = f"http://deployment-llm-playground-rag-reranker-{settings.LLM_RAG_ID}--service:18555"
            else:
                rag_dns = f"http://deployment-llm-playground-rag-embedding-{settings.LLM_RAG_ID}--service:18555"

            # RAG result
            rag_result = None
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(f"{rag_dns}/playground", json={"chunk_size": settings.LLM_PLAYGROUND_RAG_CHUNK_MAX, "prompt": test_input}, timeout=1800)
                    if response.status_code == 200:
                        rag_result = response.json()
                        if rag_result.get("status") == "done":
                            print("embedding created")
            except Exception as e:
                print("REQUEST RAG Waiting")

            rag_result_data = loads(rag_result.get("data"))
            print("============================================================")
            print("retriever_result", type(rag_result_data), rag_result_data, )
            for data in rag_result_data:
                rag_context += data.page_content
            print("=================rag_context===========================================")
            print(rag_context)


        # prompt
        prompt=""
        if settings.LLM_RUN_PROMPT:
            # system message += rag
            system_message = settings.LLM_PROMPT_SYSTEM_MESSAGE

            # user message += question
            user_message = settings.LLM_PROMPT_USER_MESSAGE
            keys = re.findall(r"\{(.*?)\}", user_message)
            if len(keys) > 0:
                #user_input = {keys[0] : test_input}
                #user_message = user_message.format(**user_input)
                prompt = "<begin_of_sentence>System: {system_message}\nUser: {user_message}\nContext: {context}\nQuestion: {question}\nAnswer: ".format(
                    system_message=system_message, user_message=user_message, context=rag_context, question=test_input
                )
            else:
                prompt = "<begin_of_sentence>System: {system_message}\nUser: {user_message}\nContext: {context}\nQuestion: {question}\nAnswer: ".format(
                    system_message=system_message, user_message=user_message, context=rag_context, question=test_input
                )
        else:
            pass

        prompt = "<begin_of_sentence>User: You are an assistant for question-answering tasks.\nContext: {context}\nQuestion: {question}\nAnswer:".format(
                context=rag_context, question=test_input)
            # 위의 프롬프트 형식이 apply_chat_template(add_generation?=True) 수행한 결과임
        print("======prompt generate========")
        print(prompt)
        # model
        result_generator = LLM_ENGINE.generate(prompt, sampling_params=LLM_SAMPLING_PARAM, request_id=session_id)
        outputs = None
        async for r in result_generator:
            outputs = r

        # result
        print(outputs)
        result = outputs.outputs[0].text.strip()

        # await db.update_playground_test(db_id=db_id, **{"model" : result_generator})            
        return result
    except Exception as e:
        traceback.print_exc()
        result = str(e)
    return result



app = FastAPI(lifespan=lifespan)
print("FASTAPI APP START")

@app.post("/", description="종합테스트")
@api_monitor()
async def post_llm(request: Request):
    print("playground test start")
    # INPUT
    data = await request.json()
    test_type = data.get("test_type") if data.get("test_type") is not None else "question"
    test_dataset_id = data.get("test_dataset_id")
    test_dataset_filename = data.get("test_dataset_filename")
    test_question = data.get("test_question")
    session_id = data.get("session_id") # history 관리
    try:
        # test input
        if test_type == "dataset":
            test_input = await get_dataset_input(dataset_id=test_dataset_id, filename=test_dataset_filename)
        else:
            test_input = [test_question]
        # test
        result = []
        for input in test_input:
            # DB: 시작 시간
            _, db_id = await db.insert_playground_test(playground_id=settings.LLM_PLAYGROUND_ID, type=test_type)
            start_time = time.time()
            # test
            output = await run_playground(test_input=input, session_id=session_id, db_id=db_id)
            end_time = time.time()
            # result
            data = {
                "input" : input,
                "output" : output,
                "time" : end_time - start_time
            }
            result.append(data)
            print(data)
            # DB: 종료 시간
            await db.update_playground_test(db_id=db_id, **{"input" : input, "output" : output})
        return result
    except Exception as e:
        traceback.print_exc()
    return result

@app.get("/")
@api_monitor()
async def health():
    global LIFESPAN_STATUS
    if LIFESPAN_STATUS == False: 
        raise HTTPException(status_code=401, detail="Installing")
    elif LIFESPAN_STATUS == "error":
        raise HTTPException(status_code=402, detail="Model Error")
    return "JF DEPLOYMENT RUNNING - playground"

if __name__ == "__main__":
    uvicorn.run(f"{file_name}:app", port=8555, host='0.0.0.0')
