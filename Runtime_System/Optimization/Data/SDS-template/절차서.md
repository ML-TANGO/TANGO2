# SDS-VLM 동영상 데모 — 새 Jetson Orin 설치 안내

이 문서는 기존 Orin 에서 돌던 동영상 데모(`demo_video`)를 새 Jetson Orin 에 같은 상태로 설치하는 절차입니다.
위에서 아래로 따라 하면 됩니다.

---

## 1. 패키지 구성

| 파일 | 크기 | 내용 |
|---|---|---|
| `eva_demo_video_orin_20261027_src.tar.gz` | 약 100MB | 설치 스크립트, 데모 코드와 데이터, llama.cpp 소스, 이 문서 |
| `eva_demo_video_models_20261027.tar` | 약 10GB | 모델 2개와 체크섬 (GGUF 는 압축 효과가 작아 압축하지 않음) |
| `SHA256SUMS` | – | 위 두 파일의 체크섬 |

소스 묶음을 풀면 다음과 같습니다.

```
eva_demo_video_orin_20261027/
├── DEPLOY.md                         # 이 문서
├── setup_orin.sh                     # 설치 스크립트 (§4)
├── demo_video/                       # 데모 코드와 데이터
│   ├── server.py, precompute.py, run_orin.sh, prepare.py, README.md
│   ├── static/                       # 화면 (HTML/CSS/JS)
│   └── data/                         # 시나리오 5개: 영상, 모델 입력 이미지, 프레임별 AIS, 사전 추론 결과
└── llama.cpp/
    ├── llama.cpp-c479922ac-eva.tar.gz  # llama.cpp 커밋 c479922ac 소스 (CLS 순서 패치 적용됨)
    └── llava_cls_order.patch           # 적용한 패치 (한 줄)
```

모델 묶음을 풀면 다음과 같습니다.

```
eva_sds_ko_9k/
├── mmproj.gguf      # CLIP ViT-L/14-336 (23개 블록) + mlp2x_gelu 프로젝터, 1.25GB
├── llm-q8_0.gguf    # LoRA 를 병합한 Qwen3-8B, Q8_0, 8.7GB
└── SHA256SUMS
```

- 모델은 `clip_qwen3_proj_lora_marine_sds_ko_9k` 체크포인트를 `scripts/convert_to_gguf.py` 로 변환한 것입니다 (상위 README §11-2).
- `demo_video/data/*/results.json` 은 기존 Orin(Jetson AGX Orin 32GB)에서 미리 추론한 결과입니다. 그대로 쓰면 사전 추론을 다시 하지 않아도 됩니다.

---

## 2. 대상 장비 요구 사항

| 항목 | 요구 사항 | 확인한 환경 |
|---|---|---|
| 장비 | Jetson Orin 계열 (aarch64, GPU sm_87) | Jetson AGX Orin Developer Kit 32GB |
| JetPack / L4T | JetPack 6 (L4T R36), CUDA 12.x 런타임 | L4T R36.5.2 (JetPack 6.2), CUDA 12.6 |
| 메모리 | 실행 중 최대 약 17GB 사용 | 32GB (tegrastats 기준 최대 16.6GB) |
| 디스크 | 설치 위치에 13GB 이상 여유 (설치 후 약 12GB 사용) | eMMC 57GB |
| 네트워크 | 설치 중 apt 저장소와 통신 (nvcc 가 없을 때), 실행 중 청중 단말과 같은 망 | 유선 LAN |
| 전원 모드 | MAXN (측정값의 조건) | MAXN |
| 권한 | sudo 는 선택. 없으면 CUDA 컴파일러를 사용자 디렉토리에 설치 | sudo 없이 설치 확인 |

- Orin NX 16GB 와 Orin Nano 는 메모리가 부족해 이 Q8_0 모델을 그대로 실행할 수 없습니다. 이 패키지는 AGX Orin 32GB 이상을 전제로 합니다.
- 다른 JetPack 버전은 CUDA 패키지 이름(`cuda-nvcc-12-6` 등)이 달라질 수 있습니다. 설치 스크립트는 `/usr/local/cuda-12.*` 의 버전을 읽어 패키지 이름을 정합니다.

---

## 3. 사전 준비 (새 Orin)

1. JetPack 6 을 설치하고 네트워크를 연결합니다.

2. 필수 패키지를 확인합니다. 없으면 설치합니다 (sudo 필요).

   ```bash
   sudo apt update
   sudo apt install -y git cmake build-essential curl python3
   ```

3. 전원 모드를 MAXN 으로 둡니다. 현재 모드는 다음으로 확인합니다.

   ```bash
   nvpmodel -q          # "NV Power Mode: MAXN" 이면 됩니다
   ```

4. (선택) sudo 를 쓸 수 있으면 CUDA 컴파일러를 미리 설치합니다. 설치하지 않으면 §4 의 스크립트가 사용자 디렉토리에 풀어 씁니다.

   ```bash
   sudo apt install -y cuda-nvcc-12-6 libcublas-dev-12-6 cuda-cudart-dev-12-6
   ```

5. 데모 웹 포트(기본 8000)를 청중 단말이 접근할 수 있게 방화벽과 망 구성을 확인합니다.

---

## 4. 설치

### 4-1. 패키지 복사와 확인

개발 서버(또는 패키지를 가진 PC)에서 새 Orin 으로 세 파일을 복사합니다.

```bash
scp eva_demo_video_orin_20261027_src.tar.gz eva_demo_video_models_20261027.tar SHA256SUMS <사용자>@<새 Orin 주소>:~/
```

새 Orin 에서 체크섬을 확인하고 소스 묶음을 풉니다.

```bash
cd ~
sha256sum -c SHA256SUMS
tar -xzf eva_demo_video_orin_20261027_src.tar.gz
```

### 4-2. 설치 스크립트 실행

```bash
cd ~/eva_demo_video_orin_20261027
MODELS_TAR=~/eva_demo_video_models_20261027.tar ./setup_orin.sh
```

스크립트는 다섯 단계를 차례로 수행하고, 단계마다 결과를 검사합니다. 실패하면 이유를 출력하고 멈추며, 원인을 고친 뒤 같은 명령으로 다시 실행하면 끝난 단계는 확인만 하고 넘어갑니다.

| 단계 | 하는 일 | 결과 위치 |
|---|---|---|
| 1. 장비 확인 | aarch64, L4T 버전, 필수 명령, 디스크 여유, 메모리 | – |
| 2. CUDA 컴파일러 | 시스템 nvcc 가 있으면 사용. 없으면 sudo 로 apt 설치, sudo 가 없으면 apt 패키지를 내려받아 사용자 디렉토리에 풀고 시스템 런타임 라이브러리를 링크 | `~/cuda-local` (sudo 없을 때) |
| 3. llama.cpp 빌드 | 패치된 소스를 풀고 CLS 순서 패치를 확인한 뒤 CUDA(sm_87)로 `llama-server` 빌드. GPU 인식(`CUDA0`) 확인 | `~/llama.cpp-eva` |
| 4. 모델 설치 | 모델 묶음을 풀고 SHA-256 확인 | `~/models/eva_sds_ko_9k` |
| 5. 데모 설치 | 코드와 데이터 복사, 시나리오 목록 확인 | `~/demo_video` |

| 환경 변수 | 기본값 | 설명 |
|---|---|---|
| `PREFIX` | `$HOME` | 설치 위치 |
| `MODELS_TAR` | (없음) | 모델 묶음 경로. 모델이 이미 설치되어 있으면 생략 가능 |
| `JOBS` | 6 | 빌드 병렬 수 |

- 빌드가 가장 오래 걸립니다. 기존 Orin(AGX Orin 32GB, `JOBS=6`)에서 3단계는 약 16분 걸렸습니다. 빌드 로그는 `~/llama.cpp-eva/build-cuda.log` 에 남습니다.
- 설치가 끝나면 모델 묶음(`~/eva_demo_video_models_20261027.tar`)은 지워도 됩니다.

정상 종료 시 마지막 출력:

```
== 설치 완료. 실행:
   cd /home/<사용자>/demo_video && ./run_orin.sh
   브라우저: http://<이 장비의 주소>:8000/
```

---

## 5. 실행과 확인

```bash
cd ~/demo_video
./run_orin.sh
```

- llama-server(127.0.0.1:8080)가 없으면 먼저 띄우고, 모델 적재가 끝나면 데모 웹 서버(0.0.0.0:8000)를 실행합니다. 모델 적재에 약 40초 걸립니다.
- 장비의 주소 후보가 모두 출력됩니다. docker 나 calico 같은 내부 가상망 주소는 외부에서 접속할 수 없으므로, 청중과 같은 망의 주소를 씁니다.
- 로그는 `~/demo_video/logs/` 에 남습니다.

브라우저로 접속해 다음을 확인합니다.

| 확인 항목 | 기대 결과 |
|---|---|
| 오른쪽 위 상태 | `Jetson AGX Orin 32GB · 모델 준비됨` (초록 점) |
| 시나리오 탭 | 추월, 마주침 A, 횡단 · 충돌 코스, 추월 · 충돌 코스, 마주침 B |
| 재생 (미리 계산된 결과) | 영상 위에 ‘상황’ / ‘조언’ 이 표시되고, 결과가 바뀔 때 중앙 하단에 행동 권고 문구가 깜빡임 |
| 현재 장면 분석하기 | 영상 위에 결과가 스트리밍되고, 첫 글자까지 약 1~2초, 생성 약 18 토큰/초 |
| 실시간 추론 모드 | 재생을 멈추지 않고 장면을 하나씩 추론, 추론 시간과 영상이 앞서 나간 시간 표시 |

상태 표시의 장비 이름은 사전 추론 결과(`results.json`)에 기록된 값입니다. 새 장비 이름으로 바꾸려면 §7-2 를 따릅니다.

---

## 6. 종료와 재시작

종료:

```bash
kill $(pgrep -x llama-server) $(pgrep -f "python3 .*demo_video/server.py")
```

재부팅 뒤에는 §5 의 `./run_orin.sh` 를 다시 실행합니다. 자동 시작은 설정하지 않았습니다.

---

## 7. 참고

### 7-1. 실측값 (기존 Orin, AGX Orin 32GB, MAXN, Q8_0)

| 항목 | 값 |
|---|---|
| 프롬프트 처리 (이미지 576 토큰 포함 약 800~900 토큰) | 평균 1.08 s |
| 생성 속도 | 17.1~18.7 토큰/초 |
| 장면 1건 전체 시간 (평균 약 290 토큰 생성) | 13.2~18.6 s |
| 메모리 사용 최대 (tegrastats RAM) | 16.6 GB |
| 설치 스크립트 3단계 (llama.cpp CUDA 빌드, `JOBS=6`) | 약 16분 |

### 7-2. 사전 추론을 새 장비에서 다시 하기

사전 추론 결과는 모델이 같으면 다시 계산하지 않고 재사용합니다. 새 장비에서 다시 계산하려면 기존 결과를 옮겨 두고 실행합니다. 75장면에 약 20분 걸립니다.

```bash
cd ~/demo_video
mkdir -p results_backup && for d in data/*/; do mv "$d/results.json" "results_backup/$(basename "$d").json"; done
./run_orin.sh            # llama-server 를 띄운 뒤 Ctrl+C 로 웹 서버만 멈춤
python3 precompute.py --llm http://127.0.0.1:8080 --device "Jetson AGX Orin 64GB"   # 장비 이름을 기록
./run_orin.sh
```

### 7-3. 문제 해결

| 증상 | 확인할 것 |
|---|---|
| 2단계에서 `apt-get download 실패` | 장비의 apt 저장소(`repo.download.nvidia.com/jetson`)와 네트워크. 또는 §3-4 처럼 sudo 로 설치 |
| 3단계에서 `빌드 실패` | `~/llama.cpp-eva/build-cuda.log` 끝부분. `CUDA Toolkit not found` 면 2단계를 다시 실행 |
| 3단계에서 GPU 를 찾지 못함 | `nvidia-smi` 가 없는 것은 정상(Jetson). `~/llama.cpp-eva/build-cuda/bin/llama-server --list-devices` 출력 확인 |
| 4단계에서 체크섬 불일치 | 모델 묶음을 다시 복사하고 §4-1 의 `sha256sum -c` 로 확인 |
| 브라우저에서 접속 안 됨 | 장비 주소(내부 가상망 주소가 아닌지), 포트 8000 방화벽, `~/demo_video/logs/` |
| 상태가 `모델 서버에 연결되지 않음` | `~/demo_video/logs/llama-server.log`, `curl http://127.0.0.1:8080/health` |
| ‘다른 분석이 진행 중’ 안내 | 모델은 한 번에 한 요청만 처리합니다. 다른 화면이 실시간 추론 모드로 쓰고 있지 않은지 확인 |

### 7-4. 스크립트 없이 설치할 때

스크립트가 하는 일은 상위 README 의 §11-2 Step 0 (llama.cpp 패치), §12 (Jetson 빌드), §14 (동영상 데모)와 같습니다.
수동으로 설치할 때는 `llama.cpp/llava_cls_order.patch` 를 llama.cpp 커밋 `c479922ac` 에 적용한 뒤 빌드합니다.
