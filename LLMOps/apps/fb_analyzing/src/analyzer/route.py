from fastapi import APIRouter, Depends, Request
from typing import List, Annotated, Optional
from analyzer import model
# from upload import service as upload_svc 
from analyzer import service as svc
from utils.resource import response, get_user_id, get_auth
import traceback, asyncio, json
from datetime import datetime
from fastapi.responses import StreamingResponse, JSONResponse

# TODO: 헤더 검증을 통한 사용자 인증 체크

analyzer = APIRouter(
    prefix = "/analyzer"
)

TAG_LIST = ["LIST"]
TAG_ITEM = ["ITEM"]


@analyzer.get("/healthz")
async def healthz():
    res = await svc.check_healthz()
    if res:
        return JSONResponse(status_code=200, content={"status": "healthy"})
    else:
        return JSONResponse(status_code=500, content={"status": "not healthy"})

@analyzer.get("",tags=TAG_LIST)
async def get_analyzer_list(args: model.AnalyzerGetListModel = Depends()):
    workspace_id = args.workspace_id
    user_id = get_user_id()
    res = svc.get_analysis_list(workspace_id=workspace_id, user_id=user_id)
    if res:
        return response(status_code=200, result=res, status=1)
    else:
        return response(status_code=500, message="Get Analyzer Error" , status=0)

@analyzer.post("", tags=TAG_LIST)
async def create_analyzer(body: model.AnalyzerCreateModel):
    try:
        res = svc.create_analyzer(
            name=body.name, description=body.description, instance_id=body.instance_id, instance_allocate=body.instance_allocate,
            access=body.access, owner_id=body.owner_id, workspace_id=body.workspace_id, users_id=body.users_id)
        if res:
            return response(status=1, message = 'Analyzer Create Complete')
        else:
            raise Exception("Analyzer DB Insert Error")
    except Exception as e:
        return response(status=0, message = f"Analyzer Create Fail '{e}' ")

@analyzer.put("", tags=TAG_LIST)
async def update_analyzer(body: model.AnalyzerUpdateModel) :
    try:
        res = svc.update_analyzer(analyzer_id=body.id, description=body.description,
                                  instance_id=body.instance_id, instance_allocate=body.instance_allocate,
                                  access=body.access, owner_id=body.owner_id, users_id=body.users_id)
        if res:
            return response(status = 1, message = 'Analyzer update Complete')
        else:
            raise Exception("Analyzer DB update Error")
    except Exception as e:
        return response(status = 0, message = f"Analyzer update Fail '{e}' ")

@analyzer.post("/bookmark", summary="북마크", tags=TAG_LIST)
def post_analyzer_bookmark(body: model.AnalyzerIdModel):
    try:
        user_id = get_user_id()
        res = svc.add_analyzer_bookmark(analyzer_id=body.analyzer_id, user_id=user_id)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)

@analyzer.delete("/bookmark", summary="북마크", tags=TAG_LIST)
def delete_analyzer_bookmark(body: model.AnalyzerIdModel):
    try:
        user_id = get_user_id()
        res = svc.delete_analyzer_bookmark(analyzer_id=body.analyzer_id, user_id=user_id)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)


# ========================================================================
# Graph
# ========================================================================
@analyzer.post("/graph", tags=TAG_ITEM, summary="데이터분석 그래프 추가")
async def insert_analyzer_graph(body: model.AnalyzerGraphCreateModel):
    """
    ## 그래프유형   
        LINE=0, BAR=1, PIE=2
    """
    try:
        user_id = get_user_id()
        res = await svc.create_analyzer_graph(analyzer_id=body.analyzer_id,
            name=body.name, workspace_id=body.workspace_id, description=body.description,
            dataset_id=body.dataset_id, file_path=body.file_path, graph_type=body.graph_type, column=body.column,
            create_user_id=user_id)
        return response(result=res, status=1)
    except:
        traceback.print_exc()
        return response(message="Get Dataset Error" , status=0)

@analyzer.delete("/graph", tags=TAG_ITEM, summary="데이터분석 그래프 전체, 선택 삭제 / 설명 확인")
async def delete_analyzer_graph(body: model.AnalyzerGraphDeleteModel):
    """
    ## 전체 삭제  
        INPUT - analyzer_id: int

    ## 선택 삭제
        INPUT - graph_id_list: list(int), ex) [1, 2, 3, 4]
    """
    try:
        res = await svc.delete_analyzer_graph(analyzer_id=body.analyzer_id, graph_id_list=body.graph_id_list)
        return response(result=res, status=1)
    except:
        traceback.print_exc()
        return response(message="Get Dataset Error" , status=0)

# ==================================================================================================
# PATH PARAM
# ==================================================================================================
@analyzer.get("/graph-sse/{analyzer_id}", tags=TAG_ITEM, summary="데이터분석 단일 조회 - 그래프 / 설명확인")
async def get_analyzer_graph_sse(analyzer_id: int, request: Request):
    """
    data는 {"x" : list, "y" : list} 형태임, x는 범주(고유값, 레이블), y는 빈도수이다. 파이차트일경우 y는 비율임
    """
    async def event_generator():
        old_history = None
        last_sent_time = datetime.now()
        try:
            while True:
                await asyncio.sleep(1)
                if await request.is_disconnected():
                    break
                result = await svc.get_analyzer_graph_list(analyzer_id=analyzer_id)
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
            print(f"Connection closed for analyzer {analyzer_id}")
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@analyzer.get("/graph/{analyzer_id}", tags=TAG_ITEM, summary="데이터분석 단일 조회 - 그래프 / 설명확인")
async def get_analyzer_graph(analyzer_id: int):
    """
    data는 {"x" : list, "y" : list} 형태임, x는 범주(고유값, 레이블), y는 빈도수이다. 파이차트일경우 y는 비율임
    """
    try:
        res = await svc.get_analyzer_graph_list(analyzer_id=analyzer_id)
        return response(result=res, status=1)
    except:
        traceback.print_exc()
        return response(message="Get Dataset Error" , status=0)

@analyzer.get("/info/{analyzer_id}", tags=TAG_ITEM, summary="데이터분석 단일 조회 - 기본정보")
async def get_analyzer_info(analyzer_id: int):
    try:
        res = await svc.get_analyzer_info(analyzer_id=analyzer_id)
        return response(result=res, status=1)
    except:
        traceback.print_exc()
        return response(message="Get Dataset Error" , status=0)

@analyzer.delete("/{id_list}", tags=TAG_LIST)
async def delete_analyzer(id_list):
    try:
        id_list = id_list.split(',')
        user_name, _ = get_auth()
        res = svc.delete_analyzer(id_list=id_list, headers_user=user_name)
        if res:
            return response(status=1, message = 'Analyzer delete Complete')
        else:
            raise Exception("Analyzer DB Delete Error")
    except Exception as e:
        return response(status=0, message = f"Analyzer delete Fail '{e}' ")
