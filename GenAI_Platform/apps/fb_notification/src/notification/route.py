from fastapi import APIRouter, Depends, HTTPException

from utils.resource import CustomResource, token_checker, response
from utils.TYPE import *

from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import Request
from pydantic import BaseModel
from typing import List, Dict
from collections import deque
from bson.objectid import ObjectId


from utils.mongodb import mongodb_conn, get_mongodb_conn
from utils.mongodb_key import DATABASE, NOTIFICATION_COLLECTION
from utils.notification_key import NOTIFICATION_USER_TYPE_ADMIN, WORKSPACE_CREATE_REQUEST
from datetime import datetime

import asyncio, json, traceback, sys


notification = APIRouter(
    prefix = "/notification"
)

# class UserRequest(BaseModel):
#     user_name: str

class NotificationRead(BaseModel):
    user_name : str
    notification_id : str

class NotificationReadAll(BaseModel):
    user_id : str


class NotificationDelete(BaseModel):
    notification_id : str

bs = "kafka.kafka.svc.cluster.local:9092"
# Consumer 설정
conf = {
    'bootstrap.servers': bs,
    'group.id': "my_group",
    'auto.offset.reset': 'earliest'
}

def collection_init():
    client = get_mongodb_conn()
    # KDN
    msa_jfb = client[DATABASE]
    # kdn_db.create_collection(NOTIFICATION_COLLECTION, capped=True, max=10000)
    msa_jfb[NOTIFICATION_COLLECTION].create_index([("create_datetime", 1)], expireAfterSeconds=604800 ) # 86400 하루


def _ObjectIdDecorator(item : dict):
    item["_id"] = str(item["_id"])
    if "create_datetime" in item and isinstance(item["create_datetime"], datetime):
        item["create_datetime"] = item["create_datetime"].isoformat()
    return item


async def get_healthz_chek( ):
    with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
        history = collection.find()
        # history = list(history)
    return True

async def get_notification_history(user_id: int ):
    with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
        # projection = {
        #         'create_datetime': 0  # create_datetime 필드를 제외
        #     }

        # history = collection.find({"user_id": user_id},projection).sort("_id", -1).limit(30)
        history = collection.find({"user_id": user_id}).sort("_id", -1).limit(30)

        history = list(history)
    return history

async def update_notification_history(notification_id : str):
    with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
        collection.update_one({"_id" : ObjectId(notification_id)}, {"$set" :{
                "read" : 1
            }})
    return True

async def update_notification_history_all(user_id : int):
    with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
        collection.update_many({"user_id": user_id}, {"$set" :{
                "read" : 1
            }})
    return True

async def delete_notification_history(notification_id : str):
    with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
        collection.delete_one({"_id": ObjectId(notification_id)})
    return True

async def delete_all_notification_history(user_id : int):
    with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
        collection.delete_many({"user_id": user_id})
    return True


async def update_workspace_create_notification_history(notification_id : str):
    with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
        collection.update_one({"_id" : ObjectId(notification_id)}, {"$set" :{
                "read" : 1, "request_info.response_status" : True
            }})
    return True


@notification.get("/healthz")
async def healthz():
    await get_healthz_chek()
    return JSONResponse(status_code=200, content={"status": "healthy"})

@notification.get("/sse")
async def sse_endpoint( request : Request):
    cr = CustomResource()
    user_id = cr.check_user_id()
    user_name = cr.check_user()
    async def event_generator():
        old_history = None
        # first_flag = True
        try:
            # 연결 시점에 초기 데이터를 보냅니다.
            # initial_history = await get_notification_history(user_id=user_info["id"])
            # yield f"data: connection \n\n"
            # old_history = initial_history

            while True:
                await asyncio.sleep(1)
                if await request.is_disconnected():
                    break
                current_history = await get_notification_history(user_id=user_id)
                current_history = list(map(_ObjectIdDecorator, current_history))
                # print(current_history)
                yield f"data: {json.dumps(current_history)}\n\n"
        except Exception as e:
            # 예외 처리 및 로그 남기기
            traceback.print_exc()
            print(f"Exception in SSE stream: {e}")
        finally:
            # 연결이 끊어졌을 때의 후속 처리
            print(f"Connection closed for user {user_name}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@notification.post("read")
async def read(notification_read : NotificationRead):
    notification_id = notification_read.notification_id
    res = await update_notification_history(notification_id=notification_id)
    return response(result = res, status=1)


@notification.post("read-all")
async def read_all():
    cr = CustomResource()
    user_id = cr.check_user_id()
    res = await update_notification_history_all(user_id=user_id)
    return response(result = res, status=1)


@notification.delete("")
async def delete_notification(notification_delete : NotificationDelete):
    notification_id = notification_delete.notification_id
    res = await delete_notification_history(notification_id=notification_id)
    return response(result = res, status=1)

@notification.delete("/all")
async def delete_notification():
    cr = CustomResource()
    user_id = cr.check_user_id()
    res = await delete_all_notification_history(user_id=user_id)
    return response(result = res, status=1)

@notification.post("workspace-request-read")
async def sse_endpoint(notification_read : NotificationRead):
    notification_id = notification_read.notification_id
    res = await update_workspace_create_notification_history(notification_id=notification_id)
    return response(result = res, status=1)