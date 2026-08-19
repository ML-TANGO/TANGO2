# Qwen3-8B × MixATIS (UGEN QA)

Qwen3-8B 를 MixATIS_clean(UGEN QA 포맷) 데이터로 **QLoRA 파인튜닝 → 평가**까지 한 번에 실행합니다.
학습/평가는 Docker 컨테이너 안에서 돌아가고, 호스트에서는 웹 콘솔(`web_app.py`) 또는 셸 스크립트로 컨테이너를 띄웁니다.

## 실행 화면

![웹 콘솔 실행 화면](intent.jpg)

위 화면은 `MODE=full` (3 epoch 학습 + 828 발화 평가) 실행이 끝난 상태입니다. 화면 구성은 세 부분입니다.

- **왼쪽 `실험 설정`** — [4-A 설정 항목](#4-a-웹-콘솔-권장) 의 항목들을 그대로 입력/선택합니다. `[▶ 실행 (학습 + 평가)]` 로 시작, `[■ 중지]` 로 컨테이너를 내리고, `[기본값 복원]` 으로 초기값으로 돌아갑니다.
- **오른쪽 위 `진행 상황`** — 학습/평가 단계와 진행률(`828/828 발화`)이 실시간으로 갱신되고, 평가가 끝나면 지표 카드가 채워집니다. Intent F1 / Slot F1 카드에는 Precision · Recall 도 함께 표시됩니다.
- **오른쪽 아래 `실행 로그`** — 컨테이너의 stdout 이 그대로 흐릅니다. 마지막에 `MixATIS 평가 결과` 요약과 산출물 경로(LoRA 어댑터, 평가 CSV), 종료 코드(`exit=0`)가 남습니다.

화면의 지표는 A100 80GB · QLoRA(4bit) 기준 `full` 실행 결과입니다.

| Intent Acc | Intent F1 | Slot F1 | Overall (Joint) Acc |
|---|---|---|---|
| 95.89% | 98.10% | 90.77% | 67.03% |

---

## 1. 사전 요구사항

- NVIDIA GPU + 드라이버 (검증 환경: A100 80GB)
- Docker Engine + **nvidia-container-toolkit**
- 디스크 여유 ~40GB
- 호스트 Python 3.7+ (웹 콘솔용, 추가 패키지 불필요)

GPU 인식 확인:

```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

---

## 2. ⚠️ 실행 전 필수: HF_TOKEN 입력

저장소에는 토큰이 들어 있지 않습니다(빈 값). 웹 콘솔(`web_app.py`)은 **`auto2.sh` 를 그대로 실행**하므로,
웹을 띄우기 전에 `auto2.sh` 25번째 줄에 본인의 Hugging Face 토큰을 넣어 두어야 합니다.

```bash
# auto2.sh:25  (수정 전)
HF_TOKEN="${HF_TOKEN:-}"

# auto2.sh:25  (수정 후 — 따옴표 안에 본인 토큰)
HF_TOKEN="${HF_TOKEN:-hf_여기에_본인_토큰}"
```

- 토큰 발급: <https://huggingface.co/settings/tokens> (read 권한)
- `${HF_TOKEN:-...}` 형태이므로 **환경변수가 있으면 환경변수가 우선**입니다. 파일을 고치기 싫다면 웹 콘솔을 띄우기 전에 export 해도 됩니다(웹 콘솔이 자기 환경변수를 자식 프로세스로 물려줍니다).
  ```bash
  export HF_TOKEN=hf_xxxxxxxxxxxx
  python web_app.py
  ```
- 셸로만 돌릴 때도 동일합니다.
  ```bash
  export HF_TOKEN=hf_xxxxxxxxxxxx
  MODE=full bash auto2.sh
  ```
- 같은 자리(`HF_TOKEN=`)가 `auto.sh`, `run_experiment.sh:18` 에도 있으니 그쪽으로 실행할 때는 함께 채우세요.
- 웹 콘솔 화면에는 토큰 입력란이 **없습니다**. 반드시 위 방법 중 하나로 미리 넣어 두세요.
- 참고: `Qwen/Qwen3-8B` 는 공개 모델이라 토큰 없이도 동작하지만, rate limit 때문에 본인 토큰을 넣는 것을 권장합니다.
- 토큰을 넣은 `auto2.sh` 는 커밋하지 마세요(토큰이 노출되면 HF 계정에서 폐기(revoke)).

---

## 3. 이미지 빌드

```bash
cd Intent_web
docker build -t qwen3-mixatis:latest .
```

빌드 시 PyTorch 2.5.1 / CUDA 12.1 베이스 이미지와 UGEN 데이터셋(`/workspace/UGEN`)이 함께 준비됩니다.

---

## 4. 실행

### 4-A. 웹 콘솔 (권장)

> 실행 전에 [2장](#2--실행-전-필수-hf_token-입력) 대로 `auto2.sh` 에 HF_TOKEN 을 넣었는지 먼저 확인하세요. 웹 콘솔은 `auto2.sh` 를 그대로 실행합니다.

```bash
cd Intent_web
python web_app.py            # 기본 0.0.0.0:8080  (PORT=9000 으로 변경 가능)
```

브라우저에서 <http://localhost:8080> 접속 → 설정 확인 후 **[▶ 실행]** 클릭.
원격 서버라면 `ssh -L 8080:localhost:8080 <user>@<서버>` 로 포워딩해 접속하세요.

설정 항목:

| 항목 | 기본값 | 설명 |
|---|---|---|
| `MODE` | `debug` | `debug`: 학습 200 예제 / 평가 20 발화<br>`full`: 3 epoch 전체 학습 / 828 발화 평가 |
| `MODEL_NAME` | `Qwen/Qwen3-8B` | HF Hub 모델 ID |
| `DATA_DIR` | `/workspace/UGEN/data/MixATIS_clean` | 컨테이너 내부 경로 |
| `OUTPUT_DIR` | `/workspace/out/qwen3-8b-mixatis-lora` | 컨테이너 내부 경로 (호스트 `./out/...`) |
| `4bit (QLoRA)` | `1` | `0` = bf16 LoRA (80GB+ GPU 필요) |

실행 로그와 진행률이 화면에 실시간 표시되고, 평가가 끝나면 Intent Acc / Intent F1 / Slot F1 / Joint Acc 가 카드로 나옵니다.

> 한 번에 하나의 실험만 실행됩니다. `web_app.py` 를 종료하면 실험도 끊기므로, `full` 실험은 `tmux` 안에서 띄우세요.
> 웹 콘솔은 인증이 없으니 내부망 또는 SSH 포워딩으로만 사용하세요.

### 4-B. 셸 실행

```bash
bash auto2.sh                 # debug 점검
MODE=full bash auto2.sh       # 전체 실험 (포그라운드)
bash auto.sh                  # 전체 실험 (nohup 백그라운드 → log.out)

# 백그라운드 + 로그 확인
nohup env MODE=full bash auto2.sh > log_full.out 2>&1 &
tail -f log_full.out
```

`auto2.sh` 환경변수: `MODE`(debug/full), `MODEL_NAME`, `DATA_DIR`, `OUTPUT_DIR`, `USE_4BIT`, `HF_TOKEN`, `IMAGE`, `GPU_DEVICE`(기본 0), `CONTAINER_NAME`(기본 `qwen3_web_run`).

### 4-C. docker run 직접 실행

```bash
docker run --rm --gpus '"device=0"' \
  -e HF_TOKEN=hf_본인_토큰 \
  -v $(pwd)/out:/workspace/out \
  -v hf_cache:/workspace/.hf_cache \
  qwen3-mixatis:latest bash run_experiment.sh full   # 또는 debug
```

`run_experiment.sh` 가 받는 추가 환경변수: `EPOCHS`(3), `BATCH_SIZE`(2), `GRAD_ACCUM`(8), `MAX_LEN`(768), `USE_4BIT`(1), `EVAL_CSV`.

### 중지

```bash
docker rm -f qwen3_web_run    # 웹/auto2.sh 실행분
docker ps                     # 그 외 컨테이너 ID 확인 후 docker rm -f <id>
```

---

## 5. 결과물

컨테이너의 `/workspace/out` 이 호스트 `./out` 으로 마운트되어 결과가 남습니다.

```
out/
├── qwen3-8b-mixatis-lora/     # LoRA 어댑터
└── mixatis_eval.csv           # 발화별 예측 결과
```

```bash
ls out/qwen3-8b-mixatis-lora
column -s, -t < out/mixatis_eval.csv | less -S
```

모델 캐시는 `hf_cache` named volume 에 저장되어, 두 번째 실행부터는 16GB 재다운로드가 없습니다.

