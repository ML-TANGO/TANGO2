"""
CT-JEPA v2 Training Script
============================
Full training loop with:
- Configurable local block type (transformer/swin/convnext)
- Mixed masking with curriculum
- EMA target encoder updates
- Multi-component loss with scheduling
- Comprehensive logging (JSONL + WandB)
- Collapse monitoring with auto-halt
- Validation: linear probe, retrieval, feature quality, t-SNE
- Phase transition evaluation
- Gradient accumulation + mixed precision
- Checkpointing
- Multi-GPU training via DDP (torchrun)

Usage:
    # Single GPU
    python -m cepa.train --data_csv cepa/final_ct2.csv --data_root /data/preprocessed

    # Multi-GPU (DDP, 5 GPUs)
    torchrun --nproc_per_node=5 -m cepa.train --data_csv cepa/final_ct2.csv --data_root /data/preprocessed
"""

import os
import sys
import argparse
import time
from datetime import timedelta
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data.distributed import DistributedSampler
import numpy as np
from torch.cuda.amp import GradScaler, autocast
from contextlib import nullcontext
from tqdm import tqdm

from .config import CTJEPAConfig
from .model import CTJEPA
from .losses import CTJEPALoss
from .masking import MaskSampler, sample_masked_s2_indices
from .data import create_dataloader, CTJEPADataset, MultiLabelProbeDataset
from .utils import (
    CollapseMonitor, CosineWarmupScheduler, TrainLogger,
    CheckpointManager, count_parameters,
)
from .validation import run_validation, run_phase_evaluation


def is_distributed():
    """Check if running in distributed mode (launched via torchrun)."""
    return dist.is_available() and dist.is_initialized()


def get_rank():
    return dist.get_rank() if is_distributed() else 0


def get_world_size():
    return dist.get_world_size() if is_distributed() else 1


def is_main_process():
    return get_rank() == 0


def setup_distributed():
    """Initialize distributed process group if launched via torchrun."""
    if 'RANK' not in os.environ:
        return  # Not a torchrun launch, single-GPU mode

    dist.init_process_group(backend='nccl', timeout=timedelta(hours=1))
    local_rank = int(os.environ['LOCAL_RANK'])
    torch.cuda.set_device(local_rank)


def cleanup_distributed():
    """Clean up distributed process group."""
    if is_distributed():
        dist.destroy_process_group()


def parse_args():
    parser = argparse.ArgumentParser(description="CT-JEPA v2 Training")

    # Architecture
    parser.add_argument('--config', type=str, default='base', choices=['small', 'base', 'large'])
    parser.add_argument('--local_block_type', type=str, default='transformer',
                        choices=['transformer', 'swin', 'convnext'])

    # Data
    parser.add_argument('--data_csv', type=str, default='cepa/final_ct2.csv')
    parser.add_argument('--data_root', type=str, default='/data/preprocessed')
    parser.add_argument('--img_col', type=str, default='object_id')
    parser.add_argument('--text_col', type=str, default='findings')
    parser.add_argument('--split_col', type=str, default='split')

    # Training
    parser.add_argument('--output_dir', type=str, default='./runs/ctjepa_v2')
    parser.add_argument('--epochs', type=int, default=None)
    parser.add_argument('--batch_size', type=int, default=None)
    parser.add_argument('--grad_accum', type=int, default=None)
    parser.add_argument('--lr', type=float, default=None)
    parser.add_argument('--resume', type=str, default=None)
    parser.add_argument('--device', type=str, default='cuda')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--debug', action='store_true')

    # Logging
    parser.add_argument('--wandb_project', type=str, default='ctjepa-v2')
    parser.add_argument('--wandb_run', type=str, default=None)
    parser.add_argument('--no_wandb', action='store_true')

    # Validation
    parser.add_argument('--val_probe_csv', type=str, default=None,
                        help='Labeled CSV for linear probe evaluation')
    parser.add_argument('--val_probe_label_col', type=str, default='label')
    parser.add_argument('--validate_only', action='store_true',
                        help='Skip training, run validation only (requires --resume)')

    return parser.parse_args()


def setup_config(args) -> CTJEPAConfig:
    config = CTJEPAConfig()
    config.model.variant = args.config
    config.model.local_block_type = args.local_block_type

    # Data paths
    config.data.csv_path = args.data_csv
    config.data.data_root = args.data_root
    config.data.img_col = args.img_col
    config.data.text_col = args.text_col
    config.data.split_col = args.split_col

    if args.epochs is not None:
        config.training.total_epochs = args.epochs
    if args.batch_size is not None:
        config.training.batch_size = args.batch_size
    if args.grad_accum is not None:
        config.training.grad_accumulation_steps = args.grad_accum
    if args.lr is not None:
        config.training.base_lr = args.lr

    # Wandb
    config.validation.use_wandb = not args.no_wandb
    config.validation.wandb_project = args.wandb_project
    config.validation.wandb_run_name = args.wandb_run

    # Linear probe
    if args.val_probe_csv:
        config.validation.probe_csv = args.val_probe_csv
        config.validation.probe_label_col = args.val_probe_label_col

    if args.debug:
        config.training.total_epochs = 2
        config.training.log_interval = 1
        config.training.save_interval = 1
        config.validation.eval_interval = 1
        config.validation.visualization_interval = 1
        config.validation.linear_probe_interval = 1
        config.validation.use_wandb = False

    return config


def set_seed(seed: int, rank: int = 0):
    """Set random seeds. Offset by rank so each GPU gets different data augmentation."""
    torch.manual_seed(seed + rank)
    torch.cuda.manual_seed_all(seed + rank)
    np.random.seed(seed + rank)


@torch.no_grad()
def prepare_batch_masks(batch, mask_sampler, config, epoch, device):
    B = batch['volume'].shape[0]

    visible_masks, masked_indices, mask_results = mask_sampler.sample_batch(
        batch_size=B,
        epoch=epoch,
        total_epochs=config.training.total_epochs,
    )

    masked_s2_list = []
    for b in range(B):
        s2_idx = sample_masked_s2_indices(
            visible_masks[b],
            num_samples=config.model.detail_num_sampled,
        )
        masked_s2_list.append(s2_idx)
    masked_s2 = torch.stack(masked_s2_list)

    return {
        'visible_mask_s3': visible_masks.to(device),
        'masked_indices_s3': masked_indices.to(device),
        'masked_s2_indices': masked_s2.to(device),
        'mask_families': [r.family for r in mask_results],
        'mask_ratios': [r.mask_ratio for r in mask_results],
    }


def train_one_epoch(model, loss_fn, optimizer, scheduler, scaler, dataloader,
                    mask_sampler, config, epoch, device, logger, collapse_monitor,
                    global_step, raw_model=None):
    """
    Single epoch training with comprehensive step-level logging.
    Supports both single-GPU and DDP multi-GPU training.

    Args:
        raw_model: unwrapped model (without DDP wrapper) for EMA updates and collapse checks.
                   If None, assumes model is not wrapped.
    """
    model.train()
    tc = config.training
    vc = config.validation
    accumulation_steps = tc.grad_accumulation_steps
    batch_size = tc.batch_size
    should_halt = False
    rank0 = is_main_process()

    if raw_model is None:
        raw_model = model

    epoch_losses = {}
    epoch_start = time.time()
    mask_family_counts = {}

    pbar = tqdm(
        dataloader,
        desc=f"Epoch {epoch}",
        disable=not rank0,
        dynamic_ncols=True,
    )
    for batch_idx, batch in enumerate(pbar):
        step_start = time.time()

        volume = batch['volume'].to(device)
        window_id = batch['window_id'].to(device)
        region_masks_s2 = batch['region_masks_s2'].to(device) if batch['region_masks_s2'] is not None else None
        texts = batch.get('texts')  # List[Optional[str]]

        mask_data = prepare_batch_masks(batch, mask_sampler, config, epoch, device)

        amp_ctx = autocast(dtype=torch.bfloat16) if tc.mixed_precision else nullcontext()

        # Use no_sync for accumulation steps (skip all-reduce until optimizer step)
        is_accumulation_step = ((batch_idx + 1) % accumulation_steps != 0)
        sync_ctx = model.no_sync() if (is_distributed() and is_accumulation_step and hasattr(model, 'no_sync')) else nullcontext()

        with sync_ctx:
            with amp_ctx:
                outputs = model(
                    volume=volume,
                    window_id=window_id,
                    visible_mask_s3=mask_data['visible_mask_s3'],
                    masked_indices_s3=mask_data['masked_indices_s3'],
                    region_masks_s2=region_masks_s2,
                    texts=texts,
                    masked_s2_indices=mask_data['masked_s2_indices'],
                    epoch=epoch,
                )

                losses = loss_fn(outputs, epoch)
                loss = losses['total'] / accumulation_steps

            if tc.mixed_precision:
                scaler.scale(loss).backward()
            else:
                loss.backward()

        # Track mask families for curriculum verification
        for fam in mask_data['mask_families']:
            mask_family_counts[fam] = mask_family_counts.get(fam, 0) + 1

        if (batch_idx + 1) % accumulation_steps == 0:
            if tc.mixed_precision:
                scaler.unscale_(optimizer)

            grad_norm = torch.nn.utils.clip_grad_norm_(
                raw_model.parameters(), tc.grad_clip_norm
            )

            if tc.mixed_precision:
                scaler.step(optimizer)
                scaler.update()
            else:
                optimizer.step()

            optimizer.zero_grad()
            momentum = raw_model.update_target_encoder()
            current_lr = scheduler.step()
            global_step += 1

            step_time = time.time() - step_start

            # Update progress bar every optimizer step
            if rank0:
                pbar.set_postfix(
                    loss=f"{losses['total'].item():.4f}",
                    lr=f"{current_lr:.2e}",
                    step=global_step,
                )

            # --------------------------------------------------------
            # Step-level logging (every log_interval, rank 0 only)
            # --------------------------------------------------------
            if rank0 and global_step % tc.log_interval == 0:
                metrics = {
                    # All loss components
                    'loss/total': losses['total'].item(),
                }
                for k, v in losses.items():
                    if k != 'total' and isinstance(v, torch.Tensor):
                        metrics[f'loss/{k}'] = v.item()

                # Optimization
                metrics['optim/lr'] = current_lr
                metrics['optim/grad_norm'] = grad_norm.item() if isinstance(grad_norm, torch.Tensor) else grad_norm
                metrics['optim/ema_momentum'] = momentum

                # Masking
                metrics['mask/family'] = mask_data['mask_families'][0]
                metrics['mask/ratio'] = np.mean(mask_data['mask_ratios'])

                # Throughput
                world_size = get_world_size()
                metrics['perf/step_time_sec'] = step_time
                metrics['perf/samples_per_sec'] = (batch_size * world_size) / max(step_time, 1e-6)

                logger.log(metrics, global_step, epoch)
                logger.print_metrics(metrics, global_step, epoch)

            # --------------------------------------------------------
            # Collapse monitoring (every collapse_check_interval, rank 0 only)
            # --------------------------------------------------------
            if rank0 and global_step % vc.collapse_check_interval == 0:
                with torch.no_grad():
                    # Core embedding health
                    collapse_metrics = collapse_monitor.check(
                        outputs['s3_embeddings'], name='s3'
                    )

                    # Prediction quality
                    pred_metrics = collapse_monitor.check_predictions(
                        outputs['pred_s3'], outputs['target_s3'],
                        outputs.get('valid_mask_s3'),
                    )
                    collapse_metrics.update(pred_metrics)

                    # Conditioning activity
                    cond_metrics = collapse_monitor.check_conditioning(raw_model, window_id)
                    collapse_metrics.update(cond_metrics)

                    logger.log(collapse_metrics, global_step, epoch)

                    # Log histograms
                    logger.log_histogram('health/s3_embed_std_distribution',
                                         outputs['s3_embeddings'].std(dim=-1).flatten(),
                                         global_step)

                    severity = collapse_metrics.get('health/s3_severity', 'ok')

                    if severity == 'WARNING':
                        print(f"\n  WARNING: Potential collapse at step {global_step}")
                        print(f"    Std min: {collapse_metrics['health/s3_embed_std_min']:.2e}")
                        print(f"    Rank ratio: {collapse_metrics['health/s3_rank_ratio']:.4f}")
                        print(f"    Pred-target cosine: {collapse_metrics.get('health/pred_target_cosine', 0):.4f}\n")

                    elif severity == 'HALT':
                        print(f"\n  COLLAPSE DETECTED at step {global_step}! Halting training.")
                        print(f"    Std min: {collapse_metrics['health/s3_embed_std_min']:.2e}")
                        print(f"    Rank ratio: {collapse_metrics['health/s3_rank_ratio']:.4f}")
                        should_halt = True
                        break

        # Track losses
        for k, v in losses.items():
            if isinstance(v, torch.Tensor):
                if k not in epoch_losses:
                    epoch_losses[k] = []
                epoch_losses[k].append(v.item())

    pbar.close()

    # Flush tail batches: if accumulated gradients remain, step the optimizer
    if (batch_idx + 1) % accumulation_steps != 0 and not should_halt:
        if tc.mixed_precision:
            scaler.unscale_(optimizer)

        grad_norm = torch.nn.utils.clip_grad_norm_(
            raw_model.parameters(), tc.grad_clip_norm
        )

        if tc.mixed_precision:
            scaler.step(optimizer)
            scaler.update()
        else:
            optimizer.step()

        optimizer.zero_grad()
        momentum = raw_model.update_target_encoder()
        current_lr = scheduler.step()
        global_step += 1

    # Broadcast halt decision so all ranks stop together
    if is_distributed():
        halt_tensor = torch.tensor([1 if should_halt else 0], device=device)
        dist.all_reduce(halt_tensor, op=dist.ReduceOp.MAX)
        should_halt = halt_tensor.item() > 0

    # End-of-epoch summary (rank 0 only)
    epoch_time = time.time() - epoch_start
    if rank0:
        summary = {f'epoch/avg_{k}': np.mean(v) for k, v in epoch_losses.items()}
        summary['epoch/time_seconds'] = epoch_time
        summary['epoch/samples_per_sec'] = len(dataloader.dataset) / max(epoch_time, 1)

        # Mask family distribution for this epoch
        total_masks = sum(mask_family_counts.values())
        for fam, count in mask_family_counts.items():
            summary[f'epoch/mask_pct_{fam}'] = count / max(total_masks, 1)

        logger.log(summary, global_step, epoch)

        print(f"\n{'='*60}")
        print(f"Epoch {epoch} | Time: {epoch_time:.1f}s | "
              f"Avg loss: {np.mean(epoch_losses.get('total', [0])):.6f} | "
              f"Samples/s: {summary['epoch/samples_per_sec']:.1f}")
        loss_parts = []
        for k in ['jepa3', 'jepa2', 'sigreg', 'align', 'cross_stage', 'decoder', 'local_contrast']:
            if k in epoch_losses:
                loss_parts.append(f"{k}={np.mean(epoch_losses[k]):.4f}")
        if loss_parts:
            print(f"  Losses: {' | '.join(loss_parts)}")
        mask_parts = [f"{fam}={count/max(total_masks,1)*100:.0f}%" for fam, count in sorted(mask_family_counts.items())]
        if mask_parts:
            print(f"  Masks: {' | '.join(mask_parts)}")
        print(f"{'='*60}\n")

    return global_step, should_halt


def main():
    args = parse_args()

    # ---- Distributed setup ----
    setup_distributed()
    rank = get_rank()
    world_size = get_world_size()
    rank0 = is_main_process()

    set_seed(args.seed, rank)

    config = setup_config(args)

    # Set device: use LOCAL_RANK for multi-GPU, fallback to args.device
    if is_distributed():
        local_rank = int(os.environ['LOCAL_RANK'])
        device = torch.device(f'cuda:{local_rank}')
    else:
        device = torch.device(args.device if torch.cuda.is_available() else 'cpu')

    # ---- Print config (rank 0 only) ----
    if rank0:
        print("=" * 60)
        print("CT-JEPA v2 Training")
        print("=" * 60)
        print(f"Variant: {config.model.variant}")
        print(f"Local block type: {config.model.local_block_type}")
        print(f"Device: {device}")
        print(f"World size: {world_size}")
        print(f"Epochs: {config.training.total_epochs}")
        print(f"Batch size per GPU: {config.training.batch_size}")
        print(f"Grad accumulation: {config.training.grad_accumulation_steps}")
        print(f"Effective batch: {config.training.batch_size * config.training.grad_accumulation_steps * world_size}")
        print(f"WandB: {'enabled' if config.validation.use_wandb else 'disabled'}")
        print()

    # ---- Build model ----
    if rank0:
        print("Building model...")
    raw_model = CTJEPA(config).to(device)

    if rank0:
        param_info = count_parameters(raw_model)
        print(f"Total parameters: {param_info['total_params_M']:.1f}M")
        print(f"Trainable parameters: {param_info['trainable_params_M']:.1f}M")
        print()

    # Wrap with DDP if distributed
    if is_distributed():
        model = DDP(raw_model, device_ids=[local_rank], gradient_as_bucket_view=False)
    else:
        model = raw_model

    # ---- Create dataloaders ----
    if rank0:
        print("Creating dataloaders...")

    # Build datasets once, reuse for sampler + dataloader
    train_dataset = CTJEPADataset(
        csv_path=config.data.csv_path, data_root=config.data.data_root,
        img_col=config.data.img_col, text_col=config.data.text_col,
        split_col=config.data.split_col, split="train",
        has_reports=config.text.use_text, max_text_len=config.text.text_max_tokens,
    )
    val_dataset = CTJEPADataset(
        csv_path=config.data.csv_path, data_root=config.data.data_root,
        img_col=config.data.img_col, text_col=config.data.text_col,
        split_col=config.data.split_col, split="val",
        has_reports=config.text.use_text, max_text_len=config.text.text_max_tokens,
    )

    train_sampler = None
    if is_distributed():
        train_sampler = DistributedSampler(
            train_dataset, num_replicas=world_size, rank=rank,
            shuffle=True, drop_last=True,
        )

    train_loader = create_dataloader(config, is_train=True, split="train",
                                     sampler=train_sampler, dataset=train_dataset)
    # Validation only runs on rank 0 — no DistributedSampler needed (full dataset)
    val_loader = create_dataloader(config, is_train=False, split="val",
                                   dataset=val_dataset)
    steps_per_epoch = len(train_loader) // config.training.grad_accumulation_steps

    # Build labeled dataset for linear probe if configured
    labeled_dataset = None
    if config.validation.probe_csv:
        try:
            labeled_dataset = MultiLabelProbeDataset(
                csv_path=config.validation.probe_csv,
                data_root=config.data.data_root,
                img_col=config.data.img_col,
                split_col=config.data.split_col,
                split="val",
            )
            if rank0:
                print(f"Linear probe dataset: {len(labeled_dataset)} samples, "
                      f"{labeled_dataset.num_classes} classes")
        except Exception as e:
            if rank0:
                print(f"Warning: Failed to create probe dataset: {e}")

    if rank0:
        print(f"Train set: {len(train_loader.dataset)} samples")
        print(f"Val set: {len(val_loader.dataset)} samples")
        print(f"Steps per epoch: {steps_per_epoch}")
        print()

    # ---- Loss, optimizer, scheduler ----
    loss_fn = CTJEPALoss(config).to(device)

    param_groups = raw_model.get_param_groups(
        config.training.base_lr, config.training.weight_decay
    )
    optimizer = torch.optim.AdamW(param_groups)

    scheduler = CosineWarmupScheduler(
        optimizer=optimizer,
        base_lr=config.training.base_lr,
        min_lr=config.training.min_lr,
        warmup_epochs=config.training.warmup_epochs,
        total_epochs=config.training.total_epochs,
        steps_per_epoch=steps_per_epoch,
    )

    total_steps = config.training.total_epochs * steps_per_epoch
    raw_model.ema.total_steps = total_steps

    scaler = GradScaler() if config.training.mixed_precision else None
    mask_sampler = MaskSampler(config)

    collapse_monitor = CollapseMonitor(
        std_threshold=config.training.collapse_std_threshold,
        warn_threshold=config.validation.collapse_warn_threshold,
        halt_threshold=config.validation.collapse_halt_threshold,
    )

    # ---- Logger & checkpoints ----
    os.makedirs(args.output_dir, exist_ok=True)

    wandb_config = {
        'variant': config.model.variant,
        'local_block_type': config.model.local_block_type,
        'total_params_M': count_parameters(raw_model)['total_params_M'],
        'batch_size_per_gpu': config.training.batch_size,
        'grad_accum': config.training.grad_accumulation_steps,
        'world_size': world_size,
        'effective_batch': config.training.batch_size * config.training.grad_accumulation_steps * world_size,
        'lr': config.training.base_lr,
        'epochs': config.training.total_epochs,
        'train_samples': len(train_loader.dataset),
        'val_samples': len(val_loader.dataset),
    }

    # Only rank 0 initializes WandB and writes logs
    logger = TrainLogger(
        log_dir=os.path.join(args.output_dir, 'logs'),
        experiment_name=f"ctjepa_v2_{config.model.variant}_{config.model.local_block_type}",
        use_wandb=config.validation.use_wandb and rank0,
        wandb_project=config.validation.wandb_project,
        wandb_run_name=config.validation.wandb_run_name,
        wandb_config=wandb_config,
    )

    ckpt_manager = CheckpointManager(
        save_dir=os.path.join(args.output_dir, 'checkpoints'),
    )

    # ---- Resume ----
    start_epoch = 0
    global_step = 0
    if args.resume:
        if rank0:
            print(f"Resuming from {args.resume}...")
        state = ckpt_manager.load(args.resume, raw_model, optimizer, scheduler)
        start_epoch = state['epoch'] + 1
        global_step = state['step']
        if rank0:
            print(f"Resumed at epoch {start_epoch}, step {global_step}")

    # ---- Validate-only mode ----
    if args.validate_only:
        if not args.resume:
            print("ERROR: --validate_only requires --resume <checkpoint_path>")
            sys.exit(1)
        if rank0:
            print("\nRunning validation only (skipping training)...\n")
            run_validation(
                model=raw_model,
                val_loader=val_loader,
                config=config,
                device=device,
                epoch=start_epoch - 1,  # epoch from checkpoint
                global_step=global_step,
                logger=logger,
                output_dir=args.output_dir,
                mask_sampler=mask_sampler,
                labeled_dataset=labeled_dataset,
            )
        logger.finish()
        cleanup_distributed()
        return

    # ---- Phase transition epochs ----
    phase_epochs = set(config.validation.phase_transition_epochs)

    # ---- Training loop ----
    if rank0:
        print("\nStarting training...\n")

    for epoch in range(start_epoch, config.training.total_epochs):
        # Set epoch on distributed sampler for proper shuffling
        if train_sampler is not None:
            train_sampler.set_epoch(epoch)

        if rank0:
            progress = epoch / config.training.total_epochs
            if progress < 0.3:
                phase = "Phase 1: Foundation (cuboid-heavy, no text)"
            elif progress < 0.65:
                phase = "Phase 2: Expansion (balanced masking, text enabled)"
            else:
                phase = "Phase 3: Refinement (hard masking, full objectives)"
            print(f"  {phase}")

        # ---- Train one epoch ----
        global_step, should_halt = train_one_epoch(
            model=model,
            loss_fn=loss_fn,
            optimizer=optimizer,
            scheduler=scheduler,
            scaler=scaler,
            dataloader=train_loader,
            mask_sampler=mask_sampler,
            config=config,
            epoch=epoch,
            device=device,
            logger=logger,
            collapse_monitor=collapse_monitor,
            global_step=global_step,
            raw_model=raw_model,
        )

        # ---- Auto-halt on collapse ----
        if should_halt:
            if rank0:
                print("  Saving emergency checkpoint before halt...")
                ckpt_manager.save(
                    model=raw_model, optimizer=optimizer, scheduler=scheduler,
                    epoch=epoch, step=global_step, loss=0.0,
                    ema_momentum=raw_model.ema.get_momentum(),
                    extra={'halt_reason': 'collapse'},
                )
            if is_distributed():
                dist.barrier()
            break

        # ---- Checkpoint (rank 0 only) ----
        if rank0 and (epoch + 1) % config.training.save_interval == 0:
            ckpt_path = ckpt_manager.save(
                model=raw_model,
                optimizer=optimizer,
                scheduler=scheduler,
                epoch=epoch,
                step=global_step,
                loss=0.0,
                ema_momentum=raw_model.ema.get_momentum(),
            )
            print(f"  Checkpoint saved: {ckpt_path}")

        # ---- Validation (rank 0 only) ----
        if rank0 and (epoch + 1) % config.validation.eval_interval == 0:
            run_validation(
                model=raw_model,
                val_loader=val_loader,
                config=config,
                device=device,
                epoch=epoch,
                global_step=global_step,
                logger=logger,
                output_dir=args.output_dir,
                mask_sampler=mask_sampler,
                labeled_dataset=labeled_dataset,
            )

        # ---- Phase transition evaluation (rank 0 only) ----
        if rank0 and epoch in phase_epochs:
            run_phase_evaluation(
                model=raw_model,
                val_loader=val_loader,
                config=config,
                device=device,
                epoch=epoch,
                global_step=global_step,
                logger=logger,
                ckpt_manager=ckpt_manager,
                mask_sampler=mask_sampler,
            )

        if is_distributed():
            dist.barrier()

    # ---- Save final model (rank 0 only) ----
    if rank0:
        print("\n  Training complete!")

        final_path = os.path.join(args.output_dir, 'ctjepa_v2_final.pt')
        torch.save({
            'config': config,
            'context_encoder': raw_model.context_encoder.state_dict(),
            'target_encoder': raw_model.target_encoder.state_dict(),
        }, final_path)
        print(f"Final model saved to {final_path}")

        # Final validation
        run_validation(
            model=raw_model,
            val_loader=val_loader,
            config=config,
            device=device,
            epoch=config.training.total_epochs - 1,
            global_step=global_step,
            logger=logger,
            output_dir=args.output_dir,
            mask_sampler=mask_sampler,
            labeled_dataset=labeled_dataset,
        )

    logger.finish()
    cleanup_distributed()


if __name__ == '__main__':
    main()
