# demo_video — 영상 기반 SDS-VLM 데모

SDS 시뮬레이터가 내보낸 영상을 재생하면서, 같은 장면을 비전-언어 모델(Vision-Language Model, VLM)이 어떻게 해석하는지 보여 주는 웹 데모입니다.
웹 서버와 모델 추론(llama.cpp `llama-server`)은 모두 Jetson AGX Orin 한 대에서 실행합니다.
청중은 같은 네트워크의 브라우저로 접속합니다.

---

## 1. 구성

```
demo_video/
├── prepare.py       # (개발 서버) 영상 세션 → 데모 데이터 묶음 생성
├── precompute.py    # (Orin) 2초 간격 장면을 미리 추론해 results.json 저장
├── server.py        # (Orin) 웹 서버. 화면·데이터 제공, 실시간 추론 중계
├── run_orin.sh      # (Orin) llama-server 와 server.py 를 함께 실행
├── static/          # 화면 (index.html, style.css, app.js). 외부 라이브러리 없음
└── data/            # prepare.py / precompute.py 산출물 (git 에서 제외)
```

| 구성 요소 | 실행 위치 | 의존성 |
|---|---|---|
| `prepare.py` | 개발 서버 | `ffmpeg`, Python 학습 환경(`transformers`, `pandas`, `Pillow`, `numpy`) |
| `precompute.py`, `server.py` | Jetson Orin | Python 3 표준 라이브러리만 사용 (Orin 기본 이미지에 pip 가 없음) |
| 모델 | Jetson Orin | CLS 순서 패치를 적용한 llama.cpp CUDA 빌드, GGUF 2개 (`llm-q8_0.gguf`, `mmproj.gguf`) |

확인한 환경은 Jetson AGX Orin 32GB, L4T R36.5.2 (JetPack 6.2), CUDA 12.6, 전원 모드 MAXN 입니다.

---

## 2. 입력 데이터

시뮬레이터 영상 세션 폴더(`session_manifest.json` 이 있는 곳)를 그대로 씁니다.
폴더 구조와 라벨 형식은 세션과 함께 배포되는 `video-dataset-and-viewer.md` 를 따릅니다.

- 시나리오마다 `video.mp4`(1920×1080, 30fps), `frame_timestamps.csv`, 프레임별 라벨 `samples/sample_NNNNNN.csv` 가 있습니다.
- 라벨 CSV 와 영상 프레임은 CSV 안의 `video_frame` 열로 연결합니다. 값은 디코더 프레임 번호(0부터)에 1을 더한 것입니다.
- `labelsBurnedIn: true` 인 영상에는 bbox 와 하단 수치표가 이미 그려져 있습니다. 데모 화면은 이 원본을 그대로 재생합니다.

---

## 3. 모델 입력 처리

학습에 쓴 이미지(AIVN-SDS)에는 라벨이 그려져 있지 않습니다.
그래서 모델에 넣기 전에 다음과 같이 처리합니다.

1. 영상 하단의 라벨 표를 잘라냅니다. 표는 선박 수에 따라 y=900~956 에서 시작하므로, 모든 시나리오에서 y<896 만 남깁니다 (1920×896, `prepare.py` 의 `CUT_Y`).
2. 그 이미지에 학습과 같은 `CLIPImageProcessor` 의 resize(짧은 변 336) + center crop(336×336) 을 적용합니다.
3. 결과를 336×336 PNG 로 저장합니다. llama.cpp 는 336×336 입력을 리사이즈 없이 쓰므로, 이 PNG 가 그대로 모델 입력이 됩니다.

- bbox 상자 선은 영상에 그려져 있어 모델 입력에도 남습니다.
- AIS 문장은 학습 데이터와 같은 `scripts/prepare_sds_dataset.py` 의 `format_ais(include_bbox=False)` 와 `PROMPT_KO` 로 만듭니다. 체크포인트 토크나이저의 chat template 까지 적용한 문자열을 저장합니다.
- 추론은 0.5초 간격 프레임(분석 격자, 시나리오당 60개)에서만 합니다.

---

## 4. 준비 (개발 서버)

```bash
cd Field_Test/SDS/VisionLanguageModel
python demo_video/prepare.py \
  --session /home/ywlee/SSD/data/tango_conf_demo/video_data_guide/2026-09-30_13-05-39 \
  --ckpt    /home/ywlee/SSD/checkpoints/tango2-sds-vlm-eva/clip_qwen3_proj_lora_marine_sds_ko_9k \
  --clip    openai/clip-vit-large-patch14-336
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--session` | (필수) | 영상 세션 폴더 |
| `--ckpt` | (필수) | 체크포인트 디렉토리 (토크나이저, chat template) |
| `--clip` | `openai/clip-vit-large-patch14-336` | CLIP 전처리 설정 |
| `--out` | `demo_video/data` | 출력 디렉토리 |
| `--grid` | 15 | 분석 격자 간격 (프레임, 15 = 0.5초) |

산출물 (`data/`, 5개 시나리오 기준 약 70MB):

```
data/
├── scenarios.json                 # 시나리오 목록, 잘라낸 경계(cut_y), 격자 간격
└── <시나리오 ID>/
    ├── video.mp4                  # 원본 영상 (재생용)
    ├── frames.json                # 프레임별 선박 상태, 격자 프레임의 프롬프트와 AIS 문장
    ├── inputs/fNNNNNN.png         # 격자 프레임의 모델 입력 이미지 (336×336)
    └── results.json               # precompute.py 가 만드는 사전 추론 결과
```

- 영상은 처음부터 순서대로 디코딩합니다 (`-fps_mode passthrough`). H.264 영상에서 시킹하면 프레임이 한두 개 어긋날 수 있기 때문입니다.
- 디코딩한 프레임 수가 `scenario.json` 의 `frameCount` 와 다르거나, 라벨이 없는 프레임이 있으면 중단합니다.

데이터와 코드를 Orin 으로 복사합니다.

```bash
rsync -a -e "ssh -p 11022" demo_video/ etri@129.254.222.149:demo_video/
```

이미 Orin 에서 `results.json` 을 만든 뒤 코드만 고쳐 올릴 때는 `--exclude data/ --exclude logs/` 를 붙여 결과를 덮어쓰지 않게 합니다.

---

## 5. Orin 준비

### 5-1. llama.cpp (CLS 순서 패치 필수)

llama.cpp 의 LLaVA 그래프(`tools/mtmd/models/llava.cpp`)는 CLS 토큰을 패치 뒤에 붙인 다음 위치 임베딩을 순서대로 더합니다.
HF CLIP 은 CLS 를 맨 앞에 둡니다. 패치 없이 실행하면 위치 임베딩이 한 칸씩 어긋나 출력이 학습 경로와 달라집니다.
근거와 측정값은 상위 README 13-2 Step 0 에 있습니다.

```bash
git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp-eva && cd ~/llama.cpp-eva
git checkout c479922ac          # 확인한 커밋 (2026-10-06)
sed -i 's/inp = ggml_concat(ctx0, inp, model.class_embedding, 1);/inp = ggml_concat(ctx0, model.class_embedding, inp, 1);/' \
  tools/mtmd/models/llava.cpp
```

JetPack 기본 이미지에는 `nvcc` 가 없어 그대로 빌드하면 CPU 전용이 됩니다.
`sudo apt install cuda-nvcc-12-6 libcublas-dev-12-6` 로 설치하거나, sudo 를 쓸 수 없으면 상위 README 13-3 의 방법으로 사용자 디렉토리에 풀어 씁니다.

```bash
cmake -B build-cuda -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87 -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF
cmake --build build-cuda -j6 --target llama-server
./build-cuda/bin/llama-server --list-devices      # CUDA0: Orin 이 보여야 함
```

### 5-2. 모델 파일

개발 서버에서 `scripts/convert_to_gguf.py` 로 만든 두 파일을 `~/models/eva_sds_ko_9k/` 에 둡니다 (상위 README 13-2).

| 파일 | 크기 | 내용 |
|---|---|---|
| `mmproj.gguf` | 1.25GB | CLIP ViT-L/14-336 (23개 블록) + mlp2x_gelu 프로젝터 |
| `llm-q8_0.gguf` | 8.7GB | LoRA 를 병합한 Qwen3-8B, Q8_0 |

---

## 6. 실행 (Orin)

```bash
cd ~/demo_video
./run_orin.sh precompute   # 처음 한 번: 2초 간격 장면을 미리 추론 (75장면, 약 20분) 후 서버 실행
./run_orin.sh              # 이후: 서버만 실행
```

- 실행하면 장비의 주소 후보가 모두 출력됩니다. 청중은 같은 망의 주소로 접속합니다 (예: `http://129.254.222.149:8000/`). docker·calico 같은 내부 가상망 주소는 외부에서 접속할 수 없습니다.
- llama-server 가 이미 떠 있으면 그대로 쓰고, 없으면 새로 띄웁니다. 로그는 `logs/` 에 남습니다.
- `precompute.py` 는 장면마다 결과를 저장하므로 중단 후 다시 실행하면 이어서 계산합니다. 모델 파일이 바뀌면 이전 결과를 버리고 다시 계산합니다.
- 경로와 포트는 환경 변수로 바꿀 수 있습니다.

| 환경 변수 | 기본값 |
|---|---|
| `LLAMA_BIN` | `~/llama.cpp-eva/build-cuda/bin/llama-server` |
| `MODEL_DIR` | `~/models/eva_sds_ko_9k` |
| `LLM_PORT` | 8080 (llama-server, 127.0.0.1 에만 열림) |
| `WEB_PORT` | 8000 (데모, 0.0.0.0) |

종료는 `server.py` 와 `llama-server` 프로세스를 끝내면 됩니다.

```bash
kill $(pgrep -x llama-server) $(pgrep -f "python3 .*demo_video/server.py")
```

---

## 7. 화면

| 영역 | 내용 |
|---|---|
| 시나리오 탭 | 조우 유형(마주침·횡단·추월), 충돌 코스 여부, 주변 선박 수 |
| 영상 | 시뮬레이터 원본 영상. 모델 출력은 영상 위쪽(하늘 영역)에 ‘상황’ 과 ‘조언’ 으로 나눠 겹쳐 표시. COLREG 조항과 조종 동작(변침·감속 등)을 강조 |
| 타임라인 | 주변 선박 중 가장 작은 CPA 곡선, 0.5NM 주의선, 분석 시점. 클릭하면 그 위치로 이동 |
| 모델이 보는 입력 | 실제로 모델에 들어가는 336×336 이미지와 AIS 입력 문장 |
| 주변 선박 | 자선 중심 레이더(북쪽 위, 6분 이동 벡터)와 선박별 거리·속력·CPA·TCPA. 거리는 프레임 라벨의 위경도로 계산 |
| 분석 카드 | 첫 글자까지 시간, 생성 속도, 전체 시간 |
| 동작 원리 | 입력 → CLIP 시각 인코딩 → Qwen3-8B → 출력 4단계 설명 |

좁은 화면(폭 640px 이하)에서는 모델 출력이 영상을 가리지 않도록 영상 아래에 붙습니다.

### 7-1. 표시 방식 (재생 조작 줄의 전환 버튼)

| 방식 | 동작 |
|---|---|
| 미리 계산된 결과 | `results.json` 의 2초 간격 결과를 재생 위치에 맞춰 보여 줍니다. ‘현재 장면 분석하기’ 를 누르면 영상을 멈추고 그 장면만 추론해 영상 위에 스트리밍합니다 |
| 실시간 추론 | 미리 계산된 결과를 쓰지 않습니다. 영상을 멈추지 않고 재생하면서, 추론 하나가 끝나는 즉시 그 순간의 장면으로 다음 추론을 시작합니다 |

실시간 추론 모드에서 보이는 정보는 다음과 같습니다.

- 영상 위에는 마지막으로 끝난 결과를 보여 줍니다. 함께 표시하는 항목은 아래와 같습니다.
  - 추론 시간. 브라우저에서 잰 요청부터 마지막 글자까지의 시간이며, 괄호 안은 서버에서 잰 시간입니다.
  - 결과가 나왔을 때 영상이 앞서 나간 시간. 결과 전에 영상이 멈추거나 끝났으면 그 사실을 표시합니다.
- 결과 아래 줄에는 진행 중인 추론의 장면, 경과 시간, 생성 토큰 수가 보입니다.
- 타임라인에는 분석한 장면(점)에서 결과가 나온 시점(막대 끝)까지 막대를 그립니다. 연속된 분석은 두 줄에 번갈아 그립니다.
- ‘모델이 보는 입력’ 은 분석 중이거나 마지막으로 분석한 장면의 이미지로 바뀝니다.

---

## 8. 서버 API

| 경로 | 설명 |
|---|---|
| `GET /` | 화면 |
| `GET /static/*`, `GET /data/*` | 화면 파일과 데이터. 영상 탐색을 위해 HTTP Range 요청을 처리합니다 |
| `GET /api/status` | llama-server 상태 (`ready`, `busy`, `model`, `n_ctx`, `vision`) |
| `POST /api/analyze` | 본문 `{"scenario": <시나리오 ID>, "frame": <격자 프레임>}`. 결과를 SSE(`data: {...}`) 로 토큰 단위 전송하고, 마지막 이벤트에 `timings`, `wall_s`, `first_token_s` 를 담습니다 |

- llama-server 는 슬롯 하나(`-np 1`)로 실행하므로 분석은 한 번에 하나만 처리합니다. 분석 중에 들어온 요청은 409 로 거절합니다. 실시간 추론 모드는 1.5초 뒤 다시 시도합니다.
- 실시간 추론 모드는 재생하는 동안 모델을 계속 사용합니다. 그동안 다른 화면의 분석 요청은 거절될 수 있습니다.
- 모드나 시나리오를 바꾸면 브라우저가 진행 중인 요청을 취소합니다. 서버는 다음 토큰을 보낼 때 연결이 끊긴 것을 알고 잠금을 풉니다.
- 요청 본문은 4096 바이트까지 받으며, 데이터 디렉토리 밖의 경로는 404 로 거절합니다.
- llama-server 는 기동할 때마다 무작위 미디어 마커를 씁니다. 서버는 `/props` 의 `media_marker` 를 읽어 프롬프트의 `<image>` 를 바꿉니다.

---

## 9. 측정값 (Jetson AGX Orin 32GB, Q8_0)

`clip_qwen3_proj_lora_marine_sds_ko_9k` 체크포인트, 세션 `2026-09-30_13-05-39` (5개 시나리오) 기준입니다.

| 항목 | 값 |
|---|---|
| 사전 추론 (75장면) | 장면당 13.2~18.6초, 생성 17.1~18.7 토큰/초, 모두 eos 로 종료 |
| 실시간 추론 1회 (추월, 1×) | 첫 글자까지 1.1초, 생성 18.7 토큰/초, 브라우저 기준 16.0초 (서버 15.8초) |
| 실시간 추론 중 영상 진행 (마주침 B, 1×) | 추론 13.7초 동안 영상 14.0초 진행 |
| 메모리 사용 최대 (tegrastats RAM, 20건 순차 추론) | 16.6GB |

모델 출력은 수정하지 않고 그대로 보여 줍니다. 출력 문장의 수치(거리, 방위)가 AIS 로 계산한 값과 다를 수 있습니다.
예를 들어 횡단·충돌 코스 15초 장면에서 모델은 최근접선 거리를 약 3.55NM 으로 출력했고, 같은 프레임의 위경도로 계산한 거리는 7.79NM 이었습니다.
화면의 ‘주변 선박’ 표는 라벨에서 계산한 값을 보여 줍니다.
