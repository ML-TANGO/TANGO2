import traceback, json, os, pymysql
from utils.msa_db.db_base import get_db
from datetime import datetime
def get_node(node_name=None, node_id=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT n.*
                FROM node n
                """
            if node_name is not None:
                sql += f"""WHERE name='{node_name}'"""
            elif node_id is not None:
                sql += f"""WHERE id='{node_id}'"""
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_node_list():
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT n.*
                FROM node n
                """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def insert_node(name, ip, role, status="Not ready"):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into node(name, ip, role, status) values (%s,%s,%s,%s)"
            cur.execute(sql, (name, ip, role, status ))
            conn.commit()
            id =cur.lastrowid
        return id
    except Exception as e:
        traceback.print_exc()
        return False

def update_node(id, name=None, ip=None, role=None, status="Not ready"):
    try:
        func_arg = locals()

        node_id = func_arg.pop('id')
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


            sql = "UPDATE node set " + ", ".join([key + " = %s" for key in keys]) + " where id = %s"
            values.append(node_id)

            cur.execute(sql, values)

            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

# workspace_id = cur.lastrowid
        # return workspace_id
def get_resource_group(id=None, name=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT *
                FROM resource_group
                """
            if id is not None:
                sql += f"""WHERE id='{id}'"""
            if name is not None:
                sql += f"""WHERE name='{name}'"""
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
        return False


def insert_resource_group(name):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into resource_group(name) values (%s)"
            cur.execute(sql, (name))
            conn.commit()
            id =cur.lastrowid
        return id
    except Exception as e:
        traceback.print_exc()
        return False

def insert_gpu_cuda_info(model, cuda_core, architecture):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into gpu_cuda_info(model, cuda_core, architecture) values (%s,%s,%s)"
            cur.execute(sql, (model, cuda_core, architecture))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

def get_gpu_cuda_info(model):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT *
                FROM gpu_cuda_info
                """
            sql += f"""WHERE model='{model}'"""
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def insert_node_gpu(node_id, resource_group_id, gpu_memory, gpu_uuid):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into node_gpu(node_id, resource_group_id, gpu_memory, gpu_uuid) values (%s,%s,%s,%s)"
            cur.execute(sql, (node_id, resource_group_id, gpu_memory, gpu_uuid))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

def get_node_gpu(gpu_uuid : str = None, gpu_id : int = None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT *
                FROM node_gpu
                """
            if gpu_uuid:
                sql += f""" WHERE gpu_uuid='{gpu_uuid}'"""
            elif gpu_id:
                sql += f""" WHERE id={gpu_id}"""
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def insert_node_cpu(node_id, resource_group_id, core):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into node_cpu(node_id, resource_group_id, core) values (%s,%s,%s)"
            cur.execute(sql, (node_id, resource_group_id, core ))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

def get_node_cpu(node_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT *
                FROM node_cpu
                """
            sql += f"""WHERE node_id='{node_id}'"""
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res


def insert_node_ram(node_id, size, type, model, speed, manufacturer, count):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into node_ram(node_id, size, type, model, speed, manufacturer, count) values (%s,%s,%s,%s,%s,%s,%s)"
            cur.execute(sql, (node_id, size, type, model, speed, manufacturer, count))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        return False

def get_node_ram(node_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT *
                FROM node_ram
                """
            sql += f"""WHERE node_id='{node_id}'"""
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


#=========================
"""
Input
=====
select_list = [{
    "instance_name" : str,
    "instance_count" : int,
}]
"""
def update_instance(instance_list):
    try:
        instance_data_list = [(item["instance_total_count"], item["instance_name"],) for item in instance_list]

        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE instance
                SET instance_count=%s
                WHERE instance_name = %s"""
            cur.executemany(sql, instance_data_list)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def insert_instance(instance_list):
    try:
        instance_data_list = [(item["instance_name"], item["instance_count"], item["instance_type"],
                        item.get("gpu_group_id"), item.get("gpu_allocate"), item["cpu_allocate"], item["ram_allocate"], )
                       for item in instance_list]
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT into instance (instance_name, instance_count, instance_type, gpu_resource_group_id,  gpu_allocate, cpu_allocate, ram_allocate)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cur.executemany(sql, instance_data_list)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def insert_node_instance(node_id, instance_list):
    try:
        instance_data_list = [(node_id, item["instance_count"], item["instance_name"],)
                       for item in instance_list]
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT into node_instance (node_id, instance_allocate, instance_id)
                VALUES (%s, %s,(
                    SELECT i.id
                    FROM instance i
                    WHERE i.instance_name = %s
                ))
            """
            cur.executemany(sql, instance_data_list)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_node_instance(node_id, instance_list):
    try:
        instance_data_list = [(node_id, item["instance_name"]) for item in instance_list]
        with get_db() as conn:
            cur = conn.cursor()
            sql = """DELETE FROM node_instance
                    WHERE node_id=%s
                    AND instance_id=(
                        SELECT i.id
                        FROM instance i
                        WHERE i.instance_name=%s)"""
            cur.executemany(sql, instance_data_list)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_unused_instance():
    """instance 개수가 0 인 인스턴스 삭제"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """DELETE FROM instance
                    WHERE instance_count=0"""
            cur.execute(sql)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

#=========================

def get_instance(instance_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT i.*
                FROM instance i
                WHERE i.id = {instance_id}
                """
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_instance_list():
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT i.*
                FROM instance i"""
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_node_cpu(node_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT nc.*, n.name node_name
                FROM node_cpu nc
                INNER JOIN node n ON n.id = nc.node_id
                WHERE nc.node_id = '{node_id}'
            """
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_node_memory(node_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT nr.*, n.name node_name
                FROM node_ram nr
                INNER JOIN node n ON n.id = nr.node_id
                WHERE nr.node_id = '{node_id}'
            """
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_node_memory_list(node_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT nr.*, n.name node_name
                FROM node_ram nr
                INNER JOIN node n ON n.id = nr.node_id
                WHERE nr.node_id = '{node_id}'
            """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_node_gpu_list(node_id, group_by_gpu=False):
    """
    group_by_gpu: True 일 경우 resource_group_id 기준으로 묶음 (uuid 무시)
    """
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if group_by_gpu == True:
                sql = f"""
                SELECT ng.*, n.name node_name, rg.name resource_name, count(*) gpu_count
                FROM node_gpu ng
                INNER JOIN node n ON n.id = ng.node_id
                INNER JOIN resource_group rg ON rg.id = ng.resource_group_id
                WHERE ng.node_id = '{node_id}'
                GROUP BY ng.resource_group_id"""
            else:
                sql = f"""
                SELECT ng.*, n.name node_name, rg.name resource_name
                FROM node_gpu ng
                INNER JOIN node n ON n.id = ng.node_id
                INNER JOIN resource_group rg ON rg.id = ng.resource_group_id
                WHERE ng.node_id = '{node_id}'"""

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

#=========================

def get_node_instance_list(node_id=None, instance_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT ni.*, i.*, n.name as node_name,
                   rg.name as gpu_name
            FROM node_instance ni
            INNER JOIN instance i ON i.id = ni.instance_id
            INNER JOIN node n ON n.id = ni.node_id
            LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
            """
            if node_id:
                sql += f"""WHERE ni.node_id  = {node_id} """
            elif instance_id:
                sql += f"""WHERE i.id  = {instance_id} """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

