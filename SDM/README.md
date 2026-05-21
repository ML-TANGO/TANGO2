# SDM — Software Defined Medicine

A self-supervised pretraining framework for **chest CT diagnosis and risk prediction**.

SDM learns general-purpose representations of 3D chest CT volumes without labels, then fine-tunes them for downstream clinical tasks:

- **Diagnosis** — multi-label classification of radiology findings (e.g. emphysema, pleural effusion, GGO)
- **Risk prediction** — patient-level outcome and progression models built on top of the pretrained encoder
- **Grounding** — localizing findings described in radiology reports back to 3D regions

## Approach

The encoder is pretrained with **CT-JEPA**, a hierarchical Joint-Embedding Predictive Architecture for 3D volumes:

1. A 3D CT volume is split into patches and encoded through 3 hierarchical stages.
2. Some tokens at the coarsest stage are masked.
3. A predictor reconstructs the masked tokens in embedding space, conditioned on the paired radiology report.
4. A frozen text encoder (Chest2Vec) supplies report-level context; image and text are aligned via SigLIP.

The result is a CT encoder that captures both visual structure and clinical semantics, ready to be fine-tuned for diagnosis and risk-prediction heads.

## Project layout

```
SDM/
├── config.py                   # all hyperparameters
├── models/                     # architecture
│   ├── blocks.py               # AdaLN-Zero, 3D attention, patch embed/merge, ConvNeXt3D, Swin3D
│   ├── encoder.py              # 3-stage hierarchical CT encoder
│   ├── predictors.py           # P3 / P2 / CrossStage / DecoderHead
│   └── model.py                # full CT-JEPA orchestrator (context + EMA target + predictors)
├── losses/
│   └── losses.py               # 7-component loss stack (JEPA, SigLIP, SIGReg, ...)
├── data/
│   ├── dataset.py              # CT volume / report loading, HU windowing
│   └── masking.py              # cuboid / slab / skip-slab / frequency masking
├── training/
│   ├── train.py                # pretraining loop (DDP, AMP, EMA, curriculum)
│   ├── train_differentmodel.py # alternative training entry
│   └── utils.py                # schedulers, logger, checkpoint manager, collapse monitor
├── evaluation/
│   ├── validation.py           # feature extraction, retrieval, feature-quality metrics
│   ├── linear_probe.py         # diagnosis fine-tuning (multi-label classification)
│   ├── linear_probe_merlin_example.py
│   └── extract_embeddings.py
├── grounding/
│   ├── grounding.py            # PhraseGrounder + heatmap extraction
│   ├── grounding_data.py       # ReXGroundingCT dataset loader
│   ├── grounding_eval.py       # protocols A / B / C
│   └── grounding_head.py       # text-conditioned segmentation head
├── chest2vec/                  # frozen text encoder used for report conditioning
├── rexgrounding/               # ReXGroundingCT evaluation data
└── tests/
```

## Installation

```bash
pip install -r requirements.txt
```

Requires `torch>=2.0`, `numpy`, `pandas`, `tqdm`, `scipy`. Optional: `matplotlib`, `scikit-learn`, `wandb`.

## Usage

### Pretrain the CT encoder

Run from the repo root (`TANGO2/`) so `SDM` is importable as a package:

```bash
python -m SDM.training.train \
    --config base \
    --data_csv /path/to/metadata.csv \
    --data_root /path/to/npz_files/ \
    --output_dir ./runs/pretrain
```

Or use the launcher script (handles single/multi-GPU automatically):

```bash
bash SDM/run.sh --config base --data_csv ... --data_root ...
```

Data: NPZ files with `ct` (float32, pre-windowed HU) and optional `totalseg` (uint16). The metadata CSV needs an `object_id` column and optionally `findings` (report text) and `split`.

### Diagnosis / linear probe

```bash
bash SDM/run_linear_probe.sh
```

### Grounding evaluation

```bash
python -m SDM.grounding.grounding_eval \
    --checkpoint ./runs/pretrain/checkpoint_latest.pt \
    --data_dir /path/to/rexgrounding/ \
    --protocol a --split val
```

Protocols: **A** zero-shot attention, **B** fine-tuned head, **C** causal perturbation.
