# Modular Medical Data Loaders

This package provides separate, modular loaders for medical imaging and text data, extracted from the original monolithic `CustomCSVDataset` class. The modular approach offers better code organization, reusability, and testing capabilities.

## Overview

The loaders package contains:

- **`ImageLoader`**: Handles loading and processing of medical images (CT NPZ files and CXR images)
- **`TextLoader`**: Handles text processing, tokenization, and augmentation
- **`example_usage.py`**: Comprehensive examples showing how to use both loaders

## Key Features

### ImageLoader
- ✅ **NPZ file support**: Loads CT scans from NPZ files with proper validation
- ✅ **3-channel HU windowing**: Generates lung, mediastinum, and bone windows for CT data
- ✅ **Error handling**: Robust error handling with fallback mechanisms during training
- ✅ **Transform support**: Applies medical image transforms (MONAI-based)
- ✅ **Batch processing**: Handles shape mismatches and tensor stacking
- ✅ **Metadata extraction**: Get image info without full loading

### TextLoader
- ✅ **Text validation**: Cleans and validates medical text data
- ✅ **Sentence shuffling**: Data augmentation through sentence reordering
- ✅ **Tokenization**: HuggingFace tokenizer integration
- ✅ **LLM2Vec support**: Creates embed masks for LLM2Vec processing
- ✅ **Batch processing**: Efficient batch text processing
- ✅ **Statistics**: Text statistics and validation

## Installation

```python
# Import the loaders
from report_gen.loaders import ImageLoader, TextLoader
```

## Quick Start

### Basic Image Loading

```python
from report_gen.loaders import ImageLoader
from training.ct_transform import get_val_transform

# Initialize image loader
image_loader = ImageLoader(
    transform=get_val_transform(),
    use_3channel=True,  # Use HU windowing for CT
    is_train=False,
    dataset_mode='ct'
)

# Load a single image
image = image_loader.load_image('/path/to/ct_scan.npz')
print(f"Loaded image shape: {image.shape}")

# Load a batch of images
images = image_loader.load_batch([
    '/path/to/scan1.npz',
    '/path/to/scan2.npz'
])
print(f"Batch shape: {images.shape}")
```

### Basic Text Processing

```python
from report_gen.loaders import TextLoader
from transformers import AutoTokenizer

# Initialize text loader
tokenizer = AutoTokenizer.from_pretrained("microsoft/LLM2CLIP-Llama-3.2-1B-Instruct-CC-Finetuned")
text_loader = TextLoader(
    tokenizer=tokenizer,
    is_train=True,  # Enable augmentation
    augment_probability=0.4
)

# Process a single text
processed_text = text_loader.process_text("Normal chest CT. No abnormalities detected.")

# Process and tokenize a batch
texts = [
    "Normal chest CT findings.",
    "Bilateral pneumonia present."
]
tokenized = text_loader.load_batch(texts, tokenize=True)
print(f"Tokenized shape: {tokenized['input_ids'].shape}")
```

## Advanced Usage

### CT Data with 3-Channel HU Windowing

```python
# Enable 3-channel mode for CT data
image_loader = ImageLoader(
    transform=transform,
    use_3channel=True,  # Creates lung, mediastinum, bone windows
    dataset_mode='ct'
)

# The loader automatically creates 3 channels:
# - Channel 0: Lung window (center: -600, width: 1000)
# - Channel 1: Mediastinum window (center: 40, width: 400)  
# - Channel 2: Bone window (center: 700, width: 1500)
```

### LLM2Vec Embed Mask Creation

```python
# For LLM2Vec processing with embed masks
text_loader = TextLoader(
    tokenizer=tokenizer,
    separator="!@#$%^&*()"
)

texts_with_separator = [
    "Chest CT shows!@#$%^&*()normal lung parenchyma",
    "Findings include!@#$%^&*()bilateral infiltrates"
]

tokenized_with_mask = text_loader.create_embed_mask_batch(texts_with_separator)
# Returns: {'input_ids': ..., 'attention_mask': ..., 'embed_mask': ...}
```

### Training vs. Validation Mode

```python
# Training mode: enables augmentation and error tolerance
train_image_loader = ImageLoader(is_train=True, dataset_mode='ct')
train_text_loader = TextLoader(is_train=True, augment_probability=0.4)

# Validation mode: strict error handling, no augmentation
val_image_loader = ImageLoader(is_train=False, dataset_mode='ct')
val_text_loader = TextLoader(is_train=False, augment_probability=0.0)
```

## Benefits Over Original Dataset

### Modularity
- **Separation of concerns**: Image and text processing are independent
- **Reusability**: Use loaders in different contexts (training, inference, analysis)
- **Testing**: Easier to unit test individual components

### Flexibility
- **Mix and match**: Use different loaders for different data types
- **Configuration**: Fine-tune each loader independently
- **Extensibility**: Easy to add new features to specific loaders

### Performance
- **Memory efficiency**: Load only what you need when you need it
- **Parallel processing**: Process images and texts independently
- **Caching**: Potential for loader-specific caching strategies

## Migration from Original Dataset

### Before (Monolithic)
```python
dataset = CustomCSVDataset(
    csv_file='data.csv',
    transform=transform,
    tokenizer=tokenizer,
    is_train=True,
    dataset_mode='ct'
)

# Everything coupled together
image, text = dataset[0]
```

### After (Modular)
```python
image_loader = ImageLoader(transform=transform, is_train=True)
text_loader = TextLoader(tokenizer=tokenizer, is_train=True)

# Independent processing
image = image_loader.load_image(img_path)
text = text_loader.process_text(caption)

# Or batch processing
images = image_loader.load_batch(img_paths)
texts = text_loader.load_batch(captions, tokenize=True)
```

## Error Handling

Both loaders implement the same robust error handling as the original dataset:

- **Training mode**: Logs errors and provides fallback data to continue training
- **Validation mode**: Raises exceptions to catch data issues early
- **Detailed error messages**: Include file paths, indices, and error context

## Examples

See `example_usage.py` for comprehensive examples including:
- CT data processing with 3-channel windowing
- Training mode with text augmentation
- LLM2Vec embed mask creation
- Image metadata extraction
- Error handling demonstrations

## Future Enhancements

Potential improvements for the modular loaders:
- **Caching mechanisms**: Cache processed images/texts for repeated access
- **Async loading**: Asynchronous data loading for better performance
- **Data validation**: More comprehensive data validation and statistics
- **Format support**: Additional medical imaging formats (DICOM, NIfTI)
- **Augmentation pipeline**: More sophisticated augmentation strategies 