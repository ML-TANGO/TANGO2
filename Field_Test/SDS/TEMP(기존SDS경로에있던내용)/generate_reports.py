#!/usr/bin/env python3
"""
Report generation script for CT volumes using trained model.
Loads npz files from a directory, matches against predefined impression and findings pools,
and generates reports in the specified JSON format.
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm

# Add the current directory to path for imports
sys.path.append(os.getcwd())

from transformers import AutoTokenizer
from merlin import Merlin
from training.llm2vec_wrapper import LLM2VecWrapper as LLM2Vec
from peft import LoraConfig, get_peft_model, TaskType
from training.ct_transform import get_val_transform

# Import dataset utilities for robust NPZ loading
import pandas as pd

# ---------------------------------------------------------------------------
#  CT on‑the‑fly pre‑processing (same settings you used for offline *.npz)
# ---------------------------------------------------------------------------
from monai.transforms.compose import Compose
from monai.transforms.io.array import LoadImage
from monai.transforms.utility.array import EnsureChannelFirst, CastToType
from monai.transforms.spatial.array import Orientation, Spacing
from monai.transforms.intensity.array import ScaleIntensityRange
from monai.transforms.croppad.array import SpatialPad, CenterSpatialCrop

TARGET_SPACING = (1.25, 1.25, 2.0)            # mm
TARGET_SHAPE   = (256, 256, 192)              # H, W, D
HU_WINDOW      = (-1000, 1500)
NPZ_DTYPE      = np.float16                   # storage only

ct_load_pipeline = Compose([
    LoadImage(image_only=True, dtype=np.float32),      # (Z, Y, X)
    EnsureChannelFirst(),                              # (1, Z, Y, X)
    Orientation(axcodes="RAS"),
    Spacing(pixdim=TARGET_SPACING,
            mode="trilinear", align_corners=True),
    ScaleIntensityRange(a_min=HU_WINDOW[0], a_max=HU_WINDOW[1],
                        b_min=0.0, b_max=1.0, clip=True),
    SpatialPad(spatial_size=(*TARGET_SHAPE,)),
    CenterSpatialCrop(roi_size=(*TARGET_SHAPE,)),
    CastToType(dtype=np.float16),
])

SUPPORTED_RAW_EXTS = (".nii", ".nii.gz", ".mha")
SUPPORTED_COMPRESSED_EXTS = (".npz",)          # keep this for backward compat

class ModelWithCustomVisual(nn.Module):
    """Combines a custom visual model (Merlin) with a text model for CLIP-style training."""
    
    def __init__(self, visual_model, text_model, vision_projection=None):
        super().__init__()
        self.visual = visual_model
        self.text = text_model
        self.vision_projection = vision_projection
        
        # Initialize learnable logit_scale and logit_bias
        self.logit_scale = nn.Parameter(torch.tensor(10.0))   # linear scale = 10
        self.logit_bias  = nn.Parameter(torch.tensor(-10.0))
        
    def encode_image(self, image):
        # Handle both 2D (CXR) and 3D (CT) images
        if len(image.shape) == 5:  # 3D CT: (B, C, D, H, W)
            features = self.visual(image)
        elif len(image.shape) == 4:  # 2D CXR: (B, C, H, W)  
            features = self.visual(image)
        else:
            raise ValueError(f"Unexpected image shape: {image.shape}")
        
        # Ensure features are in the right shape
        if len(features.shape) > 2:
            features = features.squeeze()
        
        # Apply vision projection layer if provided
        if self.vision_projection is not None:
            features = self.vision_projection(features)
        
        # Normalize projected features
        return features / features.norm(dim=-1, keepdim=True)
        
    def encode_text(self, text):
        features = self.text(text)
        return features / features.norm(dim=-1, keepdim=True)
    
    def forward(self, image, text):
        image_features = self.encode_image(image)
        text_features = self.encode_text(text)
        
        # Compute similarity using the learnable logit_scale and logit_bias
        logits = self.logit_scale * image_features @ text_features.t() + self.logit_bias
            
        return logits

class LLM2VecWithProjection(nn.Module):
    def __init__(self, llm2vec_model, projection):
        super().__init__()
        self.model = llm2vec_model
        self.projection = projection
        
        # Ensure the LLM2Vec model is in the same dtype as the projection
        self.model.to(next(self.projection.parameters()).dtype)
            
        # Freeze the base LLM model parameters but keep LoRA parameters trainable
        for name, param in self.model.named_parameters():
            if "lora_" in name:
                param.requires_grad = True  # Keep LoRA parameters trainable
            else:
                param.requires_grad = False  # Freeze base model parameters
            
        # Ensure projection layer is trainable
        for param in self.projection.parameters():
            param.requires_grad = True

    def forward(self, text):
        # Ensure input is in the correct dtype if it's a tensor
        if isinstance(text, torch.Tensor):
            text = text.to(next(self.model.parameters()).dtype)
        
        embeddings = self.model(text)
        # Ensure consistent dtype
        if embeddings.dtype != next(self.projection.parameters()).dtype:
            embeddings = embeddings.to(next(self.projection.parameters()).dtype)
        return self.projection(embeddings)

def load_model(checkpoint_path, text_base_model="microsoft/LLM2CLIP-Llama-3.2-1B-Instruct-CC-Finetuned", device="cuda", precision="bf16"):
    """Load the trained model from checkpoint."""
    
    logging.info("Loading model components...")
    
    # Set up precision
    if precision == "bf16":
        dtype = torch.bfloat16
    elif precision == "fp16":
        dtype = torch.float16
    else:
        dtype = torch.float32
    
    # Load visual model (Merlin)
    visual_model = Merlin(ImageEmbedding=True)
    visual_model.to(dtype)
    
    # Load text model (LLM2Vec)
    text_model = LLM2Vec.from_pretrained(
        base_model_name_or_path=text_base_model,
        enable_bidirectional=True,
        pooling_mode="latent_attention",
        max_length=512,
        torch_dtype=dtype,
    )
    text_model.to(device)
    # Ensure all parameters are in correct dtype
    text_model.to(dtype)
    
    # Load intermediate checkpoint for text model
    intermediate_checkpoint_path = "models/llm2vec4cxr.bin"
    if os.path.exists(intermediate_checkpoint_path):
        logging.info(f"Loading intermediate text model weights from {intermediate_checkpoint_path}")
        intermediate_state_dict = torch.load(intermediate_checkpoint_path, map_location=device)
        
        # Filter only the text model related keys and remove any module prefix
        text_model_keys = {}
        for k, v in intermediate_state_dict.items():
            # Remove 'module.' prefix if present
            key = k[len('module.'):] if k.startswith('module.') else k
            text_model_keys[key] = v
        
        # Load the intermediate weights into the text model
        missing, unexpected = text_model.load_state_dict(text_model_keys, strict=False)
        logging.info(f"Intermediate loading - Missing: {len(missing)}, Unexpected: {len(unexpected)}")
    else:
        logging.warning(f"Intermediate checkpoint not found: {intermediate_checkpoint_path}")
    
    # Add LoRA configuration to the text model
    lora_config = LoraConfig(
        task_type=TaskType.FEATURE_EXTRACTION,
        inference_mode=False,
        r=32,  # rank
        lora_alpha=32,  # scaling parameter
        lora_dropout=0.1,
        target_modules=["q_proj", "k_proj", "v_proj", "out_proj"],  # target attention modules
        bias="none",
    )
    
    # Apply LoRA only to the underlying transformer model
    base_transformer = text_model.model
    base_transformer = get_peft_model(base_transformer, lora_config)
    text_model.model = base_transformer
    # Ensure the model is still in correct dtype after LoRA
    text_model.to(dtype)

    # Create projection layers
    hidden_size = text_model.config.hidden_size
    text_projection_layer = nn.Sequential(
        nn.LayerNorm(hidden_size),
        nn.Linear(hidden_size, 1280)  # Project to 1280 dimensions
    ).to(device).to(dtype)
    
    vision_projection_layer = nn.Sequential(
        nn.LayerNorm(2048),  # Merlin outputs 2048 features
        nn.Linear(2048, 1280)  # Project to 1280 dimensions
    ).to(device).to(dtype)

    # Create wrapped text model
    text_model = LLM2VecWithProjection(text_model, text_projection_layer)
    
    # Ensure all parameters and buffers are in correct dtype
    for name, param in text_model.named_parameters():
        if param.dtype != dtype:
            param.data = param.data.to(dtype)
    
    for name, buffer in text_model.named_buffers():
        if buffer.dtype != dtype:
            buffer.data = buffer.data.to(dtype)
    
    # Create combined model
    model = ModelWithCustomVisual(visual_model, text_model, vision_projection_layer)
    
    # Load checkpoint
    logging.info(f"Loading checkpoint from {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device)
    
    # Handle different checkpoint formats
    if 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    else:
        state_dict = checkpoint
    
    # Remove 'module.' prefix if present (from DistributedDataParallel)
    if next(iter(state_dict.items()))[0].startswith('module.'):
        state_dict = {k[len('module.'):]: v for k, v in state_dict.items()}
    
    missing, unexpected = model.load_state_dict(state_dict, strict=False)
    print(f"Missing keys: {len(missing)}  |  Unexpected: {len(unexpected)}")
    
    # Print first few missing keys to debug the issue
    if len(missing) > 0:
        print("First 10 missing keys:")
        for key in missing[:10]:
            print(f"  - {key}")
    
    if len(unexpected) > 0:
        print("First 10 unexpected keys:")
        for key in unexpected[:10]:
            print(f"  - {key}")
    
    # Check if missing keys are LoRA-related
    lora_missing = [key for key in missing if 'lora_' in key]
    non_lora_missing = [key for key in missing if 'lora_' not in key]
    
    print(f"LoRA missing keys: {len(lora_missing)}")
    print(f"Non-LoRA missing keys: {len(non_lora_missing)}")
    
    # Only assert if LoRA keys are missing (non-LoRA keys are expected - they're base model weights)
    assert len(lora_missing)==0, f"LoRA weights were not restored: {lora_missing[:5]}"
    
    if len(lora_missing) == 0 and len(missing) > 0:
        print("✅ All LoRA weights loaded successfully!")
        print(f"ℹ️  {len(non_lora_missing)} base model weights missing (expected - loaded from pretrained model)")
    model.to(device)
    model.to(dtype)  # Ensure final model is in correct dtype
    model.eval()
    
    # Log model parameters for debugging
    logging.info(f"Model loaded successfully!")
    logging.info(f"Logit scale: {model.logit_scale.item():.4f}")
    logging.info(f"Logit bias: {model.logit_bias.item():.4f}")
    
    return model

def load_text_embeddings_pth(pth_file, device, dtype=torch.bfloat16):
    """Load text embeddings from a .pth file."""
    pkg = torch.load(pth_file, map_location="cpu")
    feats = pkg["embeddings"].to(device=device, dtype=dtype)
    if not torch.allclose(feats.norm(dim=-1), torch.ones_like(feats[:, 0]), atol=1e-3):
        feats = torch.nn.functional.normalize(feats, dim=-1)
    texts = pkg["texts"]  # list[str]
    return feats, texts

def get_pool(name, emb_path, json_path, model, tokenizer, device, dtype, separator):
    """
    Load one text pool. Returns (features, texts) fully prepared.
    Priority:
        1) use <emb_path> if it exists
        2) otherwise fall back to <json_path> + on‑the‑fly encoding
    """
    if emb_path and os.path.isfile(emb_path):
        logging.info(f"[{name}] Using cached embeddings from {emb_path}")
        feats, texts = load_text_embeddings_pth(emb_path, device=device, dtype=dtype)
        return feats, texts

    # ---- fall back to original JSON list --------------------------------
    logging.info(f"[{name}] No cached file. Loading {json_path} and encoding …")
    with open(json_path, "r") as f:
        texts = json.load(f)
    feats = encode_texts_batch(model, tokenizer, texts, device, batch_size=32, separator=separator)
    return feats, texts

def load_text_pools(impressions_path, findings_path):
    """Load impression and findings pools from JSON files."""
    
    logging.info(f"Loading impressions from {impressions_path}")
    with open(impressions_path, 'r') as f:
        impressions = json.load(f)
    
    logging.info(f"Loading findings from {findings_path}")
    with open(findings_path, 'r') as f:
        findings = json.load(f)
    
    logging.info(f"Loaded {len(impressions)} impressions and {len(findings)} findings")
    
    return impressions, findings

def collect_image_files(input_dir):
    """
    Return a sorted list[Path] with every *.npz, *.nii, *.nii.gz, *.mha
    in *input_dir* (non‑recursive; add rglob if you want recursion).
    """
    input_dir = Path(input_dir)
    paths = []
    for ext in SUPPORTED_COMPRESSED_EXTS + SUPPORTED_RAW_EXTS:
        paths.extend(input_dir.glob(f"*{ext}"))
    logging.info(f"Found {len(paths)} image files in {input_dir}")
    return sorted(paths)

def preprocess_ct_volume(path, val_transform, use_3channel=False):
    """
    Accept *.npz  OR  raw *.nii / *.nii.gz / *.mha.
    Returns a 5‑D tensor (1, C, D, H, W) in fp32 ready for the model.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    # ────────────────── 1) already‑compressed *.npz ──────────────────
    if path.suffix.lower() in SUPPORTED_COMPRESSED_EXTS:
        with np.load(str(path)) as npz:
            if "image" not in npz:
                raise KeyError(f"'image' key missing in {path}")
            arr = npz["image"]                         # (C, H, W, D) fp16/32
        img = torch.from_numpy(arr).float()            # → fp32
    # ────────────────── 2) raw NIfTI / MetaImage ────────────────────
    elif path.name.lower().endswith(SUPPORTED_RAW_EXTS):
        vol = ct_load_pipeline(str(path))              # (1, Z, Y, X) fp16
        # Convert MetaTensor to tensor directly
        try:
            # Try to convert to tensor first (handles MetaTensor and other types)
            img = torch.as_tensor(vol).float()         # (1, D, H, W)
        except:
            # Fallback to numpy conversion
            img = torch.from_numpy(np.array(vol)).float()  # (1, D, H, W)
    else:
        raise ValueError(f"Unsupported extension: {path.suffix}")

    # -------- optional three‑window conversion -----------------------
    if use_3channel:
        hu = img[0] * (HU_WINDOW[1] - HU_WINDOW[0]) + HU_WINDOW[0]
        lung = torch.clamp((hu + 600) / 1000, 0, 1)    # centre –600, width 1000
        medi = torch.clamp((hu - 40)  /  400, 0, 1)    # centre   40, width  400
        bone = torch.clamp((hu - 700) / 1500, 0, 1)    # centre  700, width 1500
        img = torch.stack([lung, medi, bone], dim=0)   # (3, D, H, W)

    # ----------------------------------------------------------------
    # Apply the *runtime* val_transform you already use for CLIP
    # (e.g. random crop / resize. It expects a torch tensor.)
    if val_transform is not None:
        img = val_transform(img)

    # Add batch dim expected by encode_image: (B, C, D, H, W)
    if img.dim() == 4:
        img = img.unsqueeze(0)
    return img

def encode_texts_batch(model, tokenizer, texts, device, batch_size=32, separator="!@#$%^&*()"):
    """Encode a list of texts in batches with proper embed_mask creation for LLM2Vec."""
    
    all_features = []
    max_length = 512
    
    for i in tqdm(range(0, len(texts), batch_size), desc="Encoding texts"):
        batch_texts = texts[i:i+batch_size]
        
        # Handle text with separator and create embed_mask for LLM2Vec (from dataset logic)
        texts_2 = []
        original_texts = []
        
        for text in batch_texts:
            t = text.split(separator)
            texts_2.append(t[1] if len(t) > 1 else "")
            original_texts.append("".join(t))

        original = tokenizer(
            original_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        )
        
        embed_mask = None
        for t_i, t in enumerate(texts_2):
            ids = tokenizer(
                [t],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=max_length,
                add_special_tokens=False,
            )
            if embed_mask is None:
                e_m = torch.zeros_like(original["attention_mask"][t_i])
                if len(ids["input_ids"][0]) > 0:
                    e_m[-len(ids["input_ids"][0]) :] = torch.ones(
                        len(ids["input_ids"][0])
                    )
                embed_mask = e_m.unsqueeze(0)
            else:
                e_m = torch.zeros_like(original["attention_mask"][t_i])
                if len(ids["input_ids"][0]) > 0:
                    e_m[-len(ids["input_ids"][0]) :] = torch.ones(
                        len(ids["input_ids"][0])
                    )
                embed_mask = torch.cat((embed_mask, e_m.unsqueeze(0)), dim=0)

        original["embed_mask"] = embed_mask
        
        # Move to device
        encoded = {k: v.to(device) for k, v in original.items()}
        
        # Encode
        with torch.no_grad():
            features = model.encode_text(encoded)
            # Keep features on the same device instead of moving to CPU
            all_features.append(features)
    
    return torch.cat(all_features, dim=0)

def find_best_matches(image_features, text_features, texts, logit_scale=None, logit_bias=None):
    """Find the best matching text for each image."""
    
    # Ensure both features are on the same device
    device = image_features.device
    if text_features.device != device:
        text_features = text_features.to(device)
    
    # Normalize features
    image_features = F.normalize(image_features.float(), dim=-1)
    text_features = F.normalize(text_features.float(), dim=-1)
    
    # Compute similarity
    logits = (image_features @ text_features.t()).float()
    
    if logit_scale is not None:
        # Ensure logit_scale is on the same device
        if logit_scale.device != device:
            logit_scale = logit_scale.to(device)
        logits = logit_scale.mean().float() * logits
    
    if logit_bias is not None:
        # Ensure logit_bias is on the same device
        if logit_bias.device != device:
            logit_bias = logit_bias.to(device)
        logits = logits + logit_bias.float()
    
    # Find best matches
    best_indices = torch.argmax(logits, dim=1).cpu().numpy()
    best_texts = [texts[idx] for idx in best_indices]
    best_scores = torch.max(logits, dim=1)[0].cpu().numpy()
    
    return best_texts, best_scores, best_indices

def generate_reports(model, tokenizer, input_dir, impressions_path, findings_path, device="cuda", precision="bf16", use_3channel=False, separator="!@#$%^&*()", impressions_emb=None, findings_emb=None):
    """Generate reports for all CT volumes in the input directory."""
    
    # Set up precision
    if precision == "bf16":
        dtype = torch.bfloat16
    elif precision == "fp16":
        dtype = torch.float16
    else:
        dtype = torch.float32
    
    # Load text pools using new get_pool logic
    impression_features, impressions = get_pool(
        "impressions", impressions_emb, impressions_path, 
        model, tokenizer, device, dtype, separator
    )
    findings_features, findings = get_pool(
        "findings", findings_emb, findings_path,
        model, tokenizer, device, dtype, separator
    )
    
    # Load image files (npz, nii, nii.gz, mha)
    image_files = collect_image_files(input_dir)
    
    if not image_files:
        raise ValueError(f"No image files found in {input_dir}")
    
    # Get CT transforms
    transform = get_val_transform()
    
    # Process each CT volume
    generated_reports = []
    
    model.eval()
    with torch.no_grad():
        for img_path in tqdm(image_files, desc="Processing CT volumes"):
            
            # Get input image name (without extension)
            input_image_name = img_path.stem
            
            try:
                # Load and preprocess CT volume using enhanced dataset logic
                volume = preprocess_ct_volume(img_path, val_transform=transform, use_3channel=use_3channel)
                volume = volume.to(device, dtype=dtype)
                
                # Encode image
                image_features = model.encode_image(volume)  # Already normalized
                
                # Find best impression
                best_impressions, impression_scores, impression_indices = find_best_matches(
                    image_features, impression_features, impressions,
                    logit_scale=model.logit_scale if hasattr(model, 'logit_scale') else None,
                    logit_bias=model.logit_bias if hasattr(model, 'logit_bias') else None
                )
                
                # Find best findings
                best_findings, findings_scores, findings_indices = find_best_matches(
                    image_features, findings_features, findings,
                    logit_scale=model.logit_scale if hasattr(model, 'logit_scale') else None,
                    logit_bias=model.logit_bias if hasattr(model, 'logit_bias') else None
                )
                
                # Format report
                report = f"Findings: {best_findings[0]} Impression: {best_impressions[0]}"
                
                # Add to results
                result = {
                    "input_image_name": input_image_name,
                    "report": report
                }
                generated_reports.append(result)
                
                logging.info(f"Processed {input_image_name}: "
                           f"Impression score: {impression_scores[0]:.4f}, "
                           f"Findings score: {findings_scores[0]:.4f}")
                
            except Exception as e:
                logging.error(f"Error processing {img_path}: {str(e)}")
                # Add empty result for failed cases
                result = {
                    "input_image_name": input_image_name,
                    "report": "Error: Failed to process image"
                }
                generated_reports.append(result)
    
    # Create final output
    output = {
        "name": "Generated reports",
        "type": "Report generation",
        "generated_reports": generated_reports,
        "version": {"major": 1, "minor": 0}
    }
    
    return output

def main():
    parser = argparse.ArgumentParser(description="Generate reports for CT volumes")
    parser.add_argument("--checkpoint", type=str, required=True,
                       help="Path to model checkpoint")
    parser.add_argument("--input_dir", type=str, required=True,
                       help="Directory containing npz files")
    parser.add_argument("--impressions_path", type=str, default="models/impression.json",
                       help="Path to impressions JSON file")
    parser.add_argument("--findings_path", type=str, default="models/findings.json",
                       help="Path to findings JSON file")
    parser.add_argument("--impressions_emb", type=str, default=None,
                       help="Path to pre-computed impressions embeddings .pth file (optional)")
    parser.add_argument("--findings_emb", type=str, default=None,
                       help="Path to pre-computed findings embeddings .pth file (optional)")
    parser.add_argument("--output_path", type=str, default="/output/results.json",
                       help="Output path for results JSON")
    parser.add_argument("--device", type=str, default="cuda",
                       help="Device to use for inference")
    parser.add_argument("--text_base", type=str,
                       default="microsoft/LLM2CLIP-Llama-3.2-1B-Instruct-CC-Finetuned",
                       help="Base text model name")
    parser.add_argument("--precision", type=str, default="bf16",
                       choices=["amp", "amp_bf16", "amp_bfloat16", "bf16", "fp16", "fp32"],
                       help="Floating point precision")
    parser.add_argument("--use_3channel", action="store_true",
                       help="Use 3-channel windowing (lung, mediastinum, bone)")
    parser.add_argument("--text_separator", type=str, default="!@#$%^&*()",
                       help="Text separator for LLM2Vec tokenization")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Check if files/directories exist
    if not os.path.exists(args.checkpoint):
        raise FileNotFoundError(f"Checkpoint not found: {args.checkpoint}")
    if not os.path.exists(args.input_dir):
        raise FileNotFoundError(f"Input directory not found: {args.input_dir}")
    
    # Check if at least one source exists for impressions and findings
    if args.impressions_emb is None and not os.path.exists(args.impressions_path):
        raise FileNotFoundError(f"Neither impressions .pth file nor JSON file found: {args.impressions_path}")
    if args.findings_emb is None and not os.path.exists(args.findings_path):
        raise FileNotFoundError(f"Neither findings .pth file nor JSON file found: {args.findings_path}")
    
    # Check if .pth files exist when specified
    if args.impressions_emb is not None and not os.path.exists(args.impressions_emb):
        logging.warning(f"Impressions .pth file not found: {args.impressions_emb}, will fallback to JSON")
        args.impressions_emb = None
    if args.findings_emb is not None and not os.path.exists(args.findings_emb):
        logging.warning(f"Findings .pth file not found: {args.findings_emb}, will fallback to JSON")
        args.findings_emb = None
    
    # Load model
    model = load_model(args.checkpoint, args.text_base, args.device, args.precision)
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.text_base, padding_side="left")
    
    # Generate reports
    results = generate_reports(
        model=model,
        tokenizer=tokenizer,
        input_dir=args.input_dir,
        impressions_path=args.impressions_path,
        findings_path=args.findings_path,
        device=args.device,
        precision=args.precision,
        use_3channel=args.use_3channel,
        separator=args.text_separator,
        impressions_emb=args.impressions_emb,
        findings_emb=args.findings_emb
    )
    
    # Save results
    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    with open(args.output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    logging.info(f"Generated {len(results['generated_reports'])} reports")
    logging.info(f"Results saved to {args.output_path}")

if __name__ == "__main__":
    main() 