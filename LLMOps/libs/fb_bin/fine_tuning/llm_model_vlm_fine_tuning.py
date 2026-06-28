#!/usr/bin/env python3
"""내부(플랫폼 소유) VLM 2-stage 파인튜닝 — LLaVA 류.

기존 텍스트 LLM 파인튜닝(``llm_model_fine_tuning.py``)과 **별개 경로**다. 스케줄러가
``fine_tuning_config.vlm == 1`` 일 때 이 스크립트를 deepspeed 런처로 실행한다(텍스트 FT 무손상).

흐름(텍스트 FT 와 동일 마운트·DB 계약):
  - 베이스 VLM: ``/model`` (플랫폼 model 엔티티 latest_checkpoint 마운트). LlavaForConditionalGeneration 류.
  - 데이터셋: ``--dataset_path`` (이미지+텍스트 jsonl/json/csv). 이미지는 데이터셋 디렉터리 기준 상대경로(봉쇄).
  - **2-stage**(단일 잡 순차):
      stage1: vision_tower + language_model freeze, ``multi_modal_projector`` 만 학습(이미지→LLM 정렬).
      stage2: vision_tower(+ stage1 projector) freeze, language_model 학습(used_lora=1→LoRA, 0→full) — 지시 튜닝.
  - 저장: ``/model`` 에 최종 모델+프로세서. LoRA 는 merge_and_unload 로 단독 로드 가능한 full 로 저장.
  - 상태: ``db`` 의 running/steps_per_epoch/error (없으면 no-op → 스탠드얼론 테스트 가능).

범위(ETRI 요구: SDS 외 별도 내부 VLM FT 로직, "돌아가는" 최소 수직 슬라이스): 고도화(프롬프트 토큰 마스킹,
멀티이미지, 대형모델 분산, 비-LLaVA 아키텍처)는 의도적 제외.
"""
import argparse
import json
import os
import sys
import traceback

import torch
from PIL import Image

# DB 상태 업데이트 — 플랫폼 잡에선 /fine_tuning/db.py 가 마운트되어 있고, 스탠드얼론
# 테스트(클러스터 직접 실행)에선 없으므로 soft import(없으면 no-op).
try:
    from db import (update_finetuning_error_status,
                    update_finetuning_running_status, update_steps_per_epoch)
except Exception:    # pragma: no cover - 테스트/오프라인 폴백
    def update_finetuning_running_status(): return False
    def update_finetuning_error_status(): return False
    def update_steps_per_epoch(steps_per_epoch): return False


MODEL_DIR = "/model"
LOG_DIR = "/logs"
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
_IMAGE_KEYS = ("image", "image_path", "image_url", "img", "img_path", "image_file",
               "file_name", "filename", "file")
_INSTR_KEYS = ("instruction", "prompt", "question", "query", "input", "text")
_OUTPUT_KEYS = ("output", "answer", "response", "completion", "label", "caption",
                "target", "reference")


def _log(msg):
    print(f"[vlm-ft] {msg}", flush=True)


def _is_primary():
    return (int(os.getenv("RANK", "0")) == 0 and int(os.getenv("LOCAL_RANK", "0")) == 0
            and int(os.getenv("POD_INDEX", "0")) == 0)


# ── 데이터셋 (이미지 + 텍스트) ───────────────────────────────────────────────
def _pick(row, keys):
    low = {str(k).lower(): k for k in row.keys()}
    for k in keys:
        actual = low.get(k)
        if actual is None:
            continue
        v = row.get(actual)
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() not in ("nan", "nat", "<na>", "none", "null"):
            return s
    return None


def _read_rows(path):
    """jsonl/json/csv → row(dict) 리스트."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".jsonl":
        rows = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows
    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("data") or []
        return data if isinstance(data, list) else []
    if ext == ".csv":
        import csv
        with open(path, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    raise ValueError(f"unsupported dataset extension: {ext}")


def load_vlm_samples(dataset_path, max_samples=0):
    """데이터셋 파일 → [{image(abs path), instruction, output}]. 이미지는 데이터셋 디렉터리
    내부로 봉쇄(traversal 차단). 이미지 없는 row 는 스킵(VLM 학습엔 이미지 필수)."""
    ddir = os.path.realpath(os.path.dirname(dataset_path))
    rows = _read_rows(dataset_path)
    samples, skipped = [], 0
    for row in rows:
        if not isinstance(row, dict):
            skipped += 1
            continue
        img_ref = _pick(row, _IMAGE_KEYS)
        if not img_ref or os.path.splitext(img_ref.split("?")[0])[1].lower() not in _IMAGE_EXTS:
            skipped += 1
            continue
        # 데이터셋 디렉터리 봉쇄(다른 워크스페이스/시스템 파일 접근 차단) + 디코드 가능 검증
        # (손상/부분쓰기 이미지를 load 시점에 걸러 mid-train 크래시 방지). NUL 등으로 realpath 가
        # ValueError 를 던져도 행만 스킵(잡 전체 중단 방지) — eval 서비스 패턴 동형.
        try:
            img_abs = os.path.realpath(os.path.join(ddir, img_ref))
            if os.path.commonpath([img_abs, ddir]) != ddir or not os.path.isfile(img_abs):
                skipped += 1
                continue
            with Image.open(img_abs) as _im:
                _im.verify()
        except Exception:
            skipped += 1
            continue
        instruction = _pick(row, _INSTR_KEYS) or "Describe the image."
        output = _pick(row, _OUTPUT_KEYS) or ""
        samples.append({"image": img_abs, "instruction": instruction, "output": output})
        if max_samples and len(samples) >= max_samples:
            break
    _log(f"loaded {len(samples)} vlm samples (skipped={skipped}) from {dataset_path}")
    if not samples:
        raise ValueError("no usable image+text samples (need an image column + image files)")
    return samples


class VLMCollator:
    """배치 → 프로세서로 {input_ids, attention_mask, pixel_values, labels}. LLaVA chat template
    우선, 없으면 'USER: <image>\\n{q} ASSISTANT: {a}' 폴백. labels=input_ids(pad=-100).
    (프롬프트 토큰 마스킹은 범위 밖 — full-sequence LM loss.)"""
    def __init__(self, processor, cutoff_length):
        self.processor = processor
        self.cutoff = cutoff_length
        self.image_token = getattr(processor, "image_token", None) or "<image>"

    def _build_text(self, instruction, output):
        # 데이터 텍스트에 들어온 리터럴 image 토큰 제거 — placeholder 가 1개를 초과하면 공급
        # 이미지(1장)와 토큰 수가 어긋나 학습 불가(char-clip 으로도 안 막히는 케이스).
        instruction = (instruction or "").replace(self.image_token, " ")
        output = (output or "").replace(self.image_token, " ")
        conv = [
            {"role": "user", "content": [{"type": "image"},
                                         {"type": "text", "text": instruction}]},
            {"role": "assistant", "content": [{"type": "text", "text": output}]},
        ]
        try:
            return self.processor.apply_chat_template(conv, tokenize=False,
                                                      add_generation_prompt=False)
        except Exception:
            return f"USER: {self.image_token}\n{instruction} ASSISTANT: {output}"

    def _clip(self, s):
        # 텍스트만 길이 제한(이미지 토큰은 프로세서가 고정 개수로 확장하므로 결합 시퀀스를
        # truncation 하면 이미지 토큰이 잘려 token-count mismatch → 학습 불가). 텍스트를 미리
        # 단어 단위로 자른다(이미지 토큰 보존).
        return s if len(s) <= self.cutoff * 4 else s[: self.cutoff * 4]

    def __call__(self, examples):
        texts = [self._build_text(self._clip(e["instruction"]), self._clip(e["output"]))
                 for e in examples]
        images = [Image.open(e["image"]).convert("RGB") for e in examples]
        # truncation=False — 결합 시퀀스(이미지 토큰 + 텍스트)를 자르지 않음(토큰 수 일치 보장).
        batch = self.processor(text=texts, images=images, return_tensors="pt", padding=True)
        labels = batch["input_ids"].clone()
        pad_id = self.processor.tokenizer.pad_token_id
        if pad_id is not None:
            labels[labels == pad_id] = -100
        batch["labels"] = labels
        return batch


# ── 모델 (서브모듈 freeze) ───────────────────────────────────────────────────
def _find_module(model, names):
    for path in names:
        m, ok = model, True
        for part in path.split("."):
            if hasattr(m, part):
                m = getattr(m, part)
            else:
                ok = False
                break
        if ok:
            return m
    return None


def _set_requires_grad(module, flag):
    if module is None:
        return 0
    n = 0
    for p in module.parameters():
        p.requires_grad = flag
        n += 1
    return n


def _trainable_count(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def load_vlm_model(model_dir):
    """베이스 VLM + 프로세서 로드. transformers 버전 차이를 흡수(Auto 체인)."""
    from transformers import AutoProcessor
    processor = AutoProcessor.from_pretrained(model_dir, trust_remote_code=True)
    last_err = None
    for cls_name in ("AutoModelForImageTextToText", "AutoModelForVision2Seq",
                     "LlavaForConditionalGeneration"):
        try:
            cls = getattr(__import__("transformers", fromlist=[cls_name]), cls_name)
            # dtype 미지정(fp32 로드) — 학습 중 정밀도는 Trainer 의 bf16/fp16 autocast 가 관리.
            # (fp16 가중치 직접 학습은 grad 불안정 → autocast 에 위임.)
            model = cls.from_pretrained(model_dir, trust_remote_code=True)
            _log(f"loaded VLM via {cls_name}")
            return model, processor
        except Exception as e:    # noqa: BLE001 - 다음 Auto 클래스로 폴백
            last_err = e
    raise RuntimeError(f"failed to load VLM from {model_dir}: {last_err}")


def get_submodules(model):
    vision = _find_module(model, ["vision_tower", "model.vision_tower", "visual"])
    projector = _find_module(model, ["multi_modal_projector", "model.multi_modal_projector",
                                     "mm_projector"])
    # language_model 후보만 — 'model.model'(백본 트렁크) 폴백은 비전타워/임베딩까지 포함해
    # stage2 freeze 불변식을 깨므로 제외. 못 찾으면 None → 호출부에서 명확히 실패.
    lm = _find_module(model, ["language_model", "model.language_model",
                              "model.text_model", "text_model"])
    return vision, projector, lm


# ── 학습 (stage 1: projector / stage 2: LM) ──────────────────────────────────
def _train(model, dataset, collator, *, epochs, lr, grad_accum, warmup, stage_label,
           report_steps):
    from transformers import Trainer, TrainingArguments
    use_bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    args = TrainingArguments(
        output_dir=os.path.join("/tmp_model", stage_label),
        overwrite_output_dir=True,
        num_train_epochs=epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=grad_accum,
        learning_rate=lr,
        warmup_steps=warmup,
        logging_dir=LOG_DIR,
        logging_strategy="steps",
        logging_steps=max(1, report_steps),
        save_strategy="no",
        bf16=use_bf16,
        fp16=not use_bf16 and torch.cuda.is_available(),
        remove_unused_columns=False,    # pixel_values 등 커스텀 컬럼 보존(필수)
        dataloader_pin_memory=False,
        report_to=[],
    )
    trainer = Trainer(model=model, args=args, train_dataset=dataset, data_collator=collator)
    _log(f"[{stage_label}] trainable params = {_trainable_count(model):,}")
    trainer.train()
    return trainer


def run(args):
    if _is_primary():
        update_finetuning_running_status()
        os.makedirs(LOG_DIR, exist_ok=True)
        if args.num_gpus and args.num_gpus > 1:
            # 타겟=단일 GPU(과제: 학습 PEFT/경량 지향). 다GPU 는 DDP full-replica 로 동작하나
            # VLM 2-stage 다GPU 동등성은 미검증 — 데모 스코프 밖.
            _log(f"WARNING: num_gpus={args.num_gpus} — VLM 2-stage FT is validated for single-GPU "
                 "only; multi-GPU is out of demo scope.")

    samples = load_vlm_samples(args.dataset_path, max_samples=args.max_samples)
    model, processor = load_vlm_model(MODEL_DIR)    # 디바이스 배치는 Trainer 가 관리(.cuda() X)
    from datasets import Dataset
    dataset = Dataset.from_list(samples)
    collator = VLMCollator(processor, args.cutoff_length)
    vision, projector, lm = get_submodules(model)
    if projector is None or lm is None:
        raise RuntimeError("not a supported LLaVA-style VLM (need multi_modal_projector + "
                           "language_model). 비-LLaVA 아키텍처는 범위 밖.")

    # 대시보드 진행률(스텝/epoch) — 전체 잡 기준 근사(stage1+stage2 epoch 합).
    if _is_primary():
        total_epochs = max(1.0, args.vlm_stage1_epochs + args.num_train_epochs)
        update_steps_per_epoch(steps_per_epoch=max(1, int(len(samples) / max(1, args.gradient_accumulation_steps))))
        _log(f"total stages epochs ~= {total_epochs}")

    # ── Stage 1: projector 정렬 (vision + LM freeze) ── (epochs<=0 이면 스킵)
    _set_requires_grad(model, False)
    _set_requires_grad(projector, True)
    if args.vlm_stage1_epochs and args.vlm_stage1_epochs > 0:
        _log("STAGE 1 (projector alignment) start")
        _train(model, dataset, collator, epochs=args.vlm_stage1_epochs, lr=args.learning_rate,
               grad_accum=args.gradient_accumulation_steps, warmup=args.warmup_steps,
               stage_label="stage1_projector", report_steps=10)
        _log("STAGE 1 done")
    else:
        _log("STAGE 1 skipped (vlm_stage1_epochs<=0)")

    # ── Stage 2: LM 지시 튜닝 (vision + projector freeze) ──
    if not (args.num_train_epochs and args.num_train_epochs > 0):
        raise RuntimeError("num_train_epochs must be > 0 (stage2 LM tuning)")
    _set_requires_grad(model, False)
    merged_after = False
    if args.used_lora:
        from peft import LoraConfig, get_peft_model
        # LM 어텐션 proj 에 LoRA. 비전타워가 동명(q/k/v/o_proj) 모듈을 가지면 어댑터가 거기에도
        # 붙을 수 있으므로, 래핑 후 LM 외 trainable 은 모두 동결(stage2=언어모델만 학습 보장).
        lora = LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, bias="none",
                          task_type="CAUSAL_LM",
                          target_modules=["q_proj", "k_proj", "v_proj", "o_proj"])
        model = get_peft_model(model, lora)
        kept = 0
        for n, prm in model.named_parameters():
            if prm.requires_grad and "language_model" not in n:
                prm.requires_grad_(False)
            elif prm.requires_grad:
                kept += 1
        merged_after = True
        _log(f"STAGE 2 (LoRA on language_model) start — LM LoRA tensors kept={kept}")
    else:
        if lm is None:
            raise RuntimeError("full stage2 requires a language_model submodule (none found)")
        _set_requires_grad(lm, True)
        # lm 이 vision/projector 의 부모일 수 있으므로 LM unfreeze 뒤 재동결(freeze 불변식 보장).
        _set_requires_grad(vision, False)
        _set_requires_grad(projector, False)
        _log("STAGE 2 (full language_model) start")
    _train(model, dataset, collator, epochs=args.num_train_epochs,
           lr=args.learning_rate, grad_accum=args.gradient_accumulation_steps,
           warmup=args.warmup_steps, stage_label="stage2_lm", report_steps=10)
    _log("STAGE 2 done")

    # ── 저장 (단독 로드 가능한 full 모델 + 프로세서) ──
    # merge_and_unload 는 전 rank 에서 호출(DDP 로컬 연산; 이 스크립트는 ds_config 미전달이라
    # ZeRO 샤딩 없음 — 각 rank 가 full replica). 디스크 저장은 primary 만(중복/경합 방지).
    final = model.merge_and_unload() if merged_after else model    # LoRA 병합→stage1 proj+stage2 LM
    if _is_primary():
        final.save_pretrained(MODEL_DIR, safe_serialization=True)
        processor.save_pretrained(MODEL_DIR)
        _log(f"saved VLM to {MODEL_DIR}")


def main():
    p = argparse.ArgumentParser(description="Internal VLM 2-stage fine-tuning (LLaVA-style).")
    # 텍스트 FT 와 동일한 런처 계약(deepspeed 가 주입).
    p.add_argument("--local_rank", type=int, default=0)
    p.add_argument("--num_nodes", type=int, default=1)
    p.add_argument("--num_gpus", type=int, default=1)
    p.add_argument("--dataset_path", type=str, required=True)
    p.add_argument("--num_train_epochs", type=float, default=1.0)     # stage2
    p.add_argument("--vlm_stage1_epochs", type=float, default=1.0)    # stage1 projector
    p.add_argument("--gradient_accumulation_steps", type=int, default=1)
    p.add_argument("--cutoff_length", type=int, default=1024)
    p.add_argument("--learning_rate", type=float, default=2e-5)
    p.add_argument("--warmup_steps", type=int, default=0)
    p.add_argument("--used_lora", type=int, default=1)                # stage2: 1=LoRA, 0=full
    p.add_argument("--max_samples", type=int, default=0)              # 0=전체(데모는 소량 권장)
    # 스케줄러가 FineTuningConfig 의 모든 키를 --key=value 로 넘기므로 미지정 인자는 무시.
    args, _unknown = p.parse_known_args()

    try:
        run(args)
        _log("VLM FINE TUNING SUCCESS")
    except Exception:
        traceback.print_exc()
        if _is_primary():
            update_finetuning_error_status()
        sys.exit(1)


if __name__ == "__main__":
    main()
