"""CT in, report out: input loading, lung segmentation, preprocessing, generation.

Everything model-side is the verified TC1 code inside the base image, used unmodified:
  * preprocessing   /app/validation/preprocess_npz.py build_transforms — the cohort's own
                    chain (LPS, 1.5 mm, -1024 padding, 256^3 crop around the lung lobes)
  * generation      /app/src/pipeline.py ReportGenerator, greedy decoding
The lung mask comes from TotalSegmentator (lobe labels 10-14), as for the cohort.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import nibabel as nib
import numpy as np
import SimpleITK as sitk
import torch

sys.path.insert(0, "/app/src")
sys.path.insert(0, "/app/validation")
import preprocess_npz as prep                      # noqa: E402
from pipeline import ReportGenerator, centre_crop   # noqa: E402

LUNG_LOBES = ["lung_upper_lobe_left", "lung_lower_lobe_left", "lung_upper_lobe_right",
              "lung_middle_lobe_right", "lung_lower_lobe_right"]
LIVER = 5                                           # TotalSegmentator v2 label; same sub-model as the lobes
SPACING, SHAPE = (1.5, 1.5, 1.5), (256, 256, 256)
MIN_SLICES, MIN_XY = 100, 200                       # same limits as the cohort preprocessing
SEED = 42


class InputError(ValueError):
    """The upload cannot be used; the message is shown to the user as is."""


@dataclass
class Case:
    nifti: str                                      # CT as NIfTI (converted if DICOM)
    source: str                                     # "NIfTI" / "DICOM series (N files)"
    shape: tuple
    spacing: tuple
    workdir: str
    mask: Optional[str] = None
    volume: Optional[np.ndarray] = None             # (256, 256, 256) int16 HU, LPS
    lungs: Optional[np.ndarray] = None              # (256, 256, 256) bool, same grid
    findings_block: str = ""
    report: str = ""
    si_flipped: bool = False                        # header's head-foot direction was reversed
    scores: Dict[str, float] = field(default_factory=dict)
    timing: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------- input

def load_input(paths: List[str]) -> Case:
    """NIfTI file, DICOM files, or a .zip of a DICOM series -> Case with a NIfTI path."""
    if not paths:
        raise InputError("No file uploaded.")
    work = tempfile.mkdtemp(prefix="case_", dir=os.environ.get("GUI_WORK", "/tmp"))
    niftis = [p for p in paths if p.lower().endswith((".nii", ".nii.gz"))]
    if niftis:
        if len(niftis) > 1:
            raise InputError("Upload one NIfTI volume at a time.")
        src, label = niftis[0], "NIfTI"
    else:
        dcm_dir = os.path.join(work, "dicom")
        os.makedirs(dcm_dir)
        for p in paths:
            if p.lower().endswith(".zip"):
                with zipfile.ZipFile(p) as z:
                    z.extractall(dcm_dir)
            else:
                shutil.copy(p, dcm_dir)
        src, n = _dicom_to_nifti(dcm_dir, os.path.join(work, "ct.nii.gz"))
        label = f"DICOM series ({n} slices)"
    img = nib.load(src)
    shape = tuple(int(s) for s in img.shape[:3])
    spacing = tuple(round(float(z), 3) for z in img.header.get_zooms()[:3])
    if len(img.shape) != 3:
        raise InputError(f"Expected a 3D volume, got shape {tuple(img.shape)}.")
    if shape[2] < MIN_SLICES or min(shape[:2]) < MIN_XY:
        raise InputError(f"Volume {shape} is too small: needs at least {MIN_XY}x{MIN_XY} "
                         f"in-plane and {MIN_SLICES} slices (a full chest CT series).")
    return Case(nifti=src, source=label, shape=shape, spacing=spacing, workdir=work)


def _dicom_to_nifti(root: str, out: str):
    """Pick the series with the most slices under root and write it as NIfTI."""
    best, best_files = None, []
    for d, _, _ in os.walk(root):
        for sid in sitk.ImageSeriesReader.GetGDCMSeriesIDs(d) or []:
            files = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(d, sid)
            if len(files) > len(best_files):
                best, best_files = sid, files
    if not best_files:
        raise InputError("No DICOM image series found in the upload.")
    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(best_files)
    img = reader.Execute()
    sitk.WriteImage(img, out)                       # SimpleITK writes the NIfTI affine in RAS
    return out, len(best_files)


# ---------------------------------------------------------------- pipeline stages

def segment_lungs(case: Case) -> None:
    """TotalSegmentator in its own process. In-process, nnU-Net forks workers from a
    parent that already holds the report model on CUDA, and each fork grabs GPU memory
    until the card is full. A child process also hands its GPU memory back on exit."""
    t = time.perf_counter()
    case.mask = os.path.join(case.workdir, "lungs.nii.gz")
    r = subprocess.run(["TotalSegmentator", "-i", case.nifti, "-o", case.mask, "--ml",
                        "--roi_subset", *LUNG_LOBES, "liver", "-d", "gpu", "-q"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(case.mask):
        raise RuntimeError("lung segmentation failed: " + (r.stderr or r.stdout)[-600:])
    case.timing["segmentation_s"] = round(time.perf_counter() - t, 1)


_TX = None


def preprocess(case: Case) -> None:
    """The cohort's preprocessing, exactly as process_one() applies it."""
    global _TX
    t = time.perf_counter()
    if _TX is None:
        _TX = prep.build_transforms(SPACING, SHAPE, None, np.int16, np.uint16)
    try:
        dd = _TX({"ct": case.nifti, "totalseg": case.mask})
    except prep.NoLungLabelsError:
        raise InputError("No lungs found in this volume — is it a chest CT?")
    ct = np.clip(np.round(np.asarray(dd["ct"])), -32768, 32767)
    case.volume = prep.transpose_chwd_to_cdhw(ct).astype(np.int16)[0]
    seg = prep.transpose_chwd_to_cdhw(np.asarray(dd["totalseg"]))[0]
    case.lungs = np.isin(seg, [10, 11, 12, 13, 14])
    # Some NIfTI exports store the slice direction reversed in the header, and LPS
    # reorientation then puts the head at index 0. Anatomy decides instead: the liver lies
    # below the lungs, so in correct LPS (index 0 = feet) its centroid index is lower.
    # Found in 3 of the 100 TC1 test volumes; fixed here for both the view and the model.
    liver = np.nonzero(seg == LIVER)[0]
    if liver.size and liver.mean() > np.nonzero(case.lungs)[0].mean():
        case.volume, case.lungs = case.volume[::-1].copy(), case.lungs[::-1].copy()
        case.si_flipped = True
    case.timing["preprocessing_s"] = round(time.perf_counter() - t, 1)


class Model:
    """ReportGenerator loaded once; the probe's scores are captured with a forward hook."""

    def __init__(self):
        t = time.perf_counter()
        self.gen = ReportGenerator("/app/weights", "/app/ject",
                                   "/app/ject/ject_224_ep45_encoder.pt",
                                   "google/medgemma-1.5-4b-it", "cuda")
        self._probs = None
        self.gen.probe.register_forward_hook(
            lambda _m, _i, out: setattr(self, "_probs", torch.sigmoid(out).float().cpu().numpy()))
        self.load_s = round(time.perf_counter() - t, 1)

    @torch.no_grad()
    def generate(self, case: Case) -> None:
        t = time.perf_counter()
        torch.manual_seed(SEED)
        vol = torch.from_numpy(np.ascontiguousarray(centre_crop(case.volume[None]))).unsqueeze(0)
        res = self.gen.generate(torch.stack([vol]))[0]
        case.findings_block, case.report = res["findings_block"], res["report"]
        probs = self._probs[0].round(4)
        case.scores = {name: float(probs[v["index"]])
                       for name, v in self.gen.policy["policy"].items()}
        case.timing["generation_s"] = round(time.perf_counter() - t, 1)

    def tiers(self, case: Case) -> List[dict]:
        """Every policy finding with its score and tier, as the findings block decides it."""
        rows = []
        for name, v in self.gen.policy["policy"].items():
            s = case.scores[name]
            if v.get("assertable") and v.get("t_pos") is not None and s >= v["t_pos"]:
                tier = "present"
            elif s >= v["t_neg"]:
                tier = "possible"
            else:
                tier = "not detected"
            rows.append({"finding": name, "score": s, "t_neg": v["t_neg"],
                         "t_pos": v.get("t_pos"), "tier": tier})
        return rows


def run(case: Case, model: Model, step: Callable[[float, str], None]) -> Case:
    step(0.15, "Segmenting the lungs (TotalSegmentator)…")
    segment_lungs(case)
    step(0.45, "Preprocessing: LPS · 1.5 mm · 256³ lung crop…")
    preprocess(case)
    step(0.60, "Generating the report (JECT_Generator)…")
    model.generate(case)
    return case


def cleanup_old(root: str, keep_s: float = 6 * 3600) -> None:
    """Uploaded scans are deleted after a few hours; nothing is kept long-term."""
    now = time.time()
    for d in glob.glob(os.path.join(root, "case_*")):
        if now - os.path.getmtime(d) > keep_s:
            shutil.rmtree(d, ignore_errors=True)
