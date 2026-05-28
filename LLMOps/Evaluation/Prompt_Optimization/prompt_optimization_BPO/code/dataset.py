import torch
import os, glob, json
import torch.utils.data as d
import torch.nn.functional as F
from transformers import AutoTokenizer

class BaseDataset(d.Dataset):
    def __init__(self, data_path: str, model_id: str):
        super().__init__()
        
        self.dataset = self._load_data(data_path)

        self.tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
        self.tokenizer.pad_token = self.tokenizer.eos_token
    
    def _load_data(self, data_path: str) -> list:
        dataset = []

        with open(data_path, 'r', encoding='utf-8') as d:
            for line in d:
                data = json.loads(line)
                dataset.append({'id': data['id'], 'source': data['paragraph'][0]['q'], 'label': data['paragraph'][0]['a']})

        return dataset

    def __len__(self) -> int:
        return len(self.dataset)

    def collate_fn(self, batchs: list) -> dict:
        ids = [b['id'] for b in batchs]
        xs = [b['input_ids'] for b in batchs]
        ys = [b['labels'] for b in batchs]

        max_len = max(len(tokens) for tokens in xs + ys)

        attention_mask = torch.stack([torch.tensor([0 if i <= max_len - len(tokens) - 1 else 1 for i in range(max_len)]) for tokens in xs])
        xs = torch.stack([F.pad(tokens, (max_len - len(tokens), 0), value=self.tokenizer.pad_token_id) for tokens in xs])
        ys = torch.stack([F.pad(tokens, (max_len - len(tokens), 0), value=self.tokenizer.pad_token_id) for tokens in ys])

        return ids, {'input_ids': xs, 'labels': ys, 'attention_mask': attention_mask}

class TrainDataset(BaseDataset):
    def __getitem__(self, index):
        prompt = '<|im_start|>user\n'
        inputs = self.tokenizer(text=f'{prompt}{self.dataset[index]["source"]}<|im_end|>\n<|im_start|>assistant\n', return_tensors="pt", truncation=True)['input_ids'].squeeze()
        target = self.tokenizer(text=f'{self.dataset[index]["label"]}<|im_end|><|endoftext|>', return_tensors="pt", truncation=True)['input_ids'].squeeze()

        concatenated_tokens = torch.cat([inputs, target])
        labels = concatenated_tokens.clone()
        labels[:len(inputs)] = self.tokenizer.pad_token_id

        return {'id': self.dataset[index]['id'], 'input_ids': concatenated_tokens, 'labels': labels}
    
class EvaluateDataset(BaseDataset):
    def __getitem__(self, index):
        prompt = '<|im_start|>user\n'
        inputs = self.tokenizer(text=f'{prompt}{self.dataset[index]["source"]}<|im_end|>\n<|im_start|>assistant\n', return_tensors="pt", truncation=True)['input_ids'].squeeze()
        target = self.tokenizer(text=f'{self.dataset[index]["label"]}<|im_end|><|endoftext|>', return_tensors="pt", truncation=True)['input_ids'].squeeze()

        return {'id': self.dataset[index]['id'], 'input_ids': inputs, 'labels': target}
