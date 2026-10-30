#!/usr/bin/env bash
# setup_orin.sh — 새 Jetson Orin 에 SDS-VLM 동영상 데모를 설치한다.
#
#   MODELS_TAR=/path/to/eva_demo_video_models_<날짜>.tar ./setup_orin.sh
#
# 하는 일 (단계마다 결과를 검사하고, 실패하면 이유를 출력하고 멈춘다)
#   1. 장비 확인          aarch64, L4T, 필수 명령, 디스크 여유
#   2. CUDA 컴파일러      nvcc 가 없으면 sudo apt 로 설치하거나, sudo 가 없으면 사용자 디렉토리에 푼다
#   3. llama.cpp 빌드     CLS 순서 패치를 적용한 소스를 CUDA 로 빌드 → $PREFIX/llama.cpp-eva
#   4. 모델 설치          GGUF 2개를 풀고 SHA-256 확인 → $PREFIX/models/eva_sds_ko_9k
#   5. 데모 설치          코드와 데이터를 복사 → $PREFIX/demo_video
#
# 환경 변수
#   PREFIX      설치 위치 (기본 $HOME)
#   MODELS_TAR  모델 묶음 tar 경로. 모델이 이미 설치되어 있으면 생략 가능
#   JOBS        빌드 병렬 수 (기본 6)
#
# 다시 실행해도 된다. 이미 끝난 단계는 확인만 하고 넘어간다.
set -euo pipefail

PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-$HOME}"
MODELS_TAR="${MODELS_TAR:-}"
JOBS="${JOBS:-6}"
LLAMA_COMMIT="c479922ac"

LLAMA_DIR="$PREFIX/llama.cpp-eva"
MODEL_DIR="$PREFIX/models/eva_sds_ko_9k"
DEMO_DIR="$PREFIX/demo_video"
CUDA_LOCAL="$PREFIX/cuda-local"

step() { echo; echo "== [$1] $2"; }
ok()   { echo "   OK  $*"; }
die()  { echo "   [오류] $*" >&2; exit 1; }

mkdir -p "$PREFIX"

# ── 1. 장비 확인 ──────────────────────────────────────────────────────────────
step 1 "장비 확인"
[ "$(uname -m)" = "aarch64" ] || die "aarch64 장비가 아닙니다 ($(uname -m))"
if [ -r /etc/nv_tegra_release ]; then
    L4T=$(head -1 /etc/nv_tegra_release | sed -E 's/# (R[0-9]+) \(release\), REVISION: ([0-9.]+).*/\1.\2/')
    ok "L4T $L4T"
    [[ "$L4T" == R36* ]] || echo "   [주의] 확인한 버전은 L4T R36.5.2 (JetPack 6.2) 입니다. 다른 버전은 CUDA 패키지 이름이 다를 수 있습니다."
else
    die "/etc/nv_tegra_release 가 없습니다. Jetson 장비가 맞는지 확인하십시오."
fi
for c in git cmake make gcc g++ curl python3 tar sha256sum; do
    command -v "$c" >/dev/null || die "'$c' 가 없습니다. sudo apt install git cmake build-essential curl python3 로 설치하십시오."
done
python3 -c 'import sys; assert sys.version_info >= (3, 8)' || die "Python 3.8 이상이 필요합니다"
ok "필수 명령 (git cmake make gcc g++ curl python3 tar sha256sum)"
FREE_GB=$(df -BG --output=avail "$PREFIX" | tail -1 | tr -dc 0-9)
NEED_GB=13
[ -d "$MODEL_DIR" ] && NEED_GB=3
[ "$FREE_GB" -ge "$NEED_GB" ] || die "$PREFIX 의 여유 공간이 ${FREE_GB}GB 입니다. ${NEED_GB}GB 이상 필요합니다."
ok "디스크 여유 ${FREE_GB}GB ($PREFIX)"
MEM_GB=$(free -g | awk '/^Mem:/{print $2}')
[ "$MEM_GB" -ge 20 ] || echo "   [주의] 메모리가 ${MEM_GB}GB 입니다. Q8_0 모델 실행에 약 17GB 가 필요합니다 (AGX Orin 32GB 에서 확인)."

# ── 2. CUDA 컴파일러 ──────────────────────────────────────────────────────────
step 2 "CUDA 컴파일러"
CUDA_SYS=$(ls -d /usr/local/cuda-12.* 2>/dev/null | sort -V | tail -1 || true)
[ -n "$CUDA_SYS" ] || die "/usr/local/cuda-12.* 가 없습니다. JetPack 의 CUDA 런타임이 설치되어 있어야 합니다."
CUDA_VER=${CUDA_SYS##*/cuda-}          # 예: 12.6
PKG_VER=${CUDA_VER/./-}                # 예: 12-6
ok "CUDA 런타임 $CUDA_VER ($CUDA_SYS)"

# 사용자 디렉토리에 푼 개발 패키지에는 런타임 라이브러리가 없으므로 시스템 것을 링크한다.
# 중간에 끊긴 설치도 다시 실행하면 채워지도록, 사용자 디렉토리 CUDA 를 쓸 때는 매번 실행한다.
# [ -e ] 는 깨진 링크를 없다고 보므로 libcudart.so 처럼 대상이 빠진 링크는 시스템 것으로 덮는다.
link_runtime() {
    local lib="$1/targets/aarch64-linux/lib" f b
    for f in "$CUDA_SYS"/targets/aarch64-linux/lib/*; do
        b=$(basename "$f")
        [ -e "$lib/$b" ] || ln -sf "$f" "$lib/$b"
    done
    [ -e "$lib/libcudart.so" ] || die "$lib/libcudart.so 를 만들지 못했습니다"
}

if [ -x "$CUDA_SYS/bin/nvcc" ]; then
    CUDA_HOME="$CUDA_SYS"
    ok "시스템 nvcc 사용 ($CUDA_HOME/bin/nvcc)"
elif [ -x "$CUDA_LOCAL/root/usr/local/cuda-$CUDA_VER/bin/nvcc" ]; then
    CUDA_HOME="$CUDA_LOCAL/root/usr/local/cuda-$CUDA_VER"
    link_runtime "$CUDA_HOME"
    ok "사용자 디렉토리 nvcc 사용 ($CUDA_HOME/bin/nvcc)"
elif sudo -n true 2>/dev/null; then
    echo "   sudo 로 cuda-nvcc-$PKG_VER 를 설치합니다"
    sudo apt-get install -y "cuda-nvcc-$PKG_VER" "libcublas-dev-$PKG_VER" "cuda-cudart-dev-$PKG_VER"
    CUDA_HOME="$CUDA_SYS"
    [ -x "$CUDA_HOME/bin/nvcc" ] || die "apt 설치 후에도 nvcc 가 없습니다"
    ok "apt 로 설치"
else
    # sudo 없이: apt 저장소에서 패키지만 내려받아 사용자 디렉토리에 푼다
    echo "   sudo 를 쓸 수 없어 $CUDA_LOCAL 에 풉니다"
    mkdir -p "$CUDA_LOCAL/debs"
    ( cd "$CUDA_LOCAL/debs" && apt-get download \
        "cuda-nvcc-$PKG_VER" "cuda-crt-$PKG_VER" "cuda-nvvm-$PKG_VER" "libcublas-dev-$PKG_VER" \
        "cuda-cccl-$PKG_VER" "cuda-driver-dev-$PKG_VER" "cuda-cudart-dev-$PKG_VER" ) \
        || die "apt-get download 실패. 장비의 apt 저장소(repo.download.nvidia.com/jetson)와 네트워크를 확인하십시오."
    for d in "$CUDA_LOCAL"/debs/*.deb; do dpkg -x "$d" "$CUDA_LOCAL/root"; done
    CUDA_HOME="$CUDA_LOCAL/root/usr/local/cuda-$CUDA_VER"
    link_runtime "$CUDA_HOME"
    [ -x "$CUDA_HOME/bin/nvcc" ] || die "nvcc 를 풀지 못했습니다"
    ok "사용자 디렉토리에 설치 ($CUDA_HOME)"
fi
"$CUDA_HOME/bin/nvcc" --version | tail -1 | sed 's/^/   /'

# ── 3. llama.cpp 빌드 ─────────────────────────────────────────────────────────
step 3 "llama.cpp (커밋 $LLAMA_COMMIT + CLS 순서 패치) 빌드"
if [ ! -d "$LLAMA_DIR" ]; then
    mkdir -p "$LLAMA_DIR"
    tar -xzf "$PKG/llama.cpp/llama.cpp-$LLAMA_COMMIT-eva.tar.gz" -C "$LLAMA_DIR" --strip-components=1
    ok "소스 풀기 → $LLAMA_DIR"
fi
grep -q "inp = ggml_concat(ctx0, model.class_embedding, inp, 1);" "$LLAMA_DIR/tools/mtmd/models/llava.cpp" \
    || die "$LLAMA_DIR 에 CLS 순서 패치가 없습니다. llama.cpp/llava_cls_order.patch 를 적용하십시오."
ok "CLS 순서 패치 확인 (tools/mtmd/models/llava.cpp)"
BIN="$LLAMA_DIR/build-cuda/bin/llama-server"
if [ ! -x "$BIN" ]; then
    echo "   빌드 시작 (AGX Orin 32GB, -j6 기준 약 16분). 로그: $LLAMA_DIR/build-cuda.log"
    ( cd "$LLAMA_DIR" && \
      PATH="$CUDA_HOME/bin:$PATH" cmake -B build-cuda -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87 \
          -DCMAKE_CUDA_COMPILER="$CUDA_HOME/bin/nvcc" -DCUDAToolkit_ROOT="$CUDA_HOME" \
          -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF && \
      cmake --build build-cuda -j"$JOBS" --target llama-server ) > "$LLAMA_DIR/build-cuda.log" 2>&1 \
        || die "빌드 실패. $LLAMA_DIR/build-cuda.log 의 끝부분을 확인하십시오."
fi
"$BIN" --list-devices 2>&1 | grep -q "CUDA0" || die "llama-server 가 GPU 를 찾지 못합니다: $("$BIN" --list-devices 2>&1 | tail -2)"
ok "$("$BIN" --list-devices 2>&1 | grep CUDA0 | sed 's/^ *//')"

# ── 4. 모델 설치 ──────────────────────────────────────────────────────────────
step 4 "모델 설치"
if [ ! -f "$MODEL_DIR/SHA256SUMS" ]; then
    [ -n "$MODELS_TAR" ] || die "모델이 없습니다. MODELS_TAR=<eva_demo_video_models_*.tar 경로> 를 지정하십시오."
    [ -f "$MODELS_TAR" ] || die "MODELS_TAR 파일이 없습니다: $MODELS_TAR"
    mkdir -p "$PREFIX/models"
    echo "   풀기: $MODELS_TAR"
    tar -xf "$MODELS_TAR" -C "$PREFIX/models"
fi
( cd "$MODEL_DIR" && sha256sum -c --quiet SHA256SUMS ) || die "모델 체크섬 불일치 ($MODEL_DIR). 파일을 다시 복사하십시오."
ok "SHA-256 확인: $(cd "$MODEL_DIR" && awk '{print $2}' SHA256SUMS | tr '\n' ' ')"

# ── 5. 데모 설치 ──────────────────────────────────────────────────────────────
step 5 "데모 설치"
mkdir -p "$DEMO_DIR"
cp -a "$PKG/demo_video/." "$DEMO_DIR/"
python3 -c "import json,sys; d=json.load(open('$DEMO_DIR/data/scenarios.json')); print('   OK  시나리오', len(d['scenarios']), '개:', ', '.join(s['title'] for s in d['scenarios']))"
ok "$DEMO_DIR"

echo
echo "== 설치 완료. 실행:"
if [ "$PREFIX" = "$HOME" ]; then
    echo "   cd $DEMO_DIR && ./run_orin.sh"
else
    echo "   cd $DEMO_DIR && LLAMA_BIN=$BIN MODEL_DIR=$MODEL_DIR ./run_orin.sh"
fi
echo "   브라우저: http://<이 장비의 주소>:8000/"
