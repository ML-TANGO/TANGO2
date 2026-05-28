from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import select_query, commit_query, FetchType
from typing import List
from datetime import datetime
import traceback

def get_collect_list(workspace_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT c.*, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, c.instance_count as instance_allocate
                FROM collect c
                LEFT JOIN instance i ON c.instance_id = i.id
                """
            if workspace_id is not None:
                sql += "WHERE c.workspace_id = {}".format(workspace_id)

            cur.execute(sql)
            res = cur.fetchall()

        return res
    except Exception as e:
        raise e
    return res

def get_collect_info(collect_id=None, name=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT c.*
                FROM collect c
                LEFT JOIN instance i ON c.instance_id = i.id
                """
            if collect_id is not None:
                sql += "WHERE c.id = {}".format(collect_id)
                cur.execute(sql)
                return cur.fetchone()
            if name is not None:
                sql += "where c.name = '{}'".format(name)
                cur.execute(sql)
                return cur.fetchone()

        return res
    except Exception as e:
        raise e
    # return res

async def get_collect_info_async(collect_id=None, name=None):
    res = None
    try:
        sql = """
            SELECT c.*, i.*, u.name as create_user_name
            FROM collect c
            LEFT JOIN user u ON c.owner_id = u.id
            LEFT JOIN instance i ON c.instance_id = i.id
            """
        if collect_id is not None:
            sql += "WHERE c.id = %s"
            res = await select_query(query=sql, params=(collect_id), fetch_type=FetchType.ONE)
        if name is not None:
            sql += "where c.name = %s"
            res = await select_query(query=sql, params=(name), fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        raise e


def insert_collect(name, description, dataset_id, dataset_path=None, instance_id=None, instance_count=None, collect_method=None, collect_cycle_unit=None, collect_cycle=None,
                    collect_storage_limit=None, collect_storage_size=None, collect_storage_unit=None, collect_information_list=None,
                    access=None, owner_id=None, workspace_id=None, members=None ):
    try:
        collect_id=None
        with get_db() as conn:
            cur = conn.cursor()
            sql = "INSERT into collect(name, description, dataset_id, dataset_path, instance_id, instance_count, collect_method, collect_cycle, collect_cycle_unit, \
                    collect_storage_limit, collect_storage_size, collect_storage_unit, collect_information_list, access, owner_id, workspace_id, members ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            cur.execute(sql, (name, description, dataset_id, dataset_path, instance_id, instance_count, collect_method, collect_cycle, collect_cycle_unit, collect_storage_limit,
                               collect_storage_size, collect_storage_unit, collect_information_list, access, owner_id, workspace_id,members))

            conn.commit()
            collect_id = cur.lastrowid
        return collect_id
    except Exception as e:
        traceback.print_exc()
        raise Exception("DB insert fail")

def delete_collect(id):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            if id is not None:
                sql = "DELETE FROM collect where id in ({})".format(id)
            cur.execute(sql)
            conn.commit()
        return True
    except Exception as e:
        print(e)
        return False

async def delete_collect_async(id):
    try:
        if id is not None:
            sql = "DELETE FROM collect where id in ({})".format(id)
        res = await commit_query(sql)
        return True
    except Exception as e:
        print(e)
        return False

def update_collect(id, **kwargs):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            fields = []
            values = []

            for key, value in kwargs.items():
                if value is not None:
                    fields.append(f"{key} = %s")
                    values.append(value)
                elif key =="end_datetime" or key =="start_datetime":
                    fields.append(f"{key} = %s")
                    values.append(value)
                elif key =="status":
                    fields.append(f"{key} = %s")
                    values.append(value)
            if not fields:
                print("No fields to update.")
                return False

            sql = f"UPDATE collect SET {', '.join(fields)} WHERE id=%s"
            values.append(id)  

            cur.execute(sql, values)
            conn.commit()

        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False
    
async def update_collect_bookmark(id, bookmark):
    try:
        sql="UPDATE collect SET bookmark=%s WHERE id=%s "
        await commit_query(query=sql, params=(bookmark, id))
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False
    
async def get_public_api_list():
    try:
        sql="SELECT * FROM collect_public_api"
        res = await select_query(query=sql)
        return res
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False
                            