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
import shutil
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
# 체크포인트 레지스트리(Phase1) 전용 마운트(models/{name}/checkpoints). tmp_model 과 분리 —
# stop_fine_tuning 의 move_checkpoint_files_to_parent 에 휩쓸리지 않고 영속(레지스트리 API 가 NFS 로 읽음).
# stage2 가 step 마다 경량 체크포인트(LoRA=어댑터)를 여기 저장 + _projector.pt(stage1 projector) 1회.
CKPT_DIR = "/checkpoints"
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


def _resolve_image(ddir, img_ref, image_folder=""):
    """이미지 절대경로 해석. 시도 순서: (1) 명시 ``image_folder`` 기준 (2) 데이터셋 디렉터리
    직속 (3) LLaVA/HF 관례인 ``images/`` 서브디렉터리. 표준 HF VLM 데이터셋(예: LLaVA-CC3M:
    metadata 의 image=bare 파일명 + images.zip→images/)을 데이터 무수정으로 소비하기 위함.
    모든 후보는 ``ddir`` 내부로 봉쇄(traversal 차단) + 실파일 검증. 첫 매치 반환, 없으면 None."""
    rels = []
    if image_folder:
        rels.append(os.path.join(image_folder, img_ref))
    rels.append(img_ref)
    rels.append(os.path.join("images", img_ref))
    for rel in rels:
        try:
            ap = os.path.realpath(os.path.join(ddir, rel))
        except (ValueError, OSError):
            continue
        if os.path.commonpath([ap, ddir]) == ddir and os.path.isfile(ap):
            return ap
    return None


def load_vlm_samples(dataset_path, max_samples=0, image_folder=""):
    """데이터셋 파일 → [{image(abs path), instruction, output}]. 이미지는 데이터셋 디렉터리
    내부로 봉쇄(traversal 차단; images/ 서브디렉터리 포함). 이미지 없는 row 는 스킵(VLM 학습엔 이미지 필수)."""
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
            img_abs = _resolve_image(ddir, img_ref, image_folder)
            if img_abs is None:
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
    """베이스 VLM + 프로세서 로드. transformers 버전 차이를 흡수(Auto 체인).
    trust_remote_code=False — /model(NFS latest_checkpoint)에 주입된 modeling_*.py 임의코드 실행 차단
    (보안리뷰 C-5; compose 도 False). 합성 LLaVA 는 빌트인 아키텍처라 remote code 불필요."""
    from transformers import AutoProcessor
    processor = AutoProcessor.from_pretrained(model_dir, trust_remote_code=False)
    last_err = None
    for cls_name in ("AutoModelForImageTextToText", "AutoModelForVision2Seq",
                     "LlavaForConditionalGeneration"):
        try:
            cls = getattr(__import__("transformers", fromlist=[cls_name]), cls_name)
            # dtype 미지정(fp32 로드) — 학습 중 정밀도는 Trainer 의 bf16/fp16 autocast 가 관리.
            # (fp16 가중치 직접 학습은 grad 불안정 → autocast 에 위임.)
            model = cls.from_pretrained(model_dir, trust_remote_code=False)
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
           report_steps, batch_size=1, weight_decay=0.0, callbacks=None, hf_tensorboard=True,
           eval_dataset=None, eval_steps=0, ckpt_dir=None, save_steps=0, save_total_limit=0,
           load_best=False):
    from transformers import Trainer, TrainingArguments
    use_bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    # held-out 검증셋이 있으면 step 단위 평가 → eval_loss 로깅(콜백이 eval/loss 태그로 기록). 없으면 끔.
    do_eval = eval_dataset is not None and eval_steps and eval_steps > 0
    # 체크포인트 레지스트리(Phase1): ckpt_dir+save_steps 지정 시 step 마다 경량 저장(LoRA=어댑터).
    # save_total_limit 로 캡, eval 있으면 load_best_model_at_end 로 과적합 전 best 보존(prune 면제) +
    # train() 후 best 어댑터를 메모리에 복원 → 이어지는 merge_and_unload 결과=best. HF 제약상 load_best
    # 면 save_strategy==eval_strategy & save_steps==eval_steps 정렬 필요 → 호출부가 save_steps=eval_steps.
    do_save = bool(ckpt_dir) and save_steps and save_steps > 0
    use_load_best = do_save and do_eval and load_best
    args = TrainingArguments(
        # 어댑터 체크포인트는 ckpt_dir/adapters 하위에 — _projector.pt(ckpt_dir 루트)가 Trainer 의
        # output_dir 정리/overwrite 영향 밖에 있도록 분리(리뷰 HIGH). 레지스트리=adapters/checkpoint-*.
        output_dir=(os.path.join(ckpt_dir, "adapters") if do_save else os.path.join("/tmp_model", stage_label)),
        overwrite_output_dir=True,
        num_train_epochs=epochs,
        per_device_train_batch_size=max(1, batch_size),
        per_device_eval_batch_size=max(1, batch_size),
        gradient_accumulation_steps=grad_accum,
        learning_rate=lr,
        warmup_steps=warmup,
        weight_decay=weight_decay,
        logging_dir=LOG_DIR,
        logging_strategy="steps",
        logging_steps=max(1, report_steps),
        save_strategy=("steps" if do_save else "no"),
        save_steps=(save_steps if do_save else None),
        save_total_limit=(save_total_limit if (do_save and save_total_limit) else None),
        load_best_model_at_end=use_load_best,
        metric_for_best_model=("eval_loss" if use_load_best else None),
        greater_is_better=(False if use_load_best else None),
        eval_strategy=("steps" if do_eval else "no"),
        eval_steps=(eval_steps if do_eval else None),
        bf16=use_bf16,
        fp16=not use_bf16 and torch.cuda.is_available(),
        remove_unused_columns=False,    # pixel_values 등 커스텀 컬럼 보존(필수)
        dataloader_pin_memory=False,
        # HF 기본 TensorBoardCallback 은 stage 마다 step 0 으로 리셋 기록 → x축 단절. 연속 step 이
        # 필요하면(hf_tensorboard=False) run() 의 step-offset 커스텀 콜백이 단일 writer 에 기록하고
        # 여기선 끈다. 콜백이 없을 때만(폴백) HF 기본 TB(rewrite_logs→train/* 태그)를 쓴다.
        report_to=(["tensorboard"] if hf_tensorboard else []),
    )
    trainer = Trainer(model=model, args=args, train_dataset=dataset, data_collator=collator,
                      eval_dataset=(eval_dataset if do_eval else None), callbacks=callbacks or [])
    _log(f"[{stage_label}] trainable params = {_trainable_count(model):,}"
         f"{f' | eval every {eval_steps} steps (n={len(eval_dataset)})' if do_eval else ''}")
    trainer.train()
    return trainer


def _build_continuous_tb_callback(log_dir):
    """단일 SummaryWriter 에 stage 간 global_step 을 누적(offset) 기록하는 콜백 → x축 연속.
    HF 기본 TensorBoardCallback(stage 마다 step 0 리셋) 대신 사용. logs 키는 rewrite_logs 와 동일하게
    train/* (eval_*→eval/*) 로 접두 → 플랫폼 FINE_TUNING_LOG_TAGS 와 일치. tensorboard 미설치 시
    (None, None) 반환 → 호출부가 HF 기본 TB 로 폴백."""
    try:
        from torch.utils.tensorboard import SummaryWriter
        from transformers import TrainerCallback
    except Exception:
        return None, None
    writer = SummaryWriter(log_dir)

    class _ContinuousTB(TrainerCallback):
        def __init__(self, w):
            self.writer = w
            self.offset = 0    # 직전 stage 들의 누적 step

        def on_log(self, args, state, control, logs=None, **kwargs):
            if not state.is_world_process_zero or not logs:
                return
            gstep = self.offset + int(state.global_step)
            for k, v in logs.items():
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    continue
                tag = ("eval/" + k[len("eval_"):]) if k.startswith("eval_") else ("train/" + k)
                self.writer.add_scalar(tag, float(v), gstep)
            self.writer.flush()

    return _ContinuousTB(writer), writer


def run(args):
    cont_cb, tb_writer = None, None
    if _is_primary():
        update_finetuning_running_status()
        os.makedirs(LOG_DIR, exist_ok=True)
        # 이전 run 의 tfevents 가 남아 EventAccumulator 가 신·구 데이터를 병합(그래프 오염)하지
        # 않도록 정리(신규 run 은 자기 곡선만 표시).
        for _f in os.listdir(LOG_DIR):
            if "tfevents" in _f:
                try:
                    os.remove(os.path.join(LOG_DIR, _f))
                except OSError:
                    pass
        cont_cb, tb_writer = _build_continuous_tb_callback(LOG_DIR)
        # 체크포인트 레지스트리 디렉터리 초기화 — 이전 run 의 후보만 정리(adapters/ + _projector.pt).
        # 전체 rmtree 대신 한정 — 향후 레지스트리에 사용자 선택/메타가 생겨도 비소유 상태를 지우지
        # 않도록(codex LOW). 폴더 자체는 마운트라 유지.
        try:
            os.makedirs(CKPT_DIR, exist_ok=True)
            for _e in ("adapters", "_projector.pt"):
                _p = os.path.join(CKPT_DIR, _e)
                try:
                    if os.path.isdir(_p):
                        shutil.rmtree(_p)
                    elif os.path.exists(_p):
                        os.remove(_p)
                except OSError:
                    pass
        except OSError:
            pass
        if args.num_gpus and args.num_gpus > 1:
            # 타겟=단일 GPU(과제: 학습 PEFT/경량 지향). 다GPU 는 DDP full-replica 로 동작하나
            # VLM 2-stage 다GPU 동등성은 미검증 — 데모 스코프 밖.
            _log(f"WARNING: num_gpus={args.num_gpus} — VLM 2-stage FT is validated for single-GPU "
                 "only; multi-GPU is out of demo scope.")

    samples = load_vlm_samples(args.dataset_path, max_samples=args.max_samples, image_folder=args.image_folder)
    model, processor = load_vlm_model(MODEL_DIR)    # 디바이스 배치는 Trainer 가 관리(.cuda() X)
    from datasets import Dataset
    # held-out 검증 분할(10%) → eval/loss 곡선(과적합 신호). 표본이 적으면 스킵(degenerate eval 방지).
    n_eval = int(len(samples) * 0.1)
    if n_eval >= 1 and (len(samples) - n_eval) >= 2:
        train_samples, eval_samples = samples[:-n_eval], samples[-n_eval:]
    else:
        train_samples, eval_samples = samples, None
    dataset = Dataset.from_list(train_samples)
    eval_dataset = Dataset.from_list(eval_samples) if eval_samples else None
    collator = VLMCollator(processor, args.cutoff_length)
    vision, projector, lm = get_submodules(model)
    if projector is None or lm is None:
        raise RuntimeError("not a supported LLaVA-style VLM (need multi_modal_projector + "
                           "language_model). 비-LLaVA 아키텍처는 범위 밖.")

    # 스테이지당 학습 step 수(올림) → eval 주기 자동 산출(플랫폼 기본 eval_steps=500 은 소규모 런선
    # 0회·대용량 런선 너무 성김 → 폐기). 목표: 첫 eval 이 항상 일찍(≤500 step) 뜨고 점이 ~10개 이상
    # 생기도록 [10, 500] 클램프. 대용량 런도 첫 점이 ≤500 step 에서 보이고 곡선이 충분히 채워짐.
    _ga = max(1, args.gradient_accumulation_steps)
    _per_epoch = max(1, -(-len(train_samples) // max(1, args.vlm_batch_size) // _ga))  # ceil
    def _eval_every(epochs):
        if eval_dataset is None:
            return 0
        total = max(1, int(_per_epoch * max(1.0, epochs)))
        # 첫 eval 일찍(≤500)·점 충분(~10)·소규모 런도 최소 1회(total 초과 금지, codex MED).
        return min(total, max(1, min(500, total // 10)))

    # 대시보드 진행률(스텝/epoch) — 전체 잡 기준 근사(stage1+stage2 epoch 합). steps_per_epoch=학습셋 기준.
    if _is_primary():
        total_epochs = max(1.0, args.vlm_stage1_epochs + args.num_train_epochs)
        update_steps_per_epoch(steps_per_epoch=_per_epoch)
        _log(f"total stages epochs ~= {total_epochs} | train={len(train_samples)} "
             f"eval={0 if eval_dataset is None else len(eval_dataset)}")

    # ── Stage 1: projector 정렬 (vision + LM freeze) ── (epochs<=0 이면 스킵)
    _set_requires_grad(model, False)
    _set_requires_grad(projector, True)
    if args.vlm_stage1_epochs and args.vlm_stage1_epochs > 0:
        _log("STAGE 1 (projector alignment) start")
        t1 = _train(model, dataset, collator, epochs=args.vlm_stage1_epochs,
                    lr=(args.vlm_stage1_lr if args.vlm_stage1_lr else args.learning_rate),
                    grad_accum=args.gradient_accumulation_steps, warmup=args.warmup_steps,
                    stage_label="stage1_projector", report_steps=10,
                    batch_size=args.vlm_batch_size, weight_decay=args.vlm_weight_decay,
                    callbacks=([cont_cb] if cont_cb else None), hf_tensorboard=(cont_cb is None),
                    eval_dataset=eval_dataset, eval_steps=_eval_every(args.vlm_stage1_epochs))
        if cont_cb:    # stage2 step 이 stage1 끝 step 부터 이어지도록 offset 누적(x축 연속)
            cont_cb.offset += int(t1.state.global_step)
        _log("STAGE 1 done")
    else:
        _log("STAGE 1 skipped (vlm_stage1_epochs<=0)")

    # ── stage1 projector 1회 영속(LoRA 경로) ──────────────────────────────────────
    # stage2 어댑터 체크포인트(PeftModel save)는 projector(비-LoRA·frozen)를 담지 않음(스파이크 #2) →
    # CKPT_DIR/_projector.pt 에 1회 저장(stage2 내내 동일). Phase2 promote 재조립의 building block.
    # ⚠️ run 종료 시 /model(base)이 merged best 로 덮어써지므로(하단 save_pretrained), 임의 step 재현엔
    # _projector+adapter 만으론 부족 — Phase2 promote 는 pre-stage2 base 스냅샷이 추가로 필요(codex HIGH).
    # Phase1 자체는 재조립 불요(auto-best 가 이미 /model). full-FT 는 체크포인트=풀웨이트라 projector 불요.
    if args.used_lora and _is_primary():
        try:
            os.makedirs(CKPT_DIR, exist_ok=True)
            torch.save({k: v.detach().cpu() for k, v in projector.state_dict().items()},
                       os.path.join(CKPT_DIR, "_projector.pt"))
            _log("persisted stage1 projector → _projector.pt (for adapter-checkpoint reload)")
        except Exception as _e:
            _log(f"WARNING: projector persist failed: {_e}")

    # ── Stage 2: LM 지시 튜닝 (vision + projector freeze) ──
    if not (args.num_train_epochs and args.num_train_epochs > 0):
        raise RuntimeError("num_train_epochs must be > 0 (stage2 LM tuning)")
    # 체크포인트 보관 개수(캡): 명시값 우선, 없으면 LoRA=5(경량)/full=2(풀웨이트 디스크 부담).
    _ckpt_n = (args.vlm_save_total_limit if getattr(args, "vlm_save_total_limit", 0)
               else (5 if args.used_lora else 2))
    # stage2 저장 주기: load_best 정렬을 위해 eval_steps 와 일치(eval 있을 때). eval 없으면 epoch당 1회.
    _stage2_eval = _eval_every(args.num_train_epochs)
    _stage2_save = _stage2_eval if _stage2_eval > 0 else max(1, _per_epoch)
    _set_requires_grad(model, False)
    merged_after = False
    if args.used_lora:
        from peft import LoraConfig, get_peft_model
        # LM 어텐션 proj 에 LoRA. 비전타워가 동명(q/k/v/o_proj) 모듈을 가지면 어댑터가 거기에도
        # 붙을 수 있으므로, 래핑 후 LM 외 trainable 은 모두 동결(stage2=언어모델만 학습 보장).
        _tgts = [m.strip() for m in (args.vlm_lora_target_modules or "").split(",")
                 if m.strip() and m.strip().lower() != "none"] \
            or ["q_proj", "k_proj", "v_proj", "o_proj"]
        lora = LoraConfig(r=args.vlm_lora_r, lora_alpha=args.vlm_lora_alpha,
                          lora_dropout=args.vlm_lora_dropout, bias="none",
                          task_type="CAUSAL_LM", target_modules=_tgts)
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
    t2 = _train(model, dataset, collator, epochs=args.num_train_epochs,
           lr=args.learning_rate, grad_accum=args.gradient_accumulation_steps,
           warmup=args.warmup_steps, stage_label="stage2_lm", report_steps=10,
           batch_size=args.vlm_batch_size, weight_decay=args.vlm_weight_decay,
           callbacks=([cont_cb] if cont_cb else None), hf_tensorboard=(cont_cb is None),
           eval_dataset=eval_dataset, eval_steps=_stage2_eval,
           # 체크포인트 레지스트리: step 마다 어댑터 저장(CKPT_DIR/adapters), N개 캡, eval 있으면 best 보존+복원.
           ckpt_dir=CKPT_DIR, save_steps=_stage2_save, save_total_limit=_ckpt_n, load_best=True)
    # load_best_model_at_end 가 best 어댑터를 trainer.model 에 복원 → 명시적으로 그 객체를 merge 대상으로
    # 채택(PeftModel in-place 복원이라 outer ref 와 동일하지만, HF/peft 버전 변동에도 best 보장; 리뷰 MEDIUM).
    model = getattr(t2, "model", model)
    _log("STAGE 2 done")

    # ── 저장 (단독 로드 가능한 full 모델 + 프로세서) ──
    # merge_and_unload 는 전 rank 에서 호출(DDP 로컬 연산; 이 스크립트는 ds_config 미전달이라
    # ZeRO 샤딩 없음 — 각 rank 가 full replica). 디스크 저장은 primary 만(중복/경합 방지).
    final = model.merge_and_unload() if merged_after else model    # LoRA 병합→stage1 proj+stage2 LM
    if tb_writer is not None:    # 연속 TB 기록 flush/close (남은 이벤트 디스크 반영)
        tb_writer.close()
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
    p.add_argument("--image_folder", type=str, default="")            # 이미지 루트(데이터셋 디렉터리 기준 상대). 미지정 시 직속→images/ 자동 폴백
    # VLM 하이퍼파라미터(스케줄러가 is_vlm 일 때 주입; FineTuningConfig vlm_* 매핑).
    p.add_argument("--vlm_stage1_lr", type=float, default=0.0)        # 0=learning_rate 공용
    p.add_argument("--vlm_batch_size", type=int, default=1)
    p.add_argument("--vlm_weight_decay", type=float, default=0.0)
    p.add_argument("--vlm_lora_r", type=int, default=8)
    p.add_argument("--vlm_lora_alpha", type=int, default=16)
    p.add_argument("--vlm_lora_dropout", type=float, default=0.05)
    p.add_argument("--vlm_lora_target_modules", type=str, default="")
    p.add_argument("--vlm_save_total_limit", type=int, default=0)     # 체크포인트 보관 캡(0=기본: LoRA5/full2)
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
