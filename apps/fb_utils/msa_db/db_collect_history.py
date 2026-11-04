from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import select_query, commit_query, FetchType
from typing import List
from datetime import datetime
import traceback

def get_collect_history_list(collect_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT c.*
                FROM collect_history c
                """
            if collect_id is not None:
                sql += "WHERE c.collect_id = {}".format(collect_id)

            cur.execute(sql)
            res = cur.fetchall()

        return res
    except Exception as e:
        raise e
    return res

async def get_collect_history_list_async(collect_id=None):
    res = None
    try:
        sql = """
            SELECT c.*
            FROM collect_history c
            """
        if id is not None:
            sql += "WHERE c.collect_id = %s"
            res = await select_query(query=sql, params=(collect_id), fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        raise e

def get_collect_history(id=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT c.*
                FROM collect_history c
                """
            if id is not None:
                sql += "WHERE c.id = {}".format(id)
                cur.execute(sql)
                return cur.fetchone()

        return res
    except Exception as e:
        raise e
    # return res

async def get_collect_history_async(id=None):
    res = None
    try:
        sql = """
            SELECT c.*
            FROM collect_history c
            """
        if id is not None:
            sql += "WHERE c.id = %s"
            res = await select_query(query=sql, params=(id), fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        raise e


def insert_history(collect_id, collect_info, status, status_message=None, path=None):
    try:
        # collect_id=None
        with get_db() as conn:
            cur = conn.cursor()
            sql = "INSERT into collect_history(collect_id, collect_information, status, status_message,path) values (%s,%s,%s,%s,%s)"
            cur.execute(sql, (collect_id, collect_info, status, status_message, path))

            conn.commit()
            collect_id = cur.lastrowid
        return collect_id
    except Exception as e:
        traceback.print_exc()
        raise Exception("DB insert fail")
    
async def insert_history_async(collect_id, collect_info, status, status_message=None):
    try:
        res=None
        sql = "INSERT into collect_history(collect_id, collect_info, status, status_message) values (%s,%s,%s,%s)"
        res = await commit_query(sql, params=(collect_id, collect_info, status, status_message))

        return res
    except Exception as e:
        traceback.print_exc()
        raise Exception("DB insert fail")

def delete_collect_history(id):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            if id is not None:
                sql = "DELETE FROM collect_history where id in ({})".format(id)
            cur.execute(sql)
            conn.commit()
        return True
    except Exception as e:
        print(e)
        return False
    
async def delete_collect_history_async(id):
    try:
        res=True
        if id is not None:
            sql = "DELETE FROM collect_history where id in (%s)"
            res = await commit_query(sql, params=(id))
        return res
    except:
        traceback.print_exc()
        return False

async def delete_all_collect_history_async(collect_id):
    try:
        res=True
        if collect_id is not None:
            sql = "DELETE FROM collect_history where collect_id in (%s)"
            res = await commit_query(query=sql, params=(collect_id))
        return res
    except:
        traceback.print_exc()
        return False
