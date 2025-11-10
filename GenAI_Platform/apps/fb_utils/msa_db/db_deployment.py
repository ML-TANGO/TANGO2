import traceback
import json
import pymysql
from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import select_query
from utils import settings


async def get_deployment_by_instance_id(instance_id : int, workspace_id : int):
    sql = """
            SELECT *
            FROM deployment
            WHERE workspace_id = %s AND instance_id = %s
        """
    res = await select_query(query=sql, params=(workspace_id, instance_id))
    return res

async def get_deployment_worker_request(deployment_id : int):
    sql = """
        SELECT *
        FROM deployment_worker
        WHERE deployment_id = %s AND end_datetime IS NULL
    """
    res = await select_query(query=sql, params=(deployment_id,))
    return res

def get_workspace_id_from_deployment_id(deployment_id):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT d.workspace_id
                FROM deployment d
                WHERE d.id = {}
            """.format(deployment_id)

            cur.execute(sql)
            res = cur.fetchone()
            if res is None:
                raise Exception("This Deployment ID Not Exist.")
            return res["workspace_id"]
    except Exception as e:
        traceback.print_exc()
        raise e


def get_deployment(deployment_name=None, deployment_id=None, workspace_id=None):
    """
    deployment_name으로 조회시 workspace_id 같이 사용
    training(job), project_hps(hps) 테이블을 모두 조인하고 training_type에 따라 값을 가져오게함
    """
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT d.*,
                       w.name workspace_name, w.id workspace_id, u.name user_name, 
                       p.name project_name, p.id project_id,
                       i.name image_name, i.real_name image_real_name,
                       it.instance_name instance_name, it.instance_count instance_total, it.gpu_allocate,
                       it.cpu_allocate, it.ram_allocate,
                       rg.name gpu_name, rg.id resource_group_id, 
                       rg.name resource_name, b.name built_in_model_name,
                CASE
                    WHEN d.training_type='job' THEN t.name
                    WHEN d.training_type='hps' THEN ph.name
                END AS training_name,
                CASE
                    WHEN d.is_new_model=1 THEN d.huggingface_model_id
                    WHEN d.is_new_model=0 THEN p.huggingface_model_id
                END AS deployment_huggingface_model_id,
                CASE
                    WHEN d.is_new_model=1 THEN d.huggingface_model_token
                    WHEN d.is_new_model=0 THEN p.huggingface_token
                END AS deployment_huggingface_model_token
                FROM deployment d
                INNER JOIN workspace w ON d.workspace_id = w.id
                INNER JOIN user u ON d.user_id = u.id
                LEFT JOIN project p ON p.id = d.project_id
                LEFT JOIN image i ON i.id = d.image_id
                LEFT JOIN instance it ON it.id = d.instance_id
                LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
                LEFT JOIN training t ON t.id = d.training_id
                LEFT JOIN project_hps ph ON ph.id = d.training_id
                LEFT JOIN built_in_model b ON b.id = d.built_in_model_id
            """
            # rg.name resource_name, 
                # LEFT JOIN resource_group rg ON rg.id = d.gpu_resource_group_id

            if deployment_name is not None and workspace_id is not None:
                sql += "where d.name=%s and d.workspace_id=%s"
                cur.execute(sql, (deployment_name, workspace_id ))
            elif deployment_id is not None:
                sql += "where d.id=%s"
                cur.execute(sql, (deployment_id,))
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_deployment_list_by_instance_not_null(workspace_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT d.*, i.cpu_allocate, i.ram_allocate
                FROM deployment d
                LEFT JOIN instance i ON i.id = d.instance_id
                WHERE d.workspace_id = %s and d.instance_id IS NOT NULL
            """
            cur.execute(sql, (workspace_id, ))
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_deployment_list(deployment_id_list: list=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT d.*, w.id workspace_id, w.name workspace_name, u.name user_name,
                i.gpu_allocate, i.cpu_allocate, i.ram_allocate, i.instance_name, rg.name as gpu_name
                FROM deployment d
                INNER JOIN workspace w ON d.workspace_id = w.id
                INNER JOIN user u ON d.user_id = u.id
                LEFT JOIN instance i ON i.id = d.instance_id
                LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
            """
            if deployment_id_list is not None:
                deployment_id = [str(id) for id in deployment_id_list]
                deployment_id = ','.join(deployment_id)
                sql = f"{sql} WHERE d.id IN ({deployment_id})"
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_deployment_list_in_workspace(workspace_name=None, workspace_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT d.*, w.name workspace_name, u.name user_name,
                    i.instance_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, rg.name as resource_name,
                CASE
                    WHEN d.is_new_model=1 THEN d.huggingface_model_id
                    WHEN d.is_new_model=0 THEN p.huggingface_model_id
                END AS huggingface_model_id
                FROM deployment d
                INNER JOIN workspace w ON d.workspace_id = w.id
                INNER JOIN user u ON d.user_id = u.id
                LEFT JOIN instance i ON i.id = d.instance_id
                LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
                LEFT JOIN project p ON p.id = d.project_id
            """
            if workspace_name is not None:
                cur.execute(f"{sql} where d.name='{workspace_name}'")
            elif workspace_id is not None:
                cur.execute(f"{sql} where d.workspace_id = {workspace_id}")
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_deployment_worker(deployment_worker_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT dw.*,
                       d.name deployment_name, d.workspace_id workspace_id, d.api_path api_path,
                       w.name workspace_name,  p.name project_name,
                       i.id image_id, i.name image_name, rg.name gpu_name, d.instance_id,
                       it.instance_name instance_name, wr.deployment_cpu_limit deployment_cpu_limit, wr.deployment_ram_limit deployment_ram_limit 
                FROM deployment_worker dw
                INNER JOIN deployment d ON d.id = dw.deployment_id
                INNER JOIN workspace w ON w.id = d.workspace_id
                LEFT JOIN image i on i.id = dw.image_id
                LEFT JOIN project p ON p.id = dw.project_id
                LEFT JOIN instance it ON it.id = d.instance_id
                LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
                LEFT JOIN workspace_resource wr ON wr.workspace_id = w.id
                WHERE dw.id = '{deployment_worker_id}'
            """
            # rg.name resource_name,
                # LEFT JOIN resource_group rg ON rg.id = dw.resource_group_id

            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res


def get_deployment_worker_running(deployment_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                select dw.*
                FROM deployment_worker dw
                WHERE dw.deployment_id = {deployment_id} AND start_datetime IS NOT NULL AND end_datetime IS NULL
            """
            
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_deployment_worker_list(deployment_id=None, running=True, workspace_id=None, day=False, project_id=None):
    """running True는 end_datatime이 null 인 경우, 
       running False는 중지된 워커 (end_datatime null 이 아닐때)
       running ALL 은 실행중 + 중지된 워커 모두

       project_id 사용시 check_related_deployment에서 쓰는거라 model_type이 huggingface, built-in인 것만 조회
    """
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                select dw.*, dw.id deployment_worker_id, d.name deployment_name, d.model_type,
                       w.name workspace_name, w.id workspace_id, rg.name gpu_name, d.api_path api_path,
                       it.instance_name, it.cpu_allocate, it.gpu_allocate, it.ram_allocate,
                        d.deployment_cpu_limit deployment_cpu_limit, d.deployment_ram_limit deployment_ram_limit 
                FROM deployment_worker dw
                INNER JOIN deployment d ON d.id = dw.deployment_id
                INNER JOIN workspace w ON w.id = d.workspace_id
                LEFT JOIN instance it ON it.id = d.instance_id
                LEFT JOIN resource_group rg ON rg.id = it.gpu_resource_group_id
                LEFT JOIN workspace_resource wr ON wr.workspace_id = w.id
            """
            # , rg.name resource_name
                # LEFT JOIN resource_group rg ON rg.id = d.resource_group_id

            add_sql = []
            if deployment_id is not None:
                add_sql.append(f"dw.deployment_id='{deployment_id}'")
            
            if workspace_id is not None:
                add_sql.append(f"d.workspace_id='{workspace_id}'")

            if running == "ALL":
                pass
            else:            
                if running == True:
                    add_sql.append("dw.end_datetime IS NULL")
                if running == False:
                    add_sql.append("dw.end_datetime IS NOT NULL")
            
            if project_id:
                add_sql.append(f"d.project_id='{project_id}' AND (d.model_type='huggingface' OR d.model_type='built-in')")

            if day == True:
                # end_datetime이 null이거나 24시간 전 이후인 경우 (24시간 이내에 동작중이던 워커 조회)
                add_sql.append(" (dw.end_datetime IS NULL OR dw.end_datetime >= NOW() - INTERVAL 1 DAY) ")
                
            if len(add_sql) > 0:
                tmp = ' AND '.join(add_sql)
                sql += f"WHERE {tmp}"
            
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_deployment_users(deployment_id=None, include_owner=True):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT DISTINCT u.id, u.name AS user_name, d.id as deployment_id
                FROM deployment d
                INNER JOIN user_deployment ud ON ud.deployment_id = d.id
                LEFT JOIN user_workspace uw ON d.workspace_id = uw.workspace_id and d.access= 1
                left JOIN user u ON u.id = uw.user_id OR u.id = ud.user_id 
            """

            if deployment_id is not None:
                sql += " WHERE d.id = {} ".format(deployment_id)
                if include_owner == False:
                    sql += "  AND ((u.id != ud.user_id) OR (ut.user_id != d.user_id))"

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def check_workspace_deployment_name(workspace_id, deployment_name):
    """True이면 존재, False이면 존재X"""
    result = True
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT *
                FROM deployment d
                WHERE d.workspace_id=%s and d.name=%s
            """
            cur.execute(sql, (workspace_id, deployment_name))
            res = cur.fetchall()
            result = True if len(res) > 0 else False
    except:
        traceback.print_exc()
    return result
    

# =====================================================
def insert_deployment(workspace_id, user_id, name, access, instance_type, instance_id, instance_allocate, api_path,
                      description=None, deployment_cpu_limit=None, deployment_ram_limit=None,
                      model_type=None, project_id=None, training_id=None, training_type=None,
                      huggingface_model_id=None, huggingface_model_token=None, built_in_model_id=None, model_category=None, is_new_model=0):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT into deployment (workspace_id, name, description, access, user_id, instance_type, instance_id, instance_allocate,
                                        api_path, deployment_cpu_limit, deployment_ram_limit,
                                        model_type, project_id, training_id, training_type,
                                        huggingface_model_id, huggingface_model_token, built_in_model_id, model_category, is_new_model)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            cur.execute(sql, (workspace_id, name,  description, access, user_id, instance_type, instance_id, instance_allocate,
                              api_path, deployment_cpu_limit, deployment_ram_limit, model_type, project_id, training_id, training_type,
                              huggingface_model_id, huggingface_model_token, built_in_model_id, model_category, is_new_model))
            lastrowid = cur.lastrowid
            conn.commit()
        return {
            'result':True,
            'message':'',
            'id': lastrowid
        }
    except Exception as e:
        traceback.print_exc()
        return {
            'result':False,
            'message':e
        }
        
def insert_user_deployment_list(deployments_id, users_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            rows = []
            for i in range(len(deployments_id)):
                    rows.append((deployments_id[i],users_id[i]))
            sql = "INSERT IGNORE into user_deployment(deployment_id, user_id) values (%s,%s)"
            cur.executemany(sql, rows)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_user_deployment(deployments_id, users_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            rows = []
            for i in range(len(deployments_id)):
                rows.append((deployments_id[i],users_id[i]))
            sql = "DELETE from user_deployment where deployment_id = %s and user_id = %s"
            cur.executemany(sql, rows)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e    
    
def delete_deployments(deployment_ids = []):
    if len(deployment_ids) == 0:
        return True
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = "delete from deployment where id in ({})".format(','.join(str(e) for e in deployment_ids))
            cur.execute(sql)
            conn.commit()

        return True
    except:
        traceback.print_exc()
        return False


def update_all_deployment_resource(workspace_id, **kwargs):
    try:
        columns = []
        values = []
        for column, value in kwargs.items():
            if value is not None:
                columns.append(f"{column}=%s")
                values.append(value)
        columns_str = ", ".join(columns)
        values.append(workspace_id)

        with get_db() as conn:
            cur = conn.cursor()
            sql = f""" UPDATE deployment SET {columns_str} WHERE workspace_id=%s"""
            cur.execute(sql, values)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
 
def update_deployment(deployment_id, **kwargs):
    try:
        columns = []
        values = []
        for column, value in kwargs.items():
            if value is not None:
                columns.append(f"{column}=%s")
                values.append(value)
        columns_str = ", ".join(columns)
        values.append(deployment_id)

        with get_db() as conn:
            cur = conn.cursor()
            sql = f""" UPDATE deployment SET {columns_str} WHERE id=%s"""
            cur.execute(sql, values)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def update_deployment_worker_setting(deployment_id, **kwargs):
    # project_id, command, environments, gpu_per_worker, gpu_cluster_setting, gpu_cluster_list, docker_image_id,
    try:
        columns = []
        values = []
        
        # 전달된 키워드 인수를 검사하여 업데이트할 값 준비
        for column, value in kwargs.items():
            if column == "docker_image_id":
                column = "image_id"
            elif column == "command" or column == "environments":
                value = json.dumps(value)
            columns.append(f"{column}=%s")
            values.append(value)

        # SQL 쿼리 생성
        columns_str = ", ".join(columns)
        sql = f"UPDATE deployment SET {columns_str} WHERE id=%s"
        values.append(deployment_id)
        
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(sql, values)
            
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def insert_deployment_worker_item(deployment_id, instance_id, instance_type, gpu_per_worker, project_id, image_id, command, environments, pod_count=1):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT into deployment_worker (deployment_id, instance_id, instance_type, gpu_per_worker, project_id, image_id, command, environments, pod_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql, (deployment_id, instance_id, instance_type, gpu_per_worker, project_id, image_id, command, environments, pod_count))
            lastrowid = cur.lastrowid
            conn.commit()
        return {'result': True, 'message': None, 'id': lastrowid}
    except pymysql.Error as e:
        print(e)
    except Exception as e:
        traceback.print_exc()
        return {"result" : False, 'message' : None, "id" : None}

def delete_deployment_worker(deployment_worker_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"DELETE FROM deployment_worker WHERE id='{deployment_worker_id}'"
            cur.execute(sql)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, str(e)

def delete_deployment_worker_list(deployment_worker_id_list):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            format_strings = ','.join(['%s'] * len(deployment_worker_id_list))
            sql = f"DELETE FROM deployment_worker WHERE id IN ({format_strings})"
            cur.execute(sql, deployment_worker_id_list)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, str(e)

def update_end_datetime_deployment_worker(deployment_worker_id=None, deployment_id=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE deployment_worker
                SET end_datetime=CURRENT_TIMESTAMP()"""
            if deployment_worker_id:
                sql += f""" WHERE id ='{deployment_worker_id}'"""
            elif deployment_id:
                sql += f""" WHERE deployment_id ='{deployment_id}'"""
            cur.execute(sql)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def update_deployment_worker_description(deployment_worker_id, description):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = "UPDATE deployment_worker set description = %s where id = %s"
            cur.execute(sql,(description, deployment_worker_id))
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
def update_start_datetime_deployment_worker(deployment_worker_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE deployment_worker
                SET start_datetime=CURRENT_TIMESTAMP()
                WHERE id ='{deployment_worker_id}'"""
            cur.execute(sql)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e


def update_deployment_training_id(deployment_id, project_id):
    """파이프라인 워커 배포시 사용"""
    try:
        training_id=None
        with get_db() as conn:
            cur = conn.cursor()
            sql_select = f"""
                SELECT id
                FROM (
                    SELECT j.id FROM training j WHERE j.project_id = '{project_id}'
                    UNION ALL
                    SELECT h.id FROM project_hps h WHERE h.project_id = '{project_id}'
                ) AS combined
                ORDER BY id DESC
                LIMIT 1
                """
            cur.execute(sql_select)
            select_result = cur.fetchone()
            if select_result:
                training_id = select_result.get("id")
                sql_update = f"""
                    UPDATE deployment
                    SET training_id = '{training_id}'
                    WHERE id = '{deployment_id}'
                """
                cur.execute(sql_update)
                conn.commit()
        return training_id
    except Exception as e:
        traceback.print_exc()
        return None


# bookmark ============================================
def get_user_deployment_bookmark_list(user_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT *
                FROM deployment_bookmark
                WHERE user_id = %s"""
            cur.execute(sql, (user_id))
            res = cur.fetchall()
    except Exception as e:
        traceback.print_exc()
    return res

def insert_deployment_bookmark(deployment_id, user_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT INTO deployment_bookmark (deployment_id, user_id)
                VALUES (%s,%s)"""
            cur.execute(sql, (deployment_id, user_id))
            conn.commit()
        return True, ""
    except pymysql.err.IntegrityError as ie:
        raise DuplicateKeyError("Already bookmarked")
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_deployment_bookmark(deployment_id, user_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                DELETE FROM deployment_bookmark
                WHERE deployment_id = %s AND user_id = %s"""
            cur.execute(sql, (deployment_id, user_id))
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

# dataform ============================================
def insert_deployment_data_form(deployment_id, location, method, api_key, value_type, category, category_description):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                REPLACE into deployment_data_form (deployment_id, location, method, api_key, value_type, category, category_description)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """
            cur.execute(sql, (deployment_id, location, method, api_key, value_type, category, category_description,))
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_deployment_data_form(deployment_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                delete
                from deployment_data_form
                where deployment_id = {}
            """.format(deployment_id)
            cur.execute(sql)
            conn.commit()

        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def copy_built_in_data_form(deployment_id, built_in_model_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT INTO deployment_data_form (deployment_id, location, method, api_key, value_type, category, category_description)
                SELECT %s, location, method, api_key, value_type, category, category_description
                FROM built_in_model_data_form
                WHERE built_in_model_id = %s
            """
            cur.execute(sql, (deployment_id, built_in_model_id))
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e


# gpu ==================================================
def get_deployment_gpu_workspace(workspace_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT wrm.*, rg.name model_name
                FROM workspace_resource_manage wrm
                INNER JOIN resource_group rg ON rg.id = wrm.resource_group_id
            """
            if workspace_id is not None:
                cur.execute(f"{sql} where wrm.workspace_id='{workspace_id}' AND type='deployment'")
            else:
                cur.execute(f"{sql} where type='deployment'")
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_deployment_gpu_allocated_workspace(workspace_id, resource_group_id):
    """
    gpu & workspace_id 조건 -> deployment에 할당된 gpu 개수 
    """
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT d.*
                FROM deployment d
                WHERE d.workspace_id='{workspace_id}' AND d.resource_group_id='{resource_group_id}'
            """
            cur.execute(sql,)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

# simultation =========================================

def get_service_list(workspace_id=None):
    """group by는 deployment_input_form 이 여러개 row 일 수 있으므로 list로 묶어줌
    """
    res = []
    try:
        with get_db() as conn:

            cur = conn.cursor()
            sql = """
                SELECT d.*, u.name AS creator,
                GROUP_CONCAT(ddf.category) as input_type_list
                FROM deployment d
                LEFT JOIN user u ON u.id = d.user_id
                LEFT JOIN workspace w ON d.workspace_id = w.id
                LEFT JOIN deployment_data_form ddf ON ddf.deployment_id = d.id
            """

            sql_list = []
            if workspace_id is not None:
                sql_list.append(""" d.workspace_id={} """.format(workspace_id))
            if settings.LLM_USED:
                sql_list.append(" d.llm=0 ")
            
            if len(sql_list) > 0:
                sql += " where " + " and ".join(sql_list)

            sql += "GROUP BY d.id"
            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        traceback.print_exc()
        pass
    return res

def get_service(deployment_id=None):
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()
            sql = """
                SELECT d.*, u.name AS creator,
                GROUP_CONCAT(JSON_OBJECT('location', ddf.location, 'method', ddf.method, 'api_key', ddf.api_key, 'value_type', ddf.value_type, 'category', ddf.category, 'category_description', ddf.category_description) SEPARATOR ', ') as data_input_form_list
                FROM deployment d
                LEFT JOIN user u ON u.id = d.user_id
                LEFT JOIN workspace w ON d.workspace_id = w.id
                LEFT JOIN deployment_data_form ddf ON ddf.deployment_id = d.id
                
            """
            if deployment_id is not None:
                sql += """ where d.id = {} """.format(deployment_id)
            
            sql += """GROUP BY d.id, d.name"""
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        traceback.print_exc()
        pass
    return res



# =====================================================

def get_user_list_deployment(deployment_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT ud.*, u.name user_name
                FROM user_deployment ud
                INNER JOIN user u ON u.id = ud.user_id
            """
            if deployment_id is not None:
                cur.execute(f"{sql} where ud.deployment_id='{deployment_id}'")
            else:
                cur.execute(sql,)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_user_list_workspace(workspace_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT uw.*, u.name user_name
                FROM user_workspace uw
                INNER JOIN user u ON u.id = uw.user_id
            """
            if workspace_id is not None:
                cur.execute(f"{sql} where uw.workspace_id='{workspace_id}'")
            else:
                cur.execute(sql,)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def check_user_in_workspace(user_id, workspace_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT *
                FROM user_workspace uw
                WHERE uw.user_id in (%s) AND uw.workspace_id in (%s)"""

            cur.execute(sql, (user_id, workspace_id,))
            res = cur.fetchone()
    except Exception as e:
        traceback.print_exc()
    return res

def get_workspace_info_storage(workspace_id=None, workspace_name=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT w.*, main.name main_storage_name, data.name data_storage_name
                FROM workspace w
                LEFT JOIN storage main ON main.id = w.main_storage_id
                LEFT JOIN storage data ON data.id = w.data_storage_id
                """
            if workspace_id is not None:
                sql += """WHERE w.id = '{}'""".format(workspace_id)
            elif workspace_name is not None:
                sql += """WHERE w.name = '{}'""".format(workspace_name)
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        return None

def get_image_list(workspace_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT DISTINCT i.*
                FROM image i
                LEFT JOIN image_workspace iw ON iw.image_id = i.id
            """
            if workspace_id is not None:
                sql += """WHERE (i.access = 1) or (i.access = 0 and iw.workspace_id = {})""".format(workspace_id)
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_project(project_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT p.*, w.name workspace_name,
                    s.name main_storage_name
                FROM project p
                LEFT JOIN workspace w ON w.id = p.workspace_id
                LEFT JOIN storage s ON s.id = w.main_storage_id
                WHERE p.id = '{}'""".format(project_id)
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        return None

def get_workspace_custom_training_list(workspace_id, user_id=None):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT p.*, w.name workspace_name, IF(pb.user_id IS NOT NULL, 1, 0) as bookmark,
                        u.name as user_name, GROUP_CONCAT(up.user_id) AS user_ids
                FROM project p
                INNER JOIN workspace w ON w.id = p.workspace_id
                LEFT JOIN project_bookmark pb ON pb.project_id=p.id AND pb.user_id = '{user_id}'
                LEFT JOIN user u on u.id = p.create_user_id
                LEFT JOIN user_project up ON p.id = up.project_id
                WHERE p.workspace_id = '{workspace_id}' AND p.type != 'built-in' GROUP BY p.id """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_worker_path_info(deployment_worker_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT dw.id deployment_worker_id,
                    d.name deployment_name, w.name workspace_name, main.name main_storage_name, data.name data_storage_name
                FROM deployment_worker dw
                LEFT JOIN deployment d ON d.id = dw.deployment_id
                LEFT JOIN workspace w ON w.id = d.workspace_id
                LEFT JOIN storage main ON main.id = w.main_storage_id
                LEFT JOIN storage data ON data.id = w.data_storage_id
                """
            if deployment_worker_id is not None:
                sql += """WHERE dw.id = '{}'""".format(deployment_worker_id)
            cur.execute(sql)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        return None

def get_workspace_users(workspace_id=None):
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()
            sql = """SELECT u.id, u.name as user_name, uw.favorites, uw.workspace_id as workspace_id
                FROM user_workspace uw
                INNER JOIN user u ON uw.user_id = u.id
            """
            if workspace_id is not None:
                sql += "WHERE workspace_id = {}".format(workspace_id)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

# 옵션 ==============================================================
def get_deployment_instance_used_gpu(workspace_id, instance_id):
    res = dict()
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT SUM(gpu_per_worker) as used_gpu
                FROM deployment d
                WHERE d.workspace_id='{workspace_id}' AND d.instance_id='{instance_id}'"""
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

# instance ==============================================================

def get_workspace_instance(workspace_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT i.id id, i.instance_name name, wi.instance_allocate instance_total, i.instance_type instance_type,
                           i.ram_allocate ram_allocate, i.cpu_allocate cpu_allocate, i.gpu_allocate gpu_allocate,
                           rg.name resource_name
                    FROM workspace_instance wi
                    INNER JOIN instance i ON i.id = wi.instance_id
                    LEFT JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
                    WHERE wi.workspace_id=%s
                """
            cur.execute(sql, (workspace_id))
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_instance_node_name(instance_id):
    res = dict()
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT n.name node_name
                FROM instance i
                INNER JOIN node_gpu ng ON ng.resource_group_id = i.gpu_resource_group_id
                INNER JOIN node n ON n.id = ng.node_id
                WHERE i.id='{instance_id}'
                GROUP BY i.gpu_resource_group_id"""
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res


# playground ==============================================================
def insert_deployment_llm(**kwargs):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            columns = []
            values = []
            
            for column, value in kwargs.items():
                columns.append(column)
                values.append(value)
        
            placeholders = ','.join(['%s'] * len(columns))
            columns_str = ", ".join(columns)    

            sql = """INSERT INTO deployment ({columns_str}) VALUES({placeholders})""".format(columns_str=columns_str, placeholders=placeholders) 
            cur.execute(sql,(values))
            conn.commit()
            lastrowid = cur.lastrowid
        return {'result': True, 'message': None, 'id': lastrowid}
    except:
        traceback.print_exc()
        return {"result" : False, 'message' : None, "id" : None}



def get_deployment_llm_list(workspace_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """SELECT * FROM deployment d WHERE d.llm != 0 AND d.workspace_id=%s"""
            cur.execute(sql, (workspace_id))
            res = cur.fetchall()
            return res
    except:
        traceback.print_exc()
        return []