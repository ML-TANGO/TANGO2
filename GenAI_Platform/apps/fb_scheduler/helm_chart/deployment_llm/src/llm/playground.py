import sys, os, traceback, re, uvicorn, aiofiles, os, time, httpx, traceback
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
sys.path.append('/addlib')
from deployment_api_deco import api_monitor
from uuid import uuid4

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
from langchain_core.prompts import PromptTemplate

# global
import settings, db
LLM_ENGINE = None
LLM_SAMPLING_PARAM = None
LIFESPAN_STATUS = False
LLM_TOKENIZER = None
LLM_MODEL = None  # CPU 모드용 transformers 모델
USE_TRANSFORMERS_DIRECT = False  # CPU 모드 플래그

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global LIFESPAN_STATUS, LLM_ENGINE, LLM_SAMPLING_PARAM, LLM_TOKENIZER
    try:
        # model =========================================================
        model_type = settings.LLM_MODEL_TYPE 
        enable_lora = False
        if model_type == "huggingface":
            input_model = settings.LLM_MODEL_HUGGINGFACE_ID
            input_tokenizer = settings.LLM_MODEL_HUGGINGFACE_TOKEN
            input_auth = settings.LLM_HUGGINGFACE_API_TOKEN
            try:
                try:
                    login(token=settings.LLM_HUGGINGFACE_API_TOKEN, add_to_git_credential=True)
                except:
                    login(token=input_auth, add_to_git_credential=True)
            except:
                pass
            try:
                LLM_TOKENIZER = AutoTokenizer.from_pretrained(input_model, token=input_auth)
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
            try:
                LLM_TOKENIZER = AutoTokenizer.from_pretrained(input_tokenizer)
            except:
                pass

        # lora
        if enable_lora:
            model = PeftModel.from_pretrained(input_model, "/model")
            model = model.merge_and_unload()

            # TODO
            # llm = VLLM()
            # LoRA_ADAPTER_PATH = "path/to/adapter"
            # lora_adapter = LoRARequest("lora_adapter", 1, LoRA_ADAPTER_PATH)
            # llm.invoke("What are some popular Korean street foods?", lora_request=lora_adapter)

        # LLM =========================================================
        # generate 에서 입력
        LLM_SAMPLING_PARAM = SamplingParams(
            temperature=settings.LLM_PARAM_TEMPERATURE,
            top_p=settings.LLM_PARAM_TOP_P,
            top_k=settings.LLM_PARAM_TOP_K,
            repetition_penalty=settings.LLM_PARAM_REPETITION_PENALTY,
            max_tokens=settings.LLM_PARAM_MAX_NEW_TOKENS if settings.LLM_PARAM_MAX_NEW_TOKENS > 0 else 4096,  # 기본값 4096
            stop_token_ids=[128001, 128009] # terminators
            # seed=777,
        )

        # gpu =========================================================
        if torch.cuda.is_available():
            # 첫 번째 GPU 디바이스의 Compute Capability 확인
            device_id = 0
            major, minor = torch.cuda.get_device_capability(device=device_id)
            compute_capability = major + minor / 10.0

            # bfloat16 지원 여부 판단 (Compute Capability 8.0 이상 필요)
            if compute_capability >= 8.0:
                gpu_dtype = "bfloat16"
            else:
                gpu_dtype = "half"

            # gpu_count = torch.cuda.device_count()

            gpu_total_count = settings.LLM_GPU_TOTAL_COUNT
            gpu_server_count = settings.LLM_GPU_SERVER_COUNT
            gpu_count = settings.LLM_GPU_COUNT

            if gpu_total_count == 1:
                # ray 안씀
                distributed_executor_backend = None
                tensor_parallel_size = 1
                pipeline_parallel_size = 1
            else:
                # ray 사용 
                ray.init(
                    address="auto",
                    runtime_env={"working_dir": "/llm"} # 없으면 에러
                )
                print("-- ray cluster info --")
                print(ray.cluster_resources())
                distributed_executor_backend="ray"
                # 각 pod는 하나의 GPU만 볼 수 있으므로
                # tensor_parallel_size는 pod당 GPU 수, pipeline_parallel_size는 pod 수로 설정
                tensor_parallel_size = gpu_count
                pipeline_parallel_size = gpu_server_count

            print('----------------------')
            # max_model_len 자동 계산: 큰 모델의 경우 KV cache 크기 제한
            # GPU blocks에서 사용 가능한 토큰 수 기반으로 설정
            max_model_len = 96  # 기본값: 32K tokens (대부분의 use case에 충분)
            
            engine_args = AsyncEngineArgs(
                model=input_model,
                # quantization="AWQ",
                tensor_parallel_size=tensor_parallel_size, # 노드 당 gpu 수
                gpu_memory_utilization=0.90, # gpu 메모리 사용량
                trust_remote_code=True,
                enable_prefix_caching=True,
                dtype=gpu_dtype,
                enable_lora=enable_lora,
                distributed_executor_backend=distributed_executor_backend,
                pipeline_parallel_size=pipeline_parallel_size, # 노드수
                max_model_len=max_model_len,  # KV cache OOM 방지
                # ray일때 device는 자동
            )
            # TODO !!!!
            # pipeline_parallel_size 노드수
            # tensor_parallel_size 노드 당 gpu수
            # 총 GPU1개, 같은 노드에 pod2개 (pod당 gpu1개) 일경우 안됨??
        else:
            # CPU 모드 - transformers 직접 사용 (vLLM CPU 모드는 불안정)
            print("Running in CPU mode with transformers (vLLM CPU mode has issues)")
            from transformers import AutoModelForCausalLM, TextStreamer
            
            # CPU 모드에서는 vLLM 대신 transformers 직접 사용
            global LLM_MODEL
            LLM_MODEL = AutoModelForCausalLM.from_pretrained(
                input_model,
                token=input_auth if model_type == "huggingface" else None,
                trust_remote_code=True,
                torch_dtype=torch.float16,
                device_map="cpu"
            )
            
            # 토크나이저가 초기화되지 않았다면 다시 시도
            if LLM_TOKENIZER is None:
                try:
                    if model_type == "huggingface":
                        LLM_TOKENIZER = AutoTokenizer.from_pretrained(input_model, token=input_auth)
                    else:
                        LLM_TOKENIZER = AutoTokenizer.from_pretrained(input_tokenizer)
                except Exception as e:
                    print(f"Failed to initialize tokenizer: {e}")
                    # 토크나이저 초기화 실패 시 모델의 토크나이저 사용
                    try:
                        LLM_TOKENIZER = AutoTokenizer.from_pretrained(input_model)
                    except Exception as e2:
                        print(f"Failed to initialize tokenizer from model: {e2}")
            
            # vLLM 엔진 생성하지 않고 transformers 모델 사용 플래그 설정
            global USE_TRANSFORMERS_DIRECT
            USE_TRANSFORMERS_DIRECT = True
            
            # 더미 엔진 (실제로는 사용하지 않음)
            LLM_ENGINE = None

        # GPU 모드일 때만 vLLM 엔진 생성
        if torch.cuda.is_available():
            LLM_ENGINE = AsyncLLMEngine.from_engine_args(engine_args)
        
        LIFESPAN_STATUS = True
        yield
    except:
        traceback.print_exc()
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
    global LLM_ENGINE, LLM_SAMPLING_PARAM, LLM_MODEL, USE_TRANSFORMERS_DIRECT, LLM_TOKENIZER
    try:
        session_id = str(uuid4()) # 고유한 요청 ID 생성 / vllm 0.5 버전 사용시 request_id already error / vllm 0.6은 사용 가능

        # rag
        rag=""
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
                            print("embedding done")
            except Exception as e:
                print("REQUEST RAG Waiting")

            rag_result_data = loads(rag_result.get("data"))
            print("============================================================")
            print("retriever_result", type(rag_result_data), rag_result_data, )
            for data in rag_result_data:
                rag += data.page_content
            print("============================================================")
            print(rag)

        # =====================================================================================================================
        # TODO PROMPT 어떻게 넣을 것인지 개발되어야 함
        # =====================================================================================================================
        # ===== CPU 모드와 GPU(vLLM) 모드 분기 =====
        if USE_TRANSFORMERS_DIRECT:
            # CPU 모드: transformers 직접 사용
            print("Using transformers directly for CPU inference")
            
            # 토크나이저가 None인 경우 처리
            if LLM_TOKENIZER is None:
                raise HTTPException(status_code=500, detail="Tokenizer not initialized. Please check model configuration.")
            
            if settings.LLM_RUN_PROMPT and LLM_TOKENIZER:
                system_message = settings.LLM_PROMPT_SYSTEM_MESSAGE
                user_message = settings.LLM_PROMPT_USER_MESSAGE
                messages = [
                    {"role": "system", "content": rag + system_message},
                    {"role": "user", "content": user_message},
                ]
                try:
                    prompt_string = LLM_TOKENIZER.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
                except:
                    prompt_string = test_input
            else:
                prompt_string = test_input
            
            # transformers 모델로 추론
            inputs = LLM_TOKENIZER(prompt_string, return_tensors="pt")
            
            with torch.no_grad():
                outputs = LLM_MODEL.generate(
                    **inputs,
                    max_new_tokens=settings.LLM_PARAM_MAX_NEW_TOKENS if settings.LLM_PARAM_MAX_NEW_TOKENS > 0 else 4096,  # 기본값 4096
                    temperature=settings.LLM_PARAM_TEMPERATURE if settings.LLM_PARAM_TEMPERATURE > 0 else 1.0,
                    do_sample=True if settings.LLM_PARAM_TEMPERATURE > 0 else False,
                    pad_token_id=LLM_TOKENIZER.eos_token_id
                )
            
            # 결과 디코딩 (입력 부분 제외)
            generated_tokens = outputs[0][inputs['input_ids'].shape[1]:]
            result = LLM_TOKENIZER.decode(generated_tokens, skip_special_tokens=True).strip()
            
        else:
            # GPU 모드: vLLM 사용
            if settings.LLM_RUN_PROMPT:
                system_message = settings.LLM_PROMPT_SYSTEM_MESSAGE
                user_message = settings.LLM_PROMPT_USER_MESSAGE
                messages = [
                                {"role": "system", "content": rag + system_message},
                                {"role": "user", "content": user_message},
                            ]
                try:
                    prompt_string = LLM_TOKENIZER.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
                except:
                    prompt_string = test_input
                result_generator = LLM_ENGINE.generate(prompt_string, sampling_params=LLM_SAMPLING_PARAM, request_id=session_id)
            else:
                # rag X, prompt X
                result_generator = LLM_ENGINE.generate(test_input, sampling_params=LLM_SAMPLING_PARAM, request_id=session_id)
            
            outputs = None
            async for r in result_generator:
                outputs = r

            # result
            print(outputs)
            result = outputs.outputs[0].text.strip()

        try:
            # TODO 어떤 값을 로그에 남길지
            tmp_model = await LLM_ENGINE.get_model_config()
            await db.update_playground_test(db_id=db_id, **{"model" : str(tmp_model.__dict__)})
        except:
            pass

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
    # 상태 체크
    global LIFESPAN_STATUS
    if LIFESPAN_STATUS == False: 
        raise HTTPException(status_code=401, detail="Installing")
    elif LIFESPAN_STATUS == "error":
        raise HTTPException(status_code=402, detail="Model Error")
    
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
        for _input in test_input:
            # DB: 시작 시간
            _, db_id = await db.insert_playground_test(playground_id=settings.LLM_PLAYGROUND_ID, type=test_type)
            start_time = time.time()
            # test
            output = await run_playground(test_input=_input, session_id=session_id, db_id=db_id)
            end_time = time.time()
            # result
            data = {
                "input" : _input,
                "output" : output,
                "time" : end_time - start_time
            }
            result.append(data)
            print(data)
            # DB: 종료 시간
            await db.update_playground_test(db_id=db_id, **{"input" : _input, "output" : output})
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







"""
# langchain

device = 0 if torch.cuda.is_available() else None
try:
    login(token=huggingface_api_token, add_to_git_credential=True)
except:
    pass

# model
model = AutoModelForCausalLM.from_pretrained(input_model, token=input_auth)
# lora ----------------------
if is_source_model_lora:
    model = PeftModel.from_pretrained(input_model, "/model")
    model = model.merge_and_unload()
# ----------------------
tokenizer = AutoTokenizer.from_pretrained(input_tokenizer, token=input_auth)
if tokenizer.pad_token_id is None:
    # Setting `pad_token_id` to `eos_token_id`:50256 for open-end generation
    tokenizer.pad_token = tokenizer.eos_token  # pad_token을 eos_token으로 설정

if model.config.task_specific_params:
    model.config.task_specific_params["text-generation"]["max_length"] = 2048

pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, truncation=True, device=device, **pipeline_kwargs)
llm = HuggingFacePipeline(pipeline=pipe)


# llm = HuggingFacePipeline.from_model_id(model_id=model, task="text-generation", tokenizer=tokenizer, device=device, pipeline_kwargs=pipeline_kwargs) #model_kwargs)

# RAG result
rag_result = None
if playground_run_rag_reranker:
    rag_dns = f"http://deployment-llm-rag-{playground_rag_id}-test-reranker--service:18555"
else:
    rag_dns = f"http://deployment-llm-rag-{playground_rag_id}-test-embedding--service:18555"

while True:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{rag_dns}/playground", json={"max_chunk": 3, "input": test_input}, timeout=1800)
            if response.status_code == 200:
                rag_result = response.json()
                if rag_result.get("status") == "done":
                    print("embedding done")
                    print("rag_result")
                    # print(rag_result)
                    break
            else:
                continue
    except Exception as e:
        print("REQUEST RAG Waiting")
        return "RAG Waiting"

# retriever_result = langchain_loads(rag_result.get("data"))
print("============================================================")
# print("retriever_result", type(retriever_result), retriever_result, )

# # chain
# chain = create_stuff_documents_chain(llm=llm, prompt=prompt, output_parser=StrOutputParser())
# print("============================================================")
# print("chain", chain)

# RAG PROMPT
rag_prompt=("Use the following pieces of retrieved context to answer the question. \n"
            "Do not repeat user question, just answer it. \n\n" 
            "Context: {context} \n")

# https://github.com/huggingface/transformers/blob/main/docs/source/ko/chat_templating.md
# 채팅 템플릿이 있는 모델에, 해당 템플릿을 사용하여 자동으로 처리하도록 함
messages = [
                {"role": "system", "content": rag_prompt + prompt_system_message},
                {"role": "user", "content": prompt_user_message},
                # MessagesPlaceholder("history", optional=True)
            ] # role: "system", "user", "assistant". 아래 add generation prompt True 시 assistance 빈 줄 자동으로 생성.
prompt_string = llm.pipeline.tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
prompt = PromptTemplate(
    template=prompt_string,                
)

print(f"rag_prompt: {rag_prompt}")
print(f"prompt_system_message: {prompt_system_message}")
print(f"prompt_user_message: {prompt_user_message}")

# # rag
retriever_result = langchain_loads(rag_result.get("data"))
formatted_context = "\n".join([doc.page_content for doc in retriever_result])
chain = (
    {"context": lambda x : formatted_context , "question" : RunnablePassthrough()} 
    | prompt | llm | StrOutputParser()  # StrOutputParser() # | AnswerExtractor() 
)    

# chain = (
#     RunnableMap({
#         "context": lambda x: formatted_context, 
#         "question": RunnableWithMessageHistory(get_session_history)
#     })
#     | prompt | llm |   StrOutputParser()  # StrOutputParser() # | AnswerExtractor() 
# )    

# chain_with_history = RunnableWithMessageHistory(
#     chain,
#     get_session_history,
#     input_messages_key="question",
#     history_messages_key="history", # prompt messagePlaceHolder key
# )
# response = chain_with_history.invoke(
#     {"context" : formatted_context, "question": RunnablePassthrough()},
#     config = {"configurable" : {"session_id" : session_id}}
# )

# result
response = chain.invoke(test_input)
"""