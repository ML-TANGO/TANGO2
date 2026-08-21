"""
model_summary.py — VisionLanguageModelV2 구조 시각화

torchinfo 를 사용해 각 서브모듈의 파라미터 수·출력 shape·메모리를 표시하고,
wandb 에 로깅합니다.

Usage:
  # 콘솔 출력만
  /home/ywlee/miniconda3/envs/eva/bin/python model_summary.py

  # wandb 에도 기록
  /home/ywlee/miniconda3/envs/eva/bin/python model_summary.py \\
      --wandb_project vlm-v2 \\
      --wandb_run_name arch-summary

  # SigLIP 버전 확인
  /home/ywlee/miniconda3/envs/eva/bin/python model_summary.py \\
      --vision google/siglip-so400m-patch14-384

  # 쿼리 리샘플러 프로젝터 확인 (576 패치 → 32 토큰)
  /home/ywlee/miniconda3/envs/eva/bin/python model_summary.py \\
      --projector_type qformer --projector_num_query_tokens 32
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import torch
from torchinfo import summary

from model import VLMConfig, build_model, PROJECTOR_TYPES, PROJECTOR_MLP2


def parse_args():
    p = argparse.ArgumentParser("VisionLanguageModelV2 Model Summary")
    p.add_argument("--vision", default="openai/clip-vit-large-patch14-336")
    p.add_argument("--llm",    default="/home/ywlee/Llama-3.1-8B-Instruct")
    p.add_argument("--dtype",  default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--batch_size", type=int, default=1)

    # ── Projector ─────────────────────────────────────────────────────────────
    p.add_argument("--projector_type", default=PROJECTOR_MLP2,
                   choices=list(PROJECTOR_TYPES),
                   help="Vision projector architecture")
    # 아래 인수는 cross_attn / qformer 리샘플러에서만 사용된다.
    p.add_argument("--projector_num_query_tokens", type=int, default=32,
                   help="Image tokens the resampler emits (cross_attn / qformer)")
    p.add_argument("--projector_num_heads",  type=int,   default=8,
                   help="Attention heads per resampler block")
    p.add_argument("--projector_num_layers", type=int,   default=2,
                   help="Number of stacked resampler blocks")
    p.add_argument("--projector_ffn_ratio",  type=float, default=4.0,
                   help="Resampler FFN width as a multiple of the hidden size")
    p.add_argument("--projector_dropout",    type=float, default=0.0,
                   help="Dropout inside the resampler blocks")
    p.add_argument("--projector_hidden_size", type=int,  default=None,
                   help="Resampler working width (default: vision hidden_size)")

    p.add_argument("--wandb_project",  default=None)
    p.add_argument("--wandb_run_name", default=None)
    return p.parse_args()


# ── Helpers ───────────────────────────────────────────────────────────────────

def human_size(num_params: int) -> str:
    if num_params >= 1e9:
        return f"{num_params / 1e9:.2f} B"
    elif num_params >= 1e6:
        return f"{num_params / 1e6:.2f} M"
    elif num_params >= 1e3:
        return f"{num_params / 1e3:.2f} K"
    return str(num_params)


def param_table(model) -> str:
    """Build a compact parameter breakdown table."""
    rows = [
        ("Component",         "Total params",  "Trainable", "Frozen"),
        ("-" * 28,            "-" * 14,        "-" * 12,    "-" * 10),
    ]

    components = {
        "Vision Encoder": model.vision_encoder,
        "Projector":      model.projector,
        "Language Model": model.language_model,
    }
    grand_total     = 0
    grand_trainable = 0

    for name, module in components.items():
        total     = sum(p.numel() for p in module.parameters())
        trainable = sum(p.numel() for p in module.parameters() if p.requires_grad)
        frozen    = total - trainable
        rows.append((name, human_size(total), human_size(trainable), human_size(frozen)))
        grand_total     += total
        grand_trainable += trainable

    rows.append(("-" * 28, "-" * 14, "-" * 12, "-" * 10))
    rows.append(("TOTAL", human_size(grand_total),
                 human_size(grand_trainable),
                 human_size(grand_total - grand_trainable)))

    col_w = [max(len(r[i]) for r in rows) for i in range(4)]
    lines = []
    for row in rows:
        lines.append("  ".join(cell.ljust(col_w[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def run_torchinfo(model, config, batch_size: int, device, dtype):
    """
    Run torchinfo summary for each sub-module separately
    (full model summary is too large to display due to LLM depth).
    """
    B  = batch_size
    P  = config.vision_num_patches   # projector input length  (patches)
    N  = config.num_image_tokens     # projector output length (image tokens)
    D  = config.vision_hidden_size
    LD = config.llm_hidden_size
    L  = 64   # short dummy seq length for LLM summary

    divider = "─" * 70

    sections = {}

    # ── 1. Vision Encoder ─────────────────────────────────────────────────────
    print(f"\n{divider}")
    print("  [1/3] Vision Encoder")
    print(divider)
    # CLIPVisionModel expects (B, C, H, W)
    img_size = model.vision_encoder.model.config.image_size
    vis_summary = summary(
        model.vision_encoder.model,
        input_size=(B, 3, img_size, img_size),
        dtypes=[dtype],
        device=device,
        col_names=["input_size", "output_size", "num_params", "trainable"],
        depth=3,
        verbose=0,
    )
    print(vis_summary)
    sections["vision_encoder"] = str(vis_summary)

    # ── 2. Projector ──────────────────────────────────────────────────────────
    print(f"\n{divider}")
    print(f"  [2/3] Projector (Vision → Language space)  {P} patches → {N} tokens")
    print(divider)
    proj_summary = summary(
        model.projector,
        input_size=(B, P, D),
        dtypes=[dtype],
        device=device,
        col_names=["input_size", "output_size", "num_params", "trainable"],
        depth=3,
        verbose=0,
    )
    print(proj_summary)
    sections["projector"] = str(proj_summary)

    # ── 3. Language Model ─────────────────────────────────────────────────────
    # torchinfo can't trace LlamaForCausalLM with input_size (embedding index issue),
    # so we pass inputs_embeds directly via input_data.
    print(f"\n{divider}")
    print("  [3/3] Language Model (depth=2)")
    print(divider)
    dummy_embeds = torch.zeros(B, L + N, LD, dtype=dtype, device=device)
    dummy_attn   = torch.ones(B, L + N, dtype=torch.long, device=device)
    try:
        llm_summary = summary(
            model.language_model,
            input_data=[dummy_embeds],
            kwargs={"attention_mask": dummy_attn},
            col_names=["input_size", "output_size", "num_params", "trainable"],
            depth=2,
            verbose=0,
        )
        print(llm_summary)
        sections["language_model"] = str(llm_summary)
    except Exception as e:
        # Fallback: manual parameter breakdown per layer type
        llm_text = _llm_manual_summary(model.language_model)
        print(llm_text)
        sections["language_model"] = llm_text

    return sections


def _llm_manual_summary(llm) -> str:
    """Parameter count per sub-module type when torchinfo cannot trace the LLM."""
    from collections import defaultdict
    type_counts = defaultdict(lambda: [0, 0])  # {type_name: [total, trainable]}

    for name, module in llm.named_modules():
        if len(list(module.children())) == 0:  # leaf only
            mtype = type(module).__name__
            for p in module.parameters(recurse=False):
                type_counts[mtype][0] += p.numel()
                if p.requires_grad:
                    type_counts[mtype][1] += p.numel()

    total_all = sum(p.numel() for p in llm.parameters())
    train_all = sum(p.numel() for p in llm.parameters() if p.requires_grad)

    lines = [
        f"  {'Layer type':<30} {'Total':>14}  {'Trainable':>12}",
        "  " + "-" * 60,
    ]
    for mtype, (total, trainable) in sorted(type_counts.items(), key=lambda x: -x[1][0]):
        lines.append(f"  {mtype:<30} {human_size(total):>14}  {human_size(trainable):>12}")
    lines.append("  " + "-" * 60)
    lines.append(f"  {'TOTAL':<30} {human_size(total_all):>14}  {human_size(train_all):>12}")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    DTYPE_MAP = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    dtype  = DTYPE_MAP[args.dtype]
    device = torch.device(args.device)

    print("=" * 70)
    print("  VisionLanguageModelV2 — Model Structure Summary")
    print("=" * 70)

    # ── Build model ────────────────────────────────────────────────────────────
    config = VLMConfig(
        vision_model_name=args.vision,
        llm_model_name=args.llm,
        projector_type=args.projector_type,
        projector_num_query_tokens=args.projector_num_query_tokens,
        projector_num_heads=args.projector_num_heads,
        projector_num_layers=args.projector_num_layers,
        projector_ffn_ratio=args.projector_ffn_ratio,
        projector_dropout=args.projector_dropout,
        projector_hidden_size=args.projector_hidden_size,
        freeze_vision=True,
        freeze_llm=True,
    )
    model = build_model(config, torch_dtype=dtype)
    model = model.to(device)
    model.eval()

    # ── Parameter table ────────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("  Parameter Breakdown")
    print("─" * 70)
    table = param_table(model)
    print(table)

    # ── Data flow diagram ─────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("  Data Flow")
    print("─" * 70)
    img_size = model.vision_encoder.model.config.image_size
    P = config.vision_num_patches    # patches out of the vision encoder
    N = config.num_image_tokens      # image tokens out of the projector
    L = "<seq_len>"
    # 리샘플러 계열은 패치 수와 무관하게 쿼리 토큰 수만큼만 내보낸다.
    proj_note = (
        f"  {P} patches → {N} query tokens"
        if config.is_resampler_projector
        else f"  {P} patches → {N} tokens (1 per patch)"
    )
    flow = f"""
  pixel_values  ({args.batch_size}, 3, {img_size}, {img_size})
      │
      ▼  VisionEncoder  [{config.vision_model_name}]
  image_features ({args.batch_size}, {P}, {config.vision_hidden_size})
      │
      ▼  Projector  [{config.projector_type}]{proj_note}
  proj_features  ({args.batch_size}, {N}, {config.llm_hidden_size})
      │
      │  inserted at <image> token position
      │
  input_ids  ({args.batch_size}, {L})  →  embed_tokens  →  ({args.batch_size}, {L}, {config.llm_hidden_size})
      │                                                         ▲
      └─────────────────── concat ──────────────────────────────┘
                           ({args.batch_size}, {L}+{N}-1, {config.llm_hidden_size})
      │
      ▼  LLM  [{os.path.basename(args.llm)}]
  logits  ({args.batch_size}, {L}+{N}-1, vocab_size={len(model.tokenizer)})
"""
    print(flow)

    # ── torchinfo summaries ────────────────────────────────────────────────────
    with torch.no_grad():
        sections = run_torchinfo(model, config, args.batch_size, device, dtype)

    # ── W&B logging ───────────────────────────────────────────────────────────
    if args.wandb_project:
        import wandb

        run_name = args.wandb_run_name or (
            f"arch-{args.vision.split('/')[-1]}-{os.path.basename(args.llm)}"
            f"-{config.projector_type}"
        )
        wandb.init(
            project=args.wandb_project,
            name=run_name,
            job_type="architecture",
        )

        # Log parameter counts as summary metrics
        for comp_name, module in [
            ("vision_encoder", model.vision_encoder),
            ("projector",      model.projector),
            ("language_model", model.language_model),
        ]:
            total     = sum(p.numel() for p in module.parameters())
            trainable = sum(p.numel() for p in module.parameters() if p.requires_grad)
            wandb.run.summary[f"params/{comp_name}/total"]     = total
            wandb.run.summary[f"params/{comp_name}/trainable"] = trainable

        grand_total     = sum(p.numel() for p in model.parameters())
        grand_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        wandb.run.summary["params/total"]              = grand_total
        wandb.run.summary["params/trainable"]          = grand_trainable
        wandb.run.summary["params/trainable_pct"]      = 100 * grand_trainable / grand_total
        wandb.run.summary["vision_num_patches"]        = config.vision_num_patches
        wandb.run.summary["num_image_tokens"]          = config.num_image_tokens
        wandb.run.summary["vision_hidden_size"]        = config.vision_hidden_size
        wandb.run.summary["llm_hidden_size"]           = config.llm_hidden_size
        wandb.run.summary["projector_type"]            = config.projector_type
        if config.is_resampler_projector:
            wandb.run.summary["projector/num_query_tokens"] = config.projector_num_query_tokens
            wandb.run.summary["projector/num_heads"]        = config.projector_num_heads
            wandb.run.summary["projector/num_layers"]       = config.projector_num_layers
            wandb.run.summary["projector/ffn_ratio"]        = config.projector_ffn_ratio
            wandb.run.summary["projector/dropout"]          = config.projector_dropout
            wandb.run.summary["projector/hidden_size"]      = (
                config.projector_hidden_size or config.vision_hidden_size
            )

        # Log torchinfo text as wandb artifacts
        artifact = wandb.Artifact("model-architecture", type="model-info")
        with artifact.new_file("param_table.txt", mode="w") as f:
            f.write(table)
        for name, text in sections.items():
            with artifact.new_file(f"{name}_summary.txt", mode="w") as f:
                f.write(text)
        wandb.log_artifact(artifact)

        # Log config as a wandb Table for easy inspection
        cfg_rows = [
            ["vision_model",       config.vision_model_name],
            ["llm_model",          config.llm_model_name],
            ["projector_type",     config.projector_type],
            ["vision_hidden_size", str(config.vision_hidden_size)],
            ["llm_hidden_size",    str(config.llm_hidden_size)],
            ["vision_num_patches", str(config.vision_num_patches)],
            ["num_image_tokens",   str(config.num_image_tokens)],
        ]
        if config.is_resampler_projector:
            cfg_rows += [
                ["projector_num_query_tokens", str(config.projector_num_query_tokens)],
                ["projector_num_heads",        str(config.projector_num_heads)],
                ["projector_num_layers",       str(config.projector_num_layers)],
                ["projector_ffn_ratio",        str(config.projector_ffn_ratio)],
                ["projector_dropout",          str(config.projector_dropout)],
                ["projector_hidden_size",
                 str(config.projector_hidden_size or config.vision_hidden_size)],
            ]
        cfg_rows += [
            ["total_params",     human_size(grand_total)],
            ["trainable_params", human_size(grand_trainable)],
            ["trainable_%",      f"{100*grand_trainable/grand_total:.2f}%"],
        ]
        cfg_table = wandb.Table(columns=["Key", "Value"], data=cfg_rows)
        wandb.log({"model_config": cfg_table})

        print(f"\n[W&B] Architecture logged → {wandb.run.get_url()}")
        wandb.finish()

    print("\n" + "=" * 70)
    print("  Summary complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()
