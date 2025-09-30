import os
import sys
import utils.common as common
sys.path.insert(0, os.path.abspath('..'))
from utils.settings import *
from utils.TYPE import *


def write_user_info(base, target, users=[]):
    """
    Description: 선택한 유저 정보만 옮겨서 etc data 생성 (private training case)

    Args:
        base (str) : workspace etc 데이터 경로
        target (str) : training etc 데이터 경로
        users (list(str)) : 옮길 user name list

    Returns:
        None
    """
    # 특정 유저 COPY
    os.system('mkdir -p {target}'.format(target=target))
    for i, user in enumerate(users):
        if i == 0:
            os.system('cat {base}/passwd | grep ^{user}: >  {target}/passwd'.format(base=base, user=user, target=target))
            os.system('cat {base}/shadow | grep ^{user}: >  {target}/shadow'.format(base=base, user=user, target=target))
            os.system('cat {base}/gshadow | grep ^{user}: >  {target}/gshadow'.format(base=base, user=user, target=target))
            os.system('cat {base}/group | grep ^{user}: >  {target}/group'.format(base=base, user=user, target=target))
        else :
            os.system('cat {base}/passwd | grep ^{user}: >>  {target}/passwd'.format(base=base, user=user, target=target))
            os.system('cat {base}/shadow | grep ^{user}: >>  {target}/shadow'.format(base=base, user=user, target=target))
            os.system('cat {base}/gshadow | grep ^{user}: >>  {target}/gshadow'.format(base=base, user=user, target=target))
            os.system('cat {base}/group | grep ^{user}: >>  {target}/group'.format(base=base, user=user, target=target))

def apply_user_info(base, target):
    """
    Description: Workspace user etc 전부를 copy (public training case)

    Args:
        base (str) : workspace etc 데이터 경로
        target (str) : training etc 데이터 경로

    Returns:
        None
    """
    if os.system("ls {target}/  > /dev/null 2>&1".format(target=target)) != 0:
        os.system("mkdir {target}".format(target=target))

    os.system('cat {base}/passwd > {target}/passwd'.format(base=base, target=target))
    os.system('cat {base}/shadow > {target}/shadow'.format(base=base, target=target))
    os.system('cat {base}/gshadow > {target}/gshadow'.format(base=base, target=target))
    os.system('cat {base}/group > {target}/group'.format(base=base, target=target))


def update_user_etc(user_id=None):
    # import utils.db as db
    for workspace in db.get_user_workspace(user_id=user_id):
        update_workspace_users_etc(workspace_id=workspace["id"])

def update_workspace_users_etc(workspace_id=None, users=None, workspace_name=None, training_list=[]):
    # import utils.db as db
    if workspace_id is not None:
        users = [ user_info["user_name"] for user_info in db.get_workspace_users(workspace_id=workspace_id)]
        workspace_name = db.get_workspace(workspace_id=workspace_id)["workspace_name"]
        training_list = db.get_training_list(workspace_id=workspace_id)

    base = JF_ETC_DIR
    target = "{}/{}".format(JF_ETC_DIR, workspace_name)

    write_user_info(base=base, target=target, users=users)
    update_training_etc(workspace_name=workspace_name, training_list=training_list)

# def update_workspace_users_etc(users, workspace_name, training_list=[]):
# def update_workspace_users_etc(workspace_id=None, users=None, workspace_name=None, training_list=[]):
#     # import utils.db as db
#     if workspace_id is not None:
#         users = [ user_info["user_name"] for user_info in db.get_workspace_users(workspace_id=workspace_id)]
#         workspace_name = db.get_workspace(workspace_id=workspace_id)["workspace_name"]
#         training_list = db.get_training_list(workspace_id=workspace_id)

#     public_training_list = [ training for training in training_list if training["access"] == 1 ]
#     private_training_list = [ training for training in training_list if training["access"] == 0 ]
#     base = JF_ETC_DIR
#     target = "{}/{}".format(JF_ETC_DIR, workspace_name)

#     common.write_user_info(base=base, target=target, users=users)
#     update_public_training_etc(workspace_name, public_training_list=public_training_list)
#     update_private_training_etc(workspace_name, private_training_list=private_training_list)

# def update_public_training_etc(workspace_name, public_training_list=[]):
#     import utils.kube as kube
#     pod_list = kube.get_list_namespaced_pod()
#     for training_info in public_training_list:
#         training_name = training_info["training_name"]
#         base = "{etc_host}/{workspace_name}".format(etc_host=JF_ETC_DIR, workspace_name=workspace_name)
#         target_gpu = "{etc_host}/{workspace_name}/{training_name}".format(etc_host=JF_ETC_DIR, workspace_name=workspace_name, training_name=training_name)
#         target_cpu = "{etc_host}/{workspace_name}/{training_name}{jupyter}".format(etc_host=JF_ETC_DIR, workspace_name=workspace_name, training_name=training_name, jupyter=JUPYTER_FLAG)
#         if common.apply_user_info(base=base, target=target_gpu):
#             update_training_etc(training_tool_id=training_info["tool_jupyter_id"], owner_name=training_info["user_name"], tool_type=TOOL_TYPE[1], pod_list=pod_list)

#         if common.apply_user_info(base, target=target_cpu):
#             update_training_etc(training_tool_id=training_info["tool_editor_id"], owner_name=training_info["user_name"], tool_type=TOOL_TYPE[0],  pod_list=pod_list)

# def update_private_training_etc(workspace_name, private_training_list=[]):
#     import utils.kube as kube
#     # import utils.db as db
#     pod_list = kube.get_list_namespaced_pod()
#     for training_info in private_training_list:
#         training_name = training_info["training_name"]
#         users = [ user_info["user_name"] for user_info in db.get_training_users(training_id=training_info["id"])]

#         base = JF_ETC_DIR
#         target_gpu = "{etc_host}/{workspace_name}/{training_name}".format(etc_host=JF_ETC_DIR, workspace_name=workspace_name, training_name=training_name)
#         target_cpu = "{etc_host}/{workspace_name}/{training_name}{jupyter}".format(etc_host=JF_ETC_DIR, workspace_name=workspace_name, training_name=training_name, jupyter=JUPYTER_FLAG)

#         common.write_user_info(base=base, target=target_gpu, users=users)
#         update_training_etc(training_tool_id=training_info["tool_jupyter_id"], owner_name=training_info["user_name"], tool_type=TOOL_TYPE[1], pod_list=pod_list)
#         common.write_user_info(base=base, target=target_cpu, users=users)
#         update_training_etc(training_tool_id=training_info["tool_editor_id"], owner_name=training_info["user_name"], tool_type=TOOL_TYPE[0], pod_list=pod_list)

def update_training_etc(workspace_name, training_list=[]):
    import utils.kube as kube
    # import utils.db as db
    pod_list = kube.get_list_namespaced_pod()
    for training_info in training_list:
        training_name = training_info["training_name"]
        target_path = "{etc_host}/{workspace_name}/{training_name}".format(etc_host=JF_ETC_DIR, workspace_name=workspace_name, training_name=training_name)

        if training_info["access"] == 1:
            # WORKSPAE ETC ALL COPY
            base = "{etc_host}/{workspace_name}".format(etc_host=JF_ETC_DIR, workspace_name=workspace_name)
            apply_user_info(base=base, target=target_path)
        elif training_info["access"] == 0:
            # SELECTED USERS COPY
            users = [ user_info["user_name"] for user_info in db.get_training_users(training_id=training_info["id"])]

            base = JF_ETC_DIR
            target_path = "{etc_host}/{workspace_name}/{training_name}".format(etc_host=JF_ETC_DIR, workspace_name=workspace_name, training_name=training_name)

            write_user_info(base=base, target=target_path, users=users)

        update_training_etc_do(training_id=training_info["id"], pod_list=pod_list)

# import threading
# def update_training_etc(training_tool_id, owner_name, tool_type, pod_list=None):
#     import utils.kube as kube
#     def do(training_tool_id, owner_name, tool_type, pod_list=None):
#         jupyter = ""
#         if tool_type == TOOL_TYPE[0]:
#             jupyter = JUPYTER_FLAG

#         tool_status = kube.get_training_tool_pod_status(training_tool_id=training_tool_id, pod_list=pod_list)
#         if tool_status["status"] in ["running","installing"]:
#             pod_name = kube.find_kuber_item_name(item_list=pod_list, training_tool_id=training_tool_id)[0] # "{}-{}{}".format(workspace_name, training_name, JUPYTER_FLAG if editor == True else "")
#             print("UPDATE POD NAME ", pod_name)
#             update_cmd = "kubectl exec {} bash /bin/etc_sync.sh {} >> /dev/null &".format(pod_name, owner_name)
#             print("???", update_cmd)
#             update_result, *_ = common.launch_on_host(update_cmd, ignore_stderr=True)
#             print("UPDATE RESULT " , update_result)
#     do_thread = threading.Thread(target=do, args=(training_tool_id, owner_name, tool_type, pod_list))
#     do_thread.start()

import threading
def update_training_etc_do(training_id, pod_list=None):
    import utils.kube as kube
    def do(training_id, pod_list=None):
        pod_name_list = kube.find_kuber_item_name(item_list=pod_list, training_id=training_id)
        for pod_name in pod_name_list:
            print("UPDATE POD NAME ", pod_name)
            update_cmd = "kubectl exec {} bash /bin/etc_sync.sh >> /dev/null &".format(pod_name)
            print("???", update_cmd)
            update_result, *_ = common.launch_on_host(update_cmd, ignore_stderr=True)
            print("UPDATE RESULT " , update_result)
    do_thread = threading.Thread(target=do, args=(training_id, pod_list))
    do_thread.start()


def ssh_linux_user_sync_cmd():
    etc_sync_cmd = """
    #!/bin/bash
    #v0.5 - with shadow update
    OWNER=@JF_HOST
    DOCKER_ETC="/etc/"
    PROJECT_ETC=@JF_ETC_DIR_POD_PATH

    DOCKER_USERS=$(cat $DOCKER_ETC/passwd | grep @JF_HOME | grep -o ^[^:]*)
    echo DOCKER USERS : $DOCKER_USERS

    PROJECT_USERS=$(cat $PROJECT_ETC/passwd | grep home | grep -o ^[^:]*)
    echo PROJECT USERS : $PROJECT_USERS

    # USER_ADD
    for PROJECT_USER in $PROJECT_USERS; do
        if [[ $DOCKER_USERS =~ (^|[[:space:]])"$PROJECT_USER"($|[[:space:]]) ]] ; then
            #IN
            # echo $PROJECT_USER in DOCKER USERS
            PROJECT_USER_SHADOW=$(cat $PROJECT_ETC/shadow | grep -o ^$PROJECT_USER.*)
            sed -i 's#'$PROJECT_USER.*'#'$PROJECT_USER_SHADOW'#' $DOCKER_ETC/shadow
            continue
        else
            #NOT IN
            echo ADD_USER $PROJECT_USER
            cat $PROJECT_ETC/passwd | grep ^$PROJECT_USER: >> $DOCKER_ETC/passwd
            cat $PROJECT_ETC/gshadow | grep ^$PROJECT_USER: >> $DOCKER_ETC/gshadow
            cat $PROJECT_ETC/shadow | grep ^$PROJECT_USER: >> $DOCKER_ETC/shadow
            cat $PROJECT_ETC/group | grep ^$PROJECT_USER: >> $DOCKER_ETC/group

            usermod -g @JF_HOST $PROJECT_USER
            usermod -d @JF_HOME $PROJECT_USER
            usermod -aG sudo $PROJECT_USER
        fi
    done

    # DEL_USER
    for DOCKER_USER in $DOCKER_USERS; do
        if [[ $PROJECT_USERS =~ (^|[[:space:]])"$DOCKER_USER"($|[[:space:]]) ]] ; then
            #IN
            # echo $DOCKER_USER in PROJECT_USERS
            continue
        else
            #NOT IN
            echo DEL_USER $DOCKER_USER
            pkill -9 -u $DOCKER_USER
            deluser $DOCKER_USER
        fi
    done
    """
    etc_sync_cmd = etc_sync_cmd.replace("@JF_HOST", KUBE_ENV_JF_ITEM_OWNER_KEY_ENV)
    etc_sync_cmd = etc_sync_cmd.replace("@JF_HOME", KUBE_ENV_JF_HOME_KEY_ENV)
    etc_sync_cmd = etc_sync_cmd.replace("@JF_ETC_DIR_POD_PATH", JF_ETC_DIR_POD_PATH)
    return etc_sync_cmd