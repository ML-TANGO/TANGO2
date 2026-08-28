from utils import TYPE
from utils.llm_db.db_base_async import select_query, commit_query, FetchType
from utils.llm_db.db_base import get_db
from typing import List


import json
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
        SELECT m.id, m.description, m.name, m.create_user_id, m.workspace_id, m.access, m.steps_per_epoch,
        m.gpu_count, m.instance_id, m.huggingface_git, m.huggingface_model_id, m.commit_model_name, m.commit_type,
        m.latest_fine_tuning_config,
        m.latest_fine_tuning_status,
        m.latest_commit_id,
        m.commit_status, m.pod_count, m.instance_count,
        m.training_type, m.external_manifest_name, m.external_manifest_version, m.external_job_id,
        m.domain, m.load_type,
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
                m.latest_fine_tuning_status, m.instance_id, m.gpu_count, m.instance_count,
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
        m.training_type, m.load_type, m.domain,
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
        SELECT m.id, m.name, u.name as create_user_name,
               m.training_type,
               m.external_manifest_name,
               m.external_manifest_version,
               m.domain
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
        if not user_list:
            return True
        # 파라미터화 — f-string 인터폴레이션(SQLi 패턴) 제거.
        placeholders = ",".join(["(%s, %s)"] * len(user_list))
        sql = "INSERT INTO user_model (model_id, user_id) VALUES " + placeholders
        params = [v for uid in user_list for v in (model_id, uid)]
        res = await commit_query(query=sql, params=params)
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

async def update_model_external_job(model_id : int, external_job_id : str) -> int:
    """Bind a partner-container job_id onto an external training_type model.

    Called from service.bind_external_job right after the BFF returns a
    fresh job_id from POST /api/external/jobs. Idempotent: always overwrites
    the latest job_id (재학습 시 새 job_id 로 교체).
    """
    sql = """
        UPDATE model
        SET external_job_id = %s
        WHERE id = %s AND training_type = 'external'
    """
    res = await commit_query(query=sql, params=(external_job_id, model_id))
    return res


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


# ── SP-4 양자화·포팅 lineage (v0.4 3.9) ──────────────────────────────────────

async def insert_quantize_lineage(source_model_id : int, workspace_id : int,
                                  job_str_id : str, quantization_type : str,
                                  target_device : str = None, prune : bool = False) -> int:
    """양자화 시도 1건 기록(launch 시점). 재양자화 시 새 row(history 보존)."""
    sql = """
        INSERT INTO quantize_lineage
            (source_model_id, workspace_id, job_str_id, quantization_type,
             target_device, prune, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'running')
    """
    return await commit_query(query=sql, params=(
        source_model_id, workspace_id, job_str_id, quantization_type,
        target_device, 1 if prune else 0,
    ))


async def complete_quantize_lineage(job_str_id : str, gguf_path : str,
                                    source_model_id : int = None) -> bool:
    """convert 완료 시 lineage 마감. running 행만 갱신 — 실패/취소 행을 completed 로
    덮어쓰지 않도록 가드(`status='running'`). source_model_id 주면 교차모델 마킹 차단."""
    sql = """
        UPDATE quantize_lineage
        SET status = 'completed', gguf_path = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [gguf_path, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def update_quantize_lineage_status(job_str_id : str, status : str,
                                         source_model_id : int = None) -> bool:
    """convert 실패/취소 시 lineage 상태 갱신(running 일 때만). idempotent.

    완료(completed)는 complete_quantize_lineage 가 담당 — 여기선 failed/cancelled 만.
    이게 없으면 실패한 양자화가 이력에 영원히 'running' 으로 남는다.
    source_model_id 주면 다른 모델/워크스페이스의 job 을 마킹하지 못하게 바인딩.
    """
    sql = """
        UPDATE quantize_lineage
        SET status = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [status, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def list_quantize_lineage(source_model_id : int) -> list:
    """원본 모델의 양자화 이력(최신순) — lineage 조회(원본+양자화 파라미터)."""
    sql = """
        SELECT id, source_model_id, workspace_id, job_str_id, quantization_type,
               target_device, prune, gguf_path, status,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM quantize_lineage
        WHERE source_model_id = %s
        ORDER BY id DESC
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, source_model_id),
                             fetch_type=FetchType.ALL)
    return res or []


# ── SP-5 자동평가 결과 (v0.4 3.8) ────────────────────────────────────────────

async def insert_eval_result(source_model_id : int, workspace_id : int,
                             job_str_id : str, dataset_id : int = None,
                             dataset_name : str = None, metric_set : str = None,
                             eval_project_id : int = None) -> int:
    """평가 시도 1건 기록(launch 시점, status=running). 재평가 시 새 row(이력 보존).
    eval_project_id 주면 평가 프로젝트(불변 model/dataset 묶음)에 링크(1:N) — 미지정 시
    NULL(레거시/프로젝트 밖 런 보존)."""
    sql = """
        INSERT INTO eval_result
            (source_model_id, workspace_id, eval_project_id, job_str_id, dataset_id,
             dataset_name, metric_set, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'running')
    """
    return await commit_query(query=sql, params=(
        source_model_id, workspace_id, eval_project_id, job_str_id, dataset_id,
        dataset_name, metric_set,
    ))


async def complete_eval_result(job_str_id : str, metrics_json : str,
                               source_model_id : int = None) -> bool:
    """평가 완료 시 메트릭 마감. running 행만 갱신 — 실패/취소 행을 completed 로
    덮어쓰지 않도록 가드. source_model_id 주면 교차모델 마킹 차단."""
    sql = """
        UPDATE eval_result
        SET status = 'completed', metrics = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [metrics_json, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def set_eval_result_metrics(job_str_id : str, metrics_json : str,
                                  source_model_id : int = None) -> bool:
    """metrics 만 갱신(상태 불변, running 행 한정). 전문가 평가(A4)가 start 시점에 생성한
    샘플(_samples)을 영속해 재로드 안정성을 확보하기 위함 — 실 모델출력은 비결정적이라
    매 조회마다 재생성하면 사람이 채점한 출력과 표시 출력이 달라진다. complete_eval_result
    (status→completed)와 달리 status 는 running 으로 둔다."""
    sql = """
        UPDATE eval_result
        SET metrics = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [metrics_json, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def update_eval_result_status(job_str_id : str, status : str,
                                    source_model_id : int = None) -> bool:
    """평가 실패/취소 시 상태 갱신(running 일 때만). idempotent.

    완료(completed)는 complete_eval_result 가 담당 — 여기선 failed/cancelled 만.
    source_model_id 주면 다른 모델/워크스페이스의 job 을 마킹하지 못하게 바인딩.
    """
    sql = """
        UPDATE eval_result
        SET status = %s
        WHERE job_str_id = %s AND status = 'running'
    """
    params = [status, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def list_eval_results(source_model_id : int) -> list:
    """모델의 평가 이력(최신순) — 비교표·best 배지 조회용."""
    sql = """
        SELECT id, source_model_id, workspace_id, job_str_id, dataset_id,
               dataset_name, metric_set, metrics, status,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_result
        WHERE source_model_id = %s
        ORDER BY id DESC
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, source_model_id),
                             fetch_type=FetchType.ALL)
    return res or []


async def list_eval_results_by_project(eval_project_id : int) -> list:
    """프로젝트에 속한 평가 런(run) 목록(최신순) — 프로젝트 내 run 비교표용. list_eval_results
    와 동일 shape, 필터만 eval_project_id. job_str_id IN 목록 대신 FK 필터라 IDOR 회피.
    ⚠️ eval_project_id 를 SELECT 에 포함한다 — 필터로 이미 확정된 값이라 중복처럼 보이지만,
    프로젝트 상세가 공용 비교표 빌더(_build_run_comparison → _label_runs)를 재사용하고
    그 빌더가 원본 행에서 이 컬럼을 되읽기 때문이다(빠지면 소속이 null 로 라벨된다)."""
    sql = """
        SELECT id, source_model_id, workspace_id, eval_project_id, job_str_id, dataset_id,
               dataset_name, metric_set, metrics, status,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_result
        WHERE eval_project_id = %s
        ORDER BY id DESC
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, eval_project_id),
                             fetch_type=FetchType.ALL)
    return res or []


async def list_eval_results_by_workspace(workspace_id : int) -> list:
    """워크스페이스의 채점 런 목록(최신순) — 런 단위 비교 피커의 후보 소스. list_eval_results
    와 동일 shape, 필터만 workspace_id. 러너 inference '생성' 런(metric_set='inference')은
    채점이 아니라 비교 대상이 될 수 없으므로 제외한다(count_run_statuses_by_projects 가
    상태 집계에서 빼는 것과 같은 이유·같은 조건).
    ⚠️ eval_project_id 를 SELECT 에 더한 건 list_eval_results 와의 유일한 차이 — 호출부가
    런이 속한 프로젝트명을 목록조회 한 번으로 매핑하려면(행마다 조회 X) 이 컬럼이 필요하다."""
    sql = """
        SELECT id, source_model_id, workspace_id, eval_project_id, job_str_id, dataset_id,
               dataset_name, metric_set, metrics, status,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_result
        WHERE workspace_id = %s
          AND (metric_set IS NULL OR metric_set <> 'inference')
        ORDER BY id DESC
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, workspace_id),
                             fetch_type=FetchType.ALL)
    return res or []


async def list_eval_results_by_ids(result_ids : list, workspace_id : int) -> list:
    """id 목록으로 런을 읽는다(런 단위 비교의 선택 런 조회). list_eval_results_by_workspace
    와 동일 shape, 필터만 id IN (...) AND workspace_id.

    ⚠️ workspace_id 는 편의 인자가 아니라 **필수**다. 호출부가 사용자에게서 런 id 를 그대로
    받는 경로라, 임의 id 를 찍어 남의 평가 결과를 읽는 직접적인 통로가 된다. 서비스 계층의
    사후 필터링은 한 번만 빠뜨려도 뚫리므로 쿼리 자체에 조건을 박는다 — 워크스페이스 밖
    id 는 애초에 행이 돌아오지 않는다(존재/미존재를 구분해 알려주지도 않는 조용한 누락).
    IN 절은 count_run_statuses_by_projects 와 동일하게 %s 자리표시자만 조립하고 값은 전부
    바인딩한다(문자열 보간 X). 빈 목록이면 조회하지 않는다."""
    if not result_ids:
        return []
    placeholders = ",".join(["%s"] * len(result_ids))
    sql = f"""
        SELECT id, source_model_id, workspace_id, eval_project_id, job_str_id, dataset_id,
               dataset_name, metric_set, metrics, status,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_result
        WHERE id IN ({placeholders})
          AND workspace_id = %s
        ORDER BY id DESC
    """
    res = await select_query(sql,
                             params=(TYPE.TIME_DATE_FORMAT_SQL,
                                     *tuple(result_ids), workspace_id),
                             fetch_type=FetchType.ALL)
    return res or []

async def count_run_statuses_by_projects(project_ids : list) -> list:
    """프로젝트별 run 상태 집계(GROUP BY eval_project_id, status). list_projects 가 표시
    상태를 read-time 파생할 때 프로젝트마다 run 을 조회하는 N+1 을 피하려고 한 번에 읽는다.
    반환: [{eval_project_id, status, cnt}, ...] (run 0개 프로젝트는 결과에 없음)."""
    if not project_ids:
        return []
    placeholders = ",".join(["%s"] * len(project_ids))
    # 러너 inference '생성' 런(metric_set='inference')은 채점이 아니므로 프로젝트 상태 파생 집계에서
    #   제외 — 생성만 한 프로젝트가 목록에서 completed 로 오분류되는 것 방지(리뷰 HIGH).
    sql = f"""
        SELECT eval_project_id, status, COUNT(*) AS cnt
        FROM eval_result
        WHERE eval_project_id IN ({placeholders})
          AND (metric_set IS NULL OR metric_set <> 'inference')
        GROUP BY eval_project_id, status
    """
    res = await select_query(sql, params=tuple(project_ids), fetch_type=FetchType.ALL)
    return res or []


async def get_eval_result_by_job(job_str_id : str, source_model_id : int = None):
    """job_str_id 로 eval_result 단건 조회 — 직접호출(judge) 결과 폴링용(컨테이너/NFS 미경유).
    source_model_id 주면 교차모델 조회 차단."""
    sql = """
        SELECT id, source_model_id, workspace_id, job_str_id, dataset_id,
               dataset_name, metric_set, metrics, status,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_result
        WHERE job_str_id = %s
    """
    params = [TYPE.TIME_DATE_FORMAT_SQL, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    sql += " ORDER BY id DESC LIMIT 1"
    res = await select_query(sql, params=tuple(params), fetch_type=FetchType.ALL)
    return (res or [None])[0]


async def delete_eval_result(job_str_id : str, source_model_id : int = None) -> bool:
    """평가 런 1건 삭제(이력 관리). expert 세션이면 (job_str_id) FK ON DELETE CASCADE 로
    eval_expert_rating / eval_expert_rating_history 자식행도 함께 정리된다. source_model_id
    주면 다른 모델의 런을 삭제하지 못하게 바인딩(호출부에서 존재확인 후 호출)."""
    sql = "DELETE FROM eval_result WHERE job_str_id = %s"
    params = [job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    await commit_query(query=sql, params=params)
    return True


async def list_stale_running_eval_results(source_model_id : int, max_age_hours : int) -> list:
    """스윕 후보(방치된 running 벤치마크/judge 런) 의 job_str_id 목록. fail_stale_eval_results
    로 마감하기 *전에* 호출부가 각 후보에 lazy 완료(metrics.json 재확인)를 한 번 시도하기 위한
    것 — 실제로는 성공했으나 폴링 전 창을 닫아 running 에 남은 벤치마크 런을 failed 로 오분류하지
    않게 한다. WHERE 절은 fail_stale_eval_results 와 동일(expert 제외)."""
    sql = """
        SELECT job_str_id
        FROM eval_result
        WHERE source_model_id = %s
          AND status = 'running'
          AND (metric_set IS NULL OR metric_set <> 'expert')
          AND TIMESTAMPDIFF(HOUR, create_datetime, NOW()) >= %s
    """
    res = await select_query(sql, params=(source_model_id, max_age_hours),
                             fetch_type=FetchType.ALL)
    return res or []


async def fail_stale_eval_results(source_model_id : int, max_age_hours : int) -> bool:
    """방치된 running 런을 failed 로 마감(lazy 스윕, list 조회 시 호출). 컨테이너 크래시/폴러
    재시작으로 완료 콜백이 유실돼 running 에 고착된 런을 정리한다. eval_result 엔 updated_at 이
    없어 나이는 create_datetime 기준(TIMESTAMPDIFF). 사람이 시간에 걸쳐 채점하는
    expert(metric_set='expert') 세션은 정당히 오래 running 이므로 제외.

    ⚠️ 벤치마크 완료는 lazy(FE 가 get_eval_result 폴링 시 metrics.json 을 읽어 마감)라 'running'
    이 곧 '고착'을 뜻하지 않는다(성공했으나 폴링 전 창을 닫은 경우도 running). 그래서 호출부는
    이 함수 전에 list_stale_running_eval_results 후보에 lazy 완료를 먼저 시도해야 한다 — 그러면
    metrics.json 이 있는 런은 completed 로 마감되고, 그 뒤에도 running 인(진짜 미완) 런만 여기서
    failed 로 넘어간다. (한 번 failed 되면 complete_eval_result 가 running 가드라 복구 불가.)"""
    sql = """
        UPDATE eval_result
        SET status = 'failed'
        WHERE source_model_id = %s
          AND status = 'running'
          AND (metric_set IS NULL OR metric_set <> 'expert')
          AND TIMESTAMPDIFF(HOUR, create_datetime, NOW()) >= %s
    """
    await commit_query(query=sql, params=(source_model_id, max_age_hours))
    return True


# 메트릭 방향(best 판정). 모르는 키는 max 기본(벤치마크 점수 대부분 higher=better).
# perplexity 만 낮을수록 우수. (llm_model self-metric + llm_evaluation 벤치마크 공용)
_EVAL_METRIC_DIRECTION = {
    "bleu": "max", "rouge1": "max", "rouge2": "max", "rougel": "max", "rouge": "max",
    "perplexity": "min", "auc": "max", "f1": "max", "accuracy": "max", "dice": "max",
}


def _flatten_eval_metrics(metrics) -> dict:
    """비교표용 flat numeric 메트릭 추출.
    벤치마크(nested {scores, averages, ...})는 averages(메트릭→평균)를 사용,
    self-metric(SP-5)은 top-level flat numeric 을 사용 → 혼재 이력을 동일 shape 로(§14.12).
    _ 접두 내부키·비수치·bool 은 제외."""
    if isinstance(metrics, dict) and isinstance(metrics.get("averages"), dict):
        source = metrics["averages"]    # 벤치마크 평탄화
    else:
        source = metrics if isinstance(metrics, dict) else {}
    return {k: v for k, v in source.items()
            if not str(k).startswith("_") and isinstance(v, (int, float))
            and not isinstance(v, bool)}


def _eval_run_source(metrics) -> tuple:
    """런 출처(어느 체크포인트/배포가 이 점수를 냈나)를 metrics 원본에서 판정
    → (checkpoint, mode, frozen_model, frozen_deployment).

    체크포인트 런은 metrics.checkpoint.name, 생성을 배포에 위임한 런은 metrics.generate.mode
    == 'remote'. 둘 다 아니면 전부 None.

    위임 런의 배포 이름·서빙 모델명은 **완료 시점에 굳혀 둔** `_platform_source` 에서 읽는다
    (llm_evaluation `_freeze_run_source` 가 새긴다). 그 값이 있으면 배포 행을 다시 조회할
    필요가 없고, **배포를 지운 뒤에도 라벨이 남는다** — 표시할 때마다 조회하던 옛 방식은
    배포 삭제와 함께 출처가 사라졌다. 없으면(굳히기 이전에 끝난 옛 런) None 을 돌려주고
    서비스 계층이 live 조회로 폴백한다.
    ⚠️ metrics.generate.model 은 'playground-<id>' shim 식별자라 모델명이 아니다 — 쓰지 않는다.
    비정상/누락 metrics 에도 예외를 던지지 않는다(읽기 전용 표 — 한 행이 목록을 죽이면 안 됨)."""
    if not isinstance(metrics, dict):
        return None, None, None, None
    checkpoint = metrics.get("checkpoint")
    if isinstance(checkpoint, dict) and checkpoint.get("name"):
        return str(checkpoint["name"]), "checkpoint", None, None
    generate = metrics.get("generate")
    if isinstance(generate, dict) and generate.get("mode") == "remote":
        frozen = metrics.get("_platform_source")
        frozen = frozen if isinstance(frozen, dict) else {}
        model = frozen.get("model")
        deployment = frozen.get("deployment")
        return (None, "deployment",
                str(model) if model else None,
                str(deployment) if deployment else None)
    return None, None, None, None


def _eval_run_judge(metrics) -> tuple:
    """심사(judge) 런의 심판 출처를 metrics 원본에서 판정 → (judge_model, judge_deployment).

    LogicKor 채점기가 남기는 metrics.judge{mode, model, endpoint} 를 읽는다. `_eval_run_source`
    와 **같은 규약**이다 — 배포 행 조회가 필요한 값은 완료 시점에 굳혀 둔 `_platform_judge`
    에서만 읽고(llm_evaluation `_freeze_run_source` 가 새긴다) 여기서 배포를 다시 조회하지
    않는다. 그래서 심판 배포를 내린 뒤에도 라벨이 남는다.

    mode 에 따라 이름의 출처가 다르다:
      vllm   — 컨테이너가 심판 가중치를 직접 로드. metrics.judge.model 이 우리가 넘긴 HF
               repo id('google/gemma-4-E4B-it') 라 사람이 읽는 이름 그대로 쓴다.
      remote — 이미 떠 있는 배포에 위임. 이때 metrics.judge.model 은 배포가 자기 이름으로
               보고한 shim 식별자('playground-<id>')라 **모델명이 아니다**(generate.model 과
               같은 함정) → 굳혀 둔 값만 쓰고, 없으면 None 이 맞다(화면은 '-' 를 그린다).
    심판이 없는 런(정답 대조·self-metric)은 judge 섹션 자체가 없어 (None, None).
    비정상/누락 metrics 에도 예외를 던지지 않는다(읽기 전용 표 — 한 행이 목록을 죽이면 안 됨)."""
    if not isinstance(metrics, dict):
        return None, None
    judge = metrics.get("judge")
    if not isinstance(judge, dict):
        return None, None
    if judge.get("mode") == "remote":
        frozen = metrics.get("_platform_judge")
        frozen = frozen if isinstance(frozen, dict) else {}
        model, deployment = frozen.get("model"), frozen.get("deployment")
        return (str(model) if model else None,
                str(deployment) if deployment else None)
    model = judge.get("model")
    return (str(model) if model else None), None


def build_eval_comparison(rows: list) -> dict:
    """eval_result rows → 비교표 shape ``{metric_keys, best, runs}`` (§14.12).

    self-metric(SP-5)·벤치마크·judge(후속) 런을 한 비교표에 누적. 벤치마크의 nested
    metrics 는 averages 로 평탄화. best 는 completed 런 중 메트릭별 방향(min/max) 최적값.
    llm_model / llm_evaluation 두 서비스가 동일 로직을 쓰도록 공용화(분기 drift 방지).
    """
    runs = []
    metric_keys = set()
    for r in rows:
        metrics = r.get("metrics")
        if isinstance(metrics, str):
            try:
                metrics = json.loads(metrics)
            except (TypeError, json.JSONDecodeError):
                metrics = None
        clean = _flatten_eval_metrics(metrics)
        checkpoint, source_mode, frozen_model, frozen_deployment = _eval_run_source(metrics)
        judge_model, judge_deployment = _eval_run_judge(metrics)
        metric_keys.update(clean.keys())
        runs.append({
            "id": r["id"], "job_id": r.get("job_str_id"), "dataset_id": r.get("dataset_id"),
            "dataset_name": r.get("dataset_name"), "metric_set": r.get("metric_set"),
            "status": r.get("status"), "create_datetime": r.get("create_datetime"),
            # 교차모델 비교(④)용 라벨. 단일모델 호출은 한 모델이라 무시되는 잉여 필드.
            # model_name 은 eval_result 에 없어 호출자가 row 에 주입할 때만 채워진다.
            "model_id": r.get("source_model_id"), "model_name": r.get("model_name"),
            # 런 출처 — 점수만으로는 목록에서 런을 구분할 수 없어 "무엇이 이 점수를 냈나"를 함께
            # 싣는다. source_deployment 는 배포 행 조회가 필요해 여기선 항상 None(원본 metrics
            # 만 보는 순수 빌더) — 서비스 계층이 endpoint 의 배포 id 로 채운다.
            "checkpoint": checkpoint, "source_mode": source_mode,
            # 위임 런은 **여기서 모델명을 추측하지 않는다**. 이 컬럼의 존재 이유가
            # "프로젝트 모델과 실제 생성 모델이 다를 수 있다"를 드러내는 것인데,
            # 배포 조회가 실패했을 때 프로젝트 모델명을 남기면 Qwen 이 만든 답에
            # 'src' 라고 적히는, 정확히 반대되는 라벨이 된다. 모르면 None 이 맞다
            # (화면은 '-' 를 그린다). 완료 시점에 굳혀 둔 값이 있으면 그것을 쓰고,
            # 없는 옛 런만 서비스 계층이 배포 행을 읽어 채운다.
            "source_model": (frozen_model if source_mode == "deployment"
                             else r.get("model_name")),
            "source_deployment": frozen_deployment,
            # 심판 출처 — source_deployment 와 대칭인 additive 필드(2026-08-27). LLM 심사
            # 런은 "누가 채점했나"가 점수의 일부라 목록에서 보여야 하는데, metrics.judge 는
            # nested JSON 이라 평탄화된 표에서 쓸 수 없었다. 화면은
            # `judge_deployment ?? judge_model` 로 '심판' 컬럼을 그린다 — 원격 위임이면
            # 배포 이름, 컨테이너 안 vLLM 이면 심판 가중치 이름. 심판이 없는 런(정답 대조·
            # self-metric)은 둘 다 None 이고 '-' 가 정상이다.
            "judge_model": judge_model,
            "judge_deployment": judge_deployment,
            "metrics": clean,
        })
    best = {}
    for key in metric_keys:
        direction = _EVAL_METRIC_DIRECTION.get(str(key).lower(), "max")
        candidates = [(run["id"], run["metrics"][key]) for run in runs
                      if run["status"] == "completed" and key in run["metrics"]]
        if not candidates:
            continue
        best[key] = (min if direction == "min" else max)(candidates, key=lambda x: x[1])[0]
    return {"metric_keys": sorted(metric_keys), "best": best, "runs": runs}


# ── 평가 프로젝트 관리 (2026-07-07) ──────────────────────────────────────────
# 관리 단위 = 프로젝트(모델·데이터셋·유형·이름 잠금). 1:N 으로 eval_result(run)를 묶는다
# (eval_result.eval_project_id FK). 삭제 시 FK ON DELETE CASCADE 로 자식 run
# (+expert rating/history) 전 체인이 함께 정리된다.

async def create_eval_project(workspace_id : int, name : str, eval_type : str,
                              model_id : int = None,
                              dataset_ids_json : str = None,
                              creator : str = None,
                              description : str = None) -> int:
    """평가 프로젝트 생성(status='created', run 0개). 생성된 project id 반환.

    2026-08-24: model_id/dataset_ids 는 선택이다 — 프로젝트가 모델·데이터셋을 잠그던
    계약이 끝나고 무엇을 평가하는지는 run(eval_result.source_model_id/dataset_id)이
    정한다. 두 컬럼은 잠금 시절 프로젝트의 값을 보존하려고 남아 있고 신규 생성은 NULL.

    2026-08-27: description 은 선택 입력(미지정 시 NULL) — 목록 카드 본문에 실린다."""
    # 'created' 리터럴 유지 — 대응 상수 PROJECT_STATUS_CREATED 는 앱 레이어
    # (llm_evaluation.evaluation.constants)에 있어, 공유 lib 인 fb_utils 가 특정 앱을
    # import 하면 레이어 역의존이 된다. 리터럴로 두는 게 계층 규율상 옳다.
    sql = """
        INSERT INTO eval_project
            (workspace_id, name, description, model_id, dataset_ids, eval_type, status, creator)
        VALUES (%s, %s, %s, %s, %s, %s, 'created', %s)
    """
    return await commit_query(query=sql, params=(
        workspace_id, name, description, model_id, dataset_ids_json, eval_type, creator,
    ))


async def list_eval_projects(workspace_id : int) -> list:
    """워크스페이스의 평가 프로젝트 목록(최신순). dataset_ids 는 JSON 컬럼(문자열 반환) —
    호출부(서비스)가 파싱. update_datetime 은 별도 컬럼이 아니라 최근 run 생성 시각
    (없으면 프로젝트 생성 시각)으로 파생한다 — 이 목록이 말하는 '갱신'은 평가 활동이지
    설명 문구 수정이 아니므로, description 이 편집 가능해진 뒤(2026-08-27)에도 파생
    규칙은 그대로 둔다."""
    sql = """
        SELECT p.id, p.workspace_id, p.name, p.description, p.model_id, p.dataset_ids,
               p.eval_type, p.status, p.creator,
               DATE_FORMAT(p.create_datetime, %s) AS create_datetime,
               DATE_FORMAT(
                   COALESCE(
                       (SELECT MAX(r.create_datetime)
                        FROM eval_result AS r
                        WHERE r.eval_project_id = p.id),
                       p.create_datetime
                   ),
                   %s
               ) AS update_datetime
        FROM eval_project AS p
        WHERE p.workspace_id = %s
        ORDER BY p.id DESC
    """
    res = await select_query(sql, params=(
                                 TYPE.TIME_DATE_FORMAT_SQL,
                                 TYPE.TIME_DATE_FORMAT_SQL,
                                 workspace_id,
                             ),
                             fetch_type=FetchType.ALL)
    return res or []


async def get_eval_project(project_id : int) -> dict:
    """평가 프로젝트 단건 조회(불변 model/dataset/type — run-start 시 주입원)."""
    sql = """
        SELECT id, workspace_id, name, description, model_id, dataset_ids, eval_type,
               status, creator,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_project
        WHERE id = %s
    """
    res = await select_query(sql, params=(TYPE.TIME_DATE_FORMAT_SQL, project_id),
                             fetch_type=FetchType.ONE)
    return res


async def update_eval_project_status(project_id : int, status : str) -> bool:
    """프로젝트 상태 갱신(created→running→completed). run 생성/집계 마감 시 호출."""
    sql = "UPDATE eval_project SET status = %s WHERE id = %s"
    await commit_query(query=sql, params=(status, project_id))
    return True


async def update_eval_project_description(project_id : int, description : str) -> bool:
    """프로젝트 설명 갱신. description=None 이면 설명을 지운다(NULL — 화면은 플레이스홀더).

    설명만 따로 두는 이유: 이름·유형·워크스페이스는 프로젝트의 정체성이라 생성 후 고정이고
    (런들이 그 경계 위에 쌓인다), 설명은 그 정체성을 바꾸지 않는 자유 문구다. 형제
    update_eval_project_status 와 같은 규약 — 존재확인은 호출부, 반환은 True 고정."""
    sql = "UPDATE eval_project SET description = %s WHERE id = %s"
    await commit_query(query=sql, params=(description, project_id))
    return True


async def delete_eval_project(project_id : int) -> bool:
    """프로젝트 삭제. FK ON DELETE CASCADE 로 자식 eval_result(run) + expert rating/history
    전 체인이 함께 정리된다(존재확인은 호출부)."""
    sql = "DELETE FROM eval_project WHERE id = %s"
    await commit_query(query=sql, params=(project_id,))
    return True


# ── P3 전문가 평가 (sample-level 인간 채점) ──────────────────────────────────

async def insert_expert_rating(source_model_id : int, job_str_id : str, sample_idx : int,
                               verdict : str, score : int = None, score_json : str = None,
                               input : str = None, output : str = None,
                               reference : str = None, rater_user : str = None,
                               comment : str = None) -> int:
    """전문가 채점 1건 upsert — (job_str_id, sample_idx) 유니크라 재채점 시 갱신.
    score(1~5, D2)가 신규 기본이고 verdict 는 score 에서 파생돼 함께 기록(NOT NULL 보존)."""
    sql = """
        INSERT INTO eval_expert_rating
            (source_model_id, job_str_id, sample_idx, input, output, reference,
             rater_user, verdict, score, score_json, comment)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            verdict = VALUES(verdict), score = VALUES(score),
            score_json = VALUES(score_json), comment = VALUES(comment),
            rater_user = VALUES(rater_user), create_datetime = CURRENT_TIMESTAMP
    """
    return await commit_query(query=sql, params=(
        source_model_id, job_str_id, sample_idx, input, output, reference,
        rater_user, verdict, score, score_json, comment))


async def list_expert_ratings(job_str_id : str, source_model_id : int = None) -> list:
    """세션(job_str_id)의 전문가 채점 목록(sample_idx 순). source_model_id 주면 교차모델 차단."""
    sql = """
        SELECT id, source_model_id, job_str_id, sample_idx, input, output, reference,
               rater_user, verdict, score, score_json, comment,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_expert_rating
        WHERE job_str_id = %s
    """
    params = [TYPE.TIME_DATE_FORMAT_SQL, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    sql += " ORDER BY sample_idx ASC"
    res = await select_query(sql, params=tuple(params), fetch_type=FetchType.ALL)
    return res or []


async def insert_expert_rating_history(source_model_id : int, job_str_id : str,
                                       sample_idx : int, verdict : str,
                                       score : int = None, score_json : str = None,
                                       comment : str = None, rater_user : str = None) -> int:
    """전문가 채점 이력 1건(append-only, 감사추적). 메인 eval_expert_rating 은
    (job_str_id, sample_idx) upsert 라 '현재' verdict 만 남지만, 누가 언제 어떻게 채점/재채점
    했는지는 이 테이블에 채점 이벤트마다 누적해 불변 보존한다. score/score_json 도 이벤트마다 동결."""
    sql = """
        INSERT INTO eval_expert_rating_history
            (source_model_id, job_str_id, sample_idx, rater_user, verdict, score, score_json, comment)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    return await commit_query(query=sql, params=(
        source_model_id, job_str_id, sample_idx, rater_user, verdict, score, score_json, comment))


async def list_expert_rating_history(job_str_id : str, source_model_id : int = None) -> list:
    """세션(job_str_id)의 전문가 채점 이력(시간순). source_model_id 주면 교차모델 차단."""
    sql = """
        SELECT id, source_model_id, job_str_id, sample_idx, rater_user, verdict,
               score, score_json, comment,
               DATE_FORMAT(create_datetime, %s) AS create_datetime
        FROM eval_expert_rating_history
        WHERE job_str_id = %s
    """
    params = [TYPE.TIME_DATE_FORMAT_SQL, job_str_id]
    if source_model_id is not None:
        sql += " AND source_model_id = %s"
        params.append(source_model_id)
    sql += " ORDER BY id ASC"
    res = await select_query(sql, params=tuple(params), fetch_type=FetchType.ALL)
    return res or []
