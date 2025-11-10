import pymysql
from contextlib import contextmanager
import traceback
import os

JF_DB_HOST = os.environ['JF_DB_HOST']
JF_DB_PORT = int(os.environ['JF_DB_PORT'])
JF_DB_USER = os.environ['JF_DB_USER']
JF_DB_PW = os.environ['JF_DB_PW']
JF_DB_NAME = "msa_jfb" #os.environ['JF_DB_NAME']
JF_DUMMY_DB_NAME = "msa_jfb_dummy"
JF_LLM_DB_NAME = "jonathan_llm"
JF_DB_CHARSET = os.environ['JF_DB_CHARSET']
JF_DB_DOCKER = os.environ['JF_DB_DOCKER']
JF_DB_ATTEMP_TO_CREATE = os.environ['JF_DB_ATTEMP_TO_CREATE'] == "true" # Attempt to create (DB TABLE and DUMMPY TABE) at every startup. can be slow.
JF_DB_MAX_CONNECTIONS = 10000
JF_DB_UNIX_SOCKET = os.environ['JF_DB_UNIX_SOCKET']
JF_DB_COLLATION = os.environ['JF_DB_COLLATION']

CONN_MODE_SOCKET = "socket"
CONN_MODE_PORT = "port"

def load_sql_file():
    with open('schema.sql', 'r') as file:
        return file.read()
    
def load_sql_file_llm():
    with open('schema_llm.sql', 'r') as file:
        return file.read()
    
schema = load_sql_file()
schema_llm = load_sql_file_llm()

"""
setting
1. set_db_max_connections
2. set_db_database -> 있으면 pass
3. set_db_dummy_database
        
# conn = pymysql.connect(host='jfb-mysql-db.jfb.svc.cluster.local', port=3306, user=db_user, password=db_pw, db='msa_jfb_dummy', charset=db_charset,
#             cursorclass=pymysql.cursors.DictCursor)
conn = pymysql.connect(host='jfb-mysql-db.jfb.svc.cluster.local', port=3306, user=db_user, password=db_pw)
"""

@contextmanager
def get_db(db=None):  
    """
    port 방식 -> host, port
    socket 방식 -> unix_socket
    db : get_db, get_dummy_db 할경우만, get_db_top x
    """
    try:
        try:
            conn = pymysql.connect(user=JF_DB_USER, password=JF_DB_PW, charset=JF_DB_CHARSET,
                                cursorclass=pymysql.cursors.DictCursor,
                                host=JF_DB_HOST, port=JF_DB_PORT,
                                db=db)
        except:
            conn = pymysql.connect(user=JF_DB_USER, password=JF_DB_PW, charset=JF_DB_CHARSET,
                                cursorclass=pymysql.cursors.DictCursor,
                                unix_socket=JF_DB_UNIX_SOCKET,
                                db=db)
        yield conn
    finally:
        conn.close()
        pass
    

def set_db_max_connections(max_connections):
    """
    Description :
        DB가 허용하는 최대 connections 수. 
        초기 설정 시 db호출이 많은데 max connections 때문에 처리하지 못하는 부분들 발생 가능
        settings.ini - JF_DB_MAX_CONNECTIONS 로 관리.

    Args :
        max_connections(int) - 0 ~ n.   default는 settings.ini 의 JF_DB_MAX_CONNECTIONS
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """set global max_connections={};""".format(max_connections)
            cur.execute(sql)
            conn.commit()
    except Exception as e:
        traceback.print_exc()
        pass

def set_db_database():
    try:
        with get_db() as conn:
            cur = conn.cursor()

            # galera는 database helm chart에서 생성
            # sql = """
            #     CREATE DATABASE {} default character set utf8 collate utf8_general_ci
            # """.format(JF_DB_NAME)
            # cur.execute(sql)
            
            
            # create table
            sql_list= schema.split(";")
            with get_db(db=JF_DB_NAME) as conn:
                for sql in sql_list:
                    if sql != '' and sql != '\n':
                        try:
                            conn.cursor().execute(sql)  
                        except:
                            print(sql)
                            traceback.print_exc()
            # conn.commit()
    except Exception as e:
        # traceback.print_exc()
        print("Aleady DATABASE EXIST")


def init_dummy_db():
    try:
        with get_db() as conn:
            # dummy db 삭제
            try:
                cur = conn.cursor()
                sql = "DROP DATABASE {}".format(JF_DUMMY_DB_NAME)
                cur.execute(sql)
                conn.commit()
            except pymysql.err.OperationalError as e:
                if "database doesn't exist" in str(e):
                    pass
                else:
                    raise RuntimeError(e)

            # dummy create database
            try:
                cur = conn.cursor()
                sql = "CREATE DATABASE {} default character set utf8 collate utf8_general_ci".format(JF_DUMMY_DB_NAME)
                cur.execute(sql)
                conn.commit()
            except pymysql.err.ProgrammingError as e:
                if "database exists" in str(e):
                    pass
                else:
                    raise RuntimeError(e)
                
                conn.commit()
            
            # dummy create table
            sql_list= schema.split(";")
            with get_db(db=JF_DUMMY_DB_NAME) as conn:
                for sql in sql_list:
                    if sql != '' and sql != '\n':
                        try:
                            sql = sql.replace(JF_DB_NAME, JF_DUMMY_DB_NAME)
                            conn.cursor().execute(sql)  
                        except:
                            print(sql)
                            traceback.print_exc()
    except:
        traceback.print_exc()


def set_llm_db_database():
    try:
        with get_db() as conn:
            # dummy db 삭제
            try:
                cur = conn.cursor()
                sql = "DROP DATABASE {}".format(JF_LLM_DB_NAME)
                cur.execute(sql)
                conn.commit()
            except pymysql.err.OperationalError as e:
                if "database doesn't exist" in str(e):
                    pass
                else:
                    raise RuntimeError(e)

            # dummy create database
            try:
                cur = conn.cursor()
                sql = "CREATE DATABASE {} default character set utf8 collate utf8_general_ci".format(JF_LLM_DB_NAME)
                cur.execute(sql)
                conn.commit()
            except pymysql.err.ProgrammingError as e:
                if "database exists" in str(e):
                    pass
                else:
                    raise RuntimeError(e)
                
                conn.commit()
            
            # dummy create table
            sql_list= schema_llm.split(";")
            with get_db(db=JF_LLM_DB_NAME) as conn:
                for sql in sql_list:
                    if sql != '' and sql != '\n':
                        try:
                            conn.cursor().execute(sql)  
                        except:
                            print(sql)
                            traceback.print_exc()
    except:
        traceback.print_exc()


set_db_max_connections(max_connections=JF_DB_MAX_CONNECTIONS)
set_db_database()
init_dummy_db()
set_llm_db_database()


# ===========================================================================================
# DB CHECK
# ===========================================================================================


def get_line_print(line_message, prefix="=============="):
    line_start = "{prefix} {message} {prefix}".format(message=line_message, prefix=prefix)
    line_end = "=" * len(line_start)
    return line_start, line_end


def get_add_del_item_list(new, old):
    del_item_list = list(set(old) - set(new))
    add_item_list = list(set(new) - set(old))
    return add_item_list, del_item_list

def get_table_describe_info(conn):
    table_list = []
    table_describe = {}
    """
    table_describe = {
        "TABLE_NAME_a" : [
            {'Field': 'id', 'Type': 'int(11)', 'Null': 'NO', 'Key': 'PRI', 'Default': None, 'Extra': 'auto_increment'}
            {'Field': 'user', 'Type': 'varchar(50)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
            {'Field': 'request', 'Type': 'varchar(50)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
            {'Field': 'method', 'Type': 'varchar(50)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
            {'Field': 'body', 'Type': 'varchar(10000)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
            {'Field': 'success_check', 'Type': 'char(1)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
            {'Field': 'datetime', 'Type': 'varchar(20)', 'Null': 'YES', 'Key': '', 'Default': 'current_timestamp()', 'Extra': ''}
        ],
        "TABLE_NAME_b" : [{..}..]
    }
    """
    
    cur = conn.cursor()
    sql = '''SHOW TABLES'''
    cur.execute(sql)
    res = cur.fetchall()
    
    table_list = [ list(table.values())[0] for table in res ]
    
    for table in table_list:
        sql = '''DESCRIBE {}'''.format(table)
        cur.execute(sql)
        res = cur.fetchall()
        
        table_describe[table] = res
    
    return table_list, table_describe

def get_table_constraint_info(db_name):
    with get_db() as conn:
        cur = conn.cursor()
        sql = """
            SELECT *
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS TC
            WHERE TC.CONSTRAINT_SCHEMA = '{}' 
        """.format(db_name)
        cur = conn.cursor()
        cur.execute(sql)
        res = cur.fetchall()
        
    return res

def get_jfb_DB_table_list_and_describe():
    with get_db(db=JF_DB_NAME) as conn:
        table_list, table_describe = get_table_describe_info(conn)
    return table_list, table_describe


def get_jfb_dummy_DB_table_list_and_describe():
    with get_db(db=JF_DUMMY_DB_NAME) as conn:
        dummy_table_list, dummy_table_describe = get_table_describe_info(conn)
    return dummy_table_list, dummy_table_describe

def db_schema_check():
    try:
        def table_list_compare(new, old, logs):
            add_list, del_list = get_add_del_item_list(new, old)
            # print("Table to add : ", add_list)
            logs.append("Table to add : " + str(add_list))
            # print("Table to del : ", del_list)
            logs.append("Table to del : " + str(del_list))
            return add_list, del_list

        def table_describe_compare(new, old):
            logs = []
            match = True
            def get_table_field_list(cols):
                table_field_list = [ col['Field'] for col in cols ] 
                return table_field_list
            
            def get_field_detail(field_name, cols):
                field_detail = None
                for field in cols:  
                    if field["Field"] == field_name:
                        field_detail = field
                        
                return field_detail
            
            def compare_col_detail(new_field, old_field):
                match = True
                compare_key_list = ["Type", "Null", "Key", "Default", "Extra"]
                for key in compare_key_list:
                    if new_field.get(key) != old_field.get(key):
                        match = False
                        # print("Field [{}]'s detail [{}] that does not match : New [{}] != Old [{}] ".format(new_field.get("Field"), key, new_field.get(key), old_field.get(key)))
                        logs.append("Field [{}]'s detail [{}] that does not match : New [{}] != Old [{}] ".format(new_field.get("Field"), key, new_field.get(key), old_field.get(key)))
                return match
            
            """
            new = [
                {'Field': 'id', 'Type': 'int(11)', 'Null': 'NO', 'Key': 'PRI', 'Default': None, 'Extra': 'auto_increment'}
                {'Field': 'user', 'Type': 'varchar(50)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
                {'Field': 'request', 'Type': 'varchar(50)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
                {'Field': 'method', 'Type': 'varchar(50)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
                {'Field': 'body', 'Type': 'varchar(10000)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
                {'Field': 'success_check', 'Type': 'char(1)', 'Null': 'YES', 'Key': '', 'Default': None, 'Extra': ''}
                {'Field': 'datetime', 'Type': 'varchar(20)', 'Null': 'YES', 'Key': '', 'Default': 'current_timestamp()', 'Extra': ''}
            ]
            """
            # 1. compare field
            # 2. compare type, Null, Key, Default, 'Extra'
            
            new_table_field_list = get_table_field_list(new)
            old_table_field_list = get_table_field_list(old)
            
            add_list, del_list = get_add_del_item_list(new=new_table_field_list, old=old_table_field_list)
            # Field_a -> Field_b 가 된 경우에는 _a 가 _b가 되었다는 것은 알 수 없음
            if len(add_list) > 0:
                # 설치 된 서버에서 추가 해야 할 필드
                # print("Field to add : ", add_list)
                logs.append("Field to add : " + str(add_list))
                match = False
            if len(del_list) > 0:
                # 설치 된 서버에서 삭제 해야 할 필드
                # print("Field to del : ", del_list)
                logs.append("Field to del : " + str(del_list))
                match = False
            
            for field_name in new_table_field_list:
                # 삭제 되거나 추가 된 필드는 비교 할 수 없기에
                if field_name in del_list:
                    # print("Not match Field [{}] : This field removed".format(field_name))
                    logs.append("Not match Field [{}] : This field removed".format(field_name))
                    continue
                if field_name in add_list:
                    # print("Not match Field [{}] : have to add to the installed DB.".format(field_name))
                    logs.append("Not match Field [{}] : have to add to the installed DB.".format(field_name))
                    continue
                    
                new_field = get_field_detail(field_name, new)
                old_field = get_field_detail(field_name, old)
                if not compare_col_detail(new_field=new_field, old_field=old_field):
                    match = False
            
            return match, logs
        
        def constraint_check(old_db_info, new_db_info):
            """
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'PRIMARY', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_training_tool', 'CONSTRAINT_TYPE': 'PRIMARY KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_training_tool_ibfk_1', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_training_tool', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_training_tool_ibfk_2', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_training_tool', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'PRIMARY', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_jupyter', 'CONSTRAINT_TYPE': 'PRIMARY KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_jupyter_ibfk_1', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_jupyter', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_jupyter_ibfk_2', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_jupyter', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'PRIMARY', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_hyperparamsearch', 'CONSTRAINT_TYPE': 'PRIMARY KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_hyperparamsearch_ibfk_1', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_hyperparamsearch', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_hyperparamsearch_ibfk_2', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_hyperparamsearch', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_hyperparamsearch_ibfk_3', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_hyperparamsearch', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'FK_deployment_worker_jfb.deployment', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'deployment_worker', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'PRIMARY', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_job', 'CONSTRAINT_TYPE': 'PRIMARY KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_job_ibfk_1', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_job', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_job_ibfk_2', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_job', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_job_ibfk_3', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_job', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'PRIMARY', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_deployment', 'CONSTRAINT_TYPE': 'PRIMARY KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_deployment_ibfk_1', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_deployment', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_deployment_ibfk_2', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_deployment', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_deployment_ibfk_3', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_deployment', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb', 'CONSTRAINT_NAME': 'record_deployment_ibfk_4', 'TABLE_SCHEMA': 'jfb', 'TABLE_NAME': 'record_deployment', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb_dummy', 'CONSTRAINT_NAME': 'unique_key_2', 'TABLE_SCHEMA': 'jfb_dummy', 'TABLE_NAME': 'training_port', 'CONSTRAINT_TYPE': 'UNIQUE'}
            {'CONSTRAINT_CATALOG': 'def', 'CONSTRAINT_SCHEMA': 'jfb_dummy', 'CONSTRAINT_NAME': 'deployment_worker_ibfk_6', 'TABLE_SCHEMA': 'jfb_dummy', 'TABLE_NAME': 'deployment_worker', 'CONSTRAINT_TYPE': 'FOREIGN KEY'}
            """
            def is_exist(table_name, constraint_name, target):
                for info in target:
                    if info["TABLE_NAME"] == table_name and info["CONSTRAINT_NAME"] == constraint_name:
                        return True
                return False
            
            # 삭제 해야하는 부분 (없어지는 데이터)
            last_table_name = ""
            
            print("----Have To Delete item List----")
            for info in old_db_info:
                if is_exist(table_name=info["TABLE_NAME"], constraint_name=info["CONSTRAINT_NAME"], target=new_db_info) == False:
                    if last_table_name != info["TABLE_NAME"]:
                        print("Table [{}]\n  Name [{}]. Type [{}]".format(info["TABLE_NAME"], info["CONSTRAINT_NAME"], info["CONSTRAINT_TYPE"]))
                    else:
                        print("  Name [{}]. Type [{}]".format(info["CONSTRAINT_NAME"], info["CONSTRAINT_TYPE"]))
                    last_table_name = info["TABLE_NAME"]
            
            print("\n\n\n")
            # 추가 해야하는 부분 
            print("----Have To Add item List----")
            for info in new_db_info:
                if is_exist(table_name=info["TABLE_NAME"], constraint_name=info["CONSTRAINT_NAME"], target=old_db_info) == False:
                    if last_table_name != info["TABLE_NAME"]:
                        print("Table [{}]\n  Name [{}]. Type [{}]".format(info["TABLE_NAME"], info["CONSTRAINT_NAME"], info["CONSTRAINT_TYPE"]))
                    else:
                        print("  Name [{}]. Type [{}]".format(info["CONSTRAINT_NAME"], info["CONSTRAINT_TYPE"]))
                    last_table_name = info["TABLE_NAME"]
        
        print(get_line_print("DB TABLE AND TABLE DETAIL CHECKING SKIP")[0])
        if JF_DB_ATTEMP_TO_CREATE == False:
            print("CHECKING SKIP.  settings - JF_DB_ATTEMP_TO_CREATE = {}".format(JF_DB_ATTEMP_TO_CREATE))
            print(get_line_print("DB TABLE AND TABLE DETAIL CHECKING SKIP")[1],"\n\n\n")
            return 

        jfb_table_list, jfb_table_describe = get_jfb_DB_table_list_and_describe()
        jfb_dummy_table_list, jfb_dummy_table_describe  = get_jfb_dummy_DB_table_list_and_describe()
        logs = []
        add_list, del_list = table_list_compare(new=jfb_dummy_table_list, old=jfb_table_list, logs=logs)
        
        print(get_line_print("DB TABLE CHECKING")[0])
        for log in logs:    
            print(log)
        print(get_line_print("DB TABLE CHECKING")[1],"\n\n\n")


        print(get_line_print("TABLE DETAIL CHECKING")[0])
        logs_match = []
        logs_no_match = []
        for table_name in jfb_dummy_table_list:
            # print("Start table [{}] comparison. ".format(table_name))
            
            if jfb_table_describe.get(table_name) is None:
                print("1. Table to Add: ", table_name)
                print("2. Retry DB Check")
            
            match, logs = table_describe_compare(new=jfb_dummy_table_describe.get(table_name), old=jfb_table_describe.get(table_name))
            if match:
                logs_match.append("Table [{}] comparison. Version match OK.".format(table_name))
                # print("[{}] Version match OK.".format(table_name))
            else :
                logs_no_match.append("Table [{}] comparison.".format(table_name))
                for log in logs:
                    # print("Warining : ", log)
                    logs_no_match.append("Warining : {}".format(log))
                logs_no_match.append("")

        print("----DESCRIBE NO MATCH LIST----")
        for logs in logs_no_match:
            print(logs)
        
        print("----DESCRIBE MATCH LIST----")
        for logs in logs_match:
            print(logs)
        
        print("\n\n\n")
        
        print("----CONSTRAINT CHECK LIST----")
        jfb_dummy_info = get_table_constraint_info(JF_DUMMY_DB_NAME)
        jfb_info = get_table_constraint_info(JF_DB_NAME)

        constraint_check(old_db_info=jfb_info, new_db_info=jfb_dummy_info)

        print(get_line_print("TABLE DETAIL CHECKING")[1])
        #TODO 단순 경고로만 할 것인지, RuntimeError로 할 것 인지?
        #Force Running이 있기에 RuntimeError 로?
        #추가 해야 할 Table이 있거나, 추가 해야할 Field가 있을 경우에는 RuntimeError
        #타입 변경은 경고 ?
        #삭제 해야 할 부분들은 경고 수준에서 가능
        pass

    except:
        traceback.print_exc()
        pass

db_schema_check()
print(get_line_print("END DB CHECKING")[0])
