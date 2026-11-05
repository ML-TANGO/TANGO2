#!/usr/bin/env python3
"""
Image loader module that handles loading of medical images (CT NPZ files and CXR images).
Extracted from the main dataset class to provide modular image loading functionality.
"""

import numpy as np
import torch
from PIL import Image, ImageFile
from pathlib import Path
import pandas as pd
import warnings

# Suppress warnings and handle truncated images
warnings.filterwarnings("ignore")
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

def _hu_window_to_unit(volume: np.ndarray, center: float, width: float) -> np.ndarray:
    """
    Clip a HU volume to the given window and scale to [0,1].
    Args:
        volume: raw HU ndarray, shape (D,H,W) or (C,D,H,W)
        center: window centre in HU
        width: window width in HU
    """
    lower, upper = center - width / 2.0, center + width / 2.0
    vol = np.clip(volume, lower, upper)
    return (vol - lower) / (upper - lower)


class ImageLoader:
    """
    Modular image loader that handles both CT (NPZ) and CXR (regular image) formats.
    Provides the same error handling and validation tactics as the original dataset.
    """
    
    def __init__(self, transform=None, use_3channel=False, is_train=True, dataset_mode='ct'):
        """
        Initialize the image loader.
        
        Args:
            transform: Optional transform to be applied on images
            use_3channel: Whether to use 3-channel CT data with HU windowing
            is_train: Whether this is training data (affects error handling)
            dataset_mode: 'ct' for CT scans, 'cxr' for chest X-rays
        """
        self.transform = transform
        self.use_3channel = use_3channel
        self.is_train = is_train
        self.dataset_mode = dataset_mode.lower()
        
        # Set expected shape for error handling
        self.expected_shape = self._get_expected_shape()
        
    def _get_expected_shape(self):
        """Get the expected shape after transforms for CT data."""
        if self.use_3channel:
            # 3-channel mode: (3, D, H, W)
            if self.transform and hasattr(self.transform, 'target_size'):
                return (3, *self.transform.target_size)
            elif self.transform and hasattr(self.transform, 'spatial_size'):
                return (3, *self.transform.spatial_size)
            else:
                return (3, 160, 224, 224)
        else:
            # Single channel mode: (1, D, H, W)
            if self.transform and hasattr(self.transform, 'target_size'):
                return (1, *self.transform.target_size)
            elif self.transform and hasattr(self.transform, 'spatial_size'):
                return (1, *self.transform.spatial_size)
            else:
                return (1, 160, 224, 224)
    
    def load_image(self, img_path, idx=None):
        """
        Load a single image from the given path.
        
        Args:
            img_path: Path to the image file
            idx: Optional index for debugging/logging
            
        Returns:
            torch.Tensor: Loaded and transformed image
        """
        # Validate image path
        if pd.isna(img_path) or not isinstance(img_path, str):
            raise ValueError(f"Invalid image path at index {idx}: {img_path}")
        
        img_path_obj = Path(img_path)
        if not img_path_obj.exists():
            raise FileNotFoundError(f"Image file not found: {img_path}")
        
        try:
            if str(img_path).endswith('.npz'):
                # Load NPZ file (CT scan format)
                image = self._load_npz_image(img_path, idx)
            else:
                # Load regular image file (CXR format)
                image = self._load_regular_image(img_path, idx)
                
        except Exception as e:
            # Provide detailed error information
            error_msg = (f"Failed to load image from {img_path} at index {idx}: "
                        f"{type(e).__name__}: {str(e)}")
            
            if self.is_train:
                # During training, log error but continue with a dummy sample
                print(f"Warning: {error_msg}")
                # Create a zero tensor with expected shape after transforms
                image = torch.zeros(self.expected_shape, dtype=torch.float32)
            else:
                # During validation/testing, raise the error
                raise RuntimeError(error_msg)
        
        return image
    
    def _load_npz_image(self, img_path, idx=None):
        """Load image from NPZ file (CT scan format)."""
        # Expected format: (C, D, H, W) where C>=1 (HU windows)
        with np.load(img_path) as npz_file:
            if "image" not in npz_file:
                raise KeyError(f"'image' key not found in NPZ file: {img_path}")
            
            arr = npz_file["image"]  # (C, H, W, D) float16/32
            
            # Validate array shape
            if arr.ndim != 4:
                raise ValueError(f"Expected 4D array (C, H, W, D), got {arr.ndim}D in {img_path}")
            
            if arr.shape[0] < 1:
                raise ValueError(f"Expected at least 1 channel, got {arr.shape[0]} in {img_path}")

            if self.use_3channel:
                if arr.max() <= 1.0:  # heuristic
                    arr = arr * 2500.0 - 1000.0  # back-to-HU

                if arr.ndim == 4:
                    arr = arr[0]  # assume first channel is full-range HU

                # Generate three standard windows
                # lung (centre -600, width 1000)
                # mediastinum (centre 40, width 400)  
                # bone (centre 700, width 1500)
                lung = _hu_window_to_unit(arr, -600, 1000)
                medi = _hu_window_to_unit(arr, 40, 400)
                bone = _hu_window_to_unit(arr, 700, 1500)

                multi = np.stack([lung, medi, bone], axis=0)  # (3,D,H,W)
                image = torch.from_numpy(multi).float()  # torch tensor

            else:
                # Convert to tensor with proper dtype
                image = torch.from_numpy(arr.copy()).float()  # cast to float32 for gradients
            
            # Log volume info for debugging (only occasionally to avoid spam)
            if idx is not None and idx % 100 == 0:
                print(f"Loaded CT volume {idx}: shape={image.shape}, "
                      f"dtype={image.dtype}, range=[{image.min():.2f}, {image.max():.2f}]")
            
            # Apply CT-specific transforms if provided
            if self.transform:
                try:
                    image = self.transform(image)
                except Exception as e:
                    raise RuntimeError(f"Transform failed for {img_path}: {e}")
        
        return image
    
    def _load_regular_image(self, img_path, idx=None):
        """Load regular image file (CXR format)."""
        image = Image.open(img_path)
        
        if self.transform:
            image = self.transform(image)
        
        return image
    
    def load_batch(self, img_paths, indices=None):
        """
        Load a batch of images.
        
        Args:
            img_paths: List of image paths
            indices: Optional list of indices for debugging
            
        Returns:
            torch.Tensor: Batch of loaded images
        """
        if indices is None:
            indices = list(range(len(img_paths)))
        
        images = []
        for i, (img_path, idx) in enumerate(zip(img_paths, indices)):
            image = self.load_image(img_path, idx)
            images.append(image)
        
        # Check for shape consistency before stacking
        shapes = [img.shape for img in images]
        unique_shapes = set(shapes)
        
        if len(unique_shapes) > 1:
            # Find the most common shape and use it as target
            from collections import Counter
            shape_counts = Counter(shapes)
            target_shape = shape_counts.most_common(1)[0][0]
            
            # Resize mismatched tensors to target shape
            resized_images = []
            for i, (img, shape) in enumerate(zip(images, shapes)):
                if shape != target_shape:
                    print(f"Warning: Resizing tensor {i} from {shape} to {target_shape}")
                    # Use interpolation to resize the tensor
                    if img.dim() == 4:  # (C, D, H, W)
                        resized_img = torch.nn.functional.interpolate(
                            img.unsqueeze(0),  # Add batch dimension
                            size=target_shape[1:],  # (D, H, W)
                            mode='trilinear',
                            align_corners=False
                        ).squeeze(0)  # Remove batch dimension
                    else:
                        resized_img = img
                    resized_images.append(resized_img)
                else:
                    resized_images.append(img)
            images = resized_images
        
        # Stack images with error handling
        try:
            images = torch.stack(images)
        except Exception as e:
            # Provide detailed information about tensor shapes for debugging
            shapes = [img.shape for img in images]
            raise RuntimeError(f"Failed to stack images. Shapes: {shapes}. Error: {e}")
        
        return images
    
    def get_image_info(self, img_path):
        """
        Get metadata about an image without fully loading it.
        
        Args:
            img_path: Path to the image file
            
        Returns:
            dict: Image metadata
        """
        img_path_obj = Path(img_path)
        info = {
            "path": str(img_path),
            "exists": img_path_obj.exists(),
            "filename": img_path_obj.name,
            "stem": img_path_obj.stem,
            "extension": img_path_obj.suffix,
            "is_npz": str(img_path).endswith('.npz')
        }
        
        if info["exists"] and info["is_npz"]:
            try:
                with np.load(img_path) as npz_file:
                    if "image" in npz_file:
                        arr = npz_file["image"]
                        info.update({
                            "shape": arr.shape,
                            "dtype": str(arr.dtype),
                            "size_mb": arr.nbytes / (1024 * 1024),
                            "has_image_key": True
                        })
                    else:
                        info.update({
                            "has_image_key": False,
                            "available_keys": list(npz_file.keys())
                        })
            except Exception as e:
                info["load_error"] = str(e)
        
        return info 