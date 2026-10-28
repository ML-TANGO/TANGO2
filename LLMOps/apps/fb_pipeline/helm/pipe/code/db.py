import pymysql
from datetime import datetime
from contextlib import contextmanager
import settings
import traceback

db_host = settings.JF_DB_HOST
db_port = int(settings.JF_DB_PORT)
db_user = settings.JF_DB_USER
db_pw = settings.JF_DB_PW
db_name = settings.JF_DB_NAME
db_charset = 'utf8'


def get_conn_db():
    conn = pymysql.connect(host=db_host, port=db_port, user=db_user, password=db_pw, db=db_name, charset=db_charset,
        cursorclass=pymysql.cursors.DictCursor)
    return conn


@contextmanager
def get_db():
    try:
        conn = None
        conn= get_conn_db()
        yield conn
    finally:
        conn.close()
        pass
    

def get_pipeline(pipeline_id :int):
    res = {}
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT *
                FROM pipeline
                WHERE id = {pipeline_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        raise e
    return res

def update_pipeline_done(pipeline_id :int):
    res = {}
    try:
        with get_db() as conn:
            cur = conn.cursor()
            end_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            sql = f"UPDATE pipeline SET end_datetime='{end_datetime}'  WHERE id = {pipeline_id}"
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
    except Exception as e:
        raise e
    return res

def update_pipeline_history_done(pipeline_history_id :int, retraining_count : int, increase_dataset_size : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            end_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            sql = f"""
                UPDATE pipeline_history set end_datetime='{end_datetime}', end_status='done', retraining_count={retraining_count}, increase_dataset_size={increase_dataset_size}  WHERE id={pipeline_history_id}
            """
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        raise e
    
def update_pipeline_history_error(pipeline_history_id :int, retraining_count : int, increase_dataset_size : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            end_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            sql = f"""
                UPDATE pipeline_history set end_datetime='{end_datetime}', end_status='error', retraining_count={retraining_count}, increase_dataset_size={increase_dataset_size}  WHERE id={pipeline_history_id}
            """
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        raise e

def update_pipeline_retraining(pipeline_id :int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            start_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            sql = """
                UPDATE pipeline set retraining_count = retraining_count + 1, retraining_wait_start_time = %s WHERE id=%s
            """
            cur.execute(sql,(start_datetime, pipeline_id))
            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        raise e
    
def update_pipeline_start(pipeline_id :int, dataset_size : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE pipeline set retraining_wait_start_time = NULL, start_dataset_size={dataset_size} WHERE id={pipeline_id}
            """
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        raise e
    

def update_pipeline_task_reset(pipeline_id :int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE pipeline_task set status = 'pending', start_datetime = Null, task_item_job_id=Null, task_item_job_str_id=Null, end_datetime = Null WHERE pipeline_id={pipeline_id}
            """
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        raise e    


def get_pipeline_task(task_id :int):
    res = {}
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT pt.*, p.dataset_id
                FROM pipeline_task pt
                JOIN pipeline p ON p.id = pt.pipeline_id
                WHERE pt.id = {task_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        raise e
    return res
    
def get_pipeline_task_item(task_item_id :int, task_type : str):
    res = {}
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT t.*, w.name as workspace_name, s.name as main_storage_name
                FROM {task_type} t
                JOIN workspace w ON w.id = t.workspace_id
                LEFT JOIN storage s ON s.id = w.main_storage_id
                WHERE t.id = {task_item_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        raise e
    return res

def update_pipeline_task(task_id : int, task_item_job_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            start_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            sql = f"UPDATE pipeline_task set task_item_job_id = {task_item_job_id}, start_datetime='{start_datetime}', end_datetime=NULL, status='running' WHERE id = {task_id}"
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
            return True
    except Exception as e:
        traceback.print_exc()
        raise e

def update_pipeline_task_str(task_id : int, task_item_job_str_id : str):
    """generation 노드 전용 — external container job id(문자열)는 INT 컬럼
    task_item_job_id 에 못 담으므로 task_item_job_str_id(VARCHAR) 에 저장."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            start_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            sql = "UPDATE pipeline_task set task_item_job_str_id=%s, start_datetime=%s, end_datetime=NULL, status='running' WHERE id=%s"
            cur.execute(sql, (task_item_job_str_id, start_datetime, task_id))
            conn.commit()
            return True
    except Exception as e:
        traceback.print_exc()
        raise e

def update_pipeline_task_end(task_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            end_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            sql = f"UPDATE pipeline_task set end_datetime='{end_datetime}', status='done' WHERE id = {task_id}"
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
            return True
    except Exception as e:
        raise e

def get_training(training_id: int):
    res = {}
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT *
                FROM training
                WHERE id = {training_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        raise e
    return res

def get_preprocessing_job_id(job_id: int):
    res = {}
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT *
                FROM preprocessing_job
                WHERE id = {job_id}
            """
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        raise e
    return res

def get_deployment_workers(deployment_id: int):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT *
                FROM deployment_worker
                WHERE deployment_id = {deployment_id} AND start_datetime IS NOT NULL AND end_datetime IS NULL
            """
            cur.execute(sql)
            res = cur.fetchall()
    except Exception as e:
        raise e
    return res