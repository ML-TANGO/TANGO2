#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pruner.py — LLM 가중치 프루닝 (structural / unstructural / wanda)

deploy.yaml 의 optimization.pruning_info 항목과 1:1 대응한다.

  pruning_method : structural | unstructural | wanda
  sparsity_ratio : "50%" 또는 0.5
  target_layers  : all 또는 ["model.layers.10", ...] (접두사 매칭)
  nm_pattern     : "2:4" 등 (선택) — semi-structured 희소성
  scope          : layer | global (선택, unstructural 기본 layer)

방식별 설명:

  unstructural  가중치 절댓값이 작은 원소부터 0 으로 만든다. 정확도 손실이 가장
                적지만, 흩어진 0 은 일반 하드웨어에서 속도 이득이 없다(메모리도
                dense 로 그대로 쓴다). nm_pattern 을 주면 4개마다 2개를 남기는
                식의 semi-structured 로 바뀌어 Ampere 이상 sparse tensor core
                에서 실제 가속을 받을 수 있다.

  structural    출력 채널(Linear 의 행) 전체를 L2 노름 기준으로 통째로 0 으로
                만든다. MLP 중간 뉴런을 제거하는 것과 같은 효과다.
                주의: 이 구현은 '마스킹'이며 텐서 shape 자체는 바꾸지 않는다.
                실제로 차원을 줄이려면 attention head 수·MLP intermediate_size
                같은 config 값과 이어지는 레이어까지 함께 수술해야 하고, 그건
                모델 아키텍처마다 달라 안전하게 일반화되지 않는다.

  wanda         |W| 만 보지 않고 입력 활성값 크기까지 함께 본다.
                점수 S_ij = |W_ij| × ||X_j||_2 로 계산해 출력 행마다 낮은 것부터
                자른다. 캘리브레이션 데이터가 필요한 대신 같은 sparsity 에서
                magnitude 방식보다 정확도가 잘 버틴다.
                참고: 원 논문은 레이어를 순차적으로 처리하며 앞 레이어의 프루닝
                결과가 뒤 레이어 활성값에 반영되게 한다. 여기서는 원본 모델로
                한 번에 활성 통계를 모으는 단순화된 방식이라 고 sparsity 에서는
                논문 수치보다 손해를 볼 수 있다.

사용 예:
  python pruner.py ./model_dir -o ./out --method unstructural --sparsity 0.5
  python pruner.py ./model_dir -o ./out --method unstructural --nm-pattern 2:4
  python pruner.py ./model_dir -o ./out --method structural --sparsity 0.25
  python pruner.py ./model_dir -o ./out --method wanda --sparsity 0.5 \\
      --dataset calib.txt --num-samples 128 --max-len 2048

공통 필요 패키지: pip install torch transformers safetensors
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VALID_METHODS = ("structural", "unstructural", "wanda")
CALIB_REQUIRED = ("wanda",)

# 프루닝에서 기본적으로 제외할 레이어.
#   lm_head / 임베딩은 어휘 전체에 걸쳐 있어 자르면 손실이 크고,
#   실제 파라미터 절감 대비 정확도 하락이 심하다.
DEFAULT_SKIP = ("lm_head", "embed_tokens", "embed_out", "wte", "lm_head.weight")


# ---------------------------------------------------------------------------
# 대상 레이어 선택
# ---------------------------------------------------------------------------
def iter_target_linears(model, target_layers=None, skip=DEFAULT_SKIP):
    """프루닝 대상 nn.Linear 를 (이름, 모듈) 로 순회한다.

    target_layers 가 None 또는 "all" 이면 전부,
    리스트면 해당 접두사로 시작하는 것만 고른다."""
    import torch

    prefixes = None
    if target_layers not in (None, "all", "ALL"):
        prefixes = ([target_layers] if isinstance(target_layers, str)
                    else list(target_layers))

    for name, module in model.named_modules():
        if not isinstance(module, torch.nn.Linear):
            continue
        if any(s in name for s in skip):
            continue
        if prefixes is not None and not any(name.startswith(p) for p in prefixes):
            continue
        yield name, module


def parse_nm(pattern: str) -> tuple[int, int]:
    """'2:4' → (2, 4). n 개를 남기고 m-n 개를 0 으로 만든다는 뜻."""
    try:
        n, m = (int(x) for x in str(pattern).split(":"))
    except Exception:
        raise ValueError(f"nm_pattern 형식이 잘못됐습니다: {pattern!r} (예: '2:4')")
    if not (0 < n < m):
        raise ValueError(f"nm_pattern 은 0 < n < m 이어야 합니다: {pattern!r}")
    return n, m


# ---------------------------------------------------------------------------
# 마스크 계산
# ---------------------------------------------------------------------------
def mask_unstructured(w, sparsity: float):
    """가중치 절댓값 기준, 레이어 안에서 작은 것부터 0. True=유지."""
    import torch

    k = int(w.numel() * sparsity)
    if k <= 0:
        return torch.ones_like(w, dtype=torch.bool)
    flat = w.abs().flatten().float()
    # kthvalue 는 k번째로 '작은' 값을 준다 → 그 이하를 자른다
    thresh = torch.kthvalue(flat, k).values
    return w.abs().float() > thresh


def mask_nm(w, n: int, m: int):
    """n:m semi-structured — 입력 차원을 m 개씩 묶어 n 개만 남긴다."""
    import torch

    out_f, in_f = w.shape
    if in_f % m != 0:
        raise ValueError(
            f"in_features={in_f} 가 nm_pattern 의 m={m} 으로 나누어떨어지지 않습니다.")
    groups = w.abs().float().reshape(out_f, in_f // m, m)
    # 그룹마다 상위 n 개 인덱스만 살린다
    keep_idx = groups.topk(n, dim=-1).indices
    mask = torch.zeros_like(groups, dtype=torch.bool)
    mask.scatter_(-1, keep_idx, True)
    return mask.reshape(out_f, in_f)


def mask_structural(w, sparsity: float):
    """출력 채널(행) 단위 — L2 노름이 작은 행을 통째로 0."""
    import torch

    out_f = w.shape[0]
    n_prune = int(out_f * sparsity)
    mask = torch.ones_like(w, dtype=torch.bool)
    if n_prune <= 0:
        return mask
    if n_prune >= out_f:
        raise ValueError(
            f"sparsity={sparsity:.0%} 로는 출력 채널 {out_f}개를 전부 자르게 됩니다.")
    row_norm = w.float().norm(dim=1)
    drop = row_norm.topk(n_prune, largest=False).indices
    mask[drop, :] = False
    return mask


def mask_wanda(w, act_norm, sparsity: float):
    """Wanda — S_ij = |W_ij| * ||X_j||_2, 출력 행마다 낮은 것부터 자른다."""
    import torch

    score = w.abs().float() * act_norm.reshape(1, -1)
    in_f = w.shape[1]
    n_prune = int(in_f * sparsity)
    mask = torch.ones_like(w, dtype=torch.bool)
    if n_prune <= 0:
        return mask
    drop = score.topk(n_prune, dim=1, largest=False).indices
    mask.scatter_(1, drop, False)
    return mask


# ---------------------------------------------------------------------------
# Wanda 활성 통계 수집
# ---------------------------------------------------------------------------
def collect_activation_norms(model, tokenizer, texts, max_len, targets):
    """각 대상 Linear 의 입력 특성별 ||X_j||_2 를 캘리브레이션 데이터로 누적한다."""
    import torch

    sums: dict = {}
    handles = []

    def make_hook(name):
        def hook(module, inputs, output):
            x = inputs[0].detach()
            x = x.reshape(-1, x.shape[-1]).float()
            s = (x * x).sum(dim=0)
            prev = sums.get(name)
            sums[name] = s if prev is None else prev + s
        return hook

    for name, module in targets:
        handles.append(module.register_forward_hook(make_hook(name)))

    print(f"[wanda] 활성 통계 수집: 샘플 {len(texts)}개 × 대상 {len(targets)}개 레이어")
    model.eval()
    try:
        with torch.no_grad():
            for i, text in enumerate(texts):
                enc = tokenizer(text, return_tensors="pt", truncation=True,
                                max_length=max_len)
                model(**enc)
                if (i + 1) % 32 == 0:
                    print(f"[wanda]   {i + 1}/{len(texts)}")
    finally:
        for h in handles:
            h.remove()

    missing = [n for n, _ in targets if n not in sums]
    if missing:
        print(f"[warn] 활성값을 못 받은 레이어 {len(missing)}개 — "
              f"magnitude 기준으로 대체합니다 (예: {missing[0]})", file=sys.stderr)

    return {k: v.sqrt() for k, v in sums.items()}


# ---------------------------------------------------------------------------
# 본체
# ---------------------------------------------------------------------------
def prune(model_dir: Path, out_dir: Path, method: str, sparsity: float,
          target_layers=None, nm_pattern=None, dataset=None,
          num_samples=128, max_len=2048, save_report=True) -> dict:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"[info] {method} 프루닝: sparsity={sparsity:.1%}"
          + (f", nm_pattern={nm_pattern}" if nm_pattern else ""))
    model = AutoModelForCausalLM.from_pretrained(str(model_dir), torch_dtype="auto")

    targets = list(iter_target_linears(model, target_layers))
    if not targets:
        raise RuntimeError(
            "프루닝 대상 Linear 를 찾지 못했습니다. "
            "target_layers 접두사가 실제 레이어 이름과 맞는지 확인하세요.")
    print(f"[info] 대상 Linear {len(targets)}개")

    act_norms = {}
    if method == "wanda":
        import optimizer as _opt
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        texts = _opt.load_calibration_texts(dataset, num_samples, max_len,
                                            str(model_dir))
        act_norms = collect_activation_norms(model, tokenizer, texts,
                                             max_len, targets)

    nm = parse_nm(nm_pattern) if nm_pattern else None

    per_layer = []
    total_params = total_zeros = 0

    for name, module in targets:
        w = module.weight.data
        if method == "structural":
            m = mask_structural(w, sparsity)
        elif method == "wanda":
            norm = act_norms.get(name)
            if norm is None:
                m = mask_unstructured(w, sparsity)
            else:
                m = mask_wanda(w, norm.to(w.device), sparsity)
        else:  # unstructural
            m = mask_nm(w, *nm) if nm else mask_unstructured(w, sparsity)

        module.weight.data = (w * m.to(w.dtype))
        zeros = int((~m).sum().item())
        per_layer.append({"layer": name, "params": w.numel(),
                          "zeros": zeros, "sparsity": zeros / w.numel()})
        total_params += w.numel()
        total_zeros += zeros

    achieved = total_zeros / total_params if total_params else 0.0
    print(f"[info] 대상 파라미터 {total_params:,}개 중 {total_zeros:,}개 0 "
          f"(실제 sparsity {achieved:.2%})")

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    try:
        AutoTokenizer.from_pretrained(str(model_dir)).save_pretrained(str(out_dir))
    except Exception:
        print("[warn] 토크나이저 저장 생략")

    report = {
        "pruning_method": method,
        "requested_sparsity": sparsity,
        "achieved_sparsity": achieved,
        "nm_pattern": nm_pattern,
        "target_layers": target_layers or "all",
        "pruned_layers": len(targets),
        "total_params": total_params,
        "total_zeros": total_zeros,
        "note": ("가중치를 0 으로 만드는 마스킹입니다. 텐서 shape 은 그대로이므로 "
                 "파일 크기와 메모리 사용량은 줄지 않습니다. 실제 이득을 보려면 "
                 "희소 연산을 지원하는 런타임이나 n:m 패턴이 필요합니다."),
    }
    with open(out_dir / "pruning_config.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    if save_report:
        with open(out_dir / "pruning_report.json", "w", encoding="utf-8") as f:
            json.dump({"summary": report, "layers": per_layer}, f,
                      ensure_ascii=False, indent=2)

    print(f"[done] {out_dir}")
    return report


# ---------------------------------------------------------------------------
# 공개 API — pipeline.py 가 호출
# ---------------------------------------------------------------------------
def prune_model(model_dir, output_dir, method, sparsity=0.5, target_layers=None,
                nm_pattern=None, dataset=None, num_samples=128, max_len=2048):
    """모델을 프루닝하는 공개 함수.

    반환값:
        (0, "success 메시지") 또는 (-1, "<오류 메시지>")
        다른 단계 모듈들과 같은 계약을 따른다.
    """
    try:
        method = (method or "").lower()
        if method not in VALID_METHODS:
            return (-1, f"알 수 없는 프루닝 방식입니다: {method} "
                        f"(가능: {', '.join(VALID_METHODS)})")

        src, dst = Path(model_dir), Path(output_dir)
        if not (src / "config.json").exists():
            return (-1, f"{src} 는 HF 형식 디렉토리가 아닙니다 (config.json 없음)")
        if method in CALIB_REQUIRED and not dataset:
            return (-1, f"{method} 는 캘리브레이션 데이터가 필수입니다 "
                        f"(optimization.calibration_info.dataset_path)")

        # nm_pattern 을 쓰면 sparsity 는 패턴이 결정하므로 값이 무시된다
        if nm_pattern and method != "unstructural":
            return (-1, f"nm_pattern 은 unstructural 에서만 쓸 수 있습니다 "
                        f"(현재 method={method})")
        if not nm_pattern and not (0.0 < float(sparsity) < 1.0):
            return (-1, f"sparsity 는 0 과 1 사이여야 합니다 (받은 값: {sparsity})")

        report = prune(src, dst, method, float(sparsity), target_layers,
                       nm_pattern, dataset, num_samples, max_len)
        msg = (f"{method} / 요청 {report['requested_sparsity']:.0%} → "
               f"실제 {report['achieved_sparsity']:.1%} "
               f"({report['pruned_layers']}개 레이어)")
        if nm_pattern:
            msg = f"{method} / {nm_pattern} → 실제 {report['achieved_sparsity']:.1%} " \
                  f"({report['pruned_layers']}개 레이어)"
        return (0, msg)

    except Exception as e:
        return (-1, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="LLM 가중치 프루닝 (structural/unstructural/wanda)")
    ap.add_argument("model_dir", help="HF 형식 모델 디렉토리")
    ap.add_argument("-o", "--output", required=True, help="출력 디렉토리")
    ap.add_argument("--method", required=True, choices=list(VALID_METHODS))
    ap.add_argument("--sparsity", type=float, default=0.5,
                    help="0~1 사이 비율 (nm-pattern 지정 시 무시)")
    ap.add_argument("--target-layers", default=None,
                    help="쉼표로 구분한 접두사. 미지정 시 전체")
    ap.add_argument("--nm-pattern", default=None,
                    help="'2:4' 형식 semi-structured (unstructural 전용)")
    # wanda 캘리브레이션
    ap.add_argument("--dataset", default=None, help="캘리브레이션 txt/jsonl 경로")
    ap.add_argument("--num-samples", type=int, default=128)
    ap.add_argument("--max-len", type=int, default=2048)
    args = ap.parse_args()

    targets = None
    if args.target_layers and args.target_layers.lower() != "all":
        targets = [t.strip() for t in args.target_layers.split(",") if t.strip()]

    code, msg = prune_model(
        model_dir=args.model_dir,
        output_dir=args.output,
        method=args.method,
        sparsity=args.sparsity,
        target_layers=targets,
        nm_pattern=args.nm_pattern,
        dataset=args.dataset,
        num_samples=args.num_samples,
        max_len=args.max_len,
    )
    if code == 0:
        print(msg)
        return 0
    print(f"오류: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
