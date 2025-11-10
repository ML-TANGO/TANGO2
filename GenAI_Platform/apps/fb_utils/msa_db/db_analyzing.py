from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import select_query, commit_query, FetchType
from typing import List
from datetime import datetime
import traceback
from utils import TYPE
import pymysql

def get_analyzer_list(workspace_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT a.*,
                u.name owner_name, w.name workspace_name, 
                i.instance_name instance_name, rg.name gpu_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate
                FROM analyzer a
                LEFT JOIN user u ON a.owner_id = u.id
                LEFT JOIN workspace w ON a.workspace_id = w.id 
                LEFT JOIN instance i ON a.instance_id = i.id
                LEFT JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
                """
            if workspace_id is not None:
                sql += "WHERE a.workspace_id = {}".format(workspace_id)

            cur.execute(sql)
            res = cur.fetchall()

        return res
    except Exception as e:
        traceback.print_exc()
    return res

def get_analyzer_info(analyzer_id=None, name=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT a.*,
                u.name owner_name, w.name workspace_name,
                i.instance_name instance_name, rg.name gpu_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate
                FROM analyzer a
                LEFT JOIN user u ON a.owner_id = u.id
                LEFT JOIN workspace w ON a.workspace_id = w.id 
                LEFT JOIN instance i ON a.instance_id = i.id
                LEFT JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
                """
            if analyzer_id is not None:
                sql += "WHERE a.id = {}".format(analyzer_id)
            if name is not None:
                sql += "WHERE a.name = '{}'".format(name)

            cur.execute(sql)
            return cur.fetchone()
    except Exception as e:
        traceback.print_exc()
    return res

def insert_analyzer(name, description, instance_id, instance_allocate, access, owner_id, workspace_id, graph_cpu_limit, graph_ram_limit):
    try:
        analyzer_id = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT INTO analyzer (
                    name, description, instance_id, instance_allocate, access, owner_id, workspace_id, graph_cpu_limit, graph_ram_limit
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql, (
                name, description, instance_id, instance_allocate, access, owner_id, workspace_id, graph_cpu_limit, graph_ram_limit
            ))
            conn.commit()
            analyzer_id = cur.lastrowid
        return analyzer_id
    except Exception as e:
        traceback.print_exc()
        raise Exception("DB insert fail")

def delete_analyzer(id):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            if id is not None:
                sql = "DELETE FROM analyzer where id in ({})".format(id)
            cur.execute(sql)
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

def update_analyzer(id, **kwargs):
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

            sql = f"UPDATE analyzer SET {', '.join(fields)} WHERE id = %s"
            values.append(id)  

            cur.execute(sql, values)
            conn.commit()
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

# ========================================================================
# user_analyzer
# ========================================================================

def insert_user_analyzer_list(analyzers_id, users_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            rows = []
            for i in range(len(analyzers_id)):
                    rows.append((analyzers_id[i],users_id[i]))
            sql = "INSERT IGNORE into user_analyzer(analyzer_id, user_id) values (%s,%s)"
            cur.executemany(sql, rows)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_user_analyzer(analyzers_id, users_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            rows = []
            for i in range(len(analyzers_id)):
                rows.append((analyzers_id[i],users_id[i]))
            sql = "DELETE from user_analyzer where analyzer_id = %s and user_id = %s"
            cur.executemany(sql, rows)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
def get_user_analyzer_list(analyzer_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT ua.*, u.name user_name
                FROM user_analyzer ua
                INNER JOIN user u ON u.id = ua.user_id
            """
            if analyzer_id is not None:
                cur.execute(f"{sql} where ua.analyzer_id='{analyzer_id}'")
            else:
                cur.execute(sql,)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

# ========================================================================
# Bookmark
# ========================================================================

def get_user_analyzer_bookmark_list(user_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT *
                FROM analyzer_bookmark
                WHERE user_id = %s"""
            cur.execute(sql, (user_id))
            res = cur.fetchall()
    except Exception as e:
        traceback.print_exc()
    return res

def insert_analyzer_bookmark(analyzer_id, user_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT INTO analyzer_bookmark (analyzer_id, user_id)
                VALUES (%s,%s)"""
            cur.execute(sql, (analyzer_id, user_id))
            conn.commit()
        return True, ""
    except pymysql.err.IntegrityError as ie:
        raise DuplicateKeyError("Already bookmarked")
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_analyzer_bookmark(analyzer_id, user_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                DELETE FROM analyzer_bookmark
                WHERE analyzer_id = %s AND user_id = %s"""
            cur.execute(sql, (analyzer_id, user_id))
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e


# ========================================================================
# Graph
# ========================================================================
async def insert_analyzer_graph(name, workspace_id, create_user_id, analyzer_id, dataset_id, file_path, graph_type, column, description=None):
    try:
        sql = """
        INSERT into analyzer_graph (name, description, workspace_id, create_user_id, analyzer_id, dataset_id, file_path, graph_type, `column`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        res = await commit_query(query=sql, params=(name, description, workspace_id, create_user_id, analyzer_id, dataset_id, file_path, graph_type, column))
        return res
    except Exception as e:
        traceback.print_exc()
        return False

async def get_analyzer_graph(id=None, name=None, analyzer_id=None):
    result = None
    try:
        sql = """
            SELECT *
            FROM analyzer_graph
            """
        param = []
        where = []
        if id is not None:
            where.append("id=%s")
            param.append(id)
        if name is not None:
            where.append("name=%s")
            param.append(name)
        if analyzer_id is not None:
            where.append("analyzer_id=%s")
            param.append(analyzer_id)
        if len(where) > 0:
            where = 'WHERE ' + ' AND '.join(where)
            sql += where

        result = await select_query(sql, params=param, fetch_type=FetchType.ONE)
    except Exception as e:
        traceback.print_exc()
    return result

async def get_analyzer_graph_list(analyzer_id=None):
    result = []
    try:
        sql = """SELECT ag.* FROM analyzer_graph ag """
        if analyzer_id:
            sql += " WHERE analyzer_id={}".format(analyzer_id) 
        result = await select_query(sql, fetch_type=FetchType.ALL)
    except:
        traceback.print_exc()
    return result

async def delete_analyzer_graph(analyzer_id=None, graph_id_list=None):
    try:
        sql = """DELETE FROM analyzer_graph """
        if analyzer_id:
            sql += " WHERE analyzer_id={}".format(analyzer_id)
        elif graph_id_list:
            sql +=  " WHERE id in ({})""".format(','.join(str(e) for e in graph_id_list))
        await commit_query(query=sql)
        return True
    except:
        traceback.print_exc()
        return False


# ========================================================================
# sync
# ========================================================================
def get_analyzer_graph_sync(id=None, name=None, analyzer_id=None):
    result = None
    try:
        sql = """
            SELECT ag.*, a.instance_id
            FROM analyzer_graph ag
            LEFT JOIN analyzer a ON a.id = ag.analyzer_id
            """
        param = []
        where = []
        if id is not None:
            where.append("ag.id=%s")
            param.append(id)
        if name is not None:
            where.append("ag.name=%s")
            param.append(name)
        if analyzer_id is not None:
            where.append("ag.analyzer_id=%s")
            param.append(analyzer_id)
        if len(where) > 0:
            where = 'WHERE ' + ' AND '.join(where)
            sql += where

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(sql, param)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
    return result


def get_analyzer_graph_list_sync(analyzer_id=None, running=False):
    result = []
    try:
        sql = """SELECT ag.*, a.graph_cpu_limit, a.graph_ram_limit
                FROM analyzer_graph ag
                LEFT JOIN analyzer a ON ag.analyzer_id = a.id  """
        param = []
        where = []
        if analyzer_id is not None:
            where.append("ag.analyzer_id=%s")
            param.append(analyzer_id)
        if running == True:
            where.append("ag.start_datetime IS NOT NULL and ag.end_datetime IS NULL")
        if len(where) > 0:
            where = ' WHERE ' + ' AND '.join(where)
            sql += where
        
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(sql, param)
            res = cur.fetchall()
        return res
    except:
        traceback.print_exc()
    return result


def update_start_datetime_analyzer_graph(graph_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE analyzer_graph
                SET start_datetime=CURRENT_TIMESTAMP()
                WHERE id ='{graph_id}'"""
            cur.execute(sql)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def update_end_datetime_analyzer_graph(graph_id=None, analyzer_id=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE analyzer_graph
                SET end_datetime=CURRENT_TIMESTAMP()"""
            if graph_id:
                sql += f""" WHERE id ='{graph_id}'"""
            elif analyzer_id:
                sql += f""" WHERE analyzer_id ='{analyzer_id}'"""
            cur.execute(sql)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

