import pymysql
from contextlib import contextmanager
import traceback
import os
from utils import settings

try:
    DB_HOST = settings.JF_DB_HOST
except AttributeError:
    DB_HOST = '192.168.1.13'
try:
    DB_PORT = int(settings.JF_DB_PORT)
except AttributeError:
    DB_PORT = 3306
try:
    DB_USER = settings.JF_DB_USER
except AttributeError:
    DB_USER = 'root'
try:
    DB_PW = settings.JF_DB_PW
except AttributeError:
    DB_PW = '1234'
try:
    DB_NAME = settings.JF_DB_NAME
except AttributeError:
    DB_NAME = 'msa_jfb'
try:
    DB_CHARSET = settings.JF_DB_CHARSET
except AttributeError:
    DB_CHARSET = 'utf8'
try:
    DB_DUMMY_NAME = settings.JF_DUMMY_DB_NAME
except AttributeError:
    DB_DUMMY_NAME = DB_NAME + "_dummy"
try:
    db_unix_socket = settings.JF_DB_UNIX_SOCKET
except AttributeError:
    db_unix_socket = '/jf-src/master/conf/db/mysqld.sock'

CONN_MODE_SOCKET = "socket"
CONN_MODE_PORT = "port"

# ===================================================================================================================
def get_conn_socket_db():
    conn = pymysql.connect(unix_socket=db_unix_socket, user=DB_USER, password=DB_PW, db=DB_NAME, charset=DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_port_db():
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PW, db=DB_NAME, charset=DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor)
    return conn

# kubernetes dns 통신 하므로 socket 안씀
def get_conn_db():
    mode = None
    try:
        conn = get_conn_port_db()
        mode = CONN_MODE_PORT
    except:
        conn = get_conn_socket_db()
        mode = CONN_MODE_SOCKET

    return conn, mode

@contextmanager
def get_db():
    try:
        conn = None

        conn, *_ = get_conn_db()
        yield conn
    finally:
        conn.close()
        pass

# ===================================================================================================================
# top
def get_conn_socket_db_top():
    conn = pymysql.connect(unix_socket=db_unix_socket, user=DB_USER, password=DB_PW, charset=DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_port_db_top():
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PW, charset=DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_db_top():
    mode = None
    try:
        conn = get_conn_port_db_top()
        mode = CONN_MODE_PORT
    except:
        conn = get_conn_socket_db_top()
        mode = CONN_MODE_SOCKET
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
# ===================================================================================================================
# dummy
def get_conn_socket_dummy_db():
    conn = pymysql.connect(unix_socket=db_unix_socket, user=db_user, password=db_pw, db=DB_DUMMY_NAME, charset=db_charset,
                cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_port_dummy_db():
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PW, db=DB_DUMMY_NAME, charset=DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor)
    return conn

def get_conn_dummy_db():
    mode = None
    try:
        conn = get_conn_port_dummy_db()
        mode = CONN_MODE_PORT
    except:
        conn = get_conn_socket_dummy_db()
        mode = CONN_MODE_SOCKET
    return conn, mode

@contextmanager
def get_dummy_db():
    try:
        conn = None
        conn, *_ = get_conn_dummy_db()
        yield conn
    finally:
        conn.close()
        pass

# ===================================================================================================================
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
        with get_db_top() as conn:
            cur = conn.cursor()

            sql = """
                set global max_connections={};
            """.format(max_connections)
            cur.execute(sql)
            conn.commit()

    except Exception as e:
        traceback.print_exc()

def set_db_database():
    try:
        with get_db_top() as conn:
            cur = conn.cursor()

            sql = """
                CREATE DATABASE {} default character set utf8 collate utf8_general_ci
            """.format(settings.JF_DB_NAME)
            cur.execute(sql)
            # conn.commit()

    except Exception as e:
        # traceback.print_exc()
        print("Aleady DATABASE EXIST")

def init_db_base():
    set_db_max_connections(max_connections=settings.JF_DB_MAX_CONNECTIONS)
    set_db_database()

