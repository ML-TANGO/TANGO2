"""
CT-JEPA v2 Utilities
=====================
Collapse monitoring, learning rate scheduling, logging (JSONL + WandB),
checkpointing, and training helpers.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
import os
import json
import time
from typing import Dict, Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# Collapse Monitoring
# ---------------------------------------------------------------------------

class CollapseMonitor:
    """
    Monitors representation collapse via std, effective rank, prediction quality,
    and conditioning activity. Returns structured metrics for logging.
    """

    def __init__(self, std_threshold: float = 1e-5, rank_ratio_threshold: float = 0.05,
                 warn_threshold: float = 1e-4, halt_threshold: float = 1e-5):
        self.std_threshold = std_threshold
        self.rank_ratio_threshold = rank_ratio_threshold
        self.warn_threshold = warn_threshold
        self.halt_threshold = halt_threshold
        self.history = []

    @torch.no_grad()
    def check(self, embeddings: torch.Tensor, name: str = "s3") -> Dict[str, float]:
        """Core collapse check on embedding tensor."""
        if embeddings.ndim == 3:
            B, N, D = embeddings.shape
            flat = embeddings.reshape(-1, D)
        else:
            flat = embeddings
            D = flat.shape[-1]

        std_per_dim = flat.std(dim=0)
        mean_std = std_per_dim.mean().item()
        min_std = std_per_dim.min().item()

        # Subsample for SVD
        if flat.shape[0] > 2048:
            indices = torch.randperm(flat.shape[0])[:2048]
            flat_sub = flat[indices]
        else:
            flat_sub = flat

        flat_sub = flat_sub - flat_sub.mean(dim=0, keepdim=True)

        try:
            S = torch.linalg.svdvals(flat_sub)
            S_norm = S / S.sum()
            S_norm = S_norm[S_norm > 1e-10]
            entropy = -(S_norm * S_norm.log()).sum().item()
            effective_rank = math.exp(entropy)
        except Exception:
            effective_rank = D

        rank_ratio = effective_rank / D
        is_collapsed = (min_std < self.std_threshold) or (rank_ratio < self.rank_ratio_threshold)

        # Severity levels
        severity = "ok"
        if min_std < self.halt_threshold:
            severity = "HALT"
        elif min_std < self.warn_threshold:
            severity = "WARNING"

        metrics = {
            f'health/{name}_embed_std_mean': mean_std,
            f'health/{name}_embed_std_min': min_std,
            f'health/{name}_effective_rank': effective_rank,
            f'health/{name}_rank_ratio': rank_ratio,
            f'health/{name}_is_collapsed': is_collapsed,
            f'health/{name}_severity': severity,
        }

        self.history.append(metrics)
        return metrics

    @torch.no_grad()
    def check_predictions(self, pred: torch.Tensor, target: torch.Tensor,
                          valid_mask: Optional[torch.Tensor] = None) -> Dict[str, float]:
        """Check prediction quality: std and cosine similarity to targets."""
        if valid_mask is not None:
            # Flatten valid predictions
            pred_flat = pred[valid_mask.bool()] if valid_mask.ndim == 2 else pred
            target_flat = target[valid_mask.bool()] if valid_mask.ndim == 2 else target
        else:
            pred_flat = pred.reshape(-1, pred.shape[-1])
            target_flat = target.reshape(-1, target.shape[-1])

        pred_std = pred_flat.std().item()

        # Cosine similarity
        pred_norm = F.normalize(pred_flat, dim=-1)
        tgt_norm = F.normalize(target_flat, dim=-1)
        cosine_sim = (pred_norm * tgt_norm).sum(dim=-1).mean().item()

        return {
            'health/pred_std': pred_std,
            'health/pred_target_cosine': cosine_sim,
        }

    @torch.no_grad()
    def check_conditioning(self, model: nn.Module, window_ids: torch.Tensor) -> Dict[str, float]:
        """
        Check if AdaLN conditioning differentiates between windows.
        Measures variance of gamma parameters across different window IDs.
        """
        unique_windows = window_ids.unique()
        if len(unique_windows) < 2:
            return {'health/adaln_gamma_var_across_windows': -1.0}

        cond_vectors = []
        for wid in unique_windows:
            cond = model.context_encoder.window_cond(window_id=wid.unsqueeze(0))
            cond_vectors.append(cond.squeeze(0))

        cond_stack = torch.stack(cond_vectors)  # (num_windows, D)
        gamma_var = cond_stack.var(dim=0).mean().item()

        return {
            'health/adaln_gamma_var_across_windows': gamma_var,
        }


# ---------------------------------------------------------------------------
# Learning Rate Scheduling
# ---------------------------------------------------------------------------

class CosineWarmupScheduler:
    """Cosine annealing with linear warmup."""

    def __init__(self, optimizer, base_lr: float, min_lr: float,
                 warmup_epochs: int, total_epochs: int,
                 steps_per_epoch: int):
        self.optimizer = optimizer
        self.base_lr = base_lr
        self.min_lr = min_lr
        self.warmup_steps = warmup_epochs * steps_per_epoch
        self.total_steps = total_epochs * steps_per_epoch
        self.step_count = 0

    def get_lr(self) -> float:
        if self.step_count < self.warmup_steps:
            return self.base_lr * (self.step_count + 1) / max(self.warmup_steps, 1)
        else:
            progress = (self.step_count - self.warmup_steps) / max(
                self.total_steps - self.warmup_steps, 1)
            progress = min(progress, 1.0)
            return self.min_lr + 0.5 * (self.base_lr - self.min_lr) * (
                1 + math.cos(math.pi * progress))

    def step(self):
        lr = self.get_lr()
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
        self.step_count += 1
        return lr


# ---------------------------------------------------------------------------
# Logging — JSONL + optional WandB
# ---------------------------------------------------------------------------

class TrainLogger:
    """
    Dual logger: always writes JSONL locally, optionally logs to WandB.
    Handles both scalar metrics and media (images, histograms).
    """

    def __init__(self, log_dir: str, experiment_name: str = "ctjepa_v2",
                 use_wandb: bool = False, wandb_project: str = "ctjepa-v2",
                 wandb_run_name: str = None, wandb_config: dict = None):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(
            log_dir, f"{experiment_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        )
        self.start_time = time.time()
        self.wandb_run = None

        # Initialize WandB
        if use_wandb:
            try:
                import wandb
                self.wandb_run = wandb.init(
                    project=wandb_project,
                    name=wandb_run_name or experiment_name,
                    config=wandb_config or {},
                    resume="allow",
                )
                print(f"  WandB initialized: {wandb.run.url}")
            except Exception as e:
                print(f"  WandB init failed ({e}), continuing with JSONL only")
                self.wandb_run = None

    def log(self, metrics: Dict, step: int, epoch: int):
        """Log scalar metrics to JSONL and WandB."""
        # Filter to serializable values
        entry = {
            'step': step,
            'epoch': epoch,
            'elapsed_seconds': time.time() - self.start_time,
        }
        wandb_metrics = {'epoch': epoch}

        for k, v in metrics.items():
            if isinstance(v, torch.Tensor):
                val = v.item()
            elif isinstance(v, (float, int, bool)):
                val = v
            elif isinstance(v, str):
                val = v
            else:
                continue

            entry[k] = val
            wandb_metrics[k] = val

        # JSONL
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        # WandB
        if self.wandb_run is not None:
            try:
                import wandb
                # Filter out non-numeric for wandb
                wb_clean = {k: v for k, v in wandb_metrics.items()
                            if isinstance(v, (int, float, bool))}
                wandb.log(wb_clean, step=step)
            except Exception:
                pass

    def log_image(self, key: str, image, step: int, caption: str = ""):
        """Log an image to WandB (PIL Image or numpy array)."""
        if self.wandb_run is not None:
            try:
                import wandb
                wandb.log({key: wandb.Image(image, caption=caption)}, step=step)
            except Exception:
                pass

    def log_histogram(self, key: str, values: torch.Tensor, step: int):
        """Log a histogram to WandB."""
        if self.wandb_run is not None:
            try:
                import wandb
                wandb.log({key: wandb.Histogram(values.cpu().numpy())}, step=step)
            except Exception:
                pass

    def log_table(self, key: str, columns: list, data: list, step: int):
        """Log a table to WandB."""
        if self.wandb_run is not None:
            try:
                import wandb
                table = wandb.Table(columns=columns, data=data)
                wandb.log({key: table}, step=step)
            except Exception:
                pass

    def print_metrics(self, metrics: Dict, step: int, epoch: int, prefix: str = ""):
        """Print formatted metrics to console."""
        parts = [f"{prefix}[E{epoch} | S{step}]"]
        for k, v in metrics.items():
            short_k = k.split('/')[-1] if '/' in k else k
            if isinstance(v, float):
                if abs(v) < 0.001 and v != 0:
                    parts.append(f"{short_k}: {v:.2e}")
                else:
                    parts.append(f"{short_k}: {v:.5f}")
            elif isinstance(v, bool):
                if v:
                    parts.append(f"{short_k}: YES")
            elif isinstance(v, str) and v not in ('ok',):
                parts.append(f"{short_k}: {v}")
            elif isinstance(v, (int,)):
                parts.append(f"{short_k}: {v}")
        print(" | ".join(parts[:12]))  # Cap console width

    def finish(self):
        """Close WandB run."""
        if self.wandb_run is not None:
            try:
                import wandb
                wandb.finish()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------

class CheckpointManager:
    """Save and load training checkpoints with rotation."""

    def __init__(self, save_dir: str, max_keep: int = 5):
        self.save_dir = save_dir
        self.max_keep = max_keep
        os.makedirs(save_dir, exist_ok=True)
        self.saved = []

    def save(self, model: nn.Module, optimizer, scheduler,
             epoch: int, step: int, loss: float,
             ema_momentum: float = 0.0, extra: dict = None):
        path = os.path.join(self.save_dir, f"checkpoint_epoch{epoch:04d}_step{step}.pt")

        state = {
            'epoch': epoch,
            'step': step,
            'loss': loss,
            'ema_momentum': ema_momentum,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'scheduler_step_count': scheduler.step_count,
        }
        if extra:
            state.update(extra)

        torch.save(state, path)
        self.saved.append(path)

        while len(self.saved) > self.max_keep:
            old = self.saved.pop(0)
            if os.path.exists(old):
                os.remove(old)

        latest = os.path.join(self.save_dir, "checkpoint_latest.pt")
        if os.path.exists(latest) or os.path.islink(latest):
            os.remove(latest)
        os.symlink(os.path.basename(path), latest)

        return path

    def save_phase(self, model: nn.Module, epoch: int, step: int, phase_name: str):
        """Save a phase-transition checkpoint (never rotated)."""
        path = os.path.join(self.save_dir, f"phase_{phase_name}_epoch{epoch:04d}.pt")
        torch.save({
            'epoch': epoch,
            'step': step,
            'phase': phase_name,
            'context_encoder': model.context_encoder.state_dict(),
            'target_encoder': model.target_encoder.state_dict(),
        }, path)
        return path

    def load(self, path: str, model: nn.Module, optimizer=None, scheduler=None):
        state = torch.load(path, map_location='cpu', weights_only=False)
        ckpt_sd = state['model_state_dict']

        # Filter out keys with shape mismatches (e.g. architecture changes)
        model_sd = model.state_dict()
        skipped = []
        for k in list(ckpt_sd.keys()):
            if k in model_sd and ckpt_sd[k].shape != model_sd[k].shape:
                skipped.append(k)
                del ckpt_sd[k]
        if skipped:
            print(f"  Checkpoint: {len(skipped)} params with shape mismatch (skipped): "
                  f"{skipped[:5]}{'...' if len(skipped) > 5 else ''}")

        missing, unexpected = model.load_state_dict(ckpt_sd, strict=False)
        if missing:
            print(f"  Checkpoint: {len(missing)} new params (randomly initialized): "
                  f"{missing[:5]}{'...' if len(missing) > 5 else ''}")
        if unexpected:
            print(f"  Checkpoint: {len(unexpected)} removed params (ignored): "
                  f"{unexpected[:5]}{'...' if len(unexpected) > 5 else ''}")
        if optimizer and 'optimizer_state_dict' in state:
            try:
                optimizer.load_state_dict(state['optimizer_state_dict'])
            except (ValueError, KeyError) as e:
                print(f"  Checkpoint: optimizer state incompatible, resetting. ({e})")
        if scheduler and 'scheduler_step_count' in state:
            scheduler.step_count = state['scheduler_step_count']
        return state


# ---------------------------------------------------------------------------
# Misc Helpers
# ---------------------------------------------------------------------------

@torch.no_grad()
def compute_grad_stats(model: nn.Module) -> Dict[str, float]:
    total_norm = 0.0
    param_count = 0
    max_norm = 0.0

    for p in model.parameters():
        if p.grad is not None:
            norm = p.grad.data.norm(2).item()
            total_norm += norm ** 2
            max_norm = max(max_norm, norm)
            param_count += 1

    total_norm = total_norm ** 0.5

    return {
        'grad_norm_total': total_norm,
        'grad_norm_max': max_norm,
        'num_params_with_grad': param_count,
    }


def count_parameters(model: nn.Module) -> Dict[str, float]:
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {
        'total_params': total,
        'trainable_params': trainable,
        'frozen_params': total - trainable,
        'total_params_M': total / 1e6,
        'trainable_params_M': trainable / 1e6,
    }
