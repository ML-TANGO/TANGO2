from utils import TYPE
from utils.llm_db.db_base_async import select_query, commit_query, FetchType
from utils.llm_db.db_base import get_db
from typing import List


import traceback

#==========================================
# select
#==========================================

async def get_model_user_list(model_id : int):
    try:
        sql = """
            SELECT um.user_id, u.name as user_name FROM user_model um 
            LEFT JOIN msa_jfb.user u ON u.id = um.user_id 
            WHERE um.model_id = %s
        """
        res = await select_query(sql, params=(model_id,))
        return res
    except Exception as e:
        traceback.print_exc()
        return []


async def get_workspace_user_name_and_id_list_async(workspace_id: int):
    sql = """
        SELECT u.id, u.name
        from msa_jfb.user_workspace uw
        inner join msa_jfb.user u on uw.user_id = u.id
        where uw.workspace_id = %s
    """
    res = await select_query(sql, params=(workspace_id,))
    return res

async def get_favorite_model(model_id : int, user_id : int):
    sql = """
        SELECT * FROM model_bookmark
        WHERE model_id = %s AND user_id = %s
    """
    res = await select_query(sql, params=(model_id, user_id), fetch_type=FetchType.ONE)
    
    return res is not None 

async def get_favorite_models(user_id : int):
    sql = """
        SELECT * FROM model_bookmark
        WHERE user_id = %s
    """
    res = await select_query(sql, params=(user_id,))
    
    return res

async def get_instance_list(workspace_id : int) -> List[dict]:
    
    sql = """
        SELECT rg.name as resource_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, wi.instance_allocate, i.instance_name, wi.instance_id
        FROM msa_jfb.workspace_instance wi
        JOIN msa_jfb.instance i ON i.id = wi.instance_id
        LEFT JOIN msa_jfb.resource_group rg ON i.gpu_resource_group_id = rg.id
        WHERE wi.workspace_id = %s
    """
    res = await select_query(sql, params=(workspace_id, ))
    return res


def get_model_sync(model_id : int) -> dict:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id, 
                m.gpu_count, m.instance_id, m.huggingface_git,
                m.latest_fine_tuning_config,
                m.latest_fine_tuning_status,
                m.commit_status,
                DATE_FORMAT(m.create_datetime, %s) AS create_datetime,
                DATE_FORMAT(m.update_datetime, %s) AS update_datetime,
                w.name as workspace_name, u.name as create_user_name,
                i.instance_name
                FROM model m
                JOIN msa_jfb.workspace w ON w.id = m.workspace_id
                LEFT JOIN msa_jfb.instance i ON i.id = m.instance_id
                LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
                WHERE m.id = %s
            """
            cur.execute(sql, (TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL, model_id))
            res = cur.fetchone()
    except Exception as e:
        traceback.print_exc()
        return None
    return res

async def get_model_simple(model_id: int) -> dict:
    try:
        sql = """
            SELECT m.id, m.name, m.description, m.huggingface_model_id, m.commit_model_name, m.access, m.create_user_id, u.name as create_user_name
            FROM model m 
            LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
            WHERE m.id = %s
        """
        res = await select_query(sql, params=(model_id, ), fetch_type=FetchType.ONE)
        return res
    except Exception as e:
        traceback.print_exc()
        return None


async def get_model(model_id : int) -> dict:
    sql = """
        SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id, m.steps_per_epoch,
        m.gpu_count, m.instance_id, m.huggingface_git, m.huggingface_model_id, m.commit_model_name, m.commit_type,
        m.latest_fine_tuning_config,
        m.latest_fine_tuning_status,
        m.latest_commit_id,
        m.commit_status, m.pod_count, m.instance_count,
        DATE_FORMAT(m.create_datetime, %s) AS create_datetime,
        DATE_FORMAT(m.update_datetime, %s) AS update_datetime,
        DATE_FORMAT(m.start_datetime, %s) AS start_datetime,
        w.name as workspace_name, u.name as create_user_name,
        i.instance_name
        FROM model m
        JOIN msa_jfb.workspace w ON w.id = m.workspace_id
        LEFT JOIN msa_jfb.instance i ON i.id = m.instance_id
        LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
        WHERE m.id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, TYPE.TIME_DATE_FORMAT_SQL,TYPE.TIME_DATE_FORMAT_SQL, model_id), fetch_type=FetchType.ONE)
    return res


def get_models_sync(workspace_id : int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id,
                m.latest_fine_tuning_status, m.instance_id, m.gpu_count, m.instance_count, m.instance_count as instance_allocate,
                m.commit_status, m.pod_count,
                DATE_FORMAT(m.create_datetime, %s) AS create_datetime, 
                w.name as workspace_name, u.name as create_user_name,
                i.cpu_allocate, i.ram_allocate, i.gpu_allocate
                FROM model m
                JOIN msa_jfb.workspace w ON w.id = m.workspace_id
                LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
                LEFT JOIN msa_jfb.instance i ON i.id = m.instance_id
                WHERE m.workspace_id = %s
            """
            cur.execute(sql, (TYPE.TIME_DATE_FORMAT_SQL, workspace_id))
            res = cur.fetchall()
            return res
    except Exception as e:
        traceback.print_exc()
        return res

def get_all_models_sync() -> List[dict]:
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id,
                m.latest_fine_tuning_status,
                m.commit_status,
                DATE_FORMAT(m.create_datetime, %s) AS create_datetime, 
                w.name as workspace_name, u.name as create_user_name
                FROM model m
                JOIN msa_jfb.workspace w ON w.id = m.workspace_id
                LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
            """
            cur.execute(sql, (TYPE.TIME_DATE_FORMAT_SQL))
            res = cur.fetchall()
            return res
    except Exception as e:
        traceback.print_exc()
        return res


async def get_models(workspace_id : int) -> List[dict]:
    sql = """
        SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id,
        m.latest_fine_tuning_status, m.access,
        m.commit_status,
        DATE_FORMAT(m.create_datetime, %s) AS create_datetime,
        DATE_FORMAT(m.update_datetime, %s) AS update_datetime,
        w.name as workspace_name, u.name as create_user_name
        FROM model m
        JOIN msa_jfb.workspace w ON w.id = m.workspace_id
        LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
        WHERE m.workspace_id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL,TYPE.TIME_DATE_FORMAT_SQL, workspace_id))
    return res

async def get_models_option(workspace_id : int, model_name : str = None, create_user_id : int = None) -> List[dict]:
    sql = """
        SELECT m.id, m.name, u.name as create_user_name
        FROM model m
        LEFT JOIN msa_jfb.user u ON u.id = m.create_user_id
        WHERE m.workspace_id = %s
    """
    values = [workspace_id]
    if model_name:
        sql += " AND m.name LIKE %s"
        values.append(f"%{model_name}%")
    if create_user_id:
        sql += " AND m.create_user_id=%s"
        values.append(create_user_id)
    res = await select_query(sql, params=values)
    return res

async def get_commit_models(model_id : int)-> List[dict]:
    sql = """
        SELECT cm.id, cm.name, cm.model_id, cm.workspace_id, 
        cm.commit_message, DATE_FORMAT(cm.commit_datetime, %s) AS commit_datetime, 
        cm.fine_tuning_config, cm.model_description,
        w.name as workspace_name, u.name as create_user_name, m.name as model_name, m.huggingface_model_id
        FROM commit_model cm
        JOIN model m ON m.id = cm.model_id
        JOIN msa_jfb.workspace w ON w.id = cm.workspace_id
        LEFT JOIN msa_jfb.user u ON u.id = cm.create_user_id
        LEFT JOIN msa_jfb.user mu ON mu.id = m.create_user_id
        WHERE m.id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, model_id))
    return res


async def get_commit_models_option(model_id : int, commit_name : str = None)-> List[dict]:
    sql = """
        SELECT cm.id, cm.name, u.name as create_user_name, m.name as model_name, cm.fine_tuning_config, 
                m.description, m.access, m.create_datetime, m.update_datetime
        FROM commit_model cm
        JOIN model m ON m.id = cm.model_id
        LEFT JOIN msa_jfb.user u ON u.id = cm.create_user_id
        WHERE m.id = %s
    """
    values = [model_id]
    if commit_name:
        sql += " AND cm.name LIKE %s"
        values.append(f"%{commit_name}%")
    res = await select_query(sql, params=values)
    return res

async def get_commit_models_by_workspace(workspace_id : int) -> List[dict]:
    sql = """
        SELECT cm.*, DATE_FORMAT(cm.commit_datetime, %s) AS commit_datetime, 
        w.name as workspace_name, u.name as create_user_name, m.name as model_name
        FROM commit_model cm
        JOIN model m ON m.id = cm.model_id
        JOIN msa_jfb.workspace w ON w.id = cm.workspace_id
        LEFT JOIN msa_jfb.user u ON u.id = cm.create_user_id
        WHERE cm.workspace_id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, workspace_id))
    return res

async def get_commit_model(commit_id : int) -> dict:
    sql = """
        SELECT cm.id, cm.name, cm.commit_message, cm.model_description, DATE_FORMAT(cm.commit_datetime, %s) AS commit_datetime, cm.fine_tuning_config, cm.steps_per_epoch,
        w.name as workspace_name, u.name as create_user_name, m.name as model_name, m.huggingface_git, m.huggingface_model_id, m.id as model_id
        FROM commit_model cm
        JOIN model m ON m.id = cm.model_id
        JOIN msa_jfb.workspace w ON w.id = cm.workspace_id
        LEFT JOIN msa_jfb.user u ON u.id = cm.create_user_id
        WHERE cm.id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, commit_id), fetch_type=FetchType.ONE)
    return res

async def get_workspace_model(workspace_id : int) -> dict:
    sql = """
    SELECT w.*, s.name as main_storage_name, sd.name as data_storage_name
    FROM msa_jfb.workspace w
    LEFT JOIN msa_jfb.storage s ON s.id = w.main_storage_id
    LEFT JOIN msa_jfb.storage sd ON sd.id = w.data_storage_id
    WHERE w.id = %s
    """
    res = await select_query(sql, params=(workspace_id, ), fetch_type=FetchType.ONE)
    return res

async def check_model_by_model_name(model_name: str, workspace_id:int) -> dict:
    sql = """
        SELECT * FROM model WHERE name = %s and workspace_id = %s
    """
    res = await select_query(query=sql, params=(model_name, workspace_id ), fetch_type=FetchType.ONE)
    return res

async def check_commit_model_by_name(commit_name : str , model_id : int):
    sql = """
        SELECT * FROM commit_model WHERE name = %s and model_id = %s
    """
    res = await select_query(query=sql, params=(commit_name, model_id), fetch_type=FetchType.ONE)
    return res

def get_model_dataset_sync(model_dataset_id : int ) -> dict:
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT ftd.id, ftd.training_data_path, d.name as dataset_name, d.access, s.name as data_storage_name, w.name as workspace_name
                FROM fine_tuning_dataset ftd
                JOIN model m ON m.id = ftd.model_id
                JOIN msa_jfb.datasets d ON d.id = ftd.dataset_id
                JOIN msa_jfb.workspace w ON w.id = m.workspace_id
                JOIN msa_jfb.storage s ON s.id = w.data_storage_id
                WHERE ftd.id = %s
            """
            cur.execute(sql, (model_dataset_id, ))
            res = cur.fetchone()
            return res
    except Exception as e:
        traceback.print_exc()
        return res


async def get_model_dataset(model_dataset_id : int) -> dict:
    
    res = await select_query(sql, params=(model_dataset_id, ), fetch_type=FetchType.ONE)
    return res

async def get_model_datasets(model_id : int) -> List[dict]:
    sql = """
        SELECT ftd.id, ftd.training_data_path, d.name as dataset_name, d.access, s.name as data_storage_name, w.name as workspace_name
        FROM fine_tuning_dataset ftd
        JOIN model m ON m.id = ftd.model_id
        JOIN msa_jfb.datasets d ON d.id = ftd.dataset_id
        JOIN msa_jfb.workspace w ON w.id = m.workspace_id
        JOIN msa_jfb.storage s ON s.id = w.data_storage_id
        WHERE ftd.model_id = %s
    """
    res = await select_query(sql, params=(model_id, ))
    return res

async def get_fine_tuning_config_files(model_id : int) -> List[dict]:
    sql = """
        SELECT ftc.id, ftc.file_name, ftc.size
        FROM fine_tuning_config_file ftc
        WHERE ftc.model_id = %s
    """
    res = await select_query(sql, params=(model_id, ))
    return res

async def get_fine_tuning_config_file(model_config_id : int) -> dict:
    sql = """
        SELECT ftc.id, ftc.file_name, ftc.size, ftc.model_id
        FROM fine_tuning_config_file ftc
        WHERE ftc.id = %s
    """
    res = await select_query(sql, params=(model_config_id, ), fetch_type=FetchType.ONE)
    return res

async def get_dataset_model(dataset_id : int) -> dict:
    sql = """
    SELECT d.*
    FROM msa_jfb.datasets d
    JOIN msa_jfb.user u ON u.id = d.create_user_id
    WHERE d.id = %s
    """
    res = await select_query(query=sql, params=(dataset_id, ), fetch_type=FetchType.ONE)
    return res

async def get_datasets(workspace_id : int, create_user_id : int = None, dataset_name : str =None) -> List[dict]:
    sql = """
        SELECT d.id, d.name, d.access, u.name as create_user_name, d.workspace_id
        FROM msa_jfb.datasets d
        JOIN msa_jfb.user u ON u.id = d.create_user_id
        WHERE d.workspace_id = %s
    """
    params = [workspace_id]
    if create_user_id is not None:
        sql += " AND d.create_user_id = %s"
        params.append(create_user_id)
    if dataset_name is not None:
        sql += " AND d.name LIKE %s"
        params.append(f"%{dataset_name}%")
    res = await select_query(sql, params=params)
    return res

# async def get_instance_list(workspace_id : int):
#     sql = """
#         SELECT rg.name as resource_name, i.gpu_allocate, i.cpu_allocate, i.ram_allocate, wi.instance_allocate, i.instance_name, wi.instance_id
#         FROM workspace_instance wi
#         JOIN instance i ON i.id = wi.instance_id
#         LEFT JOIN resource_group rg ON i.gpu_resource_group_id = rg.id
#         WHERE wi.workspace_id = %s
#     """
#     res = await select_query(sql, params=(workspace_id,))
#     return res

#==========================================
# insert 
#==========================================
async def create_model(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO model ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res


async def create_commit_model(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO commit_model ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_fine_tuning_dataset(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO fine_tuning_dataset ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_fine_tuning_config_file(**kwargs) -> int:
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO fine_tuning_config_file ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_favorite_model(**kwargs):
    fields = kwargs.keys()
    values = kwargs.values()
    sql = """
        INSERT INTO model_bookmark ({})
        VALUES({})
    """.format(",".join(list(fields)), ",".join(["%s"]*len(fields)))
    res = await commit_query(query=sql, params=list(values))
    return res

async def create_model_user_list(model_id : int, user_list : List[int]):
    try:
        sql = "INSERT INTO user_model (model_id, user_id) VALUES "
        sql += ",".join([f"({model_id}, {user_id})" for user_id in user_list])
        res = await commit_query(query=sql)
        return res
    except Exception as e:
        traceback.print_exc()
        return False

#==========================================
# delete
#==========================================

async def delete_model(model_id : int) -> bool:
    sql="DELETE FROM model WHERE id=%s"
    await commit_query(query=sql, params=(model_id,))
    return True
async def delete_commit_model(commit_model_id : int) -> bool:
    sql="DELETE FROM commit_model WHERE id=%s"
    await commit_query(query=sql, params=(commit_model_id,))
    return True
async def delete_model_dataset(model_dataset_id : int) -> bool:
    sql="DELETE FROM fine_tuning_dataset WHERE id=%s"
    await commit_query(query=sql, params=(model_dataset_id,))
    return True
async def delete_model_configuration(model_config_id : int) -> bool:
    sql="DELETE FROM fine_tuning_config_file WHERE id=%s"
    await commit_query(query=sql, params=(model_config_id,))
    return True

async def delete_favorite_model(model_id: int, user_id : int) -> bool:
    sql="DELETE FROM model_bookmark WHERE model_id=%s AND user_id=%s"
    await commit_query(query=sql, params=(model_id, user_id))
    return True

async def delete_model_user_list(model_id : int, user_id : int) -> bool:
    sql="DELETE FROM user_model WHERE model_id=%s AND user_id=%s"
    await commit_query(query=sql, params=(model_id, user_id))
    return True

#==========================================
# update
#==========================================

def update_model_commit_status_sync(commit_status : str, model_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            sql = "UPDATE model SET commit_status = %s WHERE id = %s"
            cur.execute(sql, (commit_status, model_id))

            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

async def update_model_commit_status(commit_status : str, model_id : int, latest_commit_id : int, commit_type : str):
    sql = "UPDATE model SET commit_status = %s, latest_commit_id = %s, commit_type = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(commit_status, latest_commit_id, commit_type, model_id))
    return True

async def update_model_commit_id(latest_commit_id : int, model_id : int):
    sql = "UPDATE model SET latest_commit_id = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(latest_commit_id, model_id))
    return True

def update_model_fine_tuning_status_sync(status : str, model_id : int, start_datetime :str = None, end_datetime : str = None, pod_count : int = 0):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = "UPDATE model SET latest_fine_tuning_status = %s "
            data = [status]
            if start_datetime:
                sql += ", start_datetime = %s"
                data.append(start_datetime)
            elif end_datetime:
                sql += ", end_datetime = %s"
                data.append(end_datetime)
            if pod_count:
                sql += ", pod_count = %s"
                data.append(pod_count)
            sql += " WHERE id = %s"
            data.append(model_id)
            cur.execute(sql, data)

            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

async def update_model_fine_tuning_status(status : str, model_id : int, steps_per_epoch : int = None):
    sql = "UPDATE model SET latest_fine_tuning_status = %s "
    paramse = [status]
    if steps_per_epoch:
        sql += ", steps_per_epoch = %s"
        paramse.append(steps_per_epoch)
    sql += " WHERE id = %s"
    paramse.append(model_id)
    res = await commit_query(query=sql, params=paramse)
    return True

async def update_model_fine_tuning_instance(instance_id : int, instance_count : int, gpu_count : int, model_id : int, fine_tuning_config : str):
    sql = "UPDATE model SET instance_id = %s, instance_count= %s, gpu_count = %s, latest_fine_tuning_config = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(instance_id, instance_count, gpu_count, fine_tuning_config, model_id))
    return True

async def update_model_description(model_id : int, description : str):
    sql = "UPDATE model SET description = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(description, model_id))
    return True

async def update_model(model_id : int, description : str, access : str, create_user_id : int):
    sql = "UPDATE model SET description = %s, access = %s, create_user_id = %s WHERE id = %s"
    res = await commit_query(query=sql, params=(description, access, create_user_id, model_id))
    return True