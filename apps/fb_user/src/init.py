import os, crypt
from utils.common import run_func_with_print_line
from utils.msa_db.db_base import get_db
from utils import settings

"""
etc_host O db O -> O
etc_host O db X -> X - 같은 sername으로 재가입시 중복에러
etc_host X db O -> X - linux 유저 체크에는 나옴
"""

def init_root():
    JF_INIT_ROOT_PW = os.environ['JF_INIT_ROOT_PW'] # root 초기 비밀번호
    with get_db() as conn:
        sql = 'SELECT count(id) as count FROM user WHERE name="admin"'
        cursor = conn.cursor()
        cursor.execute(sql)
        root_chk = cursor.fetchone()
        if root_chk['count'] == 0:
            # TODO
            # 추후 초기 비밀번호 값 설정 해줘야함
            password = crypt.crypt(JF_INIT_ROOT_PW, settings.PASSWORD_KEY)
            sql = f"INSERT INTO user (name, uid, user_type, password) VALUES ('admin', '0', '0', '{password}')"
            conn.cursor().execute(sql)
            conn.commit()

# def init_users():
#     # pod -> /etc_host, local -> pv (/jfbcore_msa/data/etc_host)
#     # if os.system("ls /etc_host/passwd") == 0: # MSA 수정
#     if os.system(f"ls {JF_ETC_DIR}/shadow") == 0:
#         print('ETC_HOST OK')
#         return
#         # main에서 copy
#         # os.system("cp {etc_host}/group {etc_host}/gshadow {etc_host}/passwd {etc_host}/shadow /etc/".format(etc_host=JF_ETC_DIR)) # BACKUP DATA TO DOCKER
#     else :
#         print('SET ROOT ETC_HOST')
#         os.system('cp /etc/group /etc/gshadow /etc/passwd /etc/shadow {etc_host}/'.format(etc_host=JF_ETC_DIR))

def main():
    # run_func_with_print_line(func=init_root, line_message="CHECK ETC")
    run_func_with_print_line(func=init_root, line_message="INIT ROOT USER")
    # run_func_with_print_line(func=init_users, line_message="INIT USER LIST")

if __name__ == "__main__":
    main()