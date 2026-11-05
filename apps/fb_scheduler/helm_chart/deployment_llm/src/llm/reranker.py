import sys, os, traceback, json, re, uvicorn, httpx, asyncio, time
sys.path.append('/addlib')
from deployment_api_deco import api_monitor
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import settings, db

file_path = __file__
file_name = os.path.basename(file_path)
file_name = os.path.splitext(file_name)[0]

# langchain =======================================================================
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain.retrievers import ContextualCompressionRetriever
from langchain_milvus import Milvus
from langchain_core.load import dumpd, dumps, load, loads
from huggingface_hub import login

# settings =======================================================================
# milvus
milvus_collection_name = settings.MILVUS_COLLECTION_NAME
milvus_connection_args = settings.MILVUS_CONNECTION_ARGS

# rag
rag_id = settings.LLM_RAG_ID
rag_embedding_run = settings.LLM_RAG_EMBEDDING_RUN
# rag_subtype
if "retrieval" in settings.LLM_TYPE:
    rag_sub_type="retrieval"
else:
    rag_sub_type="test"
embedding_dns = f"http://deployment-llm-rag-{rag_sub_type}-embedding-{settings.LLM_RAG_ID}--service:18555" if rag_embedding_run else None

# model 초기 로드
huggingface_api_token = settings.LLM_HUGGINGFACE_API_TOKEN
reranker_model = HuggingFaceEmbeddings(model_name=settings.LLM_MODEL_HUGGINGFACE_ID)
reranker_encoder = HuggingFaceCrossEncoder(model_name=settings.LLM_MODEL_HUGGINGFACE_ID)
try:
    login(token=huggingface_api_token, add_to_git_credential=True)
except:
    pass

# global variable
# status
rag_status = "creating"
rag_result = []
rag_retriever = None
vector_store = None
base_retriever = None


# reranker  =======================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_milvus()
    await reranker()
    yield

async def init_milvus():
    global vector_store, base_retriever, rag_status
    try:
        if rag_embedding_run:
            # 임베딩이 이미 만들어져야지 실행할텐데 굳이 필요할까?


            print("waiting embedding")
            while True:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(f"{embedding_dns}/rag", timeout=1800)
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("status") == "done":
                                print("embedding created")
                                break
                        else:
                            continue
                except Exception as e:
                    print("try connection embedding")
                    pass

        vector_store = Milvus(
            embedding_function=reranker_model,
            connection_args=milvus_connection_args,
            collection_name=milvus_collection_name,
        )
        base_retriever = vector_store.as_retriever()

        rag_status = "done"
        print("rag_status", rag_status)
        return
    except Exception as e:
        traceback.print_exc()
        rag_status = "error"
        rag_retriever = "error"
        rag_result = str(e)
        return
    

async def reranker(input="", max_chunk=None):
    global rag_status, rag_result, rag_retriever, vector_store, base_retriever
    rag_status = "installing"
    try:
        # 0. vector store 로드 ----------------------------
        print('Milvus vector store load')
        """
        milvus_collection_name = settings.MILVUS_COLLECTION_NAME + "_test" if deployment_type == "test" else settings.MILVUS_COLLECTION_NAME
        vector_store = Milvus(
            embedding_function=reranker_model,
            connection_args=milvus_connection_args,
            collection_name = milvus_collection_name,
        )
        retriever = vector_store.as_retriever()
        """

        # retriever = vector_store.as_retriever(search_kwargs={"k": 1}) # retriever 타입
        # retriever = vector_store.similarity_search(input) # 리스트 타입

        # 1. 압축기 ----------------------------
        print('Reranker compressor')
        if max_chunk:
            compressor = CrossEncoderReranker(model=reranker_encoder, top_n=max_chunk)
        else:
            compressor = CrossEncoderReranker(model=reranker_encoder)

        # 2. 검색기 ----------------------------
        print('Reranker retriever')
        compression_retriever  = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=base_retriever
        )
        rag_retriever = compression_retriever

        # 3. result ----------------------------------------------------------------
        print("============================")
        print('Reranker result')
        retriever_results = compression_retriever.invoke(input)
        print(retriever_results)

        rag_result = []
        for item in retriever_results:
            tmp = {
                "source" : item.metadata.get("source").replace(f"/jf-data/rags/{rag_id}/", ""),
                "content" : item.page_content,
                "character" : len(item.page_content),
            }
            if item.metadata.get("page") != -1:
                tmp["page"] = item.metadata.get("page")
            rag_result.append(tmp)
        rag_status = "done"
        await db.update_rag_result(rag_id=rag_id, rag_result=json.dumps(rag_result))

        return
    except Exception as e:
        traceback.print_exc()
        rag_status = "error"
        await db.update_rag_result(rag_id=rag_id, rag_result="error")
        return


# API =======================================================================
app = FastAPI(lifespan=lifespan)
print("FASTAPI APP START")



@app.post("/playground")
@api_monitor()
async def get_playground(request: Request):
    global rag_retriever
    result = {"status": None, "data": None}
    try:
        # Input
        data = await request.json()
        input = data.get("input", "")
        max_chunk = data.get("max_chunk")

        # Result
        await reranker(max_chunk=max_chunk)
        retriever = rag_retriever.invoke(input)
        print("-----------------")
        print(retriever)
        result["data"] = dumps(retriever)
        result["status"] = "done"
    except:
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
    global rag_retriever
    result = {"status": None, "data": None}
    try:
        # Input
        data = await request.json()
        input = data.get("input")
        max_chunk = data.get("max_chunk")

        # Result
        await reranker(input=input, max_chunk=max_chunk)
        result["status"] = rag_status
        result["data"] = rag_result
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
        await reranker()
        result["status"] = rag_status
        result["data"] = rag_result
    except:
        traceback.print_exc()
        result["status"] = "error"
    return result


@app.get("/")
@api_monitor()
async def health():
    return "JF DEPLOYMENT RUNNING - reranker"

if __name__ == "__main__":
    """
    모델 로드를 권장하는 위치
    사용자 영역
    """
    print("Starting Uvicorn...")
    uvicorn.run(f"{file_name}:app", port=8555, host='0.0.0.0', reload=False)
