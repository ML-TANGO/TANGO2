#!/usr/bin/env python
# coding: utf-8

from transformers import AutoModelForCausalLM, AutoTokenizer, get_scheduler
import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
import torch.nn.functional as F
from datetime import datetime
from pytz import timezone
from tqdm.auto import tqdm
import os, json, logging, random, sys, argparse
from peft import LoraConfig, get_peft_model

from dataset import TrainDataset, EvaluateDataset


class Trainer():
    def __init__(self, model, epochs, dataloader, lr):
        self.model = model
        self.epochs = epochs
        self.dataloader = dataloader
        self.lr = lr

        self.steps = epochs * len(dataloader)
        self.optimizer = AdamW(self.model.parameters(), lr=self.lr, weight_decay=0.01)

        self.scheduler = get_scheduler(
            'linear',
            optimizer=self.optimizer,
            num_warmup_steps=int(self.steps*0.01),
            num_training_steps=self.steps,
            )

    def __call__(self):
        progress_bar = tqdm(range(self.steps))
        checkpoints = {int(self.steps * i / 10) for i in range(1, 11)}

        self.model.train()
        for epoch in range(self.epochs):
            for meta, batch in self.dataloader:
                batch = {k: v.to(device) for k, v in batch.items()}
                outputs = self.model(**batch)
                loss = outputs.loss
                if not torch.isfinite(loss):
                    print('WARNING: non-finite loss, ending training')
                    exit(1)
                loss.backward()
                self.optimizer.step()
                self.scheduler.step()
                self.optimizer.zero_grad()
                progress_bar.set_description(f'loss: {loss}')
                progress_bar.update(1)

                #if progress_bar.n in checkpoints:
                #    self.model.save_pretrained(f'../models/checkpoints/dlo_{date}_fine-tuned_llama3_1B_lora_{epoch}_{progress_bar.n * 100 // self.steps}')

def main():
    # (0) argument parsing
    parser = argparse.ArgumentParser(description='Baseline BPO SFT')
    parser.add_argument('--model_id', type=str, default="Qwen/Qwen3-8B", help='model id/location of LLM')
    parser.add_argument('--batch_size', type=int, default=1, help='batch size for dataloader')
    parser.add_argument('--epoch', type=int, default=3, help='number of epochs')
    parser.add_argument('--lr', type=float, default=5e-5, help='learning rate')
    parser.add_argument('--base_data_path', type=str, default='../data/', help='base data path')
    parser.add_argument('--model_save_path', type=str, default=f'../models/BPO_{date}_seed100_SFT_Qwen3_8B_lora_epoch3', help='model save path')
    parser.add_argument('--result_path', type=str, default=f'../result/BPO_{date}_seed100_SFT_Qwen3_8B_lora_epoch3.result.json', help='output directory path')
    args = parser.parse_args()

    train_path = f'{args.base_data_path}/train.jsonl'
    eval_path = f'{args.base_data_path}/eval.jsonl'

    model = AutoModelForCausalLM.from_pretrained(args.model_id, device_map='auto')

    # (1) Load Data
    now_time = datetime.now(KST).strftime('%Y/%m/%d %H:%M:%S')
    _LOGGER.info(f'[{now_time}] Starting Pre-Processing..')
    train_dataset = TrainDataset(train_path, args.model_id)
    train_dataloader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, collate_fn=train_dataset.collate_fn)
    #evaluation_dataset = EvaluateDataset(eval_path, args.model_id)
    #evaluation_dataloader = DataLoader(evaluation_dataset, batch_size=args.batch_size, shuffle=False, collate_fn=evaluation_dataset.collate_fn)
    
    # (2) LoRA
    config = LoraConfig(
        r=16,
        lora_alpha=16,
        target_modules=['q_proj', 'v_proj'],
        lora_dropout=0.1,
        bias='none',
    )

    lora_model = get_peft_model(model, config)
    lora_model.to(device)

    # (3) Train
    now_time = datetime.now(KST).strftime('%Y/%m/%d %H:%M:%S')
    _LOGGER.info(f'[{now_time}] Starting Fine-Tuning..\nmodel: {args.model_save_path}\nbase model: {args.model_id}')
    trainer = Trainer(model=lora_model, epochs=args.epoch, dataloader=train_dataloader, lr=args.lr)
    trainer()

    lora_model.save_pretrained(args.model_save_path)

    # (4) Evaluation
    #now_time = datetime.now(KST).strftime('%Y/%m/%d %H:%M:%S')
    #_LOGGER.info(f'[{now_time}] Starting Evaluation..')
    #evaluator = Evaluator(model=lora_model, tokenizer=tokenizer, dataloader=evaluation_dataloader)
    #bleu, result = evaluator()

    #now_time = datetime.now(KST).strftime('%Y/%m/%d %H:%M:%S')
    #_LOGGER.info(f'[{now_time}] Success!!')

    #print()
    #print('='*30)
    #print(bleu)
    #print('='*30)

    #with open(result_path, 'wt', encoding="utf-8") as r:
    #    json.dump(result, r, indent=4)


if __name__ == '__main__':
    KST = timezone('Asia/Seoul')
    stream_hander = logging.StreamHandler()
    _LOGGER = logging.getLogger("__name__")
    _LOGGER.setLevel(level=logging.INFO)
    _LOGGER.addHandler(stream_hander)
    date = datetime.now(KST).strftime('%m%d%H%M')
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    main()
