# ETRI 평가 웹데모 서빙 (Intent_web / Logickor_web)

`Evaluation/Intent_web` 과 `Evaluation/Logickor_web` 은 ETRI 가 준 **독립 웹데모**다.
둘 다 "웹 콘솔이 셸 파이프라인을 띄우는" 구조라, 플랫폼(K8s) 에 편입하지 않고
이 호스트(idc93)에서 그대로 띄워 테스트할 수 있게 감싼 계층이 이 폴더다.

**ETRI 원본 소스는 수정하지 않는다.** 포트·GPU·인터프리터·docker 권한은 전부
런처(`serve.sh`)가 환경변수/PATH 로 주입한다.

---

## 빠른 사용법

```bash
cd Evaluation/serve
./setup.sh              # 최초 1회 (멱등 — 다시 돌려도 안전)
./serve.sh start all    # 기동
./serve.sh status       # 상태 + GPU
./serve.sh logs intent  # 로그 tail
./serve.sh stop all     # 중지
```

| 서비스 | URL | GPU | 파이프라인 |
|---|---|---|---|
| Intent_web (Qwen3-8B × MixATIS) | `http://<서버>:8090` | 7 | `auto2.sh` → docker 컨테이너 |
| Logickor_web (LogicKor 벤치마크) | `http://<서버>:8000` | 6 | `scripts/auto.sh` → 호스트 venv |

원격 접속은 SSH 포워딩 권장 (웹 콘솔에 인증이 없다):

```bash
ssh -L 8090:localhost:8090 -L 8000:localhost:8000 <계정>@<서버>
```

---

## 이 호스트에 맞추기 위해 해결한 것

### 1. 포트 — 8080/8081 이 이미 점유되어 있다
Intent_web 의 기본 포트가 8080 이라 그대로는 못 뜬다. `PORT=8090` 으로 옮겼다
(`web_app.py` 가 `PORT` 환경변수를 읽는다). Logickor 는 기본 8000 그대로.

### 2. docker 권한 — julian 은 docker 그룹이 아니다
Intent_web 은 `docker run --gpus` 로 실험 컨테이너를 띄운다. julian 계정은
docker 소켓 권한이 없고 **sudo NOPASSWD 만** 된다. 원본 스크립트를 고치지 않기 위해
`$SERVE_ROOT/bin/docker` shim(`exec sudo -n /usr/bin/docker "$@"`)을 만들고
런처가 PATH 앞단에 얹는다. `web_app.py` 와 `auto2.sh` 둘 다 PATH 로 `docker` 를
찾으므로 한 번에 해결된다.

### 3. Python 런타임 — conda 가 없다
Logickor README 는 conda(python 3.11.15)를 요구하지만 이 호스트엔 conda 가 없다.
대신 `uv` 로 동일한 3.11.15 를 받아 venv 를 만든다.

`uv pip install` 시 `--index-strategy unsafe-best-match` 가 **필수**다.
requirements.txt 의 `--extra-index-url .../whl/cu128` 에 대해 uv 는 pip 과 달리
기본적으로 첫 인덱스만 보기 때문에, 없으면 `certifi==2026.2.25` 같은 핀에서
"unsatisfiable" 로 죽는다.

### 4. `auto.sh` 가 맨 `python` 을 호출한다
`scripts/auto.sh` 는 `python train/train_lora.py ...` 처럼 인터프리터를 이름으로만
부른다. 웹앱을 venv 파이썬으로 띄우는 것만으로는 부족하고(자식은 PATH 를 따른다),
런처가 **venv 의 bin 을 PATH 앞단에 올려야** 한다. 안 그러면
`ModuleNotFoundError: No module named 'torch'` 로 Step 1 에서 죽는다.

### 5. 🔴 Intent 이미지의 transformers 가 상한 없이 풀려 있었다 (원본 수정 1줄)
`requirements-docker.txt` 가 `transformers>=4.51.0` 로만 적혀 있어, 지금 빌드하면
**transformers 5.15.1** 이 깔린다. v5 는 `TrainingArguments` 에서 `warmup_ratio` 를
없앴기 때문에 (`warmup_steps` 만 남음) 학습 직전에 죽는다:

```
TypeError: TrainingArguments.__init__() got an unexpected keyword argument 'warmup_ratio'
```

ETRI 가 검증한 시점에는 같은 명세가 4.5x 로 풀렸다. 상한을 붙여 그 동작을 복원했다:

```diff
-transformers>=4.51.0
+transformers>=4.51.0,<5      # -> 4.57.6
```

하한 4.51 은 Dockerfile 주석대로 bitsandbytes 4bit 로더(`nn.Module.set_submodule`)
때문에 필요하므로 그대로 뒀다. **이 폴더에서 ETRI 원본을 고친 유일한 지점이다.**
(플랫폼 쪽도 같은 이유로 transformers 를 <5.0.0 으로 고정하고 있다.)

### 6. GPU 배정
idc93 은 A100 80GB × 8 이고 0~5 는 서빙 스택이 쓰고 있다. 유휴인 **6, 7 번**만 쓴다.
- Intent: `GPU_DEVICE=7` (환경변수 → `auto2.sh` → `docker --gpus device=7`)
- Logickor: `gpu=6` (웹 UI 설정값 → `auto.sh` → `CUDA_VISIBLE_DEVICES=6`)

### 7. 🔴 Logickor 학습데이터가 저장소에 없다
`configs/*.yaml` 이 가리키는 `data/logickor_sft_high_converted.jsonl` 은
`.gitignore` 의 `data/*` 규칙 때문에 **포함되어 있지 않다**. 그대로 실행하면
Step 1 이 파일 없음으로 죽는다.

`bootstrap_logickor_data.py` 가 같은 저장소에 있는 LogicKor 생성결과
(`Evaluation/Logickor/generated/Gemma4-e4b-it/step/v0/default.jsonl`,
`evaluated/` 기준 judge 평균 8.32 로 default 프롬프트 중 최고)를 학습 포맷으로
변환해 42문항 × 2턴 = 84행을 만든다. ETRI 자체 `train/dataloader.py:validate_rows`
로 검증을 통과한다.

> ⚠️ **이건 파이프라인이 도는지 확인하기 위한 대체물이지 ETRI 정본 데이터가 아니다.**
> 정본 `logickor_sft_high_converted.jsonl` 을 받으면 같은 경로에 덮어쓰면 된다
> (스키마 동일). 이 데이터로 낸 점수는 참고용으로도 쓰지 말 것.

### 8. HF 토큰은 필수가 아니다
`Qwen/Qwen3-8B` 와 `google/gemma-4-E4B-it` 둘 다 **비게이트**라 토큰 없이 받아진다
(README 들은 토큰을 요구하지만 실제로는 rate limit 회피용). 넣고 싶으면:

```bash
echo 'HF_TOKEN=hf_xxxx' > ~/etri-eval-serve/secrets.env
./serve.sh restart all
```

`secrets.env` 는 저장소 밖(`SERVE_ROOT`)에 있어 커밋될 일이 없다.

---

## 알려진 제약

- **판사 모델 프리셋 `llama` 는 이 호스트에서 동작하지 않는다.**
  `logickor_eval/evaluator.py` 의 `"llama": "/home/parkjb/Llama-3.1-8B-Instruct"` 는
  ETRI 쪽 로컬 경로다. 기본값인 `gemma` 를 쓰거나, 화면에서 HF repo id / 로컬 경로를
  직접 입력하면 된다.
- **웹 콘솔에 인증이 없다.** 0.0.0.0 바인딩이므로 내부망 전용으로만 쓰고,
  외부에서는 SSH 포워딩으로 접근할 것.
- **`Intent_web/out/` 는 root 소유로 생긴다.** `auto2.sh` 가 `--user` 없이 컨테이너를
  띄우고 컨테이너 안에서는 root 로 쓰기 때문이다. julian 계정으로는 지울 수 없으니
  정리할 때는 `sudo rm -rf Evaluation/Intent_web/out` 을 쓴다. (git 에는 안 올라간다 —
  `Intent_web/.gitignore` 에 `out/` 을 넣어 두었다.)
- **한 번에 하나의 실험만 돈다** (양쪽 앱 모두). 웹 프로세스를 죽이면 실험도 끊긴다.
- `full` 모드는 몇 시간 단위다. `serve.sh` 는 nohup 으로 띄우므로 SSH 를 끊어도
  살아있지만, 긴 실험은 진행상황을 `./serve.sh logs <svc>` 로 확인할 것.

## 런타임 산출물 위치

저장소를 더럽히지 않도록 전부 `SERVE_ROOT`(기본 `~/etri-eval-serve`) 아래에 둔다.

```
~/etri-eval-serve/
├── bin/docker          # sudo shim
├── venvs/logickor/     # py3.11 + vllm/torch (ETRI 핀 스냅샷)
├── venvs/intent/       # py3.11 stdlib 전용
├── hf_cache/           # HF_HOME — 모델 캐시 공유
├── logs/               # 웹 서버 로그
├── run/                # pidfile
└── secrets.env         # (선택) HF_TOKEN
```

단, 각 앱이 자기 폴더에 쓰는 산출물은 원본 구조를 따른다:
`Intent_web/out/`, `Logickor_web/{runs,generated,evaluated}/` — 모두 gitignore 대상이다.
