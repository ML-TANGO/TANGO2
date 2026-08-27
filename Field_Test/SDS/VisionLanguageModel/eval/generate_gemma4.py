#!/usr/bin/env python3
"""
eval/generate_gemma4.py — 네이티브 Gemma 4 체크포인트로 검증셋 응답을 생성한다.

eval/generate.py 는 VisionLanguageModelV2 전용이다. 그쪽은 동결 CLIP 과 직접
구현한 프로젝터를 들고 pixel_values 를 CLIPImageProcessor 로 만든다. Gemma 4 는
비전 타워와 커넥터를 자기가 들고 있고 전처리 단계에서 패치화까지 마친 텐서와
패치 좌표를 함께 받으므로 별도 경로가 필요하다.

출력 형식은 eval/generate.py 와 같은 JSONL 이다. 그래야 eval/metrics.py 와
eval/aggregate.py 를 그대로 쓸 수 있다.

사용:
  python eval/generate_gemma4.py \
      --base_model  google/gemma-4-E4B-it \
      --ckpt        checkpoints/gemma4_e4b_sds_ko_9k_lora \
      --data_path   data/sds_valid_ko_1k.json \
      --image_dir   /home/yvvyee/data/AIVN-SDS/20260728 \
      --out         results/eval_20260728/gemma4_sds9k.jsonl
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import argparse

import torch
from PIL import Image
from transformers import AutoConfig, AutoProcessor, Gemma4ForConditionalGeneration


def parse_args():
    p = argparse.ArgumentParser("Gemma 4 검증셋 일괄 생성")
    p.add_argument("--base_model", required=True,
                   help="gemma-4-E4B-it 경로 또는 Hub id")
    p.add_argument("--ckpt", default=None,
                   help="학습 산출 디렉토리. connector.bin 과 LoRA 어댑터를 읽는다. "
                        "생략하면 사전학습 상태 그대로 생성한다")
    p.add_argument("--data_path", required=True)
    p.add_argument("--image_dir", required=True)
    p.add_argument("--out", required=True)

    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--batch_size", type=int, default=4)
    p.add_argument("--max_new_tokens", type=int, default=512)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--dtype", default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])
    return p.parse_args()


def build(args, dtype, device):
    """학습과 같은 구성으로 적재한다. 오디오는 뺀다."""
    config = AutoConfig.from_pretrained(args.base_model)
    config.audio_config = None
    model = Gemma4ForConditionalGeneration.from_pretrained(
        args.base_model, config=config, dtype=dtype)

    if args.ckpt:
        # 커넥터를 먼저 얹고 LoRA 를 나중에 붙인다. 순서를 바꾸면 PEFT 가 감싼
        # 뒤가 되어 embed_vision 에 닿는 경로가 달라진다.
        conn = os.path.join(args.ckpt, "connector.bin")
        if os.path.exists(conn):
            state = torch.load(conn, map_location="cpu", weights_only=True)
            model.model.embed_vision.load_state_dict(state)
            print(f"[Gen] 커넥터 적재: {conn}", flush=True)
        else:
            print(f"[Gen] 경고: {conn} 없음. 사전학습 커넥터를 그대로 씁니다.",
                  flush=True)

        if os.path.exists(os.path.join(args.ckpt, "adapter_config.json")):
            from peft import PeftModel
            model.model.language_model = PeftModel.from_pretrained(
                model.model.language_model, args.ckpt)
            model.model.language_model = model.model.language_model.merge_and_unload()
            print(f"[Gen] LoRA 병합: {args.ckpt}", flush=True)
        else:
            print(f"[Gen] 경고: {args.ckpt} 에 어댑터가 없습니다.", flush=True)

    return model.to(device).eval()


def main():
    args = parse_args()
    dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16,
             "float32": torch.float32}[args.dtype]
    device = torch.device(args.device)

    data = json.load(open(args.data_path, encoding="utf-8"))
    if args.limit:
        data = data[: args.limit]
    print(f"[Gen] 샘플 {len(data):,}건  ({args.data_path})", flush=True)

    # 프로세서는 체크포인트에 함께 저장해 두었으므로 그쪽을 먼저 쓴다. 학습에
    # 쓴 것과 같은 채팅 템플릿이라야 생성 입력이 학습 입력과 맞는다.
    proc_src = args.ckpt if (args.ckpt and os.path.exists(
        os.path.join(args.ckpt, "processor_config.json"))) else args.base_model
    processor = AutoProcessor.from_pretrained(proc_src)
    print(f"[Gen] 프로세서: {proc_src}", flush=True)

    model = build(args, dtype, device)

    tok = processor.tokenizer
    tok.padding_side = "left"       # 생성이 마지막 토큰에서 이어지도록
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    fout = open(args.out, "w", encoding="utf-8")

    t0 = time.time()
    done = 0
    for start in range(0, len(data), args.batch_size):
        chunk = data[start : start + args.batch_size]

        msgs = []
        for s in chunk:
            human = s["conversations"][0]["value"].replace("<image>", "").lstrip("\n")
            img = Image.open(os.path.join(args.image_dir, s["image"])).convert("RGB")
            msgs.append([{"role": "user", "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": human},
            ]}])

        enc = processor.apply_chat_template(
            msgs, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt", padding=True,
        )
        enc = {k: (v.to(device, dtype=dtype) if k == "pixel_values"
                   else v.to(device))
               for k, v in enc.items() if hasattr(v, "to")}
        prompt_len = enc["input_ids"].shape[1]

        with torch.no_grad():
            out = model.generate(
                **enc,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,            # greedy 고정
                pad_token_id=tok.pad_token_id,
            )

        # generate 가 프롬프트를 포함해 돌려주므로 새로 만든 부분만 자른다.
        texts = tok.batch_decode(out[:, prompt_len:], skip_special_tokens=True)
        for s, raw in zip(chunk, texts):
            fout.write(json.dumps({
                "id": s["id"],
                "image": s["image"],
                "reference": s["conversations"][1]["value"],
                "prediction": raw.strip(),
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
