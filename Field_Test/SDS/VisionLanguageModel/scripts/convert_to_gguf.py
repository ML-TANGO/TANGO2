#!/usr/bin/env python3
"""
convert_to_gguf.py — 커스텀 VLM 체크포인트 → llama.cpp 용 GGUF 변환

출력:
  output_dir/merged_llm/          ← LoRA 병합된 LLM (HF 포맷, convert_hf_to_gguf.py 입력용)
  output_dir/mmproj.gguf          ← CLIP + Projector (llava-cli --mmproj 인수)

지원 프로젝터:
  clip.cpp 의 mlp 그래프(clip.projector_type="mlp")는 다음으로 고정돼 있다.

    embeddings = mm_0_w · embeddings + mm_0_b
    embeddings = gelu(embeddings)
    if (mm_2_w) embeddings = mm_2_w · embeddings + mm_2_b

  행렬곱이 최대 2회이고 gelu 가 조건 없이 적용되므로 mlp2x_gelu 만 표현할 수
  있다. linear 는 gelu 를 건너뛸 수 없어서, mlp3x_gelu 는 행렬곱이 3회여서
  등가 표현이 없다. cross_attn 과 qformer 는 담을 텐서 이름이 없다.
  근거는 llama.cpp tools/mtmd/models/llava.cpp 이다.

  linear 체크포인트는 LLaVA HF 로는 정확히 변환되므로
  scripts/convert_to_llava_hf.py 를 사용한다.

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


# ──────────────────────────────────────────────────────────────────────────────
# 프로젝터 타입 검증
# ──────────────────────────────────────────────────────────────────────────────
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


# projector_type → 키 매핑. clip.cpp 의 mlp 그래프가 표현할 수 있는 구조만 담는다.
CONVERTIBLE_PROJECTORS = {
    "mlp2x_gelu": PROJ_KEY_MAP,
}


def _unsupported_message(projector_type: str) -> str:
    """
    변환 불가 사유를 대상 포맷의 성질로 설명한다.

    근거는 llama.cpp 의 tools/mtmd/models/llava.cpp 에 있는 PROJECTOR_TYPE_MLP
    그래프이다. 계산은 다음으로 고정돼 있다.

        embeddings = mm_0_w · embeddings + mm_0_b
        embeddings = gelu(embeddings)
        if (mm_2_w) embeddings = mm_2_w · embeddings + mm_2_b

    즉 행렬곱은 최대 두 번이고, gelu 는 조건 없이 항상 적용된다. mm_2_w 가
    없으면 Linear→GELU 가 되지만 그것은 우리의 linear 가 아니다.
    """
    convertible = ", ".join(sorted(CONVERTIBLE_PROJECTORS))
    if projector_type in RESAMPLER_PROJECTOR_TYPES:
        why = (
            "쿼리 리샘플러의 학습된 쿼리 토큰과 cross-attention 블록에 대응하는\n"
            "텐서 이름이 mlp 그래프에 없습니다. clip.cpp 에는 resampler 타입\n"
            "(PROJECTOR_TYPE_MINICPMV)도 있으나 그것은 MiniCPM-V 전용 구조로,\n"
            "단일 어텐션 층에 2D 위치 임베딩이 필수이고 FFN 이 없습니다.\n"
            "본 구현의 리샘플러는 블록마다 FFN 을 갖고 위치 임베딩을 쓰지 않으므로\n"
            "그 텐서 집합과도 대응되지 않습니다.\n"
            "또한 리샘플러는 패치 수와 다른 개수의 이미지 토큰을 내보내므로\n"
            "clip.cpp 가 가정하는 패치당 1토큰 규칙과도 맞지 않습니다.\n"
        )
    elif projector_type == "mlp3x_gelu":
        why = (
            "mlp3x_gelu 는 행렬곱 3회와 gelu 2회로 이루어집니다.\n"
            "mlp 그래프는 행렬곱이 최대 2회이고 gelu 는 1회이므로 등가 표현이 없습니다.\n"
            "MLP_NORM 그래프도 행렬곱 2회이며 사이에 LayerNorm 이 들어가 다른 계산입니다.\n"
        )
    elif projector_type == "linear":
        why = (
            "mlp 그래프는 첫 행렬곱 뒤에 gelu 를 조건 없이 적용합니다.\n"
            "따라서 순수한 선형 변환 Wx+b 를 표현할 방법이 없습니다.\n"
            "mm_2_w 를 생략하면 Linear→GELU 가 되지만 그것은 linear 가 아닙니다.\n"
        )
    else:
        why = "mlp 그래프의 텐서 구성과 대응시킬 방법이 없습니다.\n"
    return (
        f"projector_type={projector_type!r} 체크포인트는 GGUF(mmproj) 로 변환할 수 없습니다.\n"
        f"{why}"
        "이는 대상 포맷의 제약이며 이 스크립트의 미구현이 아닙니다.\n"
        "근거: llama.cpp tools/mtmd/models/llava.cpp 의 PROJECTOR_TYPE_MLP 그래프\n"
        "\n"
        f"이 스크립트가 변환할 수 있는 구조: {convertible}\n"
        "linear 는 LLaVA HF 로는 변환할 수 있으므로 scripts/convert_to_llava_hf.py 를\n"
        "쓰십시오. 그 밖의 구조는 이 리포지토리의 추론 경로(demo/app.py, api/,\n"
        "test.py, test_sds.py)로 서빙하십시오. projector.bin 과 vlm_config.json 을\n"
        "그대로 읽습니다."
    )


def ensure_convertible_projector(vlm_cfg: dict, proj_state: dict) -> str:
    """
    GGUF 로 옮길 수 있는 프로젝터인지 확인하고 타입 문자열을 반환한다.

    변환 불가한 경우 파일을 하나도 쓰지 않은 상태에서 중단한다.
    """
    projector_type = detect_projector_type(vlm_cfg, proj_state)
    print(f"[projector] 타입: {projector_type}")

    if projector_type not in CONVERTIBLE_PROJECTORS:
        raise ValueError(_unsupported_message(projector_type))

    key_map = CONVERTIBLE_PROJECTORS[projector_type]

    # 텐서 구성이 정확히 일치해야 한다. 남는 키를 그냥 버리면 mlp3x_gelu 의
    # 3번째 층처럼 학습된 가중치가 조용히 사라진 GGUF 가 나온다.
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

    return projector_type


def build_mmproj(proj_state: dict, clip_name: str, vlm_cfg: dict, output_path: str,
                 llama_cpp_dir: str):
    """CLIP + Projector → mmproj.gguf (llama.cpp GGUFWriter 사용)

    proj_state 는 ensure_convertible_projector() 를 통과한 projector.bin
    state_dict 이므로 PROJ_KEY_MAP 의 모든 키가 존재한다.
    """
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
    llm_hidden  = require_cfg(vlm_cfg, "llm_hidden_size")  # 4096

    writer = gguf.GGUFWriter(output_path, "clip")
    # modality flags (clip.cpp: GGML_ASSERT(has_vision) requires this)
    writer.add_bool("clip.has_vision_encoder",              True)
    writer.add_bool("clip.has_text_encoder",                False)
    writer.add_bool("clip.has_audio_encoder",               False)
    writer.add_bool("clip.has_llava_projector",             True)
    # clip.cpp 가 아는 llava 프로젝터는 2층 MLP 뿐이다. 리샘플러 체크포인트는
    # ensure_convertible_projector() 에서 이미 걸러진다.
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
    for src, dst in PROJ_KEY_MAP.items():
        writer.add_tensor(dst, to_numpy(proj_state[src]))

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

    # vlm_config.json 이 없는 구 체크포인트도 프로젝터 검사까지는 진행한다.
    # detect_projector_type 이 projector.bin 의 키 구성으로 구조를 추정하므로
    # 빈 dict 로 넘긴다. 변환 가능한 구조라면 이후 require_cfg 가 부족한 키를
    # 이름과 함께 알려 준다.
    vlm_cfg_path = os.path.join(args.ckpt_dir, "vlm_config.json")
    if os.path.isfile(vlm_cfg_path):
        with open(vlm_cfg_path) as f:
            vlm_cfg = json.load(f)
    else:
        print(f"[config] {vlm_cfg_path} 없음 → projector.bin 키 구성으로 구조를 추정합니다")
        vlm_cfg = {}

    # ── 1. 프로젝터 검증 ─────────────────────────────────────────────────────
    # LoRA merge 나 GGUF 쓰기보다 먼저 수행한다. 변환 불가한 프로젝터일 때
    # 반쯤 만들어진 출력물을 남기지 않기 위함이다.
    proj_state = torch.load(
        os.path.join(args.ckpt_dir, "projector.bin"),
        map_location="cpu", weights_only=True,
    )
    ensure_convertible_projector(vlm_cfg, proj_state)

    os.makedirs(args.output_dir, exist_ok=True)

    # ── 2. LoRA merge → merged_llm/ ──────────────────────────────────────────
    merged_dir = os.path.join(args.output_dir, "merged_llm")
    if not args.skip_merge:
        merge_lora_and_save(args.ckpt_dir, args.llm_path, merged_dir, dtype)
    else:
        print(f"[skip] LoRA merge 건너뜀 → {merged_dir}")

    # ── 3. mmproj.gguf 빌드 ──────────────────────────────────────────────────
    mmproj_path = os.path.join(args.output_dir, "mmproj.gguf")
    build_mmproj(proj_state, args.clip_model, vlm_cfg, mmproj_path,
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
