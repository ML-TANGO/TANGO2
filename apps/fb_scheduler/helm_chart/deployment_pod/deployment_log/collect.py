from fastapi import Request
from functools import wraps
import json
import os

os.makedirs("/collect", exist_ok=True)

# TODO 경로, 파일명 어떻게 할것인지
# API 파일에서 import
# from collect import collect_request_and_response
# @collect_request_and_response

# TEXT 저장 함수
def save_data(data_type, data):
    with open(f"/collect/{data_type}_data.json", "a") as f:
        f.write(json.dumps(data) + "\n")

# 이미지 저장 함수
def save_image_to_file(data_type, image_file):
    with open(f"/collect/{data_type}_image.png", "wb") as f:
        f.write(image_file)

# 데코레이터 정의
def collect_request_and_response(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # `Request` 객체 추출
        request: Request = kwargs.get("request")
        if not request:
            return await func(*args, **kwargs)

        # Content-Type에 따라 처리 분기
        content_type = request.headers.get("content-type", "")

        # INPUT
        if "application/json" in content_type:
            # JSON 요청 처리 (TEXT)
            input_data = await request.json()
            save_data("input", input_data)
        elif "multipart/form-data" in content_type:
            # Form 데이터 요청 처리 (이미지)
            form_data = await request.form()
            input_data = {}
            for key, value in form_data.items():
                if hasattr(value, "read"):  # 파일인 경우
                    image_file = await value.read() # type: bytes
                    print(type(image_file))
                    save_image_to_file("output", image_file)
        else:
            save_data("input", input_data)

        # 실제 API 함수 실행
        response = await func(*args, **kwargs)

        # OUTPUT
        for key, val in response.items(): # 딕셔너리 안에 여러개 들어올수 있는데, 이떄 어떻게 처리할지...
            if key == "text":
                save_data("output", val)
            elif key == "image":
                # 여기에는 여러개 들어올수는 없음
                for v in val:
                    image_list = list(v.values())
                    if len(image_list) > 0:
                        image_file = image_list[0].encode()  # type: str
                        print(type(image_file))
                        save_image_to_file("output", image_file)
            else:
                save_data("output", val)
        return response
        
    return wrapper