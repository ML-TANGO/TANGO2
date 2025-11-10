from utils import TYPE
from utils.msa_db.db_base import get_db, pymysql
from utils.msa_db.db_base_async import select_query, commit_query, FetchType
from typing import List
import traceback
import json


#####################
# SELECT
#####################

async def get_pipeline_duplicate_name(workspace_id : int, pipeline_name : str):
    sql = """
        SELECT * FROM pipeline WHERE workspace_id = %s AND name = %s
    """
    res = await select_query(sql, params=( workspace_id, pipeline_name), fetch_type=FetchType.ONE)
    return res

async def get_pipeline_histories(pipeline_id : int):
    sql = """
        SELECT ph.*, u.name as start_user_name
        FROM pipeline_history ph
        LEFT JOIN user u ON u.id = ph.start_user_id
        WHERE ph.pipeline_id = %s
    """
    res = await select_query(sql, params=( pipeline_id, ))
    return res

async def get_pipeline_history(pipeline_history_id : int):
    sql = """
        SELECT ph.*, u.name as start_user_name
        FROM pipeline_history ph
        LEFT JOIN user u ON u.id = ph.start_user_id
        WHERE ph.id = %s
    """
    res = await select_query(sql, params=( pipeline_history_id, ), fetch_type=FetchType.ONE)
    return res


async def get_dataset(dataset_id):
    sql = """
        SELECT d.id, d.name, d.create_datetime, d.update_datetime, u.name as create_user_name, d.description, d.access
        FROM datasets d
        LEFT JOIN user u ON u.id = d.create_user_id
        WHERE d.id = %s
    """
    res = await select_query(sql, (dataset_id, ), FetchType.ONE)
    return res

async def get_task_deployment_items(workspace_id : int):
    sql = f"""
        SELECT t.id, t.name, t.instance_id, t.instance_allocate, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, i.instance_name, rg.name as resource_name, t.model_type AS type
        FROM deployment t
        LEFT JOIN instance i ON i.id = t.instance_id
        LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
        WHERE workspace_id = {workspace_id} AND t.instance_id IS NOT NULL AND llm = 0
    """
    # AND i.instance_type = '{TYPE.RESOURCE_TYPE_GPU}'
    res = await select_query(sql)
    return res

async def get_task_items(workspace_id : int, task_type : str):
    sql = f"""
        SELECT t.id, t.name, t.instance_id, t.instance_allocate, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, i.instance_name, rg.name as resource_name, t.type
        FROM {task_type} t
        LEFT JOIN instance i ON i.id = t.instance_id
        LEFT JOIN resource_group rg ON rg.id = i.gpu_resource_group_id
        WHERE workspace_id = {workspace_id} AND t.instance_id IS NOT NULL
    """
    # if task_type == TYPE.PROJECT_TYPE:
    #     sql += f" AND i.instance_type = '{TYPE.RESOURCE_TYPE_GPU}'"
    res = await select_query(sql)
    return res

async def get_task_item(task_item_id : int, task_type : str):
    sql = f"""
        SELECT t.*, w.name as workspace_name, s.name as main_storage_name
        FROM {task_type} t
        JOIN workspace w ON w.id = t.workspace_id
        LEFT JOIN storage s ON s.id = w.main_storage_id
        WHERE t.id = {task_item_id}
    """
    res = await select_query(sql, fetch_type=FetchType.ONE)
    return res

async def get_task_training_info(task_item_job_id : int):
    sql = f"""
        SELECT *
        FROM training
        WHERE id = {task_item_job_id}
    """
    res = await select_query(sql, fetch_type=FetchType.ONE)
    return res

async def get_task_worker_info(task_item_job_id : int):
    sql = f"""
        SELECT *
        FROM deployment_worker
        WHERE id = {task_item_job_id}
    """
    res = await select_query(sql, fetch_type=FetchType.ONE)
    return res

async def get_users(workspace_id : int):
    sql = """
        SELECT u.id, u.name
        FROM user_workspace 
        JOIN user u ON u.id = uw.user_id
        WHERE uw.workspace_id = %s
    """
    res = await select_query(sql, params=( workspace_id, ))
    return res

async def get_datasets(workspace_id : int):
    sql = """
        SELECT d.id, d.name, d.access, d.create_user_id
        FROM datasets d
        WHERE d.workspace_id = %s
    """
    res = await select_query(sql, params=( workspace_id, ))
    return res

async def get_images(workspace_id : int):
    sql = """
        SELECT i.id, i.name
        FROM image i
        LEFT JOIN image_workspace iw ON i.id=iw.image_id
        LEFT JOIN workspace w ON iw.workspace_id=w.id
        WHERE (i.access = 1) or (i.access = 0 and iw.workspace_id = %s)
        ORDER BY id DESC
    """
    res = await select_query(sql, params=( workspace_id, ))
    return res


async def get_pipelines(workspace_id : int) -> List[dict]:
    sql = """
        SELECT p.id, p.name, p.description, p.access, p.type,
        DATE_FORMAT(p.create_datetime, %s) AS create_datetime,
        p.start_datetime, p.end_datetime, p.start_dataset_size, p.retraining_wait_start_time, p.retraining_count, p.retraining_type, p.retraining_unit, p.retraining_value,
        w.name as workspace_name, u.name as owner_name
        FROM pipeline p
        JOIN workspace w ON w.id = p.workspace_id
        LEFT JOIN user u ON u.id = p.owner_id
        WHERE p.workspace_id = %s
    """
    res = await select_query(sql, params=( TYPE.TIME_DATE_FORMAT_SQL, workspace_id))
    return res

async def get_workspace(workspace_id : int):
    try:
        sql = """
            SELECT w.*, sm.name as main_storage_name, sd.name as data_storage_name
            FROM workspace w
            JOIN storage sd ON w.data_storage_id = sd.id
            JOIN storage sm ON w.main_storage_id = sm.id
            WHERE w.id = %s
        """
        res = await select_query(sql, params=( workspace_id, ), fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        return {}

async def get_pipeline_simple(pipeline_id : int):
    sql = f"""
        SELECT id, name, description FROM pipeline WHERE id = {pipeline_id}
    """   
    return await select_query(sql, fetch_type=FetchType.ONE)


async def get_pipeline(pipeline_id : int):
    
    sql = """
        SELECT p.id, p.type, p.name, p.access, p.workspace_id, p.dataset_id, p.retraining_count, p.retraining_type, p.retraining_unit, p.retraining_value, 
        p.description, p.graph, p.start_datetime, p.end_datetime, p.start_dataset_size, p.retraining_wait_start_time, p.latest_history_id,
        p.built_in_type, p.built_in_sub_type, p.built_in_specification, p.built_in_data_type, p.built_in_preprocessing_list,
        DATE_FORMAT(p.create_datetime, %s) AS create_datetime, DATE_FORMAT(p.update_datetime, %s) AS update_datetime,
        w.name as workspace_name, u.name as owner_name, cu.name as create_user_name
        FROM pipeline p
        JOIN workspace w ON w.id = p.workspace_id
        LEFT JOIN user u ON u.id = p.owner_id
        LEFT JOIN user cu ON cu.id = p.create_user_id
        WHERE p.id = %s
    """
    res = await select_query(sql, params=( TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL, pipeline_id), fetch_type=FetchType.ONE)
    if res["built_in_preprocessing_list"]:
        res["built_in_preprocessing_list"] = json.loads(res["built_in_preprocessing_list"])
    return res

async def get_pipeline_tasks(pipeline_id : int):
    
    sql = """
        SELECT pt.*, i.name as image_name
        FROM pipeline_task pt
        LEFT JOIN image i ON i.id = pt.image_id
        WHERE pt.pipeline_id = %s
    """
    res = await select_query(sql, params=( pipeline_id, ))
    return res

async def get_pipeline_task(task_id : int):
    sql = """
        SELECT pt.*, i.name as image_name
        FROM pipeline_task pt
        LEFT JOIN image i ON i.id = pt.image_id
        WHERE pt.id = %s
    """
    res = await select_query(sql, params=( task_id, ), fetch_type=FetchType.ONE)
    return res

async def get_pipeline_private_users(pipeline_id : int):
    try:
        sql = """
            SELECT up.user_id, u.name as user_name
            FROM user_pipeline up
            LEFT JOIN user u ON u.id = up.user_id
            WHERE up.pipeline_id = %s
        """
        res = await select_query(sql, params=( pipeline_id, ))
        return res
    except Exception as e:
        traceback.print_exc()
        return []
    
async def get_favorite_pipeline(pipeline_id : int, user_id : int):
    sql = """
        SELECT * FROM pipeline_bookmark
        WHERE pipeline_id = %s AND user_id = %s
    """
    res = await select_query(sql, params=(pipeline_id, user_id), fetch_type=FetchType.ONE)
    
    return res is not None 

#####################
# DELETE
#####################
async def delete_pipeline_task(task_id : int) -> bool:
    try:
        sql="DELETE FROM pipeline_task WHERE id=%s"
        await commit_query(query=sql, params=(task_id,))
        return True
    except Exception as e:
        traceback.print_exc()
        return False

async def delete_pipeline(pipeline_id : int) -> bool:
    try:
        sql="DELETE FROM pipeline WHERE id=%s"
        await commit_query(query=sql, params=(pipeline_id,))
        return True
    except Exception as e:
        traceback.print_exc()
        return False
    
async def delete_pipeline_user_list(pipeline_id : int, user_id : int) -> bool:
    sql="DELETE FROM user_pipeline WHERE pipeline_id=%s AND user_id=%s"
    await commit_query(query=sql, params=(pipeline_id, user_id))
    return True

async def delete_favorite_pipeline(pipeline_id: int, user_id : int) -> bool:
    sql="DELETE FROM pipeline_bookmark WHERE pipeline_id=%s AND user_id=%s"
    await commit_query(query=sql, params=(pipeline_id, user_id))
    return True
#####################
# INSERT
#####################

async def create_favorite_pipeline(**kwargs):
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO pipeline_bookmark ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def insert_pipeline_users(pipeline_id : int, user_ids : List[int]):
    insert_data =[(pipeline_id, user_id)  for user_id in user_ids]
    fields = ['pipeline_id', 'user_id']
    sql = """INSERT INTO {} ({})
        VALUES ({})""".format('user_pipeline', ', '.join(fields), ', '.join(['%s']*len(fields)))
    await commit_query(query=sql, params=insert_data, execute="many")
    return True

async def create_pipeline(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO pipeline ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_pipeline_task(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO pipeline_task ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_pipeline_history(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO pipeline_history ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

#####################
# UPDATE
#####################

async def update_pipeline(pipeline_id : int , access : int, description : str, owner_id : int):
    try:
        sql = "UPDATE pipeline SET access=%s, description=%s, owner_id=%s WHERE id=%s"
        res = await commit_query(query=sql, params=( access, description, owner_id, pipeline_id )) 
        return True
    except Exception as e:
        return False

async def update_pipeline_history_stop(pipeline_history_id : int, end_datetime : str, end_status : str, increase_dataset_size : int, retraining_count : int, tasks : str):
    try:
        sql = "UPDATE pipeline_history SET end_datetime=%s, end_status=%s, increase_dataset_size=%s, retraining_count=%s, pipeline_tasks=%s WHERE id = %s"
        res = await commit_query(query=sql, params=( end_datetime,end_status, increase_dataset_size, retraining_count, tasks, pipeline_history_id )) 
        return True
    except Exception as e:
        return False

async def update_pipeline_dataset(pipeline_id : int, dataset_id : int):
    try:
        sql = "UPDATE pipeline SET dataset_id = %s WHERE id = %s"
        res = await commit_query(query=sql, params=(dataset_id, pipeline_id))
        return True
    except Exception as e:
        return False

async def update_pipeline_graph(pipeline_id : int, graph : str):
    try:
        sql = "UPDATE pipeline SET graph = %s WHERE id = %s"
        res = await commit_query(query=sql, params=(graph, pipeline_id))
        return True
    except Exception as e:
        return False
    
async def update_pipeline_retraining(pipeline_id : int, retraining_type : str, retraining_unit : str, retraining_value : str):
    try:
        sql = "UPDATE pipeline SET retraining_type = %s, retraining_unit=%s, retraining_value=%s  WHERE id = %s"
        res = await commit_query(query=sql, params=(retraining_type, retraining_unit, retraining_value, pipeline_id))
        return True
    except Exception as e:
        return False
  

async def update_pipeline_task_reset(pipeline_id :int):
    try:
        sql = """
                UPDATE pipeline_task set status = 'pending', start_datetime = Null, task_item_job_id=Null, end_datetime = Null WHERE pipeline_id=%s
            """
        res = await commit_query(query=sql, params=(pipeline_id,))
        return True
    except Exception as e:
        return False     
  
async def update_pipeline_reset(pipeline_id: int, start_datetime: str = None, dataset_size : int = 0):
    try:
        # 수정된 SQL 쿼리
        sql = """
        UPDATE pipeline 
        SET start_datetime = %s, 
            end_datetime = NULL, 
            start_dataset_size = %s,
            retraining_wait_start_time = NULL, 
            retraining_count = %s 
        WHERE id = %s
        """
        res = await commit_query(query=sql, params=(start_datetime, dataset_size, 0, pipeline_id))
        return True
    except Exception as e:
        print(f"Error: {e}")  # 오류 발생 시 확인을 위해 에러 메시지를 출력
        return False
 
async def update_pipeline_history_id(pipeline_id : int, history_id : int):
    try:
        sql = "UPDATE pipeline SET latest_history_id = %s WHERE id = %s"
        res = await commit_query(query=sql, params=(history_id, pipeline_id))
        return True
    except Exception as e:
        return False   


def update_pipeline_stop_sync(pipeline_id : int, end_datetime : str):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = "UPDATE pipeline SET end_datetime=%s  WHERE id = %s"
            cur.execute(sql, (end_datetime, pipeline_id))
            conn.commit()
        return True
    except Exception as e:
        return False

async def update_pipeline_stop(pipeline_id : int, end_datetime : str):
    try:
        sql = "UPDATE pipeline SET end_datetime=%s  WHERE id = %s"
        res = await commit_query(query=sql, params=( end_datetime, pipeline_id ))
        return True
    except Exception as e:
        return False
    

async def update_pipeline_task_position(task_id : int, x_position : int, x_index : int, y_index : int):
    try:
        sql = "UPDATE pipeline_task SET x_position = %s, x_index=%s, y_index=%s WHERE id = %s"
        res = await commit_query(query=sql, params=(x_position, x_index, y_index, task_id))
        return True
    except Exception as e:
        return False

async def update_pipeline_task_y_index(pipeline_id : int, task_type : str, y_index_base : int, add : bool = True):
    try:
        sql = "UPDATE pipeline_task "
        if add:
            sql += "SET y_index = y_index + 1"
        else:
            sql += "SET y_index = y_index - 1"
        sql += " WHERE pipeline_id = %s AND task_type = %s AND y_index > %s"

        res = await commit_query(query=sql, params=(pipeline_id, task_type, y_index_base))
        return True
    except Exception as e:
        return False
