import traceback
import json
import time
from datetime import date, datetime, timedelta
from threading import Timer
import os.path
import sqlite3
import pwd
import os
import pymysql
import json
import time
from collections import OrderedDict
import re
from utils.msa_db.db_base import get_db
# from utils import common

def get_basic_cost():
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT *
                FROM workspace_basic_cost
                ORDER BY id DESC
                LIMIT 1
                """
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        raise e
    return res

def insert_basic_cost(time_unit , time_unit_cost, members, add_member_cost, out_bound_network):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into workspace_basic_cost(time_unit, time_unit_cost, members, add_member_cost, out_bound_network) values (%s,%s,%s,%s,%s)"
            cur.execute(sql, (time_unit , time_unit_cost, members, add_member_cost, out_bound_network))

            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False
    
    
def insert_instance_cost_plan(name, instance_list, time_unit, time_unit_cost, type):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into instance_cost_plan(name, instance_list, time_unit, time_unit_cost, type) values (%s,%s,%s,%s,%s)"
            cur.execute(sql, (name, instance_list, time_unit, time_unit_cost, type))

            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False
    
def update_instance_cost_plan(id, **kwargs):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            fields = []
            values = []

            for key, value in kwargs.items():
                if value is not None:
                    fields.append(f"{key} = %s")
                    values.append(value)

            if not fields:
                print("No fields to update.")
                return False

            sql = f"UPDATE instance_cost_plan SET {', '.join(fields)} WHERE id = %s"
            values.append(id)  

            cur.execute(sql, values)
            conn.commit()

        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False
    

def delete_instance_cost_plan(id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM instance_cost_plan WHERE id = {id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
def get_instance_cost_plan(id : int = None, name=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT *
                FROM instance_cost_plan """
                
            if name is not None:
                sql += f" WHERE name = '{name}'"
            elif id is not None:
                sql += f" WHERE id='{id}'"
            
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_instance_cost_plan_list():
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT *
                FROM instance_cost_plan """
                
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

    
def insert_storage_cost_plan(name, source, size_unit, size, storage_id, cost):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into storage_cost_plan(name, source, size_unit, size, storage_id, cost) values (%s,%s,%s,%s,%s,%s)"
            cur.execute(sql, (name, source, size_unit, size, storage_id, cost))

            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

def update_storage_cost_plan(id, **kwargs):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            fields = []
            values = []

            for key, value in kwargs.items():
                if value is not None:
                    fields.append(f"{key} = %s")
                    values.append(value)

            if not fields:
                print("No fields to update.")
                return False

            sql = f"UPDATE storage_cost_plan SET {', '.join(fields)} WHERE id = %s"
            values.append(id)  

            cur.execute(sql, values)
            conn.commit()

        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

def delete_storage_cost_plan(id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                DELETE FROM storage_cost_plan WHERE id = {id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def get_storage_cost_plan(id : int = None, name=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT *
                FROM storage_cost_plan """
                
            if name is not None:
                sql += f" WHERE name = '{name}'"
            elif id is not None:
                sql += f" WHERE id='{id}'"
            
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_storage_cost_plan_list():
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                SELECT *
                FROM storage_cost_plan """
                
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res