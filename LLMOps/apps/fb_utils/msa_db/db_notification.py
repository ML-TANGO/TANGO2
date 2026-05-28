import traceback
import json, os, pymysql
from utils.msa_db.db_base import get_db
from utils import TYPE, settings, PATH, common



def get_notifications(limit :int = 10):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT * 
                    FROM notification_history
                    ORDER BY id DESC
                """
            if limit:
                sql += f" LIMIT {limit}"
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def update_notifications_read(user_id : int, notification_id : int):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = f"""
                UPDATE notification_history SET
                read = {1}
                WHERE user_id = {user_id} and id = {notification_id}
            """
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
    return False
    
