# Gemma4-E4B-IT LogicKor SFT Reproduction Guide

이 문서는 `google/gemma-4-E4B-it` 기반 LogicKor LoRA SFT 학습, 생성, OpenAI Judge 평가, scoring 재현 절차를 설명합니다.

## 실험 범위

기본 재현 대상은 Gemma4-E4B-IT SFT입니다.

- base model: `google/gemma-4-E4B-it`
- 학습 방식: LoRA SFT
- 기본 학습 config: `configs/train_gemma4_e4b_sft.yaml`
- step 학습 config: `configs/train_gemma4_e4b_step_sft.yaml`
- Judge 모델: `gpt-4.1`

포함된 평가 산출물은 `generated/`와 `evaluated/`에서 확인할 수 있습니다. 기본 실행 경로는 Gemma4-E4B-IT입니다.

## 성능 요약

아래 표는 `gemma-4-E4B-it` 전체 점수 요약입니다. `Zero-shot overall`, `1-shot overall`, `Cot-1-shot overall`은 각 prompt setting의 Overall 점수입니다.

| 실험 | Zero-shot overall | 1-shot overall | Cot-1-shot overall | Best |
|---|---:|---:|---:|---|
| Pre-trained | 8.06 | 7.71 | 7.76 | Zero-shot |
| LoRA SFT (평균) | 8.07 | 8.05 | 8.21 | Cot-1-shot |
| LoRA SFT (최고값) | 8.12 | 8.26 | 8.23 | 1-shot |
| 1st/2nd stage SFT (평균) | 8.20 | 8.23 | 8.38 | Cot-1-shot |
| 1st/2nd stage SFT (최고값) | 8.11 | 8.40 | 8.44 | Cot-1-shot |


## 학습 데이터

```text
data/logickor_sft_high_converted.jsonl
data/logickor_sft_high.jsonl
data/logickor_sft_middle_convert.jsonl
data/logickor_sft_middle.jsonl
```

기본 SFT config는 `data/logickor_sft_high_converted.jsonl`을 사용합니다.

## 환경 설치

학습 환경과 추론/평가 환경을 분리합니다. 두 requirements 설치 시 `--no-deps`로 권장드립니다.

### 학습 환경

```bash
conda create -n etri python=3.12.13 -y
conda activate etri
python -m pip install --no-deps -r requirements/etri-training.txt
```

### 추론 및 평가 환경

```bash
conda create -n etri-infer python=3.11.15 -y
conda activate etri-infer
python -m pip install --no-deps -r requirements/etri-infer.txt
```

CUDA driver, PyTorch, vLLM 조합은 서버 환경에 영향을 받습니다. 설치 후 `tests/`와 dry-run으로 먼저 확인합니다.

```bash
conda activate etri
python train/train_lora.py --config configs/train_gemma4_e4b_sft.yaml --output-dir /tmp/logickor-dry-run --dry-run
```

## 학습

기본 Gemma4-E4B-IT SFT 학습은 다음과 같이 실행합니다.

```bash
python train/train_lora.py \
  --config configs/train_gemma4_e4b_sft.yaml \
  --output-dir runs/gemma4_e4b_sft_high \
  --seed 42
```

학습이 끝나면 adapter와 merged model이 `runs/gemma4_e4b_sft_high/` 아래에 생성됩니다.

## 생성

평가용 답변 생성은 `etri-infer` 환경에서 실행합니다. 모델 경로는 로컬에 준비한 merged model 경로로 바꿉니다.

```bash
python logickor_eval/generator.py \
  --model models/gemma4_e4b_sft_high/merged \
  --gpu_devices 0 \
  --model_len 4096
```

`generator.py`는 `logickor_eval/questions.jsonl`을 읽고 `generated/<model-path>/` 아래에 `default.jsonl`, `1-shot.jsonl`, `cot-1-shot.jsonl`을 저장합니다.

## OpenAI Judge 평가

OpenAI API key는 코드나 script에 직접 쓰지 않고 환경변수로 전달합니다.

```bash
conda activate etri-infer
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"

bash scripts/evaluate.sh generated/models/gemma4_e4b_sft_high/merged
```

직접 실행 예시는 다음과 같습니다.

```bash
python logickor_eval/evaluator.py \
  -o generated/models/gemma4_e4b_sft_high/merged \
  -k "$OPENAI_API_KEY" \
  -j gpt-4.1 \
  -t 30
```

평가 결과는 `evaluated/<generated-output-path>/` 아래에 저장됩니다.

## Scoring

```bash
conda activate etri-infer

bash scripts/score.sh 'evaluated/models/gemma4_e4b_sft_high/merged/*.jsonl'
```

직접 실행 예시는 다음과 같습니다.

```bash
python logickor_eval/score.py \
  -p 'evaluated/models/gemma4_e4b_sft_high/merged/*.jsonl'
```

## 포함된 산출물 확인

이미 생성된 Gemma4-E4B-IT 산출물은 다음 위치에서 확인할 수 있습니다.

```text
generated/Gemma4-e4b-it/
evaluated/Gemma4-e4b-it/
```

Qwen3-8B 비교 산출물은 아래 위치에 있습니다.

```text
generated/QWEN3-8b/
evaluated/QWEN3-8B/
```

EXAONE 비교 산출물은 아래 위치에 있습니다.

```text
generated/EXAONE-3.5-7.8B-Instruct/
evaluated/EXAONE-3.5-7.8B-Instruct/sft/
```

## 재현 시 주의사항

1. `configs/train_gemma4_e4b_sft.yaml`의 `cuda_visible_devices`는 실행 서버에 맞게 수정할 수 있습니다.
2. merged model은 디스크를 크게 사용하므로 PR에는 포함하지 않습니다.
3. OpenAI Judge 결과는 judge model 버전, API 상태, thread 수에 따라 일부 달라질 수 있습니다.
4. `prompts/`와 `results/`는 이번 PR 범위에서 제외했으므로 README에서도 재현 필수 입력으로 다루지 않습니다.
