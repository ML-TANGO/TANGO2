from fastapi import APIRouter, Request, UploadFile, Form, File, Body, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import RedirectResponse
from pydantic import Field
from utils.resource import response, get_user_id, get_auth
from utils.exception.exceptions import *
import model.dto as dto
import model.service as svc
import traceback
import io

model = APIRouter(
    prefix = "/models"
)

TAG_FINE_TUNING = ['FINE_TUNING']
TAG_MODEL = ['MODEL']
TAG_COMMIT_MODEL = ['COMMIT_MODEL']
TAG_OPTION = ['OPTION']

@model.get("/fine-tuning/system-log/download", summary='setting - fine tuning', tags=TAG_FINE_TUNING)
async def get_fine_tuning_system_log_download(model_id: int):
    try:
        res = None
        res = await svc.get_fine_tuning_system_log(model_id=model_id, is_download=True, count=10000)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])   


@model.get("/option/download/default-configuration", summary='setting - fine tuning custom config format download', tags=TAG_OPTION)
async def download_default_configuration():
    try:
        # JSON 데이터 생성
        data = {
            "learning_rate" : 5e-5,
            "gradient_accumulation_steps" : 1,
            "num_train_epochs" : 3,
            "cutoff_length" : 512,
            "warmup_steps" : 0,
            "deepspeed" : {
                        "train_batch_size": "auto",
                        "train_micro_batch_size_per_gpu": "auto",
                        "gradient_accumulation_steps": "auto",
                        "gradient_clipping":"auto",
                        "zero_allow_untested_optimizer": True,
                        "fp16": {
                            "enabled": True,
                            "loss_scale": 0,
                            "loss_scale_window": 1000,
                            "initial_scale_power": 16,
                            "hysteresis": 2,
                            "min_loss_scale": 1
                        },
                        "bf16": {
                            "enabled": False
                        },
                        "zero_optimization": {
                            "stage": 1,
                            "allgather_partitions": True,
                            "allgather_bucket_size": 5e8,
                            "overlap_comm": True,
                            "reduce_scatter": True,
                            "reduce_bucket_size": 5e8,
                            "contiguous_gradients": True,
                            "round_robin_gradients": True
                        }
                    }
        }

        # 데이터를 JSON 문자열로 변환
        json_data = json.dumps(data, ensure_ascii=False, indent=4)

        # 문자열 데이터를 파일처럼 사용 가능한 메모리 버퍼로 변환
        buffer = io.BytesIO(json_data.encode("utf-8"))

        # 클라이언트로 스트리밍 전송
        return StreamingResponse(
            buffer,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=config.json"}
        )

    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])    

@model.get("/fine-tuning/sse-graph/{model_id}", summary='graph - fine tuning', tags=TAG_FINE_TUNING)
async def sse_fine_tuning_graph( model_id : int, request : Request):
    try:
        return StreamingResponse(svc.sse_get_fine_tuning_result_graph(model_id=model_id, request=request), media_type="text/event-stream")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 

@model.get("/fine-tuning/sse-time/{model_id}", summary='time - fine tuning', tags=TAG_FINE_TUNING)
async def sse_fine_tuning_time( model_id : int, request : Request):
    try:
        return StreamingResponse(svc.sse_get_fine_tuning_time(model_id=model_id, request=request), media_type="text/event-stream")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 

    
@model.get("/fine-tuning/sse-status/{model_id}", summary='status - fine tuning', tags=TAG_FINE_TUNING)
async def sse_fine_tuning_status( model_id : int, request : Request):
    try:
        return StreamingResponse(svc.sse_get_fine_tuning_status(model_id=model_id, request=request), media_type="text/event-stream")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 
    
@model.get("/fine-tuning/train-log", summary='log - fine tuning', tags=TAG_FINE_TUNING)
async def sse_fine_tuning_log(model_id : int):
    try:
        res = await svc.get_fine_tuning_result_logs(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])  

@model.get("/fine-tuning/system-log", summary='log - fine tuning', tags=TAG_FINE_TUNING)
async def get_fine_tuning_system_log(model_id: int):
    try:
        res = None
        res = await svc.get_fine_tuning_system_log(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])   

@model.post("/fine-tuning/stop", summary='stop - fine tuning', tags=TAG_FINE_TUNING)
async def stop_model_fine_tuning(model_id : int=Body(...)):
    try:
        res = None
        res, message = await svc.stop_fine_tuning(model_id=model_id)
        return response(status=1, result=res, message=message)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])   

@model.post("/fine-tuning/run", summary='run - fine tuning', tags=TAG_FINE_TUNING)
async def run_model_fine_tuning(body: dto.PostFineTuningRun):
    try:
        res = None
        res = await svc.running_fine_tuning(model_id=body.model_id, model_dataset_id=body.model_dataset_id, instance_count=body.instance_count,\
            instance_id=body.instance_id, gpu_count=body.gpu_count, fine_tuning_config=body.fine_tuning_config)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])  


@model.get("/fine-tuning/summary", summary='get - fine tuning', tags=TAG_FINE_TUNING)
async def get_model_fine_tuning_summary(model_id: int):
    try:
        res = None
        res = await svc.get_model_summary(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 

@model.get("/option/datasets",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_datasets(workspace_id : int, is_mine : bool = False, dataset_name : str = None):
    try:
        res = None
        # TODO 
        # 추후 수정
        if is_mine:
            create_user_id = 2
        else:
            create_user_id = None
        res = await svc.get_dataset_list(workspace_id=workspace_id, create_user_id=create_user_id, dataset_name=dataset_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@model.get("/option/models",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_datasets(workspace_id : int, search: str = None, is_mine : bool = False):
    try:
        res = None
        # TODO 
        # 추후 수정
        user_id = get_user_id()
        
        res = await svc.get_models_option(workspace_id=workspace_id, model_name=search, header_user_id=user_id, is_mine=is_mine)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.get("/option/commit-models",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_datasets(model_id : int, search: str = None):
    try:
        res = None
        res = await svc.get_commit_models_option(model_id=model_id, commit_name=search)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@model.get("/option/instances",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_instances(workspace_id : int):
    try:
        res = None
        res = await svc.get_instance_list(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.post("/option/huggingface-models",summary='setting - model', tags=TAG_OPTION)
async def get_models_by_huggingface(body : dto.PostHuggingface):
    try:
        res = None
        res = await svc.get_models_by_huggingface(model_name=body.model_name, huggingface_token=body.huggingface_token, private=body.private)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])  

@model.post("/option/huggingface-token-check",summary='setting - model', tags=TAG_OPTION)
async def check_huggingface_token(huggingface_token : str = Body(...)):
    try:
        res = None
        res = await svc.check_model_access(token=huggingface_token)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@model.get("/option/dataset-files",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_dataset_files(dataset_id : int, search : str = None):
    """dataset file 상세 조회"""
    try:
        user_id = get_user_id()
        res = await svc.get_dataset_files_and_folders(dataset_id=dataset_id, search_user_id=user_id, search=search) 
        return response(result=res, status =1)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e)) 
@model.post("/option/add-dataset", summary='setting - fine tuning', tags=TAG_OPTION)
async def get_model(body : dto.AddDataset):
    try:
        res = None
        res = await svc.add_dataset(model_id=body.model_id, dataset_id=body.dataset_id, training_data_path=body.training_data_path)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])
    
@model.get("/option/model-update", summary='setting - fine tuning', tags=TAG_OPTION)
async def get_model_update(model_id : int):
    try:
        res = None
        res = await svc.get_model_update(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@model.post("/option/upload-configuration", summary='setting - fine tuning', tags=TAG_OPTION)
async def upload_configuration(file: UploadFile = File(...), model_id : int = Form(...) ):
    try:
        res = None
        # res = await svc.add_dataset(model_id=body.model_id, dataset_id=body.dataset_id, training_data_path=body.training_data_path)
        res = await svc.upload_fine_tuning_configuration(file=file, model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])    
@model.delete("/option/model-dataset", summary='setting - fine tuning', tags=TAG_OPTION)
async def delete_model_dataset(model_dataset_id : int):
    try:
        res = None
        res = await svc.delete_model_dataset(model_dataset_id=model_dataset_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])
    
@model.delete("/option/model-configuration", summary='setting - fine tuning', tags=TAG_OPTION)
async def delete_model_configuration(model_config_id : int):
    try:
        res = None
        res = await svc.delete_model_configuration(model_config_id=model_config_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.get("/option/user",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_users(workspace_id : int):
    try:
        res = None
        res = await svc.get_workspace_user(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.get("/commit-models/{commit_model_id}", summary='get - fine tuning', tags=TAG_COMMIT_MODEL)
async def get_model_commit_list(commit_model_id: int):
    try:
        res = None
        res = await svc.get_commit_model(commit_model_id=commit_model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])    
    
@model.post("/commit-models/load", summary='setting - fine tuning', tags=TAG_FINE_TUNING)
async def load_model_commit(commit_model_id: int = Body(...)):
    try:
        res = None
        res = await svc.load_commit_model(commit_model_id=commit_model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 
    

@model.put("/bookmark",summary='list - model', tags=TAG_MODEL)
async def set_model_bookmark(model_id : int = Body(...)):
    try:
        res = None
        user_id = get_user_id()
        res = await svc.set_bookmark_model(model_id=model_id, header_user_id=user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])



    
@model.get("/fine-tuning", summary='get - fine tuning', tags=TAG_FINE_TUNING)
async def get_model_fine_tuning(model_id: int):
    try:
        res = None
        res = await svc.get_model_fine_tuning(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])   
    


@model.get("/commit-models", summary='get - fine tuning', tags=TAG_COMMIT_MODEL)
async def get_model_commit_list(model_id: int):
    try:
        res = None
        res = await svc.get_commit_models(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 
    


    
@model.post("/commit-models", summary='create - fine tuning', tags=TAG_COMMIT_MODEL)
async def create_model_commit(body : dto.PostModelCommit):
    try:
        res = None
        # cr = CustomResource()
        user_id = get_user_id()
        res = await svc.create_commit_model(model_id=body.model_id, commit_name=body.commit_name, commit_message=body.commit_message, create_user_id=user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])
    
    
@model.get("/healthz")
async def healthz():
    try:
        await svc.check_healthz()
        return JSONResponse(status_code=200, content={"status": "healthy"})
    except:
        return JSONResponse(status_code=500, content={"status": "not healthy"})

    
# @model.post("/shorten")
# async def shorten_url(request: dto.URLRequest):
#     # 고유한 ID를 생성하여 단축된 URL로 사용
#     try:
#         res = None
#         # cr = CustomResource()
#         res = await svc.shorten_url(original_url=request.original_url)
#         return response(status=1, result=res)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="server error", result=[])
 
@model.put("/detail",summary='update - model', tags=TAG_MODEL)
async def delete_model(model_id: int = Body(...), description: str = Body(...)):
    try:
        res = None
        res = await svc.update_model_description(model_id=model_id, description=description)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)
    
# @model.get("/{short_id}")
# async def redirect_url(short_id: str):
#     # 단축된 URL을 통해 원본 URL로 리디렉션
#     try:
#         res = None
#         # cr = CustomResource()
#         res = await svc.get_origin_url(short_id=short_id)
#         if res is None:
#             raise HTTPException(status_code=404, detail="URL not found")
#         return RedirectResponse(url=res["original_url"])
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="server error", result=[])
    
@model.get("",summary='list - model', tags=TAG_MODEL)
async def get_models(workspace_id: int=None):
    try:
        res = None
        user_id = get_user_id()
        res = await svc.get_models(workspace_id=workspace_id, header_user_id=user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)
    
@model.post("",summary='create - model', tags=TAG_MODEL)
async def create_models(body: dto.PostModel):
    try:
        res = None
        user_id = get_user_id()
        if body.create_user_id == 0:
            body.create_user_id = user_id
        res = await svc.create_model(workspace_id=body.workspace_id, model_name=body.model_name, description=body.description, huggingface_model_id=body.huggingface_model_id, users_id = body.users_id,
                                     commit_model_id=body.commit_model_id, huggingface_token=body.huggingface_token, create_user_id=body.create_user_id, private=body.private, access=body.access) # TODO 추후 수정
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)



@model.delete("",summary='delete - model', tags=TAG_MODEL)
async def delete_model(model_id: int):
    try:
        res = None
        res = await svc.delete_model(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)
    
@model.put("",summary='put - model', tags=TAG_MODEL)
async def update_model(body: dto.PutModel):
    try:
        res = None
        res = await svc.update_model(model_id=body.model_id, description=body.description,  access=body.access, user_list=body.user_list, create_user_id=body.create_user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)