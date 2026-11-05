import pymysql
from datetime import datetime
from contextlib import contextmanager
import os

db_host = os.environ.get("JF_DB_HOST")
db_port = int(os.environ.get("JF_DB_PORT"))
db_user = os.environ.get("JF_DB_USER")
db_pw = os.environ.get("JF_DB_PWD")
db_name = "jonathan_llm"
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
    
    
    
def update_steps_per_epoch(steps_per_epoch : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            model_id = os.environ.get("JF_ITEM_ID")
            sql = f"""
                UPDATE model set steps_per_epoch ={steps_per_epoch} WHERE id={model_id}
            """
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        raise e
    
def update_finetuning_error_status():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            model_id = os.environ.get("JF_ITEM_ID")
            sql = f"""
                UPDATE model set latest_fine_tuning_status = 'error' WHERE id={model_id}
            """
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        raise e
    
def update_finetuning_running_status():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            model_id = os.environ.get("JF_ITEM_ID")
            sql = f"""
                UPDATE model set latest_fine_tuning_status = 'running' WHERE id={model_id}
            """
            cur.execute(sql)
            cur.fetchone()
            conn.commit()
        return True
    except Exception as e:
        raise e