"""
train.py — VisionLanguageModelV2 Training Script

Two training phases:
  Phase 1 (--train_type projector):
    - Freeze CLIP + LLM, train only the projector
    - LR ~ 1e-3, 1 epoch on 595K CC3M images
    - Saves: checkpoints/<run>/projector.bin

  Phase 2 (--train_type lora):
    - Freeze CLIP, add LoRA to LLM, train projector + LoRA
    - LR ~ 2e-4, fine-tune on domain data
    - Loads projector from Phase 1 (--projector_path)
    - Saves: checkpoints/<run>/ (LoRA adapter + projector)

Usage (single GPU):
  /home/ywlee/miniconda3/envs/eva/bin/python train.py \\
      --train_type projector \\
      --data_path /home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/chat.json \\
      --image_dir /home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/images \\
      --output_dir checkpoints/clip_llama_projector \\
      --wandb_project vlm-v2

Usage (multi-GPU with DeepSpeed):
  See scripts/train_projector.sh
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import json
import torch
import torch.distributed as dist
from torch.utils.data import DataLoader
from transformers import (
    TrainingArguments, Trainer, AutoTokenizer, TrainerCallback
)
from transformers.trainer_utils import PREFIX_CHECKPOINT_DIR, get_last_checkpoint
from peft import LoraConfig, get_peft_model

from model import (
    VLMConfig, build_model, VisionLanguageModelV2, PROJECTOR_TYPES,
    PROJECTOR_CONFIG_KEYS, load_projector_config,
)
from data import LLaVADataset, DataCollatorForVLM


# ── Argument parsing ──────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser("VisionLanguageModelV2 Trainer")

    # Model
    p.add_argument("--vision_model", default="openai/clip-vit-large-patch14-336")
    p.add_argument("--llm_model",    default="/home/ywlee/Llama-3.1-8B-Instruct")
    p.add_argument("--projector_type", default="mlp2x_gelu",
                   choices=list(PROJECTOR_TYPES))

    # Projector (resampler options)
    # These apply only to --projector_type cross_attn / qformer.
    # The linear and mlp*_gelu projectors ignore them.
    p.add_argument("--projector_num_query_tokens", type=int, default=32,
                   help="Image tokens emitted by the resampler, regardless of "
                        "the vision patch count (cross_attn / qformer only)")
    p.add_argument("--projector_num_heads", type=int, default=8,
                   help="Attention heads per resampler block "
                        "(cross_attn / qformer only)")
    p.add_argument("--projector_num_layers", type=int, default=2,
                   help="Number of stacked resampler blocks "
                        "(cross_attn / qformer only)")
    p.add_argument("--projector_ffn_ratio", type=float, default=4.0,
                   help="Resampler feed-forward width as a multiple of its "
                        "hidden size (cross_attn / qformer only)")
    p.add_argument("--projector_dropout", type=float, default=0.0,
                   help="Dropout inside the resampler blocks "
                        "(cross_attn / qformer only)")
    p.add_argument("--projector_hidden_size", type=int, default=None,
                   help="Resampler working width. Omit to use the vision "
                        "encoder hidden size (cross_attn / qformer only)")

    # Training phase
    p.add_argument("--train_type", default="projector",
                   choices=["projector", "lora", "full"],
                   help="projector=freeze LLM; lora=LoRA on LLM; full=all params")

    # Phase 2: load pretrained projector
    p.add_argument("--projector_path", default=None,
                   help="Path to projector.bin from Phase 1 (required for lora/full)")

    # Data
    p.add_argument("--data_path",  required=True,  help="chat.json path")
    p.add_argument("--image_dir",  required=True,  help="Image folder")
    p.add_argument("--max_seq_len", type=int, default=2048)

    # Training
    p.add_argument("--output_dir", default="checkpoints/run")
    p.add_argument("--num_epochs", type=float, default=1.0)
    p.add_argument("--batch_size", type=int, default=4,
                   help="Per-device batch size")
    p.add_argument("--grad_accum", type=int, default=4)
    p.add_argument("--learning_rate", type=float, default=None,
                   help="Override LR (defaults: projector=1e-3, lora=2e-4)")
    p.add_argument("--warmup_ratio", type=float, default=0.03)
    p.add_argument("--lr_scheduler", default="cosine",
                   choices=["cosine", "linear", "constant"])
    p.add_argument("--save_steps",    type=int, default=500)
    p.add_argument("--save_total_limit", type=int, default=None,
                   help="보관할 checkpoint-N 개수. 초과하면 오래된 것부터 지운다. "
                        "DeepSpeed 실행은 체크포인트마다 DeepSpeed 자신의 모듈 "
                        "사본을 남기므로(8B 기준 33 GB) 이 값으로 총량을 제한한다. "
                        "생략하면 모두 보관한다")
    p.add_argument("--logging_steps", type=int, default=10)
    p.add_argument("--max_steps", type=int, default=-1)

    # LoRA
    p.add_argument("--lora_r",       type=int,   default=128)
    p.add_argument("--lora_alpha",   type=int,   default=256)
    p.add_argument("--lora_dropout", type=float, default=0.05)
    p.add_argument("--resume_lora_path", default=None,
                   help="Load existing LoRA adapter and continue training "
                        "(skips fresh LoRA init; adapter_config.json must exist)")

    # Hardware
    p.add_argument("--dtype", default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])
    p.add_argument("--gradient_checkpointing", action="store_true", default=True)
    p.add_argument("--dataloader_workers", type=int, default=4)

    # DeepSpeed
    p.add_argument("--deepspeed", default=None,
                   help="Path to DeepSpeed config JSON")

    # W&B
    p.add_argument("--wandb_project",  default=None,
                   help="wandb project name (omit to disable wandb)")
    p.add_argument("--wandb_run_name", default=None,
                   help="wandb run name (auto-generated if omitted)")
    p.add_argument("--wandb_watch",    default="gradients",
                   choices=["none", "gradients", "all", "parameters"],
                   help="wandb.watch mode for gradient/weight histograms")
    p.add_argument("--wandb_watch_freq", type=int, default=100,
                   help="Log histograms every N steps")

    return p.parse_args()


# ── W&B GPU memory callback ───────────────────────────────────────────────────

class WandbGPUCallback(TrainerCallback):
    """
    Logs per-step GPU memory (allocated / reserved) to wandb.
    Also logs gradient norm when available.
    """

    def __init__(self, log_freq: int = 10):
        self.log_freq = log_freq

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs is None or not _is_main_process():
            return

        import wandb
        if not wandb.run:
            return

        extra = {}

        # GPU memory for each visible device
        for i in range(torch.cuda.device_count()):
            alloc = torch.cuda.memory_allocated(i) / 1e9
            resv  = torch.cuda.memory_reserved(i)  / 1e9
            extra[f"gpu/{i}/mem_allocated_GB"] = alloc
            extra[f"gpu/{i}/mem_reserved_GB"]  = resv

        wandb.log(extra, step=state.global_step)


def _is_main_process() -> bool:
    """True on rank-0 (or non-distributed)."""
    if dist.is_available() and dist.is_initialized():
        return dist.get_rank() == 0
    return True


# ── HF-Trainer compatible wrapper ────────────────────────────────────────────

class VLMTrainer(Trainer):
    """
    Thin wrapper over HF Trainer.
    - compute_loss: delegates to model.forward() which returns VLMOutput
    - _save_checkpoint: saves only trained components
    """

    def __init__(self, *args, train_type="projector", **kwargs):
        super().__init__(*args, **kwargs)
        self.train_type = train_type

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        outputs = model(**inputs)
        loss = outputs.loss
        return (loss, outputs) if return_outputs else loss

    # ── 체크포인트에 담을 텐서 선별 ──────────────────────────────────────────
    # VisionLanguageModelV2 는 PreTrainedModel 이 아니므로 HF 의 Trainer._save 가
    # state_dict 전체를 safetensors 한 파일로 쓴다. 즉 동결된 CLIP 3억과 LLM 80억이
    # 매 체크포인트마다 16.7 GB 로 따라 들어간다. projector 만 학습하는 단계에서
    # 실제로 달라진 것은 78 MB 뿐이고, 3 step DeepSpeed 실행 하나가 142 GB 를
    # 썼다.
    #
    # 동결된 부분은 사전학습 소스에서 그대로 다시 만들어지므로 저장할 이유가 없다.
    # resize_token_embeddings 로 늘어난 <image> 행도 샘플링이 아니라 기존 임베딩의
    # 통계로 결정되므로 재현된다. 실측에서 두 번의 빌드가 1e-5 수준까지 일치했고,
    # 그 차이는 128256x4096 리덕션의 부동소수점 순서에서 오는 것으로 bf16 정밀도
    # 아래이다. 이 행은 동결되어 학습되지 않으며, prepare_inputs_labels_for_multimodal
    # 이 <image> 자리를 projector 출력으로 대체하므로 입력 임베딩 쪽은 읽히지도 않는다.
    #
    # 그래서 체크포인트에는 projector 전체와, 이번 실행이 학습하는 파라미터만 담는다.
    # train_type 으로 분기하지 않는다. requires_grad 가 곧 그 정의이며, lora 와 full
    # 이 각자 무엇을 학습하는지 여기서 다시 기술하지 않아도 된다.
    FROZEN_PREFIXES = ("vision_encoder.", "language_model.")

    # DeepSpeed 경로에는 이 필터가 닿지 않는 파일이 하나 더 남는다.
    # global_stepN/mp_rank_00_model_states.pt 는 DeepSpeed 가 직접 쓰는 모듈 전체의
    # fp32 사본이며 8.37B 기준 33.4 GB 이다. DeepSpeedEngine.save_checkpoint 에
    # exclude_frozen_parameters=True 를 넘기면 실측에서 77.8 MB 로 줄어 체크포인트
    # 디렉토리가 32 GB 에서 685 MB 가 되었다. 그러나 그렇게 저장한 체크포인트는
    # 되살릴 수 없다. transformers 는 resume 시
    #   deepspeed_load_checkpoint(..., load_module_strict=not _is_peft_model(self.model))
    # 로 호출하고, VisionLanguageModelV2 는 최상위가 PeftModel 이 아니므로 strict 가
    # 참이 된다. 실측 결과 동결된 CLIP 키에서 RuntimeError 로 거부되었다.
    # 그래서 저장을 줄이지 않는다. resume 을 깨는 절약은 절약이 아니다.
    # DeepSpeed 실행의 총 디스크는 --save_total_limit 으로 제한한다.

    def _trained_state_dict(self, state_dict: dict) -> dict:
        """
        state_dict 에서 체크포인트가 실제로 담아야 할 항목만 남긴다.

        남기는 것은 projector.* 전체(버퍼 proj.arch_signature 포함)와 requires_grad
        인 파라미터이다. 후자가 lora 어댑터와 full 파인튜닝의 LLM 가중치를 덮는다.

        선별 결과에 projector 키가 하나도 없으면 필터가 아니라 이름 규칙이 어긋난
        것이므로, 조용히 빈 체크포인트를 쓰는 대신 전체 state_dict 를 그대로
        저장하고 경고한다. 디스크를 아끼려다 가중치를 잃는 쪽이 훨씬 나쁘다.
        """
        # ZeRO-3 가 16bit 가중치를 모으지 못했을 때 HF 는 의도적으로 빈 dict 를
        # 넘겨 더미 파일을 쓰고 곧바로 지운다. 그 경로는 건드리지 않는다.
        if not state_dict:
            return state_dict

        trainable = {
            name for name, param in self.model.named_parameters() if param.requires_grad
        }
        kept = {
            key: value
            for key, value in state_dict.items()
            if key.startswith("projector.") or key in trainable
        }

        if not any(key.startswith("projector.") for key in kept):
            print(f"[Trainer] 경고: state_dict 에서 projector 키를 찾지 못했습니다 "
                  f"(전체 {len(state_dict)}개). 이름 규칙이 예상과 다르므로 "
                  f"전체 state_dict 를 저장합니다.")
            return state_dict

        return kept

    def _save(self, output_dir=None, state_dict=None):
        """
        HF 가 쓰는 model.safetensors 를 학습된 부분으로 한정한다.

        _save 를 고르는 이유는 DeepSpeed 경로와 일반 경로가 모두 여기로 모이기
        때문이다. 상위인 save_model 을 건너뛰면 DeepSpeed 의 state_dict 수집이
        집합 연산이라 rank 간 교착이 생길 수 있다. _save 는 rank 0 에서만 돌고
        파일만 쓴다.
        """
        if state_dict is None:
            state_dict = self.model.state_dict()

        total = len(state_dict)
        state_dict = self._trained_state_dict(state_dict)
        if state_dict and len(state_dict) < total:
            saved_bytes = sum(v.numel() * v.element_size() for v in state_dict.values())
            print(f"[Trainer] model.safetensors: {len(state_dict)}/{total} 텐서, "
                  f"{saved_bytes / 1e6:.1f} MB (동결 파라미터 제외)")

        super()._save(output_dir, state_dict=state_dict)

    def _issue_warnings_after_load(self, load_result) -> None:
        """
        resume 시 동결 파라미터가 체크포인트에 없는 것은 정상이다.

        _save 가 그것을 일부러 빼기 때문이며, HF 는 strict=False 로 적재하므로
        빠진 자리는 build_model 이 사전학습 소스에서 만든 값이 그대로 남는다.
        기본 구현은 그 상황에서 키 이름 수백 개를 경고로 쏟아낸다.

        다만 조용히 넘기는 조건을 좁게 잡는다. 빠진 키 중에 이번 실행이 학습하는
        파라미터나 projector 키가 하나라도 있으면 그것은 정상이 아니므로 기본
        구현에 넘겨 전체 경고를 내보낸다.
        """
        missing = list(load_result.missing_keys)
        unexpected = list(load_result.unexpected_keys)

        if missing and not unexpected:
            trainable = {
                name for name, param in self.model.named_parameters() if param.requires_grad
            }
            benign = all(
                key.startswith(self.FROZEN_PREFIXES)
                and key not in trainable
                and not key.startswith("projector.")
                for key in missing
            )
            if benign:
                print(f"[Trainer] 체크포인트에 없는 동결 파라미터 {len(missing)}개는 "
                      f"사전학습 소스에서 복원되었습니다.")
                return

        super()._issue_warnings_after_load(load_result)

    def _checkpoint_dir(self, trial) -> str:
        """
        체크포인트 하나가 실제로 저장되는 디렉토리.

        transformers 의 Trainer._save_checkpoint 와 동일한 규칙으로 만든다.
        즉 _get_output_dir(trial) 이 준 run 디렉토리 아래의
        checkpoint-<global_step> 이다.

        _get_output_dir 만 쓰면 run 디렉토리 자체가 나온다. 그렇게 하면 매
        저장이 최상위에 같은 파일 이름으로 덮어써져서, checkpoint-N 디렉토리
        하나만으로는 그 시점의 모델을 복원할 수 없고 중간 체크포인트를 골라
        쓸 수도 없다.
        """
        return os.path.join(
            self._get_output_dir(trial=trial),
            f"{PREFIX_CHECKPOINT_DIR}-{self.state.global_step}",
        )

    def _save_checkpoint(self, model, trial):
        """
        HF 가 저장하는 상태에 더해, HF 가 모르는 학습 대상 구성 요소를 같은
        checkpoint-N 디렉토리에 저장한다.

        super() 를 먼저, 모든 rank 에서 호출한다. DeepSpeed 의 체크포인트
        쓰기는 집합 연산이므로 rank 하나만 호출하면 교착된다. 그리고 super()
        가 checkpoint-N 디렉토리를 만들어 주므로 그 뒤에 rank 0 만 파일을
        더하면 된다.
        """
        super()._save_checkpoint(model, trial)

        if not _is_main_process():
            return

        checkpoint_dir = self._checkpoint_dir(trial)
        os.makedirs(checkpoint_dir, exist_ok=True)

        # Always save tokenizer
        if hasattr(model, "tokenizer"):
            model.tokenizer.save_pretrained(checkpoint_dir)

        # Projector 아키텍처 설정을 체크포인트마다 기록한다.
        # 이것이 없으면 학습 도중 체크포인트만으로는 어떤 projector 로
        # 되돌려야 하는지 알 수 없어 추론 시 재구성이 불가능하다.
        #
        # self.model 을 쓴다. 이 메서드의 `model` 인수는 감싸인 모델이며,
        # DeepSpeed 에서는 DeepSpeedEngine 이다. 그 객체의 .config 는
        # DeepSpeed 설정 dict 이고 실제 인스턴스 속성이라 __getattr__ 위임이
        # 일어나지 않으므로, vars() 가 TypeError 로 죽는다.
        # 같은 함수의 model.tokenizer / model.projector 는 __getattr__ 위임을
        # 타므로 동작하며, 그래서 이 줄만 깨진다.
        config = getattr(self.model, "config", None)
        if isinstance(config, VLMConfig):
            cfg_dict = {k: v for k, v in vars(config).items() if not k.startswith("_")}
            with open(os.path.join(checkpoint_dir, "vlm_config.json"), "w") as f:
                json.dump(cfg_dict, f, indent=2)
        else:
            print(f"[Trainer] VLMConfig 를 찾지 못해 vlm_config.json 을 건너뜁니다 "
                  f"(type={type(config).__name__})")

        # 프로젝터는 세 train_type 모두에서 학습되므로 항상 저장한다.
        torch.save(model.projector.state_dict(),
                   os.path.join(checkpoint_dir, "projector.bin"))
        saved = ["projector.bin"]

        if self.train_type == "lora":
            if hasattr(model.language_model, "save_pretrained"):
                model.language_model.save_pretrained(checkpoint_dir)
                saved.append("LoRA adapter")
        elif self.train_type == "full":
            model.language_model.save_pretrained(checkpoint_dir)
            saved.append("full LLM")

        print(f"[Trainer] Saved {', '.join(saved)} → {checkpoint_dir}")


# ── W&B initialization ────────────────────────────────────────────────────────

def init_wandb(args, config: VLMConfig):
    """Initialize wandb run (main process only)."""
    if not args.wandb_project or not _is_main_process():
        return

    import wandb

    # Auto run name: "<train_type>-<vision_short>-<llm_short>"
    if args.wandb_run_name is None:
        vision_short = args.vision_model.split("/")[-1]
        llm_short    = os.path.basename(args.llm_model)
        run_name = f"{args.train_type}-{vision_short}-{llm_short}"
    else:
        run_name = args.wandb_run_name

    wandb.init(
        project=args.wandb_project,
        name=run_name,
        config={
            # Model
            "vision_model":       config.vision_model_name,
            "llm_model":          config.llm_model_name,
            "projector_type":     config.projector_type,
            "vision_hidden_size": config.vision_hidden_size,
            "llm_hidden_size":    config.llm_hidden_size,
            "vision_num_patches": config.vision_num_patches,
            "num_image_tokens":   config.num_image_tokens,
            # Projector resampler hyperparameters (None for linear / mlp)
            "projector_num_query_tokens":
                config.projector_num_query_tokens if config.is_resampler_projector else None,
            "projector_num_heads":
                config.projector_num_heads if config.is_resampler_projector else None,
            "projector_num_layers":
                config.projector_num_layers if config.is_resampler_projector else None,
            "projector_ffn_ratio":
                config.projector_ffn_ratio if config.is_resampler_projector else None,
            "projector_dropout":
                config.projector_dropout if config.is_resampler_projector else None,
            "projector_hidden_size":
                config.projector_hidden_size if config.is_resampler_projector else None,
            # Training
            "train_type":         args.train_type,
            "batch_size":         args.batch_size,
            "grad_accum":         args.grad_accum,
            "effective_batch":    args.batch_size * args.grad_accum,
            "learning_rate":      args.learning_rate,
            "lr_scheduler":       args.lr_scheduler,
            "warmup_ratio":       args.warmup_ratio,
            "num_epochs":         args.num_epochs,
            "max_seq_len":        args.max_seq_len,
            "dtype":              args.dtype,
            # LoRA (if applicable)
            "lora_r":             args.lora_r if args.train_type == "lora" else None,
            "lora_alpha":         args.lora_alpha if args.train_type == "lora" else None,
        },
        resume="allow",
    )
    print(f"[W&B] Run: {wandb.run.get_url()}")
    return run_name


def watch_model_wandb(model, args):
    """Log model gradients / weights to wandb."""
    if not args.wandb_project or args.wandb_watch == "none" or not _is_main_process():
        return

    import wandb
    if not wandb.run:
        return

    # Only watch trainable parts to avoid logging frozen Llama weights (too large)
    wandb.watch(
        model.projector,
        log=args.wandb_watch,      # "gradients", "all", "parameters"
        log_freq=args.wandb_watch_freq,
        log_graph=False,
    )
    print(f"[W&B] Watching projector (log={args.wandb_watch}, freq={args.wandb_watch_freq})")


# ── Main ──────────────────────────────────────────────────────────────────────

def _require_resumable_projector(checkpoint_dir: str, config: VLMConfig) -> None:
    """
    Refuse to auto-resume a run whose checkpoint holds a different projector.

    train.py resumes from whatever get_last_checkpoint() finds in --output_dir,
    and HF Trainer restores this model with load_state_dict(state_dict, False).
    Since projector_type is selectable, pointing a second run with a different
    --projector_type at the same --output_dir hands the loader a state dict whose
    projector keys do not match. strict=False means the projector would be left
    randomly initialized, and the run would continue on the restored optimizer
    and scheduler state as if nothing were wrong.

    In practice transformers aborts instead, but on an unrelated error:
    _issue_warnings_after_load reaches for self.model._keys_to_ignore_on_save,
    which only a PreTrainedModel has, so the traceback names that attribute and
    says nothing about the projector. It also arrives after the 8B LLM has been
    loaded. This check runs first and says what is actually wrong.

    A checkpoint written before vlm_config.json existed cannot be compared, so
    it is reported as unverified rather than assumed to match.
    """
    recorded = load_projector_config(checkpoint_dir)
    if recorded is None:
        print(f"[Train] 경고: {checkpoint_dir} 에 vlm_config.json 이 없어 프로젝터 "
              f"구성을 대조할 수 없습니다. --projector_type "
              f"{config.projector_type} 이 이 체크포인트와 맞는지 직접 확인하십시오.")
        return

    # Only the settings that change the projector's tensors are compared. Keys
    # the checkpoint does not record are skipped: their absence is unknown, not
    # a disagreement.
    differences = [
        f"  {key:<28} checkpoint={recorded[key]!r}  requested={getattr(config, key)!r}"
        for key in PROJECTOR_CONFIG_KEYS
        if key in recorded and recorded[key] != getattr(config, key)
    ]
    if not differences:
        return

    raise SystemExit(
        f"[Train] {checkpoint_dir} 의 프로젝터 구성이 요청한 구성과 다릅니다.\n"
        + "\n".join(differences)
        + "\n\n이어서 학습하려면 위 checkpoint 값과 같은 인수를 주십시오. "
        "다른 구조로 새로 학습하려면 --output_dir 를 다른 경로로 지정하십시오.\n"
        "resume 은 프로젝터 가중치까지 복원하므로, 구조가 다르면 프로젝터가 "
        "무작위 초기화 상태로 남은 채 학습이 계속될 수 있습니다."
    )


def main():
    args = parse_args()

    DTYPE_MAP = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    dtype = DTYPE_MAP[args.dtype]

    # Default LR per phase
    if args.learning_rate is None:
        args.learning_rate = {"projector": 1e-3, "lora": 2e-4, "full": 2e-5}[args.train_type]

    # ── Build model ────────────────────────────────────────────────────────────
    config = VLMConfig(
        vision_model_name=args.vision_model,
        llm_model_name=args.llm_model,
        projector_type=args.projector_type,
        projector_num_query_tokens=args.projector_num_query_tokens,
        projector_num_heads=args.projector_num_heads,
        projector_num_layers=args.projector_num_layers,
        projector_ffn_ratio=args.projector_ffn_ratio,
        projector_dropout=args.projector_dropout,
        projector_hidden_size=args.projector_hidden_size,
        vision_feature_layer=-2,
        vision_feature_select_strategy="patch",
        freeze_vision=True,
        freeze_llm=(args.train_type == "projector"),
        max_seq_len=args.max_seq_len,
    )

    # ── Resume target ─────────────────────────────────────────────────────────
    # Resolved here rather than just before trainer.train() so that a projector
    # that disagrees with the checkpoint is caught before the 8B LLM is loaded
    # and the dataset is indexed.
    last_ckpt = get_last_checkpoint(args.output_dir) if os.path.isdir(args.output_dir) else None
    if last_ckpt:
        _require_resumable_projector(last_ckpt, config)

    model = build_model(config, torch_dtype=dtype)

    # ── Load pretrained projector (Phase 2) ───────────────────────────────────
    if args.projector_path:
        print(f"[Train] Loading projector weights from {args.projector_path}")
        state = torch.load(args.projector_path, map_location="cpu", weights_only=True)
        model.projector.load_weights(state)

    # ── Apply LoRA (Phase 2) ──────────────────────────────────────────────────
    if args.train_type == "lora":
        for p in model.language_model.parameters():
            p.requires_grad = False

        if args.resume_lora_path:
            print(f"[Train] Resuming LoRA from {args.resume_lora_path} …")
            from peft import PeftModel as _PeftModel
            model.language_model = _PeftModel.from_pretrained(
                model.language_model, args.resume_lora_path, is_trainable=True
            )
        else:
            print("[Train] Applying fresh LoRA …")
            lora_config = LoraConfig(
                r=args.lora_r,
                lora_alpha=args.lora_alpha,
                lora_dropout=args.lora_dropout,
                target_modules=[
                    "q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj",
                ],
                bias="none",
                task_type="CAUSAL_LM",
            )
            model.language_model = get_peft_model(model.language_model, lora_config)

        model.language_model.print_trainable_parameters()

    elif args.train_type == "full":
        for p in model.language_model.parameters():
            p.requires_grad = True

    # Always train the projector
    for p in model.projector.parameters():
        p.requires_grad = True

    model.print_trainable_parameters()

    # ── W&B init ───────────────────────────────────────────────────────────────
    init_wandb(args, config)
    watch_model_wandb(model, args)

    # ── Dataset ───────────────────────────────────────────────────────────────
    tokenizer       = model.tokenizer
    image_processor = model.vision_encoder.image_processor

    dataset = LLaVADataset(
        data_path=args.data_path,
        image_dir=args.image_dir,
        tokenizer=tokenizer,
        image_processor=image_processor,
        max_seq_len=args.max_seq_len,
    )

    collator = DataCollatorForVLM(pad_token_id=tokenizer.pad_token_id)

    # ── Training arguments ─────────────────────────────────────────────────────
    # TensorBoard는 항상 출력 (플랫폼 대시보드 자동 연동).
    # W&B는 --wandb_project 지정 시 추가로 활성화. 두 backend 공존 가능.
    report_to: list[str] = []
    if args.wandb_project:
        report_to.append("wandb")
    if not getattr(args, "no_tensorboard", False):
        report_to.append("tensorboard")
    if not report_to:
        report_to = "none"

    training_args = TrainingArguments(
        output_dir=args.output_dir,

        # Batch / accumulation
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,

        # Epochs / steps
        num_train_epochs=args.num_epochs,

        # Learning rate
        learning_rate=args.learning_rate,
        lr_scheduler_type=args.lr_scheduler,
        warmup_ratio=args.warmup_ratio,

        # Precision
        bf16=(args.dtype == "bfloat16"),
        fp16=(args.dtype == "float16"),
        tf32=True,

        # Saving / logging
        save_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        max_steps=args.max_steps,
        logging_steps=args.logging_steps,
        report_to=report_to,

        # DataLoader
        dataloader_num_workers=args.dataloader_workers,
        dataloader_pin_memory=True,

        # Misc
        remove_unused_columns=False,
        gradient_checkpointing=args.gradient_checkpointing,

        # DeepSpeed
        deepspeed=args.deepspeed,
    )

    # ── Trainer ────────────────────────────────────────────────────────────────
    callbacks = [WandbGPUCallback(log_freq=args.logging_steps)] if args.wandb_project else []

    trainer = VLMTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
        train_type=args.train_type,
        callbacks=callbacks,
    )

    if last_ckpt:
        print(f"[Train] Resuming from checkpoint: {last_ckpt}")

    trainer.train(resume_from_checkpoint=last_ckpt)

    # ── Final save ────────────────────────────────────────────────────────────
    if _is_main_process():
        os.makedirs(args.output_dir, exist_ok=True)
        torch.save(
            model.projector.state_dict(),
            os.path.join(args.output_dir, "projector.bin"),
        )
        tokenizer.save_pretrained(args.output_dir)

        if args.train_type in ("lora", "full"):
            model.language_model.save_pretrained(args.output_dir)

        cfg_dict = {k: v for k, v in vars(config).items() if not k.startswith("_")}
        with open(os.path.join(args.output_dir, "vlm_config.json"), "w") as f:
            json.dump(cfg_dict, f, indent=2)

        print(f"\n[Train] Done. Outputs saved to {args.output_dir}")

    if args.wandb_project and _is_main_process():
        import wandb
        wandb.finish()


if __name__ == "__main__":
    main()
