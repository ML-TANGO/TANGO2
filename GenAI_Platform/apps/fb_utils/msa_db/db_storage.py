from utils.msa_db.db_base import get_db
from typing import List
from datetime import datetime
import traceback

def get_storage(storage_id=None, name=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT s.*
                FROM storage s
                """
            if storage_id is not None:
                sql += "WHERE s.id = {}".format(storage_id)
                cur.execute(sql)
                return cur.fetchone()
            if name is not None:
                sql += "where s.name = '{}'".format(name)
                cur.execute(sql)
                return cur.fetchone()

            cur.execute(sql)
            res = cur.fetchall()

        return res
    except Exception as e:
        raise e
    return res

def insert_storage(ip, name, type, mountpoint, data_sc=None, main_sc=None, size=None):
    try:
        with get_db() as conn:

            cur = conn.cursor()
            sql = "INSERT into storage(ip, name, type, data_sc, main_sc, mountpoint, size) values (%s,%s,%s,%s,%s,%s,%s)"
            cur.execute(sql, ((ip, name, type, data_sc, main_sc, mountpoint, size)))

            conn.commit()
            storage_id = cur.lastrowid
        return storage_id
    except Exception as e:
        traceback.print_exc()
        raise Exception("DB insert fail")
def update_storage(id, ip=None, type=None, data_sc=None, main_sc=None, mountpoint=None, size=None):
    try:
        func_arg = locals()
        storage_id = func_arg.pop('id')
        keys = []
        values = []
        for k, v in func_arg.items():
            if (v is not None) and (v is not ''):
                keys.append(k)
                values.append(v)

        with get_db() as conn:
            cur = conn.cursor()
            sql = "UPDATE storage set " + ", ".join([key + " = %s" for key in keys]) + " where id = %s"
            values.append(storage_id)

            cur.execute(sql, values)
            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

def delete_storage(storage_id_list=None,name=None):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            if storage_id_list is not None:
                sql = "DELETE FROM storage where id in ({})".format(storage_id_list)
            if storage_id_list is not None:
                sql = "DELETE FROM storage where name in ({})".format(name)
            cur.execute(sql)
            conn.commit()

        return True
    except Exception as e:
        print(e)
        return False
