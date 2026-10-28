# Chest CT report generation — JECT_Generator inference

Inference code for generating chest CT FINDINGS reports with **JECT_Generator**:
JECT 3D CT encoder + MedGemma 1.5 4B (LoRA). Code only — model weights, API keys,
evaluation scripts and data are not in this repository.

```
CT (nii.gz + lung mask) → npz (LPS, 1.5 mm, 256³ HU) → centre crop 224³ → JECT encoder
   ├─ findings probe → "Findings present: …" prompt ─┐
   └─ resampler → 256 image tokens ──────────────────┴→ MedGemma 1.5 4B + LoRA → FINDINGS (greedy)
```

## Layout

| path | does |
|---|---|
| `build/Dockerfile` | inference image (`pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`); build from `build/` |
| `build/inference_bundle/run_inference.py` | npz directory → `reports.json`, batch by batch |
| `build/inference_bundle/src/pipeline.py` | `ReportGenerator`: the two-branch model above; its header explains the design |
| `build/inference_bundle/ject/model.py` | JECT 3D CT encoder |
| `build/validation/preprocess_npz.py` | nii.gz + TotalSegmentator mask → npz (LPS, 1.5 mm, 256³ lung crop) |
| `build/validation/check_cohort.py` | pre-flight check of an input directory |
| `build/validation/entrypoint.sh` | container stage dispatcher (`check`, `preprocess`, `infer`, `demo`, `shell`) |
| `build/demo/` | demo runner: `run_all.py` (steps), `env_check.py`, `generate.py` (seeded, timed inference), `check_reports.py`, `ui.py` |
| `gui/` | web demo (Gradio): upload a CT → segmentation, preprocessing, report, structured report |
| `run_demo.sh`, `check_ready.sh`, `sysinfo.sh`, `run_gui.sh` | host launchers: run, readiness check, hardware/software report, GUI |

## Not included (supply locally)

| item | where it goes |
|---|---|
| JECT encoder weights | `build/inference_bundle/ject/ject_224_ep45_encoder.pt` |
| generator weights | `build/inference_bundle/weights/` (`reportgen_noret_ep4.pt`, `align_image_tower.pt`, `findings_probe.pt`, `prompt_policy.json`) |
| MedGemma 1.5 4B base | `hf_cache/` (mounted read-only, offline) |
| API keys | `labeler.env` / `labeler_gemini.env` (mode 600; never baked into an image) |
| evaluation / labeling scripts, test data | not distributed; the demo's steps 3, 6–7 need them |

## Run

```bash
# build (from build/)
docker build -t chest-ct-foundation:tc1 --build-arg UID=$(id -u) --build-arg GID=$(id -g) build/

# preprocess + inference on a directory holding nii/ and totalseg/
docker run --rm --gpus '"device=0"' \
  -v $PWD/data:/data:ro -v $PWD/hf_cache:/hf:ro -v $PWD/out:/out \
  chest-ct-foundation:tc1 preprocess
docker run --rm --gpus '"device=0"' \
  -v $PWD/hf_cache:/hf:ro -v $PWD/out:/out \
  chest-ct-foundation:tc1 infer        # → out/reports.json

# GUI (port 7870)
./run_gui.sh
```

Inference is deterministic (greedy decoding, seed 42, batch size 4). Validated with
Python 3.11, torch 2.5.1 + CUDA 12.4, transformers 5.14.1, peft 0.20.0, on one RTX A6000
(peak ≈ 16 GB).
