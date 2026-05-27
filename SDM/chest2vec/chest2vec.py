import os
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F

from transformers import AutoTokenizer, AutoModel, BitsAndBytesConfig

try:
    from peft import PeftModel
    _HAS_PEFT = True
except Exception:
    PeftModel = None
    _HAS_PEFT = False

try:
    from huggingface_hub import snapshot_download
    _HAS_HUB = True
except Exception:
    snapshot_download = None
    _HAS_HUB = False


def require_flash_attention_2() -> str:
    if not torch.cuda.is_available():
        raise RuntimeError("FlashAttention-2 requires CUDA, but torch.cuda.is_available() is False.")
    try:
        import flash_attn  # noqa: F401
        ver = getattr(flash_attn, "__version__", "0.0.0")
        major = int(str(ver).split(".")[0])
        if major < 2:
            raise RuntimeError(f"flash-attn version {ver} < 2.0.0")
    except Exception as e:
        raise RuntimeError(
            "FlashAttention-2 is REQUIRED but not available/importable.\n"
            "Install flash-attn>=2 and ensure it matches your torch/CUDA.\n"
            f"Import/Version error: {repr(e)}"
        )
    return "flash_attention_2"


def build_qwen_query(instruction: str, query: str) -> str:
    instruction = str(instruction).strip()
    query = str(query).strip()
    return f"Instruct: {instruction}\nQuery: {query}"


def get_pool_token_id(tok) -> int:
    eod_id = tok.convert_tokens_to_ids("<|endoftext|>")
    if eod_id is None or eod_id < 0:
        eod_id = tok.pad_token_id
    return eod_id


def encode_with_eos_ids(tok, texts: List[str], max_len: int) -> Dict[str, torch.Tensor]:
    """
    Encode texts with guaranteed <|endoftext|> at the end for Qwen3-Embedding pooling.
    Reserves 1 slot for <|endoftext|>, left-pads to batch max length.
    Must match the training tokenization exactly.
    """
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    eod_id = get_pool_token_id(tok)

    # Reserve 1 position for <|endoftext|>
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

    # Left-pad to batch max length
    T = max(len(ids) for ids in input_ids) if input_ids else 1
    input_ids = [[pad_id] * (T - len(ids)) + ids for ids in input_ids]
    attn_mask = [[0] * (T - len(m)) + m for m in attn_mask]

    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "attention_mask": torch.tensor(attn_mask, dtype=torch.long),
    }


def last_token_pool(last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """
    Left-padding aware last-token pooling (extracts EOS token embedding).
    """
    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        return last_hidden_states[:, -1]
    idx = attention_mask.sum(dim=1) - 1
    return last_hidden_states[torch.arange(last_hidden_states.size(0), device=last_hidden_states.device), idx]


def get_last_hidden_state(model, input_ids, attention_mask):
    """
    Get final hidden state from the model.
    Provide position_ids for left padding (FlashAttention-2).
    """
    m = model.module if hasattr(model, "module") else model

    # Compute position_ids for left-padded sequences (required for flash_attention_2)
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


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_repo_path(repo_id_or_path: str) -> str:
    # If it's a local directory, use it as-is.
    if os.path.isdir(repo_id_or_path):
        return repo_id_or_path
    # Otherwise treat as HF repo_id and download snapshot.
    if not _HAS_HUB:
        raise RuntimeError(
            "huggingface_hub is required to load by repo_id. "
            "Install it: pip install huggingface_hub"
        )
    return snapshot_download(repo_id_or_path)


@dataclass
class EmbedOutput:
    """
    Simplified output: only global embeddings (no section embeddings).
    """
    embedding: torch.Tensor  # [N,H], float32 on CPU by default


class Chest2Vec:
    """
    Simplified wrapper for global embeddings only:
      - loads base Qwen3-Embedding
      - applies LoRA adapter
      - returns global embeddings via last-token pooling
    """
    def __init__(self, tokenizer, model, device: torch.device):
        self.tokenizer = tokenizer
        self.model = model
        self.device = device

        self.model.eval()

    @classmethod
    def from_pretrained(
        cls,
        repo_id_or_path: str,
        *,
        device: str = "cuda:0",
        use_4bit: bool = False,
        force_flash_attention_2: bool = True,
    ) -> "Chest2Vec":
        repo_path = _resolve_repo_path(repo_id_or_path)

        cfg_path = os.path.join(repo_path, "chest2vec_config.json")
        if not os.path.isfile(cfg_path):
            raise FileNotFoundError(f"Missing chest2vec_config.json in {repo_path}")
        cfg = _read_json(cfg_path)

        base_model = str(cfg["base_model"])
        adapter_subdir = str(cfg.get("adapter_subdir", "contrastive"))

        if force_flash_attention_2 or bool(cfg.get("require_flash_attention_2", False)):
            attn_impl = require_flash_attention_2()
        else:
            attn_impl = "sdpa"

        if not _HAS_PEFT:
            raise RuntimeError("peft is required. Install: pip install peft")

        device_t = torch.device(device)

        tokenizer = AutoTokenizer.from_pretrained(base_model, padding_side="left", trust_remote_code=True)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token

        device_map = {"": str(device_t)}

        # Load base model with FlashAttention-2
        if use_4bit:
            qconf = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
            try:
                base = AutoModel.from_pretrained(
                    base_model,
                    trust_remote_code=True,
                    attn_implementation=attn_impl,
                    quantization_config=qconf,
                    device_map=device_map,
                )
            except TypeError as e:
                raise RuntimeError(
                    "Your transformers version does not support attn_implementation=... "
                    "Upgrade transformers to use FlashAttention-2."
                ) from e
        else:
            try:
                base = AutoModel.from_pretrained(
                    base_model,
                    trust_remote_code=True,
                    attn_implementation=attn_impl,
                    torch_dtype=torch.bfloat16,
                    device_map=device_map,
                )
            except TypeError as e:
                raise RuntimeError(
                    "Your transformers version does not support attn_implementation=... "
                    "Upgrade transformers to use FlashAttention-2."
                ) from e

        # Load adapter from this repo folder
        adapter_dir = os.path.join(repo_path, adapter_subdir)
        if not os.path.isfile(os.path.join(adapter_dir, "adapter_config.json")):
            raise FileNotFoundError(f"adapter_config.json not found under: {adapter_dir}")

        model = PeftModel.from_pretrained(base, adapter_dir)
        model.eval()

        return cls(tokenizer=tokenizer, model=model, device=device_t)

    @torch.inference_mode()
    def embed_texts(
        self,
        texts: List[str],
        *,
        max_len: int = 512,
        batch_size: int = 16,
        return_cpu_float32: bool = True,
    ) -> EmbedOutput:
        """
        Encodes arbitrary texts and returns global embeddings via last-token pooling.
        
        Returns:
          - embedding: [N,H] - global embeddings (L2-normalized)
        """
        # Determine AMP
        device = self.device
        if device.type == "cuda":
            amp_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            use_amp = True
        else:
            amp_dtype = torch.float32
            use_amp = False

        outs = []
        for i in range(0, len(texts), batch_size):
            chunk = [str(t) for t in texts[i:i + batch_size]]
            enc = encode_with_eos_ids(self.tokenizer, chunk, max_len)
            input_ids = enc["input_ids"].to(device, non_blocking=True)
            attention_mask = enc["attention_mask"].to(device, non_blocking=True)

            with torch.autocast(device_type=("cuda" if device.type == "cuda" else "cpu"),
                                dtype=amp_dtype, enabled=use_amp):
                h = get_last_hidden_state(self.model, input_ids, attention_mask)  # [B,T,H]
                
                # Global embedding: extract EOS token embedding via last-token pooling
                emb = last_token_pool(h, attention_mask)  # [B,H]
                emb = F.normalize(emb.float(), p=2, dim=-1)

            outs.append(emb.detach())

        embeddings = torch.cat(outs, dim=0)  # on device, dtype ~ bf16

        # Move to CPU float32 if requested (recommended for retrieval stability)
        if return_cpu_float32:
            embeddings_cpu = embeddings.float().cpu()
            # re-normalize to fix any numerical drift
            embeddings_cpu = F.normalize(embeddings_cpu, p=2, dim=-1)
        else:
            embeddings_cpu = embeddings

        return EmbedOutput(embedding=embeddings_cpu)

    @torch.inference_mode()
    def embed_instruction_query(
        self,
        instructions: List[str],
        queries: List[str],
        *,
        max_len: int = 512,
        batch_size: int = 16,
        return_cpu_float32: bool = True,
    ) -> EmbedOutput:
        """
        Embed instruction-query pairs.
        
        Returns:
          - embedding: [N,H] - global embeddings (L2-normalized)
        """
        if len(instructions) != len(queries):
            raise ValueError("instructions and queries must have the same length.")
        q_texts = [build_qwen_query(i, q) for i, q in zip(instructions, queries)]
        return self.embed_texts(
            q_texts,
            max_len=max_len,
            batch_size=batch_size,
            return_cpu_float32=return_cpu_float32,
        )

    @staticmethod
    def cosine_topk(
        query_emb: torch.Tensor,     # [Nq,H] CPU float32 recommended
        cand_emb: torch.Tensor,      # [Nd,H] CPU float32 recommended
        k: int = 10,
        *,
        device: str = "cuda",
        query_batch_size: int = 256,
        doc_chunk_size: int = 8192,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Chunked cosine top-k, stable in float32.
        Returns (top_scores [Nq,k], top_indices [Nq,k]) on CPU.
        """
        device_t = torch.device(device)
        q = F.normalize(query_emb.float(), p=2, dim=-1)
        d = F.normalize(cand_emb.float(), p=2, dim=-1)
        Nq, H = q.shape
        Nd = d.shape[0]
        k = min(int(k), Nd)

        top_scores_all = torch.empty((Nq, k), dtype=torch.float32)
        top_indices_all = torch.empty((Nq, k), dtype=torch.long)

        for qs in range(0, Nq, query_batch_size):
            qe = q[qs:qs + query_batch_size].to(device_t, non_blocking=True)
            bq = qe.size(0)

            top_scores = torch.full((bq, k), -1e9, device=device_t, dtype=torch.float32)
            top_indices = torch.full((bq, k), -1, device=device_t, dtype=torch.long)

            for ds in range(0, Nd, doc_chunk_size):
                de = d[ds:ds + doc_chunk_size].to(device_t, non_blocking=True)
                scores = (qe @ de.T).float()

                chunk = scores.size(1)
                idx_chunk = torch.arange(ds, ds + chunk, device=device_t, dtype=torch.long).unsqueeze(0).expand(bq, -1)

                comb_scores = torch.cat([top_scores, scores], dim=1)
                comb_idx = torch.cat([top_indices, idx_chunk], dim=1)

                new_scores, new_pos = torch.topk(comb_scores, k, dim=1)
                new_idx = comb_idx.gather(1, new_pos)

                top_scores, top_indices = new_scores, new_idx

            top_scores_all[qs:qs + bq] = top_scores.cpu()
            top_indices_all[qs:qs + bq] = top_indices.cpu()

        return top_scores_all, top_indices_all
