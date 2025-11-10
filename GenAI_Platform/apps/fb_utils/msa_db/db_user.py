from typing import List
from datetime import datetime

import traceback
import pymysql

from utils.msa_db.db_base import get_db
from utils.msa_db.db_base_async import select_query, commit_query
from utils import TYPE, PATH, settings


#TODO
# 추후 각 아이템별 유저리스트 추가되면 삭제
def get_users():
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT *
            FROM user 
            """
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res

def get_user(user_id : int = None, user_name: str = None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT *
            FROM user """

            params = None
            if user_id:
                sql += " WHERE id = %s"
                params = (user_id, )
            elif user_name:
                sql += " WHERE name = %s"
                params = (user_name, )
            cur.execute(sql, params)
            res = cur.fetchone()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


def insert_user_group(user_group_id : int , user_id : int):
    try:
        res = None
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            INSERT INTO user_usergroup(usergroup_id, user_id) VALUES ({user_group_id}, {user_id})
            """
            cur.execute(sql)
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
    return False



def get_usergroups(search_key=None, size=None, page=None, search_value=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT ug.*, 
                    (SELECT GROUP_concat(uug.user_id) FROM user_usergroup uug WHERE uug.usergroup_id = ug.id) AS user_id_list,
                    (SELECT GROUP_concat(u.name) FROM user_usergroup uug JOIN user u ON uug.user_id = u.id WHERE uug.usergroup_id = ug.id) AS user_name_list
                FROM usergroup ug
            """

            if search_key is not None and search_value is not None:
                search_value = '"%{}%"'.format(search_value)
                sql += " where ug.{} like {} ".format(search_key, search_value)

            if size is not None and page is not None:
                sql += " limit {}, {}".format((page-1)*size, size)

            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        raise
    
def get_user_id(user_name):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT id, user_type
                FROM user
                WHERE name = '{}'""".format(user_name)

            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
        return res


def execute_and_fetch(*args, **kwargs):
    """Excute and fetch all.

    Returns None on error.

    """
    result = None
    try:
        with get_db() as connection:
            cursor = connection.cursor()

            cursor.execute(*args, **kwargs)
            connection.commit()
            result = cursor.fetchall()
    except:
        traceback.print_exc()
    return result



def get_user_list_has_group():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT DISTINCT user_id
                FROM user_usergroup
            """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
        raise
    return res


def get_user_list(search_key=None, size=None, page=None, search_value=None):
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()

            # sql = "SELECT u.*, "\
            #         "(select count(*) from user_workspace uw where uw.user_id = u.id) as workspaces , "\
            #         "(select count(*) from user_training ut where ut.user_id = u.id) as trainings , "\
            #         "(select count(*) from image i where i.user_id = u.id) as images, "\
            #         "(select count(*) from dataset d where d.create_user_id = u.id) as datasets ,"\
            #         "case u.user_type "\
            #         "WHEN 0 "\
            #             "THEN 0 "\
            #         "WHEN 3 "\
            #             "THEN "\
            #                 "case (select (case when count(w.manager_id)>0 THEN 1 ELSE 0 end) as w_chk  from workspace as w where w.manager_id=u.id) "\
            #                 "WHEN 0 "\
            #                     "THEN (select (case when count(t.user_id)>0 THEN 2 ELSE 3 end) as p_chk  from training as t where t.user_id=u.id) "\
            #                 "WHEN 1 "\
            #                     "THEN 1 "\
            #                 "end "\
            #         "end as real_user_type "\
            #         "FROM user as u "
            sql = """
                SELECT u.*,
                (select count(*) from user_workspace uw where uw.user_id = u.id) as workspaces ,
                (SELECT count(DISTINCT p.id) FROM project p
                RIGHT JOIN user_workspace uw ON uw.workspace_id = p.workspace_id
                RIGHT JOIN user_project up ON up.project_id = p.id
                WHERE uw.user_id = u.id AND (p.access = 1 OR (p.access=0 AND up.user_id = u.id))) as projects ,
                (SELECT count(DISTINCT d.id) FROM deployment d
                RIGHT JOIN user_workspace uw ON uw.workspace_id = d.workspace_id
                RIGHT JOIN user_deployment ud ON ud.deployment_id = d.id
                WHERE uw.user_id = u.id AND (d.access = 1 OR (d.access=0 AND ud.user_id = u.id))) as deployments ,
                (select count(*) from image i where i.user_id = u.id) as images,
                (select count(*) from datasets d where d.create_user_id = u.id) as datasets ,
                case u.user_type
                WHEN 0
                THEN 0
                    WHEN 3
                        THEN
                            case (select (case when count(w.manager_id)>0 THEN 1 ELSE 0 end) as w_chk  from workspace as w where w.manager_id=u.id)
                        WHEN 0
                            THEN (select (case when count(p.create_user_id)>0 THEN 2 ELSE 3 end) as p_chk  from project as p where p.create_user_id=u.id)
                        WHEN 1
                            THEN 1
                end
                end as real_user_type,
                ug.name AS group_name
                FROM user as u
                LEFT JOIN user_usergroup uug ON uug.user_id = u.id
                LEFT JOIN usergroup ug ON ug.id = uug.usergroup_id
            """

            if search_key is not None and search_value is not None:
                search_value = '"%{}%"'.format(search_value)
                sql += "where u.{} like {} ".format(search_key, search_value)

            if size is not None and page is not None:
                sql += "limit {}, {}".format((page-1)*size, size)

            cur.execute(sql)
            res = cur.fetchall()

    except:
        traceback.print_exc()
    return res


def get_user_name_and_id_list(users_id):
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()

            users_id = [str(id) for id in users_id]
            users_id = ','.join(users_id)

            sql = """SELECT id, name
                FROM user
                WHERE id in ({})

                """.format(users_id)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_user_group_in(user_id : int, user_group_id : int):
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = f"""
                SELECT *
                FROM user_usergroup
                WHERE user_id = {user_id} and usergroup_id = {user_group_id}
                """

            cur.execute(sql)
            res = cur.fetchone()
        return res
    except:
        traceback.print_exc()
    return res

def delete_user_group(user_id : int):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = f"""
                DELETE FROM user_usergroup
                WHERE user_id = {user_id}
                """

            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
    return False


def get_usergroup(usergroup_id=None, usergroup_name=None):
    # SELECT GROUP_concat(uug.user_id), GROUP_CONCAT(u.name)
    # FROM user_usergroup uug
    # LEFT JOIN user u ON u.id = uug.user_id
    # WHERE uug.usergroup_id = 4
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            if usergroup_id is not None:
                sql = """
                    SELECT ug.*, 
                        (SELECT GROUP_concat(uug.user_id) FROM user_usergroup uug WHERE uug.usergroup_id = ug.id) AS user_id_list,
                        (SELECT GROUP_concat(u.name) FROM user_usergroup uug JOIN user u ON uug.user_id = u.id WHERE uug.usergroup_id = ug.id) AS user_name_list
                    FROM usergroup ug
                    WHERE id = {id}
                """.format(id=usergroup_id)
            elif usergroup_name is not None:
                sql = """
                    SELECT ug.*, (SELECT GROUP_concat(uug.user_id) FROM user_usergroup uug WHERE uug.usergroup_id = ug.id) AS user_id_list,
                    (SELECT GROUP_concat(u.name) FROM user_usergroup uug JOIN user u ON uug.user_id = u.id WHERE uug.usergroup_id = ug.id) AS user_name_list
                    FROM usergroup ug
                    WHERE BINARY name = "{name}"
                """.format(name=usergroup_name)
            cur.execute(sql)
            res = cur.fetchone()
            if res is not None:
                res["user_id_list"] = list(map(int, res["user_id_list"].split(","))) if res["user_id_list"] is not None else []
                res["user_name_list"] = list(map(str, res["user_name_list"].split(","))) if res["user_name_list"] is not None else []
        return res, ""
    except Exception as e:
        traceback.print_exc()
        return res, e
    
    
def get_usergroup_list(search_key=None, size=None, page=None, search_value=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                SELECT ug.*, 
                    (SELECT GROUP_concat(uug.user_id) FROM user_usergroup uug WHERE uug.usergroup_id = ug.id) AS user_id_list,
                    (SELECT GROUP_concat(u.name) FROM user_usergroup uug JOIN user u ON uug.user_id = u.id WHERE uug.usergroup_id = ug.id) AS user_name_list
                FROM usergroup ug
            """

            if search_key is not None and search_value is not None:
                search_value = '"%{}%"'.format(search_value)
                sql += " where ug.{} like {} ".format(search_key, search_value)

            if size is not None and page is not None:
                sql += " limit {}, {}".format((page-1)*size, size)

            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
        raise
    
    
    
def insert_usergroup(usergroup_name, description):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = """
            INSERT into usergroup(name, description)
            values (%s, %s)
            """
            cur.execute(sql, (usergroup_name, description))
            conn.commit()

        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
    
def insert_user_usergroup_list(usergroup_id_list: [], user_id_list: []):
    if len(user_id_list) == 0:
        return True, ""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            rows = []
            for i in range(len(usergroup_id_list)):
                rows.append((usergroup_id_list[i], user_id_list[i]))

            sql = "INSERT IGNORE into user_usergroup(usergroup_id, user_id) values (%s,%s)"
            cur.executemany(sql, rows)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
def delete_usergroup_list(usergroup_id_list):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            rows = []
            for i in range(len(usergroup_id_list)):
                rows.append((usergroup_id_list[i]))

            sql = """
                DELETE from usergroup
                WHERE id = %s
            """
            cur.executemany(sql, rows)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
def update_usergroup(usergroup_id, usergroup_name, description):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = """
            UPDATE usergroup
            SET name = %s, description = %s, update_datetime = %s 
            WHERE id = %s
            """
            cur.execute(sql, (usergroup_name, description, datetime.today().strftime(TYPE.TIME_DATE_FORMAT), usergroup_id))
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def update_user_usergroup(user_id, usergroup_id):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = """
            UPDATE user_usergroup
            SET usergroup_id= %s 
            WHERE user_id = %s
            """
            cur.execute(sql, (usergroup_id, user_id))
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
def delete_user_usergroup_list(usergroup_id_list: [], user_id_list: []):
    if len(user_id_list) == 0:
        return True, ""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            rows = []
            for i in range(len(usergroup_id_list)):
                rows.append((usergroup_id_list[i], user_id_list[i]))

            sql = """
                DELETE from user_usergroup
                WHERE usergroup_id = %s AND user_id = %s
            """
            cur.executemany(sql, rows)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
def get_user_docker_image(user_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT DISTINCT *
                FROM image i
                WHERE i.user_id = {}
                """.format(user_id)
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res



def get_user_dataset(user_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT DISTINCT *
                FROM datasets d
                WHERE d.create_user_id = {}
                """.format(user_id)
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_user_workspace_dataset(user_id, workspace_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT DISTINCT *
                FROM datasets d
                WHERE d.create_user_id = {} and d.workspace_id = {}
                """.format(user_id, workspace_id)
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_user_training(user_id, only_owner=None, only_users=None):
    # owner | users  = same
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT DISTINCT *
                FROM project p
                LEFT OUTER JOIN user_project up ON up.project_id = p.id
                """
                
            if only_owner == True:
                sql += " WHERE p.create_user_id = {} ".format(user_id)
            elif only_users == True:
                sql += " WHERE up.user_id = {} ".format(user_id)
            elif only_owner is None and only_users is None:
                sql += " WHERE p.create_user_id = {} OR up.user_id = {} ".format(user_id, user_id)
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


async def get_user_async(user_id : int = None, user_name : str = None):
    res = None
    if user_id is not None:

        sql = """SELECT u.*, uug.usergroup_id usergroup_id,
            ug.name AS group_name, ug.id AS group_id
            FROM user u
            LEFT JOIN user_usergroup uug ON uug.user_id = u.id
            LEFT JOIN usergroup ug ON uug.usergroup_id = ug.id
            WHERE u.id = %s"""
        res = await select_query(query=sql, params=(user_id,), fetch_type="one")
    elif user_name is not None:

        sql = """SELECT u.*, uug.usergroup_id usergroup_id,
            ug.name AS group_name, ug.id AS group_id
            FROM user u
            LEFT JOIN user_usergroup uug ON uug.user_id = u.id
            LEFT JOIN usergroup ug ON uug.usergroup_id = ug.id
            WHERE u.name = %s"""
        res = await select_query(query=sql, params=(user_name,), fetch_type="one")
    return res


def get_user(user_id=None, user_name=None):
    res = None
    try:
        with get_db() as conn:
        # with get_db() as conn:

            cur = conn.cursor()

            if user_id is not None:

                sql = """SELECT u.*, uug.usergroup_id usergroup_id,
                    ug.name AS group_name, ug.id AS group_id
                    FROM user u
                    LEFT JOIN user_usergroup uug ON uug.user_id = u.id
                    LEFT JOIN usergroup ug ON uug.usergroup_id = ug.id
                    WHERE u.id = %s"""

                cur.execute(sql, (user_id,))
            elif user_name is not None:

                sql = """SELECT u.*, uug.usergroup_id usergroup_id,
                    ug.name AS group_name, ug.id AS group_id
                    FROM user u
                    LEFT JOIN user_usergroup uug ON uug.user_id = u.id
                    LEFT JOIN usergroup ug ON uug.usergroup_id = ug.id
                    WHERE u.name = %s"""

                cur.execute(sql, (user_name,))

            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res


def update_user_password(user_id : int, new_password: str):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "UPDATE user SET password = %s, login_counting = 0 WHERE id = %s"
            cur.execute(sql, (new_password, user_id))
            conn.commit()
        return True
    except:
        traceback.print_exc()
    return False


def update_user_info(user_id : int, email: str = None, job: str = None, nickname: str = None, team: str = None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            sql = "UPDATE user "
            set_query = []
            if email is not None:
                set_query.append(f"email='{email}'")
            if job is not None:
                set_query.append(f"job='{job}'")
            if nickname is not None:
                set_query.append(f"nickname='{nickname}'")
            if team is not None:
                set_query.append(f"team='{team}'")
            sql += f" SET {','.join(set_query)}  WHERE id='{user_id}'"

            print(sql)
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
    return False

def insert_user(user_name : str, password : str, uid : str, user_type : int,
                email : str = None, job : str = None, team : str = None, nickname : str = None):
    user_id = None
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "INSERT into user(name, uid, user_type, password, email, job, team, nickname) values (%s,%s,%s,%s,%s,%s,%s,%s)"
            cur.execute(sql, (user_name, uid, user_type, password, email, job, team, nickname))
            conn.commit()
            user_id = cur.lastrowid
        return user_id
    except:
        traceback.print_exc()
    return user_id

def insert_user_s(create_user_list, create_datetime):
    # key : [{ new_user_name, uid, user_type,  }]
    try:
        with get_db() as conn:

            cur = conn.cursor()

            rows = []
            for i in range(len(create_user_list)):
                new_user_name = create_user_list[i]["new_user_name"]
                uid = create_user_list[i]["uid"]
                user_type = create_user_list[i]["user_type"]
                rows.append((new_user_name, uid, user_type, create_datetime, create_datetime))
            sql = "INSERT into user(name, uid, user_type, create_datetime, update_datetime) values (%s,%s,%s,%s,%s)"
            cur.executemany(sql, rows)
            conn.commit()

        return True
    except:
        traceback.print_exc()
    return None


def get_users_id(users_name):
    # [test1,test2,test3..]
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()

            users_name = ['"'+user_name+'"' for user_name in users_name]
            users_name = ','.join(users_name)
            sql = """SELECT id
                FROM user
                WHERE name in ({})""".format(users_name)
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def insert_user_workspace_s(workspaces_id: [], users_id: []):
    # workspaces_id = [[1,2,3],[1],[],[1,3]]
    # users_id = [1,2,3]
    try:
        with get_db() as conn:

            cur = conn.cursor()

            rows = []
            for i in range(len(workspaces_id)):
                for workspace_id in workspaces_id[i]:
                    rows.append((workspace_id,users_id[i]))
            sql = "INSERT into user_workspace(workspace_id,user_id) values (%s,%s)"
            # cur.execute(sql, (workspace_id, user_id))
            cur.executemany(sql, rows)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def get_user_deployment(user_id, only_owner=None, only_users=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT DISTINCT *
                FROM deployment d
                LEFT OUTER JOIN user_deployment ud ON ud.deployment_id = d.id
                """
            if only_owner == True:
                sql += " WHERE d.user_id = {} ".format(user_id)
            elif only_users == True:
                sql += " WHERE ud.user_id = {} ".format(user_id)
            elif only_owner is None and only_users is None:
                sql += " WHERE d.user_id = {} OR ud.user_id = {} ".format(user_id, user_id)

            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_manager_workspace(user_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT name
                FROM workspace
                WHERE manager_id = {}""".format(user_id)

            cur.execute(sql)
            res = cur.fetchall()

    except:
        traceback.print_exc()
    return res


def delete_users(users_id):
    try:
        with get_db() as conn:

            cur = conn.cursor()

            users_id = [str(id) for id in users_id]
            users_id = ','.join(users_id)
            cur.execute("DELETE from user where id in ({})".format(users_id))
            conn.commit()

        return True
    except:
        traceback.print_exc()
        return False
    return False



def delete_user_usergroup(user_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """
                DELETE from user_usergroup
                WHERE user_id = %s
            """
            cur.execute(sql, (user_id,))
            conn.commit()
        return True
    except Exception as e:
        traceback.print_exc()
        raise
    
    
def update_user_login_counting_set(user_id, value=None):
    """
    Description: 유저의 login_counting column 값을 특정 값으로 수정하는 기능
    """
    try:
        if value is None:
            value = TYPE.MAX_NUM_OF_LOGINS
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE user SET login_counting = {value}
                WHERE id = {user_id}
            """
            cur.execute(sql)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
def get_user_workspace(user_id):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()

            sql = """SELECT DISTINCT w.id, w.name as workspace_name
                FROM user_workspace uw
                INNER JOIN workspace w ON uw.workspace_id = w.id
                WHERE uw.user_id in (%s) OR w.manager_id in (%s)"""

            cur.execute(sql, (user_id,user_id,))
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res


def get_login_session(token=None, user_id=None, session_id=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if token is not None:
                sql = """
                    SELECT *
                    FROM login_session ls
                    WHERE ls.token = '{}'
                """.format(token)
            elif user_id is not None:
                sql = """
                    SELECT *
                    FROM login_session ls
                    WHERE ls.user_id = '{}'
                """.format(user_id)
            elif session_id is not None:
                sql = """
                    SELECT *
                    FROM login_session ls
                    WHERE ls.id = '{}'
                """.format(session_id)

            cur.execute(sql)
            res = cur.fetchone()
            return res, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
def delete_login_session(token=None, user_id=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if token is not None and user_id is not None:
                sql = """
                    DELETE
                    FROM login_session
                    WHERE token = "{}" and user_id = "{}"
                """.format(token, user_id)
            elif token is not None:
                sql = """
                    DELETE
                    FROM login_session
                    WHERE token = "{}"
                """.format(token)
            elif user_id is not None:
                sql = """
                    DELETE
                    FROM login_session
                    WHERE user_id = "{}"
                """.format(user_id)
            cur.execute(sql)
            conn.commit()
            return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
def update_login_session_token(old_token, new_token):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE login_session
                SET token = "{}", last_call_datetime = "{}"
                WHERE token = "{}"
            """.format(new_token, datetime.today().strftime(TYPE.TIME_DATE_FORMAT), old_token)
            num_of_item = cur.execute(sql)
            if num_of_item == 0:
                print("Already Updated")
                return False, "Already Updated"
            conn.commit()
            return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
def update_login_session_last_call_datetime(token, datetime=datetime.today().strftime(TYPE.TIME_DATE_FORMAT)):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE login_session
                SET last_call_datetime = "{}"
                WHERE token = "{}"
            """.format(datetime, token)
            cur.execute(sql)
            conn.commit()
            return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def update_login_session_user_id_last_call_datetime(user_id, datetime=datetime.today().strftime(TYPE.TIME_DATE_FORMAT)):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE login_session
                SET last_call_datetime = "{}"
                WHERE user_id = {}
            """.format(datetime, user_id)
            cur.execute(sql)
            conn.commit()
            return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
    
def get_workspace_list(page : int=None, size: int=None, search_key: str=None, search_value: str=None, user_id: int=None, sort: int=None):
    try:
        res = []
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT DISTINCT w.*, u.name as manager_name
            FROM workspace w
            INNER JOIN user as u ON w.manager_id = u.id
            INNER JOIN user_workspace uw ON uw.workspace_id = w.id"""
            
            if search_key != None and search_value != None:
                sql += " and " if "where" in sql else " where "
                if search_key == "name":
                    sql += " w.{} like '%{}%' ".format(search_key, search_value)
                elif search_key == "user_id":
                    sql += " w.manager_id = {} or uw.user_id = {} ".format(search_value, search_value)
                else:
                    sql += " {} = {} ".format(search_key, search_value)
            
            if user_id is not None:
                if not "where" in sql:
                    sql += " where "
                else:
                    sql += "and "
                sql += " w.id in (select workspace_id from user_workspace WHERE user_id={}) ".format(user_id,user_id)        
            
            if sort is not None:
                if sort == "created_datetime":
                    sql += " ORDER BY w.create_datetime desc "
                elif sort == "last_run_datetime":
                    sql += " ORDER BY p.last_run_datetime desc "
            else :
                sql += " ORDER BY w.create_datetime desc, w.id asc "

            if page is not None and size is not None:
                sql += " limit {}, {} ".format((page-1)*size, size)
            
            cur.execute(sql)
            res = cur.fetchall()
        return res
    except Exception as e:
        traceback.print_exc()
    return res


def update_user_login_counitng(user_id, set_default=False):
    """
    Description: 유저의 login_counting column 값을 1 더하는 기능
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if not set_default:
                sql = """
                    UPDATE user set login_counting = login_counting + 1
                    where id = {}
                """.format(user_id)
            else:
                sql = """
                    UPDATE user set login_counting = 0
                    where id = {}
                """.format(user_id)

            cur.execute(sql)
            conn.commit()

        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    # return False, ""

def update_user_login_counting_set(user_id, value=None):
    """
    Description: 유저의 login_counting column 값을 특정 값으로 수정하는 기능
    """
    try:
        if value is None:
            value = TYPE.MAX_NUM_OF_LOGINS
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                UPDATE user SET login_counting = {value}
                WHERE id = {user_id}
            """
            cur.execute(sql)
            conn.commit()
        return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e
    
    
def login(name):
    res = None
    try:
        with get_db() as conn:

            cur = conn.cursor()

            sql = "SELECT * from user where name = '{}'".format(name)
            cur.execute(sql)
            res = cur.fetchone()
    except Exception as e:
        print(e)
    return res


# User session

def get_login_session(token=None, user_id=None, session_id=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if token is not None:
                sql = """
                    SELECT *
                    FROM login_session ls
                    WHERE ls.token = '{}'
                """.format(token)
            elif user_id is not None:
                sql = """
                    SELECT *
                    FROM login_session ls
                    WHERE ls.user_id = '{}'
                """.format(user_id)
            elif session_id is not None:
                sql = """
                    SELECT *
                    FROM login_session ls
                    WHERE ls.id = '{}'
                """.format(session_id)

            cur.execute(sql)
            res = cur.fetchone()
            return res, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def insert_login_session(user_id, token):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT INTO login_session (user_id, token) values (%s,%s)
            """
            cur.execute(sql,(user_id, token))
            conn.commit()
            return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def update_login_session_last_call_datetime(token, datetime=datetime.today().strftime(TYPE.TIME_DATE_FORMAT)):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE login_session
                SET last_call_datetime = "{}"
                WHERE token = "{}"
            """.format(datetime, token)
            cur.execute(sql)
            conn.commit()
            return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def update_login_session_user_id_last_call_datetime(user_id, datetime=datetime.today().strftime(TYPE.TIME_DATE_FORMAT)):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE login_session
                SET last_call_datetime = "{}"
                WHERE user_id = {}
            """.format(datetime, user_id)
            cur.execute(sql)
            conn.commit()
            return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e


def update_login_session_token(old_token, new_token):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE login_session
                SET token = "{}", last_call_datetime = "{}"
                WHERE token = "{}"
            """.format(new_token, datetime.today().strftime(TYPE.TIME_DATE_FORMAT), old_token)
            num_of_item = cur.execute(sql)
            if num_of_item == 0:
                print("Already Updated")
                return False, "Already Updated"
            conn.commit()
            return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_login_session(token=None, user_id=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if token is not None and user_id is not None:
                sql = """
                    DELETE
                    FROM login_session
                    WHERE token = "{}" and user_id = "{}"
                """.format(token, user_id)
            elif token is not None:
                sql = """
                    DELETE
                    FROM login_session
                    WHERE token = "{}"
                """.format(token)
            elif user_id is not None:
                sql = """
                    DELETE
                    FROM login_session
                    WHERE user_id = "{}"
                """.format(user_id)
            cur.execute(sql)
            conn.commit()
            return True, ""
    except Exception as e:
        traceback.print_exc()
        return False, e

def delete_expired_login_sessions(session_interval = settings.TOKEN_EXPIRED_TIME):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = '''
            DELETE FROM login_session
            WHERE login_session.last_call_datetime < DATE_SUB(NOW(), INTERVAL ''' + str(session_interval)  + " SECOND);"
            cur.execute(sql)
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

def get_user_list_in_workspace(workspace_id):
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
            SELECT u.id, u.name
            FROM user u
            LEFT JOIN user_workspace uw ON uw.user_id = u.id
            WHERE uw.workspace_id=%s
            """
            cur.execute(sql, (workspace_id))
            res = cur.fetchall()
    except Exception as e:
        traceback.print_exc()
    return res
    
# =======================================
# 회원가입
def insert_user_register(name, password, nickname=None, job=None, team=None, email=None):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
                INSERT INTO user_register (name, password, nickname, team, job, email)
                values (%s,%s,%s,%s,%s,%s)
            """
            cur.execute(sql,(name, password, nickname, team, job, email))
            conn.commit()
            request_id = cur.lastrowid
        return True, request_id
    except:
        traceback.print_exc()
        return False, None

def get_user_register_list():
    res = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = f"""
            SELECT *
            FROM user_register
            ORDER BY id DESC;
            """
            cur.execute(sql)
            res = cur.fetchall()
    except:
        traceback.print_exc()
    return res

def get_user_register(register_id=None, user_name=None):
    res = None
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                SELECT *
                FROM user_register
            """
            if register_id is not None:
                sql += f"WHERE id='{register_id}'"
            elif user_name is not None:
                sql += f"WHERE name='{user_name}'"
            cur.execute(sql)
            res = cur.fetchone()
    except:
        traceback.print_exc()
    return res

def delete_user_register(register_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                DELETE
                FROM user_register
                WHERE id=%s
            """
            cur.execute(sql,(register_id))
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    

def insert_login_history(user_id, session):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT INTO login_history (user_id, session) values (%s,%s)
            """
            cur.execute(sql,(user_id, session))
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False
    
def update_login_history_logout_datetime(user_id, session):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                UPDATE login_history
                SET logout_datetime = NOW()
                WHERE user_id = %s and session = %s
            """
            cur.execute(sql,(user_id, session))
            conn.commit()
        return True 
    except:
        traceback.print_exc()
        return False
    
def insert_login_session(user_id, session):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sql = """
                INSERT INTO login_session (user_id, token, last_call_datetime) values (%s,%s, NOW())
            """
            cur.execute(sql,(user_id, session))
            conn.commit()
        return True
    except:
        traceback.print_exc()
        return False