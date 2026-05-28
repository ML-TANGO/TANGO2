from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import select_query, FetchType
from utils import TYPE
from typing import List
from datetime import datetime
import traceback


## Single search
def get_dataset(dataset_id=None, dataset_name=None, workspace_id=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT d.*, ws.name as workspace_name, ws.data_storage_id as data_storage_id
                FROM datasets d
                INNER JOIN workspace ws ON d.workspace_id = ws.id
                """
            if dataset_id is not None:
                sql += "WHERE d.id = {}".format(dataset_id) 
            if dataset_name is not None:
                if workspace_id is not None:
                    sql += 'WHERE d.name = "{}" AND d.workspace_id = {}'.format(dataset_name, workspace_id) 
                else:
                    sql += 'WHERE d.name = "{}"'.format(dataset_name) 
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        raise e
    return res

async def get_dataset_async(dataset_id=None, dataset_name=None, workspace_id=None):
    res = None
    try:
        sql = """
            SELECT d.*, ws.name as workspace_name, ws.data_storage_id as data_storage_id,
                   s.name data_storage_name
            FROM datasets d
            INNER JOIN workspace ws ON d.workspace_id = ws.id
            LEFT JOIN storage s ON s.id = data_storage_id  
            """
        if dataset_id is not None:
            sql += "WHERE d.id = %s"
            res = await select_query(query=sql, params=(dataset_id), fetch_type=FetchType.ONE)
        if dataset_name is not None:
            if workspace_id is not None:
                sql += 'WHERE d.name = "%s" AND d.workspace_id = %s'
                res = await select_query(query=sql, params=(dataset_name, workspace_id), fetch_type=FetchType.ONE) 
            else:
                sql += 'WHERE d.name = "%s"' 
                res = await select_query(query=sql, params=(dataset_name), fetch_type=FetchType.ONE) 
        return res
    except Exception as e:
        raise e
    return res


async def get_dataset_list_new(workspace_id = None, search_key=None, search_value=None, user_id = None,
                        page = None, size = None, user_type=None):
    res = None
    try:
        
        sql = "SELECT ds.name as dataset_name, ds.create_datetime, ds.update_datetime,ds.modify_datetime, ds.access, ds.id, ds.description, ds.create_user_id, ds.filebrowser," \
                "ws.id as workspace_id, ws.name as workspace_name, u.name as owner, u2.name as workspace_manager FROM datasets as ds " \
                "INNER JOIN workspace ws ON ds.workspace_id = ws.id LEFT JOIN user u ON ds.create_user_id = u.id INNER JOIN user u2 ON u2.id = ws.manager_id"
        #sql = "SELECT * from dataset"

        if search_key is not None and search_value is not None:
            sql += "and " if "where" in sql else " where "
            if search_key == "name":
                sql += "ds.{} like '%{}%' ".format(search_key, search_value)
            elif search_key == "user_id":
                sql += "ds.create_user_id = {}".format(search_value)
            else:
                sql += "ds.{} = {} ".format(search_key, search_value)

        if workspace_id or user_id:
            if workspace_id and user_id:
                if not "where" in sql:
                    sql += " where "
                else:
                    sql += " and "
                sql += " workspace_id = {}".format(workspace_id)
            elif workspace_id:
                if not "where" in sql:
                    sql += " where "
                else:
                    sql += " and "
                sql += " workspace_id = {}".format(workspace_id)

        if page is not None and size is not None:
            sql += " limit {}, {}".format((page - 1) * size, size)
            
        res = await select_query(sql)
        return res
    except Exception as e:
        traceback.print_exc()
    return res

def get_dataset_list(workspace_id = None, search_key=None, search_value=None, user_id = None,
                        page = None, size = None, user_type=None):
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "SELECT ds.name as dataset_name, ds.create_datetime, ds.update_datetime,ds.modify_datetime, ds.access, ds.id, ds.description, ds.create_user_id, ds.filebrowser," \
                  "ws.id as workspace_id, ws.name as workspace_name, u.name as owner, u2.name as workspace_manager FROM datasets as ds " \
                  "INNER JOIN workspace ws ON ds.workspace_id = ws.id LEFT JOIN user u ON ds.create_user_id = u.id INNER JOIN user u2 ON u2.id = ws.manager_id"
            #sql = "SELECT * from dataset"

            if search_key is not None and search_value is not None:
                sql += "and " if "where" in sql else " where "
                if search_key == "name":
                    sql += "ds.{} like '%{}%' ".format(search_key, search_value)
                elif search_key == "user_id":
                    sql += "ds.create_user_id = {}".format(search_value)
                else:
                    sql += "ds.{} = {} ".format(search_key, search_value)

            if workspace_id or user_id:
                if workspace_id and user_id:
                    if not "where" in sql:
                        sql += " where "
                    else:
                        sql += " and "
                    sql += " workspace_id = {}".format(workspace_id)
                elif workspace_id:
                    if not "where" in sql:
                        sql += " where "
                    else:
                        sql += " and "
                    sql += " workspace_id = {}".format(workspace_id)

            if page is not None and size is not None:
                sql += " limit {}, {}".format((page - 1) * size, size)
            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        traceback.print_exc()
    return res

def get_dataset_used_item_tools_list(dataset_id : int , item_type : str = TYPE.PROJECT_TYPE):
    """
    동작중인 도구 리스트 
    """
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT * FROM {item_type}_tool WHERE dataset_id = {dataset_id} and request_status = 1
                """

            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        raise e
    return res

def get_dataset_used_preprocessing_jobs_list(dataset_id : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT * FROM preprocessing_job WHERE dataset_id = {dataset_id} and end_datetime IS NULL
                """

            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        raise e
    return res

def get_dataset_used_project_jobs_list(dataset_id : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT * FROM training WHERE dataset_id = {dataset_id} and end_datetime IS NULL
                """

            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        raise e
    return res

def get_dataset_used_project_hps_list(dataset_id : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT * FROM project_hps WHERE dataset_id = {dataset_id} and end_datetime IS NULL
                """

            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        raise e
    return res

def get_dataset_used_pipeline_list(dataset_id : int):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT * FROM pipeline WHERE dataset_id = {dataset_id} and start_datetime IS NOT NULL and end_datetime IS NULL
                """

            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        raise e
    return res


def get_dataset_name_list(workspace_id=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT name
                FROM datasets
                """
            if workspace_id is not None:
                sql += 'WHERE workspace_id = "{}"'.format(workspace_id) 

            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        raise e
    return res

def insert_dataset(name, workspace_id , create_user_id, access, description):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into datasets(name, workspace_id, create_user_id, access, description) values (%s,%s,%s,%s,%s)"
            cur.execute(sql, (name, workspace_id, create_user_id, access, description))

            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False



def update_dataset(id, name=None, workspace_id=None, create_user_id=None, access=None, description=None, modify_datetime=None, filebrowser=None):
    try:
        func_arg = locals()

        dataset_id = func_arg.pop('id')
        keys = []
        values = []
        for k, v in func_arg.items():
            if v is not None and v != '':
                keys.append(k)
                values.append(v)
        keys.append('update_datetime')
        values.append(datetime.today().strftime("%Y-%m-%d %H:%M:%S"))


        with get_db() as conn:
            cur = conn.cursor()


            sql = "UPDATE datasets set " + ", ".join([key + " = %s" for key in keys]) + " where id = %s"
            values.append(dataset_id)

            cur.execute(sql, values)

            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

def delete_dataset(dataset_id_list):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "DELETE FROM datasets where id in ({})".format(dataset_id_list)
            cur.execute(sql)
            conn.commit()


        return True
    except Exception as e:
        traceback.print_exc()
        return False

#TODO 삭제예정
def get_dataset_workspace_name(dataset_id_list):
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "SELECT ds.name as dataset_name, ds.access as access, ws.name as workspace_name, ws.id as workspace_id FROM datasets ds INNER JOIN workspace ws " \
                  "ON ds.workspace_id = ws.id WHERE ds.id in ({})".format(dataset_id_list)
            cur.execute(sql)
            res = cur.fetchall()

    except Exception as e:
        print(e)
        raise e
    return res


def get_user_id(user_name):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT id, user_type
                FROM user
                WHERE name = '{}'""".format(user_name)

            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res