#!/usr/bin/env python3
"""
Stage-3 (correct pairing):

Query-side:
  x = findings_section full report text (o)
  frozen encoder => token hidden states H_o and EOS global embedding g_o
  trainable pooler => 9 section embeddings q_s

Doc-side (targets):
  r_s = anatomy section text (Pleura, Lungs..., ...)
  frozen encoder => EOS embedding d_s = normalize(EOS_pool(r_s))

Positive pair (for lungs example):
  q_lung = Pooler_lung(H_o, mask_o, g_o)  <->  d_lung = Chest2VecEOS(r_lung)

Encoder is frozen and forced to eval() even during Trainer.train().
Only pooler (+ optional logit_scale, per-section bias) is trained.
"""

import os
import json
import math
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.distributed as dist
from torch.utils.data import Dataset

from transformers import AutoTokenizer, AutoModel, TrainingArguments, Trainer, BitsAndBytesConfig, TrainerCallback
from argparse import ArgumentParser

try:
    from peft import PeftModel
    _HAS_PEFT = True
except Exception:
    PeftModel = None
    _HAS_PEFT = False

try:
    from chest2vec import Chest2Vec
    _HAS_CHEST2VEC = True
except Exception:
    Chest2Vec = None
    _HAS_CHEST2VEC = False


# -----------------------------
# Constants
# -----------------------------
ANATOMY_COLUMNS = [
    "Lungs + Pleura",
    "Airways & Trachea",
    "Mediastinum & Hila",
    "Cardiovascular",
    "Thoracic MSK",
    "Upper abdomen",
    "Lower neck",
    "Others",
    "impression",
]


# -----------------------------
# Utilities
# -----------------------------
def get_local_rank() -> int:
    for var in ["LOCAL_RANK", "OMPI_COMM_WORLD_LOCAL_RANK", "MV2_COMM_WORLD_LOCAL_RANK"]:
        if var in os.environ:
            return int(os.environ[var])
    return 0


def is_main_process() -> bool:
    return (not dist.is_initialized()) or dist.get_rank() == 0


def choose_attn_impl(prefer="flash_attention_2"):
    try:
        from transformers.modeling_flash_attention_utils import is_flash_attn_greater_or_equal_2
        if prefer == "flash_attention_2" and is_flash_attn_greater_or_equal_2():
            return "flash_attention_2"
    except Exception:
        pass
    return "sdpa"


def canonicalize_text(s: str) -> str:
    return " ".join(str(s).strip().split())


def stable_int64_hash(text: str) -> int:
    h = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "little", signed=True)


def get_pool_token_id(tok) -> int:
    # Qwen3-Embedding pools on <|endoftext|>
    eod_id = tok.convert_tokens_to_ids("<|endoftext|>")
    if eod_id is None or eod_id < 0:
        eod_id = tok.pad_token_id
    return eod_id


def encode_with_eos_ids(tok, texts: List[str], max_len: int) -> Dict[str, torch.Tensor]:
    """
    - add_special_tokens=False
    - truncation to max_len-1
    - append <|endoftext|>
    - LEFT padding
    """
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    eod_id = get_pool_token_id(tok)

    enc = tok(
        [str(t) for t in texts],
        add_special_tokens=False,
        truncation=True,
        max_length=max_len - 1,
        padding=False,
        return_attention_mask=False,
    )

    input_ids = [ids + [eod_id] for ids in enc["input_ids"]]
    attn_mask = [[1] * len(ids) for ids in input_ids]

    T = max((len(ids) for ids in input_ids), default=1)
    input_ids = [[pad_id] * (T - len(ids)) + ids for ids in input_ids]
    attn_mask = [[0] * (T - len(m)) + m for m in attn_mask]

    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "attention_mask": torch.tensor(attn_mask, dtype=torch.long),
    }


def last_token_pool(last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """
    Left-padding aware last-token pooling.
    last_hidden_states: [B,T,H]
    attention_mask:     [B,T]
    """
    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        return last_hidden_states[:, -1]
    idx = attention_mask.sum(dim=1) - 1
    return last_hidden_states[torch.arange(last_hidden_states.size(0), device=last_hidden_states.device), idx]


def get_last_hidden_state(model, input_ids, attention_mask):
    """
    AutoModel last_hidden_state with explicit position_ids for LEFT padding + flash_attention_2.
    """
    m = model.module if hasattr(model, "module") else model

    position_ids = attention_mask.long().cumsum(-1) - 1
    position_ids.masked_fill_(attention_mask == 0, 0)

    out = m(
        input_ids=input_ids,
        attention_mask=attention_mask,
        position_ids=position_ids,
        use_cache=False,
        return_dict=True,
    )
    if hasattr(out, "last_hidden_state"):
        return out.last_hidden_state

    out = m(
        input_ids=input_ids,
        attention_mask=attention_mask,
        position_ids=position_ids,
        output_hidden_states=True,
        use_cache=False,
        return_dict=True,
    )
    return out.hidden_states[-1]


def all_gather_embeddings(x: torch.Tensor) -> torch.Tensor:
    """
    All-gather [N,D] across ranks, preserving autograd for local part.
    Requires dataloader_drop_last=True.
    """
    if not dist.is_initialized():
        return x
    world = dist.get_world_size()
    rank = dist.get_rank()
    bufs = [torch.zeros_like(x) for _ in range(world)]
    dist.all_gather(bufs, x.contiguous())
    bufs[rank] = x
    return torch.cat(bufs, dim=0)


def all_gather_1d_long(x: torch.Tensor) -> torch.Tensor:
    if not dist.is_initialized():
        return x
    world = dist.get_world_size()
    bufs = [torch.empty_like(x) for _ in range(world)]
    dist.all_gather(bufs, x.contiguous())
    return torch.cat(bufs, dim=0)


def freeze_all_parameters(model: nn.Module):
    for p in model.parameters():
        p.requires_grad = False


def gather_param_to_cpu(param: torch.Tensor) -> Optional[torch.Tensor]:
    """
    ZeRO-3-safe gather. All ranks call; only rank0 gets CPU tensor.
    """
    is_dist = dist.is_initialized()
    rank = dist.get_rank() if is_dist else 0
    try:
        import deepspeed
        from deepspeed import zero
        if hasattr(param, "ds_id"):
            with zero.GatheredParameters([param], modifier_rank=0):
                if (not is_dist) or rank == 0:
                    return param.detach().cpu().clone()
                return None
    except Exception:
        pass

    if (not is_dist) or rank == 0:
        return param.detach().cpu().clone()
    return None


# -----------------------------
# Load pretrained encoder FIRST (adapter dir OR full model OR HF Hub via Chest2Vec)
# -----------------------------
def load_encoder_from_chest2vec(
    repo_id: str,
    *,
    use_4bit: bool,
    attn_impl: str,
    local_rank: int,
) -> Tuple[Any, nn.Module]:
    """
    Load encoder from Hugging Face Hub using Chest2Vec wrapper.
    Extracts the base encoder model and tokenizer.
    """
    if not _HAS_CHEST2VEC:
        raise RuntimeError(
            "Chest2Vec package is not installed.\n"
            "Install it from the model repository:\n"
            "  pip install git+https://huggingface.co/<repo_id>\n"
            "Or use --no_use_chest2vec_loader to load directly via transformers."
        )
    
    device = f"cuda:{local_rank}"
    force_flash_attn2 = (attn_impl == "flash_attention_2")
    
    if is_main_process():
        print(f"[encoder] Loading from HF Hub via Chest2Vec: {repo_id}")
        print(f"  device={device}, use_4bit={use_4bit}, attn_impl={attn_impl}")
    
    # Load Chest2Vec wrapper
    chest2vec = Chest2Vec.from_pretrained(
        repo_id_or_path=repo_id,
        device=device,
        use_4bit=use_4bit,
        force_flash_attention_2=force_flash_attn2,
    )
    
    # Extract encoder and tokenizer
    encoder = chest2vec.model
    tok = chest2vec.tokenizer
    
    # Ensure padding is on left for our use case
    tok.padding_side = "left"
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    
    # Disable caching
    encoder.config.use_cache = False
    
    if is_main_process():
        print(f"[encoder] Successfully loaded from Chest2Vec wrapper")
        print(f"  Model dtype: {next(encoder.parameters()).dtype}")
    
    return tok, encoder


def load_pretrained_encoder(
    pretrained_path_or_id: str,
    *,
    base_override: Optional[str],
    use_4bit: bool,
    attn_impl: str,
    local_rank: int,
    use_chest2vec_loader: bool = False,
) -> Tuple[Any, nn.Module]:
    """
    Load encoder via one of three methods:
    
    1. If use_chest2vec_loader=True:
       Load from HF Hub using Chest2Vec wrapper (recommended for published models)
    
    2. If pretrained is a PEFT adapter dir (adapter_config.json exists):
       Load base from adapter_config.base_model_name_or_path (or base_override)
       then attach adapter via PeftModel.from_pretrained(..., is_trainable=False)

    3. Else:
       Treat pretrained_path_or_id as a full checkpoint/HF id and load directly via AutoModel
    """
    # Method 1: Chest2Vec loader (for HF Hub models)
    if use_chest2vec_loader:
        return load_encoder_from_chest2vec(
            pretrained_path_or_id,
            use_4bit=use_4bit,
            attn_impl=attn_impl,
            local_rank=local_rank,
        )
    
    # Method 2 & 3: PEFT adapter or direct AutoModel loading
    is_dir = os.path.isdir(pretrained_path_or_id)
    adapter_cfg = os.path.join(pretrained_path_or_id, "adapter_config.json") if is_dir else None
    full_cfg = os.path.join(pretrained_path_or_id, "config.json") if is_dir else None
    is_adapter_dir = bool(is_dir and adapter_cfg and os.path.exists(adapter_cfg) and not os.path.exists(full_cfg))

    qconf = None
    if use_4bit:
        qconf = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

    if is_adapter_dir:
        if not _HAS_PEFT:
            raise RuntimeError("Detected PEFT adapter dir but peft is not installed.")

        with open(adapter_cfg, "r", encoding="utf-8") as f:
            acfg = json.load(f)
        base = base_override or acfg.get("base_model_name_or_path", None)
        if not base:
            raise ValueError("Adapter dir detected but base model not found. Provide --base_override.")

        tok = AutoTokenizer.from_pretrained(base, padding_side="left", trust_remote_code=True)
        if tok.pad_token_id is None:
            tok.pad_token = tok.eos_token

        base_model = AutoModel.from_pretrained(
            base,
            trust_remote_code=True,
            attn_implementation=attn_impl,
            quantization_config=qconf,
            torch_dtype=torch.bfloat16 if not use_4bit else None,
            device_map={"": f"cuda:{local_rank}"},
        )
        model = PeftModel.from_pretrained(base_model, pretrained_path_or_id, is_trainable=False)
        model.config.use_cache = False

        if is_main_process():
            print(f"[encoder] base={base} + adapter={pretrained_path_or_id}")
        return tok, model

    # full model
    tok = AutoTokenizer.from_pretrained(pretrained_path_or_id, padding_side="left", trust_remote_code=True)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    model = AutoModel.from_pretrained(
        pretrained_path_or_id,
        trust_remote_code=True,
        attn_implementation=attn_impl,
        quantization_config=qconf,
        torch_dtype=torch.bfloat16 if not use_4bit else None,
        device_map={"": f"cuda:{local_rank}"},
    )
    model.config.use_cache = False

    if is_main_process():
        print(f"[encoder] full={pretrained_path_or_id}")
    return tok, model


# -----------------------------
# Dataset / Collator
# -----------------------------
class Stage3AnatomyDataset(Dataset):
    """
    Each item returns:
      q_text: Instruct+Query:o
      sec_texts: list of 9 anatomy section texts r_s
      pos_ids: stable hash of each section text (for multi-positive)
    """
    def __init__(
        self,
        df_path: str,
        split: Optional[str],
        findings_col: str,
        require_nonempty: bool = True,
    ):
        if df_path.lower().endswith(".parquet"):
            df = pd.read_parquet(df_path)
        elif df_path.lower().endswith(".jsonl"):
            df = pd.read_json(df_path, lines=True)
        elif df_path.lower().endswith(".json"):
            df = pd.read_json(df_path)
        else:
            df = pd.read_csv(df_path, low_memory=False)

        needed = [findings_col] + ANATOMY_COLUMNS
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if split is not None and "split" in df.columns:
            df = df[df["split"].astype(str).str.lower() == str(split).lower()].reset_index(drop=True)

        df[findings_col] = df[findings_col].fillna("").astype(str)
        for c in ANATOMY_COLUMNS:
            df[c] = df[c].fillna("").astype(str)

        if require_nonempty:
            mask = df[findings_col].str.strip() != ""
            for c in ANATOMY_COLUMNS:
                mask = mask & (df[c].str.strip() != "")
            df = df[mask].reset_index(drop=True)

        self.df = df
        self.findings_col = findings_col

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i: int) -> Tuple[str, List[str], List[int]]:
        r = self.df.iloc[i]
        q_text = str(r[self.findings_col]).strip()

        sec_texts = [str(r[c]) for c in ANATOMY_COLUMNS]
        pos_ids = [stable_int64_hash(canonicalize_text(t)) for t in sec_texts]
        return q_text, sec_texts, pos_ids


@dataclass
class Stage3AnatomyCollator:
    tok: Any
    max_len_query: int = 2048
    max_len_section: int = 512
    _first_batch_checked: bool = False

    def __call__(self, batch):
        B = len(batch)
        S = len(ANATOMY_COLUMNS)
        if B == 0:
            raise ValueError("Empty batch")

        q_texts = [x[0] for x in batch]
        sec_texts_list = [x[1] for x in batch]
        pos_ids_list = [x[2] for x in batch]

        sec_flat: List[str] = []
        pos_id = torch.zeros((B, S), dtype=torch.long)
        for i, (secs, pids) in enumerate(zip(sec_texts_list, pos_ids_list)):
            sec_flat.extend(secs)
            pos_id[i] = torch.tensor(pids, dtype=torch.long)

        q_enc = encode_with_eos_ids(self.tok, q_texts, self.max_len_query)
        d_enc = encode_with_eos_ids(self.tok, sec_flat, self.max_len_section)

        if not self._first_batch_checked:
            eod = get_pool_token_id(self.tok)
            assert (q_enc["input_ids"][:, -1] == eod).all()
            assert (d_enc["input_ids"][:, -1] == eod).all()
            object.__setattr__(self, "_first_batch_checked", True)

        pad_id = self.tok.pad_token_id if self.tok.pad_token_id is not None else self.tok.eos_token_id
        return {"q": q_enc, "d": d_enc, "pos_id": pos_id, "pad_token_id": int(pad_id), "B": B, "S": S}


# -----------------------------
# Loss: multi-positive sigmoid
# -----------------------------
class MultiPositiveSigmoidLoss(nn.Module):
    def __init__(self, symmetric: bool = True, pos_weight_cap: float = 1024.0, pow_alpha: float = 0.5):
        super().__init__()
        self.symmetric = bool(symmetric)
        self.pos_weight_cap = float(pos_weight_cap)
        self.pow_alpha = float(pow_alpha)

    def _row_balanced_bce(self, logits, pos_mask, logit_bias=None):
        if logit_bias is not None:
            logits = logits + logit_bias
        y = pos_mask.float()
        pos_cnt = y.sum(dim=1, keepdim=True).clamp_min(1.0)
        neg_cnt = (y.size(1) - pos_cnt).clamp_min(1.0)
        w_pos = (neg_cnt / pos_cnt).pow(self.pow_alpha).clamp(max=self.pos_weight_cap)
        weights = y * w_pos + (1.0 - y)
        loss = F.binary_cross_entropy_with_logits(logits, y, weight=weights, reduction="none")
        denom = weights.sum(dim=1).clamp_min(1e-6)
        return (loss.sum(dim=1) / denom).mean()

    def forward(self, logits_q2d, pos_mask_q2d, logits_d2q, pos_mask_d2q, logit_bias=None):
        loss = self._row_balanced_bce(logits_q2d, pos_mask_q2d, logit_bias=logit_bias)
        if self.symmetric:
            loss = 0.5 * (loss + self._row_balanced_bce(logits_d2q, pos_mask_d2q, logit_bias=logit_bias))
        return loss


# -----------------------------
# Pooler: latent dictionary attention (trainable)
# -----------------------------
class LatentDictSectionPooler(nn.Module):
    """
    Input: token hidden states H_o and EOS global embedding g_o
    Output: 9 section embeddings q_s

    Implementation:
      - Per-section dictionary latents D[s,k]
      - Condition latents on EOS: D[s,k] + proj(g_o)
      - Latents attend over tokens => pooled_latents
      - Merge K latents => section embedding
      - MLP + L2 norm
    """
    def __init__(
        self,
        hidden_size: int,
        num_sections: int,
        num_latents: int = 8,
        mlp_hidden: Optional[int] = None,
        dropout: float = 0.1,
        use_layernorm: bool = True,
        cond_on_eos: bool = True,
        output_dim: Optional[int] = None,
    ):
        super().__init__()
        self.H = int(hidden_size)
        self.S = int(num_sections)
        self.K = int(num_latents)
        self.cond_on_eos = bool(cond_on_eos)
        self.output_dim = int(output_dim) if output_dim else self.H

        self.ln_x = nn.LayerNorm(self.H) if use_layernorm else nn.Identity()
        self.ln_d = nn.LayerNorm(self.H) if use_layernorm else nn.Identity()

        self.dict_latents = nn.Parameter(torch.empty(self.S, self.K, self.H))
        nn.init.normal_(self.dict_latents, mean=0.0, std=0.02)

        self.eos_proj = nn.Linear(self.H, self.H, bias=False) if self.cond_on_eos else None

        self.merge_q = nn.Parameter(torch.empty(self.S, self.H))
        nn.init.normal_(self.merge_q, mean=0.0, std=0.02)

        self.scale_tok = 1.0 / math.sqrt(self.H)
        self.scale_merge = 1.0 / math.sqrt(self.H)
        self.drop = nn.Dropout(float(dropout)) if dropout and dropout > 0 else nn.Identity()

        mlp_hidden = int(mlp_hidden) if (mlp_hidden and mlp_hidden > 0) else self.H
        self.mlp = nn.Sequential(
            nn.Linear(self.H, mlp_hidden, bias=False),
            nn.GELU(),
            nn.Linear(mlp_hidden, self.H, bias=False),
        )

        # Output projection to target dimension (e.g., 768)
        self.out_proj = nn.Linear(self.H, self.output_dim, bias=False) if self.output_dim != self.H else nn.Identity()

    def forward(self, hidden_states: torch.Tensor, attention_mask: torch.Tensor, eos_emb: torch.Tensor) -> torch.Tensor:
        # hidden_states: [B,T,H], eos_emb: [B,H]
        B, T, H = hidden_states.shape
        orig_dtype = hidden_states.dtype
        assert H == self.H

        # LayerNorm in native dtype, then convert to float32 for numerical stability
        x = self.ln_x(hidden_states).float()                                  # [B,T,H] float32
        D = self.ln_d(self.dict_latents).float()                              # [S,K,H] float32

        if self.cond_on_eos:
            cond = torch.tanh(self.eos_proj(eos_emb).float())                 # [B,H] float32
            Q = D.unsqueeze(0) + cond[:, None, None, :]                       # [B,S,K,H]
        else:
            Q = D.unsqueeze(0).expand(B, -1, -1, -1)

        # [B,S,K,T]
        scores = torch.einsum("bth,bskh->bskt", x, Q) * self.scale_tok
        scores = scores.masked_fill(attention_mask[:, None, None, :] == 0, -1e4)

        attn = torch.softmax(scores, dim=-1)
        attn = self.drop(attn)

        # [B,S,K,H]
        pooled_lat = torch.einsum("bskt,bth->bskh", attn, x)

        # merge K -> 1
        merge_scores = torch.einsum("bskh,sh->bsk", pooled_lat, self.merge_q.float()) * self.scale_merge
        merge_attn = torch.softmax(merge_scores, dim=-1)
        merge_attn = self.drop(merge_attn)

        pooled = torch.einsum("bskh,bsk->bsh", pooled_lat, merge_attn)        # [B,S,H]

        y = pooled + self.mlp(pooled.to(orig_dtype)).float()
        y = self.out_proj(y.to(orig_dtype)).float()  # project to output_dim
        y = F.normalize(y, p=2, dim=-1, eps=1e-12)
        return y.to(dtype=orig_dtype)


# -----------------------------
# Stage-3 model wrapper
# -----------------------------
class Stage3Model(nn.Module):
    """
    Holds frozen encoder + trainable pooler (+ optional logit_scale, per-section bias).

    IMPORTANT:
      Trainer will call model.train().
      We override train() to keep encoder in eval() ALWAYS,
      so EOS embeddings are truly fixed (no dropout noise).
    """
    def __init__(
        self,
        encoder: nn.Module,
        pooler: LatentDictSectionPooler,
        learn_temperature: bool,
        logit_scale_init: float,
        learn_logit_bias: bool,
        logit_bias_init: float,
        encoder_hidden_size: int,
    ):
        super().__init__()
        self.encoder = encoder
        self.pooler = pooler

        freeze_all_parameters(self.encoder)
        self.encoder.eval()

        device = next(self.pooler.parameters()).device

        # Doc-side projection if output_dim differs from encoder hidden_size
        if self.pooler.output_dim != encoder_hidden_size:
            self.doc_proj = nn.Linear(encoder_hidden_size, self.pooler.output_dim, bias=False).to(device)
        else:
            self.doc_proj = None

        if learn_temperature:
            self.logit_scale = nn.Parameter(torch.tensor(float(logit_scale_init), device=device, dtype=torch.float32))

        if learn_logit_bias:
            self.section_logit_bias = nn.ParameterDict({
                str(i): nn.Parameter(torch.tensor(float(logit_bias_init), device=device, dtype=torch.float32))
                for i in range(len(ANATOMY_COLUMNS))
            })

    def train(self, mode: bool = True):
        # Only pooler is trainable; encoder stays eval
        self.pooler.train(mode)
        self.encoder.eval()
        return self


# -----------------------------
# Trainer (compute_loss implements your exact pairing)
# -----------------------------
class Stage3Trainer(Trainer):
    def __init__(
        self,
        temperature: float,
        learn_temperature: bool,
        logit_scale_max: float,
        sigmoid_pos_weight_cap: float,
        sigmoid_pow_alpha: float,
        sigmoid_symmetric: bool,
        **kw,
    ):
        super().__init__(**kw)
        self.temperature = float(temperature)
        self.learn_temperature = bool(learn_temperature)
        self.logit_scale_max = float(logit_scale_max)
        self.loss_fn = MultiPositiveSigmoidLoss(
            symmetric=bool(sigmoid_symmetric),
            pos_weight_cap=float(sigmoid_pos_weight_cap),
            pow_alpha=float(sigmoid_pow_alpha),
        )

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        sm = model.module if hasattr(model, "module") else model
        assert isinstance(sm, Stage3Model)

        B = int(inputs["B"])
        S = int(inputs["S"])
        q = inputs["q"]
        d = inputs["d"]
        pos_id_local = inputs["pos_id"].to(torch.long)  # [B,S]

        device = next(sm.pooler.parameters()).device

        # scale
        if self.learn_temperature and hasattr(sm, "logit_scale"):
            scale = sm.logit_scale.float().exp().clamp(max=self.logit_scale_max)
        else:
            scale = 1.0 / self.temperature

        # per-section bias helper
        bias_store = getattr(sm, "section_logit_bias", None)
        def bias_for_section(s_idx: int) -> Optional[torch.Tensor]:
            if not isinstance(bias_store, nn.ParameterDict):
                return None
            return bias_store[str(int(s_idx))].float()

        # move batch to device
        q_ids = q["input_ids"].to(device, non_blocking=True)
        q_mask = q["attention_mask"].to(device, non_blocking=True)
        d_ids = d["input_ids"].to(device, non_blocking=True)
        d_mask = d["attention_mask"].to(device, non_blocking=True)

        # ---------------------------
        # Query side: frozen encoder on (instruction + o)
        # ---------------------------
        with torch.no_grad():
            h_o = get_last_hidden_state(sm.encoder, q_ids, q_mask)  # [B,Tq,H]
            g_o = last_token_pool(h_o, q_mask)                      # [B,H]  (fixed)
        # Trainable pooler => 9 section embeddings q_s
        q_sections = sm.pooler(h_o, q_mask, g_o)                    # [B,S,H]

        # ---------------------------
        # Doc side: frozen encoder on each section text r_s
        # ---------------------------
        with torch.no_grad():
            h_r = get_last_hidden_state(sm.encoder, d_ids, d_mask)  # [B*S,Td,H]
            eos_r = last_token_pool(h_r, d_mask)                    # [B*S,H] (fixed)
        # Project doc embeddings to match query output_dim if needed
        if sm.doc_proj is not None:
            eos_r = sm.doc_proj(eos_r.to(dtype=q_sections.dtype))
        eos_r = F.normalize(eos_r.float(), p=2, dim=-1, eps=1e-12)
        d_sections = eos_r.to(dtype=q_sections.dtype).view(B, S, -1)  # [B,S,output_dim]

        # ---------------------------
        # Cross-GPU gather => in-batch negatives
        # ---------------------------
        q_all = all_gather_embeddings(q_sections.reshape(B * S, -1)).view(-1, S, q_sections.size(-1))
        d_all = all_gather_embeddings(d_sections.reshape(B * S, -1)).view(-1, S, d_sections.size(-1))
        pos_id_all = all_gather_1d_long(pos_id_local.reshape(-1)).view(-1, S)

        # ---------------------------
        # Loss per section
        # ---------------------------
        total = torch.tensor(0.0, device=device)
        for s_idx in range(S):
            qe = q_sections[:, s_idx, :]      # [B,H]
            de = d_sections[:, s_idx, :]      # [B,H]
            qe_all = q_all[:, s_idx, :]       # [Bg,H]
            de_all = d_all[:, s_idx, :]       # [Bg,H]

            logits_q2d = (qe.float() @ de_all.float().T) * scale
            logits_d2q = (de.float() @ qe_all.float().T) * scale

            # multi-positive mask via stable hash ids (so duplicates across batch/GPU become positives)
            pid_l = pos_id_local[:, s_idx].to(device)
            pid_g = pos_id_all[:, s_idx].to(device)
            pos_mask = pid_l.unsqueeze(1).eq(pid_g.unsqueeze(0))  # [B,Bg]

            b = bias_for_section(s_idx)
            loss_s = self.loss_fn(
                logits_q2d=logits_q2d,
                pos_mask_q2d=pos_mask,
                logits_d2q=logits_d2q,
                pos_mask_d2q=pos_mask,
                logit_bias=b,
            )
            total = total + loss_s

        loss = total / float(S)
        return (loss, {"loss": loss}) if return_outputs else loss


# -----------------------------
# Saving
# -----------------------------
class SaveCallback(TrainerCallback):
    def __init__(self, out_dir: str):
        self.out_dir = out_dir

    def on_save(self, args, state, control, model=None, **kwargs):
        if model is None:
            return control
        ckpt = os.path.join(self.out_dir, f"checkpoint-{state.global_step}")
        os.makedirs(ckpt, exist_ok=True)
        save_artifacts(model, ckpt)
        return control


def save_artifacts(model, out_dir: str):
    sm = model.module if hasattr(model, "module") else model

    if is_main_process():
        torch.save(sm.pooler.state_dict(), os.path.join(out_dir, "section_pooler.pt"))
        cfg = {
            "pooler_type": "latent_dict",
            "sections": ANATOMY_COLUMNS,
            "hidden_size": sm.pooler.H,
            "num_latents": sm.pooler.K,
            "cond_on_eos": sm.pooler.cond_on_eos,
            "output_dim": sm.pooler.output_dim,
        }
        with open(os.path.join(out_dir, "section_pooler_config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    # Save doc projection if it exists
    if sm.doc_proj is not None:
        t = gather_param_to_cpu(sm.doc_proj.weight)
        if is_main_process():
            torch.save({"weight": t}, os.path.join(out_dir, "doc_proj.pt"))

    if hasattr(sm, "logit_scale"):
        t = gather_param_to_cpu(sm.logit_scale)
        if is_main_process():
            torch.save(t, os.path.join(out_dir, "logit_scale.pt"))

    bias_store = getattr(sm, "section_logit_bias", None)
    if isinstance(bias_store, nn.ParameterDict):
        bias_cpu = {}
        for k in sorted(bias_store.keys(), key=lambda x: int(x)):
            t = gather_param_to_cpu(bias_store[k])
            if is_main_process():
                bias_cpu[str(k)] = t
        if is_main_process():
            torch.save(bias_cpu, os.path.join(out_dir, "section_logit_biases.pt"))


# -----------------------------
# Main
# -----------------------------
def main():
    ap = ArgumentParser()

    # pretrained encoder first
    ap.add_argument("--pretrained", required=True, help="Stage2: adapter dir OR full model dir OR HF id (e.g., lukeingawesome/chest2vec_0.6b_chest)")
    ap.add_argument("--base_override", default=None, help="only needed if --pretrained is adapter dir lacking base_model_name_or_path")
    ap.add_argument("--use_chest2vec_loader", action="store_true", help="Load model from HF Hub using Chest2Vec wrapper (recommended for published models like lukeingawesome/chest2vec_0.6b_chest)")
    ap.add_argument("--use_4bit", action="store_true")
    ap.add_argument("--attn_impl", default=None, choices=["flash_attention_2", "sdpa"])

    # data
    ap.add_argument("--df", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--train_split", default="train")
    ap.add_argument("--val_split", default="val")
    ap.add_argument("--no_val", action="store_true")

    ap.add_argument("--findings_col", default="findings")
    ap.add_argument("--require_nonempty", action="store_true", default=True)
    ap.add_argument("--no_require_nonempty", dest="require_nonempty", action="store_false")

    # token lengths
    ap.add_argument("--max_len_query", type=int, default=2048)
    ap.add_argument("--max_len_section", type=int, default=512)

    # pooler
    ap.add_argument("--num_latents", type=int, default=8)
    ap.add_argument("--mlp_hidden", type=int, default=0)
    ap.add_argument("--pool_dropout", type=float, default=0.1)
    ap.add_argument("--no_layernorm", action="store_true")
    ap.add_argument("--cond_on_eos", action="store_true", default=True)
    ap.add_argument("--no_cond_on_eos", dest="cond_on_eos", action="store_false")
    ap.add_argument("--output_dim", type=int, default=None, help="Output embedding dimension (default: same as encoder hidden_size, e.g., 768)")

    # training
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--per_device_bs", type=int, default=32)
    ap.add_argument("--grad_accum", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--weight_decay", type=float, default=0.01)
    ap.add_argument("--max_grad_norm", type=float, default=1.0)
    ap.add_argument("--deepspeed", default=None)

    # sigmoid + temperature + bias
    ap.add_argument("--temperature", type=float, default=0.05)
    ap.add_argument("--learn_temperature", action="store_true", default=True)
    ap.add_argument("--no_learn_temperature", dest="learn_temperature", action="store_false")
    ap.add_argument("--logit_scale_init", type=float, default=2.659)
    ap.add_argument("--logit_scale_max", type=float, default=100.0)

    ap.add_argument("--learn_logit_bias", action="store_true", default=True)
    ap.add_argument("--no_learn_logit_bias", dest="learn_logit_bias", action="store_false")
    ap.add_argument("--logit_bias_init", type=float, default=-6.5)

    ap.add_argument("--sigmoid_pos_weight_cap", type=float, default=1024.0)
    ap.add_argument("--sigmoid_pow_alpha", type=float, default=0.5)
    ap.add_argument("--no_sigmoid_symmetric", action="store_true")

    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    local_rank = get_local_rank()
    attn_impl = args.attn_impl or choose_attn_impl()

    tok, encoder = load_pretrained_encoder(
        args.pretrained,
        base_override=args.base_override,
        use_4bit=bool(args.use_4bit),
        attn_impl=attn_impl,
        local_rank=local_rank,
        use_chest2vec_loader=bool(args.use_chest2vec_loader),
    )

    # determine hidden size robustly
    with torch.no_grad():
        dev = next(encoder.parameters()).device
        test = encode_with_eos_ids(tok, ["test"], max_len=32)
        h = get_last_hidden_state(encoder, test["input_ids"].to(dev), test["attention_mask"].to(dev))
        hidden_size = int(last_token_pool(h, test["attention_mask"].to(dev)).size(1))

    if is_main_process():
        print(f"[hidden_size] {hidden_size}")

    device = next(encoder.parameters()).device
    output_dim = int(args.output_dim) if args.output_dim else hidden_size
    pooler = LatentDictSectionPooler(
        hidden_size=hidden_size,
        num_sections=len(ANATOMY_COLUMNS),
        num_latents=int(args.num_latents),
        mlp_hidden=(int(args.mlp_hidden) if args.mlp_hidden and args.mlp_hidden > 0 else hidden_size),
        dropout=float(args.pool_dropout),
        use_layernorm=(not args.no_layernorm),
        cond_on_eos=bool(args.cond_on_eos),
        output_dim=output_dim,
    ).to(device=device, dtype=torch.bfloat16 if device.type == "cuda" else torch.float32)

    if is_main_process():
        print(f"[output_dim] {output_dim}")

    model = Stage3Model(
        encoder=encoder,
        pooler=pooler,
        learn_temperature=bool(args.learn_temperature),
        logit_scale_init=float(args.logit_scale_init),
        learn_logit_bias=bool(args.learn_logit_bias),
        logit_bias_init=float(args.logit_bias_init),
        encoder_hidden_size=hidden_size,
    )

    if is_main_process():
        trainable = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
        print(f"[trainable] tensors={len(trainable)} total_params={sum(p.numel() for _, p in trainable):,}")
        for n, p in trainable[:30]:
            print(f"  {n} {tuple(p.shape)}")

    train_ds = Stage3AnatomyDataset(
        df_path=args.df,
        split=args.train_split,
        findings_col=args.findings_col,
        require_nonempty=bool(args.require_nonempty),
    )
    if len(train_ds) == 0:
        raise ValueError("Training dataset empty after filtering.")

    val_ds = None
    if not args.no_val:
        val_ds = Stage3AnatomyDataset(
            df_path=args.df,
            split=args.val_split,
            findings_col=args.findings_col,
            require_nonempty=bool(args.require_nonempty),
        )
        if len(val_ds) == 0:
            if is_main_process():
                print("[WARN] val empty; disabling.")
            val_ds = None

    collate = Stage3AnatomyCollator(tok, max_len_query=args.max_len_query, max_len_section=args.max_len_section)

    sigmoid_symmetric = not args.no_sigmoid_symmetric

    # Compute max_steps explicitly (DeepSpeed wraps the dataloader and drops __len__)
    world_size = int(os.environ.get("WORLD_SIZE", 1))
    total_batch = args.per_device_bs * world_size * args.grad_accum
    steps_per_epoch = len(train_ds) // total_batch  # drop_last=True
    max_steps = steps_per_epoch * args.epochs
    if is_main_process():
        print(f"[steps] {len(train_ds)} samples, world_size={world_size}, "
              f"total_batch={total_batch}, steps_per_epoch={steps_per_epoch}, max_steps={max_steps}")

    targs = TrainingArguments(
        output_dir=args.out,
        max_steps=max_steps,
        per_device_train_batch_size=args.per_device_bs,
        per_device_eval_batch_size=args.per_device_bs,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        weight_decay=args.weight_decay,
        max_grad_norm=args.max_grad_norm,
        logging_steps=50,
        save_strategy="epoch",
        save_total_limit=2,
        bf16=True,
        dataloader_drop_last=True,
        deepspeed=args.deepspeed,
        report_to=[],
    )

    trainer = Stage3Trainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collate,
        callbacks=[SaveCallback(args.out)],
        temperature=args.temperature,
        learn_temperature=bool(args.learn_temperature),
        logit_scale_max=float(args.logit_scale_max),
        sigmoid_pos_weight_cap=float(args.sigmoid_pos_weight_cap),
        sigmoid_pow_alpha=float(args.sigmoid_pow_alpha),
        sigmoid_symmetric=bool(sigmoid_symmetric),
    )

    trainer.train()

    # final save
    save_artifacts(trainer.model, args.out)
    if is_main_process():
        tok.save_pretrained(args.out)
        print(f"[final] saved to {args.out}")


if __name__ == "__main__":
    main()
