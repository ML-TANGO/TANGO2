# Vendored verbatim from the cohort's own `preprocess_npz.py`
# (`ct_foundation_pipeline/06_preprocess_npz/preprocess_ctrate.py`), which is the
# production script that built the main SNUH chest-CT dataset. Baked into the image
# rather than executed from the read-only data mount, so the image is self-contained
# and the version used for a run is pinned with it.
#
# Diffed against the CT-RATE training chain (ChestCT_Playground@9e2415c
# `preprocess/`, which is where the geometry the encoder was fitted to is defined):
# same transform order, same LPS axis pinning, same trilinear/nearest resampling,
# same -1024 air padding, and `AnatomyAwareCropd` computes byte-for-byte the same
# crop starts as that repo's `LungBBoxCropd`. The two are interchangeable; this one
# is used because it is what ships with the cohort and what `npz_path` in the CSV
# refers to.
#
# Do not edit. Windowing in particular must stay off: the bundle crops in HU space
# and windows on the GPU, so pre-windowing here yields a fluent but wrong report
# rather than an error.
# preprocess_multi_to_npz_fixed_rex.py
import argparse
import multiprocessing as mp
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Sequence

import numpy as np
import pandas as pd
import nibabel as nib
from tqdm import tqdm

from monai.transforms import (
    Compose,
    LoadImaged,
    EnsureChannelFirstd,
    Orientationd,
    Spacingd,
    ScaleIntensityRanged,
    SpatialPadd,
    CenterSpatialCropd,
    CastToTyped,
    MapTransform,
    Lambdad,
)

# TotalSegmentator v1/v2 lung lobe labels (default)
DEFAULT_LUNG_LABELS = (10, 11, 12, 13, 14)
# 10: lung_upper_lobe_left
# 11: lung_lower_lobe_left
# 12: lung_upper_lobe_right
# 13: lung_middle_lobe_right
# 14: lung_lower_lobe_right

# -------------------------------
# Globals set per worker
# -------------------------------
_TX = None
_CFG = None


# -------------------------------
# Exceptions
# -------------------------------

class NoLungLabelsError(RuntimeError):
    """Raised when no lung labels are found in the TotalSegmentator mask."""
    pass


# -------------------------------
# Helpers
# -------------------------------

def case_id_from_niigz(p: Path) -> str:
    name = p.name
    if name.endswith(".nii.gz"):
        return name[:-7]
    if name.endswith(".nii"):
        return name[:-4]
    return p.stem

def safe_zooms(img: nib.Nifti1Image) -> Tuple[float, float, float]:
    z = img.header.get_zooms()
    return float(z[0]), float(z[1]), float(z[2])

def transpose_chwd_to_cdhw(x: np.ndarray) -> np.ndarray:
    # (C, H, W, D) -> (C, D, H, W)
    if x.ndim != 4:
        raise ValueError(f"Expected 4D (C,H,W,D), got shape={x.shape}")
    return np.ascontiguousarray(np.transpose(x, (0, 3, 1, 2)))

# -------------------------------
# ReX fix: channel-first + copy CT affine/meta
# -------------------------------

class EnsureRexChannelFirstAndCopyCTAffined(MapTransform):
    """
    - Ensures rex is channel-first: (F, H, W, D)
    - Copies CT geometry (affine/original_affine/pixdim if available) to rex meta
      so Orientationd/Spacingd operate in the same physical space.

    IMPORTANT: uses torch.movedim for torch tensors (MetaTensor), not np.moveaxis.
    """
    def __init__(self, keys, ref_key: str = "ct", allow_missing_keys: bool = False):
        super().__init__(keys, allow_missing_keys)
        self.ref_key = ref_key

    @staticmethod
    def _is_torch(x) -> bool:
        try:
            import torch
            return torch.is_tensor(x)
        except Exception:
            return False

    @staticmethod
    def _unsqueeze0(x):
        if EnsureRexChannelFirstAndCopyCTAffined._is_torch(x):
            return x.unsqueeze(0)
        return x[None, ...]

    @staticmethod
    def _movedim_last_to_first(x):
        if EnsureRexChannelFirstAndCopyCTAffined._is_torch(x):
            import torch
            return torch.movedim(x, -1, 0)
        return np.moveaxis(x, -1, 0)

    @staticmethod
    def _to_numpy_affine(a):
        """Robustly convert affine-like objects to a numpy array copy."""
        if a is None:
            return None
        if isinstance(a, np.ndarray):
            return a.copy()
        if EnsureRexChannelFirstAndCopyCTAffined._is_torch(a):
            return a.detach().cpu().numpy().copy()
        return np.array(a, copy=True)

    def __call__(self, data: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(data)

        ref = d.get(self.ref_key, None)
        if ref is None:
            raise KeyError(f"Reference key '{self.ref_key}' missing or None.")

        # CT expected after EnsureChannelFirstd: (1,H,W,D) typically
        if ref.ndim == 4:
            ref_spatial = tuple(ref.shape[1:4])
        elif ref.ndim == 3:
            ref_spatial = tuple(ref.shape)
        else:
            raise ValueError(f"Unexpected CT shape: {tuple(ref.shape)}")

        # Get CT meta from sidecar dict if present, otherwise from MetaTensor.meta
        ct_meta = d.get(f"{self.ref_key}_meta_dict", None) or {}
        ct_affine = ct_meta.get("affine", None)
        ct_orig_affine = ct_meta.get("original_affine", None)
        ct_pixdim = ct_meta.get("pixdim", None)

        # Fallback: MetaTensor meta
        if (ct_affine is None or ct_orig_affine is None) and hasattr(ref, "meta"):
            ct_affine = ct_affine if ct_affine is not None else ref.meta.get("affine", None)
            ct_orig_affine = ct_orig_affine if ct_orig_affine is not None else ref.meta.get("original_affine", None)
            ct_pixdim = ct_pixdim if ct_pixdim is not None else ref.meta.get("pixdim", None)

        ct_affine_np = self._to_numpy_affine(ct_affine)
        ct_orig_affine_np = self._to_numpy_affine(ct_orig_affine) if ct_orig_affine is not None else (
            ct_affine_np.copy() if ct_affine_np is not None else None
        )

        for key in self.key_iterator(d):
            x = d.get(key, None)
            if x is None:
                continue

            # --- Ensure channel-first layout ---
            if x.ndim == 3:
                x = self._unsqueeze0(x)  # (1,H,W,D)
            elif x.ndim == 4:
                # Case A: already (F,H,W,D)
                if tuple(x.shape[1:4]) == ref_spatial:
                    pass
                # Case B: (H,W,D,F) -> move last axis to first
                elif tuple(x.shape[0:3]) == ref_spatial:
                    x = self._movedim_last_to_first(x)
                else:
                    raise ValueError(
                        f"[{key}] rex shape {tuple(x.shape)} does not match CT spatial {ref_spatial} "
                        f"in either (F,H,W,D) or (H,W,D,F)."
                    )
            else:
                raise ValueError(f"[{key}] Expected 3D or 4D, got {x.ndim}D shape={tuple(x.shape)}")

            d[key] = x

            # --- Copy CT geometry into rex meta dict (sidecar) ---
            meta_key = f"{key}_meta_dict"
            rex_meta = d.get(meta_key, None) or {}
            rex_meta["original_channel_dim"] = 0
            rex_meta["channel_dim"] = 0
            rex_meta["spatial_shape"] = ref_spatial

            if ct_affine_np is not None:
                rex_meta["affine"] = ct_affine_np.copy()
            if ct_orig_affine_np is not None:
                rex_meta["original_affine"] = ct_orig_affine_np.copy()
            if ct_pixdim is not None:
                rex_meta["pixdim"] = tuple(ct_pixdim)

            d[meta_key] = rex_meta

            # --- Also update MetaTensor meta if applicable (extra-safe) ---
            if hasattr(x, "meta"):
                if ct_affine_np is not None:
                    x.meta["affine"] = ct_affine_np.copy()
                if ct_orig_affine_np is not None:
                    x.meta["original_affine"] = ct_orig_affine_np.copy()
                if ct_pixdim is not None:
                    x.meta["pixdim"] = tuple(ct_pixdim)

        return d


# -------------------------------
# Anatomy-aware cropping using lung bounding box
# -------------------------------

class AnatomyAwareCropd(MapTransform):
    """
    Crop to `roi_size` centered on the lung bounding box from TotalSegmentator.

    After Orientationd("LPS") + Spacingd, the axes are (C, R-L, A-P, I-S).
    The crop ensures the lung region is fully contained when possible.
    For volumes taller than roi_size along S-I, it biases towards keeping
    the superior (lung) region and extends inferiorly into the abdomen.

    Raises NoLungLabelsError if no lung labels are found in the mask.
    """

    def __init__(
        self,
        keys: Sequence[str],
        seg_key: str = "totalseg",
        roi_size: Tuple[int, int, int] = (384, 384, 320),
        lung_labels: Sequence[int] = DEFAULT_LUNG_LABELS,
        allow_missing_keys: bool = False,
    ):
        super().__init__(keys, allow_missing_keys)
        self.seg_key = seg_key
        self.roi_size = tuple(roi_size)
        self.lung_labels = set(lung_labels)

    def __call__(self, data: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(data)

        seg = d.get(self.seg_key)
        if seg is None:
            raise NoLungLabelsError(
                f"No TotalSegmentator mask (key='{self.seg_key}') found — "
                "cannot perform anatomy-aware cropping."
            )

        seg_np = np.asarray(seg)
        # seg shape: (C, H, W, D) after EnsureChannelFirst
        if seg_np.ndim == 4:
            seg_3d = seg_np[0]
        elif seg_np.ndim == 3:
            seg_3d = seg_np
        else:
            raise ValueError(f"Unexpected totalseg ndim={seg_np.ndim}")

        spatial_shape = seg_3d.shape  # (H, W, D) = (R-L, A-P, I-S) in RAS

        # Find lung voxels
        lung_mask = np.isin(seg_3d, list(self.lung_labels))

        if not lung_mask.any():
            raise NoLungLabelsError(
                f"No lung labels {sorted(self.lung_labels)} detected in TotalSegmentator mask. "
                f"Unique labels present: {np.unique(seg_3d).tolist()}"
            )

        # Bounding box of lungs
        coords = np.argwhere(lung_mask)  # (N, 3)
        bbox_min = coords.min(axis=0)  # (3,)
        bbox_max = coords.max(axis=0)  # (3,)
        bbox_center = (bbox_min + bbox_max) // 2

        # Compute crop start for each axis.
        # Try to contain the full lung bbox; center remaining space around it.
        starts = []
        for i in range(3):
            target = self.roi_size[i]
            vol_size = spatial_shape[i]

            if vol_size <= target:
                # Volume is smaller or equal after padding — no crop needed on this axis
                starts.append(0)
                continue

            lung_extent = bbox_max[i] - bbox_min[i] + 1

            if lung_extent >= target:
                # Lungs bigger than crop — center on lung center
                start = bbox_center[i] - target // 2
            else:
                # Center lungs within the crop
                slack = target - lung_extent
                start = bbox_min[i] - slack // 2

            # Clamp to valid range
            start = max(0, min(start, vol_size - target))
            starts.append(start)

        # Crop all keys
        for key in self.key_iterator(d):
            x = d.get(key)
            if x is None:
                continue
            # x shape: (C, H, W, D)
            d[key] = x[
                :,
                starts[0]:starts[0] + self.roi_size[0],
                starts[1]:starts[1] + self.roi_size[1],
                starts[2]:starts[2] + self.roi_size[2],
            ]

        # Also crop the seg_key itself if it wasn't in keys
        if self.seg_key not in set(self.keys):
            x = d[self.seg_key]
            d[self.seg_key] = x[
                :,
                starts[0]:starts[0] + self.roi_size[0],
                starts[1]:starts[1] + self.roi_size[1],
                starts[2]:starts[2] + self.roi_size[2],
            ]

        return d


# -------------------------------
# Build MONAI preprocessing pipeline
# -------------------------------

def build_transforms(target_spacing, target_shape, hu_window, img_dtype, lbl_dtype,
                     lung_labels=DEFAULT_LUNG_LABELS):
    keys_all = ("ct", "totalseg", "rex")

    steps = [
        LoadImaged(keys=keys_all, allow_missing_keys=True, reader="NibabelReader"),
        EnsureChannelFirstd(keys=("ct", "totalseg"), allow_missing_keys=True),

        EnsureRexChannelFirstAndCopyCTAffined(keys=("rex",), ref_key="ct", allow_missing_keys=True),

        Orientationd(
            keys=keys_all, axcodes="LPS",
            labels=(("L","R"),("P","A"),("I","S")),
            allow_missing_keys=True
        ),

        Spacingd(
            keys=keys_all,
            pixdim=target_spacing,
            mode=("trilinear", "nearest", "nearest"),
            align_corners=True,
            allow_missing_keys=True
        ),
    ]

    # Optional HU windowing (skip when hu_window is None → save raw HU as int16)
    if hu_window is not None:
        steps.append(
            ScaleIntensityRanged(
                keys="ct",
                a_min=hu_window[0], a_max=hu_window[1],
                b_min=0.0, b_max=1.0,
                clip=True,
                allow_missing_keys=True
            )
        )

    # Pad CT with -1024 (air in HU); pad masks with 0 (background label)
    steps.append(
        SpatialPadd(keys=("ct",), spatial_size=target_shape, allow_missing_keys=True,
                    constant_values=-1024)
    )
    steps.append(
        SpatialPadd(keys=("totalseg", "rex"), spatial_size=target_shape, allow_missing_keys=True)
    )

    # Anatomy-aware crop centered on lungs (replaces CenterSpatialCropd)
    steps.append(
        AnatomyAwareCropd(
            keys=keys_all,
            seg_key="totalseg",
            roi_size=target_shape,
            lung_labels=lung_labels,
            allow_missing_keys=True,
        )
    )

    steps.append(
        CastToTyped(keys=("totalseg", "rex"), dtype=lbl_dtype, allow_missing_keys=True)
    )

    return Compose(steps)


# -------------------------------
# Multiprocessing init
# -------------------------------

def _init_worker(cfg: Dict[str, Any]):
    global _TX, _CFG
    _CFG = cfg
    _TX = build_transforms(
        target_spacing=cfg["target_spacing"],
        target_shape=cfg["target_shape"],
        hu_window=cfg["hu_window"],
        img_dtype=cfg["img_dtype"],
        lbl_dtype=cfg["lbl_dtype"],
        lung_labels=cfg["lung_labels"],
    )

# -------------------------------
# Worker
# -------------------------------

def process_one(args) -> Dict[str, Any]:
    global _TX, _CFG
    ct_path, original_root, totalseg_root, rex_root, out_root = args

    ct_path = Path(ct_path)
    original_root = Path(original_root)
    totalseg_root = Path(totalseg_root)
    rex_root = Path(rex_root)
    out_root = Path(out_root)

    rel = ct_path.relative_to(original_root)
    tot_path = totalseg_root / rel
    rex_path = rex_root / rel

    case_id = case_id_from_niigz(ct_path)

    # This dataset stores masks as "<case_id>_totalseg.nii.gz"; the pipeline default
    # expects the same filename as the CT. Fall back to the suffixed name.
    if not tot_path.exists():
        alt = totalseg_root / f"{case_id}_totalseg.nii.gz"
        if alt.exists():
            tot_path = alt

    out_file = out_root / f"{case_id}.npz"

    result: Dict[str, Any] = {
        "case_id": case_id,
        "ct_path": str(ct_path),
        "totalseg_path": str(tot_path) if tot_path.exists() else "",
        "rex_path": str(rex_path) if rex_path.exists() else "",
        "status": None,
        "ct_original_shape": None,
        "ct_original_spacing": None,
        "rex_original_shape": None,
        "processed_ct_shape": None,
        "processed_tot_shape": None,
        "processed_rex_shape": None,
        "out_npz": str(out_file),
    }

    if out_file.exists():
        result["status"] = "already_exists"
        return result

    # Header metadata
    try:
        ct_img = nib.load(str(ct_path))
        result["ct_original_shape"] = tuple(ct_img.shape)
        result["ct_original_spacing"] = safe_zooms(ct_img)
    except Exception as e:
        result["status"] = f"error_ct_load: {type(e).__name__}: {e}"
        return result

    # Optional: record rex shape if present
    if rex_path.exists():
        try:
            rex_img = nib.load(str(rex_path))
            result["rex_original_shape"] = tuple(rex_img.shape)
        except Exception:
            pass

    # Skip volumes that are too small (e.g. partial scans, localizers)
    orig_shape = ct_img.shape[:3]
    if orig_shape[2] < 100:
        result["status"] = f"error_too_small: depth={orig_shape[2]} < 100 slices"
        print(f"[SKIP] {case_id}: depth={orig_shape[2]} < 100 slices")
        return result
    if orig_shape[0] < 200 or orig_shape[1] < 200:
        result["status"] = f"error_too_small: xy=({orig_shape[0]},{orig_shape[1]}) < 200"
        print(f"[SKIP] {case_id}: xy=({orig_shape[0]},{orig_shape[1]}) < 200")
        return result

    # Require totalseg mask for anatomy-aware cropping
    if not tot_path.exists():
        result["status"] = "error_no_totalseg: TotalSegmentator mask not found"
        print(f"[ERROR] {case_id}: TotalSegmentator mask not found at {tot_path}")
        return result

    # Build dict for MONAI
    data_dict: Dict[str, Any] = {"ct": str(ct_path), "totalseg": str(tot_path)}
    if rex_path.exists():
        data_dict["rex"] = str(rex_path)

    try:
        dd = _TX(data_dict)

        # CT: clip + round for int16, or direct cast for float dtypes
        ct_np = np.asarray(dd["ct"])
        if _CFG["img_dtype"] == np.int16:
            ct_np = np.clip(np.round(ct_np), -32768, 32767)
        ct = transpose_chwd_to_cdhw(ct_np).astype(_CFG["img_dtype"])
        save_dict = {"ct": ct}
        result["processed_ct_shape"] = tuple(ct.shape)

        if "totalseg" in dd:
            tot = transpose_chwd_to_cdhw(np.asarray(dd["totalseg"])).astype(_CFG["lbl_dtype"])
            save_dict["totalseg"] = tot
            result["processed_tot_shape"] = tuple(tot.shape)

        if "rex" in dd:
            rex = transpose_chwd_to_cdhw(np.asarray(dd["rex"])).astype(_CFG["lbl_dtype"])
            save_dict["rex"] = rex
            result["processed_rex_shape"] = tuple(rex.shape)

        if _CFG["compress"]:
            np.savez_compressed(out_file, **save_dict)
        else:
            np.savez(out_file, **save_dict)

        result["status"] = "processed"
        return result

    except NoLungLabelsError as e:
        result["status"] = f"error_no_lungs: {e}"
        print(f"[ERROR] {case_id}: {e}")
        return result

    except Exception as e:
        result["status"] = f"error_transform: {type(e).__name__}: {e}"
        return result

# -------------------------------
# Main
# -------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_root", required=True)
    ap.add_argument("--dst", required=True)

    ap.add_argument("--target_spacing", nargs=3, type=float, default=(1.0, 1.0, 1.0))
    ap.add_argument("--target_shape", nargs=3, type=int, default=(384, 384, 320))
    ap.add_argument("--hu_window", nargs=2, type=float, default=None,
                    help="HU window [min, max] for ScaleIntensityRange. "
                         "Omit to save raw HU values (for int16 storage).")

    ap.add_argument("--img_dtype", type=str, default="int16",
                    choices=["int16", "float16", "float32"])
    ap.add_argument("--lbl_dtype", type=str, default="uint16",
                    choices=["uint8", "uint16", "int16"])

    ap.add_argument("--lung_labels", nargs="+", type=int, default=list(DEFAULT_LUNG_LABELS),
                    help="TotalSegmentator lung label IDs for anatomy-aware cropping. "
                         "Default: 10 11 12 13 14 (lung lobes)")

    ap.add_argument("--compress", action="store_true")
    ap.add_argument("--nproc", type=int, default=max(mp.cpu_count() - 2, 4))

    ap.add_argument("--original_dirname", type=str, default="original")
    ap.add_argument("--rex_dirname", type=str, default="rexgrounding")
    ap.add_argument("--totalseg_dirname", type=str, default="totalseg")
    args = ap.parse_args()

    data_root = Path(args.data_root)
    original_root = data_root / args.original_dirname
    rex_root = data_root / args.rex_dirname
    totalseg_root = data_root / args.totalseg_dirname

    out_root = Path(args.dst)
    out_root.mkdir(parents=True, exist_ok=True)

    img_dtype = {"int16": np.int16, "float16": np.float16, "float32": np.float32}[args.img_dtype]
    lbl_dtype = {"uint8": np.uint8, "uint16": np.uint16, "int16": np.int16}[args.lbl_dtype]

    cfg = {
        "target_spacing": tuple(args.target_spacing),
        "target_shape": tuple(args.target_shape),
        "hu_window": tuple(args.hu_window) if args.hu_window is not None else None,
        "img_dtype": img_dtype,
        "lbl_dtype": lbl_dtype,
        "lung_labels": tuple(args.lung_labels),
        "compress": bool(args.compress),
    }

    ct_paths = sorted(original_root.rglob("*.nii.gz"))
    print(f"Found {len(ct_paths)} CT files under: {original_root}")

    tasks = [(p, original_root, totalseg_root, rex_root, out_root) for p in ct_paths]

    print(f"Starting preprocessing with nproc={args.nproc} ... (compress={cfg['compress']})")
    print(f"  target_spacing={cfg['target_spacing']}, target_shape={cfg['target_shape']}")
    print(f"  hu_window={cfg['hu_window']}, img_dtype={args.img_dtype}")
    print(f"  lung_labels={cfg['lung_labels']}")

    with mp.Pool(args.nproc, initializer=_init_worker, initargs=(cfg,)) as pool:
        results = list(tqdm(
            pool.imap(process_one, tasks),
            total=len(tasks),
            desc="Preprocessing",
            unit="case",
            ncols=110
        ))

    df = pd.DataFrame(results)
    meta_csv = out_root / "preprocessing_metadata.csv"
    df.to_csv(meta_csv, index=False)

    print(f"\nSaved metadata to: {meta_csv}")
    print("\nStatus counts:")
    print(df["status"].value_counts(dropna=False))

    # Summarize lung-error cases
    lung_errors = df[df["status"].str.startswith("error_no_lungs", na=False)]
    if len(lung_errors) > 0:
        print(f"\n[WARNING] {len(lung_errors)} cases skipped (no lung labels detected):")
        for _, row in lung_errors.iterrows():
            print(f"  - {row['case_id']}")

if __name__ == "__main__":
    main()
