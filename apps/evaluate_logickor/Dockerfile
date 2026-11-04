# LogicKor 채점 집계 컨테이너.
# score 단계만 하므로 모델을 로드하지 않는다 → torch/vllm/transformers 불필요 → slim 베이스.
# ⚠️ LogicKor 의 생성·심판 단계는 transformers 5.5.4 / vllm 핀이 필요해 이 이미지로는
#    돌릴 수 없다(별 이미지). 여기서 그 의존성을 끌어오면 슬림 베이스의 의미가 사라진다.
FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /srv/requirements.txt
# scoring.py 는 app.py 가 import 한다(집계 로직 본체) — 둘 다 필요.
COPY scoring.py /srv/scoring.py
COPY app.py /srv/app.py

ENV JF_PORT=8000

EXPOSE 8000
ENTRYPOINT []
CMD ["python3", "/srv/app.py"]
