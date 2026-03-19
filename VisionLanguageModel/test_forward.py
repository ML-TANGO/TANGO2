import os
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"

import torch
from transformers import AutoTokenizer
from llava_custom.model.builder import load_pretrained_model
from llava_custom.data.dataset import LazySupervisedDataset, DataCollatorForSupervisedDataset

def test():
    model_path = "/home/ywlee/Llama-3.1-8B-Instruct"
    print("Loading model...")
    tokenizer, model = load_pretrained_model(
        model_path, None, False, torch_dtype=torch.bfloat16, attn_implementation="flash_attention_2"
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        
    model.config.vocab_size = len(tokenizer)
    class ModelArgs:
        mm_vision_tower = "openai/clip-vit-large-patch14-336"
        mm_projector_type = "mlp2x_gelu"
        mm_vision_select_layer = -2
        tune_mm_mlp_adapter = True
        freeze_backbone = True

    model.get_model().initialize_vision_modules(
        model_args=ModelArgs()
    )
    
    model.to("cuda", dtype=torch.bfloat16)

    print("Loading dataset...")
    # Just grab 1 item
    class MockDataArgs:
        data_path = "/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/chat.json"
        image_folder = "/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/images"
        is_multimodal = True
        image_processor = model.get_model().get_vision_tower().image_processor
    
    tokenizer.model_max_length = 2048
    dataset = LazySupervisedDataset(MockDataArgs.data_path, tokenizer, MockDataArgs())
    collator = DataCollatorForSupervisedDataset(tokenizer)
    
    print("Getting item...")
    item = dataset[0]
    batch = collator([item])
    
    print("Inputs prepared. Running forward...")
    input_ids = batch['input_ids'].cuda()
    labels = batch['labels'].cuda()
    attention_mask = batch['attention_mask'].cuda()
    
    if 'images' in batch:
        images = batch['images'].to(device="cuda", dtype=torch.bfloat16)
    else:
        images = None

    try:
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
            images=images
        )
        print("Forward success! Loss:", outputs.loss.item())
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
