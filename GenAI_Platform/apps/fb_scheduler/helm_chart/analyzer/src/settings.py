import os
# =================================================================================
# ENV 
# =================================================================================
# env.db
TIME_DATE_FORMAT_SQL = "%Y-%m-%d %H:%i:%S"
JF_DB_HOST = os.environ.get("JF_DB_HOST") if os.environ.get("JF_DB_HOST") else '192.168.1.20'
JF_DB_PORT = int(os.environ.get("JF_DB_PORT")) if os.environ.get("JF_DB_PORT") else 30001
JF_DB_USER = os.environ.get("JF_DB_USER") if os.environ.get("JF_DB_USER") else 'root'
JF_DB_PW = os.environ.get("JF_DB_PW") if os.environ.get("JF_DB_PW") else 'acryl4958@'
JF_DB_NAME = os.environ.get("JF_DB_NAME") if os.environ.get("JF_DB_NAME") else 'msa_jfb'
JF_DB_CHARSET = os.environ.get("JF_DB_CHARSET") if os.environ.get("JF_DB_CHARSET") else 'utf8'

# env.analyzer
JF_DATA_PATH = os.environ.get("JF_DATA_PATH") if os.environ.get("JF_DATA_PATH") else None
if JF_DATA_PATH != None:
    _split_path = JF_DATA_PATH.split("/")[5:]
    if _split_path[0] == '0':
        JF_POD_DATA_PATH = f"/jf-data/datasets_ro/{'/'.join(_split_path[1:])}" 
    else:
        JF_POD_DATA_PATH = f"/jf-data/datasets_rw/{'/'.join(_split_path[1:])}"
else:
    JF_POD_DATA_PATH = None

JF_ANALYZER_ID = os.environ.get("JF_ANALYZER_ID") if os.environ.get("JF_ANALYZER_ID") else None
JF_GRAPH_ID = os.environ.get("JF_GRAPH_ID") if os.environ.get("JF_GRAPH_ID") else None
JF_GRAPH_TYPE = os.environ.get("JF_GRAPH_TYPE") if os.environ.get("JF_GRAPH_TYPE") else None
JF_COLUMN = os.environ.get("JF_COLUMN") if os.environ.get("JF_COLUMN") else None
