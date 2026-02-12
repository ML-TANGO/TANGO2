import pymysql
from contextlib import contextmanager
import traceback
import os
import sys
from utils import settings
sys.path.insert(0, os.path.abspath('..'))
# from utils.exception.exceptions import *
# from utils import settings
# from utils.TYPE import *

try:
    db_host = settings.JF_DB_HOST
except :
    db_host = '192.168.1.20'
try:
    db_port = int(settings.JF_DB_PORT)
except :
    db_port = 30001
try:
    db_unix_socket = settings.JF_DB_UNIX_SOCKET
except :
    db_unix_socket = '/jf-src/master/conf/db/mysqld.sock'
try:
    db_user = settings.JF_DB_USER
except :
    db_user = 'root'
try:
    db_pw = settings.JF_DB_PW
except :
    db_pw = 'tango1234@'
try:
    db_name = "jonathan_llm"
except :
    db_name = 'jonathan_llm'
try:
    db_charset = settings.JF_DB_CHARSET
except :
    db_charset = 'utf8'
try:
    db_dummy_name = "jonathan_llm_dummy"
except :
    db_dummy_name = db_name + "_dummy"

try:
    db_max_connections = 10000
except :
    db_max_connections = 10000


CONN_MODE_SOCKET = "socket"
CONN_MODE_PORT = "port"


def get_conn_socket_db_top():
    conn = pymysql.connect(unix_socket=db_unix_socket, user=db_user, password=db_pw, charset=db_charset,
        cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_port_db_top():    
    conn = pymysql.connect(host=db_host, port=db_port, user=db_user, password=db_pw, charset=db_charset,
        cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_db_top():
    mode = None
    try:
        conn = get_conn_socket_db_top()
        mode = CONN_MODE_SOCKET
    except:
        conn = get_conn_port_db_top()
        mode = CONN_MODE_PORT
    return conn, mode

def get_conn_socket_db():
    conn = pymysql.connect(unix_socket=db_unix_socket, user=db_user, password=db_pw, db=db_name, charset=db_charset,
        cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_port_db():
    conn = pymysql.connect(host=db_host, port=db_port, user=db_user, password=db_pw, db=db_name, charset=db_charset,
        cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_db():
    mode = None
    conn = get_conn_port_db()
    mode = CONN_MODE_PORT
    # try:
    #     conn = get_conn_socket_db()
    #     mode = CONN_MODE_SOCKET
    # except:
    #     conn = get_conn_port_db()
    #     mode = CONN_MODE_PORT
    return conn, mode

def get_conn_socket_dummy_db():
    conn = pymysql.connect(unix_socket=db_unix_socket, user=db_user, password=db_pw, db=db_dummy_name, charset=db_charset,
                cursorclass=pymysql.cursors.DictCursor)
    return conn
    
def get_conn_port_dummy_db():
    conn = pymysql.connect(host=db_host, port=db_port, user=db_user, password=db_pw, db=db_dummy_name, charset=db_charset,
                    cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_dummy_db():
    mode = None
    try:
        conn = get_conn_socket_dummy_db()
        mode = CONN_MODE_SOCKET
    except:
        conn = get_conn_port_dummy_db()
        mode = CONN_MODE_PORT
    return conn, mode

@contextmanager
def get_db_top():
    try:
        conn = None
        conn, *_ = get_conn_db_top()
        yield conn
    finally:
        conn.close()
        pass

@contextmanager
def get_db():
    try:
        conn = None
        conn, *_ = get_conn_db()
        yield conn
    finally:
        conn.close()
        pass

@contextmanager
def get_dummy_db():
    try:
        conn = None
        conn, *_ = get_conn_dummy_db()
        yield conn
    finally:
        conn.close()
        pass

def set_db_max_connections(max_connections):
    """
    Description :
        DB가 허용하는 최대 connections 수. 
        초기 설정 시 db호출이 많은데 max connections 때문에 처리하지 못하는 부분들 발생 가능
        ini - JF_LLM_DB_MAX_CONNECTIONS 로 관리.

    Args :
        max_connections(int) - 0 ~ n.   default는 settings.ini 의 JF_LLM_DB_MAX_CONNECTIONS

    """
    try:
        with get_db_top() as conn:
            cur = conn.cursor()
            sql = """
                set global max_connections={};
            """.format(max_connections)
            cur.execute(sql)
            conn.commit()
        
    except Exception as e:
        traceback.print_exc()

def init_db_setting():
    set_db_max_connections(max_connections=db_max_connections)