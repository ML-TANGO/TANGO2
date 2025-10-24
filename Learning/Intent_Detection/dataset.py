import torch
import os, json
import torch.utils.data as d
import torch.nn.functional as F
from transformers import AutoTokenizer
from overrides import overrides
from tqdm.auto import tqdm


class BaseDataset(d.Dataset):
    def __init__(self, data_path: str, model_id: str, padding_side: str = "left"):
        super().__init__()
        data_x, data_y = [], []

        ## ATIS 포맷 디렉토리
        if os.path.isdir(data_path) and \
           all(os.path.exists(os.path.join(data_path, fn)) for fn in ["seq.in", "seq.out", "label"]):
            data_pairs = self._load_atis_dir(data_path)    ## 
        else:
            data_pairs = self._load_data(data_path)        # 기존 JSON 로더

        for data in data_pairs:
            if data.get('label'):
                data_x.append(data['source'])
                data_y.append(data['label'])
                self._child_init_process(data)
        self.data_x = data_x
        self.data_y = data_y        

        self.tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)

        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # self.tokenizer.padding_side = padding_side


    def _load_atis_dir(self, atis_dir: str) -> list:
        import json as _json
        def read_lines(p):
            with open(p, "r", encoding="utf-8") as f:
                return [ln.strip() for ln in f]

        xin  = read_lines(os.path.join(atis_dir, "seq.in"))
        xout = read_lines(os.path.join(atis_dir, "seq.out"))
        ylab = read_lines(os.path.join(atis_dir, "label"))
        assert len(xin) == len(xout) == len(ylab), "seq.in/seq.out/label 라인수가 다릅니다."


        def tags_to_spans(tokens, tags):
            spans, cur, buf = {}, None, []
            def flush():
                nonlocal cur, buf
                if cur and buf:
                    spans.setdefault(cur, []).append(" ".join(buf))
                cur, buf = None, []
            for tok, tag in zip(tokens, tags):
                if tag == "O" or not tag:
                    flush(); continue
                pre, _, slot = tag.partition("-")
                if pre == "B":
                    flush(); cur = slot; buf = [tok]
                elif pre == "I" and cur == slot:
                    buf.append(tok)
                else:
                    flush(); cur = slot if pre in ("B","I") else None
                    buf = [tok] if cur else []
            flush()
            return spans

        pairs = []
        split = os.path.basename(os.path.normpath(atis_dir))
        for i, (src, tg, lb) in enumerate(zip(xin, xout, ylab)):
            toks = src.split(); tags = tg.split()
            if len(toks) != len(tags):
                continue
            intents = [s for s in lb.split("#") if s]  # 다중 인텐트 대응
            slots   = tags_to_spans(toks, tags)
            target  = _json.dumps({"intents": intents, "slots": slots}, ensure_ascii=False)  
            pairs.append({"id": f"{split}-{i}", "source": src, "label": target, "ref": ""})
        return pairs

    def _load_data(self, data_path: str) -> list:
        with open(data_path, 'r', encoding='utf-8') as d:
            data = json.load(d)

        return data

    def _child_init_process(self, x):
        pass

    def __len__(self):
        return len(self.data_x)

    ## 
    def collate_fn(self, batchs):
        xs = [b['input_ids'] for b in batchs]
        ys = [b['labels'] for b in batchs]

        max_len = max(max(len(x) for x in xs), max(len(y) for y in ys))
        pad_id = self.tokenizer.pad_token_id

        def pad_stack(seq_list, pad_value):
            return torch.stack([F.pad(s, (max_len - len(s), 0), value=pad_value) for s in seq_list])

        xs = pad_stack(xs, pad_id)
        # labels 패딩: -100 -> pad_token_id
        ys = pad_stack(ys, pad_id)   

        attention_mask = (xs != pad_id).long()
        return {'input_ids': xs, 'labels': ys, 'attention_mask': attention_mask}


class PromptingDataset(BaseDataset):
    def __init__(self, data_path: str, model_id: str):
        self.data_id = []
        self.data_ref = []
        super().__init__(data_path, model_id)

    @overrides
    def _child_init_process(self, x):
        self.data_id.append(x['id'])
        self.data_ref.append(x['ref'])

    def __getitem__(self, index):
        # 프롬프트에 줄바꿈 추가로 토큰 안정화
        prompt = (
            "<|start_header_id|>system<|end_header_id|>\n\n"
            "The provided text includes the English source, the German translation, and a sentence-level German reference translation.\n"
            "Please revise the German translation by correcting errors such as hallucinations and omissions, using the source and the reference as guidance."
            "<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        )
        text = (
            f"{prompt}"
            f"The English source: {self.data_x[index]}\n\n"
            f"The German translation: {self.data_y[index]}\n\n"
            f"The sentence-level German reference translation: {self.data_ref[index]}"
            "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        inputs = self.tokenizer(text=text, return_tensors="pt", truncation=True)['input_ids'].squeeze(0)

        return {
            'id': self.data_id[index],
            'source': self.data_x[index],
            'ref': self.data_ref[index],
            'input_ids': inputs
        }

    @overrides
    def collate_fn(self, batchs):
        xs = [b['input_ids'] for b in batchs]
        ids = [b['id'] for b in batchs]
        sources = [b['source'] for b in batchs]
        refs = [b['ref'] for b in batchs]

        max_len = max(len(x) for x in xs)
        pad_id = self.tokenizer.pad_token_id

        xs = torch.stack([F.pad(x, (max_len - len(x), 0), value=pad_id) for x in xs])
        # attention_mask를 pad 기준으로 계산
        attention_mask = (xs != pad_id).long()

        return {'id': ids, 'source': sources, 'ref': refs, 'input_ids': xs, 'attention_mask': attention_mask}


class TrainDataset(BaseDataset):
    def __getitem__(self, index):
        
        # Input = Instruction(System 고정) + User utterance(= seq.in)에서 instruciton 부분 fix
        system_msg = (
            "Extract the user's intents and slot-value pairs from the utterance. "
            "Return JSON on a single line with keys exactly 'intents' and 'slots'. "
            "Use ATIS-style intent labels (e.g., atis_airport, atis_flight). "
            "Each slots[key] must be an array of strings (no nested objects). "
            "Do not add explanations or extra text."
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": self.data_x[index]},
            {"role": "assistant", "content": self.data_y[index]},
        ]

        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )

        input_ids = self.tokenizer(text, return_tensors="pt", truncation=True)['input_ids'].squeeze(0)

        # 정답 토큰 길이만큼 뒤쪽만 라벨로 사용
        tgt_ids = self.tokenizer(self.data_y[index], return_tensors="pt", truncation=True)['input_ids'].squeeze(0)
        labels = torch.full_like(input_ids, -100)
        labels[-len(tgt_ids):] = input_ids[-len(tgt_ids):]

        return {'input_ids': input_ids, 'labels': labels}


    # 추가: 학습용 collate는 labels의 패딩도 -100로 마스킹
    @overrides
    def collate_fn(self, batchs):
        xs = [b['input_ids'] for b in batchs]
        ys = [b['labels'] for b in batchs]

        max_len = max(max(len(x) for x in xs), max(len(y) for y in ys))
        pad_id = self.tokenizer.pad_token_id

        def pad_stack(seq_list, pad_value):
            import torch.nn.functional as F
            return torch.stack([F.pad(s, (max_len - len(s), 0), value=pad_value) for s in seq_list])

        xs = pad_stack(xs, pad_id)
        # 수정: 학습 시 패딩을 -100으로
        ys = pad_stack(ys, -100)

        attention_mask = (xs != pad_id).long()
        return {'input_ids': xs, 'labels': ys, 'attention_mask': attention_mask}



class EvaluateDataset(BaseDataset):
    def __getitem__(self, index):
        system_msg = (
            "Extract the user's intents and slot-value pairs from the utterance. "
            "Return JSON on a single line with keys exactly 'intents' and 'slots'. "
            "Use ATIS-style intent labels (e.g., atis_airport, atis_flight). "
            "Each slots[key] must be an array of strings (no nested objects). "
            "Do not add explanations or extra text."
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": self.data_x[index]},
        ]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True)['input_ids'].squeeze(0)
        target = self.tokenizer(self.data_y[index], return_tensors="pt", truncation=True)['input_ids'].squeeze(0)
        return {'input_ids': inputs, 'labels': target}
        

    # 추가: 평가용 collate는 labels 패딩을 pad_id로(디코딩용)
    @overrides
    def collate_fn(self, batchs):
        xs = [b['input_ids'] for b in batchs]
        ys = [b['labels'] for b in batchs]
        max_len = max(max(len(x) for x in xs), max(len(y) for y in ys))
        pad_id = self.tokenizer.pad_token_id

        import torch.nn.functional as F
        xs = torch.stack([F.pad(x, (max_len - len(x), 0), value=pad_id) for x in xs])
        ys = torch.stack([F.pad(y, (max_len - len(y), 0), value=pad_id) for y in ys])

        attention_mask = (xs != pad_id).long()
        return {'input_ids': xs, 'labels': ys, 'attention_mask': attention_mask}



#class Collator(): #이거를 Dataset의 메서드로 바꾸기
#    def __init__(self, tokenizer):
#        self.tokenizer = tokenizer
#
#    def __call__(self, batchs):
#        xs = [b['input_ids'] for b in batchs]
#        ys = [b['labels'] for b in batchs]
#
#        max_len = max(len(tokens) for tokens in xs + ys)
#
#        attention_mask = torch.stack([torch.tensor([0 if i <= max_len - len(tokens) - 1 else 1 for i in range(max_len)]) for tokens in xs])
#        xs = torch.stack([F.pad(tokens, (max_len - len(tokens), 0), value=self.tokenizer.pad_token_id) for tokens in xs])
#        ys = torch.stack([F.pad(tokens, (max_len - len(tokens), 0), value=self.tokenizer.pad_token_id) for tokens in ys])
#
#        return {'input_ids': xs, 'labels': ys, 'attention_mask': attention_mask}

