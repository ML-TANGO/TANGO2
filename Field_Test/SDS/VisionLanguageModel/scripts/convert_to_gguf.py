#!/usr/bin/env python3
"""
convert_to_gguf.py — 커스텀 VLM 체크포인트 → llama.cpp 용 GGUF 변환

출력:
  output_dir/merged_llm/          ← LoRA 병합된 LLM (HF 포맷, convert_hf_to_gguf.py 입력용)
  output_dir/mmproj.gguf          ← CLIP + Projector (llava-cli --mmproj 인수)

사전 설치:
  pip install gguf safetensors transformers peft

사용법:
  # Step 1: 이 스크립트로 merged_llm/ 과 mmproj.gguf 생성
  python scripts/convert_to_gguf.py \\
    --ckpt_dir   /home/ywlee/SSD/checkpoints/clip_llama31_lora_marine_sds_lora_ko \\
    --llm_path   /home/ywlee/Llama-3.1-8B-Instruct \\
    --clip_model openai/clip-vit-large-patch14-336 \\
    --output_dir /home/ywlee/SSD/llava_gguf

  # Step 2: llama.cpp convert_hf_to_gguf.py 로 LLM GGUF 변환
  python /path/to/llama.cpp/convert_hf_to_gguf.py \\
    /home/ywlee/SSD/llava_gguf/merged_llm \\
    --outfile /home/ywlee/SSD/llava_gguf/llm.gguf \\
    --outtype bf16

  # Step 3: 추론
  /path/to/llama.cpp/llava-cli \\
    -m /home/ywlee/SSD/llava_gguf/llm.gguf \\
    --mmproj /home/ywlee/SSD/llava_gguf/mmproj.gguf \\
    --image input.png \\
    -p "현재 해상 상황을 묘사하시오."
"""
import argparse
import json
import os
import sys

import torch


# ──────────────────────────────────────────────────────────────────────────────
# CLIP → GGUF 텐서명 매핑
# ──────────────────────────────────────────────────────────────────────────────
CLIP_GLOBAL_MAP = {
    "vision_model.embeddings.class_embedding":              "v.class_embd",
    "vision_model.embeddings.patch_embedding.weight":       "v.patch_embd.weight",
    "vision_model.embeddings.position_embedding.weight":    "v.position_embd.weight",
    "vision_model.pre_layrnorm.weight":                     "v.pre_ln.weight",
    "vision_model.pre_layrnorm.bias":                       "v.pre_ln.bias",
    "vision_model.post_layernorm.weight":                   "v.post_ln.weight",
    "vision_model.post_layernorm.bias":                     "v.post_ln.bias",
}

CLIP_LAYER_MAP = {
    "self_attn.q_proj.weight":  "attn_q.weight",
    "self_attn.q_proj.bias":    "attn_q.bias",
    "self_attn.k_proj.weight":  "attn_k.weight",
    "self_attn.k_proj.bias":    "attn_k.bias",
    "self_attn.v_proj.weight":  "attn_v.weight",
    "self_attn.v_proj.bias":    "attn_v.bias",
    "self_attn.out_proj.weight":"attn_out.weight",
    "self_attn.out_proj.bias":  "attn_out.bias",
    "mlp.fc1.weight":           "ffn_up.weight",
    "mlp.fc1.bias":             "ffn_up.bias",
    "mlp.fc2.weight":           "ffn_down.weight",
    "mlp.fc2.bias":             "ffn_down.bias",
    "layer_norm1.weight":       "ln1.weight",
    "layer_norm1.bias":         "ln1.bias",
    "layer_norm2.weight":       "ln2.weight",
    "layer_norm2.bias":         "ln2.bias",
}

PROJ_KEY_MAP = {
    "proj.0.weight": "mm.0.weight",
    "proj.0.bias":   "mm.0.bias",
    "proj.2.weight": "mm.2.weight",
    "proj.2.bias":   "mm.2.bias",
}


def build_mmproj(ckpt_dir: str, clip_name: str, vlm_cfg: dict, output_path: str,
                 llama_cpp_dir: str):
    """CLIP + Projector → mmproj.gguf (llama.cpp GGUFWriter 사용)"""
    import numpy as np
    from transformers import CLIPVisionModel, AutoConfig

    # llama.cpp gguf-py 로드
    gguf_py = os.path.join(llama_cpp_dir, "gguf-py")
    if gguf_py not in sys.path:
        sys.path.insert(0, gguf_py)
    import gguf

    print(f"[mmproj] CLIP 로드: {clip_name}")
    clip = CLIPVisionModel.from_pretrained(clip_name, torch_dtype=torch.float32)
    clip_sd = clip.state_dict()

    clip_cfg   = AutoConfig.from_pretrained(clip_name).vision_config
    num_layers = clip_cfg.num_hidden_layers   # 24
    hidden     = clip_cfg.hidden_size         # 1024
    ffn        = clip_cfg.intermediate_size   # 4096
    heads      = clip_cfg.num_attention_heads # 16
    img_size   = clip_cfg.image_size          # 336
    patch_size = clip_cfg.patch_size          # 14
    eps        = clip_cfg.layer_norm_eps      # 1e-5

    feature_layer = vlm_cfg.get("vision_feature_layer", -2)
    # non-negative index: -2 with 24 layers → 24 + (-2) + 1 = 23
    block_count = (num_layers + feature_layer + 1) if feature_layer < 0 else feature_layer
    llm_hidden  = vlm_cfg["llm_hidden_size"]  # 4096

    writer = gguf.GGUFWriter(output_path, "clip")
    # modality flags (clip.cpp: GGML_ASSERT(has_vision) requires this)
    writer.add_bool("clip.has_vision_encoder",              True)
    writer.add_bool("clip.has_text_encoder",                False)
    writer.add_bool("clip.has_audio_encoder",               False)
    writer.add_bool("clip.has_llava_projector",             True)
    writer.add_string("clip.projector_type",                "mlp")
    writer.add_uint32("clip.vision.image_size",             img_size)
    writer.add_uint32("clip.vision.patch_size",             patch_size)
    writer.add_uint32("clip.vision.embedding_length",       hidden)
    writer.add_uint32("clip.vision.feed_forward_length",    ffn)
    writer.add_uint32("clip.vision.block_count",            block_count)
    writer.add_uint32("clip.vision.attention.head_count",   heads)
    writer.add_uint32("clip.vision.projection_dim",         llm_hidden)
    writer.add_float32("clip.vision.attention.layer_norm_epsilon", eps)
    writer.add_bool("clip.use_gelu",                        True)
    # OpenAI CLIP ViT normalization params (required by clip.cpp ASSERT)
    writer.add_array("clip.vision.image_mean", [0.48145466, 0.4578275, 0.40821073])
    writer.add_array("clip.vision.image_std",  [0.26862954, 0.26130258, 0.27577711])
    writer.add_array("clip.vision.feature_layer", [block_count])

    def to_numpy(t: torch.Tensor) -> np.ndarray:
        # numpy shape 은 ggml 로드 시 자동으로 역순(column-major)이 되므로
        # 별도 permute/transpose 불필요 (공식 convert_image_encoder_to_gguf.py 와 동일)
        return t.float().contiguous().numpy()

    # 전역 텐서
    for hf_key, gguf_name in CLIP_GLOBAL_MAP.items():
        if hf_key in clip_sd:
            writer.add_tensor(gguf_name, to_numpy(clip_sd[hf_key]))

    # 레이어별 텐서
    for i in range(block_count + 1):
        prefix = f"vision_model.encoder.layers.{i}."
        for suffix, gguf_suffix in CLIP_LAYER_MAP.items():
            hf_key = prefix + suffix
            if hf_key in clip_sd:
                writer.add_tensor(f"v.blk.{i}.{gguf_suffix}",
                                  to_numpy(clip_sd[hf_key]))

    # Projector
    proj_raw = torch.load(
        os.path.join(ckpt_dir, "projector.bin"),
        map_location="cpu", weights_only=True,
    )
    for src, dst in PROJ_KEY_MAP.items():
        if src in proj_raw:
            writer.add_tensor(dst, to_numpy(proj_raw[src]))
        else:
            print(f"[mmproj] 경고: projector 키 없음 → {src}")

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()  # write_ti_data_to_file() 포함
    writer.close()

    size_mb = os.path.getsize(output_path) / 1e6
    print(f"[gguf] {output_path} 저장 완료 ({size_mb:.1f} MB)")


def merge_lora_and_save(ckpt_dir: str, llm_path: str, output_dir: str,
                        dtype: torch.dtype):
    """LoRA merge 후 HF 포맷으로 저장 (llama.cpp convert_hf_to_gguf.py 입력용)."""
    import json
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    adapter_cfg_path = os.path.join(ckpt_dir, "adapter_config.json")
    created = False
    if not os.path.exists(adapter_cfg_path):
        print("[merge] adapter_config.json 없음 → 재구성")
        from safetensors import safe_open
        sf_path = os.path.join(ckpt_dir, "adapter_model.safetensors")
        with safe_open(sf_path, framework="pt", device="cpu") as f:
            keys = list(f.keys())
            rank = None
            for k in keys:
                if "lora_A.weight" in k:
                    rank = f.get_tensor(k).shape[0]; break
        target_mods = sorted({".".join(k.split(".")[5:-2]) for k in keys if "lora_A" in k})
        cfg = {
            "base_model_name_or_path": llm_path, "bias": "none",
            "fan_in_fan_out": False, "inference_mode": True,
            "init_lora_weights": True, "lora_alpha": rank,
            "lora_dropout": 0.0, "modules_to_save": None,
            "peft_type": "LORA", "r": rank, "revision": None,
            "target_modules": target_mods, "task_type": "CAUSAL_LM",
        }
        with open(adapter_cfg_path, "w") as fp:
            json.dump(cfg, fp, indent=2)
        created = True

    print(f"[merge] base LLM 로드: {llm_path}")
    base = AutoModelForCausalLM.from_pretrained(
        llm_path, torch_dtype=dtype, device_map="cpu"
    )
    print("[merge] LoRA 병합 중...")
    model = PeftModel.from_pretrained(base, ckpt_dir, device_map="cpu")
    merged = model.merge_and_unload()

    os.makedirs(output_dir, exist_ok=True)
    print(f"[merge] 저장: {output_dir}")
    merged.save_pretrained(output_dir, safe_serialization=True)
    # llm_path 토크나이저 사용 — ckpt_dir 에는 <|image|> 특수토큰이 추가되어
    # convert_hf_to_gguf.py 의 vocab_size 어설션을 위반하기 때문
    AutoTokenizer.from_pretrained(llm_path).save_pretrained(output_dir)

    if created:
        os.remove(adapter_cfg_path)

    print(f"[merge] ✅ {output_dir}")
    return output_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt_dir",       required=True, help="체크포인트 디렉토리")
    parser.add_argument("--output_dir",     required=True, help="출력 디렉토리")
    parser.add_argument("--llm_path",       required=True, help="base LLM 경로 (로컬 또는 HF 모델 ID)")
    parser.add_argument("--clip_model",     required=True, help="CLIP 모델 경로 (로컬 또는 HF 모델 ID)")
    parser.add_argument("--llama_cpp_dir",  required=True, help="llama.cpp 리포지토리 경로 (gguf-py 로드에 사용)")
    parser.add_argument("--bf16",           action="store_true", default=True)
    parser.add_argument("--fp16",           action="store_true")
    parser.add_argument("--skip_merge",     action="store_true",
                        help="LoRA merge 건너뜀 (merged_llm 이미 존재)")
    args = parser.parse_args()

    dtype = torch.float16 if args.fp16 else torch.bfloat16

    vlm_cfg_path = os.path.join(args.ckpt_dir, "vlm_config.json")
    with open(vlm_cfg_path) as f:
        vlm_cfg = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    # ── 1. LoRA merge → merged_llm/ ──────────────────────────────────────────
    merged_dir = os.path.join(args.output_dir, "merged_llm")
    if not args.skip_merge:
        merge_lora_and_save(args.ckpt_dir, args.llm_path, merged_dir, dtype)
    else:
        print(f"[skip] LoRA merge 건너뜀 → {merged_dir}")

    # ── 2. mmproj.gguf 빌드 ──────────────────────────────────────────────────
    mmproj_path = os.path.join(args.output_dir, "mmproj.gguf")
    build_mmproj(args.ckpt_dir, args.clip_model, vlm_cfg, mmproj_path,
                 args.llama_cpp_dir)

    print("\n✅ 변환 완료")
    print(f"   merged_llm : {merged_dir}")
    print(f"   mmproj.gguf: {mmproj_path}")
    print("\n[다음 단계 — LLM GGUF 변환]")
    print(f"  python /path/to/llama.cpp/convert_hf_to_gguf.py \\")
    print(f"    {merged_dir} \\")
    print(f"    --outfile {args.output_dir}/llm.gguf \\")
    print(f"    --outtype bf16")
    print(f"\n[llava-cli 실행]")
    print(f"  ./llava-cli \\")
    print(f"    -m {args.output_dir}/llm.gguf \\")
    print(f"    --mmproj {mmproj_path} \\")
    print(f"    --image input.png \\")
    print(f'    -p "현재 해상 상황을 묘사하시오."')


if __name__ == "__main__":
    main()
