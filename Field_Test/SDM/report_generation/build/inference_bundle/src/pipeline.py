"""End-to-end report generation from a preprocessed chest-CT npz.

    CT volume (int16 HU, 256^3) -> centre crop 224^3 -> window on GPU
      -> JECT trunk s1-s3 (shared)
           |                                      |
    stage4, alignment-trained              stage4, as pretrained
           |                                      |
    aligned pooler -> global latent        resampler (256 latents) -> 256 x 2560
      -> findings probe                           |
      -> "Findings present: ..." ----------------> MedGemma 1.5-4b-it + LoRA
                                                    -> FINDINGS text

The two branches deliberately use **different stage4 weights**. The findings classifier
was fitted on the text-aligned encoder; the generator was trained against the encoder as
pretrained, and never saw the aligned features. Feeding either branch the other's stage4
silently changes the input distribution the downstream weights were fitted to — measured:
running generation off the aligned stage4 reproduced only 2 of 24 reference reports.
Alignment trained stage4 and pos_embed_s4 only, so s1-s3 run once and feed both.

This is the `noret` model: it takes no retrieved reports, so no report index or
retrieval corpus is required. That was a measured choice, not a simplification —
retrieval made no difference to clinical accuracy (paired 95% CI +0.0043
[-0.0083, +0.0169]) while tripling prompt length.
"""
from __future__ import annotations

import copy, importlib.util, os, sys
from typing import Dict, List, Optional, Sequence

import numpy as np
import torch
import torch.nn as nn

IMAGE_TOKEN_ID = 262144
MM_TOKENS = 256
GLOBAL_LATENT = 10          # last of the 11 aligned latents: the whole-study one
WINDOW_CENTER, WINDOW_WIDTH = 0.0, 2000.0     # JECT's "general" window (id 2)


def _import_by_path(name: str, path: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _allow_inputs_embeds_generation(model) -> None:
    """Let ``generate(inputs_embeds=...)`` through on transformers >= 5.15.

    The image enters this model as soft tokens spliced into the input embeddings, so
    generation must take ``inputs_embeds``. 5.15 refactored Gemma3's
    ``prepare_inputs_for_generation`` to ``**kwargs``, and ``generate`` decides whether a
    model supports ``inputs_embeds`` by looking for that parameter *by name* in the
    signature — so it now refuses input it still handles correctly. Re-declaring the
    parameter restores it. No-op on 5.14.x, which declares it explicitly.
    """
    import inspect
    fn = model.prepare_inputs_for_generation
    if "inputs_embeds" in inspect.signature(fn).parameters:
        return

    # the parameter must literally be named ``kwargs``: generate() also validates its
    # arguments by reading this signature, and expands to the forward signature only
    # when it finds a var-keyword parameter with that name.
    def prepare(input_ids, inputs_embeds=None, **kwargs):
        return fn(input_ids, inputs_embeds=inputs_embeds, **kwargs)

    model.prepare_inputs_for_generation = prepare


def window_hu(volume: torch.Tensor) -> torch.Tensor:
    """Raw HU -> [0, 1]. Applied on device so the loader can ship int16."""
    lo, hi = WINDOW_CENTER - WINDOW_WIDTH / 2, WINDOW_CENTER + WINDOW_WIDTH / 2
    return ((volume.float() - lo) / (hi - lo)).clamp_(0.0, 1.0)


def centre_crop(vol: np.ndarray, size: int = 224) -> np.ndarray:
    """Crop in HU space before windowing, matching how the model was trained."""
    if vol.ndim == 4:
        vol = vol[0]
    off = [(s - size) // 2 for s in vol.shape[-3:]]
    if any(o < 0 for o in off):
        raise ValueError(f"volume {vol.shape[-3:]} smaller than crop {size}")
    return vol[off[0]:off[0] + size, off[1]:off[1] + size, off[2]:off[2] + size]


class LatentAttentionPooling(nn.Module):
    """K learned queries cross-attend to the token grid -> [B, K, D].

    The residual from the latents onto the attention output is load-bearing: without it
    attention starts near-uniform, every query returns ~mean(V), and the K outputs are
    near-identical. Kept here so checkpoints load with matching parameter names.
    """

    def __init__(self, dim: int, num_latents: int = 8, num_heads: int = 8,
                 mlp_ratio: float = 4.0):
        super().__init__()
        self.latents = nn.Parameter(torch.randn(1, num_latents, dim) * 0.02)
        self.norm_latents = nn.LayerNorm(dim)
        self.norm_tokens = nn.LayerNorm(dim)
        self.attn = nn.MultiheadAttention(dim, num_heads, batch_first=True)
        self.norm_mlp = nn.LayerNorm(dim)
        hidden = int(dim * mlp_ratio)
        self.mlp = nn.Sequential(nn.Linear(dim, hidden), nn.GELU(), nn.Linear(hidden, dim))

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        q = self.norm_latents(self.latents).expand(tokens.shape[0], -1, -1)
        kv = self.norm_tokens(tokens)
        attended, _ = self.attn(q, kv, kv, need_weights=False)
        attended = attended + q
        return attended + self.mlp(self.norm_mlp(attended))


class Resampler(nn.Module):
    def __init__(self, d_in: int, d_out: int, n_tokens: int = MM_TOKENS, heads: int = 8):
        super().__init__()
        self.pool = LatentAttentionPooling(d_in, n_tokens, heads)
        self.proj = nn.Sequential(nn.LayerNorm(d_in), nn.Linear(d_in, d_out),
                                  nn.GELU(), nn.Linear(d_out, d_out))

    def forward(self, tokens):
        return self.proj(self.pool(tokens))


INSTRUCTION = (
    "You are a radiologist reporting a non-contrast chest CT. Using the CT volume and "
    "the automated findings, write the FINDINGS section. Report only what the images "
    "support; the automated findings are hints, not ground truth."
)


def render_findings(scores: Sequence[float], policy: dict, max_uncertain: int = 5) -> str:
    """Three tiers backed by measured operating points: assert only where precision
    >= 0.50 is reachable, hedge in a capped band, otherwise stay silent (NPV ~0.99).

    Uncertain candidates rank by elevation relative to each finding's own negative cut.
    Raw scores are not comparable across findings — rare labels carry inflated values,
    so a raw-score cap fills every case with the same noisy rare findings.
    """
    positive, uncertain = [], []
    for name, v in policy["policy"].items():
        s = scores[v["index"]]
        if v.get("assertable") and v.get("t_pos") is not None and s >= v["t_pos"]:
            positive.append((s, name))
        elif s >= v["t_neg"]:
            ceiling = v["t_pos"] if v.get("t_pos") is not None else 1.0
            uncertain.append(((s - v["t_neg"]) / max(ceiling - v["t_neg"], 1e-6), name))
    positive.sort(reverse=True); uncertain.sort(reverse=True)
    lines = ["Findings present: " +
             (", ".join(n for _, n in positive) if positive else "none")]
    if uncertain[:max_uncertain]:
        lines.append("Possible: " + ", ".join(n for _, n in uncertain[:max_uncertain]))
    return "\n".join(lines)


class ReportGenerator(nn.Module):
    def __init__(self, weights_dir: str, ject_dir: str, ject_checkpoint: str,
                 medgemma: str = "google/medgemma-1.5-4b-it", device: str = "cuda",
                 dtype=torch.bfloat16):
        super().__init__()
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer

        jm = _import_by_path("ject_model", os.path.join(ject_dir, "model.py"))
        self.encoder, self.enc_cfg, _ = jm.load_pretrained(ject_checkpoint, stream="target")
        self.device = torch.device(device)
        self.dtype = dtype

        self.encoder = self.encoder.to(self.device).eval()

        # The aligned stage4, kept separate from the pretrained one it was finetuned from.
        align = torch.load(os.path.join(weights_dir, "align_image_tower.pt"),
                           map_location="cpu", weights_only=False)["trainable"]
        enc_sd = {k[len("image.encoder."):]: v for k, v in align.items()
                  if k.startswith("image.encoder.")}
        extra = [k for k in enc_sd if not (k.startswith("stage4.") or k == "pos_embed_s4")]
        if extra:
            raise RuntimeError(f"alignment checkpoint changes layers this bundle shares "
                               f"between both branches: {extra[:5]}")
        self.s4_aligned = copy.deepcopy(self.encoder.stage4)
        self.s4_aligned.load_state_dict(
            {k[len("stage4."):]: v for k, v in enc_sd.items() if k.startswith("stage4.")})
        self.s4_aligned = self.s4_aligned.to(self.device).eval()
        self.pos_embed_s4_aligned = enc_sd["pos_embed_s4"].to(self.device)

        d = self.enc_cfg.dims[3]
        pool_sd = {k[len("image.pool."):]: v for k, v in align.items()
                   if k.startswith("image.pool.")}
        self.align_pool = LatentAttentionPooling(d, pool_sd["latents"].shape[1], 8)
        self.align_pool.load_state_dict(pool_sd)
        self.align_proj = nn.Linear(d, d)
        self.align_proj.load_state_dict({k[len("image.proj."):]: v for k, v in align.items()
                                         if k.startswith("image.proj.")})
        self.align_pool = self.align_pool.to(self.device).eval()
        self.align_proj = self.align_proj.to(self.device).eval()

        probe = torch.load(os.path.join(weights_dir, "findings_probe.pt"),
                           map_location="cpu", weights_only=False)
        self.probe = nn.Linear(probe["weight"].shape[1], probe["weight"].shape[0])
        self.probe.weight.data, self.probe.bias.data = probe["weight"], probe["bias"]
        self.probe = self.probe.to(self.device).eval()
        self.label_columns = probe["columns"]
        import json
        self.policy = json.load(open(os.path.join(weights_dir, "prompt_policy.json")))

        self.lm = AutoModelForCausalLM.from_pretrained(medgemma, dtype=dtype,
                                                       attn_implementation="eager")
        self.tokenizer = AutoTokenizer.from_pretrained(medgemma)
        self.lm = get_peft_model(self.lm, LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            bias="none", task_type="CAUSAL_LM"))
        gen = torch.load(os.path.join(weights_dir, "reportgen_noret_ep4.pt"),
                         map_location="cpu", weights_only=False)
        missing = self.lm.load_state_dict(gen["lora"], strict=False)
        if missing.unexpected_keys:
            raise RuntimeError(f"unexpected LoRA keys: {missing.unexpected_keys[:5]}")
        self.resampler = Resampler(d, self.lm.config.text_config.hidden_size).to(dtype)
        self.resampler.load_state_dict(gen["resampler"])
        self.resampler = self.resampler.to(self.device).eval()
        self.lm = self.lm.to(self.device).eval()
        _allow_inputs_embeds_generation(self.lm.get_base_model())

    @torch.no_grad()
    def trunk(self, volume: torch.Tensor, ct_type_id: torch.Tensor) -> torch.Tensor:
        """Raw-HU volume -> s3 tokens, windowed on device. Shared by both branches."""
        e = self.encoder
        x = window_hu(volume)
        if tuple(x.shape[-3:]) != tuple(self.enc_cfg.input_size):
            raise ValueError(f"expected {tuple(self.enc_cfg.input_size)}, "
                             f"got {tuple(x.shape[-3:])}")
        wid = torch.full((x.shape[0],), 2, dtype=torch.long, device=x.device)
        h = e.patch_embed(x)
        h = h + e.window_embed(wid).unsqueeze(1) + e.ct_type_embed(ct_type_id).unsqueeze(1)
        for blk in e.stage1:
            h = blk(h, e.grid_s1)
        h, _ = e.merge1(h, e.grid_s1)
        for blk in e.stage2:
            h = blk(h, e.grid_s2)
        h, _ = e.merge2(h, e.grid_s2)
        h = h + e.pos_embed
        for blk in e.stage3:
            h = blk(h, e.grid_s3)
        h, _ = e.merge3(h, e.grid_s3)
        return h

    @torch.no_grad()
    def stage4(self, h: torch.Tensor, blocks, pos_embed) -> torch.Tensor:
        """s3 tokens -> s4 tokens [B, 343, 1024] through the given stage4 branch."""
        h = h + pos_embed
        for blk in blocks:
            h = blk(h, self.encoder.grid_s4)
        return h

    @torch.no_grad()
    def findings_block(self, h3: torch.Tensor) -> List[str]:
        tok = self.stage4(h3, self.s4_aligned, self.pos_embed_s4_aligned).float()
        # bf16 autocast, because the probe and its thresholds were fitted on embeddings
        # produced this way; float32 here would shift scores against fixed cuts.
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=self.device.type == "cuda"):
            g = torch.nn.functional.normalize(
                self.align_proj(self.align_pool(tok)[:, GLOBAL_LATENT]), dim=-1).float()
        # Round to 4 decimals: the deployed pipeline read its scores back from JSON
        # written at that precision, and the policy's uncertain list is rank-ordered, so
        # a 1e-5 difference can silently swap two hedged findings.
        probs = torch.sigmoid(self.probe(g)).float().cpu().numpy().round(4)
        return [render_findings(p, self.policy) for p in probs]

    @torch.no_grad()
    def generate(self, volumes: torch.Tensor, ct_type_id: Optional[torch.Tensor] = None,
                 max_new_tokens: int = 320) -> List[Dict[str, str]]:
        """[B, 1, 224, 224, 224] int16 raw HU -> per case {findings_block, report}."""
        volumes = volumes.to(self.device)
        if ct_type_id is None:                      # CT-RATE is non-contrast
            ct_type_id = torch.zeros(volumes.shape[0], dtype=torch.long,
                                     device=self.device)
        h3 = self.trunk(volumes, ct_type_id.to(self.device))
        blocks = self.findings_block(h3)
        gen_tok = self.stage4(h3, self.encoder.stage4, self.encoder.pos_embed_s4).float()
        img = self.resampler(gen_tok.to(self.dtype))

        prompts = [f"{INSTRUCTION}\n\nAUTOMATED FINDINGS:\n{b}\n\nFINDINGS:"
                   for b in blocks]
        embed = self.lm.get_input_embeddings()
        slot = torch.full((MM_TOKENS,), IMAGE_TOKEN_ID, dtype=torch.long)
        seqs = [torch.cat([slot, torch.tensor(
            self.tokenizer(p, add_special_tokens=True)["input_ids"], dtype=torch.long)])
            for p in prompts]
        width = max(len(s) for s in seqs)
        pad = self.tokenizer.pad_token_id or 0
        ids = torch.full((len(seqs), width), pad, dtype=torch.long)
        attn = torch.zeros((len(seqs), width), dtype=torch.long)
        for i, s in enumerate(seqs):                # left pad
            ids[i, width - len(s):] = s
            attn[i, width - len(s):] = 1
        ids, attn = ids.to(self.device), attn.to(self.device)

        emb = embed(ids).clone()
        mask = ids == IMAGE_TOKEN_ID
        for b in range(ids.shape[0]):
            j = mask[b].nonzero(as_tuple=True)[0]
            if len(j):
                emb[b, j] = img[b, :len(j)].to(emb.dtype)
        out = self.lm.generate(inputs_embeds=emb, attention_mask=attn,
                               max_new_tokens=max_new_tokens, do_sample=False)
        texts = self.tokenizer.batch_decode(out, skip_special_tokens=True)
        return [{"findings_block": b, "report": t.strip()} for b, t in zip(blocks, texts)]
