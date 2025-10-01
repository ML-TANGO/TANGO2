import random
import re
from dataclasses import dataclass
from multiprocessing import Value
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np
import pandas as pd
import torch
from PIL import Image, ImageFile
from torch.utils.data import Dataset, DataLoader
from torch.utils.data.distributed import DistributedSampler
from .distributed import is_master

# Add MONAI imports (simplified)
try:
    import monai
    from monai.data.dataloader import DataLoader as MonaiDataLoader
    MONAI_AVAILABLE = True
    from training.ct_transform import get_train_transform, get_val_transform
except ImportError:
    MONAI_AVAILABLE = False
    MonaiDataLoader = DataLoader
# -------------------------------------------------

import numbers

# -------- HU window utilities --------
def _hu_window_to_unit(volume: np.ndarray,
                       center: float,
                       width: float) -> np.ndarray:
    """
    Clip a HU volume to the given window and scale to [0,1].
    Args
        volume : raw HU ndarray, shape (D,H,W) or (C,D,H,W)
        center : window centre in HU
        width  : window width in HU
    """
    lower, upper = center - width / 2.0, center + width / 2.0
    vol = np.clip(volume, lower, upper)
    return (vol - lower) / (upper - lower)
    
import warnings
warnings.filterwarnings("ignore")
ImageFile.LOAD_TRUNCATED_IMAGES = True # Truncated File Read
Image.MAX_IMAGE_PIXELS = None # DecompressionBombWarning

def shuffle_sentences(text, probability=0.2):
    # Split the text into sentences using a regex to account for periods that end sentences
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Shuffle the sentences
    if random.random() < probability:
        random.shuffle(sentences)
    
    # Join the shuffled sentences back into a single string
    shuffled_text = ' '.join(sentences)
    return shuffled_text


class CustomCSVDataset(Dataset):
    def __init__(self, csv_file, transform=None, img_key='image_path', caption_key='caption', 
                 tokenizer=None, is_train=True, dataset_mode='cxr', split=None, split_column='split',
                 separator="!@#$%^&*()", use_3channel=False):
        """
        Flexible CSV dataset that supports both CXR temporal data and CT single scan data.
        
        Args:
            csv_file (string): Path to the csv file
            transform (callable, optional): Optional transform to be applied on images
            img_key (string): Column name for image paths
            caption_key (string): Column name for captions/findings
            tokenizer (callable, optional): Optional tokenizer for processing captions
            is_train (bool): Whether this is training data (affects data augmentation)
            dataset_mode (string): 'cxr' for temporal CXR data, 'ct' for single CT scans
            split (string, optional): Data split to filter by (e.g., 'train', 'val', 'test')
            split_column (string): Column name for data splits
        """
        self.data_frame = pd.read_csv(csv_file)
        
        # Filter by split if specified
        if split and split_column in self.data_frame.columns:
            self.data_frame = self.data_frame[self.data_frame[split_column] == split].reset_index(drop=True)
            print(f"Loaded {len(self.data_frame)} samples for {split} split from {csv_file}")
        else:
            print(f"Loaded {len(self.data_frame)} samples from {csv_file}")
        
        self.transform = transform
        self.img_key = img_key
        self.caption_key = caption_key
        self.tokenizer = tokenizer
        self.is_train = is_train
        self.dataset_mode = dataset_mode.lower()
        self.max_length = 512
        self.separator = separator
        self.use_3channel = use_3channel
        
        # Set expected shape for CT error handling
        self.expected_shape = self._get_expected_shape()
        
        # Validate required columns based on dataset mode
        if self.dataset_mode == 'cxr':
            # CXR mode requires temporal columns
            required_cols = ['object_id', 'img_path', 'previous_img_path', 'caption', 'label']
            missing_cols = [col for col in required_cols if col not in self.data_frame.columns]
            if missing_cols:
                print(f"Warning: Missing CXR columns {missing_cols}, will use available columns")
        elif self.dataset_mode == 'ct':
            # CT mode requires single image and findings
            required_cols = [img_key, caption_key]
            missing_cols = [col for col in required_cols if col not in self.data_frame.columns]
            if missing_cols:
                raise ValueError(f"Missing required CT columns: {missing_cols}")
        
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
    
    def __len__(self):
        return len(self.data_frame)
    
    def __getitem__(self, idx):
        """Returns one sample of data"""
        if torch.is_tensor(idx):
            idx = idx.tolist()
            
        row = self.data_frame.iloc[idx]
        
        if self.dataset_mode == 'cxr':
            return self._get_cxr_item(row, idx)
        elif self.dataset_mode == 'ct':
            return self._get_ct_item(row, idx)
        else:
            raise ValueError(f"Unsupported dataset mode: {self.dataset_mode}")
    
    def _get_cxr_item(self, row, idx):
        """Get CXR temporal data item"""
        # Get image paths and caption
        oid = row.get('object_id', f'sample_{idx}')
        cur_path = Path(row['img_path'])
        prev_path = Path(row['previous_img_path'])
        caption = str(row.get('caption', ''))
        hard_caption = ''  # not yet implemented
        label = row.get('label', 0)
        
        if self.is_train:
            caption = shuffle_sentences(caption, probability=0.1)
        
        # Load and process images
        prev_image = Image.open(prev_path)
        cur_image = Image.open(cur_path)
        if self.transform:
            prev_image = self.transform(prev_image)
            cur_image = self.transform(cur_image)
        
        return prev_image, cur_image, caption, hard_caption, oid, label

    def _get_ct_item(self, row, idx):
        """Get CT single scan item with enhanced NPZ loading and validation."""
        img_path = row[self.img_key]
        caption = row[self.caption_key]
        
        # Validate image path
        if pd.isna(img_path) or not isinstance(img_path, str):
            raise ValueError(f"Invalid image path at index {idx}: {img_path}")
        
        img_path_obj = Path(img_path)
        if not img_path_obj.exists():
            raise FileNotFoundError(f"Image file not found: {img_path}")
        
        # Load image from NPZ file (for CT scans)
        try:
            if str(img_path).endswith('.npz'):
                # Load NPZ file (CT scan format)
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
                        if arr.max() <= 1.0:                         # heuristic
                            arr = arr * 2500.0 - 1000.0              # back‑to‑HU

                        if arr.ndim == 4:
                            arr = arr[0]        # assume first channel is full‑range HU

                        # ----------------------------------------------------------
                        # 2.  Generate three standard windows
                        #    lung (centre -600, width 1500)
                        #    mediastinum (centre  40, width  400)
                        #    bone (centre 700, width 2000)
                        # ----------------------------------------------------------
                        lung  = _hu_window_to_unit(arr,  -600, 1000)
                        medi  = _hu_window_to_unit(arr,    40,  400)
                        bone  = _hu_window_to_unit(arr,   700, 1500)

                        multi = np.stack([lung, medi, bone], axis=0)      # (3,D,H,W)
                        image = torch.from_numpy(multi).float()           # torch tensor

                    else:
                    # Convert to tensor with proper dtype
                        image = torch.from_numpy(arr.copy()).float()  # cast to float32 for gradients
                        
                        # Log volume info for debugging (only occasionally to avoid spam)
                    if idx % 100 == 0 and hasattr(self, '_debug_logging'):
                        print(f"Loaded CT volume {idx}: shape={image.shape}, "
                            f"dtype={image.dtype}, range=[{image.min():.2f}, {image.max():.2f}]")
                    
                    # Apply CT-specific transforms if provided
                    if self.transform:
                        try:
                            image = self.transform(image)
                        except Exception as e:
                            raise RuntimeError(f"Transform failed for {img_path}: {e}")
                
            else:
                # Fallback for regular image files (though not typical for CT)
                image = Image.open(img_path_obj)
                if self.transform:
                    image = self.transform(image)
                    
        except Exception as e:
            # Provide more detailed error information
            error_msg = (f"Failed to load image from {img_path} at index {idx}: "
                        f"{type(e).__name__}: {str(e)}")
            if self.is_train:
                # During training, log error but continue with a dummy sample
                print(f"Warning: {error_msg}")
                # Create a zero tensor with expected shape after transforms
                image = torch.zeros(self.expected_shape, dtype=torch.float32)
                caption = "Error loading medical scan"
            else:
                # During validation/testing, raise the error
                raise RuntimeError(error_msg)
        
        # Handle missing or NaN findings
        if pd.isna(caption) or not isinstance(caption, str):
            caption = "Medical scan findings"  # Default placeholder
        
        # Clean and validate caption
        caption = str(caption).strip()
        if len(caption) == 0:
            caption = "Medical scan findings"
        
        # Apply text augmentation for training
        if self.is_train:
            caption = shuffle_sentences(caption, probability=0.4)
        
        # Create metadata (optional, can be useful for debugging)
        meta = {
            "id": img_path_obj.stem,
            "img_path": str(img_path),
            "idx": idx,
            "shape": tuple(image.shape) if isinstance(image, torch.Tensor) else None
        }
        
        # Return format compatible with training
        return image, str(caption)
    
    def collate_fn(self, batch):
        """Collate function that handles both CXR and CT data formats"""
        if self.dataset_mode == 'cxr':
            return self._collate_cxr(batch)
        elif self.dataset_mode == 'ct':
            return self._collate_ct(batch)
    
    def _collate_cxr(self, batch):
        """Collate function for CXR temporal data"""
        prev_images, cur_images, captions, hard_captions, oids, labels = zip(*batch)
        prev_images = torch.stack(prev_images)
        cur_images = torch.stack(cur_images)
        
        if self.tokenizer:
            captions = self.tokenizer(
                captions,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length,
            )
            hard_captions = self.tokenizer(
                hard_captions,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length,
            )
        return prev_images, cur_images, captions, hard_captions, oids, labels
    
    def _collate_ct(self, batch):
        """Collate function for CT single scan data with enhanced error handling."""
        if not batch:
            raise ValueError("Empty batch provided to collate function")
        
        images = []
        captions = []
        
        for i, item in enumerate(batch):
            if len(item) != 2:
                raise ValueError(f"Expected (image, text) tuple, got {len(item)} items at batch index {i}")
            
            image, text = item
            
            # Validate image tensor
            if not isinstance(image, torch.Tensor):
                raise TypeError(f"Expected torch.Tensor for image at batch index {i}, got {type(image)}")
            
            if image.dim() != 4:
                raise ValueError(f"Expected 4D image tensor at batch index {i}, got {image.dim()}D")
            
            # Validate text
            if not isinstance(text, str):
                text = str(text)  # Convert to string if possible
            
            images.append(image)
            captions.append(text)
        
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
        
        # Tokenize texts if tokenizer is provided
        if self.tokenizer:
            try:
                # Handle text with separator and create embed_mask for LLM2Vec
                texts_2 = []
                original_texts = []
                
                for text in captions:
                    t = text.split(self.separator)
                    texts_2.append(t[1] if len(t) > 1 else "")
                    original_texts.append("".join(t))

                original = self.tokenizer(
                    original_texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                )
                
                embed_mask = None
                for t_i, t in enumerate(texts_2):
                    ids = self.tokenizer(
                        [t],
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=self.max_length,
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
                texts = original
                
            except Exception as e:
                raise RuntimeError(f"Failed to tokenize texts: {e}")
        else:
            texts = captions
        
        return images, texts

class SharedEpoch:
    def __init__(self, epoch: int = 0):
        self.shared_epoch = Value('i', epoch)

    def set_value(self, epoch):
        self.shared_epoch.value = epoch

    def get_value(self):
        return self.shared_epoch.value


@dataclass
class DataInfo:
    dataloader: DataLoader
    sampler: Optional[DistributedSampler] = None
    shared_epoch: Optional[SharedEpoch] = None

    def set_epoch(self, epoch):
        if self.shared_epoch is not None:
            self.shared_epoch.set_value(epoch)
        if self.sampler is not None and isinstance(self.sampler, DistributedSampler):
            self.sampler.set_epoch(epoch)


def get_cxr_dataset(args, preprocess_fn, is_train, epoch=0, tokenizer=None):
    input_filename = args.train_data if is_train else args.val_data
    assert input_filename
    dataset = CustomCSVDataset(
        csv_file=input_filename,
        transform=preprocess_fn,
        img_key=args.csv_img_key,
        caption_key=args.csv_caption_key,
        tokenizer=tokenizer,
        is_train=is_train)
    
    num_samples = len(dataset)
    sampler = DistributedSampler(dataset) if args.distributed and is_train else None
    shuffle = is_train and sampler is None

    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=shuffle,
        num_workers=args.workers,
        pin_memory=True,
        sampler=sampler,
        drop_last=is_train,
        collate_fn=dataset.collate_fn
    )
    dataloader.num_samples = num_samples
    dataloader.num_batches = len(dataloader)

    return DataInfo(dataloader, sampler)


def get_retrieval_dataset(args, preprocess_fn, is_train=False, tokenizer=None,
                          input_filename=None, dataset_mode='cxr'):
    # input_filename = args.train_data if is_train else args.val_data
    assert input_filename
    
    # Set up parameters based on dataset mode
    if dataset_mode == 'ct':
        # CT mode parameters
        split = getattr(args, 'train_split', 'train') if is_train else getattr(args, 'val_split', 'val')
        img_key = getattr(args, 'csv_img_key', 'img_path')
        caption_key = getattr(args, 'csv_caption_key', 'findings')
        split_column = getattr(args, 'split_column', 'split')
        separator = getattr(args, 'text_separator', '!@#$%^&*()')
        use_3channel = getattr(args, 'use_3channel', False)
    else:
        # CXR mode parameters (default)
        split = None
        split_column = 'split'
        img_key = args.csv_img_key
        caption_key = args.csv_caption_key
        separator = getattr(args, 'text_separator', '!@#$%^&*()')
        use_3channel = False
    
    dataset = CustomCSVDataset(
        csv_file=input_filename,
        transform=preprocess_fn,
        img_key=img_key,
        caption_key=caption_key,
        tokenizer=tokenizer,
        is_train=is_train,
        dataset_mode=dataset_mode,
        split=split,
        split_column=split_column,
        separator=separator,
        use_3channel=use_3channel)
    
    num_samples = len(dataset)
    sampler = DistributedSampler(dataset) if args.distributed and is_train else None
    shuffle = is_train and sampler is None

    dataloader = DataLoader(
        dataset,
        batch_size=args.eval_batch_size,
        shuffle=shuffle,
        num_workers=args.workers,
        pin_memory=True,
        sampler=sampler,
        drop_last=is_train,
        collate_fn=dataset.collate_fn
    )
    dataloader.num_samples = num_samples
    dataloader.num_batches = len(dataloader)

    return DataInfo(dataloader, sampler)

def get_ct_dataset(args, preprocess_fn, is_train, epoch=0, tokenizer=None):
    """Get CT dataset with proper transforms and collation."""
    input_filename = args.train_data if is_train else args.val_data
    assert input_filename
    
    # Set up parameters for CT mode
    split = getattr(args, 'train_split', 'train') if is_train else getattr(args, 'val_split', 'val')
    img_key = getattr(args, 'csv_img_key', 'img_path')
    caption_key = getattr(args, 'csv_caption_key', 'findings')
    split_column = getattr(args, 'split_column', 'split')
    separator = getattr(args, 'text_separator', '!@#$%^&*()')
    use_3channel = getattr(args, 'use_3channel', False)
    
    dataset = CustomCSVDataset(
        csv_file=input_filename,
        transform=preprocess_fn,
        img_key=img_key,
        caption_key=caption_key,
        tokenizer=tokenizer,
        is_train=is_train,
        dataset_mode='ct',
        split=split,
        split_column=split_column,
        separator=separator,
        use_3channel=use_3channel)
    
    num_samples = len(dataset)
    sampler = DistributedSampler(dataset) if args.distributed and is_train else None
    shuffle = is_train and sampler is None

    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=shuffle,
        num_workers=args.workers,
        pin_memory=True,
        sampler=sampler,
        drop_last=is_train,
        collate_fn=dataset.collate_fn
    )
    dataloader.num_samples = num_samples
    dataloader.num_batches = len(dataloader)

    return DataInfo(dataloader, sampler)

def get_dataset_fn(data_path, dataset_type):
    if dataset_type == "cxr":
        return get_cxr_dataset
    elif dataset_type == "ct":
        return get_ct_dataset
    else:
        raise ValueError(f"Unsupported dataset type: {dataset_type}")

def get_data(args, preprocess_fns, epoch=0, tokenizer=None):
    preprocess_train, preprocess_val = preprocess_fns ##TODO: Modify this
    data = {}

    if args.train_data or args.dataset_type in ["cxr", "ct"]:
        data["train"] = get_dataset_fn(args.train_data, args.dataset_type)(
            args, preprocess_train, is_train=True, epoch=epoch, tokenizer=tokenizer)

    if args.val_data:
        data["val"] = get_dataset_fn(args.val_data, args.dataset_type)(
            args, preprocess_val, is_train=False, tokenizer=tokenizer)

    return data



