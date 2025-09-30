#-*- coding: utf-8 -*-

import json

import requests
from utils.settings import LOGIN_VALIDATION_CHECK_API, LOGIN_METHOD

MARKER_API_URL = "https://jonathan.acryl.ai/marker-api/isAuto"  # User auto labeling info"
FREE_WORKSPACE_ID = 5
FREE_WORKSPACE_NAME = "acryl-free-ws"
USER_PASSWORD = 'asdf1234!'
USER_TYPE = 3

END_TIME = "2100-04-30 14:59"

# ns = api.namespace('jonathan-platform', description="User's Jonathan Flightbase usage")

# if LOGIN_METHOD == "jonathan":
#     init_users()
#     user_db_info = db.get_user_list()
#     for user in user_db_info:
#         user_name = user["name"]
#         if os.system(f"id {user_name}") != 0:
#             print('create user in linux - ssh', user_name)
#             enc_pw = crypt.crypt(USER_PASSWORD, '22') # pw encrypt
#             os.system(f'useradd -s /bin/bash -p {enc_pw} {user_name}') # create user, pw
#             uid = pwd.getpwnam(user_name).pw_uid

#     etc_backup()
#     updated_user_list = [ user_info["user_name"] for user_info in db.get_workspace_users(workspace_id=FREE_WORKSPACE_ID)]
#     update_workspace_users_etc(users=updated_user_list, workspace_name=FREE_WORKSPACE_NAME, training_list=db.get_workspace_training_list(workspace_id=FREE_WORKSPACE_ID))


# jp_parser = api.parser()
# jp_parser.add_argument('Authorization', type=str, required=True, location='headers', help="Jonathan Platform Token")

# jp_user_parser = api.parser()
# jp_user_parser.add_argument('email', type=str, required=True, location='json', help="Create JF User")
# jp_user_parser.add_argument('username', type=str, required=True, location='json', help="Create JF User")
# jp_user_parser.add_argument('password', type=str, required=True, location='json', help="Create JF User")

# jp_update_password_parser= api.parser()
# jp_update_password_parser.add_argument('username', type=str, required=True, location='json', help="Update password for a JP user")
# jp_update_password_parser.add_argument('new_password', type=str, required=True, location='json', help="Update password for a JP user")

# def _token_checker(f):
#     """
#     통합에서 발급받은 토큰 검증, 토근 유효시 유저 정보(이메일 등) 응답에서 확인
#     """
#     @functools.wraps(f)
#     def decorated_function(*args, **kwargs):
#         user_info = get_user_info_with_jp_token(request)
#         if user_info is not None:
#             if user_info.get("email") is None:
#                 return response(
#                     status=0,
#                     message=f"User email is not provided from Jonathan Platform server")
#             else:
#                 kwargs["email"] = user_info["email"]
#                 kwargs["username"] = user_info["username"]
#                 return f(*args, **kwargs)
#         else:
#             return response(
#                 status=0,
#                 message=f"Jonathan Platform token is not valid or is missing")
#     return decorated_function


def get_user_info_with_jp_token(request):
    """Validate token for Jonathan Platform

    :param api request, validate token in request header

    NOTE:
        통합(Jonathan Platform) API 담당자 Harry님
    """
    token = request.headers.get("Authorization")

    if token is None:
        print("No token in the request header")
        return None

    headers = {"Authorization": token}
    res = requests.get(LOGIN_VALIDATION_CHECK_API, headers=headers)

    if res.status_code == 200:
        # print("JP TOKEN IS VALID")
        user_info = json.loads(res.text)
        return user_info
    else:
        print("JP TOKEN IS NOT VALID")
        return None


def create_jf_user_name_from_email(email):
    """
    NOTE:
        통합 유저는 이메일 기반, JF는 이메일 기반이 아니므로 email-provider 로 JF 유저 아이디 생성
    """
    address, provider = email.split("@")
    return f"{address}-{provider.split('.')[0]}"


# def pod_end(pod_item):
#     from pod import is_job_pod, is_tool_pod, is_deployment_pod, is_hps_pod, delete_pod_resource_usage_log_dir
#     def update_item_end_time(pod_labels):
#         # CREATE_KUBER_TYPE = ["job","jupyter","deployment"]
#         # Training - editor   :  type = jupyter, editor=True ==> jupyter_id
#         #        - jupyter : type = jupyter, editor=False ==> jupyter_id
#         #        - job : type = job ==> job_id

#         # Deployment - deployment : type = deployment ==> deployment_id
#         if is_job_pod(labels=pod_labels):
#             print("Job End Time UDATE!")
#             db.update_job_end_time(job_id=pod_labels.get("job_id"))
#             print(send_gmail(pod_labels))
#         elif is_tool_pod(labels=pod_labels):
#             print("Tool End Time UDATE!")
#             db.update_training_tool_end_time(training_tool_id=pod_labels.get("training_tool_id"))
#         elif is_deployment_pod(labels=pod_labels):
#             print("Deployment End Time UDATE!")
#             db.update_deployment_end_time(deployment_id=pod_labels.get("deployment_id"))
#         elif is_hps_pod(labels=pod_labels):
#             print("HPS End Time UDATE!")
#             db.update_hyperparamsearch_end_time(hps_id=pod_labels.get("hps_id"))


#     pod_labels = kube_parser.parsing_item_labels(pod_item)
#     pod_name = kube_parser.parsing_item_name(pod_item)

#     delete_pod_resource_usage_log_dir(pod_name=pod_name)
#     update_item_end_time(pod_labels=pod_labels)

# def send_gmail(pod_labels):
#     import requests
#     import json

#     token = '8nPZYAYTZAmD94owR23u'
#     email_url = 'http://115.71.28.82:5011/app/send_email'
#     username = pod_labels.get('executor_name')
#     title = 'Jonathan™을 이용한 학습이 완료되었습니다.'
#     body = "<ul><li><b>Workspace</b> : {}</li><li><b>Training</b> : {}</li><li><b>Job</b> : {}(No.{})</li></ul>".format(pod_labels.get('workspace_name'), pod_labels.get('training_name'), pod_labels.get('job_name'), int(pod_labels.get('job_group_index'))+1 )
#     data = {"username":"{}".format(username),"token":"{}".format(token),"title":"{}".format(title),"body":"{}".format(body)}
#     r = requests.post(email_url,data=json.dumps(data))
#     if r.status_code == 200:
#         return "Send to email success"
#     return "Send to email Fail"


# @ns.route("/user", methods=['POST', 'DELETE'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class JPUser(CustomResource):
#     """
#     NOTE:
#         통합에서 유저 생성, 삭제 요청시 호출
#     """

#     @_token_checker
#     @ns.expect(jp_user_parser)
#     def post(self, *args, **kwargs):
#         args = jp_user_parser.parse_args()
#         email = args['email']
#         password = args['password']
#         username = kwargs['username']
#         email_with_valid_token = kwargs["email"]
#         if email != email_with_valid_token:
#             res = response(status=0, message=f"JP-token does not have the given email information.")
#         else:
#             res = create_user(email=email,user_name=username, password=password)
#         return self.send(res)

#     @_token_checker
#     @ns.expect(jp_user_parser)
#     def delete(self, *args, **kwargs):
#         args = jp_user_parser.parse_args()
#         email = args['email']
#         user_name = kwargs['username']
#         email_with_valid_token = kwargs["email"]

#         if email != email_with_valid_token:
#             res = response(status=0, message=f"JP-token does not have the given email information.")
#             return self.send(res)

#         try:
#             jf_user_info = get_jf_user_info(user_name)
#             if jf_user_info is None:
#                 res = response(
#                     status=1, message="User not found")
#                 return self.send(res)
#             else:
#                 user_id = jf_user_info["id"]
#                 res = delete_users(id_list=[user_id], headers_user='jonathan')
#                 return self.send(res)
#         except Exception:
#             traceback.print_exc()
#             res = response(
#                     status=0, message="Delete error")
#             return self.send(res)


# @ns.route('/jf-usage', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class JPUsage(CustomResource):
#     """Get training jobs info, docker image count and dataset count."""
#     @_token_checker
#     @ns.expect(jp_parser)
#     def get(self, *args, **kwargs):
#         """
#         NOTE:
#             최근 Job이 기준이 되어서 최근 Job의 Training 정보를 반환
#             오토라벨링 API 담당자 - Will님
#             토큰 검증 후 유저 이메일을 받아서 해당 유정 이메일로 JF 유저 이름 확인
#             JF 유저 정보로 Job, Traning, Image count, Dataset count 그리고 auto labeling 정보 반환
#         """
#         user_job_info = {
#             "image_count": 0,
#             "dataset_count": 0,
#             "auto_labeling_status": 0,
#             "training_name": "",
#             "training_type": "",
#             "job_name" : "",
#             "job_active": 0,
#             "job_progress": 0,
#             "job_count": {
#                 "pending": 0,
#                 "running": 0,
#                 "finished": 0,
#                 "total": 0
#             }
#         }

#         email_with_valid_token = kwargs["email"]
#         user_name = create_jf_user_name_from_email(email_with_valid_token)
#         jf_user_info = get_jf_user_info(user_name)
#         if jf_user_info is None:
#             res = response(
#                 status=0,
#                 message=f'Get Jonathan Flightbase user info Error(user email: {email_with_valid_token})')
#             return self.send(res)
#         try:
#             user_id = jf_user_info["id"]
#             print("jp_user_email : ",email_with_valid_token)
#             print("jf_user_name : ", user_name)
#             print("jf_user_id : ", user_id)

#             user_job_info["auto_labeling_status"] = get_user_auto_labeling_status(user_id)
#             latest_job_info = get_latest_job_info(user_id)

#             if latest_job_info is not None:
#                 user_job_info["training_name"] = latest_job_info["training_name"]
#                 user_job_info["training_type"] = latest_job_info["training_type"]
#                 user_job_info["job_name"] = latest_job_info["job_name"]
#                 job_status_info = get_job_status_info(
#                     training_id=latest_job_info["training_id"],
#                     group_number=latest_job_info["group_number"])

#                 if job_status_info is not None:
#                     user_job_info["job_count"] = job_status_info["count"]
#                     user_job_info["job_progress"] = job_status_info["progress"]

#             if user_job_info["job_count"]["finished"] != user_job_info["job_count"]["total"]:
#                 user_job_info["job_active"] = 1
#             user_job_info["image_count"] = get_docker_image_count(user_id)
#             user_job_info["dataset_count"] = get_dataset_count(user_id)
#             res = response(status=1, result=user_job_info)
#         except Exception:
#             traceback.print_exc()
#             res = response(
#                 status=0,
#                 message=f"Get user's Jonathan Flightbase usage data Error")
#         return self.send(res)

# # 향후 프론트 기능 추가까지 터치 X
# def get_user_auto_labeling_status(user_id):
#     """
#     NOTE:
#         반환되는 상태값 관련 통합(Jonathan platform) Front 담당자 - Andy님
#     """
#     user_workspaces = db.get_user_workspace(user_id)

#     if user_workspaces is not None:
#         ws_list = [ws["workspace_name"] for ws in user_workspaces]
#         if len(ws_list) == 0:
#             print("This user does not belong to any workspaces")
#             return 0
#         data = {"workspaces" : ws_list}
#         try:
#             res = requests.post(MARKER_API_URL, data=data)
#             res = json.loads(res.text)["response"]
#             print("Marker_api response : ", res)
#             status = res["isAuto"]
#             if status == "in progress":
#                 return 1
#             elif status == "finish":
#                 return 2
#             elif status == "empty":
#                 return 0
#         except:
#             traceback.print_exc()
#             print("Marker_api error")
#             return 0


# def create_user(email, user_name, password=USER_PASSWORD):
#     from storage import get_storage_and_workspace_usage_list
#     def _rollback():
#         os.system(f'userdel {user_name}')
#         etc_backup()

#     if check_exist_user_from_linux(user_name):
#         return response(status=0, message=f"User name already exists in file system, email: {email}, user name: {user_name}")
#     if db.get_user(user_name=user_name) is not None:
#         return response(status=0, message=f"User name already exists in DB, email: {email}, user name: {user_name}")

#     # add user
#     try:
#         # password = front_cipher.decrypt(password)
#         enc_pw = crypt.crypt(password, '22') # pw encrypt
#         os.system(f'useradd -s /bin/bash -p {enc_pw} {user_name}') # create user, pw
#         uid = pwd.getpwnam(user_name).pw_uid

#         etc_backup()
#     except:
#         traceback.print_exc()
#         _rollback()
#         return response(status=0, message="Linux User create error")

#     # db insert user
#     try:
#         db.insert_user(user_name, uid, USER_TYPE, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
#         jf_user_info = {
#             "email": email,
#             "name": user_name
#         }
#         user_storage=None
#         storage_list = get_storage_and_workspace_usage_list()['list']
#         for storage in storage_list:
#             if storage['share']==0:
#                 if user_storage is None:
#                     user_storage=storage
#                 else:
#                     if user_storage['usage']['pcent']<storage['usage']['pcent']:
#                         user_storage = storage
#         user_id = db.get_user_id(user_name)["id"]
#         current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         expire_time = (datetime.now() + timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
#         workspace.create_workspace(headers_user="root", manager_id=user_id, workspace_name=user_name+"-workspace", training_gpu=1, deployment_gpu=0, start_datetime=current_time, end_datetime=expire_time, users=[], description="", guaranteed_gpu=0, storage_id=user_storage['id'], workspace_size="15G")

#         return response(status=1, result=jf_user_info)
#     except:
#         traceback.print_exc()
#         _rollback()
#         return response(status=0, message="DB insert Error")


# def get_jf_user_info(user_name):
#     try:
#         res = None
#         with db.get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT
#                     id
#                 FROM
#                     user
#                 WHERE
#                     name = '{user_name}'
#             """

#             cur.execute(sql)
#             res = cur.fetchone()
#     except Exception:
#         traceback.print_exc()
#     return res


# def get_latest_job_info(user_id):
#     """Get a currently running job
#     or first job to run next if a job is not running
#     or latest finished job if every job has finished."""

#     job_info = None
#     try:
#         job_info = get_running_job_or_to_run(user_id)

#         if job_info is None:
#             job_info = get_latest_finished_job(user_id)

#     except Exception:
#         traceback.print_exc()

#     return job_info


# def get_running_job_or_to_run(user_id):
#     try:
#         res = None
#         with db.get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT
#                     t.id as training_id,
#                     t.name as training_name,
#                     t.type as training_type,
#                     j.name as job_name,
#                     j.group_number as group_number
#                 FROM
#                     job j
#                 INNER JOIN
#                     training t ON j.training_id = t.id
#                 WHERE
#                     j.creator_id = {user_id}
#                 AND
#                     j.end_datetime is NULL
#                 ORDER BY
#                     j.create_datetime ASC
#                 LIMIT 1
#             """

#             cur.execute(sql)
#             res = cur.fetchone()
#     except Exception:
#         traceback.print_exc()

#     return res


# def get_latest_finished_job(user_id):
#     try:
#         res = None
#         with db.get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT
#                     t.id as training_id,
#                     t.name as training_name,
#                     t.type as training_type,
#                     j.name as job_name,
#                     j.group_number as group_number
#                 FROM
#                     job j
#                 INNER JOIN
#                     training t ON j.training_id = t.id
#                 WHERE
#                     j.creator_id = {user_id}
#                 AND
#                     j.start_datetime is not NULL
#                 AND
#                     j.end_datetime is not NULL
#                 ORDER BY
#                     j.create_datetime DESC
#                 LIMIT 1
#             """

#             cur.execute(sql)
#             res = cur.fetchone()
#     except Exception:
#         traceback.print_exc()

#     return res


# def get_job_status_info(training_id=None, group_number=None):
#     """
#     NOTE:
#         Job status - pending, running, finished 으로 시작, 종료시간으로 확인
#     """
#     jobs_info = None
#     try:
#         jobs_group = get_jobs_group_info(training_id, group_number)

#         if len(jobs_group) > 0:
#             total_count = len(jobs_group)
#             jobs_info = {
#                 "progress": 0,
#                 "count": {
#                     "total": total_count,
#                     "pending": 0,
#                     "running": 0,
#                     "finished": 0
#                 }
#             }
#             for job in jobs_group:
#                 if job["start_datetime"] is None:
#                     jobs_info["count"]["pending"] += 1
#                 elif job["end_datetime"] is None:
#                     jobs_info["count"]["running"] += 1
#                 else:
#                     jobs_info["count"]["finished"] += 1
#             jobs_info["progress"] = int(jobs_info["count"]["finished"]
#                                         / total_count
#                                         * 100)
#     except Exception:
#         traceback.print_exc()

#     return jobs_info


# def get_jobs_group_info(training_id, group_number):
#     try:
#         res = None
#         with db.get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT
#                     id, start_datetime, end_datetime
#                 FROM
#                     job
#                 WHERE
#                     training_id={training_id}
#                 AND
#                     group_number={group_number}
#                 ORDER BY
#                     job_group_index ASC
#             """

#             cur.execute(sql)
#             res = cur.fetchall()
#     except Exception:
#         traceback.print_exc()

#     return res


# def get_docker_image_count(user_id):
#     count = 0

#     try:
#         docker_image_count = get_user_docker_image_count(user_id)
#         count = docker_image_count["count"]
#     except Exception:
#         traceback.print_exc()

#     return count


# def get_user_docker_image_count(user_id):
#     try:
#         res = None
#         with db.get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT
#                     COUNT(*) as count
#                 FROM
#                     image
#                 WHERE
#                     user_id={user_id}
#             """

#             cur.execute(sql)
#             res = cur.fetchone()
#     except Exception:
#         traceback.print_exc()

#     return res


# def get_dataset_count(user_id):
#     count = 0

#     try:
#         dataset_count = get_user_dataset_count(user_id)
#         count = dataset_count["count"]
#     except Exception:
#         traceback.print_exc()

#     return count


# def get_user_dataset_count(user_id):
#     try:
#         res = None
#         with db.get_db() as conn:
#             cur = conn.cursor()
#             sql = f"""
#                 SELECT
#                     COUNT(*) as count
#                 FROM
#                     dataset
#                 WHERE
#                     create_user_id={user_id}
#             """

#             cur.execute(sql)
#             res = cur.fetchone()
#     except Exception:
#         traceback.print_exc()

#     return res


# MARKER_DATASET_API_URL = "http://localhost:9194/datasets/status" #"http://marker.acryl.ai/api/datasets/status"
# MARKER_DATASET_FOLDER_API_URL = "http://localhost:9194/folders/status" #"http://marker.acryl.ai/api/folders/status"

# # user_workspace_parser = api.parser()
# # user_workspace_parser.add_argument('workspace_id', required=False, type=str, location='args', help='워크스페이스 아이디')
# # user_workspace_parser.add_argument('page', required=False, type=str, location='args', help='조회할 페이지 시작 인덱스')
# # user_workspace_parser.add_argument('size', required=False, type=str, location='args', help='한번에 가져올 데이터 수')
# # user_workspace_parser.add_argument('search_key', required=False, type=str, location='args', help='검색 키')
# # user_workspace_parser.add_argument('search_value', required=False, type=str, location='args', help='검색 값')

# # dataset_files_parser = api.parser()
# # dataset_files_parser.add_argument('search_path', type=str, location='args', required=False, default='/', help='업로드할 위치')
# # dataset_files_parser.add_argument('search_page', type=str, location='args', required=False, default=0, help='조회할 페이지 시작 인덱스')
# # dataset_files_parser.add_argument('search_size', type=str, location='args', required=False, default=0, help='한번에 가져올 데이터 수')
# # dataset_files_parser.add_argument('search_type', type=str, location='args', required=False, help='필터 file or dir')
# # dataset_files_parser.add_argument('search_key', type=str, location='args', required=False, help='검색 키')
# # dataset_files_parser.add_argument('search_value', type=str, location='args', required=False, help='검색 값')

# # dataset_files_info_parser = api.parser()
# # dataset_files_info_parser.add_argument('search_path', type=str, location='args', required=False, default='/', help='조회할 경로')

# auto_labeling_parser = api.parser()
# auto_labeling_parser.add_argument('workspace_id', type=str, location='form', required=True, help='워크스페이스 아이디')
# auto_labeling_parser.add_argument('dataset_id', type=str, location='form', required=True, help='데이터셋 아이디' )
# auto_labeling_parser.add_argument('auto_labeling', type=str, location='form', required=True, help='오토라벨링 0 or 1' )

# from datasets import user_workspace_parser, dataset_files_parser, dataset_files_info_parser
# from datasets import Datasets, DatasetFiles, DatasetInfo

# def get_datasets_with_autolabeling(datasets_result, jf_headers):

#     dataset_list = datasets_result["list"]

#     dataset_autolabel_check_list = []
#     dataset_autolabel_check_api_item_list = []
#     dataset_autolabel_non_check_list = []
#     workspace_name = ""
#     for dataset in dataset_list:
#         workspace_name = dataset.get("workspace_name")
#         if dataset.get("auto_labeling") == 1:
#             dataset_autolabel_check_list.append(dataset)
#             dataset_autolabel_check_api_item_list.append({
#                 "id": dataset["id"],
#                 "name": dataset["dataset_name"]
#                 })
#         else :
#             dataset_autolabel_non_check_list.append(dataset)

#         # dataset_autolabel_check_list.append(dataset)
#         # dataset_autolabel_check_api_item_list.append({
#         #     "id": dataset["id"],
#         #     "name": dataset["dataset_name"]
#         #     })

#     if len(dataset_autolabel_check_api_item_list) > 0:
#         data = {
#             "workspace": workspace_name,
#             "datasets": dataset_autolabel_check_api_item_list
#         }
#         data = json.dumps(data)
#         print(data)
#         headers = {'Content-Type': 'application/json; charset=utf-8'}
#         headers.update(jf_headers)
#         res = requests.post(MARKER_DATASET_API_URL, headers=headers, data=data)
#         marker_result = res.json()
#         print(marker_result)
#         if marker_result.get("result") != True:
#             return response(status=0, message="marker api error : {} {}".format(res, marker_result))

#     for i in range(len(dataset_autolabel_check_api_item_list)):
#         dataset_autolabel_check_list[i]["auto_labeling_status"] = marker_result["response"][i]["progress"]

#     return response(status=1, result=datasets_result)


# def get_dataset_with_autolabeling(dataset_id, dataset_result, jf_headers):
#     dataset_files = dataset_result["list"]

#     dataset_dir_info = db.get_dataset_dir(dataset_id)

#     params = {'workspace': dataset_dir_info["workspace_name"], 'dataset': dataset_dir_info["name"]}
#     res = requests.get(MARKER_DATASET_FOLDER_API_URL, params=params, headers=jf_headers)
#     res = res.json()
#     print(res)
#     if res.get("result") != True:
#         return response(status=0, message="marker api error : {}".format(res))
#     # {'result': True,
#     # 'response': {'workspace': 'ji-test', 'dataset': 'ier-image', 'progress': 'finish', 'folders':
#     # [{'folder': 'Image', 'progress': 'finish', 'percent': '100.0'}, {'folder': 'Image2', 'progress': 'finish', 'percent': '100.0'}]}}
#     marker_folder_list = res["response"]["folders"]

#     for dataset_file in dataset_files:
#         if dataset_file["type"] != "dir":
#             continue

#         for i, marker_folder in enumerate(marker_folder_list):
#             if marker_folder["folder"] ==  dataset_file["name"]:
#                 dataset_file["autolabeling_status"] = {
#                     "progress": marker_folder["progress"],
#                     "percent": marker_folder["percent"]
#                 }
#                 del marker_folder_list[i]
#                 break


#     # for dataset_file in dataset_files:
#     #     if dataset_file["type"] == "dir":
#     return response(status=1, result=dataset_result)

# def get_dataset_info_with_autolabeling(dataset_info_result, jf_headers):

#     params = {'workspace': dataset_info_result["workspace_name"], 'dataset': dataset_info_result["name"]}
#     res = requests.get(MARKER_DATASET_FOLDER_API_URL, params=params, headers=jf_headers)
#     res = res.json()
#     if res.get("result") != True:
#         return response(status=0, message="marker api error : {}".format(res))
#     # {'result': True,
#     # 'response': {'workspace': 'ji-test', 'dataset': 'ier-image', 'progress': 'finish', 'folders':
#     # [{'folder': 'Image', 'progress': 'finish', 'percent': '100.0'}, {'folder': 'Image2', 'progress': 'finish', 'percent': '100.0'}]}}
#     dataset_info_result["autolabeling_progress"] = res["response"]["progress"]

#     return response(status=1, result=dataset_info_result)


# def auto_labeling_update(body,headers_user=None):
#     try:
#         result = db.update_dataset(id = body['dataset_id'], name=None,
#                                         workspace_id=None, access=None, file_count=None, description=None,auto_labeling=body['auto_labeling'])
#         print('auto_labeling update success')
#         if result:
#             db.logging_history(user=headers_user, task='dataset', action='auto_labeling', workspace_id=body['workspace_id'])
#         return response(status = 1, message = "auto_labeling_check success")

#     except:
#         traceback.print_exc()
#         return response(status = 0, message = "auto_labeling_check Error")


# # Datasets CRUD
# @ns.route('/datasets', methods=['GET', 'POST', 'PUT'])
# @ns.route('/datasets/<id_list>', methods=['DELETE'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class DatasetsWithAutolabeling(CustomResource):
#     @token_checker
#     @ns.expect(user_workspace_parser)
#     def get(self):
#         """
#         Dataset 목록 조회
#         ---
#         # 설명
#             workspace_id가 없으면 모든 워크스페이스의 데이터셋 목록 조회
#             page or size가 없는 경우 조건에 맞는 전체 목록 조회
#         """
#         args = user_workspace_parser.parse_args()
#         # workspace_id = args['workspace_id']
#         # page = args['page']
#         # size = args['size']
#         # search_value = args['search_value']
#         # search_key = args['search_key']
#         # if page is not None:
#         #     page = int(page)
#         # if size is not None:
#         #     size = int(size)
#         # res = get_datasets(search_key=search_key, search_value=search_value,
#         #                     workspace_id=workspace_id, page=page, size=size, headers_user=self.check_user())
#         res = Datasets.get._original(self)
#         res = json.loads(res.response[0].decode("utf-8").replace("'",'"'))
#         res = get_datasets_with_autolabeling(datasets_result=res["result"], jf_headers=self.get_jf_headers())
#         db.request_logging(self.check_user(), 'datasets', 'get', str(args), res['status'])
#         return self.send(res)


# # Dataset Files R
# @ns.route('/datasets/<dataset_id>/files', methods=['GET', 'POST', 'PUT'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class DatasetFilesWithAutolabeling(CustomResource):
#     @token_checker
#     @ns.expect(dataset_files_parser)
#     def get(self, dataset_id):
#         """
#         Dataset 파일 목록 조회
#         """
#         print("DatasetFiles/get")
#         # #res = get_dataset_dir(dataset_id)
#         # args = dataset_files_parser.parse_args()
#         # #dataset_id = args['dataset_id']
#         # search_path = args['search_path']
#         # search_page = int(args['search_page'])
#         # search_size = int(args['search_size'])
#         # search_type = args['search_type']
#         # search_key = args['search_key']
#         # search_value = args['search_value']
#         # if search_page < 1 :
#         #     search_page = 1
#         # if search_size < 1 :
#         #     search_size = 10
#         # res = get_dataset_files(dataset_id=dataset_id, search_path=search_path, search_page=search_page, search_size=search_size,
#         #                         search_type=search_type, search_key=search_key, search_value=search_value, headers_user=self.check_user())
#         res = DatasetFiles.get._original(self,dataset_id)
#         res = json.loads(res.response[0].decode("utf-8").replace("'",'"'))
#         res = get_dataset_with_autolabeling(dataset_id=dataset_id, dataset_result=res["result"], jf_headers=self.get_jf_headers())
#         db.request_logging(self.check_user(), 'datasets/'+str(dataset_id)+'/files', 'get', None, res['status'])
#         return self.send(res)

# @ns.route('/datasets/<dataset_id>/files/info', methods=['GET'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class DatasetInfoWithAutolabeling(CustomResource):
#     @token_checker
#     @ns.expect(dataset_files_info_parser)
#     def get(self, dataset_id):
#         """
#         Dataset 파일 정보 조회
#         """
#         print("DatasetInfo/get")
#         # args = dataset_files_info_parser.parse_args()
#         # search_path = args['search_path']
#         # res = get_dataset_info(dataset_id=dataset_id, search_path=search_path, headers_user=self.check_user())
#         res = DatasetInfo.get._original(self,dataset_id)
#         res = json.loads(res.response[0].decode("utf-8").replace("'",'"'))
#         res = get_dataset_info_with_autolabeling(dataset_info_result=res["result"], jf_headers=self.get_jf_headers())
#         db.request_logging(self.check_user(), 'datasets/'+str(dataset_id)+'/files/info', 'get', None, res['status'])
#         return self.send(res)

# @ns.route('/datasets/auto_labeling', methods=['PUT'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class Datasets_auto_labeling(CustomResource):
#     @token_checker
#     @ns.expect(auto_labeling_parser)
#     def put(self):
#         """
#         Auto_labeling 여부 수정
#         """
#         args = auto_labeling_parser.parse_args()
#         print('auto')
#         res = auto_labeling_update(args, headers_user=self.check_user())
#         return self.send(res)

# @ns.route("/user/change_password", methods=['POST'])
# @ns.response(200, 'Success')
# @ns.response(400, 'Validation Error')
# class JPUserPassword(CustomResource):
#     #@_token_checker
#     @ns.expect(jp_update_password_parser)
#     def post(self, *args, **kwargs):
#         args = jp_update_password_parser.parse_args()
#         username = args['username']
#         new_password = args['new_password']
#         status = False
#         try:
#             res = user_passwd_change(user_name=username,new_password=new_password, decrypted=True)
#             status = res
#         except:
#             print("Jonathan Platform /user/change_password Change Error")
#         toReturn = {"changed": status}
#         return self.send(toReturn)
