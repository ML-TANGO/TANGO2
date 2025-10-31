import spwd
import crypt
import traceback
import os
import subprocess

def linux_login_check(user_name, password):
    try:
        enc_pwd = spwd.getspnam(user_name)[1]
        if enc_pwd in ['NP', '!', '', None]:
            return False
        if enc_pwd in ['LK', '*']:
            return False
        if enc_pwd == '!!':
            return False
        if crypt.crypt(password, enc_pwd) == enc_pwd:
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc()
        pass
    return False


def linux_user_create(user_name: str, password: str, uid: int=None):
    """
        Description : Linux 계정 생성 함수

        Args :
            user_name (str) : 사용자 계정명
            password (str) : plain text의 password
            uid (int) : 생성할 계정의 uid. 미지정시 자동 생성
    """

    enc_pw = crypt.crypt(password, "$6$") # pw encrypt
    if uid is None:
        os.system("useradd -s /bin/bash -p '{enc_pw}' {user_name}".format(enc_pw=enc_pw, user_name=user_name)) # create user, pw
    else :
        os.system("useradd -s /bin/bash -p '{enc_pw}' -u {uid} {user_name}".format(enc_pw=enc_pw, uid=uid, user_name=user_name)) # create user, pw

def linux_user_uid_update(user_name: str, uid: int) -> None:
    """
    Description: Linux 계정 uid 변경 함수

    Args:
        user_name (str): 사용자 이름
        uid (int): 변경할 uid (ex. {user_name}의 uid를 {uid}로 변경)

    Raises: (List of possible errors)
        usermod: UID 'xxx' already exists
        usermod: no changes
        usermod: 'xxx' does not exist

    Returns:
        None:

    Examples:
        linux_user_uid_update("test_name", 1999)  # None
    """

    command = f"usermod -u {uid} {user_name}"  # {user_name}의 uid를 {uid}로 변경
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
    _, error = process.communicate()
    if error:
        # print(f"Error: user_name {user_name}, uid {uid}")
        raise Exception(f"Error: {error}")