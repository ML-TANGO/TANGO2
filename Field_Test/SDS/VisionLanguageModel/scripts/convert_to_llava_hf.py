#!/usr/bin/env python3
"""
convert_to_llava_hf.py — 커스텀 VLM 체크포인트 → HuggingFace LLaVA 포맷 변환
vLLM 또는 transformers LlavaForConditionalGeneration 에서 직접 로드 가능

변환 내용:
  - adapter_model.safetensors (LoRA) → base LLM 에 merge
  - projector.bin                    → multi_modal_projector.linear_{1,2} 로 변환
  - openai/clip-vit-large-patch14-336 → vision_tower 포함

지원 프로젝터:
  LlavaMultiModalProjector 는 linear_1 → ACT2FN[projector_hidden_act] → linear_2
  로 고정돼 있다. 활성 함수가 설정 가능하고 ACT2FN["linear"] 가 항등 함수이므로
  다음 두 구조를 정확히 표현할 수 있다.

    mlp2x_gelu  act="gelu"    linear_1=proj.0, linear_2=proj.2
    linear      act="linear"  linear_1=proj,   linear_2=항등 행렬 (출력 동치)

  나머지 세 구조는 대상 포맷에 등가 표현이 없어 거부한다. mlp3x_gelu 는 비선형이
  2개 필요하나 이 프로젝터에는 1개뿐이고, cross_attn 과 qformer 는 학습된 쿼리와
  cross-attention 을 담을 텐서가 없으며 이미지 토큰 수도 패치 수와 달라진다.
  근거는 transformers/models/llava/modeling_llava.py 이다.

사용법:
  python scripts/convert_to_llava_hf.py \\
    --ckpt_dir   /home/ywlee/SSD/checkpoints/clip_llama31_lora_marine_sds_lora_ko \\
    --llm_path   /home/ywlee/Llama-3.1-8B-Instruct \\
    --clip_model openai/clip-vit-large-patch14-336 \\
    --output_dir /home/ywlee/SSD/llava_hf_merged \\
    [--bf16]     # 저장 dtype (기본 bfloat16)

출력:
  output_dir/
    config.json
    tokenizer*.json / tokenizer_config.json
    model-*.safetensors  (sharded)
"""
import argparse
import json
import os
import sys

import torch
from safetensors.torch import load_file as load_safetensors
from safetensors.torch import save_file as save_safetensors

# ── projector 키 매핑 (커스텀 → LLaVA HF) ─────────────────────────────────────
# LlavaMultiModalProjector 는 linear_1 → ACT2FN[projector_hidden_act] → linear_2
# 로 고정돼 있다(transformers/models/llava/modeling_llava.py). 활성 함수는 설정
# 가능하고 ACT2FN["linear"] 는 진짜 항등 함수이므로, 표현 가능한 구조는 두 가지다.
#
#   mlp2x_gelu : act="gelu"   linear_1=proj.0, linear_2=proj.2        (그대로 대응)
#   linear     : act="linear" linear_1=proj,   linear_2=항등 행렬      (수학적 동치)
#
# linear 의 경우 출력은 I·(Wx+b) + 0 = Wx+b 이므로 원본과 정확히 같다.
PROJ_KEY_MAP_MLP2 = {
    "proj.0.weight": "multi_modal_projector.linear_1.weight",
    "proj.0.bias":   "multi_modal_projector.linear_1.bias",
    "proj.2.weight": "multi_modal_projector.linear_2.weight",
    "proj.2.bias":   "multi_modal_projector.linear_2.bias",
}

PROJ_KEY_MAP_LINEAR = {
    "proj.weight": "multi_modal_projector.linear_1.weight",
    "proj.bias":   "multi_modal_projector.linear_1.bias",
}

# projector_type → (키 매핑, projector_hidden_act)
CONVERTIBLE_PROJECTORS = {
    "mlp2x_gelu": (PROJ_KEY_MAP_MLP2,   "gelu"),
    "linear":     (PROJ_KEY_MAP_LINEAR, "linear"),
}

# ── 프로젝터 타입 검증 ────────────────────────────────────────────────────────
# model/config.py 의 RESAMPLER_PROJECTOR_TYPES 와 동일하게 유지한다.
RESAMPLER_PROJECTOR_TYPES = ("cross_attn", "qformer")

# QueryResampler(model/projector.py) 의 state_dict 에만 존재하는 키.
# vlm_config.json 에 projector_type 이 없는 구 체크포인트를 판별하는 데 쓴다.
RESAMPLER_STATE_KEYS = ("proj.query", "proj.context_proj.weight", "proj.out_proj.weight")


def require_cfg(vlm_cfg: dict, key: str):
    """
    vlm_config.json 의 필수 값을 읽는다.

    구 체크포인트는 vlm_config.json 이 없을 수 있다. 프로젝터 구조는 state_dict
    으로 추정할 수 있으나 이 값들은 추정할 수 없으므로, 무슨 키가 왜 필요한지
    밝히고 중단한다. dict 인덱싱만 하면 맨 KeyError 만 나온다.
    """
    if key not in vlm_cfg:
        raise ValueError(
            f"vlm_config.json 에서 {key!r} 를 찾을 수 없어 변환을 계속할 수 없습니다.\n"
            "이 값은 projector.bin 만으로는 추정할 수 없습니다.\n"
            "학습에 사용한 체크포인트의 vlm_config.json 을 --ckpt_dir 에 두십시오."
        )
    return vlm_cfg[key]


def detect_projector_type(vlm_cfg: dict, proj_state: dict) -> str:
    """
    체크포인트의 프로젝터 타입을 판별한다.

    vlm_config.json 의 projector_type 을 우선 사용한다. 해당 키가 없는 구
    체크포인트는 projector.bin 의 키 구성으로 추정한다. 어느 구조에도
    해당하지 않으면 "unknown" 을 반환한다.
    """
    recorded = vlm_cfg.get("projector_type")
    if recorded:
        return recorded
    if any(k in proj_state for k in RESAMPLER_STATE_KEYS):
        # 블록마다 self_attn 이 있으면 Q-Former, 없으면 cross-attention 리샘플러
        return "qformer" if any(".self_attn." in k for k in proj_state) else "cross_attn"
    if "proj.weight" in proj_state:
        return "linear"
    if "proj.4.weight" in proj_state:
        return "mlp3x_gelu"
    if "proj.0.weight" in proj_state:
        return "mlp2x_gelu"
    return "unknown"


def convert_projector(vlm_cfg: dict, proj_state: dict, dtype: torch.dtype):
    """
    projector.bin 을 LLaVA HF 의 multi_modal_projector 키로 변환한다.

    Returns:
        (tensors, projector_hidden_act). 활성 함수는 LlavaConfig 에 그대로
        넣어야 하며, 구조에 따라 "gelu" 또는 "linear" 이다.

    변환 불가한 구조는 깨진 모델을 내보내지 않도록 여기서 중단한다. 근거는
    transformers/models/llava/modeling_llava.py 의 LlavaMultiModalProjector 이며,
    선형 변환 두 개와 그 사이의 활성 함수 하나로 고정돼 있다.
    """
    projector_type = detect_projector_type(vlm_cfg, proj_state)
    print(f"[projector] 타입: {projector_type}")

    if projector_type not in CONVERTIBLE_PROJECTORS:
        raise ValueError(_unsupported_message(projector_type))

    key_map, hidden_act = CONVERTIBLE_PROJECTORS[projector_type]

    # 텐서 구성이 정확히 일치해야 한다. 남는 키를 그냥 버리면 mlp3x_gelu 의
    # 3번째 층처럼 학습된 가중치가 조용히 사라진 모델이 나온다.
    missing = sorted(src for src in key_map if src not in proj_state)
    extra   = sorted(key for key in proj_state if key not in key_map)
    if missing or extra:
        detail = ""
        if missing:
            detail += f"필요한 키 없음         : {', '.join(missing)}\n"
        if extra:
            detail += f"담을 자리가 없는 키    : {', '.join(extra)}\n"
        raise ValueError(
            f"projector_type={projector_type!r} 로 판별했으나 텐서 구성이 맞지 않습니다.\n"
            f"{detail}"
            "체크포인트의 vlm_config.json 과 projector.bin 이 어긋났을 수 있습니다."
        )

    tensors = {
        dst: proj_state[src].to(dtype).contiguous()
        for src, dst in key_map.items()
    }

    # linear 구조는 linear_2 자리에 항등 변환을 채워 2층 형태로 맞춘다.
    # act="linear" 이므로 최종 출력은 I·(Wx+b) + 0 = Wx+b 로 원본과 동치이다.
    if projector_type == "linear":
        llm_hidden = proj_state["proj.weight"].shape[0]
        tensors["multi_modal_projector.linear_2.weight"] = (
            torch.eye(llm_hidden, dtype=dtype).contiguous()
        )
        tensors["multi_modal_projector.linear_2.bias"] = (
            torch.zeros(llm_hidden, dtype=dtype).contiguous()
        )
        print(f"[projector] linear → 2층 형태로 확장 (act=linear, linear_2=I[{llm_hidden}])")

    return tensors, hidden_act


def _unsupported_message(projector_type: str) -> str:
    """변환 불가 사유를 대상 포맷의 성질로 설명한다."""
    convertible = ", ".join(sorted(CONVERTIBLE_PROJECTORS))
    if projector_type in RESAMPLER_PROJECTOR_TYPES:
        why = (
            "쿼리 리샘플러는 학습된 쿼리 토큰과 cross-attention 블록을 갖는데\n"
            "LlavaMultiModalProjector 에는 그것을 담을 텐서가 없습니다.\n"
            "또한 리샘플러는 패치 수와 다른 개수의 이미지 토큰을 내보내는데\n"
            "LlavaForConditionalGeneration 은 이미지 토큰 수를 패치 수에서 계산합니다.\n"
        )
    elif projector_type == "mlp3x_gelu":
        why = (
            "mlp3x_gelu 는 선형 변환 3개와 비선형 2개로 이루어집니다.\n"
            "LlavaMultiModalProjector 는 선형 변환 2개와 비선형 1개뿐이고,\n"
            "비선형을 건너뛰어 선형 변환을 합칠 수는 없으므로 등가 표현이 없습니다.\n"
        )
    else:
        why = (
            "LlavaMultiModalProjector 의 텐서 구성과 대응시킬 방법이 없습니다.\n"
        )
    return (
        f"projector_type={projector_type!r} 체크포인트는 LLaVA HF 포맷으로 변환할 수 없습니다.\n"
        f"{why}"
        "이는 대상 포맷의 제약이며 이 스크립트의 미구현이 아닙니다.\n"
        "근거: transformers/models/llava/modeling_llava.py 의 LlavaMultiModalProjector\n"
        "\n"
        f"이 스크립트가 변환할 수 있는 구조: {convertible}\n"
        "그 밖의 구조는 이 리포지토리의 추론 경로(demo/app.py, api/, test.py, test_sds.py)로\n"
        "서빙하십시오. projector.bin 과 vlm_config.json 을 그대로 읽습니다."
    )


def build_adapter_config(ckpt_dir: str, llm_path: str) -> dict:
    """adapter_config.json 이 없을 때 safetensors weight 형상으로 재구성."""
    from safetensors import safe_open

    sf_path = os.path.join(ckpt_dir, "adapter_model.safetensors")
    with safe_open(sf_path, framework="pt", device="cpu") as f:
        keys = list(f.keys())
        rank = None
        for k in keys:
            if "lora_A.weight" in k:
                rank = f.get_tensor(k).shape[0]
                break

    # base_model.model.model.layers.{i}.self_attn.q_proj.lora_A.weight
    # index:  0          1     2      3    4         5           6      7   8
    # → target module: self_attn.q_proj  (index 5:-2)
    target_modules = sorted({
        ".".join(k.split(".")[5:-2])
        for k in keys if "lora_A" in k
    })

    return {
        "base_model_name_or_path": llm_path,
        "bias": "none",
        "fan_in_fan_out": False,
        "inference_mode": True,
        "init_lora_weights": True,
        "lora_alpha": rank,
        "lora_dropout": 0.0,
        "modules_to_save": None,
        "peft_type": "LORA",
        "r": rank,
        "revision": None,
        "target_modules": target_modules,
        "task_type": "CAUSAL_LM",
    }


def merge_lora(llm_path: str, ckpt_dir: str, dtype: torch.dtype) -> dict:
    """LoRA 를 base LLM 에 병합하고 state_dict(cpu) 반환."""
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    # adapter_config.json 이 없으면 임시 생성
    adapter_cfg_path = os.path.join(ckpt_dir, "adapter_config.json")
    created = False
    if not os.path.exists(adapter_cfg_path):
        print("[merge_lora] adapter_config.json 없음 → weight 형상으로 재구성")
        cfg = build_adapter_config(ckpt_dir, llm_path)
        with open(adapter_cfg_path, "w") as fp:
            json.dump(cfg, fp, indent=2, ensure_ascii=False)
        created = True

    print(f"[merge_lora] base LLM 로드: {llm_path}")
    base = AutoModelForCausalLM.from_pretrained(
        llm_path, torch_dtype=dtype, device_map="cpu"
    )
    print("[merge_lora] LoRA 어댑터 로드 및 병합 중...")
    model = PeftModel.from_pretrained(base, ckpt_dir, device_map="cpu")
    merged = model.merge_and_unload()
    state = {k: v.contiguous() for k, v in merged.state_dict().items()}

    if created:
        os.remove(adapter_cfg_path)

    return state


def load_clip_state(clip_model_name: str, dtype: torch.dtype) -> dict:
    """CLIP 비전 인코더 state_dict 를 vision_tower.* 키로 반환."""
    from transformers import CLIPVisionModel

    print(f"[clip] 로드: {clip_model_name}")
    clip = CLIPVisionModel.from_pretrained(clip_model_name, torch_dtype=dtype)
    state = {}
    for k, v in clip.state_dict().items():
        state[f"vision_tower.{k}"] = v.contiguous()
    return state


def build_llava_config(
    llm_path: str, clip_model_name: str, vlm_cfg: dict, projector_hidden_act: str
) -> "LlavaConfig":
    from transformers import AutoConfig, LlavaConfig

    llm_config  = AutoConfig.from_pretrained(llm_path)
    clip_config = AutoConfig.from_pretrained(clip_model_name)
    vision_cfg  = clip_config.vision_config

    return LlavaConfig(
        text_config=llm_config,
        vision_config=vision_cfg,
        image_token_index=require_cfg(vlm_cfg, "image_token_id"),
        # 프로젝터 구조에 따라 결정된다. mlp2x_gelu 는 "gelu",
        # linear 는 항등 활성인 "linear" 이다. convert_projector 가 돌려준다.
        projector_hidden_act=projector_hidden_act,
        # LLaVA HF "default" = patch tokens only (CLS 제외) → vlm_cfg "patch" 와 동일
        vision_feature_select_strategy="default",
        vision_feature_layer=require_cfg(vlm_cfg, "vision_feature_layer"),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt_dir",    required=True, help="체크포인트 디렉토리")
    parser.add_argument("--output_dir",  required=True, help="출력 디렉토리")
    parser.add_argument("--llm_path",    required=True, help="base LLM 경로 (로컬 또는 HF 모델 ID)")
    parser.add_argument("--clip_model",  required=True, help="CLIP 모델 경로 (로컬 또는 HF 모델 ID)")
    parser.add_argument("--bf16",        action="store_true", default=True, help="저장 dtype bfloat16 (기본값)")
    parser.add_argument("--fp16",        action="store_true", help="저장 dtype float16")
    parser.add_argument("--max_shard_gb", type=float, default=4.0, help="shard 크기 GB")
    args = parser.parse_args()

    dtype = torch.float16 if args.fp16 else torch.bfloat16

    # vlm_config 읽기.
    # 없는 구 체크포인트도 프로젝터 검사까지는 진행한다. detect_projector_type 이
    # projector.bin 의 키 구성으로 구조를 추정하므로 빈 dict 로 넘긴다. 변환이
    # 가능한 구조라면 이후 build_llava_config 가 필요한 키의 부재를 알린다.
    vlm_cfg_path = os.path.join(args.ckpt_dir, "vlm_config.json")
    if os.path.isfile(vlm_cfg_path):
        with open(vlm_cfg_path) as f:
            vlm_cfg = json.load(f)
    else:
        print(f"[config] {vlm_cfg_path} 없음 → projector.bin 키 구성으로 구조를 추정합니다")
        vlm_cfg = {}

    llm_path        = args.llm_path
    clip_model_name = args.clip_model

    # ── 1. Projector 키 재명명 ────────────────────────────────────────────────
    # LoRA merge 보다, 그리고 출력 디렉토리 생성보다 먼저 수행한다. 변환 불가한
    # 프로젝터를 몇십 분짜리 merge 이후가 아니라 시작 시점에 걸러내고, 걸러진
    # 경우 빈 디렉토리조차 남기지 않기 위함이다.
    proj_raw = torch.load(
        os.path.join(args.ckpt_dir, "projector.bin"),
        map_location="cpu",
        weights_only=True,
    )
    proj_state, projector_hidden_act = convert_projector(vlm_cfg, proj_raw, dtype)

    os.makedirs(args.output_dir, exist_ok=True)

    # ── 2. LoRA merge ──────────────────────────────────────────────────────────
    llm_state = merge_lora(llm_path, args.ckpt_dir, dtype)
    # language_model.* 프리픽스 추가
    llm_state = {f"language_model.{k}": v for k, v in llm_state.items()}

    # ── 3. CLIP 비전 인코더 ───────────────────────────────────────────────────
    clip_state = load_clip_state(clip_model_name, dtype)

    # ── 4. 전체 state_dict 병합 ───────────────────────────────────────────────
    full_state = {**llm_state, **proj_state, **clip_state}
    print(f"[merge] 총 텐서 수: {len(full_state)}")

    # ── 5. LLaVA config 생성 및 저장 ─────────────────────────────────────────
    llava_cfg = build_llava_config(llm_path, clip_model_name, vlm_cfg, projector_hidden_act)
    llava_cfg.save_pretrained(args.output_dir)
    print(f"[config] {args.output_dir}/config.json 저장 완료")

    # ── 6. 토크나이저 복사 ────────────────────────────────────────────────────
    import shutil
    for fname in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja"):
        src = os.path.join(args.ckpt_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, args.output_dir)
    # special_tokens_map 이 base llm 에 있을 수 있음
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.ckpt_dir)
    tok.save_pretrained(args.output_dir)
    print(f"[tokenizer] 저장 완료")

    # ── 7. safetensors shard 저장 ────────────────────────────────────────────
    max_shard_bytes = int(args.max_shard_gb * 1024 ** 3)
    shards = []
    current_shard: dict = {}
    current_bytes = 0
    index_map = {}

    for key, tensor in full_state.items():
        nbytes = tensor.numel() * tensor.element_size()
        if current_bytes + nbytes > max_shard_bytes and current_shard:
            shards.append(current_shard)
            current_shard = {}
            current_bytes = 0
        current_shard[key] = tensor
        current_bytes += nbytes

    if current_shard:
        shards.append(current_shard)

    total_shards = len(shards)
    for idx, shard in enumerate(shards, 1):
        fname = f"model-{idx:05d}-of-{total_shards:05d}.safetensors"
        fpath = os.path.join(args.output_dir, fname)
        save_safetensors(shard, fpath)
        print(f"[shard {idx}/{total_shards}] {fname}  ({os.path.getsize(fpath)/1e9:.2f} GB)")
        for k in shard:
            index_map[k] = fname

    # model.safetensors.index.json
    index = {
        "metadata": {"total_size": sum(
            v.numel() * v.element_size() for v in full_state.values()
        )},
        "weight_map": index_map,
    }
    index_path = os.path.join(args.output_dir, "model.safetensors.index.json")
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)

    print(f"\n✅ 변환 완료: {args.output_dir}")
    print(f"   총 가중치: {index['metadata']['total_size']/1e9:.2f} GB")
    print(f"\n[vLLM 실행 예시]")
    print(f"  vllm serve {args.output_dir} \\")
    print(f"    --model {args.output_dir} \\")
    print(f"    --trust-remote-code \\")
    print(f"    --max-model-len 4096")


if __name__ == "__main__":
    main()
