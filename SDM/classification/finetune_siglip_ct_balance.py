# stage2_calibrate_and_head_ft.py
# ---------------------------------------------------------------
# 1) bias‑only calibration to force "good" threshold == 0.5
# 2) optional head‑only fine‑tuning (no backbone grads)
# ---------------------------------------------------------------
from pathlib import Path
import argparse, json, logging, math, os, sys, warnings
import torch, torch.nn as nn
import numpy as np
from torch.cuda.amp import GradScaler, autocast
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.optim.swa_utils import AveragedModel, SWALR
from sklearn.metrics import f1_score
from tqdm import tqdm
try:
    import wandb
    WANDB_OK = True
except ImportError:
    WANDB_OK = False
    warnings.warn("wandb not installed – telemetry disabled", RuntimeWarning)

# ---------- import the objects from your stage‑1 file -----------
from finetune_siglip_ct import (
    SigLIPClassifier, load_backbone, make_loaders, set_seed,
    FocalBalancedLoss, search_thresholds, evaluate
)
# ---------------------------------------------------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt",   default="outputs/best_crg.pth",
                   help="stage‑1 checkpoint with .state_dict etc.")
    p.add_argument("--csv",    default="/data/all_ct_with_labels.csv")
    p.add_argument("--labels", default="default_labels18.json")
    p.add_argument("--three-channel", action="store_true")
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--epochs", type=int, default=4,
                   help="extra head‑only epochs after bias shift; 0 = skip")
    p.add_argument("--lr-head", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--amp", action="store_true")
    p.add_argument("--output", default="outputs")

    # ---------- WandB ----------
    p.add_argument("--wandb-project", default="",
                   help="Weights‑and‑Biases project (entity/project). "
                        "Leave empty to disable.")
    p.add_argument("--wandb-name", default=None,
                   help="Run name (defaults to stage2_<ckpt‑stem>)")
    return p.parse_args(argv)

# ------------------------- helpers -----------------------------
@torch.no_grad()
def apply_bias_shift(model: nn.Module,
                     thresholds: np.ndarray):
    """Shift classifier bias so that threshold 0.5 == previous optimal."""
    logits_bias = model.head[-1].bias        # last Linear of head
    delta = torch.from_numpy(
        np.log(thresholds / (1 - thresholds))).to(logits_bias.device)
    logits_bias.data.sub_(delta)

# --------------------------- main ------------------------------
def main(argv=None):
    args = parse_args(argv)
    Path(args.output).mkdir(exist_ok=True, parents=True)

    # ---------- basic logging & reproducibility -----------------
    set_seed(42)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # ---------- labels & data loaders ---------------------------
    labels = json.loads(Path(args.labels).read_text()) \
             if isinstance(args.labels, str) else args.labels

    tr_loader, val_loader = make_loaders(
        args.csv, labels,
        bs=args.batch_size, nw=8,
        three_ch=args.three_channel,
        balance=False, rank=0, world_size=1
    )

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    # ---------- rebuild model & load weights --------------------
    ckpt = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    backbone = load_backbone("")                # structure only
    model = SigLIPClassifier(backbone, len(labels)).to(device)
    state_dict = ckpt["model"]
    # Remove 'module.' prefix if present and filter out 'n_averaged' and any unexpected keys
    allowed_keys = set(model.state_dict().keys())
    new_state_dict = {k.replace("module.", "", 1) if k.startswith("module.") else k: v
                      for k, v in state_dict.items()
                      if (k.replace("module.", "", 1) if k.startswith("module.") else k) in allowed_keys}
    model.load_state_dict(new_state_dict, strict=True)

    # ---------- optional WandB initialisation -------------------
    if WANDB_OK and args.wandb_project:
        run_name = args.wandb_name or f"stage2_{Path(args.ckpt).stem}"
        wandb.init(project=args.wandb_project,
                   name=run_name,
                   config=vars(args),
                   dir=args.output)

    # ---------- STEP 1: compute optimal thresholds --------------
    logging.info("Searching per‑class thresholds on validation set …")
    _, logits, gts = evaluate(
        model, val_loader,
        FocalBalancedLoss(torch.ones(len(labels), device=device)),
        device, labels, thresholds=0.5, show_tqdm=True
    )
    # tqdm‑wrapped threshold search (progress_cb not supported in this implementation)
    thresholds, macro_f1_opt = search_thresholds(logits, gts, step=0.005)
    logging.info(f"Mean optimal threshold = {thresholds.mean():.3f}  | "
                 f"macro‑F1@opt = {macro_f1_opt:.4f}")

    # ---------- STEP 2: bias shift ------------------------------
    logging.info("Shifting classifier bias so that thr = 0.5 matches opt …")
    apply_bias_shift(model, thresholds)

    # quick check (with tqdm inside evaluate)
    _, logits2, _ = evaluate(
        model, val_loader,
        FocalBalancedLoss(torch.ones(len(labels), device=device)),
        device, labels, thresholds=0.5, show_tqdm=True
    )
    macro_f1_after_shift = f1_score(gts, (logits2 > 0.5).astype(int),
                                    average="macro", zero_division=0)
    logging.info(f"macro‑F1@0.5 before shift: {f1_score(gts,(logits>0.5).astype(int),average='macro'):.4f}")
    logging.info(f"macro‑F1@0.5  after shift: {macro_f1_after_shift:.4f}")

    # ---------- (optional) STEP 3: head‑only fine‑tune ----------
    best_f1 = macro_f1_after_shift  # Initialize best_f1 for both paths
    
    if args.epochs > 0:
        logging.info(f"Head‑only fine‑tuning for {args.epochs} epochs …")

        # freeze backbone
        for p in model.backbone.parameters():
            p.requires_grad = False

        head_params = [p for p in model.head.parameters() if p.requires_grad]
        opt = AdamW(head_params, lr=args.lr_head, weight_decay=args.weight_decay)
        sch = CosineAnnealingLR(opt, T_max=args.epochs)
        scaler = GradScaler(enabled=args.amp)
        ema = AveragedModel(model, avg_fn=None)
        swa = AveragedModel(model)
        swa_start = int(args.epochs * 0.6)
        swa_sch = SWALR(opt, swa_lr=args.lr_head * 0.05)

        criterion = FocalBalancedLoss(torch.ones(len(labels), device=device))

        if WANDB_OK and args.wandb_project:
            wandb.watch(model.head, log="all", log_freq=50)

        for ep in range(1, args.epochs + 1):
            model.train(); running = 0.
            pbar = tqdm(enumerate(tr_loader, 1), total=len(tr_loader),
                        ncols=110, desc=f"[head‑ft {ep}/{args.epochs}]")
            opt.zero_grad()
            for i, (x, y) in pbar:
                x, y = x.to(device), y.to(device)
                with autocast(enabled=args.amp):
                    loss = criterion(model(x), y)
                scaler.scale(loss).backward()
                scaler.step(opt); scaler.update(); opt.zero_grad()
                running += loss.item()
                ema.update_parameters(model)
                if ep >= swa_start:
                    swa.update_parameters(model)
                    swa_sch.step()
                pbar.set_postfix(loss=running/i)

            sch.step()

            # ----- validation on EMA weights
            metrics, *_ = evaluate(
                ema, val_loader, criterion, device, labels,
                thresholds=0.5, show_tqdm=True)
            f1_now = metrics["macro_f1"]
            logging.info(f"  epoch {ep}: macro‑F1@0.5 = {f1_now:.4f} "
                         f"(best {best_f1:.4f})")
            if f1_now > best_f1:
                best_f1 = f1_now
                torch.save({"model": ema.state_dict(),
                            "thresholds": np.full(len(labels), 0.5, np.float32),
                            "metrics": metrics
                }, Path(args.output) / "best_stage2.pth")

            # ---------- WandB logging ----------
            if WANDB_OK and args.wandb_project:
                wandb.log({"epoch": ep,
                           "train/loss": running / len(tr_loader),
                           "val/macro_F1": f1_now,
                           "lr": sch.get_last_lr()[0],
                           **{f"val/F1_{lbl}": metrics[f"{lbl}_f1"]
                              for lbl in labels}})

    else:
        torch.save({"model": model.state_dict(),
                    "thresholds": np.full(len(labels), 0.5, np.float32),
                    "metrics": {"macro_f1": macro_f1_after_shift}
        }, Path(args.output) / "best_stage2.pth")
        logging.info("Saved calibrated checkpoint without extra fine‑tuning.")

    # WandB summary & finish
    if WANDB_OK and args.wandb_project:
        wandb.summary.update({"final_macro_F1": best_f1})
        wandb.finish()

    logging.info("Stage‑2 completed ✓")

if __name__ == "__main__":
    main()
