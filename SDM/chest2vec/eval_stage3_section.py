#!/usr/bin/env python3
"""
Evaluation script for Stage-3 section pooler (LatentDictSectionPooler).

Matches the training logic in stage3_section.py:
  Query side:  findings text o  -> frozen encoder -> H_o, g_o -> pooler -> q_s  (section embeddings)
  Doc side:    section text r_s -> frozen encoder -> EOS embedding d_s (L2 normalized)

Per-section retrieval with recall@k on the 'test' split of the same dataframe.
"""

import os
import json
import math
import argparse
import hashlib
from typing import Dict, Tuple, List, Optional

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

import torch
import torch.nn as nn
import torch.nn.functional as F

from transformers import AutoTokenizer, AutoModel, BitsAndBytesConfig

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

try:
    from huggingface_hub import snapshot_download
    _HAS_HUB = True
except Exception:
    snapshot_download = None
    _HAS_HUB = False


# ─────────────────────────────────────────────
# Constants (MUST match training)
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
# Text utilities (identical to stage3_section.py)
# ─────────────────────────────────────────────
def canonicalize_text(s: str) -> str:
    return " ".join(str(s).strip().split())


def stable_int64_hash(text: str) -> int:
    h = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "little", signed=True)


def get_pool_token_id(tok) -> int:
    eod_id = tok.convert_tokens_to_ids("<|endoftext|>")
    if eod_id is None or eod_id < 0:
        eod_id = tok.pad_token_id
    return eod_id


def encode_with_eos_ids(tok, texts: List[str], max_len: int) -> Dict[str, torch.Tensor]:
    """Must match training: no special tokens, truncate, append EOS, left-pad."""
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


def get_last_hidden_state(model, input_ids, attention_mask):
    """AutoModel last_hidden_state with explicit position_ids for left padding."""
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


def last_token_pool(last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        return last_hidden_states[:, -1]
    idx = attention_mask.sum(dim=1) - 1
    return last_hidden_states[torch.arange(last_hidden_states.size(0), device=last_hidden_states.device), idx]


def choose_attn_impl(prefer="flash_attention_2"):
    try:
        from transformers.modeling_flash_attention_utils import is_flash_attn_greater_or_equal_2
        if prefer == "flash_attention_2" and is_flash_attn_greater_or_equal_2():
            return "flash_attention_2"
    except Exception:
        pass
    return "sdpa"


# ─────────────────────────────────────────────
# LatentDictSectionPooler (copy from training)
# ─────────────────────────────────────────────
class LatentDictSectionPooler(nn.Module):
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
        B, T, H = hidden_states.shape
        orig_dtype = hidden_states.dtype
        assert H == self.H

        x = self.ln_x(hidden_states).float()
        D = self.ln_d(self.dict_latents).float()

        if self.cond_on_eos:
            cond = torch.tanh(self.eos_proj(eos_emb).float())
            Q = D.unsqueeze(0) + cond[:, None, None, :]
        else:
            Q = D.unsqueeze(0).expand(B, -1, -1, -1)

        scores = torch.einsum("bth,bskh->bskt", x, Q) * self.scale_tok
        scores = scores.masked_fill(attention_mask[:, None, None, :] == 0, -1e4)

        attn = torch.softmax(scores, dim=-1)
        # no dropout at eval
        pooled_lat = torch.einsum("bskt,bth->bskh", attn, x)

        merge_scores = torch.einsum("bskh,sh->bsk", pooled_lat, self.merge_q.float()) * self.scale_merge
        merge_attn = torch.softmax(merge_scores, dim=-1)

        pooled = torch.einsum("bskh,bsk->bsh", pooled_lat, merge_attn)

        y = pooled + self.mlp(pooled.to(orig_dtype)).float()
        y = self.out_proj(y.to(orig_dtype)).float()  # project to output_dim
        y = F.normalize(y, p=2, dim=-1, eps=1e-12)
        return y.to(dtype=orig_dtype)


# ─────────────────────────────────────────────
# Encoder loading (same 3 methods as training)
# ─────────────────────────────────────────────
def _resolve_repo_path(repo_id_or_path: str) -> str:
    if os.path.isdir(repo_id_or_path):
        return repo_id_or_path
    if not _HAS_HUB:
        raise RuntimeError("huggingface_hub is required to load by repo_id.")
    return snapshot_download(repo_id_or_path)


def load_encoder(
    pretrained: str,
    *,
    base_override: Optional[str],
    use_4bit: bool,
    attn_impl: str,
    device: str,
    use_chest2vec_loader: bool = False,
):
    if use_chest2vec_loader:
        if not _HAS_CHEST2VEC:
            raise RuntimeError("Chest2Vec package is not installed.")
        force_flash = (attn_impl == "flash_attention_2")
        chest2vec = Chest2Vec.from_pretrained(
            repo_id_or_path=pretrained,
            device=device,
            use_4bit=use_4bit,
            force_flash_attention_2=force_flash,
        )
        encoder = chest2vec.model
        tok = chest2vec.tokenizer
        tok.padding_side = "left"
        if tok.pad_token_id is None:
            tok.pad_token = tok.eos_token
        encoder.config.use_cache = False
        return tok, encoder

    is_dir = os.path.isdir(pretrained)
    adapter_cfg_path = os.path.join(pretrained, "adapter_config.json") if is_dir else None
    full_cfg_path = os.path.join(pretrained, "config.json") if is_dir else None
    is_adapter = bool(is_dir and adapter_cfg_path and os.path.exists(adapter_cfg_path) and not os.path.exists(full_cfg_path))

    qconf = None
    if use_4bit:
        qconf = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

    if is_adapter:
        if not _HAS_PEFT:
            raise RuntimeError("peft is required for adapter loading.")
        with open(adapter_cfg_path, "r") as f:
            acfg = json.load(f)
        base = base_override or acfg.get("base_model_name_or_path")
        if not base:
            raise ValueError("Adapter dir detected but base model unknown. Use --base_override.")
        tok = AutoTokenizer.from_pretrained(base, padding_side="left", trust_remote_code=True)
        if tok.pad_token_id is None:
            tok.pad_token = tok.eos_token
        base_model = AutoModel.from_pretrained(
            base, trust_remote_code=True, attn_implementation=attn_impl,
            quantization_config=qconf,
            torch_dtype=torch.bfloat16 if not use_4bit else None,
            device_map={"": device},
        )
        model = PeftModel.from_pretrained(base_model, pretrained, is_trainable=False)
        model.config.use_cache = False
        return tok, model

    tok = AutoTokenizer.from_pretrained(pretrained, padding_side="left", trust_remote_code=True)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModel.from_pretrained(
        pretrained, trust_remote_code=True, attn_implementation=attn_impl,
        quantization_config=qconf,
        torch_dtype=torch.bfloat16 if not use_4bit else None,
        device_map={"": device},
    )
    model.config.use_cache = False
    return tok, model


# ─────────────────────────────────────────────
# Pooler loading
# ─────────────────────────────────────────────
def load_pooler(pooler_dir: str, hidden_size: int) -> Tuple[LatentDictSectionPooler, Optional[nn.Linear]]:
    """
    Load pooler and optional doc_proj layer.
    Returns (pooler, doc_proj) where doc_proj may be None if output_dim == hidden_size.
    """
    resolved = _resolve_repo_path(pooler_dir)

    # search resolved dir then parent
    candidates = [resolved, os.path.dirname(resolved.rstrip("/"))]
    pt_path = cfg_path = doc_proj_path = ""
    for d in candidates:
        p1 = os.path.join(d, "section_pooler.pt")
        p2 = os.path.join(d, "section_pooler_config.json")
        p3 = os.path.join(d, "doc_proj.pt")
        if (not pt_path) and os.path.isfile(p1):
            pt_path = p1
        if (not cfg_path) and os.path.isfile(p2):
            cfg_path = p2
        if (not doc_proj_path) and os.path.isfile(p3):
            doc_proj_path = p3

    if not pt_path:
        raise FileNotFoundError(f"section_pooler.pt not found in {pooler_dir}")
    if not cfg_path:
        raise FileNotFoundError(f"section_pooler_config.json not found in {pooler_dir}")

    with open(cfg_path, "r") as f:
        cfg = json.load(f)

    pooler_type = cfg.get("pooler_type", "latent_dict")
    if pooler_type != "latent_dict":
        raise RuntimeError(
            f"This eval script is for pooler_type='latent_dict', got '{pooler_type}'. "
            "Use eval_stage_3_ct.py for query_attn poolers."
        )

    cfg_sections = cfg.get("sections", ANATOMY_COLUMNS)
    if list(cfg_sections) != ANATOMY_COLUMNS:
        print(f"[WARN] Section mismatch:\n  eval:   {ANATOMY_COLUMNS}\n  config: {cfg_sections}")
        print("  Continuing with config sections...")

    num_latents = int(cfg.get("num_latents", 8))
    cond_on_eos = bool(cfg.get("cond_on_eos", True))
    output_dim = int(cfg.get("output_dim", hidden_size))

    pooler = LatentDictSectionPooler(
        hidden_size=hidden_size,
        num_sections=len(cfg_sections),
        num_latents=num_latents,
        cond_on_eos=cond_on_eos,
        output_dim=output_dim,
    )

    sd = torch.load(pt_path, map_location="cpu")
    pooler.load_state_dict(sd, strict=True)
    pooler.eval()

    print(f"  pooler.pt:    {pt_path}")
    print(f"  config:       {cfg_path}")
    print(f"  num_latents:  {num_latents}")
    print(f"  cond_on_eos:  {cond_on_eos}")
    print(f"  hidden_size:  {hidden_size}")
    print(f"  output_dim:   {output_dim}")
    print(f"  sections:     {cfg_sections}")

    # Load doc_proj if output_dim differs from hidden_size
    doc_proj = None
    if output_dim != hidden_size:
        if doc_proj_path:
            doc_proj = nn.Linear(hidden_size, output_dim, bias=False)
            doc_proj_sd = torch.load(doc_proj_path, map_location="cpu")
            doc_proj.load_state_dict(doc_proj_sd, strict=True)
            doc_proj.eval()
            print(f"  doc_proj.pt:  {doc_proj_path}")
        else:
            print(f"[WARN] output_dim ({output_dim}) != hidden_size ({hidden_size}) but doc_proj.pt not found")

    return pooler, doc_proj


# ─────────────────────────────────────────────
# Encoding: query side (pooler -> 7 section embeddings)
# ─────────────────────────────────────────────
@torch.inference_mode()
def encode_queries(
    query_texts: List[str],
    *,
    tokenizer,
    encoder,
    pooler: LatentDictSectionPooler,
    max_len: int,
    batch_size: int,
    device: torch.device,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Returns (pooler_emb [N,S,H], global_eos_emb [N,H]) on CPU."""
    sec_outs = []
    eos_outs = []
    for i in tqdm(range(0, len(query_texts), batch_size), desc="Encode queries", unit="batch"):
        chunk = query_texts[i : i + batch_size]
        enc = encode_with_eos_ids(tokenizer, chunk, max_len)
        ids = enc["input_ids"].to(device, non_blocking=True)
        mask = enc["attention_mask"].to(device, non_blocking=True)

        h = get_last_hidden_state(encoder, ids, mask)       # [B,T,H]
        g = last_token_pool(h, mask)                         # [B,H]
        q_sec = pooler(h, mask, g)                           # [B,S,H]

        q_cpu = F.normalize(q_sec.float().cpu(), p=2, dim=-1)
        g_cpu = F.normalize(g.float().cpu(), p=2, dim=-1)
        sec_outs.append(q_cpu)
        eos_outs.append(g_cpu)

    return torch.cat(sec_outs, dim=0), torch.cat(eos_outs, dim=0)


# ─────────────────────────────────────────────
# Encoding: doc side (frozen encoder EOS -> L2 norm)
# ─────────────────────────────────────────────
@torch.inference_mode()
def encode_docs(
    doc_texts: List[str],
    *,
    tokenizer,
    encoder,
    max_len: int,
    batch_size: int,
    device: torch.device,
    doc_proj: Optional[nn.Module] = None,
) -> torch.Tensor:
    """Returns CPU tensor [N, output_dim] (or [N, H] if no doc_proj)."""
    outs = []
    for i in tqdm(range(0, len(doc_texts), batch_size), desc="Encode docs", unit="batch"):
        chunk = doc_texts[i : i + batch_size]
        enc = encode_with_eos_ids(tokenizer, chunk, max_len)
        ids = enc["input_ids"].to(device, non_blocking=True)
        mask = enc["attention_mask"].to(device, non_blocking=True)

        h = get_last_hidden_state(encoder, ids, mask)
        eos = last_token_pool(h, mask)

        # Apply doc projection if provided
        if doc_proj is not None:
            eos = doc_proj(eos)

        eos = F.normalize(eos.float(), p=2, dim=-1)

        outs.append(eos.cpu())

    return torch.cat(outs, dim=0)


# ─────────────────────────────────────────────
# Retrieval (chunked top-k)
# ─────────────────────────────────────────────
@torch.inference_mode()
def topk_retrieve(
    q_emb: torch.Tensor,   # [Nq, H]
    d_emb: torch.Tensor,   # [Nd, H]
    k: int,
    *,
    query_batch: int = 256,
    doc_chunk: int = 8192,
    device: str = "cuda",
) -> Tuple[torch.Tensor, torch.Tensor]:
    dev = torch.device(device)
    Nq, Nd = q_emb.size(0), d_emb.size(0)
    k = min(k, Nd)

    all_scores = torch.empty(Nq, k, dtype=torch.float32)
    all_indices = torch.empty(Nq, k, dtype=torch.long)

    for qs in tqdm(range(0, Nq, query_batch), desc="Retrieval", unit="batch"):
        qe = F.normalize(q_emb[qs : qs + query_batch].to(dev, dtype=torch.float32), p=2, dim=-1)
        bq = qe.size(0)
        top_s = torch.full((bq, k), -1e9, device=dev)
        top_i = torch.full((bq, k), -1, device=dev, dtype=torch.long)

        for ds in range(0, Nd, doc_chunk):
            de = F.normalize(d_emb[ds : ds + doc_chunk].to(dev, dtype=torch.float32), p=2, dim=-1)
            scores = qe @ de.T
            idx_off = torch.arange(ds, ds + de.size(0), device=dev).unsqueeze(0).expand(bq, -1)

            cs = torch.cat([top_s, scores], dim=1)
            ci = torch.cat([top_i, idx_off], dim=1)
            ns, pos = torch.topk(cs, k, dim=1)
            top_s, top_i = ns, ci.gather(1, pos)

        all_scores[qs : qs + bq] = top_s.cpu()
        all_indices[qs : qs + bq] = top_i.cpu()

    return all_scores, all_indices


def parse_ks(s: str) -> Tuple[int, ...]:
    return tuple(int(x.strip()) for x in s.split(",") if x.strip())


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Evaluate Stage-3 LatentDict section pooler")

    # Encoder
    ap.add_argument("--pretrained", required=True,
                     help="Same as training: adapter dir, full model, or HF id")
    ap.add_argument("--base_override", default=None)
    ap.add_argument("--use_chest2vec_loader", action="store_true")
    ap.add_argument("--use_4bit", action="store_true")
    ap.add_argument("--attn_impl", default=None, choices=["flash_attention_2", "sdpa"])

    # Pooler
    ap.add_argument("--pooler_dir", required=True,
                     help="Dir (or HF repo) with section_pooler.pt + section_pooler_config.json")

    # Data
    ap.add_argument("--df", required=True, help="Same CSV used for training (e.g. train_srrg.csv)")
    ap.add_argument("--split", default="test", help="Split to evaluate on")
    ap.add_argument("--findings_col", default="findings_section")

    # Encoding
    ap.add_argument("--max_len_query", type=int, default=512)
    ap.add_argument("--max_len_section", type=int, default=512)
    ap.add_argument("--embed_bs", type=int, default=16)
    ap.add_argument("--device", default="cuda:0")

    # Retrieval
    ap.add_argument("--ks", type=str, default="1,5,10")
    ap.add_argument("--query_batch_size", type=int, default=256)
    ap.add_argument("--doc_chunk_size", type=int, default=8192)
    ap.add_argument("--sim_device", default="cuda", choices=["cuda", "cpu"])
    ap.add_argument("--dedup_docs", action="store_true",
                     help="Deduplicate doc bank per section by canonical text")

    # Baseline
    ap.add_argument("--no_baseline", action="store_true",
                     help="Skip global-EOS baseline comparison")

    # Output
    ap.add_argument("--save_metrics_csv", default="", help="Save per-section metrics CSV")
    ap.add_argument("--save_retrievals", default="",
                     help="Directory to save per-section retrieval JSONs")

    args = ap.parse_args()
    ks = parse_ks(args.ks)
    device = args.device

    # ── Load data ────────────────────────────
    print("Loading data...")
    if args.df.lower().endswith(".parquet"):
        df = pd.read_parquet(args.df)
    elif args.df.lower().endswith((".jsonl",)):
        df = pd.read_json(args.df, lines=True)
    elif args.df.lower().endswith(".json"):
        df = pd.read_json(args.df)
    else:
        df = pd.read_csv(args.df, low_memory=False)

    needed = [args.findings_col] + ANATOMY_COLUMNS
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    if "split" in df.columns:
        df = df[df["split"].astype(str).str.lower() == args.split.lower()].reset_index(drop=True)
    print(f"  Split '{args.split}': {len(df)} rows")

    df[args.findings_col] = df[args.findings_col].fillna("").astype(str)
    for c in ANATOMY_COLUMNS:
        df[c] = df[c].fillna("").astype(str)

    # ── Load encoder ─────────────────────────
    attn_impl = args.attn_impl or choose_attn_impl()
    print(f"Loading encoder (attn_impl={attn_impl})...")
    tok, encoder = load_encoder(
        args.pretrained,
        base_override=args.base_override,
        use_4bit=args.use_4bit,
        attn_impl=attn_impl,
        device=device,
        use_chest2vec_loader=args.use_chest2vec_loader,
    )
    encoder.eval()

    # ── Determine hidden size ────────────────
    with torch.no_grad():
        dev = next(encoder.parameters()).device
        test_enc = encode_with_eos_ids(tok, ["test"], max_len=32)
        h = get_last_hidden_state(encoder, test_enc["input_ids"].to(dev), test_enc["attention_mask"].to(dev))
        hidden_size = int(last_token_pool(h, test_enc["attention_mask"].to(dev)).size(1))
    print(f"  hidden_size: {hidden_size}")

    # ── Load pooler ──────────────────────────
    print("Loading pooler...")
    pooler, doc_proj = load_pooler(args.pooler_dir, hidden_size)
    pooler = pooler.to(device=dev, dtype=next(encoder.parameters()).dtype)
    pooler.eval()
    if doc_proj is not None:
        doc_proj = doc_proj.to(device=dev, dtype=next(encoder.parameters()).dtype)
        doc_proj.eval()

    # ── Build query texts ────────────────────
    query_texts = [
        str(row[args.findings_col]).strip()
        for _, row in df.iterrows()
    ]

    # ── Encode all queries (-> [N, S, H] + [N, H]) ──
    print("Encoding queries (all sections + global EOS)...")
    q_emb_all, q_eos_all = encode_queries(
        query_texts,
        tokenizer=tok,
        encoder=encoder,
        pooler=pooler,
        max_len=args.max_len_query,
        batch_size=args.embed_bs,
        device=dev,
    )
    print(f"  q_emb_all (pooler):  {tuple(q_emb_all.shape)}")
    print(f"  q_eos_all (global):  {tuple(q_eos_all.shape)}")

    run_baseline = not args.no_baseline
    # Disable baseline if output_dim differs from hidden_size (dimensions won't match)
    if run_baseline and doc_proj is not None:
        print("[INFO] Baseline disabled: output_dim != hidden_size (q_eos and d_emb have different dimensions)")
        run_baseline = False

    # ── Per-section retrieval ────────────────
    results_pooler = []
    results_baseline = []

    for s_idx, sname in enumerate(ANATOMY_COLUMNS):
        section_texts = df[sname].tolist()
        keep = [i for i, t in enumerate(section_texts) if str(t).strip() != ""]
        if not keep:
            print(f"[WARN] section '{sname}' has no non-empty rows; skipping.")
            continue

        q_emb = q_emb_all[keep, s_idx, :]  # [Nq, H]  (pooler)
        q_eos = q_eos_all[keep, :]          # [Nq, H]  (global EOS)
        target_ids = np.array(
            [stable_int64_hash(canonicalize_text(section_texts[i])) for i in keep],
            dtype=np.int64,
        )

        # Build doc bank
        if args.dedup_docs:
            seen = {}
            doc_texts, doc_canon = [], []
            for t in section_texts:
                c = canonicalize_text(t)
                if not c:
                    continue
                if c not in seen:
                    seen[c] = len(doc_texts)
                    doc_texts.append(t)
                    doc_canon.append(c)
            doc_ids = np.array([stable_int64_hash(c) for c in doc_canon], dtype=np.int64)
        else:
            doc_texts = [t for t in section_texts if str(t).strip() != ""]
            doc_ids = np.array(
                [stable_int64_hash(canonicalize_text(t)) for t in doc_texts],
                dtype=np.int64,
            )

        if not doc_texts:
            print(f"[WARN] section '{sname}' doc bank empty; skipping.")
            continue

        print(f"\n── {sname} ({len(keep)} queries, {len(doc_texts)} docs) ──")

        d_emb = encode_docs(
            doc_texts,
            tokenizer=tok,
            encoder=encoder,
            max_len=args.max_len_section,
            batch_size=args.embed_bs,
            device=dev,
            doc_proj=doc_proj,
        )

        kmax = min(max(ks), len(doc_texts))

        # --- Pooler retrieval ---
        top_scores, top_indices = topk_retrieve(
            q_emb, d_emb, kmax,
            query_batch=args.query_batch_size,
            doc_chunk=args.doc_chunk_size,
            device=args.sim_device,
        )
        top_idx = top_indices.numpy()
        retrieved_ids = doc_ids[top_idx]
        top_scores_np = top_scores.numpy()

        print(f"  [pooler]   sim range: [{float(top_scores_np.min()):.4f}, {float(top_scores_np.max()):.4f}]")

        metrics_p = {"section": sname, "num_queries": len(keep), "num_docs": len(doc_texts)}
        for k in ks:
            k_eff = min(int(k), kmax)
            hits = (retrieved_ids[:, :k_eff] == target_ids[:, None]).any(axis=1)
            metrics_p[f"recall@{k_eff}"] = float(hits.mean())
        results_pooler.append(metrics_p)

        # --- Baseline (global EOS) retrieval ---
        if run_baseline:
            bl_scores, bl_indices = topk_retrieve(
                q_eos, d_emb, kmax,
                query_batch=args.query_batch_size,
                doc_chunk=args.doc_chunk_size,
                device=args.sim_device,
            )
            bl_idx = bl_indices.numpy()
            bl_retrieved = doc_ids[bl_idx]
            bl_scores_np = bl_scores.numpy()

            print(f"  [baseline] sim range: [{float(bl_scores_np.min()):.4f}, {float(bl_scores_np.max()):.4f}]")

            metrics_b = {"section": sname, "num_queries": len(keep), "num_docs": len(doc_texts)}
            for k in ks:
                k_eff = min(int(k), kmax)
                hits_b = (bl_retrieved[:, :k_eff] == target_ids[:, None]).any(axis=1)
                metrics_b[f"recall@{k_eff}"] = float(hits_b.mean())
            results_baseline.append(metrics_b)

        # Print side-by-side for this section
        for k in ks:
            k_eff = min(int(k), kmax)
            p_val = metrics_p[f"recall@{k_eff}"]
            if run_baseline:
                b_val = metrics_b[f"recall@{k_eff}"]
                delta = p_val - b_val
                sign = "+" if delta >= 0 else ""
                print(f"  recall@{k_eff}:  pooler={p_val:.6f}  baseline={b_val:.6f}  delta={sign}{delta:.6f}")
            else:
                print(f"  recall@{k_eff}:  pooler={p_val:.6f}")

        # ── Save per-section retrieval details ──
        if args.save_retrievals:
            os.makedirs(args.save_retrievals, exist_ok=True)
            out_file = os.path.join(
                args.save_retrievals,
                f"retrievals_{sname.replace(' ', '_').replace('&', 'and')}.json",
            )
            retrieval_data = {
                "section": sname,
                "num_queries": len(keep),
                "num_docs": len(doc_texts),
                "kmax": int(kmax),
                "queries": [
                    {
                        "query_idx": int(keep[i]),
                        "query_text": str(query_texts[keep[i]]),
                        "target_id": int(target_ids[i]),
                        "target_text": str(section_texts[keep[i]]),
                        "retrieved": [
                            {
                                "rank": int(r + 1),
                                "doc_idx": int(top_idx[i, r]),
                                "doc_id": int(retrieved_ids[i, r]),
                                "similarity": float(top_scores_np[i, r]),
                                "is_hit": bool(retrieved_ids[i, r] == target_ids[i]),
                                "doc_text": str(doc_texts[top_idx[i, r]]),
                            }
                            for r in range(kmax)
                        ],
                        "found_at_rank": int(
                            np.where(retrieved_ids[i] == target_ids[i])[0][0] + 1
                        )
                        if (retrieved_ids[i] == target_ids[i]).any()
                        else -1,
                    }
                    for i in range(len(keep))
                ],
            }
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(retrieval_data, f, indent=2, ensure_ascii=False)
            print(f"  Saved -> {out_file}")

    # ── Summary ──────────────────────────────
    if not results_pooler:
        raise RuntimeError("No section produced results.")

    recall_cols = [c for c in results_pooler[0] if c.startswith("recall@")]

    # ── Pooler results ──
    pooler_df = pd.DataFrame(results_pooler)
    pooler_macro = {c: float(pooler_df[c].mean()) for c in recall_cols}

    if run_baseline and results_baseline:
        baseline_df = pd.DataFrame(results_baseline)
        baseline_macro = {c: float(baseline_df[c].mean()) for c in recall_cols}

        # Build comparison table
        print("\n" + "=" * 90)
        print("  COMPARISON: Section Pooler vs Global EOS Baseline")
        print("=" * 90)

        header = f"{'Section':<35}"
        for c in recall_cols:
            k_label = c.replace("recall@", "R@")
            header += f" {'pooler':>8} {'base':>8} {'delta':>8} |"
        # print column group headers
        col_header = f"{'':35}"
        for c in recall_cols:
            k_label = c.replace("recall@", "R@")
            col_header += f"  ──── {k_label} ────  |"
        print(col_header)
        print(header)
        print("-" * 90)

        for i, row_p in pooler_df.iterrows():
            row_b = baseline_df.iloc[i]
            line = f"{row_p['section']:<35}"
            for c in recall_cols:
                pv = row_p[c]
                bv = row_b[c]
                d = pv - bv
                sign = "+" if d >= 0 else ""
                line += f" {pv:>8.4f} {bv:>8.4f} {sign}{d:>7.4f} |"
            print(line)

        print("-" * 90)
        macro_line = f"{'MACRO AVG':<35}"
        for c in recall_cols:
            pv = pooler_macro[c]
            bv = baseline_macro[c]
            d = pv - bv
            sign = "+" if d >= 0 else ""
            macro_line += f" {pv:>8.4f} {bv:>8.4f} {sign}{d:>7.4f} |"
        print(macro_line)
        print("=" * 90)
    else:
        print("\n==== Per-section metrics (pooler) ====")
        print(pooler_df.to_string(index=False))
        print("\n==== Macro avg ====")
        for c in recall_cols:
            print(f"  {c}: {pooler_macro[c]:.6f}")

    if args.save_metrics_csv:
        # Build combined CSV with both pooler and baseline columns
        save_rows = []
        for i, row_p in pooler_df.iterrows():
            r = {
                "section": row_p["section"],
                "num_queries": row_p["num_queries"],
                "num_docs": row_p["num_docs"],
            }
            for c in recall_cols:
                r[f"pooler_{c}"] = row_p[c]
            if run_baseline and results_baseline:
                row_b = baseline_df.iloc[i]
                for c in recall_cols:
                    r[f"baseline_{c}"] = row_b[c]
                    r[f"delta_{c}"] = row_p[c] - row_b[c]
            save_rows.append(r)

        # Macro row
        macro_r = {"section": "MACRO_AVG", "num_queries": "", "num_docs": ""}
        for c in recall_cols:
            macro_r[f"pooler_{c}"] = pooler_macro[c]
        if run_baseline and results_baseline:
            for c in recall_cols:
                macro_r[f"baseline_{c}"] = baseline_macro[c]
                macro_r[f"delta_{c}"] = pooler_macro[c] - baseline_macro[c]
        save_rows.append(macro_r)

        save_df = pd.DataFrame(save_rows)
        save_df.to_csv(args.save_metrics_csv, index=False)
        print(f"\nSaved metrics -> {args.save_metrics_csv}")


if __name__ == "__main__":
    main()
