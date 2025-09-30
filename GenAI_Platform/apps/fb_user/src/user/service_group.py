# from utils.resource import CustomResource, token_checker
# from flask_restplus import reqparse, Resource
# from restplus import api
from utils.resource import response
import traceback

# # import utils.db as db
from utils.msa_db import db_user
import utils.common as common
from utils import settings

# ns = api.namespace('users', description='USER API')
# parser = reqparse.RequestParser()


# get_usergroups = reqparse.RequestParser()
# get_usergroups.add_argument('page', type=int, required=False, location='args', help="페이지 번호")
# get_usergroups.add_argument('size', type=int, required=False, location='args', help="한 페이지당 개수")
# get_usergroups.add_argument('search_key', type=str, required=False, location='args', help="검색 타입")
# get_usergroups.add_argument('search_value', type=str, required=False, location='args', help="검색 값")

# post_usergroup = api.parser()
# post_usergroup.add_argument('usergroup_name', type=str, required=True, location='json', help='usergroup name ')
# post_usergroup.add_argument('user_id_list', type=list, default=[], location='json', help='user id list ')
# post_usergroup.add_argument('description', type=str, required=False, location='json', help='usergroup description')

# put_usergroup = api.parser()
# put_usergroup.add_argument('usergroup_id', type=int, required=True, location='json', help='usergroup id ')
# put_usergroup.add_argument('usergroup_name', type=str, required=True, location='json', help='usergroup name ')
# put_usergroup.add_argument('user_id_list', type=list, default=[], location='json', help='user id list ')
# put_usergroup.add_argument('description', type=str, required=False, location='json', help='usergroup description')

def usergroup_option(headers_user):
    try:
        if headers_user != settings.ADMIN_NAME:
            return response(status=0, message="permission denied")
        group_user_id_list =  [ info["user_id"] for info in db_user.get_user_list_has_group()]

        user_list = [ { "name": user["name"] , "id" : user["id"] } for user in db_user.get_user_list() if user["name"] != settings.ADMIN_NAME and user["id"] not in group_user_id_list ]

        result = {
            "user_list" : user_list
        }

        return response(status=1, result=result)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get Option error : {}".format(e))

def check_if_non_existing_user_is_included(user_id_list):
    if user_id_list == []:
        return []
    db_users = db_user.get_user_name_and_id_list(user_id_list)
    db_user_id_list = [db_user["id"] for db_user in db_users]

    user_id_set = set(user_id_list)
    db_user_id_set = set(db_user_id_list)

    non_existing_user_str_id_list = [str(id_) for id_ in sorted(user_id_set - db_user_id_set)]

    return non_existing_user_str_id_list

def get_usergroup(usergroup_id):
    try:
        usergroup_info, message = db_user.get_usergroup(usergroup_id=usergroup_id)
        if usergroup_info is None:
            return response(status=0, message="Not found usergroup : {}".format(message))

        group_user_list = []
        for i in range(len(usergroup_info["user_id_list"])):
            group_user_list.append({
                "id": usergroup_info["user_id_list"][i],
                "name": usergroup_info["user_name_list"][i]
            })

        result = {
            "name" : usergroup_info["name"],
            "description": usergroup_info["description"],
            "group_user_list": group_user_list
        }

        return response(status=1, result=result)
    except:
        traceback.print_exc()
        return response(status=0, message="Get usergroup Error")

def get_usergroup_list(page, size, search_key, search_value):
    try:
        usergroup_info_list = db_user.get_usergroup_list(page=page, size=size, search_key=search_key, search_value=search_value)
        if usergroup_info_list is None:
            return response(status=0, result={"list":[],"total":0})
        total = len(db_user.get_usergroup_list())

        usergroup_list = []
        for usergroup_info in usergroup_info_list:
            user_name_list = usergroup_info["user_name_list"].split(",") if usergroup_info["user_name_list"] is not None else []
            usergroup_list.append({
                "id": usergroup_info["id"],
                "name": usergroup_info["name"],
                "user_count": len(user_name_list),
                "create_datetime": usergroup_info["create_datetime"],
                "update_datetime": usergroup_info["update_datetime"],
                "description": usergroup_info["description"],
                "user_name_list" : user_name_list
            })

        return response(status=1, result={"list":usergroup_list, "total": total})
    except:
        traceback.print_exc()
        return response(status=0, message="Get usergroup list Error")

def create_usergroup(usergroup_name, user_id_list, description):
    try:
        non_existing_user_list = check_if_non_existing_user_is_included(user_id_list)
        if non_existing_user_list:
            return response(status=0, message="Users do not exist, user ids({})".format(", ".join(non_existing_user_list)))

        insert_usergroup_result, message = db_user.insert_usergroup(usergroup_name=usergroup_name, description=description)
        if insert_usergroup_result == False:
            if "Duplicate entry" in str(message):
                return response(status=0, message="Create usergroup Name [{}] Already Exists ".format(usergroup_name))
            return response(status=0, message="Insert usergroup Error : {}".format(message))

        usergroup_info, message = db_user.get_usergroup(usergroup_name=usergroup_name)
        insert_user_usergroup_list_result, message =  db_user.insert_user_usergroup_list(usergroup_id_list=[usergroup_info["id"]] * len(user_id_list), user_id_list=user_id_list)
        if insert_user_usergroup_list_result == False:
            return response(status=0, message="Insert user_usergroup Error : {}".format(message))

        return response(status=1, message="Usergroup : {} created".format(usergroup_name))
    except :
        traceback.print_exc()
        return response(status=0, message="Create usergroup Error")

def delete_usergroup(usergroup_id_list):
    try:
        delete_result, message = db_user.delete_usergroup_list(usergroup_id_list=usergroup_id_list)
        if delete_result == False:
            return response(status=0, message="Delete usergroup Error : {}".format(message))

        return response(status=1, message="Deleted usergroup")
    except:
        traceback.print_exc()
        return response(status=0, message="Delete usergroup Error")

def update_usergroup(usergroup_id, usergroup_name, user_id_list, description):
    try:
        non_existing_user_list = check_if_non_existing_user_is_included(user_id_list)
        if non_existing_user_list:
            return response(status=0, message="Users do not exist, user ids({})".format(", ".join(non_existing_user_list)))

        usergroup_info, message = db_user.get_usergroup(usergroup_id=usergroup_id)
        if usergroup_info is None:
            return response(status=0, message="Usergroup does not exist {}".format(message)) # OK

        if usergroup_info["name"] != usergroup_name:
            duple_check, message = db_user.get_usergroup(usergroup_name=usergroup_name)
            if duple_check is not None:
                return response(status=0, message="Usergroup Name [{}] already exists".format(usergroup_name)) # OK

        update_result, message = db_user.update_usergroup(usergroup_id=usergroup_id, usergroup_name=usergroup_name, description=description)
        if update_result == False:
            return response(status=0, message="Update usergroup name Error : {}".format(message))

        add_id_list, del_id_list = common.get_add_del_item_list(new=user_id_list, old=usergroup_info["user_id_list"])
        if len(add_id_list) == 0 and len(del_id_list) == 0:
            return response(status=1, message="Updated usergroup")

        insert_user_result, insert_message = db_user.insert_user_usergroup_list(usergroup_id_list=[usergroup_id] * len(add_id_list), user_id_list=add_id_list)
        delete_user_result, delete_message = db_user.delete_user_usergroup_list(usergroup_id_list=[usergroup_id] * len(del_id_list), user_id_list=del_id_list)

        if insert_user_result == False or delete_user_result == False:
            return response(status=0, message="Update usergroup user change error : {} {}".format(insert_message, delete_message))

        return response(status=1, message="Updated usergroup")
    except:
        traceback.print_exc()
        return response(status=0, message="Update Group Error")

# @ns.route("/group", methods=['GET', 'POST', 'PUT'])
# @ns.route('/group/<id_list>', methods=['DELETE'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class UserGroup(CustomResource):
#     @token_checker
#     @ns.expect(get_usergroups)
#     def get(self):
#         """USERGROUP GET"""
#         args = get_usergroups.parse_args()

#         page = args["page"]
#         size = args["size"]
#         search_key = args["search_key"]
#         search_value = args["search_value"]

#         if self.is_admin_user():
#             res = get_usergroup_list(page=page, size=size, search_key=search_key, search_value=search_value)
#         else:
#             res = response(status=0, message="Permisson Error")
#         return self.send(res)

#     @token_checker
#     @ns.expect(post_usergroup)
#     def post(self):
#         """USERGROUP CREATE"""
#         args = post_usergroup.parse_args()

#         usergroup_name = args["usergroup_name"]
#         user_id_list = args['user_id_list']
#         description = args['description']

#         if self.is_admin_user():
#             res = create_usergroup(usergroup_name=usergroup_name, user_id_list=user_id_list, description=description)
#         else:
#             res = response(status=0, message="Permisson Error")
#         return self.send(res)

#     @token_checker
#     @ns.param('id_list', 'id list')
#     def delete(self, id_list):
#         """USERGROUP DELETE"""

#         id_list = id_list.split(',')

#         if self.is_admin_user():
#             res = delete_usergroup(usergroup_id_list=id_list)
#         else:
#             res = response(status=0, message="Permisson Error")

#         return self.send(res)

#     @token_checker
#     @ns.expect(put_usergroup)
#     def put(self):
#         """USERGROUP UPDATE"""
#         args = put_usergroup.parse_args()

#         usergroup_id = args['usergroup_id']
#         usergroup_name = args['usergroup_name']
#         user_id_list = args['user_id_list']
#         description = args['description']

#         if self.is_admin_user():
#             res = update_usergroup(usergroup_id=usergroup_id, usergroup_name=usergroup_name, user_id_list=user_id_list, description=description)
#         else:
#             res = response(status=0, message="Permisson Error")

#         return self.send(res)

# @ns.route('/group/<int:usergroup_id>', methods=['GET'], doc={'params': {'usergroup_id': 'USERGROUP ID'}})
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class UserGroupSimple(CustomResource):
#     def __init__(self, workspace_id):
#         self.workspace_id = workspace_id

#     @token_checker
#     def get(self, usergroup_id):
#         """usergroup id 조회"""

#         if self.is_admin_user():
#             res = get_usergroup(usergroup_id=usergroup_id)
#         else:
#             res = response(status=0, message="Permisson Error")

#         return self.send(res)