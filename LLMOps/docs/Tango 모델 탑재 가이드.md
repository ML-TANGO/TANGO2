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
| **vLLM** | LLM 추론(inference)을 빠르게 처리하기 위한 오픈소스 서빙 엔진. 플랫폼 **배포(클러스터)** 의 기본 서빙 엔진 |
| **서빙 엔진** | 배포 시 선택하는 추론 런타임. vLLM · llama.cpp · TGI · Ollama · Triton · TensorRT-LLM 6종 (5장 참고) |
| **GGUF** | llama.cpp 계열이 읽는 양자화 모델 파일 포맷. 플랫폼의 양자화 기능이 생성하며 온디바이스·독립 배포에 사용 (10장 참고) |
| **DeepSpeed** | 대규모 모델 학습을 효율적으로 수행하기 위한 Microsoft의 최적화 라이브러리 |
| **ZeRO** | DeepSpeed의 메모리 최적화 전략. Stage 1~3으로 메모리 절약 수준이 달라짐 |
| **탑재** | 모델 파일을 플랫폼에 등록하고 서빙 가능한 상태로 배포하는 행위 |
| **8-bit 로딩 LoRA** | 베이스 모델을 bitsandbytes 8-bit로 양자화해 로드한 상태에서 LoRA 파인튜닝을 수행하는 방식(`load_in_8bit`). 메모리 사용량을 줄여 더 큰 모델을 학습할 수 있음 |
| **Gradient Checkpointing** | 학습 중 중간 activation을 저장하지 않고 역전파 시 재계산하여 VRAM 사용량을 줄이는 기법. 속도는 소폭 감소하나 메모리 효율이 크게 향상됨 |

## 0.4 사전 요건

본 문서를 따라 진행하려면 아래 항목에 대한 기본적인 이해가 필요합니다.

- Hugging Face `transformers` 모델 포맷 (`safetensors`, `config.json` 등)
- LoRA(Low-Rank Adaptation) 파인튜닝 개념
- 쿠버네티스(Kubernetes) 기반 컨테이너 서비스 환경

## 0.5 현재 엔진 버전 정보

> ℹ️ **최종 업데이트: 2026-10-28** (소스 기준 동기화)
>
> 아래 표는 저장소의 **소스 코드(requirements / Dockerfile)** 가 정의하는 진실 값입니다. 컨테이너 내부에서 `pip install` 시점에 해석되는 실제 패치 버전은 빌드 시점에 따라 달라질 수 있으므로, 모델/어댑터를 만들 때는 **허용 범위 안의 최신 안정 버전**을 기준으로 작업해 주세요.

| 구성 요소 | 코드 기준 허용 범위 | 출처 |
| --- | --- | --- |
| CUDA (파인튜닝 베이스) | `12.4.1` | `apps/llm_model/fine_tuning_image/Dockerfile` (`nvidia/cuda:12.4.1-devel-ubuntu22.04`) |
| torch | `>=2.5.1, <2.6.0` | `apps/llm_model/fine_tuning_image/requirements.txt` |
| transformers | `>=4.52.4, <5.0.0` | 동상 |
| PEFT | `>=0.15.0` | 동상 |
| DeepSpeed | `>=0.16.0` | 동상 |
| accelerate | `>=1.5.0` | 동상 |
| bitsandbytes | `>=0.45.0` | 동상 |
| huggingface-hub | `>=0.28.0` | 동상 |
| tokenizers | `>=0.21.0` | 동상 |
| 서빙 엔진 이미지 (배포) | 엔진별 이미지 6종 | `apps/fb_utils/settings.py` 의 `SERVING_ENGINE_IMAGE_MAP` |

> ⚠️ 서빙 엔진은 본 저장소의 파이썬 의존성으로 고정되어 있지 않습니다. 배포 시 스케줄러가 `deployment_llm` 차트를 설치하면서 `apps/fb_utils/settings.py` 의 `SERVING_ENGINE_IMAGE_MAP` 에서 **선택한 엔진의 이미지**를 골라 씁니다. 각 이미지의 빌드 소스는 `libs/fb_image/llm*/Dockerfile` 입니다.
>
> | 엔진 | settings 상수 | 빌드 소스 (베이스) |
> | --- | --- | --- |
> | vLLM | `DEPLOYMENT_LLM_IMAGE` | `libs/fb_image/llm/Dockerfile` (`vllm>=0.8.0`) |
> | llama.cpp | `DEPLOYMENT_LLM_LLAMACPP_IMAGE` | `libs/fb_image/llm_llamacpp/Dockerfile` (`ghcr.io/ggml-org/llama.cpp:full`) |
> | TGI | `DEPLOYMENT_LLM_TGI_IMAGE` | `libs/fb_image/llm_tgi/Dockerfile` (`text-generation-inference:3.3.7`) |
> | Ollama | `DEPLOYMENT_LLM_OLLAMA_IMAGE` | `libs/fb_image/llm_ollama/Dockerfile` (`ollama/ollama:0.32.0`) |
> | Triton | `DEPLOYMENT_LLM_TRITON_IMAGE` | `libs/fb_image/llm_triton/Dockerfile` (`tritonserver:25.06-vllm-python-py3`) |
> | TensorRT-LLM | `DEPLOYMENT_LLM_TENSORRT_IMAGE` | `libs/fb_image/llm_tensorrt/Dockerfile` (`tritonserver:25.06-trtllm-python-py3`) |
>
> 운영 클러스터에서 실제로 쓰이는 엔진 버전은 위 상수가 가리키는 이미지 태그로 확인하세요.

---

# 1. 개요

## 1.1 적용 범위

본 문서는 다음 시나리오에 적용됩니다.

- 사전 학습된 원본 모델(Full Model)을 플랫폼에 탑재하는 경우
- LoRA 파인튜닝 결과물(Adapter 모델)을 플랫폼에 탑재하는 경우
- 플랫폼 내 파인튜닝 기능을 통해 생성된 모델을 **배포/추론** 메뉴에서 서빙하는 경우
- 파인튜닝한 모델을 GGUF 로 양자화해 온디바이스(엣지)·독립 패키지로 배포하는 경우

## 1.2 전체 요건 구성

| 섹션 | 내용 |
| --- | --- |
| **1.3 지원 모델 범위** | 파인튜닝 + 배포 검증 완료된 모델 계열 및 버전 |
| **1.4 제한 사항** | 멀티모달, MoE, 모델 크기 제한, 양자화 지원 범위 |
| **2. 필수 파일 구조** | 모델 탑재 시 요구되는 파일 목록 및 디렉토리 구조 |
| **3. config.json 필수 내용** | 모델 설정 파일의 필수 필드 및 유의사항 |
| **4. Tokenizer 조건** | 토크나이저 로드 조건 및 채팅 템플릿 처리 방식 |
| **5. 서빙 엔진 호환 조건** | 배포 시 선택하는 서빙 엔진과 vLLM 아키텍처 지원 범위, `max_model_len` |
| **6. stop_token_ids 조건** | 모델 계열별 생성 종료 토큰 설정 |
| **7. DeepSpeed 설정** | 파인튜닝 시 적용되는 기본 설정 및 정밀도 조건 |
| **8. 데이터셋 조건** | 파인튜닝용 데이터셋 포맷 요건 |
| **9. 탑재 시나리오 예시** | 외부 모델 탑재 예시 |
| **10. GGUF 양자화** | 온디바이스·독립 배포용 양자화 패키지 |
| **11. 폐쇄망(HF 오프라인) 참고** | HF 토큰·공유 HF 캐시·가중치 사전 스테이징 |
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
| **멀티모달 모델** | 범용 VLM(Qwen-VL, LLaMA 4 Scout/Maverick 등)의 탑재·파인튜닝은 지원하지 않습니다 — 모델 생성 화면의 `Multimodal` 선택지가 비활성입니다(내부 LLaVA 2-stage 파인튜닝 백엔드는 `apps/llm_model` 에 있으나 화면에서 막혀 있음). **SDS 도메인 VLM**(CLIP + LLaMA-3.1 계열, 협력기관 외부 컨테이너 `eva-vlm`)은 모델 생성 시 `Domain > SDS` 로 학습·추론·배포를 지원합니다. SDM/SDF 도메인은 비활성입니다. |
| **Qwen 3 MoE** | 30B-A3B 등 MoE 변형은 DeepSpeed 호환성 미검증 |
| **transformers 5.x 전용 모델** | `transformers<5.0.0` 제약으로 5.x에서만 추가된 아키텍처는 미지원 |
| **모델 크기 제한** | 단일 GPU(48GB 기준): Dense 최대 ~8B (LoRA + gradient checkpointing + bf16) |
| **양자화 파인튜닝** | 8-bit 로딩 LoRA 지원 (`load_in_8bit`, `bitsandbytes>=0.45.0`). 4-bit(QLoRA)·GPTQ/AWQ 학습은 지원하지 않습니다. 배포용 GGUF 양자화는 10장 참고 |

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

참고: **아키텍처별 LoRA 적용 레이어 (static 모드 기준, `auto_target_modules=0`)** — 모델 클래스 이름(예: `LlamaForCausalLM`)에 아래 키워드가 포함되는지로 고릅니다:

| 클래스 이름 키워드 | LoRA 적용 레이어 |
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

토크나이저는 파인튜닝과 배포(서빙) 모두에서 사용됩니다.

**필수 조건:**

- `tokenizer.json` 또는 `vocab.json` + `merges.txt` 형식 모두 지원 (플랫폼이 자동 판별)
- `eos_token`이 반드시 정의되어 있어야 함 (패딩 토큰 설정에 사용됨)
- 토크나이저가 일반 텍스트를 처리할 수 있어야 함

> 💡 **참고:** 기존에는 토크나이저의 `pad_token`을 항상 `eos_token`으로 덮어썼으나, 업데이트 이후 `pad_token`이 이미 정의된 경우에는 기존 값을 유지합니다. 모델 자체에 `pad_token`이 정의되어 있다면 별도 조치 없이 그대로 사용됩니다.
> 

**채팅 템플릿:**

`tokenizer_config.json`에 `chat_template`이 정의되어 있으면 배포(서빙) 시 자동으로 활용됩니다. 없는 경우 raw 텍스트 입력으로 폴백 처리됩니다.

---

# 5. 서빙 엔진 호환 조건 (배포/추론)

모델은 **배포** 메뉴에서 클러스터 배포를 만들 때 서빙 엔진을 골라 띄우고, **추론** 메뉴에서 채팅·데이터셋 추론으로 사용합니다. 선택할 수 있는 엔진은 6종입니다(이미지 출처는 0.5절).

| 엔진 | 입력 모델 형식 | 비고 |
| --- | --- | --- |
| vLLM | HF/safetensors (LoRA 어댑터 포함) | 기본 엔진. VLM 이미지 입력 지원(아래) |
| llama.cpp | GGUF 직접, 또는 HF 모델을 서빙 시 변환 | 10장의 양자화 결과(GGUF)를 서빙할 때 사용 |
| TGI | HF/safetensors | |
| Ollama | HF/safetensors (모델스토어 등록 후 서빙) | |
| Triton | HF/safetensors (Triton + vLLM backend) | |
| TensorRT-LLM | HF/safetensors (`trtllm-serve`, PyTorch 백엔드) | 사전 엔진 빌드(AOT) 불필요 |

아래 아키텍처 표는 기본 엔진인 **vLLM v0.8.0+**(`libs/fb_image/llm/Dockerfile` 의 `vllm>=0.8.0`) 기준입니다.

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

> ⚠️ **`max_model_len` (컨텍스트 길이):** vLLM 엔진은 `max_model_len` 을 모델 `config.json` 의 컨텍스트 길이 필드(`max_position_embeddings`, `max_sequence_length`, `max_seq_len`, `seq_length`, `n_positions`, `model_max_length` 순으로 확인)에서 자동으로 정하되, **상한 8192** 로 자릅니다. 32K/128K 컨텍스트 모델도 KV 캐시가 GPU 메모리를 넘지 않도록 8192 로 기동되며, 이보다 짧은 모델은 config 값을 그대로 씁니다. 필드를 읽지 못하면 8192 를 씁니다. (`apps/fb_scheduler/helm_chart/deployment_llm/src/llm/playground.py`)
> 

**VLM(이미지 입력):** vLLM 엔진은 모델에 `AutoProcessor` 의 image processor 가 붙으면 VLM 으로 판별해 이미지 입력 추론을 받습니다. 요청당 이미지는 기본 최대 4장(`LLM_MAX_IMAGES_PER_PROMPT`), 1장당 원본 12MB(`LLM_MAX_IMAGE_BYTES`)까지이며, 이미지 토큰도 위 8192 컨텍스트 안에서 소비됩니다.


---

# 6. stop_token_ids 조건

배포(서빙)에서 모델이 응답 생성을 멈추는 시점을 결정하는 종료 토큰 ID입니다.

> ⚠️ **주요 제한사항:** 현재 플랫폼의 vLLM 엔진은 **LLaMA-3 계열의 종료 토큰 ID (`128001`, `128009`)를 기본값으로 사용**합니다(`deployment_llm/src/llm/playground.py` 의 `SamplingParams`). LLaMA-3 이외의 모델을 사용할 경우 답변이 제대로 끊기지 않는 문제가 발생할 수 있습니다.
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

**8-bit 로딩 LoRA (양자화 파인튜닝):**

파인튜닝 설정의 8-bit 옵션(`load_in_8bit=1`)을 켜면 베이스 모델을 bitsandbytes 8-bit로 양자화해 로드한 상태에서 LoRA 파인튜닝을 수행합니다 (`bitsandbytes>=0.45.0`). 4-bit(QLoRA)와 GPTQ/AWQ 양자화 학습은 지원하지 않습니다.

> 💡 **참고:** 8-bit 옵션과 관계없이 모델은 `torch_dtype="auto"` 로 로딩되어 모델의 네이티브 dtype(fp16/bf16)을 그대로 쓰므로, float32 로딩 대비 VRAM 사용량이 절반 수준입니다.
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

> 💡 원본이 CSV / TXT / Parquet 이면 드라이브의 데이터셋 상세에서 **포맷 변환**(빌트인 전처리 `builtin_transform`)으로 `text` / `instruction` / `chat` 형식의 JSON·JSONL 을 원본 옆에 만들 수 있습니다. 컬럼은 이름 규칙(예: `instruction`·`prompt`·`question` → 입력, `output`·`response`·`answer` → 출력)으로 자동 매핑됩니다.

---

# 9. 탑재 시나리오 예시

## 사전 학습된 외부 모델 탑재 (Qwen2.5-7B)

> **상황:** 협력 기관이 Hugging Face에서 받은 Qwen2.5-7B 모델을 그대로 플랫폼에 탑재하고 배포/추론 메뉴에서 서빙하려는 경우
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
- 컨텍스트 길이: vLLM 엔진은 config 에서 자동 유도하되 8192 로 상한 → 8192 를 넘는 컨텍스트가 필요하면 사전 협의

**④ 탑재 후 확인**

**배포** 메뉴에서 클러스터 배포를 시작한 뒤, **추론** 메뉴에서 간단한 프롬프트로 동작을 확인합니다. 응답이 정상적으로 끊기는지(stop_token_ids 적용 여부)를 특히 확인합니다.

---

# 10. GGUF 양자화 (온디바이스·독립 배포용)

모델 상세의 **양자화** 탭에서 커밋된 모델을 llama.cpp GGUF 로 변환합니다. 변환은 플랫폼 소유 외부 컨테이너 `convert-llamacpp`(`apps/convert/`, manifest 1.1.3)가 수행하며, 플랫폼 기동 시 자동 등록됩니다.

| 항목 | 내용 |
| --- | --- |
| 입력 | 플랫폼 모델의 커밋(merged HF 모델). SDS(eva-vlm) 모델은 커밋을 고르면 LoRA 를 베이스에 merge 한 뒤 변환 |
| 양자화 타입 | `Q4_K_M` / `Q5_K_M` / `Q6_K` (f16 GGUF 를 거쳐 양자화) |
| 산출물(포팅 패키지) | `model.gguf` + `inference.py` + `run.sh` + `config.json` + `metadata.json`. SDS(VLM)는 비전 인코더 `mmproj`(f16)를 함께 담음 |
| 사용처 | 온디바이스(엣지) 배포, 독립 패키지(Standalone) 배포, llama.cpp 엔진 클러스터 배포 |
| 이력 관리 | 양자화 탭의 이력 표에서 삭제하면 이력 행과 포팅 패키지(스토리지)가 함께 정리됨 |

> 💡 온디바이스·독립 배포는 이 양자화 패키지(GGUF)가 있어야 시작할 수 있습니다. 변환은 CPU 작업(GPU 0)이며, SDS 8B 모델은 merge + 변환에 시간이 걸립니다(manifest `timeout_seconds: 7200`).
>
> SDS(eva-vlm) merge 는 베이스(LLaMA-3.1-8B·CLIP-336)를 **오프라인 HF 캐시(`/hf-cache`)에서만** 읽습니다 — 11장의 사전 스테이징이 필요합니다.

---

# 11. 폐쇄망(HF 오프라인) 환경 참고

- **HF 토큰은 선택입니다.** values 의 `global.jfb.settings.huggingface.token` 을 비워 두면 기동 시 HF login 을 건너뜁니다. Hugging Face 모델·gated/private 저장소를 쓸 때만 입력합니다(`devops/INSTALL.md`).
- **외부 컨테이너 잡은 HF 에 접속하지 않습니다.** SDS 학습(`eva-vlm-train`)·SDS 양자화(`convert-llamacpp`) 등은 manifest env 가 `HF_HUB_OFFLINE=1` 이고, 워크스페이스 네임스페이스의 공유 HF 캐시 PVC(`hf-model-cache-pvc`, values 의 `global.jfb.volume.hfModelCache`)를 `/hf-cache` 로 **읽기 전용** 마운트해 가중치를 읽습니다.
- 따라서 베이스 가중치는 운영자가 미리 받아 둡니다: `devops/hf-prefetch/run.sh <워크스페이스-네임스페이스> [모델 repo id...]` (기본 목록 = SDS VLM 학습용 `openai/clip-vit-large-patch14-336`, `meta-llama/Llama-3.1-8B-Instruct`). 스크립트가 gated 저장소용 토큰 주입, `.bin` → `safetensors` 변환, 파일 권한(0644) 보정까지 처리합니다.
- 가중치가 캐시에 없으면 SDS 학습 컨테이너는 모델을 올리지 못해 `/health` 가 준비 상태가 되지 않고(학습이 시작되지 않음), SDS 양자화의 merge 도 베이스를 읽지 못해 진행되지 않습니다.

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
| **서빙 엔진 호환** | 사용할 엔진 확인(5장). vLLM 이면 v0.8.0+ 지원 아키텍처 확인 (LLaMA 4, Qwen3, Gemma 2/3 포함) | ☐ |
| **stop_token_ids** | LLaMA-3 이외 모델이면 담당자에게 변경 요청 | ☐ |
| **정밀도** | `precision=auto` 사용 시 자동 감지. bf16 전용 모델도 별도 요청 불필요 | ☐ |
| **max_model_len** | vLLM 은 config 에서 자동 유도(상한 8192). 8192 초과가 필요하면 사전 협의 | ☐ |
| **데이터셋** | `train` split 존재 확인. 포맷은 text / chat / instruction 중 선택 (파인튜닝 사용 시) | ☐ |
| **지원 모델 범위** | 모델 계열이 지원 목록(1.3장)에 포함되는지 확인. 멀티모달/MoE 제한 사항(1.4장) 확인 | ☐ |
| **모델 크기** | 단일 GPU(48GB): Dense 최대 ~8B. 더 큰 모델은 multi-GPU 또는 8-bit 로딩 LoRA 검토 필요 | ☐ |
| **GGUF 양자화** | 온디바이스·독립 배포가 목적이면 llama.cpp 변환 가능한 아키텍처인지 확인(10장) | ☐ |
| **폐쇄망** | HF 접근이 막힌 환경이면 토큰 비움 + 공유 HF 캐시 사전 스테이징(11장) | ☐ |