from fastapi import APIRouter, Depends, HTTPException

from utils.resource import CustomResource, token_checker, response
from utils.TYPE import *

from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import Request
from pydantic import BaseModel
from typing import List, Dict
from collections import deque
from bson.objectid import ObjectId
from utils.redis_key import SSE_PROGRESS
from utils.redis import get_redis_client
from utils.common import format_size

# from utils.mongodb import mongodb_conn, get_mongodb_conn
# from utils.mongodb_key import DATABASE, NOTIFICATION_COLLECTION
# from utils.notification_key import NOTIFICATION_USER_TYPE_ADMIN, WORKSPACE_CREATE_REQUEST
from datetime import datetime

import asyncio, json, traceback, sys


progress = APIRouter(
    prefix = "/progress"
)

# class UserRequest(BaseModel):
#     user_name: str

# class NotificationRead(BaseModel):
#     user_name : str
#     notification_id : str

# class NotificationReadAll(BaseModel):
#     user_id : str


# class NotificationDelete(BaseModel):
#     notification_id : str

# bs = "kafka.kafka.svc.cluster.local:9092"
# # Consumer 설정
# conf = {
#     'bootstrap.servers': bs,
#     'group.id': "my_group",
#     'auto.offset.reset': 'earliest'
# }

# def collection_init():
#     client = get_mongodb_conn()
#     # KDN
#     msa_jfb = client[DATABASE]
#     # kdn_db.create_collection(NOTIFICATION_COLLECTION, capped=True, max=10000)
#     msa_jfb[NOTIFICATION_COLLECTION].create_index([("create_datetime", 1)], expireAfterSeconds=604800 ) # 86400 하루


# def _ObjectIdDecorator(item : dict):
#     item["_id"] = str(item["_id"])
#     if "create_datetime" in item and isinstance(item["create_datetime"], datetime):
#         item["create_datetime"] = item["create_datetime"].isoformat()
#     return item

redis_client = get_redis_client()

# async def get_healthz_chek( ):
#     with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
#         history = collection.find()
#         # history = list(history)
#     return True

# @progress.get("/healthz")
# async def healthz():
#     await get_healthz_chek()
#     return JSONResponse(status_code=200, content={"status": "healthy"})

@progress.get("/sse/{workspace_id}")
async def sse_endpoint( request : Request,workspace_id):
    try:
        cr = CustomResource()
        user_id = cr.check_user_id()
        user_name = cr.check_user()
        async def event_generator():
            # old_history = None
            # first_flag = True
            try:
                global redis_client
                # 연결 시점에 초기 데이터를 보냅니다.
                # initial_history = await get_notification_history(user_id=user_info["id"])
                # yield f"data: connection \n\n"
                # old_history = initial_history

                while True:
                    progress_info={}
                    await asyncio.sleep(1)
                    if await request.is_disconnected():
                        break
                    sse_info = redis_client.hgetall(SSE_PROGRESS.format(user_id=user_id))
                    # print(sse_info)
                    if sse_info is not None:
                        # sse_info=json.loads(sse_info)
                        for sub_key, key in sse_info.items():
                            upload_info = redis_client.hget(key, sub_key)

                            if upload_info is not None:
                                upload_info=json.loads(upload_info)
                                print(type(upload_info['workspace_id']))
                                print(type(workspace_id))
                                if upload_info['workspace_id'] == int(workspace_id):
                                    if not progress_info.get(upload_info['dataset_name'],False):
                                        progress_info[upload_info['dataset_name']]=[]
                                    if upload_info['type'] == "size":
                                        upload_info['upload_size'] = format_size(upload_info['upload_size'])
                                        upload_info['total_size'] = format_size(upload_info['total_size'])
                                    progress_info[upload_info['dataset_name']].append(upload_info)

                    yield f"data: {progress_info}\n\n"
            except Exception as e:
                # 예외 처리 및 로그 남기기
                traceback.print_exc()
                print(f"Exception in SSE stream: {e}")
            finally:
                # 연결이 끊어졌을 때의 후속 처리
                print(f"Connection closed for user {user_name}")
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except:
        traceback.print_exc()



# @notification.post("read")
# async def read(notification_read : NotificationRead):
#     notification_id = notification_read.notification_id
#     res = await update_notification_history(notification_id=notification_id)
#     return response(result = res, status=1)


# @notification.post("read-all")
# async def read_all():
#     cr = CustomResource()
#     user_id = cr.check_user_id()
#     res = await update_notification_history_all(user_id=user_id)
#     return response(result = res, status=1)


# @notification.delete("")
# async def delete_notification(notification_delete : NotificationDelete):
#     notification_id = notification_delete.notification_id
#     res = await delete_notification_history(notification_id=notification_id)
#     return response(result = res, status=1)

# @notification.delete("/all")
# async def delete_notification():
#     cr = CustomResource()
#     user_id = cr.check_user_id()
#     res = await delete_all_notification_history(user_id=user_id)
#     return response(result = res, status=1)

# @notification.post("workspace-request-read")
# async def sse_endpoint(notification_read : NotificationRead):
#     notification_id = notification_read.notification_id
#     res = await update_workspace_create_notification_history(notification_id=notification_id)
#     return response(result = res, status=1)