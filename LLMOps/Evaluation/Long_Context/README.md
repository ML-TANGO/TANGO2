# 입력 토큰 길이 수 평가

본 디렉토리는 공개 NIAH(`gkamradt/needle-in-a-haystack`) 저장소에 실행 파일을 추가해 **커스텀 모델**의 long-context 평가를 실행하는 방법을 안내함

## 포함 파일

```text
Long_Context/
├── .gitignore
├── README.md
├── files/
│   ├── configs/models/google-gemma-4-e4b-it-transformers.yaml
│   ├── configs/runs/gemma_single_needle.local.yaml
│   └── needlehaystack/providers/transformers_local.py
├── patches/
│   ├── register_transformers_provider.patch
│   └── configurable_tokenizer.patch
└── scripts/
    ├── setup.sh
    ├── run_eval.sh
    └── niah_helper.py
```

## 빠른 사용 (스크립트)

실험 환경마다 `setup.sh`를 한 번 실행한 뒤, `run_eval.sh` 맨 위의 설정만 고쳐서 실행

### 1) 설치

TANGO2 전체가 필요 없다면 이 디렉토리만 sparse checkout으로 받음

```bash
git clone --filter=blob:none --sparse https://github.com/ML-TANGO/TANGO2.git
cd TANGO2
git sparse-checkout set LLMOps/Evaluation/Long_Context
cd LLMOps/Evaluation/Long_Context
scripts/setup.sh
```

`setup.sh`가 하는 일은 다음과 같음

- NIAH 원본을 `needle-in-a-haystack/`에 고정 commit으로 clone하고, `files/`를 복사하고 `patches/`를 적용함
- uv가 관리하는 Python 3.12로 `.venv`를 생성. 다른 서버에서 복사해 온 `.venv`는 그 서버의 경로를 가리키므로 새로 생성이 필요함
- 드라이버의 CUDA 버전을 보고 PyTorch wheel(cu126/cu128)을 선택함. `--torch_index`로 직접 지정할 수 있고, GPU가 없으면 cpu wheel을 설치함
- 테스트한 버전으로 고정된 의존성을 설치하고, `cl100k_base` 토크나이저를 미리 받아 설치됨

Gemma 모델을 받으려면 Hugging Face 로그인과 모델 이용 동의가 필요할 수 있음

```bash
source needle-in-a-haystack/.venv/bin/activate
hf auth login
```

### 2) 어댑터 다운로드 (선택)

학습한 LoRA 어댑터는 Hugging Face Hub에 업로드함. 사전학습 모델만 평가한다면 이 단계는 건너뛰어도 됨

| HF 레포 | base 모델 | 크기 |
|---|---|---|
| [yanghoon/gemma4-e4b-ipo-v1-lora](https://huggingface.co/yanghoon/gemma4-e4b-ipo-v1-lora) | `google/gemma-4-E4B-it` | 약 300MB |
| [yanghoon/gemma4-12b-ipo-v1-lora](https://huggingface.co/yanghoon/gemma4-12b-ipo-v1-lora) | `google/gemma-4-12B-it` | 약 550MB |

`Long_Context` 폴더에서 실행. `hf` 명령은 `.venv` 안에 설치되어 있음

```bash
source needle-in-a-haystack/.venv/bin/activate
hf download yanghoon/gemma4-e4b-ipo-v1-lora --local-dir ./adapters/gemma4-e4b-ipo-v1-lora
hf download yanghoon/gemma4-12b-ipo-v1-lora --local-dir ./adapters/gemma4-12b-ipo-v1-lora
```

- `--local-dir`를 빼면 HF 캐시(`~/.cache/huggingface/hub/...`) 안의 긴 경로에 저장됨. 찾기 쉬운 위치로 지정하는 것을 권함
- `--local-dir`는 명령을 실행한 폴더 기준임. 다른 폴더에서 실행한다면 `/`로 시작하는 절대경로로 수정할 것
- 제대로 받았는지 확인하려면 폴더마다 base 모델이 맞게 나오는지 확인
  ```bash
  grep base_model_name_or_path adapters/*/adapter_config.json
  ```

### 3) 평가 설정

`scripts/run_eval.sh` 맨 위의 설정 블록만 수정

```bash
MODEL="google/gemma-4-E4B-it"   # HF 모델 id 또는 로컬 경로. ADAPTER를 쓸 때 ""이면 adapter_config.json에서 읽음
ADAPTER=""                      # 어댑터 폴더(절대경로). "" = 사전학습 모델 그대로 평가
CONTEXT=(all)                   # k 단위. 예: (2 4) / (4 8 16). (all) = 4 8 16 32 64 128
TOKENIZER="model"                 # 길이를 세는 기준: gpt(디폴트) | model(사용 모델의 토크나이저)
DEPTHS=(50)                     # needle 위치(%). 예: (0 50 100)
GPUS=""                         # 예: "0" / "0,1". "" = 보이는 GPU 전부
```

예를 들어 E4B 어댑터를 2k·4k에서 평가하려면 다음과 같이 수정

```bash
MODEL=""
ADAPTER="/home/<user>/.../Long_Context/adapters/gemma4-e4b-ipo-v1-lora"
CONTEXT=(2 4)
TOKENIZER="model"
DEPTHS=(0 50 100)
GPUS="0,1"
```

### 4) 실행

```bash
bash scripts/run_eval.sh --dry_run   # 모델을 불러오지 않고 길이 계산과 설정만 확인
bash scripts/run_eval.sh
```

dry run은 길이별로 모델이 실제로 받을 토큰 수를 출력함. 예: `4k: context_length=4,096 -> prompt 4,139 model tokens`. 실제 실행에서는 한 번 평가할 때마다 `[ok] ctx=4096 depth=50.0% score=1.00`처럼 한 줄씩 출력하고, 마지막에 길이 × 위치 요약 표를 보여줌

### 5) 결과

결과는 `needle-in-a-haystack/results/<모델>[__<어댑터>]__tok-<토크나이저>/`에 저장됨

| 파일 | 내용 |
|---|---|
| `results.jsonl` | 평가한 조합별 원본 결과(응답, 점수, 토큰 수) |
| `summary.csv` | 길이 × 위치 점수 표 |
| `run.yaml`, `model.yaml` | 스크립트가 만든 NIAH 설정 |
| `plan.json` | 길이 라벨과 길이를 센 토크나이저 기록 |

- 점수는 응답에 `eat a sandwich and sit in Dolores Park`가 포함되면 1, 아니면 0(대소문자 무시). 표현이 조금만 달라도 0점이 되므로, 0점이 나오면 `results.jsonl`의 `response`를 확인
- 같은 설정으로 다시 실행하면 이미 끝난 조합은 건너뜀. 오류가 난 조합도 끝난 것으로 치므로, 다시 평가하려면 해당 결과 폴더를 삭제 필요
