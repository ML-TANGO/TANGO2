# 베이스 이미지 설정: 파이썬 도커 이미지로 사용
FROM python:latest 

WORKDIR /app/

COPY ./requirements.txt /app/
RUN pip install -r requirements.txt

COPY ./main.py /app/

CMD uvicorn --host=0.0.0.0 --port 8000 main:app
