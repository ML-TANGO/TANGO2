#!/usr/bin/env python3
"""
eval/generate.py — 검증셋 전체에 대해 한 체크포인트의 응답을 생성한다.

LLaVA 형식 JSON 을 그대로 입력으로 쓴다. 학습 때와 같은 프롬프트가 그 파일에
들어 있으므로, 프롬프트를 여기서 다시 만들지 않는다. 다시 만들면 학습 입력과
어긋날 여지가 생긴다.

출력은 JSONL 이며 한 줄이 한 샘플이다.
  {"id": ..., "image": ..., "reference": ..., "prediction": ..., "raw": ...}

사용:
  python eval/generate.py \
      --projector_path checkpoints/<ckpt>/projector.bin \
      --lora_path      checkpoints/<ckpt> \
      --llm_model      /home/yvvyee/data/Models/Qwen3-8B \
      --data_path      data/sds_valid_ko_1k.json \
      --image_dir      /home/yvvyee/data/AIVN-SDS/20260728 \
      --out            results/eval_20260728/<name>.jsonl
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import argparse

import torch
from PIL import Image

from model import (
    VLMConfig, build_model, PROJECTOR_TYPES,
    PROJECTOR_CONFIG_KEYS, load_projector_config, resolve_projector_settings,
)


def parse_args():
    p = argparse.ArgumentParser("검증셋 일괄 생성")
    p.add_argument("--vision_model", default="openai/clip-vit-large-patch14-336")
    p.add_argument("--llm_model", required=True)
    p.add_argument("--projector_path", required=True)
    p.add_argument("--lora_path", default=None)
    p.add_argument("--projector_type", default=None, choices=list(PROJECTOR_TYPES),
                   help="생략하면 체크포인트의 vlm_config.json 을 따르고, "
                        "그것도 없으면 VLMConfig 기본값을 쓴다")

    p.add_argument("--data_path", required=True)
    p.add_argument("--image_dir", required=True)
    p.add_argument("--out", required=True)

    p.add_argument("--limit", type=int, default=0, help="앞 N 건만 (0 이면 전체)")
    p.add_argument("--batch_size", type=int, default=8)
    p.add_argument("--max_new_tokens", type=int, default=512)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--dtype", default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])
    return p.parse_args()


def strip_think(text: str) -> str:
    """Qwen3 는 </think> 앞에 사고 과정을 낸다. 채점 대상은 그 뒤쪽이다."""
    if "</think>" in text:
        return text.split("</think>")[-1].strip()
    return text.strip()


def main():
    args = parse_args()
    DTYPE = {"bfloat16": torch.bfloat16, "float16": torch.float16,
             "float32": torch.float32}[args.dtype]
    device = torch.device(args.device)

    data = json.load(open(args.data_path, encoding="utf-8"))
    if args.limit:
        data = data[: args.limit]
    print(f"[Gen] 샘플 {len(data):,}건  ({args.data_path})", flush=True)

    # ── 프로젝터 구성 ─────────────────────────────────────────────────────────
    settings, sources = resolve_projector_settings(
        {k: (args.projector_type if k == "projector_type" else None)
         for k in PROJECTOR_CONFIG_KEYS},
        load_projector_config(args.projector_path),
    )
    print(f"[Gen] projector_type = {settings['projector_type']} "
          f"(from {sources['projector_type']})", flush=True)

    config = VLMConfig(
        vision_model_name=args.vision_model,
        llm_model_name=args.llm_model,
        vision_feature_layer=-2,
        vision_feature_select_strategy="patch",
        freeze_vision=True,
        freeze_llm=True,
        **settings,
    )
    model = build_model(config, torch_dtype=DTYPE)

    proj_state = torch.load(args.projector_path, map_location="cpu", weights_only=True)
    model.projector.load_weights(proj_state)
    print(f"[Gen] projector 적재: {args.projector_path}", flush=True)

    if args.lora_path:
        from peft import PeftModel
        model.language_model = PeftModel.from_pretrained(
            model.language_model, args.lora_path
        )
        model.language_model = model.language_model.merge_and_unload()
        print(f"[Gen] LoRA 병합: {args.lora_path}", flush=True)

    model = model.to(device).eval()
    tok = model.tokenizer
    proc = model.vision_encoder.image_processor

    # 좌측 패딩이라야 생성이 마지막 토큰에서 이어진다. 우측 패딩이면 패딩 뒤에서
    # 이어 쓰게 되어 배치 결과가 단건 결과와 달라진다.
    tok.padding_side = "left"
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    fout = open(args.out, "w", encoding="utf-8")

    gen_kwargs = dict(
        max_new_tokens=args.max_new_tokens,
        do_sample=False,                 # greedy 고정. 비교 재현성을 위해서다.
        pad_token_id=tok.pad_token_id,
        eos_token_id=tok.eos_token_id,
    )

    t0 = time.time()
    done = 0
    for start in range(0, len(data), args.batch_size):
        chunk = data[start : start + args.batch_size]

        prompts, pixels = [], []
        for s in chunk:
            human = s["conversations"][0]["value"]
            prompts.append(tok.apply_chat_template(
                [{"role": "user", "content": human}],
                tokenize=False, add_generation_prompt=True,
            ))
            img = Image.open(os.path.join(args.image_dir, s["image"])).convert("RGB")
            pixels.append(proc(images=img, return_tensors="pt").pixel_values[0])

        enc = tok(prompts, add_special_tokens=False, return_tensors="pt",
                  padding=True)
        input_ids = enc.input_ids.to(device)
        attn = enc.attention_mask.to(device)
        pixel_values = torch.stack(pixels).to(device, dtype=DTYPE)

        with torch.no_grad():
            out = model.generate(
                input_ids=input_ids,
                attention_mask=attn,
                pixel_values=pixel_values,
                **gen_kwargs,
            )

        texts = tok.batch_decode(out, skip_special_tokens=True)
        for s, raw in zip(chunk, texts):
            fout.write(json.dumps({
                "id": s["id"],
                "image": s["image"],
                "reference": s["conversations"][1]["value"],
                "prediction": strip_think(raw),
                "raw": raw,
            }, ensure_ascii=False) + "\n")
        fout.flush()

        done += len(chunk)
        el = time.time() - t0
        print(f"[Gen] {done:5d}/{len(data)}  {el:7.1f}s  "
              f"({done / max(el, 1e-9):.2f} samp/s)", flush=True)

    fout.close()
    print(f"[Gen] 완료 → {args.out}  ({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
