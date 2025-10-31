import pymysql
from contextlib import contextmanager
import traceback
from base import *
from utils import settings

# ===================================================================================================================
def init_create_db(conn):
    from utils.msa_jfb import schema
    sql_list= schema.schema.split(";")
    # sqls = open(BASE_DIR+'/schema.sql', 'r').read()
    # sql_list = sqls.split(';')
    for sql in sql_list:
        if sql != '' and sql != '\n':
            try:
                conn.cursor().execute(sql)
            except:
                traceback.print_exc()
        #conn.cursor().executescript(f.read())
    # conn.cursor().execute()
    conn.commit()

# def get_delete_db_trigger_sql(db_name):
#     """
#         트리거 삭제 쿼리 리스트
#     """
#     with get_db() as conn:
#         cur = conn.cursor()
#         sql = """
#             SELECT Concat('DROP TRIGGER ', Trigger_Name, ';') as drop_lines
#             FROM  information_schema.TRIGGERS
#             WHERE TRIGGER_SCHEMA = '{}';
#         """.format(db_name)
#         cur = conn.cursor()
#         cur.execute(sql)
#         res = cur.fetchall()
#     return res

# def init_create_db_trigger(conn, db_name):
#     import utils.db_trigger as trigger
#     # 트리거 삭제 쿼리 리스트
#     sql_trigger_delete_info = get_delete_db_trigger_sql(db_name)
#     sql_trigger_delete_list = [info["drop_lines"] for info in sql_trigger_delete_info]
#     # 트리거 생성 쿼리 리스트
#     sql_trigger_list= trigger.trigger.split("//")

#     # 전체 트리거 쿼리 리스트 = 삭제 + 생성
#     sql_list = sql_trigger_delete_list + sql_trigger_list
#     for sql in sql_list:
#         if sql != '' and sql != '\n':
#             try:
#                 conn.cursor().execute(sql)
#             except:
#                 traceback.print_exc()
#         #conn.cursor().executescript(f.read())
#     # conn.cursor().execute()
#     conn.commit()

# def init_dummy_db():
#     with get_db_top() as conn:
#         try:
#             cur = conn.cursor()
#             sql = "DROP DATABASE {}".format(DB_DUMMY_NAME)
#             cur.execute(sql)
#             conn.commit()
#         except pymysql.err.OperationalError as e:
#             if "database doesn't exist" in str(e):
#                 pass
#             else:
#                 raise RuntimeError(e)

#         try:
#             cur = conn.cursor()
#             sql = "CREATE DATABASE {} default character set utf8 collate utf8_general_ci".format(DB_DUMMY_NAME)
#             cur.execute(sql)
#             conn.commit()
#         except pymysql.err.ProgrammingError as e:
#             if "database exists" in str(e):
#                 pass
#             else:
#                 raise RuntimeError(e)

# ===================================================================================================================
def init_db_table():
    print('+++++++++++++++++++++++')
    if settings.JF_DB_ATTEMP_TO_CREATE == False:
        return
    print('-----------------------')
    with get_db() as conn:
        run_func_with_print_line(func=init_create_db, line_message="CREATE msa_jfb TABLE", conn=conn)
        # run_func_with_print_line(func=init_create_db_trigger, line_message="INIT DB TRIGGER", conn=conn, db_name=settings.JF_DB_NAME)

    # run_func_with_print_line(func=init_dummy_db, line_message="INIT DUMMY DB")

def set_mariadb_setting():
    # 기본 b-tree로 되어 있는 index에 hash를 추가함
    res = ""
    with get_db() as conn:
        cur = conn.cursor()
        sql = '''set global innodb_adaptive_hash_index = 1;
        '''
        cur.execute(sql)
        res = cur.fetchall()
    return res

# ===================================================================================================================
def get_line_print(line_message, prefix="=============="):
    line_start = "{prefix} {message} {prefix}".format(message=line_message, prefix=prefix)
    line_end = "=" * len(line_start)
    return line_start, line_end

def run_func_with_print_line(func, line_message, prefix="==============", *args, **kwargs):
    line_start, line_end = get_line_print(line_message=line_message, prefix=prefix)
    print("\n\n NEW METHOD")
    print(line_start)
    func(*args, **kwargs)
    print(line_end)

# ===================================================================================================================

def main():
    import time
    time.sleep(5)

    init_db_base()
    cnt = 0
    while cnt < 3:
        try:
            init_db_table()
            # 다른 앱 보다 먼저 실행되야함 (테이블이 생성되기전에 다른 곳에서 init_db_other가 실행되면 안됨)
            # 한번에 생성이 잘 안됨 ('Can\'t create table `jfb`.`deployment_bookmark` (errno: 150 "Foreign key constraint is incorrectly formed")')
        except:
            pass
        cnt += 1
    set_mariadb_setting()

if __name__ == "__main__":
    main()
