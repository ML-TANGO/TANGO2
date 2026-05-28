# db.py
from pymongo import MongoClient, collection
from contextlib import contextmanager
from utils import settings
from utils.mongodb_key import DATABASE, NOTIFICATION_COLLECTION, REQUEST_COLLECTION, USER_DASHBOARD_TIMELINE, ADMIN_DASHBOARD_TIMELINE, TEST_DUMMY_TIMELINE
from urllib.parse import quote
from typing import Optional
from pydantic import BaseModel
from utils import notification_key
from datetime import datetime, timedelta
from bson import ObjectId
import traceback

MONGODB_PASSWORD = quote(settings.JF_MONGODB_PASSWORD)
NAMESPACE = settings.JF_SYSTEM_NAMESPACE
MONGO_DETAILS = f"mongodb://root:{MONGODB_PASSWORD}@{settings.JF_MONGODB_DNS}:{settings.JF_MONGODB_PORT}/"


def get_mongodb_conn() -> MongoClient:
    return MongoClient(MONGO_DETAILS)



@contextmanager
def mongodb_conn(database_name : str , collection_name : str):
    try:
        conn = None
        conn = get_mongodb_conn()
        db = conn[database_name]
        collection = db[collection_name]
        yield collection
    finally:
        conn.close()
        pass





class RequestInfo(BaseModel):
    type: str # workspace, user
    request_info : dict
    status: int = 0 # 0 reject, 1 accept, 2 waiting
    create_datetime : datetime = datetime.now()

class WorkspaceRequestInfo(BaseModel):
    manager_id :int  
    workspace_name : str
    allocate_instances : list
    start_datetime : str
    end_datetime : str
    users : list
    description : str = None
    main_storage_id : int
    data_storage_request : str
    main_storage_request : str
    data_storage_id : int
    response_status : bool = False

class NotificationInfo(BaseModel):
    user_id : int
    read : int = 0
    user_type: str = notification_key.NOTIFICATION_USER_TYPE_ADMIN
    noti_type: str 
    message : str
    create_datetime : Optional[str | datetime] = datetime.now()
    
    
class NotificationWorkspace(NotificationInfo):
    workspace_id : int 

    # request_info : WorkspaceRequestInfo = None

class DashboardTimeLine(BaseModel):
    gpu : dict
    cpu : dict
    ram : dict
    storage_main : dict
    storage_data : dict
    pricing : dict

def insert_admin_dashboard_dummy_timeline(dashboard_timeline : DashboardTimeLine) -> str:
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=TEST_DUMMY_TIMELINE) as collection:
            collection.insert_one(dashboard_timeline)
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def insert_admin_dashboard_timeline(dashboard_timeline : DashboardTimeLine) -> str:
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=ADMIN_DASHBOARD_TIMELINE) as collection:
        #with mongodb_conn(database_name=DATABASE, collection_name=ADMIN_DASHBOARD_TIMELINE) as collection:
            result=collection.insert_one(dashboard_timeline)
            print("ID",result.inserted_id)
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    except:
        traceback.print_exc()
        return False, e

def insert_user_dashboard_timeline(dashboard_timeline : DashboardTimeLine) -> str:
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=USER_DASHBOARD_TIMELINE) as collection:
            collection.insert_one(dashboard_timeline)
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def insert_notification_history(notification : NotificationInfo) -> str:
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
            collection.insert_one(notification.model_dump())
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_resource_over_message(workspace_id : int, user_id: int, message : str):
    res = []
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=NOTIFICATION_COLLECTION) as collection:
            # 30분 전의 시각 계산
            thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
            # print(thirty_minutes_ago)
            query = {
                'user_id' : user_id,
                'create_datetime': {'$gte': thirty_minutes_ago, '$lt' : datetime.now()},
                'workspace_id' :workspace_id,
                'message' : message
            }
            res = collection.find(query)
            return list(res)
    except Exception as e:
        traceback.print_exc()
        return res
    

def insert_request(request : RequestInfo) -> str:
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=REQUEST_COLLECTION) as collection:
            collection.insert_one(request.model_dump())
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
def get_request_user_list():
    res = []
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=REQUEST_COLLECTION) as collection:
            res = list(collection.find({"type" : "user"})) 
    except Exception as e:
        traceback.print_exc()
    return res
    
    
def get_request_user(object_id):
    res = dict()
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=REQUEST_COLLECTION) as collection:
            res = collection.find_one({"_id" : ObjectId(object_id)})
    except Exception as e:
        traceback.print_exc()
    return res
    

def delete_request_user(object_id):
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=REQUEST_COLLECTION) as collection:
            collection.delete_one({"_id" : ObjectId(object_id)})
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_user_dashboard_timeline(now_date, workspace_id=None):
    res = None
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=USER_DASHBOARD_TIMELINE) as collection:
            start_date = now_date - timedelta(hours=12)
            query = {
                "create_datetime": {
                    "$gte": start_date,
                    "$lte": now_date
                }
            }
            if workspace_id is not None:
                query['workspace_id']=workspace_id
            res = collection.find(query).sort('_id', -1)
            return list(res)
    except:
        traceback.print_exc()
        return res


def get_admin_dashboard_timeline(now_date):
    res = None
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=ADMIN_DASHBOARD_TIMELINE) as collection:
            start_date = now_date - timedelta(hours=12)
            query = {
                "create_datetime": {
                    "$gte": start_date,
                    "$lte": now_date
                }
            }
            res = collection.find(query).sort('_id', -1)
            return list(res)
    except:
        traceback.print_exc()
        return res
    
def get_admin_dashboard_dummy_timeline(now_date):
    res = None
    try:
        with mongodb_conn(database_name=DATABASE, collection_name=TEST_DUMMY_TIMELINE) as collection:
            start_date = now_date - timedelta(days=60)
            query = {
                "create_datetime": {
                    "$gte": start_date,
                    "$lte": now_date
                }
            }
            res = collection.find(query).sort('_id', -1)
            return list(res)
    except:
        traceback.print_exc()
        return res