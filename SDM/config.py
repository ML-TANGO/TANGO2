"""
CT-JEPA v2 Configuration
========================
All hyperparameters and model configurations in one place.
Based on ThoraxJEPA config with additions for local block type selection
and data path configuration.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import math


@dataclass
class VolumeConfig:
    """Input volume specification."""
    depth: int = 192
    height: int = 256
    width: int = 256
    channels: int = 1
    hu_clip_min: float = -1000.0
    hu_clip_max: float = 2000.0


@dataclass
class WindowConfig:
    """HU windowing parameters."""
    windows: dict = field(default_factory=lambda: {
        "lung":     {"center": 450,  "width": 2100},   # -600 to 1500: lung parenchyma, nodules, airways
        "med":      {"center": 195,  "width": 310},    # 40 to 350: soft tissue, vessels, lymph nodes
        "general":  {"center": 0,    "width": 2000},   # -1000 to 1000: balanced all-purpose
        "full":     {"center": 1500, "width": 5000},   # -1000 to 4000: full range (TODO: expand with int16 data)
    })
    num_windows: int = 4


@dataclass
class PatchConfig:
    """Patch embedding configuration."""
    patch_size: Tuple[int, int, int] = (8, 8, 8)

    @property
    def grid_size_s1(self) -> Tuple[int, int, int]:
        return (24, 32, 32)  # D/8, H/8, W/8

    @property
    def grid_size_s2(self) -> Tuple[int, int, int]:
        return (12, 16, 16)  # S1 / 2

    @property
    def grid_size_s3(self) -> Tuple[int, int, int]:
        return (6, 8, 8)  # S2 / 2

    @property
    def num_tokens_s1(self) -> int:
        return math.prod(self.grid_size_s1)  # 24576

    @property
    def num_tokens_s2(self) -> int:
        return math.prod(self.grid_size_s2)  # 3072

    @property
    def num_tokens_s3(self) -> int:
        return math.prod(self.grid_size_s3)  # 384


@dataclass
class ModelConfig:
    """Architecture configuration."""
    variant: str = "base"  # "small", "base", "large"

    # Local block type for stages 1-2
    local_block_type: str = "transformer"  # "transformer" | "swin" | "convnext"
    swin_window_size: Tuple[int, int, int] = (4, 4, 4)

    @property
    def dims(self):
        return {
            "small": (96, 192, 384),
            "base":  (128, 256, 512),
            "large": (192, 384, 768),
        }[self.variant]

    @property
    def dim_s1(self) -> int:
        return self.dims[0]

    @property
    def dim_s2(self) -> int:
        return self.dims[1]

    @property
    def dim_s3(self) -> int:
        return self.dims[2]

    @property
    def blocks(self):
        return {
            "small": (2, 4, 6),
            "base":  (2, 4, 8),
            "large": (2, 6, 12),
        }[self.variant]

    @property
    def num_blocks_s1(self) -> int:
        return self.blocks[0]

    @property
    def num_blocks_s2(self) -> int:
        return self.blocks[1]

    @property
    def num_blocks_s3(self) -> int:
        return self.blocks[2]

    # Attention heads
    num_heads_s1: int = 4
    num_heads_s2: int = 8
    num_heads_s3: int = 16
    window_size_s1: Tuple[int, int, int] = (8, 8, 8)
    window_size_s2: Tuple[int, int, int] = (4, 4, 4)
    mlp_ratio: float = 4.0
    drop_path_rate: float = 0.1

    # Region tokens
    num_region_tokens: int = 25
    use_region_tokens: bool = True

    # Global readout (replaces Stage 4)
    num_readout_queries: int = 4
    readout_dim: int = 512

    # Predictor
    predictor_depth: int = 4
    predictor_num_heads: int = 8

    # Detail predictor (Stage 2)
    use_detail_predictor: bool = True
    detail_num_sampled: int = 512

    # Lightweight decoder
    use_decoder_head: bool = True


@dataclass
class MaskingConfig:
    """Masking strategy configuration."""
    # Mask ratio schedule: steps down at text conditioning and alignment epochs
    mask_ratio_foundation: float = 0.65   # epochs 0 to text_introduction_epoch
    mask_ratio_text: float = 0.55         # text_introduction_epoch to align_introduction_epoch
    mask_ratio_alignment: float = 0.45    # align_introduction_epoch onwards

    family_probs: dict = field(default_factory=lambda: {
        "cuboid":   0.40,
        "axial":    0.12,
        "coronal":  0.12,
        "sagittal": 0.12,
        "skip_slab": 0.12,
        "frequency": 0.12,
    })

    num_cuboid_targets: int = 5
    cuboid_min_size: Tuple[int, int, int] = (2, 2, 2)
    cuboid_max_size: Tuple[int, int, int] = (3, 4, 4)

    slab_width: int = 2
    num_slabs: int = 3

    skip_slab_center_width: int = 2
    skip_slab_gap: int = 1

    freq_mask_ratio: float = 0.5
    freq_mask_mode: str = "low"

    use_anatomy_bias: bool = True
    anatomy_bias_strength: float = 2.0


@dataclass
class TextConfig:
    """Text conditioning configuration."""
    use_text: bool = True
    text_encoder_name: str = "lukeingawesome/chest2vec_0.6b_chest"
    text_embed_dim: int = 1024  # Qwen3-0.6B hidden dim (probed at init)
    text_max_tokens: int = 256
    text_dropout_rate: float = 0.5
    text_introduction_epoch: int = 40  # after warmup
    chest2vec_instruction: str = "Represent the radiology report for retrieval"
    # Matryoshka truncation dimensions
    matryoshka_align_dim: int = 512   # truncation for SigLIP alignment path
    matryoshka_pred_dim: int = 256    # truncation for predictor context token


@dataclass
class LossConfig:
    """Loss weights and parameters."""
    lambda_jepa3: float = 1.0
    lambda_jepa2: float = 0.3
    lambda_align: float = 0.1
    align_temperature: float = 0.07
    align_introduction_epoch: int = 100  # delayed: predictor needs 60 epochs with text before alignment
    lambda_sigreg: float = 0.05
    sigreg_num_projections: int = 128
    sigreg_num_test_points: int = 64
    lambda_cross_stage: float = 0.1
    cross_stage_introduction_epoch: int = 100
    lambda_decoder: float = 0.05
    lambda_local_contrast: float = 0.05
    use_djepa: bool = False
    djepa_introduction_epoch: int = 200


@dataclass
class EMAConfig:
    """EMA teacher configuration."""
    momentum_start: float = 0.996
    momentum_end: float = 0.9999
    momentum_schedule: str = "cosine"


@dataclass
class TrainingConfig:
    """Training hyperparameters."""
    optimizer: str = "adamw"
    base_lr: float = 2.5e-4
    weight_decay: float = 0.05
    warmup_epochs: int = 40
    total_epochs: int = 300
    lr_schedule: str = "cosine"
    min_lr: float = 1e-6
    grad_clip_norm: float = 1.0

    batch_size: int = 6
    grad_accumulation_steps: int = 32
    num_workers: int = 8
    prefetch_factor: int = 4

    mixed_precision: bool = True

    log_interval: int = 50
    save_interval: int = 5
    eval_interval: int = 20

    collapse_std_threshold: float = 1e-5
    collapse_check_interval: int = 500


@dataclass
class DataConfig:
    """Data paths and column configuration."""
    csv_path: str = "cepa/final_ct2.csv"
    data_root: str = "/data/preprocessed"
    img_col: str = "object_id"
    text_col: str = "findings"
    split_col: str = "split"


@dataclass
class ValidationConfig:
    """Validation and monitoring configuration."""
    # Step-level logging
    log_interval: int = 50               # log losses/optim every N steps
    collapse_check_interval: int = 500   # full collapse check every N steps
    collapse_warn_threshold: float = 1e-4
    collapse_halt_threshold: float = 1e-5

    # Epoch-level validation
    eval_interval: int = 10              # run validation every N epochs
    linear_probe_interval: int = 10      # run linear probe every N epochs
    visualization_interval: int = 10     # save visualizations every N epochs

    # Phase transition epochs (for comprehensive eval)
    phase_transition_epochs: Tuple[int, ...] = (40, 100)

    # Linear probe config
    probe_csv: Optional[str] = None      # labeled CSV for linear probe
    probe_label_col: str = "label"
    probe_num_samples: int = 500         # max samples for probe
    probe_epochs: int = 50               # SGD epochs for probe

    # Feature quality
    num_tsne_samples: int = 1000         # samples for t-SNE
    num_retrieval_samples: int = 500     # samples for retrieval eval

    # Wandb
    use_wandb: bool = True
    wandb_project: str = "ctjepa-v2"
    wandb_run_name: Optional[str] = None


@dataclass
class CTJEPAConfig:
    """Master configuration."""
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    window: WindowConfig = field(default_factory=WindowConfig)
    patch: PatchConfig = field(default_factory=PatchConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    masking: MaskingConfig = field(default_factory=MaskingConfig)
    text: TextConfig = field(default_factory=TextConfig)
    loss: LossConfig = field(default_factory=LossConfig)
    ema: EMAConfig = field(default_factory=EMAConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    data: DataConfig = field(default_factory=DataConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    def __post_init__(self):
        self.model.readout_dim = self.model.dim_s3
