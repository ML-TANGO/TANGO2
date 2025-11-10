from fastapi import APIRouter, Depends, HTTPException, Request
from utils.redis import get_redis_client_async
from utils.resource import response, get_auth, get_user_id
from utils.TYPE import *
from utils.redis_key import USER_ALERT_CHANNEL
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.responses import StreamingResponse
from utils.mongodb import mongodb_conn
from utils.mongodb_key import DATABASE, NOTIFICATION_COLLECTION
from utils.notification_key import NOTIFICATION_USER_TYPE_ADMIN, WORKSPACE_CREATE_REQUEST
from datetime import datetime
from pydantic import BaseModel
from bson.objectid import ObjectId


import asyncio, json, traceback, sys, logging

notification = APIRouter(
    prefix = "/notification"
)


class NotificationRead(BaseModel):
    user_name : str
    notification_id : str

class NotificationReadAll(BaseModel):
    user_id : str


class NotificationDelete(BaseModel):
    notification_id : str

async def get_noti_not_read_count(user_id: str):
    with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
        not_read_count = collection.count_documents({"user_id": user_id, "read": 0})
    return not_read_count


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

def _ObjectIdDecorator(item : dict):
    item["_id"] = str(item["_id"])
    if "create_datetime" in item and isinstance(item["create_datetime"], datetime):
        # %Y-%m-%d %H:%M:%S 형식으로 변경 2025-03-27T06:20:00.944870 -> 2025-03-27 06:20:00
        
        item["create_datetime"] = item["create_datetime"].isoformat(sep=' ')
    return item

async def get_healthz_chek( ):
    redis_client = await get_redis_client_async()
    try:
        # Redis에 ping을 보내서 연결 확인
        await redis_client.ping()
        # MongoDB 연결 확인
        with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
            # MongoDB에 ping을 보내서 연결 확인
            collection.find_one()
        return True
    except Exception as e:
        # 예외 발생 시 False 반환
        print(f"Health check failed: {e}")
        return False

@notification.get("/healthz")
async def healthz():
    result = await get_healthz_chek()
    return JSONResponse(status_code=200, content={"status": result})

@notification.get("/recent-history")
async def recent_history():
    user_id = get_user_id()
    with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
        noti_list = list(collection.find({"user_id": user_id}).sort("create_datetime", -1).limit(30))
        current_history = list(map(_ObjectIdDecorator, noti_list))
    return response(result=current_history, status=1)

@notification.post("/read")
async def read(notification_read : NotificationRead):
    notification_id = notification_read.notification_id
    res = await update_notification_history(notification_id=notification_id)
    return response(result = res, status=1)


@notification.post("/read-all")
async def read_all():
    user_id = get_user_id()
    res = await update_notification_history_all(user_id=user_id)
    return response(result = res, status=1)

@notification.delete("/all")
async def delete_notification():
    user_id = get_user_id()
    res = await delete_all_notification_history(user_id=user_id)
    return response(result = res, status=1)

@notification.post("/workspace-request-read")
async def sse_endpoint(notification_read : NotificationRead):
    notification_id = notification_read.notification_id
    res = await update_workspace_create_notification_history(notification_id=notification_id)
    return response(result = res, status=1)

@notification.get("/sse")
async def sse(request : Request):
    user_id = get_user_id()
    redis_client = await get_redis_client_async()
    
    async def event_generator():
        try:
            old_read_count = await get_noti_not_read_count(user_id)
            # 연결 시점에 초기 데이터를 보내줌
            yield f"data: {json.dumps({'not_read_count': old_read_count})}\n\n"
            while True:
                await asyncio.sleep(1)
                if await request.is_disconnected():
                    break
                # Redis에서 메시지를 가져옴
                msgs = await redis_client.xread(streams={USER_ALERT_CHANNEL.format(user_id) : "0"}, count=10, block=1000)
                if msgs:
                    for stream, messages in msgs:
                        for msg_id, data in messages:
                            # 메시지를 처리
                            data["not_read_count"] = await get_noti_not_read_count(user_id) 
                            yield f"data: {data}\n\n"
                            # 메시지 처리가 완료되면 ACK
                            await redis_client.xack(USER_ALERT_CHANNEL.format(user_id), "mygroup", msg_id)
                            await redis_client.xdel(USER_ALERT_CHANNEL.format(user_id), msg_id)
                else:
                    # 메시지가 없을 경우 
                    recent_read_count = await get_noti_not_read_count(user_id)
                    if recent_read_count != old_read_count:
                        # 새로운 메시지가 도착했을 때만 전송
                        old_read_count = recent_read_count
                        yield f"data: {json.dumps({'not_read_count': old_read_count})}\n\n"


        except asyncio.CancelledError as e:
            # 예외 처리 및 로그 남기기
            print(f"CancelledError in SSE stream: {e}")
        except Exception as e:
            # 예외 처리 및 로그 남기기
            traceback.print_exc()
            print(f"Exception in SSE stream: {e}")
        finally:
            # 연결이 끊어졌을 때의 후속 처리
            print(f"Connection closed for user {user_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@notification.delete("")
async def delete_notification(notification_delete : NotificationDelete):
    notification_id = notification_delete.notification_id
    res = await delete_notification_history(notification_id=notification_id)
    return response(result = res, status=1)