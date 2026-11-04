import torch
import torch.nn as nn
import torch.distributed as dist
import os

def unwrap_model(model):
    """Unwrap model from DistributedDataParallel or other wrappers."""
    if hasattr(model, 'module'):
        return model.module
    return model

def get_loss_scale_for_deepspeed(model):
    """Get loss scale from DeepSpeed optimizer."""
    optimizer = model.optimizer
    loss_scale = None
    if hasattr(optimizer, 'loss_scale'):
        loss_scale = optimizer.loss_scale
    elif hasattr(optimizer, 'cur_scale'):
        loss_scale = optimizer.cur_scale
    return loss_scale, optimizer._global_grad_norm

def get_grad_norm_(parameters, norm_type: float = 2.0) -> torch.Tensor:
    """Calculate gradient norm."""
    if isinstance(parameters, torch.Tensor):
        parameters = [parameters]
    parameters = [p for p in parameters if p.grad is not None]
    norm_type = float(norm_type)
    if len(parameters) == 0:
        return torch.tensor(0.)
    device = parameters[0].grad.device
    if norm_type == float('inf'):
        total_norm = max(p.grad.detach().abs().max().to(device) for p in parameters)
    else:
        total_norm = torch.norm(torch.stack([torch.norm(p.grad.detach(), norm_type).to(device) for p in parameters]), norm_type)
    return total_norm.to(dtype=torch.float32)

def save_model(model, epoch, args):
    """Save model checkpoint."""
    if args.logs and args.logs.lower() != 'none' and args.enable_deepspeed:
        deepspeed_checkpoint_path = os.path.join('./checkpoints/saved_models', "checkpoints")
        client_state = {'epoch': epoch}
        checkpoint_tag = f"epoch_{epoch}"
        if dist.is_initialized():
            dist.barrier()
        model.save_checkpoint(save_dir=deepspeed_checkpoint_path, tag=checkpoint_tag, client_state=client_state)
        if dist.is_initialized():
            dist.barrier()
        return deepspeed_checkpoint_path

def load_model(pth, model):
    """Load model from DeepSpeed checkpoint."""
    from deepspeed.utils.zero_to_fp32 import get_fp32_state_dict_from_zero_checkpoint
    checkpoint_path = pth
    state_dict = get_fp32_state_dict_from_zero_checkpoint(checkpoint_path)
    model.load_state_dict(state_dict, strict=False)
    return model 