"""
Vision-to-Language Projector
Maps vision encoder output dimension to LLM embedding dimension.
"""
import torch
import torch.nn as nn


class VisionProjector(nn.Module):
    """
    MLP that aligns vision features to the LLM embedding space.

    Options:
        "linear"     : single Linear layer
        "mlp2x_gelu" : Linear → GELU → Linear  (default, same as LLaVA 1.5)
        "mlp3x_gelu" : Linear → GELU → Linear → GELU → Linear
    """

    def __init__(
        self,
        vision_hidden_size: int,
        llm_hidden_size: int,
        projector_type: str = "mlp2x_gelu",
    ):
        super().__init__()
        self.vision_hidden_size = vision_hidden_size
        self.llm_hidden_size = llm_hidden_size
        self.projector_type = projector_type

        if projector_type == "linear":
            self.proj = nn.Linear(vision_hidden_size, llm_hidden_size)

        elif projector_type == "mlp2x_gelu":
            self.proj = nn.Sequential(
                nn.Linear(vision_hidden_size, llm_hidden_size),
                nn.GELU(),
                nn.Linear(llm_hidden_size, llm_hidden_size),
            )

        elif projector_type == "mlp3x_gelu":
            self.proj = nn.Sequential(
                nn.Linear(vision_hidden_size, llm_hidden_size),
                nn.GELU(),
                nn.Linear(llm_hidden_size, llm_hidden_size),
                nn.GELU(),
                nn.Linear(llm_hidden_size, llm_hidden_size),
            )

        else:
            raise ValueError(
                f"Unknown projector type: {projector_type!r}. "
                "Choose from: 'linear', 'mlp2x_gelu', 'mlp3x_gelu'"
            )

        self._init_weights()

    def _init_weights(self):
        """Xavier uniform init for all linear layers."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, N, vision_hidden_size)
        Returns:
            (B, N, llm_hidden_size)
        """
        return self.proj(x)

    def load_weights(self, state_dict: dict):
        """Load projector weights from a saved state dict (keys may have prefix)."""
        # Strip common prefixes
        prefixes = ["projector.", "multi_modal_projector.", "mm_projector."]
        cleaned = {}
        for k, v in state_dict.items():
            key = k
            for prefix in prefixes:
                if key.startswith(prefix):
                    key = key[len(prefix):]
                    break
            cleaned[key] = v
        missing, unexpected = self.load_state_dict(cleaned, strict=False)
        if missing:
            print(f"[Projector] Missing keys: {missing}")
        if unexpected:
            print(f"[Projector] Unexpected keys: {unexpected}")
