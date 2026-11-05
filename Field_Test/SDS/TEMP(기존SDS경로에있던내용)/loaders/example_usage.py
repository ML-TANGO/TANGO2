#!/usr/bin/env python3
"""
Example usage of the modular ImageLoader and TextLoader classes.
Demonstrates how to use the same tactics as the original dataloader in a modular way.
"""

import os
import sys
import pandas as pd
import torch
from pathlib import Path
from transformers import AutoTokenizer

# Add the parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from report_gen.loaders import ImageLoader, TextLoader

# Try to import transforms, use None if not available
try:
    from report_gen.training.ct_transform import get_val_transform
except ImportError:
    def get_val_transform():
        print("CT transforms not available, using None")
        return None


def example_ct_processing():
    """Example of processing CT data using separate loaders."""
    print("=== CT Data Processing Example ===")
    
    # Initialize transforms
    transform = get_val_transform()
    
    # Initialize image loader for CT data
    image_loader = ImageLoader(
        transform=transform,
        use_3channel=True,  # Use 3-channel HU windowing
        is_train=False,     # Validation mode
        dataset_mode='ct'
    )
    
    # Initialize text loader
    tokenizer = AutoTokenizer.from_pretrained("microsoft/LLM2CLIP-Llama-3.2-1B-Instruct-CC-Finetuned")
    text_loader = TextLoader(
        tokenizer=tokenizer,
        is_train=False,     # Validation mode
        max_length=512,
        separator="!@#$%^&*()",
        augment_probability=0.0  # No augmentation in validation
    )
    
    # Example data (replace with your actual data)
    sample_data = {
        'img_path': [
            '/path/to/ct_scan_1.npz',
            '/path/to/ct_scan_2.npz'
        ],
        'findings': [
            'Normal CT scan of the chest. No acute findings.',
            'Bilateral lower lobe opacities consistent with pneumonia.'
        ]
    }
    
    print(f"Processing {len(sample_data['img_path'])} samples...")
    
    # Process images and texts separately
    images = []
    texts = []
    
    for i, (img_path, finding) in enumerate(zip(sample_data['img_path'], sample_data['findings'])):
        try:
            # Load and process image
            if Path(img_path).exists():  # Only process if file exists
                image = image_loader.load_image(img_path, idx=i)
                images.append(image)
                print(f"✓ Loaded image {i}: shape={image.shape}")
            else:
                print(f"✗ Image file not found: {img_path}")
                continue
            
            # Process text
            processed_text = text_loader.process_text(finding, apply_augmentation=False)
            texts.append(processed_text)
            print(f"✓ Processed text {i}: '{processed_text[:50]}...'")
            
        except Exception as e:
            print(f"✗ Error processing sample {i}: {e}")
    
    if images and texts:
        # Batch processing
        try:
            # Stack images into batch
            if len(images) > 1:
                image_batch = image_loader.load_batch(
                    sample_data['img_path'][:len(images)], 
                    indices=list(range(len(images)))
                )
                print(f"✓ Created image batch: shape={image_batch.shape}")
            else:
                image_batch = images[0].unsqueeze(0)
                print(f"✓ Single image batch: shape={image_batch.shape}")
            
            # Tokenize texts
            tokenized_texts = text_loader.load_batch(
                texts, 
                tokenize=True, 
                create_embed_mask=False,
                apply_augmentation=False
            )
            print(f"✓ Tokenized texts: input_ids shape={tokenized_texts['input_ids'].shape}")
            
            # Get text statistics
            text_stats = text_loader.get_text_stats(texts)
            print(f"✓ Text statistics: {text_stats}")
            
        except Exception as e:
            print(f"✗ Error in batch processing: {e}")
    
    print("CT processing example completed.\n")


def example_training_augmentation():
    """Example of training mode with data augmentation."""
    print("=== Training Mode with Augmentation Example ===")
    
    # Initialize loaders for training
    image_loader = ImageLoader(
        transform=None,  # Add your training transforms here
        use_3channel=False,
        is_train=True,   # Training mode
        dataset_mode='ct'
    )
    
    text_loader = TextLoader(
        tokenizer=None,  # No tokenizer for this example
        is_train=True,   # Training mode
        augment_probability=0.4  # 40% chance of sentence shuffling
    )
    
    # Example training texts
    training_texts = [
        "The patient presents with chest pain. No acute abnormalities detected. Follow-up recommended.",
        "Bilateral pneumonia identified. Consolidation in both lower lobes. Treatment initiated.",
        "Normal chest CT. Clear lung fields. No pathological findings observed."
    ]
    
    print("Original texts:")
    for i, text in enumerate(training_texts):
        print(f"  {i}: {text}")
    
    print("\nAugmented texts (multiple runs to show randomness):")
    for run in range(3):
        print(f"\nRun {run + 1}:")
        augmented_texts = text_loader.process_batch(training_texts, apply_augmentation=True)
        for i, text in enumerate(augmented_texts):
            print(f"  {i}: {text}")
    
    # Validate processed texts
    validation_results = text_loader.validate_batch(training_texts)
    print(f"\nText validation results: {validation_results}")
    
    print("Training augmentation example completed.\n")


def example_embed_mask_creation():
    """Example of creating embed masks for LLM2Vec."""
    print("=== Embed Mask Creation Example ===")
    
    # Initialize tokenizer and text loader
    tokenizer = AutoTokenizer.from_pretrained("microsoft/LLM2CLIP-Llama-3.2-1B-Instruct-CC-Finetuned")
    text_loader = TextLoader(
        tokenizer=tokenizer,
        is_train=False,
        separator="!@#$%^&*()"
    )
    
    # Example texts with separator for LLM2Vec
    separator = "!@#$%^&*()"
    texts_with_separator = [
        f"Chest CT scan shows{separator}normal lung parenchyma",
        f"Medical imaging reveals{separator}bilateral infiltrates consistent with infection"
    ]
    
    print("Texts with separator:")
    for i, text in enumerate(texts_with_separator):
        print(f"  {i}: {text}")
    
    try:
        # Create embed masks
        tokenized_with_mask = text_loader.create_embed_mask_batch(texts_with_separator)
        
        print(f"\nTokenized output shapes:")
        for key, value in tokenized_with_mask.items():
            if isinstance(value, torch.Tensor):
                print(f"  {key}: {value.shape}")
        
        print(f"\nEmbed mask sample:")
        print(f"  First sample embed_mask: {tokenized_with_mask['embed_mask'][0]}")
        
    except Exception as e:
        print(f"✗ Error creating embed masks: {e}")
    
    print("Embed mask creation example completed.\n")


def example_image_info():
    """Example of getting image metadata without loading."""
    print("=== Image Information Example ===")
    
    image_loader = ImageLoader()
    
    # Example paths (replace with actual paths)
    sample_paths = [
        '/path/to/sample1.npz',
        '/path/to/sample2.jpg',
        '/path/to/nonexistent.npz'
    ]
    
    for path in sample_paths:
        info = image_loader.get_image_info(path)
        print(f"\nPath: {path}")
        print(f"Info: {info}")
    
    print("Image information example completed.\n")


def main():
    """Run all examples."""
    print("Starting modular loader examples...\n")
    
    # Comment out examples that require actual data files
    # example_ct_processing()
    example_training_augmentation()
    example_embed_mask_creation()
    example_image_info()
    
    print("All examples completed!")


if __name__ == "__main__":
    main() 