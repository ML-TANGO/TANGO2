import sys, os, traceback, json, re, uvicorn, asyncio
sys.path.append('/addlib')
from deployment_api_deco import api_monitor
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import settings, db
from pathlib import Path

file_path = __file__
file_name = os.path.basename(file_path)
file_name = os.path.splitext(file_name)[0]

# langchain =======================================================================
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_unstructured import UnstructuredLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_milvus import Milvus
from langchain_core.load import dumpd, dumps, load, loads
from huggingface_hub import login
from langchain_milvus.retrievers import MilvusCollectionHybridSearchRetriever

import torch

# settings =======================================================================
# milvus
milvus_collection_name = settings.MILVUS_COLLECTION_NAME
milvus_connection_args = settings.MILVUS_CONNECTION_ARGS


# rag
rag_id = settings.LLM_RAG_ID
chunk_len = int(settings.LLM_RAG_CHUNK_LEN)

# rag_subtype
if "retrieval" in settings.LLM_TYPE: 
    rag_sub_type="creating"
else:
    rag_sub_type="test"

# model 초기 로드
# ------------------------------------------------------
model_name = settings.LLM_MODEL_HUGGINGFACE_ID
huggingface_api_token = settings.LLM_HUGGINGFACE_API_TOKEN

try:
    login(token=huggingface_api_token, add_to_git_credential=True)
except:
    pass
# ------------------------------------------------------

model_kwargs = dict()
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model_kwargs["device"] = device
# model_token = settings.LLM_MODEL_HUGGINGFACE_TOKEN
# if model_token:
#     model_kwargs["token"] = model_token
# ------------------------------------------------------
embedding_model = HuggingFaceEmbeddings(model_name=model_name, model_kwargs=model_kwargs)
# ------------------------------------------------------


# global variable ------------------------------------
# status
rag_status = "creating"
rag_result = []
rag_retriever = None
vector_store = None

"""
# TEST OPENAI
from langchain_openai import ChatOpenAI
# OpenAI API Key는 환경 변수에서 가져옴 (OPENAI_API_KEY)
if 'OPENAI_API_KEY' not in os.environ:
    raise ValueError("OPENAI_API_KEY environment variable is required")
embedding_model = ChatOpenAI(model="gpt-3.5-turbo") 
"""

# embedding =======================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    if rag_sub_type == "creating":
        await embedding()
    else:
        await test_init()
    yield

async def embedding(chunk_size=chunk_len):
    global rag_status, rag_result, rag_retriever
    rag_status = "creating"

    try:
        # 1. 로더 ----------------------------------------------------------------
        data = []
        file_list_pdf = []
        file_list_other = []

        async def load_pdf(file_path):
            try:
                loader = PyPDFLoader(file_path)
                async for page in loader.alazy_load():
                    data.append(page)
            except:
                pass

        for file in Path(f"/jf-data/rags/{rag_id}/").glob('**/*'):
            file_abs_path = str(file.absolute())
            if file.suffix == ".pdf":
                file_list_pdf.append(file_abs_path)
            else:
                file_list_other.append(file_abs_path)


        if len(file_list_pdf) > 0:
            for file in file_list_pdf:
                await load_pdf(file_path=file)
            
        if len(file_list_other) > 0:
            loader = UnstructuredLoader(file_list_other)
            docs = loader.load()
            for doc in docs:
                doc.metadata["page"] = -1 # None으로 넣으면 milvus에서 에러
            data = data + docs
        

        # 2. splitter ----------------------------------------------------------------
        print("splitter")
        chunk_overlap = chunk_size * 0.2
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        documents = splitter.split_documents(data)


        # 3. embedding ----------------------------------------------------------------
        # langchain milvus에서 처리 
        # page_contents = [doc.page_content for doc in documents]
        # embeddings = embedding_model.embed_documents(page_contents) # page_contents 받음

        # 4. vector store ----------------------------------------------------------------
        print("Milvus embedding")
        vector_store = Milvus.from_documents(
            documents = documents, # page_contents x, documents o
            embedding = embedding_model, # 임베딩
            connection_args=milvus_connection_args,
            collection_name =milvus_collection_name,
            drop_old=True, # 이전데이터 삭제
        )

        # 6. retriever ----------------------------------------------------------------
        print("retriever")
        retriever = vector_store.as_retriever()
        rag_retriever = retriever

        # 7. result ----------------------------------------------------------------
        print("result")
        try:
            for i, result in enumerate(documents):
                rag_result.append({
                    "source" : result.metadata.get("source").replace(f"/jf-data/rags/{rag_id}/", ""),
                    "page" : result.metadata.get("page") if result.metadata.get("page") != -1 else None,
                    "content" : result.page_content,
                    "character" : len(result.page_content),
                })
                # break
                # if i == 1:
                    # break # 너무 길어지면 데이터 불러오는 시간이 오래걸려 줄임
            rag_status = "done"
            await db.update_rag_result(rag_id=rag_id, rag_result=json.dumps(rag_result))
        except Exception as e:
            traceback.print_exc()
            rag_status = "error"
            rag_result = str(e)
        print("rag_status", rag_status)
        print("rag_result", rag_result)
        return
    except Exception as e:
        traceback.print_exc()
        rag_status = "error"
        rag_retriever = "error"
        rag_result = str(e)
        await db.update_rag_result(rag_id=rag_id, rag_result="error")
        return
    

# 검색  =======================================================================

async def test_init():
    global vector_store, rag_status
    try:
        vector_store = Milvus(
            embedding_function=embedding_model,
            connection_args=milvus_connection_args,
            collection_name=milvus_collection_name,
        )


        # sparse_search_params = {"metric_type": "IP"}
        # dense_search_params = {"metric_type": "IP", "params": {}}
        # vector_store = MilvusCollectionHybridSearchRetriever(
        #     collection=milvus_collection_name,
        #     rerank=WeightedRanker(0.5, 0.5),
        #     anns_fields=[dense_field, sparse_field],
        #     field_embeddings=[dense_embedding_func, sparse_embedding_func],
        #     field_search_params=[dense_search_params, sparse_search_params],
        #     top_k=3,
        #     text_field=text_field,
        # )

        rag_status = "done"
        print("rag_status", rag_status)
        return
    except Exception as e:
        traceback.print_exc()
        rag_status = "error"
        rag_retriever = "error"
        rag_result = str(e)
        return
    


# API =======================================================================
app = FastAPI(lifespan=lifespan)
print("FASTAPI APP START")

@app.post("/playground")
@api_monitor()
async def get_playground(request: Request):
    global vector_store
    result = {"status": None, "data": None}
    try:
        # Input
        data = await request.json()
        input = data.get("input", "")
        max_chunk = data.get("max_chunk", 3)

        # Result
        retriever = vector_store.similarity_search(input, k=max_chunk)
        print("-----------------")
        print(retriever)
        result["data"] = dumps(retriever)
        result["status"] = "done"
    except Exception as e:
        traceback.print_exc()
        result["status"] = "error"
        result["data"] = str(e)
    return result

@app.post("/test")
@api_monitor()
async def get_test(request: Request):
    """
    rag - test 실행 결과를 받을때 사용
    """
    global vector_store
    result = {"status": None, "data": None}
    try:
        # Input
        data = await request.json()
        input = data.get("input", "")
        max_chunk = data.get("max_chunk", 3)

        # Result
        result_data = []
        search = vector_store.similarity_search(input, k=max_chunk)
        for item in search:
            tmp = {
                "source" : item.metadata.get("source"),
                "content" : item.page_content,
                "character" : len(item.page_content),
            }
            if item.metadata.get("page") != -1:
                tmp["page"] = item.metadata.get("page")
            result_data.append(tmp)
        result["status"] = "done"
        result["data"] = result_data
    except Exception as e:
        traceback.print_exc()
        result["status"] = "error"
        result["data"] = str(e)
    return result

@app.get("/rag")
@api_monitor()
async def get_rag():
    """
    rag - setting - retrieval 실행 결과를 받을때 사용
    """
    global rag_status, rag_result
    result = {"status": None, "data": None}
    try:
        result["status"] = rag_status
        result["data"] = rag_result
    except:
        traceback.print_exc()
        result["status"] = "error"
    return result

@app.get("/")
@api_monitor()
async def health():
    return "JF DEPLOYMENT RUNNING - embedding"

# __main__
if __name__ == "__main__":
    """
    모델 로드를 권장하는 위치
    사용자 영역
    """
    print("Starting Uvicorn...")
    uvicorn.run(f"{file_name}:app", port=8555, host='0.0.0.0', reload=False)
