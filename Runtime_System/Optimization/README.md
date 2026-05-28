# TANGO2 LLM 원샷 프루닝(One-shot Pruning)

딥러닝 프레임워크 **TANGO2** 환경에서 대형 언어 모델(LLM)을 **원샷 프루닝**으로 최적화(메모리 절감/경량화)하는 예제입니다.  
본 레포는 두 가지 핵심 스크립트로 구성됩니다:

- **모델 다운로드:** `download.py` – Hugging Face Hub에서 LLM 체크포인트를 로컬로 내려받습니다.
- **원샷 프루닝:** `oneshot_prune.py` – PyTorch/Transformers 기반으로 LLM 신경망을 원샷(L1 magnitude) 방식으로 프루닝하고 저장합니다.

---

## ✨ 무엇이 원샷 프루닝인가요?
- **원샷(one-shot)**: 학습을 오래 재진행하지 않고, 한 번의 중요도 산정으로 가중치를 잘라내는 간소화/고속 프루닝 방식입니다.
- **장점**: 빠른 경량화, 쉬운 파이프라인 구성  
- **주의**: 정확도 하락이 있을 수 있어, 필요시 **짧은 (Q)LoRA 보정**으로 성능을 일부 회복하는 것을 권장합니다.

---

## 📦 요구 사항

- Python ≥ 3.10
- CUDA GPU(선택) 또는 충분한 CPU/RAM
- 기본 패키지
  ```bash
  pip install -U torch transformers accelerate safetensors sentencepiece huggingface_hub
  ```
- (GPU 4비트 양자화 옵션) `pip install bitsandbytes`

---

## 🔐 Hugging Face 접근(중요)

- `meta-llama/Llama-2-13b-hf`는 **gated repo** 입니다. Meta 약관 동의 및 **승인 완료**가 필요합니다.
- 터미널 로그인:
  ```bash
  huggingface-cli login  # hf_xxx... read 토큰 입력
  ```

---

## ⬇️ 모델 다운로드 – `download.py`
예시 스크립트는 Hugging Face Hub에서 스냅샷을 **폴더로 통째로** 내려받습니다. 필요에 따라 `repo_id`를 원하는 모델로 바꾸세요. (예: `meta-llama/Llama-2-13b-hf`, 승인 필요)

```python
from huggingface_hub import snapshot_download

local_dir = snapshot_download(
    repo_id="meta-llama/Llama-3.2-1B",   # ← 원하는 모델 ID로 변경 가능
    local_dir="./Llama-3.2-1B"           # 저장 경로
)
print("Downloaded to:", local_dir)
```

**권장 사용법**
```bash
python download.py
# 또는 코드에서 repo_id="meta-llama/Llama-2-13b-hf"로 수정 후 실행
```

---

## ✂️ 원샷 프루닝 – `oneshot_prune.py`
LLaMA-2 13B를 로드하고 **L1 magnitude 기반 원샷 프루닝**을 수행해 저장합니다. 기본적으로 `nn.Linear`의 `weight`를 대상으로 하며, `lm_head`는 제외됩니다. 로그 문자열은 “global”이라 표기되지만, 실제 구현은 **레이어별(L1) 원샷**으로 동작해 **메모리 사용량을 줄입니다.**

### 사용 예시

#### 1) GPU(권장, FP16)
```bash
python oneshot_prune.py   --model_id meta-llama/Llama-2-13b-hf   --device cuda --dtype fp16   --sparsity 0.5   --save_dir ./llama2-13b-pruned-50   --eval_texts "Large language models are powerful." "프루닝 후 성능 확인 텍스트"
```

#### 2) CPU(FP16) – 메모리 절약 모드
```bash
python oneshot_prune.py   --model_id meta-llama/Llama-2-13b-hf   --device cpu --dtype fp16   --sparsity 0.5   --save_dir ./llama2-13b-pruned-50
```

### 주요 인자
- `--model_id`: HF 모델 ID (기본: `meta-llama/Llama-2-13b-hf`)
- `--sparsity`: 0~1 사이 희소도 (예: `0.5` → 50% 제거)
- `--device`: `cuda` / `cpu` (기본 자동)
- `--dtype`: `fp16` / `bf16` / `fp32`
- `--include` / `--exclude`: 모듈 이름 필터 (기본 `lm_head` 제외)
- `--eval_texts`: 간단 PPL 평가 문장들

### 결과물
- 프루닝된 모델이 `--save_dir` 경로에 **`save_pretrained` 포맷**으로 저장됩니다.
- 추후 **GGUF 변환(예: llama.cpp)** → **양자화** → **Ollama 등록** 등의 파이프라인에 그대로 활용 가능합니다.

---

## 🧠 TANGO2 워크플로우 팁

- **스파시티 스윕**: `0.3 / 0.4 / 0.5` 등 여러 값으로 프루닝 → 검증 데이터에서 PPL/정확도 비교
- **빠른 보정**: 프루닝 후 **(Q)LoRA**로 수 시간 내 보정 파인튜닝을 붙이면 성능 복원에 효과적
- **실제 속도 최적화**: 비구조적 희소성은 메모리 이득 중심입니다. 속도까지 노리면  
  **2:4 / 4:8 반구조 sparsity + 해당 커널/백엔드 지원**(예: TensorRT, Sparse kernels)을 고려하세요.
- **하드웨어 제약**: 13B는 VRAM/RAM 부담이 큽니다. 작업 전 **7B 모델로 리허설**을 강력 추천합니다.

---

## 🛠️ 트러블슈팅

- **401/403 (gated repo)**  
  → Meta 접근 승인 확인, `huggingface-cli login`, 코드에서 `token=` 전달 또는 환경변수 `HF_TOKEN` 사용

- **TypeError: parameters on different devices**  
  → 여러 디바이스에 분산 로드되어 발생. 한 디바이스(cpu 또는 단일 gpu)로 올리거나, 본 스크립트처럼 **레이어별 L1 프루닝**을 사용

- **Killed (OOM)**  
  → 메모리 부족. `--dtype fp16`로 메모리 절약, 또는 sparsity 낮추기/일부 모듈 제외/7B 모델로 전환

---

## 📁 파일 구조(예시)
```
.
├── download.py                     # HF에서 모델 내려받기
├── oneshot_prune.py     # LLaMA-2 13B 원샷 프루닝 스크립트
└── README.md
```

---

## 📜 라이선스 & 주의
- LLaMA-2 가중치는 **Meta 라이선스**를 따릅니다. 사용 조건을 반드시 확인하세요.
- 본 스크립트는 연구/프로토타입 목적의 예시이며, 배포 전 충분한 검증이 필요합니다.

---

## ✅ 빠른 시작(요약)

1) **로그인/승인**
```bash
huggingface-cli login   # hf_xxx... read 토큰
```

2) **다운로드**
```bash
python download.py  # repo_id를 원하는 모델로 수정 가능
```

3) **프루닝 실행**
```bash
python oneshot_prune.py   --model_id meta-llama/Llama-2-13b-hf   --device cuda --dtype fp16   --sparsity 0.5   --save_dir ./llama2-13b-pruned-50
```

4) **(선택) 보정/변환/배포**
- (Q)LoRA 보정 → GGUF 변환 → 양자화 → Ollama 등록
