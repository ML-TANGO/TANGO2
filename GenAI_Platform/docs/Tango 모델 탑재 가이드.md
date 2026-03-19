# Tango 모델 탑재 가이드

> 📌 **이 문서는 외부 협력 기관 개발자를 위한 기술 요구사항 문서입니다.** Tango GenAI 플랫폼에 LLM 모델을 탑재하기 전에 반드시 확인하고 준수해야 할 조건들을 정리합니다.
> 

# 0. 시작하기 전에

## 0.1 이 문서의 목적

본 문서는 **외부 협력 기관 또는 자체 파인튜닝 결과물을 보유한 개발자**가 Tango GenAI 플랫폼에 LLM 모델을 탑재할 때 사전에 충족해야 할 기술 요건을 안내합니다.

모델 탑재 시도 전에 본 문서의 체크리스트(부록)를 먼저 확인하시기 바랍니다.

## 0.2 대상 독자

- 사전 학습된 외부 LLM 모델을 플랫폼에 등록하려는 개발자
- 플랫폼 내 파인튜닝 기능을 통해 생성된 모델을 서빙하려는 개발자
- LoRA 파인튜닝 결과물을 플랫폼에 탑재하려는 개발자

## 0.3 용어 정리

| 용어 | 설명 |
| --- | --- |
| **LLM** (Large Language Model) | GPT, LLaMA 등 대규모 텍스트 데이터로 학습된 언어 모델 |
| **LoRA** (Low-Rank Adaptation) | 기존 모델의 일부 레이어만 추가 학습하는 경량 파인튜닝 기법. 전체 모델 대비 훨씬 적은 자원으로 특화 학습 가능 |
| **Adapter 모델** | LoRA 파인튜닝 결과물. 베이스 모델과 별도로 저장되는 경량 가중치 파일 |
| **Full 모델** | LoRA 없이 전체 가중치를 보유한 원본 또는 Full Fine-tuning 모델 |
| **safetensors** | Hugging Face에서 만든 안전하고 빠른 모델 가중치 파일 포맷 (`.safetensors`) |
| **vLLM** | LLM 추론(inference)을 빠르게 처리하기 위한 오픈소스 서빙 엔진. 플랫폼의 플레이그라운드에서 사용 |
| **DeepSpeed** | 대규모 모델 학습을 효율적으로 수행하기 위한 Microsoft의 최적화 라이브러리 |
| **ZeRO** | DeepSpeed의 메모리 최적화 전략. Stage 1~3으로 메모리 절약 수준이 달라짐 |
| **탑재** | 모델 파일을 플랫폼에 등록하고 서빙 가능한 상태로 배포하는 행위 |
| **QLoRA** (Quantized LoRA) | 모델을 4-bit로 양자화한 상태에서 LoRA 파인튜닝을 수행하는 기법. 메모리 사용량을 대폭 줄여 단일 GPU에서도 대형 모델 학습 가능 |
| **Gradient Checkpointing** | 학습 중 중간 activation을 저장하지 않고 역전파 시 재계산하여 VRAM 사용량을 줄이는 기법. 속도는 소폭 감소하나 메모리 효율이 크게 향상됨 |

## 0.4 사전 요건

본 문서를 따라 진행하려면 아래 항목에 대한 기본적인 이해가 필요합니다.

- Hugging Face `transformers` 모델 포맷 (`safetensors`, `config.json` 등)
- LoRA(Low-Rank Adaptation) 파인튜닝 개념
- 쿠버네티스(Kubernetes) 기반 컨테이너 서비스 환경

## 0.5 현재 엔진 버전 정보

> ℹ️ **최종 업데이트: 2026-03-13**
> 

| 구성 요소 | 버전 |
| --- | --- |
| vLLM (배포) | `0.16.0` |
| transformers | `4.57.6` (`>=4.52.4, <5.0.0`) |
| torch | `2.5.1` (`>=2.5.1, <2.6.0`) |
| PEFT | `0.18.1` |
| DeepSpeed | `0.18.7` |
| bitsandbytes | `>=0.45.0` |
| CUDA | `12.4.1` |

---

# 1. 개요

## 1.1 적용 범위

본 문서는 다음 시나리오에 적용됩니다.

- 사전 학습된 원본 모델(Full Model)을 플랫폼에 탑재하는 경우
- LoRA 파인튜닝 결과물(Adapter 모델)을 플랫폼에 탑재하는 경우
- 플랫폼 내 파인튜닝 기능을 통해 생성된 모델을 플레이그라운드에서 서빙하는 경우

## 1.2 전체 요건 구성

| 섹션 | 내용 |
| --- | --- |
| **1.3 지원 모델 범위** | 파인튜닝 + 배포 검증 완료된 모델 계열 및 버전 |
| **1.4 제한 사항** | 멀티모달, MoE, 모델 크기 제한, 양자화 지원 범위 |
| **2. 필수 파일 구조** | 모델 탑재 시 요구되는 파일 목록 및 디렉토리 구조 |
| **3. config.json 필수 내용** | 모델 설정 파일의 필수 필드 및 유의사항 |
| **4. Tokenizer 조건** | 토크나이저 로드 조건 및 채팅 템플릿 처리 방식 |
| **5. vLLM 호환 조건** | 플레이그라운드 서빙 엔진의 아키텍처 지원 범위 |
| **6. stop_token_ids 조건** | 모델 계열별 생성 종료 토큰 설정 |
| **7. DeepSpeed 설정** | 파인튜닝 시 적용되는 기본 설정 및 정밀도 조건 |
| **8. 데이터셋 조건** | 파인튜닝용 데이터셋 포맷 요건 |
| **부록** | 전체 요건 체크리스트 |

## 1.3 파인튜닝 + 배포 지원 모델 범위

아래는 현재 플랫폼에서 파인튜닝 및 배포까지 검증 완료된 모델 계열입니다.

| 모델 계열 | 지원 버전 | 비고 |
| --- | --- | --- |
| Qwen 2.5 | 0.5B ~ 72B |  |
| Qwen 3 | 0.6B ~ 32B (Dense) | `auto_target_modules=1` 사용 권장 |
| LLaMA 3 / 3.1 / 3.2 / 3.3 | 1B ~ 70B | text 모델만 (vision 제외) |
| Gemma 2 | 2B ~ 27B |  |
| Gemma 3 | 1B ~ 27B (text) | text 모델만, transformers `>=4.50.0` 필요 |
| Mistral / Mixtral | 7B ~ 8x22B | Dense 및 MoE |
| Phi-3 / Phi-3.5 | 3.8B ~ 14B |  |
| Yi 1.5 | 6B ~ 34B |  |
| DeepSeek-V2 | 16B (Lite) ~ 236B | MoE, multi-GPU 필요 |
| Baichuan 2 | 7B ~ 13B |  |

## 1.4 제한 사항

| 항목 | 상세 |
| --- | --- |
| **멀티모달 모델** | LLaMA 4 Scout/Maverick, Qwen-VL 등 vision 모델은 미지원 (text-only 파인튜닝만 가능) |
| **Qwen 3 MoE** | 30B-A3B 등 MoE 변형은 DeepSpeed 호환성 미검증 |
| **transformers 5.x 전용 모델** | `transformers<5.0.0` 제약으로 5.x에서만 추가된 아키텍처는 미지원 |
| **모델 크기 제한** | 단일 GPU(48GB 기준): Dense 최대 ~8B (LoRA + gradient checkpointing + bf16) |
| **양자화 파인튜닝** | QLoRA(4-bit) 지원 (`bitsandbytes>=0.45.0`). GPTQ/AWQ는 inference only |

---

# 2. 필수 파일 구조

모델 디렉토리 안에 아래 파일들이 반드시 포함되어야 합니다. 탑재 시 플랫폼이 자동으로 파일 존재 여부를 검사합니다.
(Huggingface에서 공개 모델을 직접 다운로드할 경우에는 아래 파일들이 기본적으로 포함되어 있습니다)

```markdown
model_dir/
├── config.json                  ← 필수
├── model.safetensors            ← 필수 (또는 model-00001-of-NNNNN.safetensors 샤딩)
├── model.safetensors.index.json ← 샤딩된 모델 파일을 사용할 경우 필수
├── tokenizer.json               ← 필수 (tokenizer 로드에 사용)
├── tokenizer_config.json        ← 필수
├── generation_config.json       ← 권장
└── special_tokens_map.json      ← 권장
```

---

# 3. config.json 필수 내용

`config.json`은 플랫폼이 모델을 로드하고 LoRA 타겟 레이어를 탐지할 때 사용하는 핵심 파일입니다. 아래 필드들을 반드시 포함해야 합니다.

```json
{
    "architectures": ["LlamaForCausalLM"],
    "model_type": "llama",
    "hidden_size": 4096,
    "num_attention_heads": 32,
    "num_hidden_layers": 32,
    "vocab_size": 32000,
    "torch_dtype": "float16",
    "transformers_version": "4.xx.x"
}
```

| 필드 | 필수 여부 | 설명 |
| --- | --- | --- |
| `architectures` | ✅ 필수 | 모델 클래스 이름 (예: `LlamaForCausalLM`) |
| `model_type` | ✅ 필수 | 아키텍처 타입. LoRA 타겟 모듈 자동 탐지에 사용 |
| `torch_dtype` | 권장 | 모델 정밀도 설정 |
| `transformers_version` | 권장 | 호환 버전 명시 |

참고: **`model_type` 기준 LoRA 적용 레이어 (static 모드 기준, `auto_target_modules=0`):**

| model_type | LoRA 적용 레이어 |
| --- | --- |
| `llama`, `llama2` | q_proj, k_proj, v_proj, o_proj |
| `qwen`, `deepseek-r1`, `mpt` | q_proj, k_proj, v_proj, o_proj |
| `falcon` | q_proj, k_proj, v_proj, out_proj |
| `gpt2`, `gptj`, `gpt_neo` | c_attn, c_proj |
| `gpt_neox` | query_key_value, dense |
| `opt` | q_proj, k_proj, v_proj, out_proj |
| `bloom` | query_key_value, dense |

> 💡 **`auto_target_modules` 옵션:** 위 목록에 없는 모델이거나 최신 아키텍처를 사용하는 경우, 플랫폼내부에서 `auto_target_modules=1` 설정을 사용하여 PEFT가 모델의 모든 linear 레이어를 자동으로 탐지하여 LoRA를 적용하고 있습니다.
> 

---

# 4. Tokenizer 조건

토크나이저는 파인튜닝과 플레이그라운드 서빙 모두에서 사용됩니다.

**필수 조건:**

- `tokenizer.json` 또는 `vocab.json` + `merges.txt` 형식 모두 지원 (플랫폼이 자동 판별)
- `eos_token`이 반드시 정의되어 있어야 함 (패딩 토큰 설정에 사용됨)
- 토크나이저가 일반 텍스트를 처리할 수 있어야 함

> 💡 **참고:** 기존에는 토크나이저의 `pad_token`을 항상 `eos_token`으로 덮어썼으나, 업데이트 이후 `pad_token`이 이미 정의된 경우에는 기존 값을 유지합니다. 모델 자체에 `pad_token`이 정의되어 있다면 별도 조치 없이 그대로 사용됩니다.
> 

**채팅 템플릿:**

`tokenizer_config.json`에 `chat_template`이 정의되어 있으면 플레이그라운드에서 자동으로 활용됩니다. 없는 경우 raw 텍스트 입력으로 폴백 처리됩니다.

---

# 5. vLLM 호환 조건 (플레이그라운드)

플랫폼의 플레이그라운드는 **vLLM v0.8.0+** 기반으로 업그레이드되었습니다. 이전 버전(v0.5.4) 대비 지원 아키텍처가 크게 확대되었습니다.

| 지원 여부 | 아키텍처 예시 |
| --- | --- |
| ✅ 지원 | LLaMA, LLaMA-2, LLaMA-3, **LLaMA 4** 계열 |
| ✅ 지원 | Mistral, Mixtral |
| ✅ 지원 | Qwen, Qwen2, **Qwen3** |
| ✅ 지원 | GPT-2, GPT-J, GPT-NeoX |
| ✅ 지원 | Falcon, BLOOM, OPT |
| ✅ 지원 | DeepSeek (일부) |
| ✅ 지원 | **Gemma 2/3** |
| ⚠️ 조건부 지원 | Custom architecture (`trust_remote_code=True` 필요) |

> ⚠️ **주요 제한사항:** 현재 `max_model_len`이 **96으로 고정**되어 있습니다. 이는 실제 서비스 용도로는 매우 짧은 값으로, 긴 컨텍스트가 필요한 모델은 정상 동작하지 않을 수 있습니다. 조정이 필요한 경우 플랫폼 담당자에게 문의하세요.
> 

---

# 6. stop_token_ids 조건

플레이그라운드에서 모델이 응답 생성을 멈추는 시점을 결정하는 종료 토큰 ID입니다.

> ⚠️ **주요 제한사항:** 현재 플랫폼은 **LLaMA-3 계열의 종료 토큰 ID (`128001`, `128009`)를 기본값으로 사용**합니다. LLaMA-3 이외의 모델을 사용할 경우 답변이 제대로 끊기지 않는 문제가 발생할 수 있습니다.
> 

**모델 계열별 EOS Token ID 참고:**

| 모델 계열 | EOS Token ID |
| --- | --- |
| LLaMA-3 | 128001, 128009 |
| LLaMA-2 | 2 |
| Mistral | 2 |
| Qwen2 | 151645 |

**LLaMA-3 이외의 모델을 탑재하는 경우,** `stop_token_ids` 설정 변경이 필요합니다. 플랫폼 담당자에게 모델 계열을 알려주시면 맞는 값으로 조정해 드립니다.

---

# 7. DeepSpeed 설정

파인튜닝 시 아래 기본 DeepSpeed 설정이 적용됩니다. 특수한 경우 외에는 별도 수정 없이 사용 가능합니다.

**기본 설정 요약:**

| 항목 | 기본값 | 선택 가능한 값 | 비고 |
| --- | --- | --- | --- |
| 정밀도 (`precision`) | auto | `auto` / `fp16` / `bf16` | auto 설정 시 모델의 `torch_dtype`을 감지하여 자동 전환 |
| ZeRO Stage (`zero_stage`) | 1 | `1` / `2` / `3` | 대형 모델(7B+) multi-GPU 학습 시 Stage 2~3 요청 가능 |
| LoRA 타겟 모듈 | auto (all-linear) | `0`=static / `1`=auto | auto 설정 시 모든 linear 레이어 자동 탐지 |
| Batch size | auto | — | 플랫폼이 자동 설정 |

> 💡 **정밀도 자동 감지:** `precision=auto`(기본값)로 설정하면 플랫폼이 모델의 `config.json`에서 `torch_dtype`을 읽어 fp16/bf16을 자동으로 선택합니다. bf16 전용 모델도 별도 요청 없이 탑재 가능합니다.
> 

**Gradient Checkpointing:**

Gradient Checkpointing이 기본으로 활성화되어 있습니다. 학습 중 activation 메모리를 저장하지 않고 역전파 시 재계산하여 VRAM 사용량을 대폭 절감합니다. 이를 통해 단일 GPU(48GB)에서 Dense ~8B 모델까지 LoRA 파인튜닝이 가능합니다.

> 💡 LoRA와 Gradient Checkpointing을 함께 사용할 때 필요한 `enable_input_require_grads()` 처리는 플랫폼이 자동으로 수행합니다.
> 

**QLoRA (4-bit 양자화 파인튜닝):**

QLoRA를 통해 모델을 4-bit로 양자화한 상태에서 LoRA 파인튜닝을 수행할 수 있습니다 (`bitsandbytes>=0.45.0`). GPTQ/AWQ 양자화는 inference 전용으로 파인튜닝에는 사용할 수 없습니다.

> ⚠️ **주의:** QLoRA 사용 시 모델 로딩 시 `torch_dtype="auto"` 설정으로 모델의 네이티브 dtype(fp16/bf16)으로 로딩되므로 VRAM 사용량이 float32 대비 절반으로 줄어듭니다.
> 

---

# 8. 데이터셋 조건 (파인튜닝 사용 시)

플랫폼의 파인튜닝 기능을 사용할 경우, 학습 데이터셋은 아래 조건을 충족해야 합니다.

플랫폼은 아래 3가지 데이터셋 포맷을 지원합니다. `dataset_format=auto`(기본값)로 설정하면 플랫폼이 자동으로 형식을 감지합니다.

| 포맷 | 필수 컬럼 | 설명 |
| --- | --- | --- |
| `text` | `text` | 일반 텍스트 형식. 기존 방식 |
| `chat` | `messages` | OpenAI 대화 형식 (`role`/`content` 리스트) |
| `instruction` | `instruction`, `output` | Instruction-following 형식. `input` 컬럼은 선택 |

| 조건 | 설명 |
| --- | --- |
| **포맷** | `auto` / `text` / `chat` / `instruction` 중 선택 (기본값: `auto`) |
| **Split** | `train` split이 반드시 존재해야 함 |
| **validation/test** | 없어도 학습 진행 가능 |

---

# 9. 탑재 시나리오 예시

## 사전 학습된 외부 모델 탑재 (Qwen2.5-7B)

> **상황:** 협력 기관이 Hugging Face에서 받은 Qwen2.5-7B 모델을 그대로 플랫폼에 탑재하고 플레이그라운드에서 서빙하려는 경우
> 

**① 파일 구성 확인**

Hugging Face에서 다운로드한 디렉토리를 확인합니다. `config.json`, `model.safetensors`, `tokenizer.json`, `tokenizer_config.json`이 모두 있는지 체크합니다.

```
qwen2.5-7b/
├── config.json                     ✅ 필수
├── model-00001-of-00004.safetensors ✅ 필수 (샤딩)
├── model-00002-of-00004.safetensors
├── model-00003-of-00004.safetensors
├── model-00004-of-00004.safetensors
├── model.safetensors.index.json    ✅ 샤딩 시 필수
├── tokenizer.json                  ✅ 필수
├── tokenizer_config.json           ✅ 필수
├── generation_config.json          ✅ 권장
└── special_tokens_map.json         ✅ 권장
```

**② config.json 확인**

`config.json`을 열어 아래 필드들을 확인합니다.

```json
{
  "architectures": ["Qwen2ForCausalLM"],
  "model_type": "qwen2",
  "torch_dtype": "bfloat16"
}
```

- `model_type`이 `"qwen2"`로 지원 목록에 포함되어 있으므로 LoRA 파인튜닝 시 static 모드도 사용 가능
- `torch_dtype`이 `"bfloat16"` → `precision=auto`(기본값) 설정 시 플랫폼이 자동으로 bf16으로 로드

**③ 플랫폼 담당자에게 사전 전달 사항**

- 모델명: `Qwen2.5-7B`
- 모델 계열: Qwen2 → stop_token_ids 변경 필요 (`151645`로 설정 요청)
- 컨텍스트 길이: 긴 컨텍스트 사용 예정 → `max_model_len` 조정 요청

**④ 탑재 후 확인**

플레이그라운드에서 간단한 프롬프트로 동작을 확인합니다. 응답이 정상적으로 끊기는지(stop_token_ids 적용 여부)를 특히 확인합니다.

---

# 부록. 탑재 전 체크리스트

모델 탑재 전 아래 항목을 모두 확인하세요.

| 항목 | 조건 | 확인 |
| --- | --- | --- |
| **필수 파일** | `config.json`  • `model.safetensors` (Full 모델) 또는 `adapter_config.json`  • `adapter_model.safetensors` (LoRA) | ☐ |
| **tokenizer 파일** | `tokenizer.json`, `tokenizer_config.json` 존재 | ☐ |
| **config.json** | `model_type`, `architectures` 필드 포함 | ☐ |
| **model_type** | `auto_target_modules=1`(기본값) 사용 시 불필요. static 모드 사용 시 지원 목록(3장) 확인 | ☐ |
| **eos_token** | tokenizer에 `eos_token` 정의됨 | ☐ |
| **vLLM 호환** | vLLM v0.8.0+ 지원 아키텍처 확인 (LLaMA 4, Qwen3, Gemma 2/3 포함) | ☐ |
| **stop_token_ids** | LLaMA-3 이외 모델이면 담당자에게 변경 요청 | ☐ |
| **정밀도** | `precision=auto` 사용 시 자동 감지. bf16 전용 모델도 별도 요청 불필요 | ☐ |
| **max_model_len** | 긴 컨텍스트 필요 시 담당자에게 조정 요청 | ☐ |
| **데이터셋** | `train` split 존재 확인. 포맷은 text / chat / instruction 중 선택 (파인튜닝 사용 시) | ☐ |
| **지원 모델 범위** | 모델 계열이 지원 목록(1.3장)에 포함되는지 확인. 멀티모달/MoE 제한 사항(1.4장) 확인 | ☐ |
| **모델 크기** | 단일 GPU(48GB): Dense 최대 ~8B. 더 큰 모델은 multi-GPU 또는 QLoRA 검토 필요 | ☐ |