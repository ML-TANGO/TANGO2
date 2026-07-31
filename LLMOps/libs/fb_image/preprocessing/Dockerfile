# 빌트인 전처리 공용 실행 이미지 (lean 베이스).
#
# 목적: fb_preprocessing 빌트인(TFS) 잡 pod 의 기본 실행 이미지.
#   docker.io/acrylaaai 게시 → 신규 클러스터가 pull 가능(사내 jfb/ 레지스트리 미가용 대응).
#
# 실행 규약: 스케줄러가 이 이미지 pod 안에서 `python3 -u /built_in/<script> <params>` 실행.
#   빌트인 스크립트(format_convert / preprocessing_augment / preprocess_marker_json /
#   sds_llava_convert)는 NFS bin PVC(subPath=preprocessing)가 /built_in 에 RO 마운트된다.
#   → 이미지는 스크립트를 bake 하지 않고 "베이스(런타임 의존성)"만 제공한다.
#
# 활성 빌트인(4종)의 의존성:
#   - FORMAT_CONVERT   (데이터 포맷 변환 CSV/TXT/Parquet→JSON/JSONL) : pandas + pyarrow(Parquet)
#   - MARKER_ANALYSIS  (preprocess_marker_json)                     : pandas
#   - IMAGE_AUGMENT    (preprocessing_augment)                      : Pillow (+ numpy)
#   - SDS_LLAVA_CONVERT(sds_llava_convert)                          : 표준 라이브러리
FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1

# 활성 빌트인 4종 실행에 필요한 최소 의존성(버전 고정). 전부 manylinux wheel → 빌드 툴 불요.
# build context = 이 디렉토리(libs/fb_image/preprocessing). requirements.txt 가 단일 소스.
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

WORKDIR /built_in
CMD ["/bin/bash"]
