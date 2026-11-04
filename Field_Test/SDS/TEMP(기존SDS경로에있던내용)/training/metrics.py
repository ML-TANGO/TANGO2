import torch
import torch.nn.functional as F
import numpy as np

class AverageMeter:
    """Computes and stores the average and current value"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

def get_metrics(image_features, text_features, logit_scale, epoch=None, oids=None):
    """Calculate retrieval metrics for image-text matching."""
    metrics = {}
    logits_per_image = (logit_scale * image_features @ text_features.t()).detach().cpu()
    logits_per_text = logits_per_image.t().detach().cpu()

    logits = {"image_to_text": logits_per_image, "text_to_image": logits_per_text}
    ground_truth = torch.arange(len(text_features)).view(-1, 1)

    for name, logit in logits.items():
        ranking = torch.argsort(logit, descending=True)
        preds = torch.where(ranking == ground_truth)[1]
        preds = preds.detach().cpu().numpy()
        metrics[f"{name}_mean_rank"] = preds.mean() + 1
        metrics[f"{name}_median_rank"] = np.floor(np.median(preds)) + 1
        for k in [1, 5, 10]:
            metrics[f"{name}_R@{k}"] = np.mean(preds < k)

    return metrics

def get_chunk_metrics(image_features, text_features, logit_scale):
    """Calculate metrics on a manageable chunk of data."""
    metrics = get_metrics(image_features, text_features, logit_scale)
    
    # Free memory
    torch.cuda.empty_cache()
    
    return metrics

def aggregate_metrics(metrics_per_chunk):
    """Aggregate metrics from multiple chunks with proper weighting."""
    aggregated = {}
    total_samples = sum(count for _, count in metrics_per_chunk)
    
    # Initialize aggregated metrics
    first_metrics = metrics_per_chunk[0][0]
    for key in first_metrics:
        aggregated[key] = 0.0
    
    # Weight metrics by chunk size
    for chunk_metrics, count in metrics_per_chunk:
        weight = count / total_samples
        for key, value in chunk_metrics.items():
            aggregated[key] += value * weight
            
    return aggregated 