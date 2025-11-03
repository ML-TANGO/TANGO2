"""
gradio_ct_infer_viewer.py — CT viewer + on‑the‑fly SigLIP inference (with an explicit Run Inference button)
Install:
  pip install gradio==4.* pandas numpy pillow torch scikit-learn

Project deps (same as your evaluation code):
  training/ct_transform.py (get_val_transform)
  merlin.py (Merlin backbone)
"""

from __future__ import annotations
import os, sys, logging
from pathlib import Path
from typing import List, Tuple, Optional

import gradio as gr
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image

# ───────────────────────── Project imports ─────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "training"))

try:
    from training.ct_transform import get_val_transform  # type: ignore
except Exception:
    def get_val_transform():
        # Fallback: identity
        class _Id(nn.Module):
            def forward(self, x): return x
        return _Id()

from merlin import Merlin  # type: ignore

# ───────────────────────── Config ─────────────────────────
MODEL_PATH = os.getenv("MODEL_PATH", "/model/ct_siglip/1c_fit3.pth")
CSV_PATH   = os.getenv("CSV_PATH", "results/tmp.csv")
SPLIT_NAME = os.getenv("SPLIT", "val")
DEVICE_STR = "cuda" if torch.cuda.is_available() else "cpu"

LABEL_COLS: List[str] = [
    'Medical material', 'Arterial wall calcification', 'Cardiomegaly',
    'Pericardial effusion', 'Coronary artery wall calcification',
    'Hiatal hernia', 'Lymphadenopathy', 'Emphysema', 'Atelectasis',
    'Lung nodule', 'Lung opacity', 'Pulmonary fibrotic sequela',
    'Pleural effusion', 'Mosaic attenuation pattern',
    'Peribronchial thickening', 'Consolidation', 'Bronchiectasis',
    'Interlobular septal thickening'
]

# Viewer presets (centre, width). Brain removed; Bone uses (1000, 1500)
PRESETS = {
    "Mediastinum": (40, 400),
    "Lung": (-600, 1500),
    "Bone": (1000, 1500),
    "Liver": (50, 150),
}

# Inference 3‑channel windowing (centre, width)
# If training used 700/1500 for bone, change INFER_BONE_CENTER to 700
INFER_LUNG_CENTER, INFER_LUNG_WIDTH       = -600, 1000
INFER_MEDIAST_CENTER, INFER_MEDIAST_WIDTH = 40, 400
INFER_BONE_CENTER, INFER_BONE_WIDTH       = 1000, 1500

CSS = """
:root {
  --brand: #06b6d4;
  --panel: #0e1626;
  --panel-border: rgba(255,255,255,.06);
  --muted: #a9b3c4;
}
.gradio-container { max-width: 1500px !important; margin: auto !important; }
.header { display:flex; justify-content:space-between; align-items:flex-end; padding: 8px 4px 12px; }
.header h1 { margin:0; font-weight:800; letter-spacing:-0.02em; }
.header .meta { font-size:12px; color:var(--muted); }
.panel { background: var(--panel); border: 1px solid var(--panel-border); border-radius: 14px; padding: 12px; box-shadow: 0 12px 32px rgba(0,0,0,.25); }
.viewer-card img { border-radius: 12px; }
.controls .gr-group, .controls .gr-slider, .controls .gr-radio, .controls .gr-dropdown { margin-bottom: 8px; }
.badge { display:inline-block; padding: 2px 8px; border-radius: 6px; border:1px solid var(--panel-border); color: var(--muted); font-size: 12px; }
.pills { display:flex; flex-wrap:wrap; gap:6px; }
.pill { padding: 4px 10px; border-radius: 999px; font-size: 12px; }
/* Ground-truth positives: strong blue */
.pill.gt  { background:#1d4ed8; color:#fff; border:1px solid #3b82f6; }
/* Generated labels: green for Positive, red for Uncertain */
.pill.pos { background:#059669; color:#fff; border:1px solid #10b981; }
.pill.unc { background:#b91c1c; color:#fff; border:1px solid #ef4444; }
.pill.empty { background: transparent; color: var(--muted); border:1px dashed var(--panel-border); }
.thumb-row { display:flex; gap:8px; margin-top:8px; }
.thumb { flex:1; overflow:hidden; border-radius: 10px; border:1px solid var(--panel-border); }
.slice-caption { font-size:12px; color:var(--muted); text-align:center; margin-top:6px; }
hr.divider { border: 0; border-top: 1px solid var(--panel-border); margin: 8px 0; }
"""

# ───────────────────────── Dataframe (for sampling + GT only) ─────────────────────────
if Path(CSV_PATH).exists():
    df = pd.read_csv(CSV_PATH).query("split == @SPLIT_NAME").reset_index(drop=True)
else:
    df = pd.DataFrame(columns=["object_id", "img_path"])

# ───────────────────────── Model (same structure as eval) ─────────────────────────
def _hu_window_to_unit(volume: np.ndarray, center: float, width: float) -> np.ndarray:
    lower, upper = center - width / 2.0, center + width / 2.0
    vol = np.clip(volume, lower, upper)
    return (vol - lower) / (upper - lower + 1e-8)

class SigLIPClassifier(nn.Module):
    def __init__(self, backbone: nn.Module, n_classes: int, drop: float = .1):
        super().__init__()
        self.backbone = backbone
        dim = getattr(backbone, "output_dim", 2048)
        self.head = nn.Sequential(
            nn.Dropout(drop), nn.Linear(dim, dim // 2), nn.GELU(),
            nn.Dropout(drop), nn.Linear(dim // 2, n_classes)
        )
    def forward(self, x):
        feat = self.backbone(x).flatten(1)
        return self.head(feat)

class _AffineCalibrator(nn.Module):
    def __init__(self, n_cls: int):
        super().__init__()
        self.log_T = nn.Parameter(torch.zeros(n_cls))
        self.bias  = nn.Parameter(torch.zeros(n_cls))
    def forward(self, z: torch.Tensor) -> torch.Tensor:
        return (z + self.bias) / torch.exp(self.log_T)

class CalibratedSigLIP(nn.Module):
    def __init__(self, base: nn.Module, calib: _AffineCalibrator):
        super().__init__()
        self.base = base
        self.calib = calib
    def forward(self, x):
        return self.calib(self.base(x))

def load_model_from_checkpoint(checkpoint_path: str,
                               labels: List[str],
                               device: torch.device):
    logging.info(f"Loading model from {checkpoint_path}")
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    state = ckpt["model"]
    has_calib = any(k.startswith("calib.") for k in state)
    n_cls = len(labels)

    backbone = Merlin(ImageEmbedding=True)
    base_model = SigLIPClassifier(backbone, n_cls, drop=0.1)

    if has_calib:
        model = CalibratedSigLIP(base_model, _AffineCalibrator(n_cls))
        logging.info("Using CalibratedSigLIP (calibration layer found)")
    else:
        model = base_model
        logging.info("Using plain SigLIP (no calibration layer)")

    if any(k.startswith("module.") for k in state):
        state = {k.replace("module.", "", 1): v for k, v in state.items()}

    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing or unexpected:
        logging.warning(f"Missing keys: {len(missing)} | Unexpected keys: {len(unexpected)}")

    model.to(device).eval()

    thresholds = np.full(n_cls, 0.5, dtype=np.float32)
    if not has_calib:
        thr = ckpt.get("thresholds", None)
        if thr is not None:
            thresholds = np.array(thr, dtype=np.float32)

    return model, thresholds

DEVICE = torch.device(DEVICE_STR)
MODEL: Optional[nn.Module] = None
THRESHOLDS: Optional[np.ndarray] = None
VAL_TRANSFORM: Optional[nn.Module] = None

def ensure_model():
    global MODEL, THRESHOLDS, VAL_TRANSFORM
    if MODEL is None:
        VAL_TRANSFORM = get_val_transform()
        MODEL, THRESHOLDS = load_model_from_checkpoint(MODEL_PATH, LABEL_COLS, DEVICE)

# ───────────────────────── Viewer helpers ─────────────────────────
def to_hu(arr: np.ndarray) -> np.ndarray:
    return arr * 2500.0 - 1000.0 if arr.max() <= 1.0 else arr.astype(np.float32)

def pick_axial_axis(shape: tuple[int, int, int]) -> int:
    diffs = [abs(shape[(i + 1) % 3] - shape[(i + 2) % 3]) for i in range(3)]
    return int(np.argmin(diffs))

def auto_reorient(vol: np.ndarray) -> np.ndarray:
    if vol.ndim == 4:  # drop channel
        vol = vol[0]
    axial = pick_axial_axis(vol.shape)
    return np.moveaxis(vol, axial, 0) if axial != 0 else vol  # (D,H,W)

def window_to_uint8(slice_hu: np.ndarray, centre: float, width: float,
                    out_size: int = 1024) -> Image.Image:
    lo, hi = centre - width/2, centre + width/2
    img = np.clip(slice_hu, lo, hi)
    img = ((img - lo) / (hi - lo + 1e-5) * 255).astype(np.uint8)
    return Image.fromarray(img, mode="L").resize((out_size, out_size), Image.NEAREST)

def plane_slice(vol: np.ndarray, plane: str, idx: int) -> np.ndarray:
    if plane == "axial":   return vol[idx]
    if plane == "coronal": return np.rot90(vol[:, idx, :])
    return np.rot90(vol[:, :, idx])  # sagittal

def md_strong(label: str, text: str) -> str:
    if not isinstance(text, str) or text.strip() == "":
        return f"**{label}:** _empty_"
    return f"**{label}:**\n\n{text}"

def chips_html(items, kind="pos"):
    if not items:
        return "<div class='pills'><span class='pill empty'>—</span></div>"
    cls = "pill pos" if kind == "pos" else "pill unc"
    return "<div class='pills'>" + "".join(f"<span class='{cls}'>{x}</span>" for x in items) + "</div>"

def gt_chips_html(row: pd.Series) -> str:
    def is_one(x) -> bool:
        try: return float(x) == 1.0
        except Exception: return False
    pos = [c for c in LABEL_COLS if c in row and is_one(row[c])]
    header = "<div class='meta' style='margin:4px 0 6px'>Ground‑truth positives</div>"
    if not pos:
        return header + "<div class='pills'><span class='pill empty'>No positive labels</span></div>"
    chips = "".join(f"<span class='pill gt'>{p}</span>" for p in pos)
    return header + f"<div class='pills'>{chips}</div>"

# ───────────────────────── Inference helpers ─────────────────────────
def prepare_tensor(vol_hu: np.ndarray) -> torch.Tensor:
    lung = _hu_window_to_unit(vol_hu, INFER_LUNG_CENTER, INFER_LUNG_WIDTH)
    medi = _hu_window_to_unit(vol_hu, INFER_MEDIAST_CENTER, INFER_MEDIAST_WIDTH)
    bone = _hu_window_to_unit(vol_hu, INFER_BONE_CENTER, INFER_BONE_WIDTH)
    arr = np.stack([lung, medi, bone], 0)  # (3,D,H,W)
    x = torch.from_numpy(arr).float()
    if VAL_TRANSFORM is not None:
        x = VAL_TRANSFORM(x)
    return x

@torch.inference_mode()
def run_model(vol_hu: np.ndarray) -> np.ndarray:
    ensure_model()
    x = prepare_tensor(vol_hu).unsqueeze(0).to(DEVICE)  # (1, C, ...)
    logits = MODEL(x)
    probs = torch.sigmoid(logits).squeeze(0).detach().cpu().numpy()
    return probs  # shape [C]

def derive_pos_unc(probs: np.ndarray, thresholds: np.ndarray, band: float) -> Tuple[List[str], List[str]]:
    thr = thresholds.astype(np.float32)
    pos_mask = probs >= (thr + band)
    unc_mask = (np.abs(probs - thr) <= band) & ~pos_mask
    pos = [LABEL_COLS[i] for i in np.where(pos_mask)[0].tolist()]
    unc = [LABEL_COLS[i] for i in np.where(unc_mask)[0].tolist()]
    return pos, unc

def make_generated_text(pos: List[str], unc: List[str]) -> Tuple[str, str, str]:
    pos_s = ", ".join(pos) if pos else ""
    unc_s = ", ".join(unc) if unc else ""
    findings_text = f"Positive: [{pos_s}]\nUncertain: [{unc_s}]"
    if pos:
        imp_text = f"Abnormalities detected: {', '.join(pos[:3])}."
    elif unc:
        imp_text = "No definite abnormality; several findings are uncertain."
    else:
        imp_text = "No acute abnormality detected."
    return md_strong("Findings", findings_text), md_strong("Impression", imp_text), f"Findings: {findings_text}\n\nImpression: {imp_text}"

def make_scores_df(probs: np.ndarray, thresholds: np.ndarray, band: float) -> pd.DataFrame:
    rows = []
    for i, lab in enumerate(LABEL_COLS):
        p = float(probs[i])
        t = float(thresholds[i])
        if p >= t + band:
            status = "Positive"
        elif abs(p - t) <= band:
            status = "Uncertain"
        else:
            status = "Negative"
        rows.append({"label": lab, "probability": round(p, 4), "threshold": round(t, 3), "status": status})
    # Sort: Positive → Uncertain → Negative, then by prob desc
    order = {"Positive": 0, "Uncertain": 1, "Negative": 2}
    df_scores = pd.DataFrame(rows)
    if not df_scores.empty:
        df_scores["__ord__"] = df_scores["status"].map(order)
        df_scores = df_scores.sort_values(["__ord__", "probability"], ascending=[True, False]).drop(columns="__ord__")
    return df_scores

# ───────────────────────── Common formatter ─────────────────────────
def _format_outputs(object_id_str: str,
                    vol: np.ndarray,
                    gt_findings: str,
                    gt_impression: str,
                    gt_pos_html: str):
    d = vol.shape[0]
    mid = d // 2
    centre, width = 40, 400
    preview = window_to_uint8(vol[mid], centre, width)
    ax = window_to_uint8(plane_slice(vol, "axial", mid), centre, width, out_size=256)
    co = window_to_uint8(plane_slice(vol, "coronal", vol.shape[1]//2), centre, width, out_size=256)
    sa = window_to_uint8(plane_slice(vol, "sagittal", vol.shape[2]//2), centre, width, out_size=256)

    # Placeholders (no inference yet)
    gen_html = (
        "<div class='meta' style='margin:4px 0 6px'>Generated labels</div>"
        "<div class='meta'>Positive</div><div class='pills'><span class='pill empty'>—</span></div>"
        "<div class='meta' style='margin-top:6px'>Uncertain</div><div class='pills'><span class='pill empty'>—</span></div>"
    )
    gen_find_md = md_strong("Findings", "Not computed. Click **Run inference**.")
    gen_impr_md = md_strong("Impression", "Not computed. Click **Run inference**.")
    gen_full = ""

    return (
        object_id_str,
        md_strong("Findings", gt_findings or ""),          # GT (bold)
        md_strong("Impression", gt_impression or ""),      # GT (bold)
        gt_pos_html,                                       # GT positive chips
        gen_html, gen_find_md, gen_impr_md, gen_full,      # generated placeholders
        preview,
        gr.update(value=mid, minimum=0, maximum=d - 1, step=1),
        "axial", "0°",
        vol,
        None,                                              # probs_state cleared
        ax, co, sa,
        f"<span class='badge'>Volume: {vol.shape[0]}×{vol.shape[1]}×{vol.shape[2]}</span>  "
        f"<span class='badge'>Split: {SPLIT_NAME}</span>  "
        f"<span class='badge'>Device: {DEVICE_STR}</span>",
        f"Axial slice {mid+1} / {d}",
        pd.DataFrame(columns=["label","probability","threshold","status"])  # empty scores table
    )

# ──────────────────────────── Call‑backs (load but don’t infer) ────────────────────────────
def sample_case():
    if df.empty:
        raise RuntimeError("CSV is missing or empty; upload an NPZ file instead.")
    row = df.sample(1).iloc[0]
    with np.load(row.img_path, mmap_mode="r") as npz:
        vol = auto_reorient(to_hu(npz["image"]))
    gt_pos = gt_chips_html(row)
    gt_f = row.findings if isinstance(getattr(row, "findings", ""), str) else ""
    gt_i = row.impression if isinstance(getattr(row, "impression", ""), str) else ""
    return _format_outputs(str(row.object_id), vol, gt_f, gt_i, gt_pos)

def load_by_id(object_id: str):
    if df.empty:
        raise RuntimeError("CSV is missing or empty; upload an NPZ file instead.")
    sub = df[df.object_id.astype(str) == str(object_id)]
    if sub.empty:
        return sample_case()
    row = sub.iloc[0]
    with np.load(row.img_path, mmap_mode="r") as npz:
        vol = auto_reorient(to_hu(npz["image"]))
    gt_pos = gt_chips_html(row)
    gt_f = row.findings if isinstance(getattr(row, "findings", ""), str) else ""
    gt_i = row.impression if isinstance(getattr(row, "impression", ""), str) else ""
    return _format_outputs(str(row.object_id), vol, gt_f, gt_i, gt_pos)

def load_uploaded(npz_file: gr.File):
    if npz_file is None:
        raise gr.Error("Please upload an NPZ file first.")
    with np.load(npz_file.name, mmap_mode="r") as npz:
        if "image" not in npz:
            raise gr.Error("NPZ must contain an 'image' array.")
        vol = auto_reorient(to_hu(npz["image"]))
    gt_pos = "<div class='meta' style='margin:4px 0 6px'>Ground‑truth positives</div>" \
             "<div class='pills'><span class='pill empty'>N/A (uploaded)</span></div>"
    return _format_outputs(f"uploaded:{Path(npz_file.name).name}", vol, "", "", gt_pos)

# ───────────────────────── Run inference (button) ─────────────────────────
def run_inference_clicked(vol, unc_band: float):
    if vol is None:
        raise gr.Error("Load a case (random / by ID) or upload an NPZ, then click Run inference.")
    probs = run_model(vol)
    pos, unc = derive_pos_unc(probs, THRESHOLDS, unc_band)
    gen_lbl_html = (
        "<div class='meta' style='margin:4px 0 6px'>Generated labels</div>"
        "<div class='meta'>Positive</div>" + chips_html(pos, "pos") +
        "<div class='meta' style='margin-top:6px'>Uncertain</div>" + chips_html(unc, "unc")
    )
    gen_findings_md, gen_impression_md, gen_full = make_generated_text(pos, unc)
    scores_df = make_scores_df(probs, THRESHOLDS, unc_band)
    return gen_lbl_html, gen_findings_md, gen_impression_md, gen_full, probs, scores_df

# Uncertainty band change → recompute panels *using last probs* (no re‑inference)
def rederive_from_band(unc_band: float, probs: np.ndarray):
    if probs is None or THRESHOLDS is None:
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
    pos, unc = derive_pos_unc(probs, THRESHOLDS, unc_band)
    gen_lbl_html = (
        "<div class='meta' style='margin:4px 0 6px'>Generated labels</div>"
        "<div class='meta'>Positive</div>" + chips_html(pos, "pos") +
        "<div class='meta' style='margin-top:6px'>Uncertain</div>" + chips_html(unc, "unc")
    )
    gen_findings_md, gen_impression_md, gen_full = make_generated_text(pos, unc)
    scores_df = make_scores_df(probs, THRESHOLDS, unc_band)
    return gen_lbl_html, gen_findings_md, gen_impression_md, gen_full, scores_df

# ───────────────────────── Viewer updates ─────────────────────────
def update_view(slice_idx, centre, width, plane, rot, vol):
    if vol is None:
        return None
    sl = plane_slice(vol, plane, int(slice_idx))
    rot_map = {"0°": 0, "90°": 1, "180°": 2, "270°": 3}
    sl = np.rot90(sl, rot_map[rot])
    return window_to_uint8(sl, centre, width)

def refresh_all(slice_idx, centre, width, plane, rot, vol):
    main = update_view(slice_idx, centre, width, plane, rot, vol)
    if vol is None:
        return None, None, None, ""
    ax = window_to_uint8(plane_slice(vol, "axial",    int(slice_idx) if plane=="axial"   else vol.shape[0]//2), centre, width, out_size=256)
    co = window_to_uint8(plane_slice(vol, "coronal",  int(slice_idx) if plane=="coronal" else vol.shape[1]//2), centre, width, out_size=256)
    sa = window_to_uint8(plane_slice(vol, "sagittal", int(slice_idx) if plane=="sagittal" else vol.shape[2]//2), centre, width, out_size=256)
    sizes = {"axial": vol.shape[0], "coronal": vol.shape[1], "sagittal": vol.shape[2]}
    counter = f"{plane.capitalize()} slice {int(slice_idx)+1} / {sizes[plane]}"
    return main, ax, co, sa, counter

def update_slider_range(plane, vol):
    if vol is None:
        return gr.update()
    size = {"axial": vol.shape[0], "coronal": vol.shape[1], "sagittal": vol.shape[2]}[plane]
    return gr.update(value=size//2, minimum=0, maximum=size-1, step=1)

def apply_preset(preset):
    if preset in PRESETS:
        c, w = PRESETS[preset]
        return gr.update(value=c), gr.update(value=w)
    return gr.update(), gr.update()

def reset_view(vol):
    if vol is None:
        return gr.update(), gr.update(), gr.update()
    mid = vol.shape[0] // 2
    return gr.update(value="axial"), gr.update(value="0°"), gr.update(value=mid)

# ──────────────────────────────  UI  ────────────────────────────────
with gr.Blocks(title="CT Viewer • SigLIP inference", css=CSS, theme=gr.themes.Soft()) as demo:
    vol_state   = gr.State(None)
    probs_state = gr.State(None)

    gr.HTML(
        f"""
        <div class="header">
          <div>
            <h1>CT Viewer + Inference</h1>
            <div class="meta">Random sample (CSV) or upload NPZ → <b>⚡ Run inference</b> → organize & visualize</div>
          </div>
          <div class="meta">Model: <b>{Path(MODEL_PATH).name}</b> · Device: <b>{DEVICE_STR}</b></div>
        </div>
        """
    )

    # Row 0: upload OR random / jump
    with gr.Row():
        upload = gr.File(label="Upload CT NPZ (optional)", file_types=[".npz"], file_count="single")
        with gr.Column():
            sample_btn = gr.Button(f"🎲 Random sample ({SPLIT_NAME})", variant="secondary")
            case_dd = gr.Dropdown(
                choices=[str(x) for x in df.object_id.astype(str).tolist()],
                label="Jump to case (object_id)",
                value=None, allow_custom_value=False, interactive=True,
            )

    with gr.Row():
        # Left: controls
        with gr.Column(scale=1, elem_classes=["panel", "controls"]):
            plane_sel = gr.Radio(["axial", "coronal", "sagittal"], value="axial", label="View plane")
            rot_sel   = gr.Radio(["0°", "90°", "180°", "270°"], value="0°", label="Rotation")

            with gr.Row():
                win_c = gr.Slider(-1000, 1500, value=40,  step=10, label="Window centre (HU)")
                win_w = gr.Slider(100,   2000, value=400, step=10, label="Window width (HU)")

            preset = gr.Dropdown(choices=list(PRESETS.keys()), label="Window preset", value="Mediastinum")
            slice_sl = gr.Slider(label="Slice #", minimum=0, maximum=1, step=1)

            gr.HTML("<hr class='divider'>")
            unc_band = gr.Slider(0.0, 0.3, value=0.05, step=0.01,
                                 label="Uncertainty band (± around threshold for 'Uncertain')")

            # New: explicit Run inference button
            infer_btn = gr.Button("⚡ Run inference", variant="primary")

            with gr.Row():
                reset_btn = gr.Button("Reset view")
                gr.HTML("")

        # Middle: viewer
        with gr.Column(scale=2, elem_classes=["panel", "viewer-card"]):
            viewer = gr.Image(height=768, image_mode="L", label=None, show_label=False)
            slice_counter = gr.HTML("<div class='slice-caption'>&nbsp;</div>")
            gr.HTML("<hr class='divider'>")
            with gr.Row(elem_classes=["thumb-row"]):
                ax_thumb = gr.Image(label="Axial",   show_label=True, height=170, elem_classes=["thumb"])
                co_thumb = gr.Image(label="Coronal", show_label=True, height=170, elem_classes=["thumb"])
                sa_thumb = gr.Image(label="Sagittal",show_label=True, height=170, elem_classes=["thumb"])

        # Right: reports / metadata
        with gr.Column(scale=1, elem_classes=["panel"]):
            object_id  = gr.Textbox(label="object_id", interactive=False)
            dim_info   = gr.HTML("")  # badges
            with gr.Tabs():
                with gr.Tab("Ground truth"):
                    findings   = gr.Markdown(label="Findings")    # bold
                    impression = gr.Markdown(label="Impression")  # bold
                    pos_html   = gr.HTML()  # GT positives (blue)
                with gr.Tab("Generated (current)"):
                    gen_lbl_html      = gr.HTML()       # chips (green/red)
                    gen_findings_md   = gr.Markdown(label="Findings")    # bold
                    gen_impression_md = gr.Markdown(label="Impression")  # bold
                    gen_rep           = gr.Textbox(label="Full report (raw)", lines=10)
                    gen_scores        = gr.Dataframe(headers=["label","probability","threshold","status"],
                                                     interactive=False)

    # Output order for loaders (no inference yet)
    outputs_load = [
        object_id, findings, impression, pos_html,
        gen_lbl_html, gen_findings_md, gen_impression_md, gen_rep,
        viewer, slice_sl, plane_sel, rot_sel,
        vol_state, probs_state,
        ax_thumb, co_thumb, sa_thumb, dim_info, slice_counter,
        gen_scores
    ]

    # Loaders: sample / by-id / upload (load → clear generated panels)
    sample_btn.click(sample_case, [], outputs_load)
    case_dd.change(load_by_id, [case_dd], outputs_load)
    upload.change(load_uploaded, [upload], outputs_load)

    # Run inference (uses current volume + band)
    infer_btn.click(
        run_inference_clicked, [vol_state, unc_band],
        [gen_lbl_html, gen_findings_md, gen_impression_md, gen_rep, probs_state, gen_scores]
    )

    # Uncertainty band change → recompute panels using cached probs (no model forward)
    unc_band.change(
        rederive_from_band, [unc_band, probs_state],
        [gen_lbl_html, gen_findings_md, gen_impression_md, gen_rep, gen_scores],
        queue=False
    )

    # Viewer interactions
    plane_sel.change(update_slider_range, [plane_sel, vol_state], slice_sl).then(
        refresh_all,
        [slice_sl, win_c, win_w, plane_sel, rot_sel, vol_state],
        [viewer, ax_thumb, co_thumb, sa_thumb, slice_counter],
        queue=False
    )
    for ctl in (slice_sl, win_c, win_w, rot_sel):
        ctl.change(
            refresh_all,
            [slice_sl, win_c, win_w, plane_sel, rot_sel, vol_state],
            [viewer, ax_thumb, co_thumb, sa_thumb, slice_counter],
            queue=False
        )
    preset.change(apply_preset, [preset], [win_c, win_w]).then(
        refresh_all, [slice_sl, win_c, win_w, plane_sel, rot_sel, vol_state],
        [viewer, ax_thumb, co_thumb, sa_thumb, slice_counter], queue=False
    )
    reset_btn.click(
        reset_view, [vol_state], [plane_sel, rot_sel, slice_sl]
    ).then(
        update_slider_range, [plane_sel, vol_state], slice_sl
    ).then(
        refresh_all, [slice_sl, win_c, win_w, plane_sel, rot_sel, vol_state],
        [viewer, ax_thumb, co_thumb, sa_thumb, slice_counter], queue=False
    )

# Launch
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    demo.launch(share=True)
