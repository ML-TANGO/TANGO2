import base64
import json

# 레지스트리 인증 정보 설정
auth_config = {
    "auths": {
        "IP:PORT": {
            "username": "tango",
            "password": "tango",
            "auth": base64.b64encode(b"tango:tango").decode()
        }
    }
}

# JSON으로 변환
docker_config_json = json.dumps(auth_config)

# Base64로 인코딩
encoded_docker_config = base64.b64encode(docker_config_json.encode()).decode()

print(encoded_docker_config)