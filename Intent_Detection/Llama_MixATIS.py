import os, json, logging, argparse
from datetime import datetime
from pytz import timezone

import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW  #
from tqdm.auto import tqdm

from transformers import (
    AutoModelForCausalLM, AutoTokenizer,
    get_scheduler  #
)

import evaluate  # 
from dataset import TrainDataset, EvaluateDataset

import re
from collections import Counter
import random


## 
def _safe_parse_json(txt: str):
    import re, json
    txt = (txt or "").strip()

    # 1) 균형 괄호 기반으로 첫 JSON 블록 추출
    def _extract_balanced_json(s: str):
        start = s.find('{')
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(s)):
            c = s[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return s[start:i+1]
        return None

    # 기본 시도
    block = _extract_balanced_json(txt)

    # 2) 백업1: 마지막 '}'까지 잘라서 시도 (EOT 뒤에 잡텍스트가 붙은 경우 대비)
    if block is None:
        last = txt.rfind('}')
        first = txt.find('{')
        if first != -1 and last != -1 and last > first:
            cand = txt[first:last+1]
            try:
                json.loads(cand)
                block = cand
            except Exception:
                block = None

    # 3) 백업2: 비탐욕 정규식으로 가장 짧은 JSON 후보 시도
    if block is None:
        m = re.search(r'\{.*?\}', txt, flags=re.S)
        block = m.group(0) if m else None

    if block is None:
        return {"intents": [], "slots": {}}

    # 로드 & 정규화
    try:
        obj = json.loads(block)
    except Exception:
        return {"intents": [], "slots": {}}

    # intents: str -> [str], 공백 제거
    intents = obj.get("intents", [])
    if isinstance(intents, str):
        intents = [intents]
    intents = [str(x).strip() for x in intents if str(x).strip()]

    # slots: dict, value는 항상 list[str]
    slots = obj.get("slots", {})
    if not isinstance(slots, dict):
        slots = {}
    norm_slots = {}
    for k, v in slots.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            vals = [str(x).strip() for x in v if str(x).strip()]
        else:
            vals = [str(v).strip()] if str(v).strip() else []
        if vals:
            norm_slots[str(k)] = vals

    return {"intents": intents, "slots": norm_slots}

def _slot_pairs(slots: dict):

    pairs = []
    for k, vals in slots.items():
        for v in vals:
            pairs.append((k.strip().lower(), v.strip().lower()))
    return set(pairs)


def _micro_prf(tp, fp, fn):

    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec  = tp / (tp + fn) if (tp + fn) else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1



class Trainer: 
    def __init__(self, model_id: str, epochs: int, dataloader: DataLoader, lr: float=5e-5, use_flash: bool=True):
        # tokenizer + pad 
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)

        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # 
        model_kwargs = dict(
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            device_map="auto"
        )
        if use_flash:
            model_kwargs["attn_implementation"] = "flash_attention_2"  

        self.model = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)       

        # 모델 config에 pad_token_id 반영
        if self.model.config.pad_token_id is None:
            self.model.config.pad_token_id = self.tokenizer.pad_token_id
        
        
        self.epochs = epochs
        self.dataloader = dataloader
        self.lr = lr

        self.steps = epochs * len(dataloader)
        self.optimizer = AdamW(self.model.parameters(), lr=self.lr, weight_decay=0.01)

        # 스케줄러 warmup 최소 1 step 보장
        self.scheduler = get_scheduler(
            'linear',
            optimizer=self.optimizer,
            num_warmup_steps=max(1, int(self.steps * 0.01)),
            num_training_steps=self.steps
        )

    def __call__(self):
        progress_bar = tqdm(total=self.steps, desc="training")
        self.model.train()

        for _ in range(self.epochs):
            for batch in self.dataloader:
                # device_map="auto" 사용 시 model.device로 직접 올려줌
                batch = {k: v.to(self.model.device) for k, v in batch.items()}
                outputs = self.model(**batch)
                loss = outputs.loss
                if not torch.isfinite(loss):
                    print('WARNING: non-finite loss, ending training')
                    return
                loss.backward()
                self.optimizer.step()
                self.scheduler.step()
                self.optimizer.zero_grad()
                progress_bar.set_description(f"loss: {loss:.4f}")
                progress_bar.update(1)

    def save(self, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        self.model.save_pretrained(output_dir)
        # 토크나이저도 함께 저장 (chat template 포함)
        self.tokenizer.save_pretrained(output_dir)


class Evaluator:
    def __init__(self, model_id: str, dataloader: DataLoader, max_new_tokens: int = 256, num_beams: int = 4):
        # tokenizer + pad_token
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)

        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # 모델 로드
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            device_map="auto"
        )
        if self.model.config.pad_token_id is None:
            self.model.config.pad_token_id = self.tokenizer.pad_token_id

        gen_cfg = self.model.generation_config
        gen_cfg.pad_token_id = self.tokenizer.pad_token_id
        gen_cfg.eos_token_id = self.tokenizer.eos_token_id
        self.model.generation_config = gen_cfg

        self.dataloader = dataloader
        self.max_new_tokens = max_new_tokens
        self.num_beams = num_beams

    def __call__(self):
        progress_bar = tqdm(total=min(5, len(self.dataloader)), desc="evaluating (sample only)")

        results = []
        n = 0
        intent_exact = 0
        joint_exact = 0
        tp = fp = fn = 0

        self.model.eval()
        logged = 0

        with torch.no_grad():
            for batch in self.dataloader:
                input_ids = batch['input_ids'].to(self.model.device)
                attention_mask = (input_ids != self.tokenizer.pad_token_id).long()
                input_lengths = attention_mask.sum(dim=1)

                outputs = self.model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=False,
                    num_beams=self.num_beams,
                )

                decoded_pred = []
                for i in range(outputs.size(0)):
                    gen_only = outputs[i, input_lengths[i]:]
                    decoded_pred.append(self.tokenizer.decode(gen_only, skip_special_tokens=True).strip())

                decoded_labels = [
                    self.tokenizer.decode(l.to(self.model.device), skip_special_tokens=True).strip()
                    for l in batch['labels']
                ]

                # 평가 로직
                for pred_txt, gold_txt in zip(decoded_pred, decoded_labels):
                    n += 1
                    p = _safe_parse_json(pred_txt)
                    g = _safe_parse_json(gold_txt)

                    if logged < 3 and not p["intents"] and not p["slots"]:
                        print("\n[DEBUG] RAW GEN:", repr(pred_txt[:250]))
                        print("[DEBUG] PARSED :", p)
                        print("[DEBUG] GOLD   :", g)
                        logged += 1

                    if set(x.lower() for x in p["intents"]) == set(x.lower() for x in g["intents"]):
                        intent_exact += 1

                    p_set = _slot_pairs(p["slots"])
                    g_set = _slot_pairs(g["slots"])
                    tp += len(p_set & g_set)
                    fp += len(p_set - g_set)
                    fn += len(g_set - p_set)

                    if set(x.lower() for x in p["intents"]) == set(x.lower() for x in g["intents"]) and (p_set == g_set):
                        joint_exact += 1

                for i in range(len(decoded_pred)):
                    results.append({
                        'input': self.tokenizer.decode(input_ids[i], skip_special_tokens=True),
                        'output': decoded_pred[i],
                        'label': decoded_labels[i],
                    })

                progress_bar.update(1)

                # 5개만 돌리고 중단
                if len(results) >= 5:
                    break

        intent_acc = intent_exact / n if n else 0.0
        prec, rec, slot_f1 = _micro_prf(tp, fp, fn)
        joint_acc = joint_exact / n if n else 0.0

        metrics = {
            "intent_accuracy": round(intent_acc, 6),
            "slot_precision":  round(prec, 6),
            "slot_recall":     round(rec, 6),
            "slot_f1":         round(slot_f1, 6),
            "joint_accuracy":  round(joint_acc, 6),
            "samples":         n,
        }

        # 샘플 5개만 저장
        with open("eval_sample_outputs.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        return metrics, results

def main():
    parser = argparse.ArgumentParser(description='Llama Fine-Tuning for MixATIS Dataset')
    parser.add_argument('--model_id', type=str, default="meta-llama/Meta-Llama-3.1-8B-Instruct", help='model id/location of LLM')
    parser.add_argument('--batch_size', type=int, default=4, help='batch size for dataloader')
    parser.add_argument('--epochs', type=int, default=1, help='epochs for training')
    parser.add_argument('--data_path', type=str, default=os.path.expanduser('./data/MixATIS_clean/train'), help='train ATIS dir')
    parser.add_argument('--eval_path', type=str, default=os.path.expanduser('./data/MixATIS_clean/dev'), help='eval ATIS dir')
    parser.add_argument('--output_dir', type=str, default='./ckpt_llama31_mixatis', help='where to save finetuned model/tokenizer')
    parser.add_argument('--eval_only', action='store_true', help='skip training and only evaluate from output_dir')
    parser.add_argument('--save_path', type=str, default='../data/revised_data/train_revised.json', help='output path (.json)')
    parser.add_argument('--no_flash', action='store_true', help='disable flash_attention_2 if env not supported')
    args = parser.parse_args()

    KST = timezone('Asia/Seoul')
    now = lambda: datetime.now(KST).strftime('%Y/%m/%d %H:%M:%S')

    if args.eval_only:
        assert os.path.isdir(args.model_id), f"Checkpoint not found: {args.model_id}"
        eval_dataset = EvaluateDataset(args.eval_path, args.model_id)  # tokenizer도 checkpoint에서 로드
        eval_loader  = DataLoader(eval_dataset, batch_size=args.batch_size, shuffle=False, collate_fn=eval_dataset.collate_fn)
        _LOGGER.info(f'[INFO] ({now()}) Eval-only mode: checkpoint={args.model_id}, eval_path={args.eval_path}')

        evaluator = Evaluator(args.model_id, eval_loader, max_new_tokens=256, num_beams=1)
        metrics, results = evaluator()
        _LOGGER.info(f"[INFO] TEST Metrics: {json.dumps(metrics, ensure_ascii=False)}")


        with open("eval_sample_outputs.json", "w", encoding="utf-8") as f:
            json.dump(results[:5], f, ensure_ascii=False, indent=2)
        return


    _LOGGER.info(f'[INFO] ({now()}) Data Loading..\n  train: {args.data_path}\n  eval: {args.eval_path}\n  batch: {args.batch_size}')
    train_dataset = TrainDataset(args.data_path, args.model_id)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, collate_fn=train_dataset.collate_fn)

    _LOGGER.info(f'[INFO] ({now()}) Start Training.. model: {args.model_id}')
    trainer = Trainer(args.model_id, args.epochs, train_loader, use_flash=(not args.no_flash))
    trainer()

    _LOGGER.info(f'[INFO] ({now()}) Saving finetuned model to: {args.output_dir}')
    trainer.save(args.output_dir)

    if os.path.exists(args.eval_path):
        eval_dataset = EvaluateDataset(args.eval_path, args.model_id)
        eval_loader  = DataLoader(eval_dataset, batch_size=args.batch_size, shuffle=False, collate_fn=eval_dataset.collate_fn)
        _LOGGER.info(f'[INFO] ({now()}) Start Evaluation..')

        evaluator = Evaluator(args.output_dir, eval_loader, max_new_tokens=256, num_beams=4)
        metrics, rows = evaluator()
        _LOGGER.info(f"[INFO] Metrics: {json.dumps(metrics, ensure_ascii=False)}")

    _LOGGER.info(f'[INFO] ({now()}) Done. save_path: {args.save_path}')



if __name__ == '__main__':
    stream_handler = logging.StreamHandler()
    _LOGGER = logging.getLogger("__name__")
    _LOGGER.setLevel(level=logging.INFO)
    _LOGGER.addHandler(stream_handler)
    main()
