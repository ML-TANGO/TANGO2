from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import select_query

from typing import List
from utils import TYPE, PATH
from datetime import date, datetime, timedelta

import utils.common as common
import traceback
import json
import pymysql

from utils.exception.exceptions import *

admin_user_id_list = None

IMAGE_STATUS_PENDING = 0
IMAGE_STATUS_INSTALLING = 1
IMAGE_STATUS_READY = 2
IMAGE_STATUS_FAILED = 3

def get_image_list(workspace_id=None):
    # import utils.db as db
    try:
        # WHERE
        search_query = ""
        if workspace_id is not None:
            search_query = """WHERE (i.access = 1) or (i.access = 0 and iw.workspace_id = {})""".format(workspace_id)

        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT i.id id,
            i.name as name,
            w.id workspace_id,
            w.name workspace_name,
            i.real_name real_name,
            i.file_path file_path,
            i.status status,
            i.fail_reason fail_reason,
            i.type type,
            i.access access,
            i.iid iid,
            i.libs_digest libs_digest,
            i.docker_digest docker_digest,
            i.description description,
            i.upload_filename upload_filename,
            u.name user_name,
            i.size size,
            i.create_datetime create_datetime,
            i.update_datetime update_datetime,
            i.user_id as uploader_id
            FROM image i
            LEFT JOIN image_workspace iw ON i.id=iw.image_id
            LEFT JOIN workspace w ON iw.workspace_id=w.id
            LEFT JOIN user u ON i.user_id=u.id
            {search_query}
            ORDER BY id DESC
            """.format(search_query=search_query)

            cur.execute(sql)
            res = cur.fetchall()
            res = reduce_joined_result(res, 'id', 'workspace', ('workspace_id', 'workspace_name'))
            res = common.resource_str_column_to_dict(res)
        return res
    except Exception as e:
        traceback.print_exc()
        return []

def get_image_single(image_id):
    # import utils.db as db
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT i.id id,
                    w.id workspace_id,
                    w.name workspace_name,
                    -- w.manager_id workspace_manager_id,
                    i.user_id as uploader_id,
                    i.name image_name,
                    i.real_name real_name,
                    i.file_path file_path,
                    i.status status,
                    i.fail_reason fail_reason,
                    i.type type,
                    i.access access,
                    i.size as size,
                    i.iid iid,
                    i.docker_digest docker_digest,
                    i.libs_digest libs_digest,
                    i.description description,
                    i.upload_filename upload_filename,
                    i.user_id as uploader_id,
                    u.name user_name,
                    i.create_datetime create_datetime,
                    i.update_datetime update_datetime,
                    i.user_id user_id
            FROM image i
            LEFT JOIN image_workspace iw ON i.id=iw.image_id
            LEFT JOIN workspace w ON iw.workspace_id=w.id
            LEFT JOIN user u ON i.user_id=u.id
            WHERE i.id=%s"""
            cur.execute(sql, image_id)
            res = cur.fetchall()
            res = reduce_joined_result(res, 'id', 'workspace', ('workspace_id', 'workspace_name'))
            
            if not res:
                return False
        return res[0]
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_image_manager_list(image_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            select DISTINCT manager_id
            FROM image_workspace iw
            INNER JOIN (
                select DISTINCT id, manager_id
                from workspace w
                INNER join  image_workspace iw on w.id = iw.workspace_id
                ) tmp on tmp.id = iw.workspace_id
            WHERE image_id = %s
            """
            cur.execute(sql, image_id)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_workspace_manager_id(workspace_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT manager_id
            FROM workspace
            WHERE id = %s
            """
            cur.execute(sql, workspace_id)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_image_workspace_list(image_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT workspace_id
            FROM image_workspace
            WHERE image_id = %s
            """
            cur.execute(sql, image_id)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_admin_user_id_list():
    try:
        global admin_user_id_list
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT id
            FROM user
            WHERE user_type=0
            """
            cur.execute(sql)
            rows = cur.fetchall()

        if admin_user_id_list is None:
            admin_user_id_list = [row['id'] for row in rows]
        return admin_user_id_list
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_image_by_status(status):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT id, status, type, file_path, real_name, size, libs_digest, iid, upload_filename
            FROM image
            WHERE status in (%s)"""
            cur.execute(sql, status)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_image_id_by_real_name(real_name):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT id
            FROM image
            WHERE real_name=%s """
            cur.execute(sql, real_name)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_image_id_by_name(name):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT id
            FROM image
            WHERE name=%s """
            cur.execute(sql, name)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_db_iid_list():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT iid
            FROM image i
            WHERE iid is not NULL"""
            cur.execute(sql)
            res = cur.fetchall()
            
            result = []
            for item in res:
                result.append(item["iid"])
        return result
    except Exception as e:
        traceback.print_exc()
        return False, e

def get_workspace_image_id(image_id):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()

            sql = "SELECT * FROM image_workspace WHERE image_id = {} ".format(image_id)

            cur.execute(sql)
            res = cur.fetchall()

    except Exception as e:
        traceback.print_exc()
        pass
    return res

def update_image_data(image_id, data):
    """
    image data 업데이트
    input
        image_id(int), data(dict) - {"key" : value}
        data = {
            "status" : 3,
            "fail_reason" : "Not installed"
            "libs_digest" : [{'name': 'torch', 'version': '1.7.1+cu110'}, {'name': 'cuda', 'version': '11.0'}]
        }
    
    * Null 을 넣고 싶을 경우 None 쓰기
    * fail_reason 같이, 문장을 넣어주는 경우에 "'"가 포함되면 에러가 발생할 수 있음 - example) Don't
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = "UPDATE image SET "
            for col, row in data.items():
                if row == None:              # Null case
                    sql += f"{col}=Null, "                    
                elif col in ["status"]:      # status: int
                    sql += f"{col}={row}, "
                elif col in ["libs_digest"]: # libs_digest: list
                    row = json.dumps(row)
                    sql += f"{col}='{row}', "
                else:
                    sql += f"{col}='{row}', "
            sql += f"""update_datetime=CURRENT_TIMESTAMP()
                    WHERE id={image_id} AND status!=4""" # 삭제중일 경우에 status가 변하지 않도록 처리

            cur.execute(sql, ())
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def update_image_workspace(image_id, workspace_id_list, access):
    try:
        with get_db() as conn:
            conn.autocommit = False
            cur = conn.cursor()

            # 워크스페이스 업데이트
            if access == 1:  # 전체공개, db image_workspace 삭제
                sql = """
                DELETE FROM image_workspace
                WHERE image_id=%s"""
                cur.execute(sql, image_id)
            elif access == 0:  # 워크스페이스 공개
                # 1. image_workspace 초기화
                sql = """
                DELETE FROM image_workspace
                WHERE image_id=%s"""
                cur.execute(sql, image_id)

                sql = """
                INSERT INTO image_workspace(image_id, workspace_id)
                VALUES (%s, %s)"""
                cur.executemany(sql, map(lambda x: (image_id, x), workspace_id_list))
            conn.commit()
    except pymysql.err.Error as e:
        traceback.print_exc()
        conn.rollback()
        return False, e

def insert_create_image(user_id, image_name, real_name, file_path, upload_type, access, description, upload_filename, iid, status=IMAGE_STATUS_PENDING):
    try:
        with get_db() as conn:
            lastrowid = None
            cur = conn.cursor()

            if not iid:
                sql = """
                INSERT INTO image(user_id, name, real_name,
                file_path, status, type, access, description, 
                upload_filename, update_datetime)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
                """
                cur.execute(sql, (user_id, image_name, real_name,
                                  file_path, status, upload_type, access, description,
                                  upload_filename))
            else:
                sql = """
                INSERT INTO image(user_id, name, real_name,
                file_path, status, type, access, description,
                upload_filename, iid, update_datetime)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
                """
                cur.execute(sql, (user_id, image_name, real_name,
                                  file_path, status, upload_type, access, description,
                                  upload_filename, iid))
            conn.commit()
            cur.fetchall()
            lastrowid = cur.lastrowid
        return lastrowid
    except Exception as e:
        traceback.print_exc()
        raise CreateImageError

def insert_image_workspace(image_id, workspace_id_list):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            INSERT INTO image_workspace(image_id, workspace_id)
            VALUES (%s, %s)"""
            cur.executemany(sql, map(lambda x: (image_id, x), workspace_id_list))
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_image(image_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            DELETE FROM image
            WHERE id = %s
            """
            cur.execute(sql, image_id)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_image_workspace(image_id, workspace_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            DELETE FROM image_workspace 
            WHERE image_id = %s AND workspace_id = %s
            """
            cur.execute(sql, (image_id, workspace_id))
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def check_if_image_name_exists(image_name):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT *
                FROM image
                WHERE name = '{image_name}'
                LIMIT 1
            """
            cur.execute(sql)
            res = cur.fetchone()

            if res is None:
                return False
            elif len(res) > 0:
                return True
    except Exception as e:
        traceback.print_exc()
        return False, e

async def get_installing_commit_image_list_new(tool_id: int):
    sql = """
    SELECT i.*
    FROM image i
    WHERE JSON_UNQUOTE(JSON_EXTRACT(i.upload_filename, '$.training_tool_id'))=%s;
    """
    res = await select_query(sql, (tool_id), fetch_type="one")
    return res


def get_installing_commit_image_list(tool_id: int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT i.*
                FROM image i
                WHERE JSON_UNQUOTE(JSON_EXTRACT(i.upload_filename, '$.training_tool_id'))=%s
                ORDER BY i.id DESC
            """.format()
            cur.execute(sql, (tool_id))
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        return None

def get_user_name(user_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT name
                FROM user
                WHERE id = {}""".format(user_id)

            cur.execute(sql)
            res = cur.fetchone()

    except:
        traceback.print_exc()
    return res

#TODO
#수정해야함

def get_node_list(page=None, limit=None, search_key="", search_value=""):
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = """
                    SELECT n.*, ng.gpu_config 
                    from node n 
                    LEFT JOIN (Select node_id, group_concat(concat(model,"(",memory,")")) as gpu_config from node_gpu group by node_id) as ng on ng.node_id = n.id  
                    """
            sql+= ''

            if search_key != "" and search_value != "":
                sql += "and " if "where" in sql else "where "
                if search_key == "name":
                    sql += "{} like '%{}%' ".format(search_key, search_value)
                else:
                    sql += "{} = {} ".format(search_key, search_value)

            if page is not None and limit is not None:
                sql += "limit {}, {}".format((page - 1) * limit, limit)
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_workspace_list(page : int=None, size: int=None, search_key: str=None, search_value: str=None, user_id: int=None, sort: int=None):
    try:
        res = []
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT DISTINCT w.*, u.name as manager_name
            FROM workspace w
            INNER JOIN user as u ON w.manager_id = u.id
            INNER JOIN user_workspace uw ON uw.workspace_id = w.id"""
            
            if search_key != None and search_value != None:
                sql += " and " if "where" in sql else " where "
                if search_key == "name":
                    sql += " w.{} like '%{}%' ".format(search_key, search_value)
                elif search_key == "user_id":
                    sql += " w.manager_id = {} or uw.user_id = {} ".format(search_value, search_value)
                else:
                    sql += " {} = {} ".format(search_key, search_value)
            
            if user_id is not None:
                if not "where" in sql:
                    sql += " where "
                else:
                    sql += "and "
                sql += " w.id in (select workspace_id from user_workspace WHERE user_id={}) ".format(user_id,user_id)        
            
            if sort is not None:
                if sort == "created_datetime":
                    sql += " ORDER BY w.create_datetime desc "
                elif sort == "last_run_datetime":
                    sql += " ORDER BY p.last_run_datetime desc "
            else :
                sql += " ORDER BY w.create_datetime desc, w.id asc "

            if page is not None and size is not None:
                sql += " limit {}, {} ".format((page-1)*size, size)
            
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


def get_image(image_id):
    try:
        res = None
        with get_db() as conn:

            cur = conn.cursor()
            sql = """
                SELECT *
                FROM image
                WHERE id = {}
            """.format(image_id)

            cur.execute(sql)
            res = cur.fetchone()

    except Exception as e:
        traceback.print_exc()
        pass
    return res

def reduce_joined_result(rows, reduce_by, reduce_to, reduce_column):
    res = []
    reduced_list = []
    last = None
    for row in rows:
        if row[reduce_by]!=last:
            last = row[reduce_by]
            try:
                res[-1][reduce_to] = reduced_list
            except IndexError:
                pass

            d={}
            for col in row.keys():
                if col not in reduce_column:
                    d[col] = row[col]
            res.append(d)
            reduced_list=[]

        all_null=True
        d={}
        for col in reduce_column:
            d[col] = row[col]
            if d[col] != None:
                all_null=False
        if not all_null:
            reduced_list.append(d)
    try:
        res[-1][reduce_to] = reduced_list
    except IndexError:
        traceback.print_exc()
        return False
    return res


def get_node_name(node_ip):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT n.name node_name
                FROM node n
                WHERE n.ip = %s"""
            cur.execute(sql, (node_ip))
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
        return None
