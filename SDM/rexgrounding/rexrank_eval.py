import argparse
import json
import os
import numpy as np
import nibabel as nib
from scipy.ndimage import label, generate_binary_structure
from multiprocessing import Pool
from tqdm import tqdm

# Constants used across evaluation
GLOBAL_HIT_THR = 0.1          # threshold on global (union) dice to call a finding a hit
MATCH_DICE_THR = 0.2          # minimum dice to accept a GT<->prediction component match
CC_CONNECTIVITY_DEFAULT = 2   # 3D: 1=6-neigh, 2=18-neigh, 3=26-neigh
MIN_SIZE_DEFAULT = 50         # minimum voxel size for a prediction component to be kept
DATA_DTYPE = np.uint8         # dtype to load volumes (saves memory & speeds ops)
MAX_COMPONENTS_PER_FINDING = 50  # cap predicted components per finding (None to disable)


def prf(tp, fp, fn):
	"""Compute precision, recall, F1 with safe handling of zero denominators."""
	precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if tp == 0 and fp == 0 else 0.0)
	recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if tp == 0 and fn == 0 else 0.0)
	f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
	return precision, recall, f1

def dice(mask1, mask2, eps=1e-6):
    m1 = mask1 > 0
    m2 = mask2 > 0
    inter = (m1 & m2).sum()
    sum_ = m1.sum() + m2.sum()
    if sum_ == 0:
        return 1.0
    return (2 * inter + eps) / (sum_ + eps)

def load_4d(path):
	"""Load 4D NIfTI as uint8."""
	img = nib.load(path)
	data = np.asanyarray(img.dataobj)
	return data.astype(DATA_DTYPE, copy=False) if data.dtype != DATA_DTYPE else data

def load_existing_cases(path):
	"""Load existing cases and summary if output file exists."""
	if not os.path.isfile(path):
		return [], None
	with open(path, 'r') as f:
		data = json.load(f)
	cases = data.get("cases", []) if isinstance(data, dict) else []
	summary = data.get("summary") if isinstance(data, dict) else None
	return cases if isinstance(cases, list) else [], summary

def atomic_write_json(path, data):
	"""Atomically write JSON to path (write to tmp then replace)."""
	tmp_path = path + ".tmp"
	with open(tmp_path, 'w') as f:
		json.dump(data, f, indent=2)
		f.flush()
		os.fsync(f.fileno())
	os.replace(tmp_path, path)


def compute_summary_overall(cases, global_only, min_size, cc_connectivity):
    """Recompute overall summary from accumulated 'cases' entries."""
    valid_cases = [c for c in cases if isinstance(c, dict) and "findings" in c]
    total_cases = len(valid_cases)
    total_findings = 0
    total_hits = 0
    global_dice_values = []
    per_case_global_dice_means = []

    total_tp = total_fp = total_fn = 0
    total_gt_instances = total_pred_instances = 0
    matched_dice_values = []

    for c in valid_cases:
        findings = c.get("findings", {}) or {}
        f_vals = list(findings.values())
        total_findings += len(f_vals)
        if f_vals:
            gd_list = [fd.get("global_dice", 0.0) for fd in f_vals]
            global_dice_values.extend(gd_list)
            per_case_global_dice_means.append(float(np.mean(gd_list)))
        total_hits += sum(1 for fd in f_vals if fd.get("global_hit"))

        if not global_only:
            total_tp += sum(fd.get("tp", 0) for fd in f_vals)
            total_fp += sum(fd.get("fp", 0) for fd in f_vals)
            total_fn += sum(fd.get("fn", 0) for fd in f_vals)
            total_gt_instances += sum(fd.get("num_gt_instances", 0) for fd in f_vals)
            total_pred_instances += sum(fd.get("num_pred_instances", 0) for fd in f_vals)
            for fd in f_vals:
                for m in fd.get("matched_instances", []) or []:
                    if isinstance(m, dict) and "dice" in m:
                        matched_dice_values.append(float(m["dice"]))

    hit_rate = float(total_hits / total_findings) if total_findings else 0.0
    mean_global_dice_per_finding = float(np.mean(global_dice_values)) if global_dice_values else 0.0
    mean_global_dice_per_case = float(np.mean(per_case_global_dice_means)) if per_case_global_dice_means else 0.0
    mean_findings_per_case = float(total_findings / total_cases) if total_cases else 0.0

    if global_only:
        return {
            "params": {"global_only": True, "global_hit_thr": GLOBAL_HIT_THR},
            "total_cases": total_cases,
            "total_findings": total_findings,
            "total_hits": total_hits,
            "total_misses": total_findings - total_hits,
            "hit_rate": hit_rate,
            "mean_global_dice_per_finding": mean_global_dice_per_finding,
            "mean_global_dice_per_case": mean_global_dice_per_case,
            "mean_findings_per_case": mean_findings_per_case,
        }

    overall_prec, overall_rec, overall_f1 = prf(total_tp, total_fp, total_fn)
    return {
        "params": {
            "global_only": False,
            "global_hit_thr": GLOBAL_HIT_THR,
            "match_dice_thr": MATCH_DICE_THR,
            "min_size": min_size,
            "cc_connectivity": cc_connectivity,
        },
        "total_cases": total_cases,
        "total_findings": total_findings,
        "total_hits": total_hits,
        "total_misses": total_findings - total_hits,
        "hit_rate": hit_rate,
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "total_gt_instances": total_gt_instances,
        "total_pred_instances": total_pred_instances,
        "overall_instance_precision": float(overall_prec),
        "overall_instance_recall": float(overall_rec),
        "overall_instance_f1": float(overall_f1),
        "mean_global_dice_per_finding": mean_global_dice_per_finding,
        "mean_global_dice_per_case": mean_global_dice_per_case,
        "mean_matched_dice_per_finding": float(np.mean(matched_dice_values)) if matched_dice_values else 0.0,
        "mean_findings_per_case": mean_findings_per_case,
    }

def cc_filter(binary_mask, min_size, connectivity):
	"""Return relabeled connected components after removing components < min_size."""
	structure = generate_binary_structure(3, connectivity)
	lbl, n = label(binary_mask, structure=structure)
	if n == 0:
		return lbl
	
	sizes = np.bincount(lbl.ravel())
	remove = np.where(sizes < min_size)[0]
	if len(remove) > 0:
		lbl[np.isin(lbl, remove)] = 0
	
	relabeled, _ = label(lbl > 0, structure=structure)
	return relabeled

def match_instances(gt_cc, pred_cc):
	"""Greedy one-to-one matching of GT and predicted components based on Dice."""
	gt_ids = np.unique(gt_cc)[np.unique(gt_cc) > 0]
	pred_ids = np.unique(pred_cc)[np.unique(pred_cc) > 0]
	
	if gt_ids.size == 0 or pred_ids.size == 0:
		return [], set(gt_ids.tolist()), set(pred_ids.tolist())
	
	gt_masks = {int(i): (gt_cc == i) for i in gt_ids}
	pred_masks = {int(j): (pred_cc == j) for j in pred_ids}
	remaining_gt = set(gt_masks.keys())
	remaining_pred = set(pred_masks.keys())
	matches = []
	
	while remaining_gt and remaining_pred:
		best = (0.0, None, None)
		for gi in remaining_gt:
			gm = gt_masks[gi]
			for pj in remaining_pred:
				pm = pred_masks[pj]
				d = dice(gm, pm)
				if d > best[0]:
					best = (d, gi, pj)
		if best[1] is None or best[0] < MATCH_DICE_THR:
			break
		matches.append((best[1], best[2], best[0]))
		remaining_gt.remove(best[1])
		remaining_pred.remove(best[2])

	return matches, remaining_gt, remaining_pred


def evaluate_finding(gt_f, pred_f, global_only, min_size, connectivity):
	"""Evaluate a single finding channel."""
	gt_cc = gt_f.astype(DATA_DTYPE, copy=False)
	pred_bin = pred_f > 0
	
	if global_only:
		gd = dice(gt_cc > 0, pred_bin)
		return {"global_dice": float(gd), "global_hit": bool(gd >= GLOBAL_HIT_THR)}
	
	pred_cc = cc_filter(pred_bin, min_size, connectivity)

	# Keep only top-K largest components
	if MAX_COMPONENTS_PER_FINDING:
		comp_ids = np.unique(pred_cc)[np.unique(pred_cc) > 0]
		if comp_ids.size > MAX_COMPONENTS_PER_FINDING:
			sizes = np.bincount(pred_cc.ravel())
			id_sizes = [(int(cid), int(sizes[cid])) for cid in comp_ids]
			id_sizes.sort(key=lambda x: x[1], reverse=True)
			keep_ids = set(cid for cid, _ in id_sizes[:MAX_COMPONENTS_PER_FINDING])
			pred_cc[(pred_cc > 0) & (~np.isin(pred_cc, list(keep_ids)))] = 0

	global_d = dice(gt_cc > 0, pred_cc > 0)
	matches, unmatched_gt, unmatched_pred = match_instances(gt_cc, pred_cc)
	
	tp, fn, fp = len(matches), len(unmatched_gt), len(unmatched_pred)
	prec, rec, f1 = prf(tp, fp, fn)
	
	unique_gt = np.unique(gt_cc)[np.unique(gt_cc) > 0]
	unique_pred = np.unique(pred_cc)[np.unique(pred_cc) > 0]
	return {
		"global_dice": float(global_d),
		"global_hit": bool(global_d >= GLOBAL_HIT_THR),
		"tp": tp, "fp": fp, "fn": fn,
		"instance_precision": float(prec),
		"instance_recall": float(rec),
		"instance_f1": float(f1),
		"mean_matched_dice": float(np.mean([m[2] for m in matches])) if matches else 0.0,
		"matched_instances": [{"gt_id": int(g), "pred_id": int(p), "dice": float(d)} for g, p, d in matches],
		"unmatched_gt": sorted([int(x) for x in unmatched_gt]),
		"unmatched_pred": sorted([int(x) for x in unmatched_pred]),
		"num_gt_instances": len(unique_gt),
		"num_pred_instances": len(unique_pred),
	}


def evaluate_volume(gt_path, pred_path, global_only, min_size, connectivity):
	gt, pred = load_4d(gt_path), load_4d(pred_path)
	if gt.shape != pred.shape:
		raise ValueError(f"Shape mismatch: {gt.shape} vs {pred.shape}")
	return {f"finding_{i}": evaluate_finding(gt[i], pred[i], global_only, min_size, connectivity) 
			for i in range(gt.shape[0])}

def compute_case_stats(findings, global_only):
	"""Aggregate per-case stats from per-finding evaluation results."""
	f_vals = list(findings.values())
	finding_global_dice = [fd["global_dice"] for fd in f_vals]
	case_global_dice_mean = float(np.mean(finding_global_dice)) if finding_global_dice else 0.0
	hits = sum(1 for fd in f_vals if fd.get("global_hit"))
	hit_rate = hits / len(findings) if findings else 0.0
	
	if global_only:
		return {
			"mean_global_dice": case_global_dice_mean,
			"hits": hits,
			"misses": len(findings) - hits,
			"hit_rate": hit_rate,
			"finding_global_dice_list": finding_global_dice,
		}

	case_tp = sum(fd["tp"] for fd in f_vals)
	case_fp = sum(fd["fp"] for fd in f_vals)
	case_fn = sum(fd["fn"] for fd in f_vals)
	case_gt_instances = sum(fd["num_gt_instances"] for fd in f_vals)
	case_pred_instances = sum(fd["num_pred_instances"] for fd in f_vals)
	case_matched_dice_vals = [fd["mean_matched_dice"] for fd in f_vals if fd["matched_instances"]]
	case_mean_matched_dice = float(np.mean(case_matched_dice_vals)) if case_matched_dice_vals else 0.0
	case_precision, case_recall, case_f1 = prf(case_tp, case_fp, case_fn)
	
	return {
		"tp": case_tp,
		"fp": case_fp,
		"fn": case_fn,
		"gt_instances": case_gt_instances,
		"pred_instances": case_pred_instances,
		"mean_global_dice": case_global_dice_mean,
		"mean_matched_dice": case_mean_matched_dice,
		"instance_precision": case_precision,
		"instance_recall": case_recall,
		"instance_f1": case_f1,
		"hits": hits,
		"misses": len(findings) - hits,
		"hit_rate": hit_rate,
		"finding_global_dice_list": finding_global_dice,
		"matched_dice_list": case_matched_dice_vals,
	}

def process_case(args):
	"""Worker for parallel case evaluation."""
	fname, gt_dir, pred_dir, global_only, min_size, connectivity = args
	gt_path, pred_path = os.path.join(gt_dir, fname), os.path.join(pred_dir, fname)
	
	if not os.path.isfile(pred_path):
		return {"file": fname, "error": "missing_prediction"}
	
	findings = evaluate_volume(gt_path, pred_path, global_only, min_size, connectivity)
	return {"file": fname, "findings": findings, "stats": compute_case_stats(findings, global_only)}

def main():
	parser = argparse.ArgumentParser(description="Instance-level evaluation producing summary + per-case breakdown.")
	parser.add_argument("--gt_dir", required=True)
	parser.add_argument("--pred_dir", required=True)
	parser.add_argument("--output_json", required=True)
	parser.add_argument("--dataset_json", required=True)
	parser.add_argument("--num_workers", type=int, default=16, help="Number of parallel worker processes (default 1 = no multiprocessing).")
	parser.add_argument("--global_only", action="store_true", help="Only compute global Dice & hit metrics (skip instance-level).")
	parser.add_argument("--min_size", type=int, default=MIN_SIZE_DEFAULT, help=f"Minimum prediction component size (voxels). Default {MIN_SIZE_DEFAULT}.")
	parser.add_argument("--cc_connectivity", type=int, choices=[1,2,3], default=CC_CONNECTIVITY_DEFAULT, help="Connected-component neighborhood: 1=6, 2=18, 3=26 (default 3).")
	# Instances assumed pre-labeled; no flag needed.

	args = parser.parse_args()

	with open(args.dataset_json, 'r') as f:
		data = json.load(f)

	test_entries = data.get("test", []) if isinstance(data, dict) else []
	gt_files = sorted({os.path.basename(e.get("seg_path")) for e in test_entries if e.get("seg_path")})

	# Resume support: skip already-completed cases
	existing_cases, _ = load_existing_cases(args.output_json)
	processed_files = {c.get("file") for c in existing_cases if c.get("file") and "findings" in c}
	remaining_files = [f for f in gt_files if f not in processed_files]
	if not remaining_files:
		output = {"summary": compute_summary_overall(existing_cases, args.global_only, args.min_size, args.cc_connectivity), "cases": existing_cases}
		atomic_write_json(args.output_json, output)
		print(f"Saved evaluation JSON (summary + cases) to {args.output_json}")
		return

	tasks = [(f, args.gt_dir, args.pred_dir, args.global_only, args.min_size, args.cc_connectivity) 
			 for f in remaining_files]
	cases = list(existing_cases)

	iterator = (Pool(processes=args.num_workers).imap_unordered(process_case, tasks) 
				if args.num_workers > 1 else map(process_case, tasks))
	
	for res in tqdm(iterator, total=len(tasks), desc="Evaluating cases", unit="case"):
		if "error" not in res:
			res = {"file": res["file"], "findings": res["findings"], "case_stats": res["stats"]}
		cases.append(res)
		atomic_write_json(args.output_json, {"cases": cases})

	summary = compute_summary_overall(cases, args.global_only, args.min_size, args.cc_connectivity)
	output = {"summary": summary, "cases": cases}
	atomic_write_json(args.output_json, output)
	print(f"Saved evaluation JSON (summary + cases) to {args.output_json}")

if __name__ == "__main__":
	main()