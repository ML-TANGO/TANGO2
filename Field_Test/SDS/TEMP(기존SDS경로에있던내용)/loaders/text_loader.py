#!/usr/bin/env python3
"""
Text loader module that handles loading and processing of medical text data.
Extracted from the main dataset class to provide modular text loading functionality.
"""

import random
import re
import pandas as pd
import torch
from typing import List, Dict, Optional, Union


def shuffle_sentences(text: str, probability: float = 0.2) -> str:
    """
    Shuffle sentences in text for data augmentation.
    
    Args:
        text: Input text string
        probability: Probability of shuffling sentences
        
    Returns:
        str: Text with possibly shuffled sentences
    """
    # Split the text into sentences using a regex to account for periods that end sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Shuffle the sentences with given probability
    if random.random() < probability:
        random.shuffle(sentences)
    
    # Join the shuffled sentences back into a single string
    shuffled_text = ' '.join(sentences)
    return shuffled_text


class TextLoader:
    """
    Modular text loader that handles medical text processing, tokenization, and augmentation.
    Provides the same text processing tactics as the original dataset.
    """
    
    def __init__(self, tokenizer=None, is_train=True, max_length=512, 
                 separator="!@#$%^&*()", augment_probability=0.4):
        """
        Initialize the text loader.
        
        Args:
            tokenizer: HuggingFace tokenizer for text processing
            is_train: Whether this is training data (affects augmentation)
            max_length: Maximum sequence length for tokenization
            separator: Separator used for LLM2Vec embed_mask creation
            augment_probability: Probability of applying text augmentation
        """
        self.tokenizer = tokenizer
        self.is_train = is_train
        self.max_length = max_length
        self.separator = separator
        self.augment_probability = augment_probability
    
    def clean_and_validate_text(self, text: Union[str, pd.Series], default_text: str = "Medical scan findings") -> str:
        """
        Clean and validate text input.
        
        Args:
            text: Input text (string or pandas Series)
            default_text: Default text to use if input is invalid
            
        Returns:
            str: Cleaned and validated text
        """
        # Handle missing or NaN text
        if pd.isna(text) or not isinstance(text, str):
            return default_text
        
        # Clean and validate text
        text = str(text).strip()
        if len(text) == 0:
            return default_text
        
        return text
    
    def augment_text(self, text: str) -> str:
        """
        Apply text augmentation (sentence shuffling) during training.
        
        Args:
            text: Input text string
            
        Returns:
            str: Possibly augmented text
        """
        if self.is_train:
            return shuffle_sentences(text, probability=self.augment_probability)
        return text
    
    def process_text(self, text: Union[str, pd.Series], apply_augmentation: bool = True) -> str:
        """
        Process a single text: clean, validate, and optionally augment.
        
        Args:
            text: Input text
            apply_augmentation: Whether to apply augmentation
            
        Returns:
            str: Processed text
        """
        # Clean and validate
        text = self.clean_and_validate_text(text)
        
        # Apply augmentation if requested and in training mode
        if apply_augmentation:
            text = self.augment_text(text)
        
        return text
    
    def process_batch(self, texts: List[Union[str, pd.Series]], apply_augmentation: bool = True) -> List[str]:
        """
        Process a batch of texts.
        
        Args:
            texts: List of input texts
            apply_augmentation: Whether to apply augmentation
            
        Returns:
            List[str]: List of processed texts
        """
        processed_texts = []
        for text in texts:
            processed_text = self.process_text(text, apply_augmentation)
            processed_texts.append(processed_text)
        
        return processed_texts
    
    def tokenize_texts(self, texts: List[str]) -> Dict[str, torch.Tensor]:
        """
        Tokenize a list of texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            Dict: Tokenized texts with attention masks
        """
        if self.tokenizer is None:
            raise ValueError("Tokenizer not provided for text tokenization")
        
        try:
            tokenized = self.tokenizer(
                texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length,
            )
            return tokenized
        except Exception as e:
            raise RuntimeError(f"Failed to tokenize texts: {e}")
    
    def create_embed_mask_batch(self, texts: List[str]) -> Dict[str, torch.Tensor]:
        """
        Create tokenized texts with embed_mask for LLM2Vec processing.
        This follows the same logic as the original collate function.
        
        Args:
            texts: List of text strings containing separator
            
        Returns:
            Dict: Tokenized texts with embed_mask
        """
        if self.tokenizer is None:
            raise ValueError("Tokenizer not provided for embed mask creation")
        
        try:
            # Handle text with separator and create embed_mask for LLM2Vec
            texts_2 = []
            original_texts = []
            
            for text in texts:
                t = text.split(self.separator)
                texts_2.append(t[1] if len(t) > 1 else "")
                original_texts.append("".join(t))

            # Tokenize original texts
            original = self.tokenizer(
                original_texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length,
            )
            
            # Create embed mask
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
            return original
            
        except Exception as e:
            raise RuntimeError(f"Failed to create embed mask batch: {e}")
    
    def load_text(self, text: Union[str, pd.Series], apply_augmentation: bool = True) -> str:
        """
        Load and process a single text entry.
        
        Args:
            text: Input text
            apply_augmentation: Whether to apply augmentation
            
        Returns:
            str: Processed text
        """
        return self.process_text(text, apply_augmentation)
    
    def load_batch(self, texts: List[Union[str, pd.Series]], 
                   tokenize: bool = True, create_embed_mask: bool = False,
                   apply_augmentation: bool = True) -> Union[List[str], Dict[str, torch.Tensor]]:
        """
        Load and process a batch of texts with optional tokenization.
        
        Args:
            texts: List of input texts
            tokenize: Whether to tokenize the texts
            create_embed_mask: Whether to create embed_mask for LLM2Vec
            apply_augmentation: Whether to apply augmentation
            
        Returns:
            Union[List[str], Dict]: Processed texts or tokenized batch
        """
        # Process all texts
        processed_texts = self.process_batch(texts, apply_augmentation)
        
        if not tokenize:
            return processed_texts
        
        if create_embed_mask:
            return self.create_embed_mask_batch(processed_texts)
        else:
            return self.tokenize_texts(processed_texts)
    
    def get_text_stats(self, texts: List[str]) -> Dict[str, float]:
        """
        Get statistics about a batch of texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            Dict: Text statistics
        """
        if not texts:
            return {}
        
        lengths = [len(text.split()) for text in texts]
        char_lengths = [len(text) for text in texts]
        
        stats = {
            "num_texts": len(texts),
            "avg_word_length": sum(lengths) / len(lengths),
            "max_word_length": max(lengths),
            "min_word_length": min(lengths),
            "avg_char_length": sum(char_lengths) / len(char_lengths),
            "max_char_length": max(char_lengths),
            "min_char_length": min(char_lengths),
        }
        
        return stats
    
    def validate_batch(self, texts: List[str]) -> Dict[str, bool]:
        """
        Validate a batch of texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            Dict: Validation results
        """
        validation_results = {
            "all_strings": all(isinstance(text, str) for text in texts),
            "no_empty": all(len(text.strip()) > 0 for text in texts),
            "reasonable_length": all(len(text) < 10000 for text in texts),  # Reasonable upper bound
            "no_null": all(text is not None for text in texts)
        }
        
        validation_results["valid"] = all(validation_results.values())
        
        return validation_results 