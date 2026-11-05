# 플랫폼 소유 빌트인 전처리 — 데이터 포맷 변환 잡 이미지 (v0.4 3.x / C트랙 #7).
# fb_preprocessing 빌트인(FORMAT_CONVERT) 잡이 이 이미지에서
#   python3 -u /built_in/format_convert.py <params> --input_data=/dataset/<path>
# 를 실행한다. 데이터셋은 /dataset 에 마운트, 출력은 원본 옆 파일(sidecar).
# CPU-only(GPU 불요). marker/augment 빌트인 이미지와 동일하게 /built_in 에 스크립트 baked.
FROM python:3.11-slim

# CSV/Parquet 파싱 — pandas + pyarrow(Parquet).
RUN python3 -m pip install --no-cache-dir pandas==2.2.2 pyarrow==16.1.0

# 빌트인 스크립트 = /built_in/{PREPROCESSING_TFS_SCRIPT[tf]} (스케줄러가 이 경로로 실행).
COPY format_convert.py /built_in/format_convert.py

WORKDIR /built_in
