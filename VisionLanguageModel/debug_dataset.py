import torch
import transformers
from llava_custom.data.dataset import LazySupervisedDataset, DataCollatorForSupervisedDataset
from llava_custom.constants import IMAGE_TOKEN_INDEX

def debug():
    model_path = "/home/ywlee/HDD/HuggingFace/Llama-3.1-8B-Instruct"
    data_path = "/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/chat.json"
    image_folder = "/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/images"
    
    tokenizer = transformers.AutoTokenizer.from_pretrained(model_path, use_fast=False)
    
    class Args:
        def __init__(self):
            self.image_folder = image_folder
            from transformers import CLIPImageProcessor
            self.image_processor = CLIPImageProcessor.from_pretrained("openai/clip-vit-large-patch14-336")

    data_args = Args()
    dataset = LazySupervisedDataset(data_path, tokenizer, data_args)
    
    print(f"Dataset length: {len(dataset)}")
    
    for i in range(5):
        sample = dataset[i]
        input_ids = sample['input_ids']
        labels = sample['labels']
        
        print(f"Sample {i}:")
        print(f"  Input IDs max: {input_ids.max()}, min: {input_ids.min()}")
        print(f"  Labels max: {labels.max()}, min: {labels.min()}")
        print(f"  Has image: {'image' in sample}")
        
        if input_ids.max() >= 128256:
            print(f"  !!! ERROR: Input ID {input_ids.max()} >= 128256")
        
        # Check for any negative values other than -200
        neg_indices = input_ids[input_ids < 0]
        for val in neg_indices:
            if val != IMAGE_TOKEN_INDEX:
                print(f"  !!! ERROR: Unexpected negative index {val}")

if __name__ == "__main__":
    debug()
