#!/usr/bin/env python3
"""
convert_to_llava_hf.py — 커스텀 VLM 체크포인트 → HuggingFace LLaVA 포맷 변환
vLLM 또는 transformers LlavaForConditionalGeneration 에서 직접 로드 가능

변환 내용:
  - adapter_model.safetensors (LoRA) → base LLM 에 merge
  - projector.bin (mlp2x_gelu)      → multi_modal_projector.linear_{1,2} 키 재명명
  - openai/clip-vit-large-patch14-336 → vision_tower 포함

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
PROJ_KEY_MAP = {
    "proj.0.weight": "multi_modal_projector.linear_1.weight",
    "proj.0.bias":   "multi_modal_projector.linear_1.bias",
    "proj.2.weight": "multi_modal_projector.linear_2.weight",
    "proj.2.bias":   "multi_modal_projector.linear_2.bias",
}


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


def build_llava_config(llm_path: str, clip_model_name: str, vlm_cfg: dict) -> "LlavaConfig":
    from transformers import AutoConfig, LlavaConfig

    llm_config  = AutoConfig.from_pretrained(llm_path)
    clip_config = AutoConfig.from_pretrained(clip_model_name)
    vision_cfg  = clip_config.vision_config

    return LlavaConfig(
        text_config=llm_config,
        vision_config=vision_cfg,
        image_token_index=vlm_cfg["image_token_id"],
        projector_hidden_act="gelu",
        # LLaVA HF "default" = patch tokens only (CLS 제외) → vlm_cfg "patch" 와 동일
        vision_feature_select_strategy="default",
        vision_feature_layer=vlm_cfg["vision_feature_layer"],
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

    # vlm_config 읽기
    vlm_cfg_path = os.path.join(args.ckpt_dir, "vlm_config.json")
    with open(vlm_cfg_path) as f:
        vlm_cfg = json.load(f)

    llm_path        = args.llm_path
    clip_model_name = args.clip_model

    os.makedirs(args.output_dir, exist_ok=True)

    # ── 1. LoRA merge ──────────────────────────────────────────────────────────
    llm_state = merge_lora(llm_path, args.ckpt_dir, dtype)
    # language_model.* 프리픽스 추가
    llm_state = {f"language_model.{k}": v for k, v in llm_state.items()}

    # ── 2. Projector 키 재명명 ────────────────────────────────────────────────
    proj_raw = torch.load(
        os.path.join(args.ckpt_dir, "projector.bin"),
        map_location="cpu",
        weights_only=True,
    )
    proj_state = {}
    for src, dst in PROJ_KEY_MAP.items():
        if src in proj_raw:
            proj_state[dst] = proj_raw[src].to(dtype).contiguous()
        else:
            print(f"[projector] 경고: 키 없음 → {src}")

    # ── 3. CLIP 비전 인코더 ───────────────────────────────────────────────────
    clip_state = load_clip_state(clip_model_name, dtype)

    # ── 4. 전체 state_dict 병합 ───────────────────────────────────────────────
    full_state = {**llm_state, **proj_state, **clip_state}
    print(f"[merge] 총 텐서 수: {len(full_state)}")

    # ── 5. LLaVA config 생성 및 저장 ─────────────────────────────────────────
    llava_cfg = build_llava_config(llm_path, clip_model_name, vlm_cfg)
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
