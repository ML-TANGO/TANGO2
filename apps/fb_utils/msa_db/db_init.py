
from typing import List
from datetime import datetime

import crypt
import traceback

from utils.msa_db.db_base import get_db
from utils import TYPE, PATH, settings


def init_root():
    with get_db() as conn:
        sql = f'SELECT count(id) as count FROM user WHERE name="{settings.ADMIN_NAME}"'
        cursor = conn.cursor()
        cursor.execute(sql)
        root_chk = cursor.fetchone()
        if root_chk['count'] == 0:
            enc_pw = crypt.crypt(settings.ADMIN_NAME, settings.PASSWORD_KEY)
            sql = f"INSERT INTO user (name, uid, user_type, password) VALUES ('{settings.ADMIN_NAME}', '0', '0', '{enc_pw}')"
            conn.cursor().execute(sql)
            conn.commit()