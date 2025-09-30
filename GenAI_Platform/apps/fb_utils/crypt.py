import base64
import hashlib
from Crypto import Random
from Crypto.Cipher import AES
# pip install pycrypto

FRONT_KEY = 'robertirenelico!robertirenelico!'
FRONT_IV = b'robertirenelico!'

SESSION_KEY = "jfloginsessionjfjfloginsessionjf"
SESSION_IV = b"jfloginsessionjf"

class AESCipher():

    def __init__(self, key, iv, en_decode_type="base64"):
        self.bs = 16
        self.key = key
        self.iv = iv
        self.en_decode_type = en_decode_type # base64(password), hex(token)

    @staticmethod
    def str_to_bytes(data):
        u_type = type(b''.decode('utf8'))
        if isinstance(data, u_type):
            return data.encode('utf8')
        return data

    def _pad(self, s):
        return s + (self.bs - len(s) % self.bs) * AESCipher.str_to_bytes(chr(self.bs - len(s) % self.bs))

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]

    """
    # MSA 수정
    cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
    => cipher = AES.new(self.key.encode(), AES.MODE_CBC, self.iv)
    """
    def _encrypt_base64(self, raw):
        raw = self._pad(AESCipher.str_to_bytes(raw))
        cipher = AES.new(self.key.encode(), AES.MODE_CBC, self.iv)
        return base64.b64encode(cipher.encrypt(raw)).decode('utf-8')

    def _encrypt_hex(self, raw):
        raw = self._pad(AESCipher.str_to_bytes(raw))
        cipher = AES.new(self.key.encode(), AES.MODE_CBC, self.iv)
        return cipher.encrypt(raw).hex()

    def _decrypt_base64(self, enc):
        enc = base64.b64decode(enc)
        cipher = AES.new(self.key.encode(), AES.MODE_CBC, self.iv)
        dec = cipher.decrypt(enc)
        return dec[:-dec[-1]].decode('utf-8')

    def _decrypt_hex(self, enc):
        enc = bytes.fromhex(enc)
        cipher = AES.new(self.key.encode(), AES.MODE_CBC, self.iv)
        dec = cipher.decrypt(enc)
        return dec[:-dec[-1]].decode('utf-8')

    def encrypt(self, raw):
        if self.en_decode_type == "base64":
            return self._encrypt_base64(raw)
        elif self.en_decode_type == "hex":
            return self._encrypt_hex(raw)

    def decrypt(self, enc):
        if self.en_decode_type == "base64":
            return self._decrypt_base64(enc)
        elif self.en_decode_type == "hex":
            return self._decrypt_hex(enc)

front_cipher = AESCipher(FRONT_KEY, FRONT_IV, "base64")
session_cipher = AESCipher(SESSION_KEY, SESSION_IV, "hex")

import time
def gen_user_token(user_name, gen_count):
    login_time = time.time()
    raw = "{}/{}/{}".format(user_name, login_time, gen_count)
    token = session_cipher.encrypt(raw)
    return token

def decrypt_user_token(user_token):
    token_user, start_timestamp, gen_count = session_cipher.decrypt(user_token).split("/")
    return token_user, float(start_timestamp), int(gen_count)

"""Creates a key pair then register it as a login credential for ssh

:param userName: UNIX username
:type userName: str
:returns: loc of a private key created
:rtype: str
"""
import os
def createAKeyForSSH(user_name):
    # cmd = '''
    # mkdir /home/''' + userName + '''
    # chown '''+ userName + ''': /home/''' + userName + '''
    # chmod 700''' + ''': /home/''' + userName + '''
    # su - ''' + userName + ''' sh -c "
    # mkdir .ssh
    # chmod 700 .ssh
    # cd .ssh
    # echo y | ssh-keygen -f ''' + userName +''' -t rsa -N ''
    # chmod 600 '/home/''' + userName + '''/.ssh/'*
    # cp -f ''' +  userName + '''.pub authorized_keys "
    # '''

    cmd = """
        mkdir /home/{user_name}
        chown {user_name} /home/{user_name}
        chmod 700 /home/{user_name}
        su - {user_name} sh -c "
        mkdir .ssh
        chmod 700 .ssh
        cd .ssh
        echo y | ssh-keygen -f {user_name} -t rsa -N ''
        chmod 600 '/home/{user_name}/.ssh/'*
        cp -f {user_name}.pub authorized_keys "
    """.format(user_name=user_name)

    os.system(cmd)
    return '/home/' + user_name + '/.ssh/' + user_name # loc of a private key