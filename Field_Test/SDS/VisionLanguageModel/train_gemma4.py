"""
train_gemma4.py — 네이티브 Gemma 4 멀티모달 모델 학습

이 저장소의 train.py 는 동결 CLIP 과 직접 만든 프로젝터를 언어 모델에 붙이는
구조를 학습한다. Gemma 4 는 비전 타워와 커넥터를 이미 갖고 있고 사전학습도
그 셋이 함께 되어 있어 같은 틀에 얹을 수 없다. 그래서 별도 진입점을 둔다.

Gemma4Model 의 구성은 이 저장소의 3 분할과 같은 모양이다.
    vision_tower    Gemma4VisionModel            167.36 M
    embed_vision    RMSNorm + Linear(768→2560)     1.97 M   ← 커넥터
    language_model  Gemma4TextModel             7463.01 M
    audio_tower / embed_audio                    제외

오디오는 config.audio_config 를 None 으로 두어 뺀다. 그러면 audio_tower 와
embed_audio 가 모두 None 이 되고, 사전학습 가중치의 오디오 키는 unexpected 로
경고만 남는다. 실측으로 확인했다.

학습 단계 (--train_type):
    connector  비전 타워와 언어 모델을 동결하고 커넥터만 학습한다.
               이 저장소 train.py 의 projector 단계에 대응한다.
    lora       커넥터와 언어 모델 LoRA 를 함께 학습한다. 비전 타워는 동결이다.
               train.py 의 lora 단계에 대응한다.
    text_lora  이미지를 쓰지 않고 언어 모델 LoRA 만 학습한다. LLaMarine 처럼
               텍스트 전용 도메인 데이터를 얹는 단계다.

사용:
  python train_gemma4.py --train_type lora \\
      --model_path /home/ywlee/SSD/checkpoints/gemma-4-E4B-it \\
      --data_path  data/sds_train_ko_9k.json \\
      --image_dir  ../dataset/20260728 \\
      --valid_data_path data/sds_valid_ko_1k.json \\
      --output_dir checkpoints/gemma4_sds_ko_9k
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json

import torch
from transformers import (
    AutoConfig, AutoProcessor, Gemma4ForConditionalGeneration,
    Trainer, TrainingArguments,
)

from data.gemma4_dataset import (
    Gemma4SDSDataset, Gemma4TextDataset, Gemma4Collator,
)

TRAIN_TYPES = ("connector", "lora", "text_lora")

# Gemma 4 텍스트 모델의 어텐션과 MLP 선형층 이름. 실측으로 확인했으며
# Llama 와 Qwen 계열과 같다. k_proj 와 v_proj 는 KV 공유 때문에 층 수보다
# 적게 나타나지만 이름으로 지정하는 데에는 영향이 없다.
#
# per_layer_input_gate, per_layer_projection, per_layer_model_projection 은
# Per-Layer Embedding 경로의 선형층이다. 기본으로는 넣지 않는다. 이 저장소의
# 다른 계열과 같은 7 개 대상으로 두어야 비교가 되기 때문이다.
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj"]


def parse_args():
    p = argparse.ArgumentParser("Gemma 4 네이티브 멀티모달 학습")

    p.add_argument("--model_path", required=True,
                   help="gemma-4-E4B-it 경로 또는 Hub id")
    p.add_argument("--train_type", default="lora", choices=TRAIN_TYPES)
    p.add_argument("--resume_lora_path", default=None,
                   help="이어받을 LoRA 어댑터 디렉토리")
    p.add_argument("--connector_path", default=None,
                   help="이어받을 커넥터 가중치(connector.bin). 생략하면 "
                        "사전학습된 embed_vision 을 그대로 쓴다")

    p.add_argument("--data_path", required=True)
    p.add_argument("--image_dir", default=None,
                   help="text_lora 가 아니면 필수")
    p.add_argument("--valid_data_path", default=None)
    p.add_argument("--valid_image_dir", default=None)
    p.add_argument("--max_seq_len", type=int, default=2048)

    p.add_argument("--output_dir", required=True)
    p.add_argument("--num_epochs", type=float, default=3.0)
    p.add_argument("--batch_size", type=int, default=1)
    p.add_argument("--eval_batch_size", type=int, default=None)
    p.add_argument("--grad_accum", type=int, default=32)
    p.add_argument("--learning_rate", type=float, default=None,
                   help="생략 시 connector 1e-3, lora 2e-4, text_lora 5e-5")
    p.add_argument("--lr_scheduler", default="cosine",
                   choices=["cosine", "linear", "constant"])
    p.add_argument("--warmup_ratio", type=float, default=0.03)
    p.add_argument("--max_steps", type=int, default=-1)
    p.add_argument("--save_steps", type=int, default=200)
    p.add_argument("--save_total_limit", type=int, default=2)
    p.add_argument("--eval_steps", type=int, default=None)
    p.add_argument("--logging_steps", type=int, default=10)

    p.add_argument("--lora_r", type=int, default=128)
    p.add_argument("--lora_alpha", type=int, default=256)
    p.add_argument("--lora_dropout", type=float, default=0.05)

    p.add_argument("--dtype", default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])
    p.add_argument("--gradient_checkpointing", action="store_true", default=True)
    p.add_argument("--dataloader_workers", type=int, default=4)
    p.add_argument("--deepspeed", default=None)
    p.add_argument("--wandb_project", default=None)
    p.add_argument("--wandb_run_name", default=None)

    args = p.parse_args()
    if args.train_type != "text_lora" and not args.image_dir:
        p.error("--image_dir 는 connector 와 lora 단계에서 필수입니다")
    return args


def build_model(args, dtype):
    """오디오를 뺀 Gemma 4 를 적재하고 단계에 맞게 학습 대상을 정한다."""
    config = AutoConfig.from_pretrained(args.model_path)
    config.audio_config = None          # 오디오 제외
    config.text_config.use_cache = False

    model = Gemma4ForConditionalGeneration.from_pretrained(
        args.model_path, config=config, dtype=dtype,
    )
    inner = model.model
    print(f"[Gemma4] audio_tower={inner.audio_tower}  embed_audio={inner.embed_audio}")

    if args.connector_path:
        state = torch.load(args.connector_path, map_location="cpu", weights_only=True)
        inner.embed_vision.load_state_dict(state)
        print(f"[Gemma4] 커넥터 적재: {args.connector_path}")

    # 먼저 전부 동결한 뒤 단계별로 되살린다. 되살릴 것을 빠뜨리면 학습 대상이
    # 0 이 되어 곧바로 드러나지만, 동결을 빠뜨리면 조용히 전체가 학습된다.
    model.requires_grad_(False)

    if args.train_type == "connector":
        inner.embed_vision.requires_grad_(True)

    elif args.train_type in ("lora", "text_lora"):
        from peft import LoraConfig, get_peft_model, PeftModel
        if args.resume_lora_path:
            print(f"[Gemma4] LoRA 이어받기: {args.resume_lora_path}")
            model.model.language_model = PeftModel.from_pretrained(
                model.model.language_model, args.resume_lora_path, is_trainable=True)
        else:
            print("[Gemma4] LoRA 새로 적용")
            # task_type 을 주지 않는다. LoRA 를 붙이는 대상이 최상위
            # Gemma4ForConditionalGeneration 이 아니라 그 안의 Gemma4TextModel
            # 이기 때문이다. task_type="CAUSAL_LM" 이면 PEFT 가
            # PeftModelForCausalLM 으로 감싸면서 base_model 의
            # prepare_inputs_for_generation 을 찾는데, Gemma4TextModel 에는
            # 그 메서드가 없어 AttributeError 로 죽는다. 생성은 상위
            # Gemma4ForConditionalGeneration 이 담당하므로 여기서는 필요 없다.
            model.model.language_model = get_peft_model(
                model.model.language_model,
                LoraConfig(r=args.lora_r, lora_alpha=args.lora_alpha,
                           lora_dropout=args.lora_dropout,
                           target_modules=LORA_TARGETS,
                           bias="none"))
        if args.train_type == "lora":
            inner.embed_vision.requires_grad_(True)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"[Gemma4] 학습 대상 {trainable:,} / 전체 {total:,} "
          f"({100 * trainable / total:.3f}%)")
    if trainable == 0:
        raise SystemExit("[Gemma4] 학습 대상이 없습니다. --train_type 을 확인하십시오.")
    return model, config


class Gemma4Trainer(Trainer):
    """
    커넥터는 PEFT 가 저장하지 않으므로 체크포인트마다 따로 남긴다.

    train_type 이 lora 나 text_lora 이면 language_model 이 PeftModel 이라
    save_pretrained 가 어댑터를 쓴다. connector 단계에는 어댑터가 없다.
    """

    def __init__(self, *args, train_type="lora", processor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.train_type = train_type
        self.processor = processor

    def prediction_step(self, model, inputs, prediction_loss_only, ignore_keys=None):
        # 어휘 262,144 의 로짓을 모을 이유가 없다. 검증에는 손실만 쓴다.
        inputs = self._prepare_inputs(inputs)
        with torch.no_grad(), self.compute_loss_context_manager():
            loss = self.compute_loss(model, inputs)
        return (loss.detach().mean(), None, None)

    def _save_checkpoint(self, model, trial):
        super()._save_checkpoint(model, trial)
        if not self.is_world_process_zero():
            return
        from transformers.trainer_utils import PREFIX_CHECKPOINT_DIR
        out = os.path.join(self._get_output_dir(trial=trial),
                           f"{PREFIX_CHECKPOINT_DIR}-{self.state.global_step}")
        self._save_parts(out)

    def _save_parts(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        inner = self.model.model
        saved = []
        if self.train_type != "text_lora":
            torch.save(inner.embed_vision.state_dict(),
                       os.path.join(out_dir, "connector.bin"))
            saved.append("connector.bin")
        lm = inner.language_model
        if hasattr(lm, "save_pretrained") and self.train_type in ("lora", "text_lora"):
            lm.save_pretrained(out_dir)
            saved.append("LoRA adapter")
        if self.processor is not None:
            self.processor.save_pretrained(out_dir)
            saved.append("processor")
        print(f"[Gemma4] 저장: {', '.join(saved)} → {out_dir}")


def main():
    args = parse_args()
    dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16,
             "float32": torch.float32}[args.dtype]
    if args.learning_rate is None:
        args.learning_rate = {"connector": 1e-3, "lora": 2e-4,
                              "text_lora": 5e-5}[args.train_type]

    processor = AutoProcessor.from_pretrained(args.model_path)
    model, config = build_model(args, dtype)

    if args.train_type == "text_lora":
        train_ds = Gemma4TextDataset(args.data_path, processor, args.max_seq_len)
        eval_ds = (Gemma4TextDataset(args.valid_data_path, processor, args.max_seq_len)
                   if args.valid_data_path else None)
    else:
        train_ds = Gemma4SDSDataset(args.data_path, args.image_dir,
                                    processor, args.max_seq_len)
        eval_ds = (Gemma4SDSDataset(args.valid_data_path,
                                    args.valid_image_dir or args.image_dir,
                                    processor, args.max_seq_len)
                   if args.valid_data_path else None)

    pad_id = processor.tokenizer.pad_token_id
    if pad_id is None:
        pad_id = processor.tokenizer.eos_token_id
    collator = Gemma4Collator(pad_token_id=pad_id)

    report_to = ["tensorboard"]
    if args.wandb_project:
        os.environ.setdefault("WANDB_PROJECT", args.wandb_project)
        report_to.append("wandb")

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.eval_batch_size or args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.num_epochs,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        lr_scheduler_type=args.lr_scheduler,
        warmup_ratio=args.warmup_ratio,
        bf16=(dtype == torch.bfloat16),
        fp16=(dtype == torch.float16),
        eval_strategy=("steps" if eval_ds is not None else "no"),
        eval_steps=(args.eval_steps or args.save_steps) if eval_ds is not None else None,
        prediction_loss_only=True,
        save_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        logging_steps=args.logging_steps,
        report_to=report_to,
        run_name=args.wandb_run_name,
        dataloader_num_workers=args.dataloader_workers,
        remove_unused_columns=False,
        gradient_checkpointing=args.gradient_checkpointing,
        deepspeed=args.deepspeed,
    )

    trainer = Gemma4Trainer(
        model=model, args=training_args,
        train_dataset=train_ds, eval_dataset=eval_ds,
        data_collator=collator,
        train_type=args.train_type, processor=processor,
    )

    trainer.train()

    if eval_ds is not None:
        metrics = trainer.evaluate()
        trainer.log_metrics("eval", metrics)
        trainer.save_metrics("eval", metrics)

    if trainer.is_world_process_zero():
        trainer._save_parts(args.output_dir)
        with open(os.path.join(args.output_dir, "gemma4_train_config.json"), "w") as f:
            json.dump({"model_path": args.model_path,
                       "train_type": args.train_type,
                       "audio_excluded": True,
                       "lora_targets": LORA_TARGETS if args.train_type != "connector" else None,
                       "lora_r": args.lora_r, "lora_alpha": args.lora_alpha,
                       "max_seq_len": args.max_seq_len}, f, indent=2)
        print(f"\n[Gemma4] 완료 → {args.output_dir}")


if __name__ == "__main__":
    main()
