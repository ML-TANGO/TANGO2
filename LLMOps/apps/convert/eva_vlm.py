"""eva-vlm(SDS) 체크포인트 → 양자화 입력 materialize.

SDS 학습(협력기관 eva-vlm 컨테이너)은 커밋에 LoRA 어댑터 + projector.bin + vlm_config.json 만
남긴다(`commit_models/<commit>/`). llama.cpp 변환은 merged HF LLM 을 받으므로, 여기서
  1) base LLM(오프라인 HF 캐시) 에 어댑터를 merge 해 HF 디렉터리로 저장하고
  2) CLIP 비전 인코더 + projector 를 llama.cpp mtmd 가 읽는 mmproj GGUF 로 쓴다.

eva 학습/추론과 같은 계산이 되도록(vision_encoder.py / projector.py / model_manager.py 대조):
  - 비전 특징 = hidden_states[vision_feature_layer] (CLS 제외, post_layernorm 미적용)
    → mmproj 는 그 층까지만 싣고(block_count) post_layernorm 은 넣지 않는다.
  - CLIP FFN 활성화 = quick_gelu → clip.use_gelu 를 쓰지 않는다(mtmd 기본 = quick gelu).
  - projector = mlp2x_gelu(Linear→GELU→Linear) → mtmd 'mlp' 타입, 텐서 mm.0 / mm.2.
    (gguf 공식 매핑은 linear_1→mm.1 이지만 mtmd 의 llava mlp 는 mm.0/mm.2 를 읽는다.)
  - 토크나이저는 base 원본(커밋 것은 <image> 추가 + transformers 5 형식이라 llama.cpp 4.x 가 못 읽음).
    <image> 임베딩 행은 학습에 쓰이지 않는다(576 이미지 임베딩으로 치환) → vocab 128256 그대로 안전.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from typing import Any, Dict

# 커밋 디렉터리 이름 — 플랫폼 커밋명(영숫자/._-). 경로 조작 방지.
_CKPT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# base 모델은 오프라인 HF 캐시에 있는 것만 허용한다(임의 repo 다운로드·경로 주입 차단).
ALLOWED_LLM_REPOS = ("meta-llama/Llama-3.1-8B-Instruct",)
ALLOWED_VISION_REPOS = ("openai/clip-vit-large-patch14-336",)

_TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                    "generation_config.json")


def resolve_checkpoint(checkpoints_root: str, name: str) -> str:
    """커밋 디렉터리 경로. 이름 정규식 + root 이탈 검사 + 필수 파일 확인."""
    if not isinstance(name, str) or not _CKPT_NAME_RE.match(name):
        raise ValueError(f"invalid checkpoint name: {name!r}")
    root = os.path.realpath(checkpoints_root)
    path = os.path.realpath(os.path.join(root, name))
    if os.path.commonpath([path, root]) != root:
        raise ValueError(f"checkpoint escapes {checkpoints_root}: {name!r}")
    for required in ("projector.bin", "vlm_config.json"):
        if not os.path.isfile(os.path.join(path, required)):
            raise FileNotFoundError(f"{name}: {required} 가 없습니다 (eva-vlm 커밋이 아님)")
    # 커밋 안 파일이 심링크로 커밋 밖(같은 마운트의 다른 커밋 등)을 가리키지 않게 한다.
    for fn in ("projector.bin", "vlm_config.json", "adapter_config.json", "adapter_model.safetensors"):
        fp = os.path.join(path, fn)
        if os.path.lexists(fp) and os.path.commonpath([os.path.realpath(fp), path]) != path:
            raise ValueError(f"{name}: {fn} 가 커밋 밖을 가리킵니다")
    if os.path.isfile(os.path.join(path, "adapter_config.json")) and \
            not os.path.isfile(os.path.join(path, "adapter_model.safetensors")):
        # .bin 어댑터는 pickle 이라 받지 않는다(eva 학습은 safetensors 로 저장한다).
        raise FileNotFoundError(f"{name}: adapter_model.safetensors 가 없습니다")
    return path


def read_vlm_config(ckpt_dir: str) -> Dict[str, Any]:
    with open(os.path.join(ckpt_dir, "vlm_config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    if cfg.get("projector_type", "mlp2x_gelu") != "mlp2x_gelu":
        raise ValueError(f"unsupported projector_type: {cfg.get('projector_type')!r}")
    if cfg.get("vision_feature_select_strategy", "patch") != "patch":
        # mtmd 의 llava 'mlp' 경로는 CLS 를 떼고 패치만 쓴다 — 다른 전략은 계산이 달라진다.
        raise ValueError("unsupported vision_feature_select_strategy: "
                         f"{cfg.get('vision_feature_select_strategy')!r}")
    return cfg


def base_repo_ids(ckpt_dir: str, vlm_cfg: Dict[str, Any]) -> tuple[str, str]:
    """(llm repo, vision repo). 어댑터의 base_model_name_or_path 를 우선한다 — 일부 커밋의
    vlm_config 는 학습 호스트 로컬 경로(/home/...)를 담고 있다. 허용 목록 밖이면 거부."""
    llm = vlm_cfg.get("llm_model_name")
    adapter_cfg = os.path.join(ckpt_dir, "adapter_config.json")
    if os.path.isfile(adapter_cfg):
        with open(adapter_cfg, encoding="utf-8") as f:
            llm = json.load(f).get("base_model_name_or_path") or llm
    vision = vlm_cfg.get("vision_model_name")
    if llm not in ALLOWED_LLM_REPOS:
        raise ValueError(f"base LLM {llm!r} 은 지원 목록에 없습니다 ({', '.join(ALLOWED_LLM_REPOS)})")
    if vision not in ALLOWED_VISION_REPOS:
        raise ValueError(f"vision 모델 {vision!r} 은 지원 목록에 없습니다 ({', '.join(ALLOWED_VISION_REPOS)})")
    return llm, vision


def local_snapshot(repo_id: str) -> str:
    """오프라인 HF 캐시(HF_HOME) 의 snapshot 경로. 네트워크 접근 없음."""
    from huggingface_hub import snapshot_download

    return snapshot_download(repo_id, local_files_only=True)


def materialize_llm(ckpt_dir: str, base_dir: str, out_dir: str) -> bool:
    """base LLM 에 커밋의 LoRA 어댑터를 merge 해 HF 디렉터리로 저장. merge 여부 반환.
    projector 만 학습한 커밋(어댑터 없음)은 base 를 그대로 쓴다."""
    import torch
    from transformers import AutoModelForCausalLM

    merged = os.path.isfile(os.path.join(ckpt_dir, "adapter_config.json"))
    model = AutoModelForCausalLM.from_pretrained(
        base_dir, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True)
    if merged:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, ckpt_dir).merge_and_unload()
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir, safe_serialization=True)
    for fn in _TOKENIZER_FILES:
        src = os.path.join(base_dir, fn)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(out_dir, fn))
    return merged


def _load_projector(ckpt_dir: str) -> Dict[str, Any]:
    import torch

    # weights_only=True: 텐서 dict 만 허용(임의 객체 역직렬화 차단). eva model_manager 와 같은 호출.
    state = torch.load(os.path.join(ckpt_dir, "projector.bin"), map_location="cpu", weights_only=True)
    out = {}
    for key, tensor in state.items():
        for prefix in ("projector.", "multi_modal_projector.", "mm_projector."):
            if key.startswith(prefix):
                key = key[len(prefix):]
        # LoRA 커밋의 projector.bin 은 큰 공유 저장소의 view 다 — clone 으로 떼어 낸다.
        out[key] = tensor.detach().clone()
    return out


def build_mmproj(ckpt_dir: str, vision_dir: str, vlm_cfg: Dict[str, Any], out_path: str) -> Dict[str, Any]:
    """CLIP 비전 인코더 + projector → mmproj GGUF(f16 행렬 / f32 norm·bias). 요약 dict 반환."""
    import gguf
    import numpy as np
    import torch
    from safetensors import safe_open

    with open(os.path.join(vision_dir, "config.json"), encoding="utf-8") as f:
        clip_cfg = json.load(f)
    vcfg = clip_cfg.get("vision_config", clip_cfg)
    with open(os.path.join(vision_dir, "preprocessor_config.json"), encoding="utf-8") as f:
        pre_cfg = json.load(f)
    if vcfg.get("hidden_act", "quick_gelu") != "quick_gelu":
        raise ValueError(f"unsupported CLIP hidden_act: {vcfg.get('hidden_act')!r}")

    n_layers_total = int(vcfg["num_hidden_layers"])
    feature_layer = int(vlm_cfg.get("vision_feature_layer", -2))
    # hidden_states[k] = k 개 층을 지난 출력(0 = 임베딩+pre_ln). 음수는 뒤에서 센다.
    n_layers = feature_layer if feature_layer >= 0 else n_layers_total + 1 + feature_layer
    if not 1 <= n_layers <= n_layers_total:
        raise ValueError(f"vision_feature_layer {feature_layer} out of range")
    hidden = int(vcfg["hidden_size"])
    llm_hidden = int(vlm_cfg.get("llm_hidden_size", 4096))

    projector = _load_projector(ckpt_dir)
    expected = {"proj.0.weight": (llm_hidden, hidden), "proj.0.bias": (llm_hidden,),
                "proj.2.weight": (llm_hidden, llm_hidden), "proj.2.bias": (llm_hidden,)}
    for key, shape in expected.items():
        got = tuple(projector[key].shape) if key in projector else None
        if got != shape:
            raise ValueError(f"projector {key}: expected {shape}, got {got}")

    writer = gguf.GGUFWriter(out_path, gguf.MODEL_ARCH_NAMES[gguf.MODEL_ARCH.MMPROJ])
    writer.add_type(gguf.GGUFType.MMPROJ)
    writer.add_file_type(gguf.LlamaFileType.MOSTLY_F16)
    writer.add_name("eva-vlm mmproj")
    writer.add_clip_has_vision_encoder(True)
    writer.add_clip_projector_type("mlp")
    writer.add_vision_projection_dim(llm_hidden)
    writer.add_vision_image_size(int(vcfg["image_size"]))
    writer.add_vision_patch_size(int(vcfg["patch_size"]))
    writer.add_vision_embedding_length(hidden)
    writer.add_vision_feed_forward_length(int(vcfg["intermediate_size"]))
    writer.add_vision_block_count(n_layers)
    writer.add_vision_head_count(int(vcfg["num_attention_heads"]))
    writer.add_vision_attention_layernorm_eps(float(vcfg.get("layer_norm_eps", 1e-5)))
    writer.add_vision_image_mean([float(x) for x in pre_cfg["image_mean"]])
    writer.add_vision_image_std([float(x) for x in pre_cfg["image_std"]])

    tmap = gguf.get_tensor_name_map(gguf.MODEL_ARCH.MMPROJ, n_layers)
    layer_re = re.compile(r"\.encoder\.layers\.(\d+)\.")

    def _add(name: str, tensor) -> None:
        data = tensor.to(torch.float32).numpy()
        # 2D 이상 행렬은 f16, norm/bias/임베딩 벡터는 f32 (mtmd 관례).
        if data.ndim >= 2:
            data = data.astype(np.float16)
        writer.add_tensor(name, data)

    count = 0
    with safe_open(os.path.join(vision_dir, "model.safetensors"), framework="pt") as f:
        for key in f.keys():
            if not key.startswith("vision_model."):
                continue
            if key.endswith("position_ids"):
                continue  # 가중치가 아닌 인덱스 버퍼(일부 CLIP 체크포인트에 저장돼 있다)
            if key.startswith("vision_model.post_layernorm."):
                continue  # 학습 특징은 post-LN 이전 hidden_states — 넣으면 mtmd 가 적용한다
            m = layer_re.search(key)
            if m and int(m.group(1)) >= n_layers:
                continue  # 특징 층 이후 블록은 계산에 쓰이지 않는다
            mapped = tmap.get_name("vision_tower." + key, try_suffixes=(".weight", ".bias"))
            if mapped is None:
                raise ValueError(f"unmapped CLIP tensor: {key}")
            _add(mapped, f.get_tensor(key))
            count += 1
    for idx in (0, 2):
        _add(f"mm.{idx}.weight", projector[f"proj.{idx}.weight"])
        _add(f"mm.{idx}.bias", projector[f"proj.{idx}.bias"])
        count += 2

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()
    return {"vision_layers": n_layers, "tensors": count, "image_size": int(vcfg["image_size"])}


def prepare(checkpoints_root: str, name: str, workdir: str) -> Dict[str, Any]:
    """커밋 → (merged HF LLM 디렉터리, mmproj GGUF 경로, 메타). convert app 이 호출."""
    ckpt_dir = resolve_checkpoint(checkpoints_root, name)
    vlm_cfg = read_vlm_config(ckpt_dir)
    llm_repo, vision_repo = base_repo_ids(ckpt_dir, vlm_cfg)
    llm_dir = os.path.join(workdir, "merged")
    merged = materialize_llm(ckpt_dir, local_snapshot(llm_repo), llm_dir)
    mmproj_path = os.path.join(workdir, "mmproj.f16.gguf")
    summary = build_mmproj(ckpt_dir, local_snapshot(vision_repo), vlm_cfg, mmproj_path)
    return {"llm_dir": llm_dir, "mmproj_path": mmproj_path, "lora_merged": merged,
            "llm_repo": llm_repo, "vision_repo": vision_repo, "checkpoint": name, **summary}
