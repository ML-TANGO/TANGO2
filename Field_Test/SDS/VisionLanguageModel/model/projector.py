"""
Vision-to-Language Projector
Maps vision encoder output dimension to LLM embedding dimension.

Five projector architectures are selectable:

    "linear"     : single Linear layer
    "mlp2x_gelu" : Linear -> GELU -> Linear  (default, same as LLaVA 1.5)
    "mlp3x_gelu" : Linear -> GELU -> Linear -> GELU -> Linear
    "cross_attn" : learned queries attend to the patch sequence (Flamingo-style
                   perceiver resampler), emitting a fixed number of tokens
    "qformer"    : same as "cross_attn" plus query self-attention in every block
                   (BLIP-2 style Q-Former)

"qformer" here means "query resampler with query self-attention". It is not
weight-compatible with BLIP-2's Q-Former, which additionally carries a shared
text branch and interleaves its cross-attention across 12 layers. Train it from
scratch; do not expect to load BLIP-2 weights into it.

The first three preserve the patch count, so N patches in gives N image tokens
out. The last two compress the patch sequence into `num_query_tokens` tokens
regardless of N.
"""
from typing import Optional

import torch
import torch.nn as nn

from .config import (
    PROJECTOR_TYPES,
    PROJECTOR_LINEAR,
    PROJECTOR_MLP2,
    PROJECTOR_MLP3,
    PROJECTOR_QFORMER,
    RESAMPLER_PROJECTOR_TYPES,
)


# Order of the scalars recorded in QueryResampler.arch_signature. Only used to
# name the offender when a checkpoint's signature disagrees.
ARCH_SIGNATURE_FIELDS = ("num_query_tokens", "num_heads", "num_layers", "hidden_size")

# Where that signature sits in a VisionProjector state dict.
ARCH_SIGNATURE_KEY = "proj.arch_signature"

# Prefix a projector's keys carry inside a whole-model state dict. Only the
# prefix is translated, never the leaf names, so this does NOT import a
# LLaVA-HF (multi_modal_projector.linear_1.*) or upstream-LLaVA
# (model.mm_projector.0.*) projector; those layouts name their layers
# differently and are rejected on the leaf names.
PROJECTOR_PREFIXES = ("projector.",)

# Top-level siblings of the projector inside VisionLanguageModelV2. A caller may
# hand load_weights a whole-model state dict; those keys belong to other modules
# and are not the projector's business.
SIBLING_MODULE_PREFIXES = ("vision_encoder.", "language_model.")


def _summarize_keys(keys, limit: int = 6) -> str:
    """Render a key list for an error message without dumping every entry."""
    keys = list(keys)
    if not keys:
        return "none"
    shown = ", ".join(keys[:limit])
    return shown if len(keys) <= limit else f"{shown}, ... (+{len(keys) - limit} more)"


# ── Resampler building blocks ─────────────────────────────────────────────────

class ResamplerBlock(nn.Module):
    """
    One resampler block operating on the query sequence.

    Pre-layernorm residual sublayers, in order:
        1. query self-attention   (only when self_attention=True)
        2. cross-attention from the queries to the vision context
        3. position-wise feed-forward network

    Enabling self-attention is what turns a Flamingo-style cross-attention
    resampler into a BLIP-2 style Q-Former block.

    Cross-attention runs in every block, whereas BLIP-2 inserts it in every
    other layer of its 12-layer Q-Former. Alternating only makes sense at that
    depth: at the default num_layers=2 it would leave the second block with no
    view of the image at all. Deep stacks that want the BLIP-2 cadence can be
    built by raising num_layers, at 4.2M parameters per cross-attention sublayer.
    """

    def __init__(
        self,
        hidden_size: int,
        num_heads: int,
        ffn_ratio: float,
        dropout: float,
        self_attention: bool,
    ):
        super().__init__()
        self.self_attention = self_attention

        if self_attention:
            self.self_attn_norm = nn.LayerNorm(hidden_size)
            self.self_attn = nn.MultiheadAttention(
                embed_dim=hidden_size,
                num_heads=num_heads,
                dropout=dropout,
                batch_first=True,
            )

        self.cross_attn_norm = nn.LayerNorm(hidden_size)
        self.context_norm = nn.LayerNorm(hidden_size)
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True,
        )

        # nn.Linear accepts out_features=0, so a ratio small enough to round the
        # width down to zero would build silently and then contribute nothing but
        # zeros through the residual. That is a misconfigured projector, not a
        # narrow one, so it is rejected here alongside the other shape checks.
        ffn_hidden = int(hidden_size * ffn_ratio)
        if ffn_hidden < 1:
            raise ValueError(
                f"Projector ffn_ratio {ffn_ratio} rounds the feed-forward width "
                f"down to {ffn_hidden} at hidden size {hidden_size}. "
                f"Use a ratio of at least {1 / hidden_size:.6g}."
            )
        self.ffn_norm = nn.LayerNorm(hidden_size)
        self.ffn = nn.Sequential(
            nn.Linear(hidden_size, ffn_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ffn_hidden, hidden_size),
        )

    def forward(self, queries: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        """
        Args:
            queries: (B, Q, hidden_size)
            context: (B, N, hidden_size)
        Returns:
            (B, Q, hidden_size)
        """
        if self.self_attention:
            normed = self.self_attn_norm(queries)
            attended, _ = self.self_attn(normed, normed, normed, need_weights=False)
            queries = queries + attended

        normed_q = self.cross_attn_norm(queries)
        normed_ctx = self.context_norm(context)
        attended, _ = self.cross_attn(normed_q, normed_ctx, normed_ctx, need_weights=False)
        queries = queries + attended

        return queries + self.ffn(self.ffn_norm(queries))


class QueryResampler(nn.Module):
    """
    Compresses a variable-length patch sequence into a fixed number of learned
    query tokens, then maps them to the LLM embedding dimension.

    With self_attention=False this is a cross-attention resampler; with
    self_attention=True it is a Q-Former.
    """

    def __init__(
        self,
        vision_hidden_size: int,
        llm_hidden_size: int,
        hidden_size: int,
        num_query_tokens: int,
        num_heads: int,
        num_layers: int,
        ffn_ratio: float,
        dropout: float,
        self_attention: bool,
    ):
        super().__init__()
        if hidden_size % num_heads != 0:
            raise ValueError(
                f"Projector hidden size {hidden_size} is not divisible by "
                f"num_heads {num_heads}."
            )
        if num_layers < 1:
            raise ValueError(f"Projector needs at least one layer, got {num_layers}.")
        if num_query_tokens < 1:
            raise ValueError(
                f"Projector needs at least one query token, got {num_query_tokens}."
            )

        self.num_query_tokens = num_query_tokens
        self.query = nn.Parameter(torch.empty(num_query_tokens, hidden_size))
        nn.init.trunc_normal_(self.query, std=0.02)

        # num_heads leaves no trace in the state dict: nn.MultiheadAttention
        # keeps it as a plain int, and its in_proj/out_proj shapes depend only
        # on the width. So a checkpoint trained at 16 heads loads into an
        # 8-head projector with zero missing and zero unexpected keys, and
        # every head boundary is silently wrong. Recording the architecture
        # scalars as a buffer puts them in the state dict where load_weights
        # can compare them. See ARCH_SIGNATURE_FIELDS for the running order.
        self.register_buffer(
            "arch_signature",
            torch.tensor(
                [num_query_tokens, num_heads, num_layers, hidden_size],
                dtype=torch.int64,
            ),
            persistent=True,
        )

        self.context_proj = nn.Linear(vision_hidden_size, hidden_size)
        self.blocks = nn.ModuleList([
            ResamplerBlock(
                hidden_size=hidden_size,
                num_heads=num_heads,
                ffn_ratio=ffn_ratio,
                dropout=dropout,
                self_attention=self_attention,
            )
            for _ in range(num_layers)
        ])
        self.out_norm = nn.LayerNorm(hidden_size)
        self.out_proj = nn.Linear(hidden_size, llm_hidden_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, N, vision_hidden_size)
        Returns:
            (B, num_query_tokens, llm_hidden_size)

        No positional embedding is added to the context. The ViT already applies
        its own learned position embedding (577 x 1024 for CLIP ViT-L/14-336),
        so patch order is carried in the features this receives, and BLIP-2
        likewise feeds raw ViT features to its Q-Former.

        The consequence is that this forward is invariant to permutations of the
        sequence axis: position reaches it inside each feature vector, never
        through the index. For a single image that is exactly right, since the
        ViT already put it there.

        It is NOT right for the video encoder. VisionEncoderWrapper's
        LanguageBind path runs every frame through the same image ViT and
        concatenates the results into (B, T*N, D), so a patch from frame 0 and
        the corresponding patch from frame 7 carry identical position
        information and are told apart only by their index. The per-patch
        projectors preserve that index into the LLM sequence, where the LLM's
        own positional encoding recovers frame order. A resampler discards it.
        So cross_attn and qformer are single-image projectors as they stand;
        pairing either with a multi-frame encoder trains and reports a plausible
        loss while carrying no temporal information at all. Giving the context a
        frame embedding before the first block is what that would need.
        """
        context = self.context_proj(x)
        queries = self.query.unsqueeze(0).expand(x.shape[0], -1, -1)
        for block in self.blocks:
            queries = block(queries, context)
        return self.out_proj(self.out_norm(queries))


# ── Public projector ──────────────────────────────────────────────────────────

class VisionProjector(nn.Module):
    """
    Aligns vision features to the LLM embedding space.

    See the module docstring for the available `projector_type` values. The
    resampler hyperparameters are ignored by the linear and MLP variants.
    """

    def __init__(
        self,
        vision_hidden_size: int,
        llm_hidden_size: int,
        projector_type: str = PROJECTOR_MLP2,
        hidden_size: Optional[int] = None,
        num_query_tokens: int = 32,
        num_heads: int = 8,
        num_layers: int = 2,
        ffn_ratio: float = 4.0,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.vision_hidden_size = vision_hidden_size
        self.llm_hidden_size = llm_hidden_size
        self.projector_type = projector_type
        # Only the resamplers have a fixed output token count.
        self.num_query_tokens = (
            num_query_tokens if projector_type in RESAMPLER_PROJECTOR_TYPES else None
        )

        if projector_type == PROJECTOR_LINEAR:
            self.proj = nn.Linear(vision_hidden_size, llm_hidden_size)

        elif projector_type == PROJECTOR_MLP2:
            self.proj = nn.Sequential(
                nn.Linear(vision_hidden_size, llm_hidden_size),
                nn.GELU(),
                nn.Linear(llm_hidden_size, llm_hidden_size),
            )

        elif projector_type == PROJECTOR_MLP3:
            self.proj = nn.Sequential(
                nn.Linear(vision_hidden_size, llm_hidden_size),
                nn.GELU(),
                nn.Linear(llm_hidden_size, llm_hidden_size),
                nn.GELU(),
                nn.Linear(llm_hidden_size, llm_hidden_size),
            )

        elif projector_type in RESAMPLER_PROJECTOR_TYPES:
            self.proj = QueryResampler(
                vision_hidden_size=vision_hidden_size,
                llm_hidden_size=llm_hidden_size,
                hidden_size=hidden_size or vision_hidden_size,
                num_query_tokens=num_query_tokens,
                num_heads=num_heads,
                num_layers=num_layers,
                ffn_ratio=ffn_ratio,
                dropout=dropout,
                self_attention=(projector_type == PROJECTOR_QFORMER),
            )

        else:
            raise ValueError(
                f"Unknown projector type: {projector_type!r}. "
                f"Choose from: {', '.join(repr(t) for t in PROJECTOR_TYPES)}"
            )

        self._init_weights()

    def _init_weights(self):
        """Xavier uniform init for all linear layers."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    # ── Introspection ────────────────────────────────────────────────────────

    @property
    def dtype(self) -> torch.dtype:
        """Parameter dtype, used by callers to cast vision features before forward."""
        return next(self.parameters()).dtype

    @property
    def device(self) -> torch.device:
        return next(self.parameters()).device

    def output_num_tokens(self, input_num_tokens: int) -> int:
        """
        Number of image tokens this projector emits for `input_num_tokens`
        vision patches. The resampler variants emit a fixed count.
        """
        if self.projector_type in RESAMPLER_PROJECTOR_TYPES:
            return self.num_query_tokens
        return input_num_tokens

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, N, vision_hidden_size)
        Returns:
            (B, output_num_tokens(N), llm_hidden_size)
        """
        return self.proj(x)

    def load_weights(self, state_dict: dict, strict: bool = True):
        """
        Load projector weights from a saved state dict (keys may have a prefix).

        Raises ValueError when the checkpoint's tensor layout does not match
        this projector. Since projector_type is selectable, loading a checkpoint
        trained with a different architecture, or with the same architecture at
        a different query count or width, would otherwise leave this module
        partly or wholly randomly initialized and let training or inference
        proceed on garbage.

        Three kinds of mismatch are reported. Keys this projector expects but
        the checkpoint lacks, keys the checkpoint carries that this projector
        has no slot for, and keys present on both sides whose tensor shapes
        disagree. The last kind is what a changed projector_num_query_tokens or
        projector_hidden_size produces, since the key names stay the same.

        Pass strict=False to downgrade every mismatch to a printed warning and
        load whatever does line up.

        Returns:
            (missing, unexpected) key lists. Shape-mismatched keys are counted
            as missing, since their weights were not loaded.
        """
        # Strip the projector prefix a whole-model state dict carries.
        cleaned = {}
        prefixed = False
        for k, v in state_dict.items():
            key = k
            for prefix in PROJECTOR_PREFIXES:
                if key.startswith(prefix):
                    key = key[len(prefix):]
                    prefixed = True
                    break
            cleaned[key] = v

        # A whole-model dict also carries the encoder and the LLM. Those are
        # siblings of the projector, not stray projector keys, so drop them
        # rather than reporting them as unexpected.
        if prefixed:
            for key in [k for k in cleaned if k.startswith(SIBLING_MODULE_PREFIXES)]:
                del cleaned[key]

        # Drop shape-mismatched entries before load_state_dict, which would
        # otherwise raise its own RuntimeError. Doing it here keeps every kind
        # of mismatch in one report and makes strict=False actually work.
        own = self.state_dict()
        mismatched = []
        for key in [k for k in cleaned if k in own]:
            checkpoint_shape = tuple(cleaned[key].shape)
            own_shape = tuple(own[key].shape)
            if checkpoint_shape != own_shape:
                mismatched.append(
                    f"{key} checkpoint{checkpoint_shape} vs projector{own_shape}"
                )
                del cleaned[key]

        # Architecture scalars that leave no other trace, num_heads above all.
        # The signature records how THIS module was built, so it is compared and
        # then removed rather than loaded. Letting load_state_dict write the
        # checkpoint's values over it would leave the buffer describing an
        # architecture the module does not have, and re-saving that projector
        # would then reject its own correct weights. Its absence from a
        # checkpoint is likewise not a missing weight, just an unknown.
        differing_scalars = self._compare_arch_signature(cleaned, own)
        cleaned.pop(ARCH_SIGNATURE_KEY, None)

        missing, unexpected = self.load_state_dict(cleaned, strict=False)
        missing = [key for key in missing if key != ARCH_SIGNATURE_KEY]

        if missing or unexpected or mismatched or differing_scalars:
            report = (
                f"Checkpoint tensors do not match projector_type="
                f"{self.projector_type!r}.\n"
                f"  Missing         ({len(missing)}): {_summarize_keys(missing)}\n"
                f"  Unexpected      ({len(unexpected)}): {_summarize_keys(unexpected)}\n"
                f"  Shape mismatch  ({len(mismatched)}): {_summarize_keys(mismatched, limit=3)}\n"
                f"  Settings differ ({len(differing_scalars)}): "
                f"{_summarize_keys(differing_scalars, limit=4)}\n"
                "The checkpoint was most likely trained with a different "
                "projector_type or different resampler hyperparameters. "
                "The projector settings recorded in the checkpoint's "
                "vlm_config.json are the authoritative ones."
            )
            if strict:
                raise ValueError(report)
            print(f"[Projector] {report}")

        return missing, unexpected

    def _compare_arch_signature(self, cleaned: dict, own: dict) -> list:
        """
        Compare the recorded resampler scalars against this projector's.

        Returns a list of human-readable "field checkpoint=A vs projector=B"
        strings. Empty when the projector has no signature (the linear and MLP
        variants), when the checkpoint predates it, or when a signature of the
        wrong length was already reported as a shape mismatch by the caller.
        """
        if ARCH_SIGNATURE_KEY not in own or ARCH_SIGNATURE_KEY not in cleaned:
            return []

        recorded = cleaned[ARCH_SIGNATURE_KEY].tolist()
        current = own[ARCH_SIGNATURE_KEY].tolist()
        return [
            f"{field} checkpoint={was} vs projector={now}"
            for field, was, now in zip(ARCH_SIGNATURE_FIELDS, recorded, current)
            if was != now
        ]
