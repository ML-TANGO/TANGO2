"""
optimizer.py
============
PyTorch로 저장된 모델(HF 디렉토리)을 AWQ / GPTQ / RTN(일반 weight 양자화)
방식으로 양자화. deploy.yaml의 optimization.quant_info 항목과 1:1 대응.

  quant_method : awq | gptq | rtn
  bits         : 4 | 8
  group_size   : -1(채널 단위) | 64 | 128
  zero_point   : true(asymmetric) | false(symmetric)
  gptq_param   : damping_factor, act_order(desc_act)
  calibration  : dataset_path, sample_sentence_number, max_len_tokens_per_sentence

v2 변경점:
  - optimize_model(): pipeline.py 가 호출하는 공개 API. model_converter.convert_model 과
    동일한 (code, message) 계약을 따른다.
  - torch/transformers 를 함수 안에서 지연 임포트 → 설정 검증만 할 때 의존성 불필요
  - max_len(max_len_tokens_per_sentence)을 실제로 적용 (기존에는 GPTQ 경로에서 무시됨)
  - 양자화 대상 Linear 가 하나도 없을 때 max() 크래시 방지
  - group_size 폴백 시 침묵하지 않고 경고 출력

사용 예:
  # RTN (캘리브레이션 불필요, CPU 가능)
  python optimizer.py /path/model_dir -o out_dir --method rtn --bits 8 --group-size 128 --zero-point

  # GPTQ (캘리브레이션 필요, GPU 권장) — gptqmodel 사용
  python optimizer.py model_dir -o out_dir --method gptq --bits 4 --group-size 128 \
      --dataset calib.txt --num-samples 512 --max-len 2048 --damping 0.01 --act-order

  # AWQ (캘리브레이션 필요, GPU 필수) — llm-compressor 사용
  python optimizer.py model_dir -o out_dir --method awq --bits 4 --group-size 128 \
      --dataset calib.txt --num-samples 512 --max-len 2048

방식별 비고:
  - RTN(round-to-nearest): 가중치만 보고 그룹 단위로 반올림 양자화.
    캘리브레이션이 없어 빠르지만 4bit에서는 AWQ/GPTQ보다 정확도 손실이 큼.
    주의: 저장본은 fake-quant(원래 dtype)이라 파일 크기가 줄지 않는다.
          --pack 은 int8 코드북을 별도 저장할 뿐 런타임이 바로 읽지는 못한다.
  - GPTQ: 2차 근사 기반. AutoGPTQ는 아카이브되어 후속인 gptqmodel 사용.
    pip install gptqmodel
  - AWQ: activation-aware. AutoAWQ는 deprecated되어 llm-compressor 사용.
    pip install llmcompressor   (vLLM에서 바로 로드 가능한 형식으로 저장됨)

공통 필요 패키지: pip install torch transformers safetensors
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VALID_METHODS = ("awq", "gptq", "rtn", "fp8", "nvfp4")
CALIB_REQUIRED = ("awq", "gptq", "fp8", "nvfp4")
# bits/group_size/zero_point 를 방식이 고정하는 것들 (NVIDIA ModelOpt 경유)
MODELOPT_METHODS = ("fp8", "nvfp4")


# ---------------------------------------------------------------------------
# 캘리브레이션 데이터 로드 (txt: 줄 단위 / jsonl: {"text": ...})
# ---------------------------------------------------------------------------
def load_calibration_texts(dataset_path: str, num_samples: int,
                           max_len: int | None = None,
                           tokenizer_path: str | None = None) -> list[str]:
    """캘리브레이션 문장을 읽는다.

    max_len 이 주어지면 문장당 토큰 수를 그 값으로 자른다.
    tokenizer_path 가 있으면 실제 토크나이저로, 없으면 대략 4 char/token 근사로
    자른다(설정이 조용히 무시되던 기존 동작을 고침)."""
    p = Path(dataset_path)
    if not p.exists():
        raise FileNotFoundError(f"캘리브레이션 데이터셋이 없습니다: {p}")

    texts: list[str] = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if p.suffix == ".jsonl":
                obj = json.loads(line)
                line = obj.get("text") or obj.get("content") or ""
            if line:
                texts.append(line)
            if len(texts) >= num_samples:
                break
    if not texts:
        raise ValueError("캘리브레이션 텍스트를 읽지 못했습니다.")

    if max_len:
        texts = _truncate_texts(texts, max_len, tokenizer_path)

    print(f"[info] 캘리브레이션 샘플 {len(texts)}개 로드"
          + (f" (문장당 최대 {max_len} 토큰)" if max_len else ""))
    return texts


def _truncate_texts(texts: list[str], max_len: int,
                    tokenizer_path: str | None) -> list[str]:
    if tokenizer_path:
        try:
            from transformers import AutoTokenizer
            tok = AutoTokenizer.from_pretrained(tokenizer_path)
            out = []
            for t in texts:
                ids = tok(t, add_special_tokens=False)["input_ids"][:max_len]
                out.append(tok.decode(ids))
            return out
        except Exception as e:
            print(f"[warn] 토크나이저 기반 자르기 실패({e}) → 문자 수 근사로 대체",
                  file=sys.stderr)
    # 근사: 영어/코드 기준 대략 4 char ≈ 1 token
    limit = max_len * 4
    return [t[:limit] for t in texts]


# ---------------------------------------------------------------------------
# RTN: 그룹 단위 round-to-nearest weight 양자화 (직접 구현)
# ---------------------------------------------------------------------------
def rtn_quantize_tensor(w, bits: int, group_size: int, zero_point: bool):
    """
    [out_features, in_features] 2D 가중치를 그룹 단위로 양자화 후
    역양자화(fake-quant)한 텐서와, packed 저장용 (q, scale, zeros)를 반환.
    group_size=-1 이면 행(채널) 전체가 한 그룹.
    """
    import torch

    assert w.dim() == 2, "RTN은 2D weight(Linear)에만 적용"
    out_f, in_f = w.shape
    gs = in_f if group_size == -1 else group_size
    if in_f % gs != 0:
        # 그룹으로 나누어떨어지지 않으면 채널 단위로 폴백 (조용히 넘어가지 않는다)
        print(f"[warn] in_features={in_f} 가 group_size={gs} 로 나누어떨어지지 않아 "
              f"채널 단위(group_size={in_f})로 폴백합니다.", file=sys.stderr)
        gs = in_f

    wf = w.float().reshape(out_f, in_f // gs, gs)  # [out, n_groups, gs]
    qmax = 2 ** bits - 1

    if zero_point:  # asymmetric: [min, max] → [0, qmax]
        w_min = wf.amin(dim=-1, keepdim=True)
        w_max = wf.amax(dim=-1, keepdim=True)
        scale = (w_max - w_min).clamp(min=1e-8) / qmax
        zeros = torch.round(-w_min / scale)
        q = torch.clamp(torch.round(wf / scale) + zeros, 0, qmax)
        deq = (q - zeros) * scale
    else:  # symmetric: [-absmax, absmax]
        half = 2 ** (bits - 1) - 1
        absmax = wf.abs().amax(dim=-1, keepdim=True).clamp(min=1e-8)
        scale = absmax / half
        zeros = torch.zeros_like(scale)
        q = torch.clamp(torch.round(wf / scale), -half - 1, half)
        deq = q * scale

    packed = {
        # asymmetric은 [0, 2^b-1] 범위이므로 uint8, symmetric은 음수 포함이므로 int8
        "q": q.to(torch.uint8 if zero_point else torch.int8).reshape(out_f, in_f),
        "scale": scale.squeeze(-1).to(torch.float16),     # [out, n_groups]
        "zeros": zeros.squeeze(-1).to(torch.float16),
        "group_size": gs,
    }
    return deq.reshape(out_f, in_f).to(w.dtype), packed


def quantize_rtn(model_dir: Path, out_dir: Path, bits: int, group_size: int,
                 zero_point: bool, pack: bool, skip_lm_head: bool) -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from safetensors.torch import save_file

    print(f"[info] RTN 양자화: {bits}bit, group_size={group_size}, "
          f"{'asymmetric' if zero_point else 'symmetric'}")
    model = AutoModelForCausalLM.from_pretrained(str(model_dir), torch_dtype="auto")

    n_quant, errs = 0, []
    packed_store: dict = {}
    for name, module in model.named_modules():
        if not isinstance(module, torch.nn.Linear):
            continue
        if skip_lm_head and "lm_head" in name:
            print(f"[skip] {name} (lm_head 제외)")
            continue
        w = module.weight.data
        deq, packed = rtn_quantize_tensor(w, bits, group_size, zero_point)
        errs.append((w.float() - deq.float()).abs().max().item())
        module.weight.data = deq  # fake-quant 반영
        if pack:
            packed_store[f"{name}.qweight"] = packed["q"]
            packed_store[f"{name}.scales"] = packed["scale"]
            packed_store[f"{name}.zeros"] = packed["zeros"]
        n_quant += 1

    if n_quant == 0:
        raise RuntimeError(
            "양자화할 Linear 레이어를 하나도 찾지 못했습니다. "
            "모델 구조를 확인하거나 --quant-lm-head 옵션을 검토하세요.")
    print(f"[info] Linear {n_quant}개 양자화, 최대 복원 오차: {max(errs):.4f}")

    out_dir.mkdir(parents=True, exist_ok=True)
    # fake-quant 모델 저장 (어느 런타임에서나 일반 모델처럼 로드 가능)
    model.save_pretrained(str(out_dir))
    try:
        AutoTokenizer.from_pretrained(str(model_dir)).save_pretrained(str(out_dir))
    except Exception:
        print("[warn] 토크나이저 저장 생략")
    # 실제 압축 저장본 (int8 코드 + fp16 scale/zeros)
    if pack:
        save_file(packed_store, str(out_dir / "rtn_packed.safetensors"),
                  metadata={"bits": str(bits), "group_size": str(group_size),
                            "zero_point": str(zero_point)})
        print(f"[done] 압축 가중치: {out_dir / 'rtn_packed.safetensors'}")
    with open(out_dir / "quantize_config.json", "w") as f:
        json.dump({"quant_method": "rtn", "bits": bits, "group_size": group_size,
                   "zero_point": zero_point}, f, indent=2)
    print(f"[done] {out_dir}")


# ---------------------------------------------------------------------------
# GPTQ: gptqmodel (AutoGPTQ 후속)
# ---------------------------------------------------------------------------
def quantize_gptq(model_dir: Path, out_dir: Path, bits: int, group_size: int,
                  zero_point: bool, dataset: str, num_samples: int, max_len: int,
                  damping: float, act_order: bool,
                  tokenizer_path: str | None = None) -> None:
    try:
        from gptqmodel import GPTQModel, QuantizeConfig
    except ImportError:
        raise RuntimeError(
            "gptqmodel이 필요합니다: pip install gptqmodel\n"
            "  (AutoGPTQ는 아카이브되어 더 이상 사용을 권장하지 않습니다)")

    texts = load_calibration_texts(dataset, num_samples, max_len,
                                   tokenizer_path or str(model_dir))

    cfg = QuantizeConfig(
        bits=bits,
        group_size=group_size,
        sym=not zero_point,          # zero_point=true → asymmetric
        desc_act=act_order,          # activation 크기순 양자화 (정확도↑, 속도↓)
        damp_percent=damping,        # 헤시안 안정화 계수
    )
    print(f"[info] GPTQ 양자화 시작 (GPU 권장): {cfg}")
    model = GPTQModel.load(str(model_dir), cfg)
    model.quantize(texts, batch_size=1)   # 캘리브레이션 + 양자화
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save(str(out_dir))
    print(f"[done] {out_dir} — transformers/vLLM에서 바로 로드 가능")


# ---------------------------------------------------------------------------
# AWQ: llm-compressor (AutoAWQ 후속)
# ---------------------------------------------------------------------------
def quantize_awq(model_dir: Path, out_dir: Path, bits: int, group_size: int,
                 zero_point: bool, dataset: str, num_samples: int, max_len: int,
                 tokenizer_path: str | None = None) -> None:
    try:
        from llmcompressor import oneshot
        from llmcompressor.modifiers.awq import AWQModifier
    except ImportError:
        raise RuntimeError(
            "llm-compressor가 필요합니다: pip install llmcompressor\n"
            "  (AutoAWQ는 deprecated되어 더 이상 유지보수되지 않습니다)")
    try:
        from datasets import Dataset
    except ImportError:
        raise RuntimeError("datasets 가 필요합니다: pip install datasets")

    texts = load_calibration_texts(dataset, num_samples, max_len,
                                   tokenizer_path or str(model_dir))
    ds = Dataset.from_dict({"text": texts})

    recipe = AWQModifier(
        targets="Linear",
        scheme=f"W{bits}A16",            # weight-only (activation fp16)
        ignore=["lm_head"],
        group_size=group_size,
        symmetric=not zero_point,
    )
    print(f"[info] AWQ 양자화 시작 (GPU 필수): W{bits}A16, group_size={group_size}")
    oneshot(
        model=str(model_dir),
        dataset=ds,
        recipe=recipe,
        output_dir=str(out_dir),
        max_seq_length=max_len,
        num_calibration_samples=len(texts),
    )
    print(f"[done] {out_dir} — vLLM에서 바로 로드 가능")


# ---------------------------------------------------------------------------
# ModelOpt: FP8 / NVFP4 (TensorRT-LLM 경로)
# ---------------------------------------------------------------------------
def quantize_modelopt(model_dir: Path, out_dir: Path, method: str, dataset: str,
                      num_samples: int, max_len: int,
                      tokenizer_path: str | None = None) -> None:
    """NVIDIA ModelOpt 로 FP8 / NVFP4 양자화 후 HF 체크포인트로 내보낸다.

    bits / group_size / zero_point 는 방식이 결정하므로 인자로 받지 않는다.
      FP8   : per-tensor scaling, Hopper(sm89) 이상에서 가속
      NVFP4 : 블록 크기 16 고정, Blackwell(sm100) 이상에서 가속

    산출물은 safetensors 기반 HF 체크포인트다. 구형 export_tensorrt_llm_checkpoint
    는 deprecated 되어 쓰지 않는다.
    """
    import torch

    try:
        import modelopt.torch.quantization as mtq
        from modelopt.torch.export import export_hf_checkpoint
    except ImportError:
        raise RuntimeError(
            "nvidia-modelopt 가 필요합니다: pip install nvidia-modelopt[torch]\n"
            "  (TensorRT-LLM 1.2.0 이상과 함께 사용하세요)")

    from transformers import AutoModelForCausalLM, AutoTokenizer

    cfg_map = {"fp8": "FP8_DEFAULT_CFG", "nvfp4": "NVFP4_DEFAULT_CFG"}
    cfg_name = cfg_map[method]
    if not hasattr(mtq, cfg_name):
        raise RuntimeError(
            f"설치된 ModelOpt 에 {cfg_name} 가 없습니다. "
            f"버전을 확인하세요 (사용 가능: "
            f"{[a for a in dir(mtq) if a.endswith('_CFG')][:8]})")
    quant_cfg = getattr(mtq, cfg_name)

    if not torch.cuda.is_available():
        raise RuntimeError(
            f"{method} 양자화에는 GPU 가 필요합니다 (CUDA 를 찾지 못했습니다).")

    # 가속 가능 여부를 미리 알려 준다 — 양자화 자체는 되지만 속도 이득이 없을 수 있다
    cap = torch.cuda.get_device_capability()
    sm = cap[0] * 10 + cap[1]
    need = 89 if method == "fp8" else 100
    if sm < need:
        print(f"[warn] 현재 GPU 는 sm_{sm} 입니다. {method} 는 sm_{need} 이상에서 "
              f"가속됩니다. 양자화는 진행하지만 추론 속도 이득은 없을 수 있습니다.",
              file=sys.stderr)

    print(f"[info] ModelOpt {method.upper()} 양자화 시작 ({cfg_name})")
    tok = AutoTokenizer.from_pretrained(tokenizer_path or str(model_dir))
    model = AutoModelForCausalLM.from_pretrained(
        str(model_dir), torch_dtype="auto", device_map="cuda")

    texts = load_calibration_texts(dataset, num_samples, max_len,
                                   tokenizer_path or str(model_dir))

    def forward_loop(m):
        """amax 수집용 캘리브레이션 패스."""
        with torch.no_grad():
            for i, text in enumerate(texts):
                enc = tok(text, return_tensors="pt", truncation=True,
                          max_length=max_len).to(m.device)
                m(**enc)
                if (i + 1) % 32 == 0:
                    print(f"[modelopt]   캘리브레이션 {i + 1}/{len(texts)}")

    model = mtq.quantize(model, quant_cfg, forward_loop)

    out_dir.mkdir(parents=True, exist_ok=True)
    export_hf_checkpoint(model, export_dir=str(out_dir))
    try:
        tok.save_pretrained(str(out_dir))
    except Exception:
        print("[warn] 토크나이저 저장 생략")
    print(f"[done] {out_dir} — TensorRT-LLM 에서 바로 로드 가능")


# ---------------------------------------------------------------------------
# 공개 API — pipeline.py 등 다른 프로그램에서 import 해서 호출
# ---------------------------------------------------------------------------
def optimize_model(model_dir, output_dir, method, bits=4, group_size=128,
                   zero_point=False, dataset=None, num_samples=512, max_len=2048,
                   damping=0.01, act_order=False, pack=False, quant_lm_head=False,
                   tokenizer_path=None):
    """모델을 양자화하는 공개 함수.

    필수 인자:
        model_dir  : HF 형식 모델 폴더
        output_dir : 출력 폴더
        method     : "awq" | "gptq" | "rtn"

    반환값:
        (a, b) 튜플. model_converter.convert_model 과 동일한 계약.
          a = 0  / b = "success"      성공
          a = -1 / b = "<오류 메시지>"  실패
    """
    try:
        method = (method or "").lower()
        if method not in VALID_METHODS:
            return (-1, f"알 수 없는 양자화 방식입니다: {method} "
                        f"(가능: {', '.join(VALID_METHODS)})")
        if method not in MODELOPT_METHODS and bits not in (4, 8):
            return (-1, f"bits 는 4 또는 8 이어야 합니다 (받은 값: {bits})")

        src = Path(model_dir)
        dst = Path(output_dir)
        if not (src / "config.json").exists():
            return (-1, f"{src} 는 HF 형식 디렉토리가 아닙니다 (config.json 없음)")
        if method in CALIB_REQUIRED and not dataset:
            return (-1, f"{method} 는 캘리브레이션 데이터가 필수입니다 "
                        f"(optimization.calibration_info.dataset_path)")

        dst.mkdir(parents=True, exist_ok=True)

        if method in MODELOPT_METHODS:
            # bits/group_size/zero_point 는 방식이 결정하므로 넘기지 않는다
            quantize_modelopt(src, dst, method, dataset, num_samples, max_len,
                              tokenizer_path)
        elif method == "rtn":
            quantize_rtn(src, dst, bits, group_size, zero_point, pack,
                         skip_lm_head=not quant_lm_head)
        elif method == "gptq":
            quantize_gptq(src, dst, bits, group_size, zero_point, dataset,
                          num_samples, max_len, damping, act_order, tokenizer_path)
        else:  # awq
            quantize_awq(src, dst, bits, group_size, zero_point, dataset,
                         num_samples, max_len, tokenizer_path)
        return (0, "success")

    except Exception as e:
        return (-1, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def model_optimizer() -> int:
    ap = argparse.ArgumentParser(description="LLM weight 양자화 (awq/gptq/rtn/fp8/nvfp4)")
    ap.add_argument("model_dir", help="HF 형식 모델 디렉토리 (.bin/.safetensors)")
    ap.add_argument("-o", "--output", required=True, help="출력 디렉토리")
    ap.add_argument("--method", required=True, choices=list(VALID_METHODS),
                    help="fp8/nvfp4 는 ModelOpt 경유(GPU 필수), bits/group-size 무시")
    ap.add_argument("--bits", type=int, default=4, choices=[4, 8])
    ap.add_argument("--group-size", type=int, default=128, help="-1 = 채널 단위")
    ap.add_argument("--zero-point", action="store_true",
                    help="asymmetric 양자화 (미지정 시 symmetric)")
    # 캘리브레이션 (awq/gptq)
    ap.add_argument("--dataset", default=None, help="캘리브레이션 txt/jsonl 경로")
    ap.add_argument("--num-samples", type=int, default=512)
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--tokenizer", default=None,
                    help="캘리브레이션 자르기에 쓸 토크나이저 경로 (기본: model_dir)")
    # gptq 전용
    ap.add_argument("--damping", type=float, default=0.01, help="GPTQ damping factor")
    ap.add_argument("--act-order", action="store_true", help="GPTQ desc_act")
    # rtn 전용
    ap.add_argument("--pack", action="store_true", help="RTN: int8 압축 저장본 추가 생성")
    ap.add_argument("--quant-lm-head", action="store_true", help="RTN: lm_head도 양자화")
    args = ap.parse_args()

    code, message = optimize_model(
        model_dir=args.model_dir,
        output_dir=args.output,
        method=args.method,
        bits=args.bits,
        group_size=args.group_size,
        zero_point=args.zero_point,
        dataset=args.dataset,
        num_samples=args.num_samples,
        max_len=args.max_len,
        damping=args.damping,
        act_order=args.act_order,
        pack=args.pack,
        quant_lm_head=args.quant_lm_head,
        tokenizer_path=args.tokenizer,
    )
    if code == 0:
        print(message)
        return 0
    print(f"오류: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(model_optimizer())
