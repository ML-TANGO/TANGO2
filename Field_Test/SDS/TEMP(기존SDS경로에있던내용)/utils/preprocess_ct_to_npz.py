# preprocess_ct_to_npz.py
import os, json, argparse, multiprocessing as mp, re, numpy as np
from pathlib import Path
from tqdm import tqdm
import pandas as pd
import monai
from monai.transforms import (
    Compose, LoadImaged, EnsureChannelFirstd, Orientationd, Spacingd,
    ScaleIntensityRanged, SpatialPadd, CenterSpatialCropd, CastToTyped
)
import nibabel as nib

# ---------------------------------------------------------------------------
# Ensure the ITK wheels are available so that LoadImaged's default
# ITKReader can read *.mha.  If they are missing, give a clear message
# instead of letting the transform fail later.
# ---------------------------------------------------------------------------
try:
    import itk  # noqa: F401
except ModuleNotFoundError:  # *** explanatory error, not a hard crash ***
    raise ModuleNotFoundError(
        "It looks like the 'itk' Python package is not installed.\n"
        "Please run  ➜  pip install --upgrade itk==5.*  (or monai[all])\n"
        "to enable reading *.mha / *.mhd files with MONAI.")

try:
    import SimpleITK as sitk   # tiny (2–3 MB) and often already present
    _HAS_SITK = True
except ImportError:
    _HAS_SITK = False

# ---------- constants -------------------------------------------------------
TARGET_SPACING   = (1.25, 1.25, 2.0)        # (x, y, z) mm – less information loss
TARGET_SHAPE     = (256, 256, 192)          # (H, W, D) after tight crop + pad
HU_WINDOW        = (-1000, 1500)            # clip & scale to [0,1]
NPZ_DTYPE        = np.float16               # storage only!
SUPPORTED_EXTS   = (".nii.gz", ".nii", ".mha")
N_PROC           = max(mp.cpu_count() // 2, 4)
# ---------------------------------------------------------------------------

offline_tx = Compose([
    LoadImaged(keys="image"),
    EnsureChannelFirstd(keys="image"),
    Orientationd(keys="image", axcodes="RAS"),
    Spacingd(keys="image", pixdim=TARGET_SPACING,
             mode="trilinear", align_corners=True),
    ScaleIntensityRanged(keys="image",
        a_min=HU_WINDOW[0], a_max=HU_WINDOW[1],
        b_min=0.0, b_max=1.0, clip=True),
    SpatialPadd(keys="image", spatial_size=(*TARGET_SHAPE,)),
    CenterSpatialCropd(keys="image", roi_size=(*TARGET_SHAPE,)),
    CastToTyped(keys="image", dtype=NPZ_DTYPE),
])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def strip_known_suffix(fname: str) -> str:
    """
    Remove .nii.gz / .nii / .mha (case‑insensitive) from a filename.
    """
    for ext in SUPPORTED_EXTS:
        if fname.lower().endswith(ext):
            return fname[:-len(ext)]
    return Path(fname).stem   # fallback

def get_original_shape(path: Path):
    """
    Return (H, W, D) tuple of the raw image *without* loading the full
    MONAI/ITK pipeline. Falls back to SimpleITK for MetaImage.
    """
    p = str(path)
    # --- NIfTI: nibabel is the lightest choice -----------------------------
    if p.lower().endswith((".nii", ".nii.gz")):
        img = nib.load(p)
        return img.shape
    # --- MetaImage (.mha / .mhd) -------------------------------------------
    if _HAS_SITK:
        img = sitk.ReadImage(p)
        # SimpleITK returns (x, y, z). Convert to (H, W, D) → (y, x, z)
        size_xyz = img.GetSize()
        return size_xyz[1], size_xyz[0], size_xyz[2]
    # If SimpleITK not available just skip original shape
    return None

# ---------------------------------------------------------------------------
def process_one(path_outdir_pair):
    path, out_dir = path_outdir_pair
    # ----------------------------------------------------------------------
    case_id = strip_known_suffix(Path(path).name)
    out_file = out_dir / f"{case_id}.npz"

    original_shape = get_original_shape(path)

    if out_file.exists():
        return {
            'img_path': str(path),
            'case_id': case_id,
            'original_shape': original_shape,
            'processed_file': str(out_file),
            'status': 'already_exists'
        }

    try:
        data_dict = offline_tx({"image": str(path)})
        vol = data_dict["image"]          # (1, Z, Y, X) float16
        np.savez_compressed(out_file, image=vol.astype(NPZ_DTYPE))
        return {
            'img_path': str(path),
            'case_id': case_id,
            'original_shape': original_shape,
            'processed_file': str(out_file),
            'status': 'processed'
        }
    except Exception as e:
        return {
            'img_path': str(path),
            'case_id': case_id,
            'original_shape': original_shape,
            'processed_file': None,
            'status': f'error: {str(e)}'
        }

# ---------------------------------------------------------------------------
def collect_paths(src_dir: Path):
    """
    Gather all supported image files in *src_dir* (recursive).
    Returns a list[Path] and a dict{ext: count} for pretty printing.
    """
    paths = []
    ext_counter = {ext: 0 for ext in SUPPORTED_EXTS}
    for ext in SUPPORTED_EXTS:
        found = list(src_dir.rglob(f"*{ext}"))
        paths.extend(found)
        ext_counter[ext] = len(found)
    return paths, ext_counter

def main(src_dir, dst_dir):
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    dst_dir.mkdir(exist_ok=True, parents=True)

    all_paths, counts = collect_paths(src_dir)
    if not all_paths:
        print("No supported image files found. Exiting.")
        return

    print("Found:")
    for k, v in counts.items():
        if v:
            print(f"  {v:5d}  {k}")
    print(f"Total: {len(all_paths)}\n")

    print(f"Starting preprocessing with {N_PROC} processes...")
    with mp.Pool(N_PROC) as pool:
        results = list(tqdm(
            pool.imap(process_one, [(p, dst_dir) for p in all_paths]),
            total=len(all_paths),
            desc="Processing CT scans",
            unit="files",
            dynamic_ncols=True,
            ncols=100
        ))

    # ----------------- collect / save metadata -----------------------------
    metadata_list = [r for r in results if r]  # drop None
    if not metadata_list:
        print("No metadata collected.")
        return

    df = pd.DataFrame(metadata_list)

    # original_shape may be None for some files → guard
    if df["original_shape"].notna().any():
        df['original_height'] = df['original_shape'].apply(lambda x: x[0] if x else None)
        df['original_width']  = df['original_shape'].apply(lambda x: x[1] if x else None)
        df['original_depth']  = df['original_shape'].apply(lambda x: x[2] if x else None)

    metadata_file = dst_dir / "preprocessing_metadata.csv"
    df.to_csv(metadata_file, index=False)
    print(f"Saved metadata for {len(df)} files to {metadata_file}")

    # ----------------- nice console summary --------------------------------
    print("\nProcessing Summary:")
    print(df['status'].value_counts())

    processed_df = df[df['status'] == 'processed']
    if not processed_df.empty and processed_df['original_shape'].notna().any():
        print("\nOriginal shape statistics (processed files):")
        for col, name in [('original_height', 'Height'),
                          ('original_width',  'Width'),
                          ('original_depth',  'Depth')]:
            vals = processed_df[col].dropna()
            if not vals.empty:
                print(f"{name:<6}: min={vals.min()}, max={vals.max()}, mean={vals.mean():.1f}")

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Pre‑process CT volumes (supports *.nii, *.nii.gz, *.mha) "
                    "into tightly‑cropped, intensity‑scaled float16 *.npz"
    )
    ap.add_argument("--src", default="/home/bilab7/data/train",
                    help="folder with original *.nii[.gz] / *.mha files")
    ap.add_argument("--dst", default="/home/bilab7/data/train_preprocessed3",
                    help="output folder for *.npz")
    args = ap.parse_args()
    main(args.src, args.dst)
