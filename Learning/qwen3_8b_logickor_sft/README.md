# Qwen3-8B LogicKor

Qwen3-8B 기반 LogicKor SFT 모델을 재현/평가 최소 코드 패키지입니다
모델 가중치와 학습 데이터는 Google Drive로 공유드립니다
- 가중치 및 학습데이터 링크: https://drive.google.com/drive/folders/15bH5YiUSgpqKj9z8SV4SePUcTA8xylIw?usp=sharing

## 실험 결과 요약

LogicKor 기준 Qwen3-8B 원본 모델과 SFT 모델을 비교한 결과입니다. 공유드리는 모델은 가장 높은 평균 점수를 보인 `Qwen3-8B SFT` 버전입니다

| 모델/학습 방식 | default | 1-shot | cot-1-shot | 비고 |
|---|---:|---:|---:|---|
| Qwen3-8B Pre-trained | 1.67 | 1.33 | 1.46 | 학습 전 기준선 |
| Qwen3-8B SFT | 5.65 | 6.71 | 5.93 | 공유 대상 best 모델 |
| Qwen3-8B Curriculum SFT | 5.67 | 5.40 | 5.73 | middle warm-up 후 high align |

## 데이터 증강 및 학습 전략

### 데이터 증강

학습 데이터는 LogicKor 문항별로 가장 높은 Judge 점수를 받은 모델 답변을 few-shot 예시로 사용해 증강

- 증강 모델: Claude Sonnet 4.6
- few-shot 원천 데이터: `prompts/logicor_best_of_default_sft.jsonl`
- few-shot 구성: 각 질문별 최고 점수 모델 답변 기반
- 증강 프롬프트: `prompts/logicor_fewshot_augmentation_prompt.md`
- 생성 방식: 같은 category의 few-shot 3~6개를 프롬프트에 주입하고, 동일 schema의 신규 `questions` / `references` 샘플 생성

증강 시에는 few-shot 문장 복사를 금지하고, 원본 LogicKor의 category, 난이도, 2-turn 대화 구조를 유지하도록 제한함

### 학습 전략

Qwen3-8B를 기반으로 `logickor_sft_high_converted.jsonl` 데이터에 대해 LoRA SFT를 수행함

- base model: `Qwen/Qwen3-8B`
- 학습 방식: LoRA SFT
- 주요 설정: `configs/train_qwen3_8b_sft.yaml`
- 최종 공유 대상: `Qwen3-8B SFT` 버전

## 1. 구성

### 포함

```text
configs/          학습 config
train/            LoRA SFT 학습 코드
logickor_eval/    LogicKor 생성, Judge 평가, 점수 집계 코드
requirements/     학습/평가 가상환경 핵심 패키지 목록
scripts/          학습부터 scoring까지 실행 예시 스크립트
prompts/          데이터 증강에 사용한 프롬프트와 few-shot 예시 셋
```

## 2. Google Drive에서 받을 파일

```text
학습 데이터:
  data/logickor_sft_high_converted.jsonl

학습 완료 모델 예시:
  models/qwen3_8b_sft_high/adapter/
  models/qwen3_8b_sft_high/merged/
```

평가만 수행하려면 `models/qwen3_8b_sft_high/merged/`가 필요
재학습까지 수행하려면 `data/logickor_sft_high_converted.jsonl`이 필요함

## 3. 가상환경

학습과 추론/평가 환경을 분리해서 진행

| 환경 | 용도 | requirements |
|---|---|---|
| `etri` | LoRA SFT 학습 | `requirements/etri-training.txt` |
| `etri-infer` | vLLM 생성, OpenAI Judge, scoring | `requirements/etri-infer.txt` |

### 학습 환경 설치

```bash
conda create -n etri python=3.12 -y
conda activate etri
pip install -r requirements/etri-training.txt

# CUDA 12.8 환경에서 사용한 PyTorch 예시
pip install --upgrade --force-reinstall \
  --index-url https://download.pytorch.org/whl/cu128 \
  torch torchvision torchaudio
```

### 평가 환경 설치

```bash
conda create -n etri-infer python=3.12 -y
conda activate etri-infer
pip install -r requirements/etri-infer.txt
```

> 실제 CUDA/드라이버/vLLM 조합에 따라 PyTorch와 vLLM 설치 버전은 조정이 필요할 수 있음

## 4. 디렉토리 배치

모델 가중치와 학습 데이터를 아래처럼 배치

```text
qwen3_8b_logickor_sft/
├── data/
│   └── logickor_sft_high_converted.jsonl
└── models/
    └── qwen3_8b_sft_high/
        ├── adapter/
        └── merged/
```

## 5. 학습 방법

학습은 `etri` 환경에서 실행

```bash
conda activate etri

bash scripts/train.sh \
  configs/train_qwen3_8b_sft.yaml \
  runs/qwen3_8b_sft_high
```

동일 명령을 직접 쓰면 다음과 같음

```bash
python train/train_lora.py \
  --config configs/train_qwen3_8b_sft.yaml \
  --output-dir runs/qwen3_8b_sft_high \
  --seed 42
```

학습이 완료되면 다음 산출물이 생성됨

```text
runs/qwen3_8b_sft_high/adapter/       LoRA adapter
runs/qwen3_8b_sft_high/merged/        base + adapter 병합 모델
runs/qwen3_8b_sft_high/run_meta.json  학습 메타데이터
```

## 6. LogicKor 생성

평가용 생성은 `etri-infer` 환경에서 실행

```bash
conda activate etri-infer

bash scripts/generate.sh models/qwen3_8b_sft_high/merged
```

직접 실행 예시는 다음과 같음

```bash
python logickor_eval/generator.py \
  --model models/qwen3_8b_sft_high/merged \
  --gpu_devices 0 \
  --model_len 4096
```

`generator.py`는 `logickor_eval/questions.jsonl`을 읽고, 현재 작업 디렉토리 기준 `generated/<model-path>/` 아래에 결과를 저장함

## 7. OpenAI Judge 평가

보안을 위해 OpenAI API key는 코드나 shell script에 직접 쓰지 말고 환경변수로 설정 권장

```bash
conda activate etri-infer
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"

bash scripts/evaluate.sh generated/models/qwen3_8b_sft_high/merged
```

직접 실행 예시는 다음과 같음

```bash
python logickor_eval/evaluator.py \
  -o generated/models/qwen3_8b_sft_high/merged \
  -k "$OPENAI_API_KEY" \
  -j gpt-4.1 \
  -t 30
```

평가 결과는 현재 작업 디렉토리 기준 `evaluated/<model-output-relative-path>/`에 저장됨

## 8. Scoring

```bash
conda activate etri-infer

bash scripts/score.sh 'evaluated/models/qwen3_8b_sft_high/merged/*.jsonl'
```

직접 실행 예시는 다음과 같음

```bash
python logickor_eval/score.py \
  -p 'evaluated/models/qwen3_8b_sft_high/merged/*.jsonl'
```

출력은 category별 single-turn/multi-turn 점수와 전체 평균 점수임

## 9. 재현 시 주의사항

1. `configs/train_qwen3_8b_sft.yaml`의 `cuda_visible_devices`는 실행 환경에 맞게 수정이 필요할 수 있음
2. merged model은 디스크를 크게 사용함. LoRA adapter만 공유하거나 보관할 경우 `train/merge_adapter.py`로 필요 시 병합할 수 있음
3. 평가 결과는 OpenAI Judge 모델/버전, thread 수, API 상태에 따라 약간 달라질 수 있음(defalut judge model: **gpt-4.1**)

## 10. 참고

- LogicKor 원본 저장소: https://github.com/instructkr/LogicKor
- 본 패키지의 `logickor_eval/`은 재현 편의를 위한 최소 평가 코드임
