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
#
# 데이터 파이프라인 노드도 이 베이스에서 실행된다. 노드마다 이미지를 만들지 않고
# 스크립트만 NFS 로 주입하므로, 노드가 늘어도 이 이미지는 그대로다.
#   범용    : dp_prep / dp_filter / dp_generate / dp_judge / dp_assemble
#   해양 SDS: dp_sds_video / dp_sds_ais / dp_sds_join
# 추가 의존성 = imagehash(pHash 중복제거) + pymupdf(PDF 페이지화) + av(영상 프레임 디코딩).
# 생성·심사 노드는 모델 서빙을 HTTP 로 부르므로 torch 는 여기 없다.
FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1
ENV DEBIAN_FRONTEND=noninteractive

# 잡 기동 시 /support/check_package_installed.sh 가 확인하는 필수 패키지를 미리 넣는다.
#
# 왜 이미지에 넣나: 그 스크립트는 **모든 잡이 기동할 때마다** 실행되고, 이 베이스는
# python:3.11-slim 이라 9개가 전부 없었다. 그래서 잡마다 apt 설치가 돌아 컨테이너 실행
# 시간의 대부분을 먹었다(실측: 전처리 잡 114초 중 약 100초, 실제 계산은 수 초).
# 노드를 잘게 쪼갤수록 이 고정비가 곱해지므로 — 파이프라인 구조를 지키려면 여기서 없애야 한다.
# 목록은 libs/fb_bin/support/check_package_installed.sh 와 같아야 한다(하나라도 빠지면
# 그 스크립트가 apt 를 다시 탄다).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        sudo openssh-client openssh-server net-tools iproute2 \
        python3-pip curl git wget \
 && rm -rf /var/lib/apt/lists/*

# 활성 빌트인 4종 실행에 필요한 최소 의존성(버전 고정). 전부 manylinux wheel → 빌드 툴 불요.
# build context = 이 디렉토리(libs/fb_image/preprocessing). requirements.txt 가 단일 소스.
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

WORKDIR /built_in
CMD ["/bin/bash"]
