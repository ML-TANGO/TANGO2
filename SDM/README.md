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

| File | Purpose |
|------|---------|
| `config.py` | Hyperparameters (volume, model, masking, loss, training) |
| `encoder.py` | 3-stage hierarchical CT encoder |
| `model.py` | Full CT-JEPA model (context + EMA target + predictors + text alignment) |
| `predictors.py`, `blocks.py`, `masking.py`, `losses.py` | Core training components |
| `data.py` | CT volume / report loading |
| `train.py` | Pretraining loop |
| `validation.py` | Linear probes, retrieval, feature-quality metrics |
| `linear_probe.py` | Diagnosis fine-tuning (multi-label classification) |
| `grounding.py`, `grounding_eval.py`, `grounding_head.py` | Phrase-grounding evaluation |
| `chest2vec/` | Text encoder used for report conditioning |
| `rexgrounding/` | ReXGroundingCT evaluation data |

## Installation

```bash
pip install -r requirements.txt
```

Requires `torch>=2.0`, `numpy`, `pandas`, `tqdm`, `scipy`. Optional: `matplotlib`, `scikit-learn`, `wandb`.

## Usage

### Pretrain the CT encoder

```bash
python -m cepa.train \
    --config base \
    --data_csv /path/to/metadata.csv \
    --data_root /path/to/npz_files/ \
    --output_dir ./runs/pretrain
```

Data: NPZ files with `ct` (float32, pre-windowed HU) and optional `totalseg` (uint16). The metadata CSV needs an `object_id` column and optionally `findings` (report text) and `split`.

### Diagnosis / linear probe

```bash
bash run_linear_probe.sh
```

### Grounding evaluation

```bash
python -m cepa.grounding_eval \
    --checkpoint ./runs/pretrain/checkpoint_latest.pt \
    --data_dir /path/to/rexgrounding/ \
    --protocol a --split val
```

Protocols: **A** zero-shot attention, **B** fine-tuned head, **C** causal perturbation.
