import traceback
import json, os, pymysql
from utils.msa_db.db_base import get_db
from utils import TYPE, settings, PATH, common


def get_built_in_model_list(model_ids=None, model_name=None, created_by=None):
    """get built in model list from id list string

    Args:
        model_ids (str, optional): model id string joined by ",". ex) 2013, 2094. Defaults to None.
        model_name (str, optional): built in model name. Defaults to None.
        created_by (str, optional): created by. Defaults to None.

    Returns:
        list: built in model info dic list.
    """
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT bm.*, image.id as docker_image_id
                    FROM built_in_model bm
                    LEFT JOIN image ON image.name = bm.run_docker_name
                """

            if model_ids is not None:
                # sql+= " WHERE bm.id = {}".format(model_id)
                # sql+= ' WHERE bm.id in ({})'.format(','.join(str(e) for e in model_ids))
                sql+= ' WHERE bm.id in ({})'.format(model_ids)
            elif model_name is not None:
                sql+= " WHERE bm.name = '{}'".format(model_name)

            if created_by is not None:
                sql+= " AND bm.created_by = '{}' ".format(created_by) if "WHERE" in sql else " WHERE bm.created_by = '{}' ".format(created_by)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_built_in_model_kind_and_created_by():
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT DISTINCT bm.kind, bm.created_by
                    FROM built_in_model bm
                """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_built_in_model_data_training_form(model_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT *
                    FROM built_in_model_data_training_form bmtf
                """

            if model_id is not None:
                sql+= " WHERE bmtf.built_in_model_id = {}".format(model_id)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_built_in_model(model_id=None, model_name=None, created_by=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT bm.*, image.id as docker_image_id
                    FROM built_in_model bm
                    LEFT JOIN image ON image.name = bm.run_docker_name
                """

            if model_id is not None:
                sql+= " WHERE bm.id = {}".format(model_id)
            elif model_name is not None:
                sql+= " WHERE bm.name = '{}'".format(model_name)
            else:
                return res

            if created_by is not None:
                sql+= " AND bm.created_by = '{}' ".format(created_by) if "WHERE" in sql else " WHERE bm.created_by = '{}' ".format(created_by)

            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def get_built_in_model_parameter(model_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT DISTINCT bmp.parameter, bmp.parameter_description, bmp.default_value
                    FROM built_in_model_parameter bmp
                    WHERE bmp.built_in_model_id = {}
                """.format(model_id)
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_built_in_model_data_deployment_form(model_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT *
                    FROM built_in_model_data_deployment_form bmdf
                """

            if model_id is not None:
                sql+= " WHERE bmdf.built_in_model_id = {}".format(model_id)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_built_in_model_name_and_id_list(created_by=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            #TODO model => name으로 바꿔야함
            sql = """
                SELECT bm.id, bm.name as model, bm.run_docker_name
                FROM built_in_model bm
            """
            if created_by is not None:
                sql += " WHERE bm.created_by = '{}'".format(created_by)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

# def insert_built_in_model():
#     with get_db() as conn:
#         init_built_in_model(conn)

def delete_built_in_model(built_in_model_ids):
    """built_in_model 삭제 함수

    Args:
        built_in_model_ids (str): built in model id list str. ex) "2021, 2015"

    Returns:
        status (bool): success-True / fail-False
    """
    # if len(built_in_model_ids) == 0:
    #     return True
    try:
        with get_db() as conn:
            cur = conn.cursor()

            # sql = "delete from built_in_model where id in ({})".format(','.join(str(e) for e in built_in_model_ids))
            sql = "delete from built_in_model where id in ({})".format(built_in_model_ids)
            cur.execute(sql)
            conn.commit()

        return True
    except:
        traceback.print_exc()
        return False

def update_built_in_model_status(built_in_model_id, status_type, status, update_datetime):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE built_in_model
                SET {status_type}_status = {status}, update_datetime = "{update_datetime}"
                WHERE id = {built_in_model_id}
            """.format(status_type=status_type, status=status, update_datetime=update_datetime, built_in_model_id=built_in_model_id)
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def update_built_in_model_update_time(built_in_model_id, update_datetime):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = """
                UPDATE built_in_model
                SET update_datetime = "{update_datetime}"
                WHERE id = {built_in_model_id}
            """.format(built_in_model_id=built_in_model_id, update_datetime=update_datetime)
            cur.execute(sql)
            conn.commit()

        return True
    except:
        traceback.print_exc()
        return False

def update_built_in_model_create_time(built_in_model_id, create_datetime):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = """
                UPDATE built_in_model
                SET create_datetime = "{create_datetime}"
                WHERE id = {built_in_model_id}
            """.format(built_in_model_id=built_in_model_id, create_datetime=create_datetime)
            cur.execute(sql)
            conn.commit()

        return True
    except:
        traceback.print_exc()
        return False

def update_built_in_model_docker_image_id(built_in_model_id, docker_image_id):
    """
        Description : Built in model의 Docker image 변경 시 관련 아이템들의 도커 이미지도 같이 교체

        Args :
            built_in_model_id (int) : 변경 된 built_in_model_id
            docker_image_id (int) : 변경 후 docker image id

        Returns :
            (bool) : True | False (성공 | 실패)
            (str) : 실패 시 에러 메세지. 성공 시 ('')
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()

            # Training Item Update
            sql = """
                UPDATE training t
                SET t.docker_image_id = {}
                WHERE t.built_in_model_id = {}
            """.format(docker_image_id, built_in_model_id)
            cur.execute(sql)

            # Training Tool Item Update
            sql = """
                UPDATE training_tool tt
                LEFT JOIN training t ON tt.training_id = t.id
                SET tt.docker_image_id = {}
                WHERE t.built_in_model_id = {}
            """.format(docker_image_id, built_in_model_id)
            cur.execute(sql)

            # Deployment Item Update
            sql = """
                UPDATE deployment d
                SET d.docker_image_id = {}
                WHERE d.built_in_model_id = {}
            """.format(docker_image_id, built_in_model_id)

            #TODO Queue Item Update

            cur.execute(sql)
            conn.commit()

    except Exception as e:
        traceback.print_exc()
        return False, e
    return True, ""


def init_built_in_model():
    def find_infojson(file_name_list):
        result=[]
        for s in file_name_list:
            s_list=s.split('.')
            try:
                if s_list[-1]==TYPE.INFO_JSON_EXTENSION:
                    result.append(s)
                elif s=='info.json':
                    result.append(s)
            except:
                pass
        return result

    with get_db() as conn:
        def get_column_keys(sql):
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = cursor.fetchall()
            return columns

        try:
            built_in_model_columns_key = get_column_keys(sql='SHOW COLUMNS FROM jfb.built_in_model')
            columns_key = {
                "training_input_data_form_list":[],
                "deployment_input_data_form_list":[],
                "parameters": {}, # paramter, default_value
                "parameters_description": None
            }
            for key in built_in_model_columns_key:
                columns_key[key["Field"]] = None

            training_form_columns_key = get_column_keys(sql='SHOW COLUMNS FROM jfb.built_in_model_data_training_form')
            training_columns_key = {}
            for key in training_form_columns_key:
                training_columns_key[key["Field"]] = None

            deployment_form_columns_key = get_column_keys(sql='SHOW COLUMNS FROM jfb.built_in_model_data_deployment_form')
            deployment_columns_key = {}
            for key in deployment_form_columns_key:
                deployment_columns_key[key["Field"]] = None

            built_in_parameter_columes_key = get_column_keys(sql='SHOW COLUMNS FROM jfb.built_in_model_parameter')
            parameter_columns_key = {}
            for key in built_in_parameter_columes_key:
                parameter_columns_key[key["Field"]] = None

            models_path = settings.JF_BUILT_IN_MODELS_PATH
            models = os.listdir(models_path)
            model_info_list = []
            info_model_dic={}
            for model in models:
                try:
                    model_file_list=os.listdir("{}/{}".format(models_path, model))
                    file_name_list=find_infojson(model_file_list)
                    for file in file_name_list:
                        # info_model_dic[file]=model
                        if os.path.isfile("{}/{}/{}".format(models_path, model, file)):
                            info_model_dic["{}/{}/{}".format(models_path, model, file)]={"path":model,"infojson_path":file}
                except:
                    pass
            # print("info_model_dic:",info_model_dic)
            # for model in models:
            for info_file in list(info_model_dic.keys()):
                try:
                    # model=info_model_dic[info_file]["model"]
                    # info_file = "{}/{}/{}".format(models_path, model, info_file)
                    json_data = common.load_json_file(info_file)
                    # with open(info_file, encoding="utf-8") as json_file:
                    #     json_data = json.load(json_file)
                    # model_info = {"path": model}
                    model_info = dict(columns_key)
                    model_info["path"] = info_model_dic[info_file]["path"]
                    model_info["infojson_path"] = info_model_dic[info_file]["infojson_path"]
                    for k, v in json_data.items():
                        if k in columns_key:
                            # if k == "parameters" and type(v) == type({}):
                            #     parameters = ""
                            #     for item in v.items():
                            #         parameters += "--{} {} ".format(item[0], item[1])
                            #     v = parameters
                            if (k == "parameters" or k == "parameters_description") and type(v) == type({}):
                                m_v = dict(model_info["parameters"])
                                if k == "parameters":
                                    for p_k, p_v in v.items():
                                        if m_v.get(p_k) is None:
                                            m_v[p_k] = { "parameter" : p_k, "default_value" : p_v }
                                        else :
                                            m_v[p_k]["parameter"] = p_k
                                            m_v[p_k]["default_value"] = p_v

                                elif k == "parameters_description":
                                    for p_k, p_v in v.items():
                                        if m_v.get(p_k) is None:
                                            m_v[p_k] = { "parameter" : p_k, "parameter_description" : p_v }
                                        else :
                                            m_v[p_k]["parameter"] = p_k
                                            m_v[p_k]["parameter_description"] = p_v
                                k = "parameters"
                                v = m_v
                                # print(k, v)

                            elif k == "training_input_data_form_list" and type(v) == type([]):
                                for i, training_input_data_form in enumerate(v):
                                    t_info = dict(training_columns_key)
                                    for t_k, t_v in training_input_data_form.items():
                                        if t_k in training_columns_key:
                                            t_info[t_k] = t_v
                                    for t_k in list(training_columns_key.keys()):
                                        if t_info[t_k] is None:
                                            del t_info[t_k]
                                    v[i] = t_info
                                for i, training_input_data_form in reversed(list(enumerate(v))):
                                    if len(set(["type", "name", "category"])-(set(training_columns_key)-set(training_input_data_form)))< 3:
                                    # if training_input_data_form["type"]==None or training_input_data_form["name"]==None or training_input_data_form["category"]==None:
                                        # print("====training_input_data_form{}".format(training_input_data_form))
                                        del v[i]

                            elif k == "deployment_input_data_form_list" and type(v) == type([]):
                                for i, deployment_input_data_form in enumerate(v):
                                    d_info = dict(deployment_columns_key)
                                    # print("====d_info{}".format(d_info))
                                    for d_k, d_v in deployment_input_data_form.items():
                                        if d_k in deployment_columns_key:
                                            d_info[d_k] = d_v
                                    for d_k in list(deployment_columns_key.keys()):
                                        if d_info[d_k] is None:
                                            del d_info[d_k]
                                    v[i] = d_info
                                for i, deployment_input_data_form in reversed(list(enumerate(v))):
                                    if len(set(["api_key", "location"])-(set(deployment_columns_key)-set(deployment_input_data_form)))<2:
                                    # if deployment_input_data_form["location"]==None or deployment_input_data_form["api_key"]==None:
                                        # print("====deployment_input_data_form{}".format(deployment_input_data_form))
                                        del v[i]

                            # elif k == "deployment_input_data_form_list" and type(v) == type([]):
                            #     for d_c_k in deployment_columns_key:
                            #         model_info["deployment_input_data_form_list"].append(item)
                            elif k == "input_data_dirs" and type(v) == type([]):
                                v = ",".join(v)
                            elif k == "deployment_output_types" and type(v) == type([]):
                                v = ",".join(v)

                            model_info[k] = v


                    for k in list(model_info.keys()):
                        if model_info[k] is None:
                            del model_info[k]
                    # if model_info["id"] is None:
                    #     del model_info["id"]
                    model_info_list.append(model_info)
                    print("Built_in model : [{}] loaded".format(info_file))
                except FileNotFoundError:
                    print("Built_in model : [{}] Not loaded : info.json file not found".format(info_file))
                except NotADirectoryError:
                    pass
                except :
                    print("Built_in model : [{}] Error".format(info_file))
                    traceback.print_exc()

            built_in_model_id_set=set()
            for model_info in model_info_list:
                training_input_data_form_list = []
                deployment_input_data_form_list = []
                built_in_model_parameter_list = []
                if len(model_info.get("training_input_data_form_list")) > 0:
                    training_input_data_form_list = model_info.get("training_input_data_form_list")
                if len(model_info.get("deployment_input_data_form_list")) > 0:
                    deployment_input_data_form_list = model_info.get("deployment_input_data_form_list")
                if "parameters" in model_info.keys():
                    if model_info.get("parameters") is not None and len(list(model_info.get("parameters").values())) > 0:
                        built_in_model_parameter_list = list(model_info.get("parameters").values())
                    del model_info["parameters"]
                del model_info["training_input_data_form_list"]
                del model_info["deployment_input_data_form_list"]


                cur = conn.cursor()
                keys = ",".join(list(model_info.keys()))

                values =  ",".join([ "'{}'".format(value) if type(value) == type("") else "{}".format(value) for value in list(model_info.values()) ])
                print("=======\nvalues: ".format(values))
                sql = """
                    INSERT INTO built_in_model ({}) VALUES ({})
                """.format(keys, values)
                built_in_model_id = model_info.get("id")
                try:
                    cur.execute(sql)
                    if built_in_model_id==None:
                        built_in_model_id = cur.lastrowid
                    conn.commit()
                except pymysql.err.IntegrityError as e:
                    pass
                except Exception as e:
                    traceback.print_exc()
                    print("Built_in model : [{0}] insert Error : {0} ".format(model_info["path"], str(e)))
                    continue

                if built_in_model_id == None:
                    continue

                if built_in_model_id in built_in_model_id_set:
                    print("Built_in_model : Duplicate ID in [{}/{}] file".format(model_info["path"], model_info["infojson_path"]))
                    continue

                built_in_model_id_set.add(built_in_model_id)

                try:
                    # TODO TRAINING INPUT FORM 이 없는 경우 해당 부분 거치지 않도록
                    if len(training_input_data_form_list) > 0:
                        # built_in_model_id = get_built_in_model(model_name=model_info["name"])["id"]
                        keys = ""
                        values = []
                        for item in training_input_data_form_list:
                            item["built_in_model_id"] = built_in_model_id
                            keys = ",".join(list(item.keys()))
                            values = ",".join([ "'{}'".format(value) if type(value) == type("") else "{}".format(value) for value in list(item.values()) ])
                            sql = """
                                INSERT INTO built_in_model_data_training_form ({}) VALUES({})
                            """.format(keys, values)
                            try:
                                cur.execute(sql)
                                conn.commit()
                            except pymysql.err.IntegrityError as e:
                                pass
                            except Exception as e:
                                traceback.print_exc()
                except Exception as e:
                    traceback.print_exc()
                    print("Built_in model : [{0}] insert Error : {0} ".format(model_info["name"]), str(e))
                    continue
                try:
                    if len(deployment_input_data_form_list) > 0:
                        # built_in_model_id = get_built_in_model(model_name=model_info["name"])["id"]
                        keys = ""
                        values = []

                        for item in deployment_input_data_form_list:
                            item["built_in_model_id"] = built_in_model_id
                            keys = ",".join(list(item.keys()))
                            values = ",".join([ "'{}'".format(value) for value in list(item.values()) ])
                            sql = """
                                INSERT INTO built_in_model_data_deployment_form ({}) VALUES({})
                            """.format(keys, values)
                            try:
                                cur.execute(sql)
                                conn.commit()
                            except pymysql.err.IntegrityError as e:
                                pass
                            except Exception as e:
                                traceback.print_exc()
                except Exception as e:
                    traceback.print_exc()
                    print("Built_in model : [{0}] insert Error : {0} ".format(model_info["path"]), str(e))
                    continue

                try:

                    if len(built_in_model_parameter_list) > 0:
                        # print(built_in_model_parameter_list, model_info["name"])
                        # built_in_model_id = get_built_in_model(model_name=model_info["name"])["id"]
                        keys = ""
                        values = []

                        for item in built_in_model_parameter_list:
                            item["built_in_model_id"] = built_in_model_id
                            keys = ",".join(list(item.keys()))
                            values = ",".join([ "'{}'".format(value) for value in list(item.values()) ])
                            sql = """
                                INSERT INTO built_in_model_parameter ({}) VALUES({})
                            """.format(keys, values)
                            try:
                                cur.execute(sql)
                                conn.commit()
                            except pymysql.err.IntegrityError as e:
                                pass
                            except Exception as e:
                                traceback.print_exc()
                except Exception as e:
                    traceback.print_exc()
                    print("Built_in model : [{0}] insert Error : {0} ".format(model_info["path"]), str(e))
                    continue

                print("Built_in model : [{}] insert".format(model_info["path"]))
        except:
            traceback.print_exc()

def get_image_id_by_name(name):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT id
            FROM image
            WHERE name=%s """
            cur.execute(sql, name)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
        return False, e


def get_docker_image_name_and_id_list(workspace_id=None):
    try:
        res = None
        if workspace_id==None:
            with get_db() as conn:

                cur = conn.cursor()
                sql = """
                    SELECT i.id, i.name FROM image i
                """
                cur.execute(sql)
                res = cur.fetchall()

        else:
            with get_db() as conn:

                cur = conn.cursor()

                # sql = 'SELECT * FROM image WHERE workspace_id={}'.format(workspace_id)
                sql = """
                    SELECT i.id, i.name FROM image i
                    LEFT JOIN image_workspace iw ON i.id = iw.image_id
                    WHERE i.access = 1 OR iw.workspace_id = {} AND i.status = 2
                """.format(workspace_id)

                cur.execute(sql)
                res = cur.fetchall()

    except Exception as e:
        pass
    return res



def get_built_in_model_kind():
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                    SELECT DISTINCT kind
                    FROM built_in_model
                """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res