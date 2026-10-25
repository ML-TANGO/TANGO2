"""
model_loader.py — HuggingFace repo id / 캐시 / 로컬 경로의 모델을 안전하게 로드한다.

모델은 다음 세 가지 형태로 지정할 수 있고 모두 동일하게 동작한다.
  - repo id            : ``Qwen/Qwen3-8B``, ``google/gemma-4-E4B-it``  (권장)
  - HF 캐시 디렉터리    : ``~/.cache/huggingface/hub/models--Qwen--Qwen3-8B``
  - 로컬 스냅샷 경로    : ``/path/to/snapshot`` (config.json 이 있는 디렉터리)

repo id 로 지정하면 캐시에 없을 때 자동으로 내려받는다(:func:`download_model`).
gated 모델(gemma 계열)은 ``export HF_TOKEN=...`` 이 필요하다.

gemma-4-E4B-it 처럼 멀티모달 래퍼(Gemma4ForConditionalGeneration)인 모델은
AutoModelForCausalLM 으로 바로 안 열릴 수 있으므로 여러 Auto 클래스를 순서대로
시도한다. 텍스트 전용 평가에서는 필요 시 language_model 서브모듈을 꺼내 쓴다.
"""

from __future__ import annotations

import glob
import os
import re
from typing import Any


def _hf_hub_cache() -> str:
    """HF 허브 캐시 경로. HF_HOME / HF_HUB_CACHE 환경변수를 존중한다."""
    env = os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    if env:
        return os.path.expanduser(env)
    home = os.environ.get("HF_HOME")
    if home:
        return os.path.join(os.path.expanduser(home), "hub")
    return os.path.expanduser("~/.cache/huggingface/hub")


HF_HUB = _hf_hub_cache()

# ---------------------------------------------------------------------------
# 선택 가능한 모델 카탈로그 (웹 UI 드롭다운)
#   repo_id 로 적어 두면 캐시에 없을 때 자동 다운로드된다.
# ---------------------------------------------------------------------------
MODEL_CATALOG: list[dict] = [
    dict(repo_id="Qwen/Qwen3-8B", label="Qwen3 8B", params="8.2B", gated=False,
         run_dir="runs/qwen3_8b_eval",
         note="Qwen3 dense · chat template 권장 (thinking 모드 기본)"),
    dict(repo_id="google/gemma-4-E4B-it", label="Gemma 4 E4B IT", params="E4B(유효 4B)",
         gated=True, run_dir="runs/gemma4_e4b_eval",
         note="멀티모달 래퍼 · chat template + BOS 권장 · HF_TOKEN 필요(gated)"),
]

DEFAULT_MODEL = MODEL_CATALOG[0]["repo_id"]

_REPO_ID_RE = re.compile(r"^[A-Za-z0-9][\w.\-]*/[\w.\-]+$")


def is_repo_id(name: str) -> bool:
    """``org/name`` 형태의 HuggingFace repo id 인가. (로컬 경로는 False)"""
    s = (name or "").strip().rstrip("/")
    if not s or s.count("/") != 1 or s.startswith((".", "~", "/")):
        return False
    if os.path.isdir(os.path.expanduser(s)):
        return False           # 같은 이름의 로컬 디렉터리가 우선
    return bool(_REPO_ID_RE.match(s))


def repo_id_of(path_or_repo: str) -> str | None:
    """입력(경로/캐시 디렉터리/repo id)에서 repo id 를 역산한다. 못 찾으면 None."""
    s = (path_or_repo or "").strip().rstrip("/")
    if is_repo_id(s):
        return s
    m = re.search(r"models--([A-Za-z0-9][\w.\-]*)--([\w.\-]+)", s)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def cache_dir_for(repo_id: str) -> str:
    """repo id 에 대응하는 HF 캐시 디렉터리(models--org--name) 경로."""
    return os.path.join(HF_HUB, "models--" + repo_id.replace("/", "--"))


def snapshot_dir(path_or_repo: str) -> str | None:
    """캐시/로컬에 실제로 내려받힌 스냅샷 디렉터리. 없으면 None."""
    p = os.path.expanduser((path_or_repo or "").strip().rstrip("/"))
    if os.path.isdir(p) and os.path.exists(os.path.join(p, "config.json")):
        return p

    cands = []
    if os.path.isdir(os.path.join(p, "snapshots")):
        cands.append(p)
    else:
        base = os.path.join(HF_HUB, os.path.basename(p))
        if os.path.isdir(os.path.join(base, "snapshots")):
            cands.append(base)
    rid = repo_id_of(path_or_repo)
    if rid:
        c = cache_dir_for(rid)
        if os.path.isdir(os.path.join(c, "snapshots")):
            cands.append(c)

    for cand in cands:
        ref = os.path.join(cand, "refs", "main")
        if os.path.exists(ref):
            with open(ref) as f:
                sha = f.read().strip()
            snap = os.path.join(cand, "snapshots", sha)
            if os.path.isdir(snap) and os.path.exists(os.path.join(snap, "config.json")):
                return snap
        snaps = sorted(glob.glob(os.path.join(cand, "snapshots", "*")),
                       key=os.path.getmtime, reverse=True)
        for snap in snaps:
            if os.path.exists(os.path.join(snap, "config.json")):
                return snap
    return None


def resolve_model_path(path_or_repo: str) -> str:
    """
    다음 형태를 모두 transformers 가 바로 먹을 수 있는 값으로 정규화한다.
      - org/name                                    → 그대로 (캐시에 없으면 자동 다운로드)
      - /abs/path/to/snapshot                       → 그대로
      - ~/.cache/huggingface/hub/models--org--name  → repo id 로 환원
      - models--org--name                           → repo id 로 환원

    캐시 디렉터리를 repo id 로 되돌리는 이유: 파일이 일부만 받아진 경우에도
    huggingface_hub 이 빠진 파일만 이어받게 하려는 것이다. 오프라인 모드
    (HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE)에서는 로컬 스냅샷 경로를 돌려준다.
    """
    raw = (path_or_repo or "").strip().rstrip("/")
    p = os.path.expanduser(raw)
    offline = (os.environ.get("HF_HUB_OFFLINE", "") not in ("", "0", "false")
               or os.environ.get("TRANSFORMERS_OFFLINE", "") not in ("", "0", "false"))

    # 1) 이미 스냅샷(=config.json 존재)인 로컬 경로는 그대로
    if os.path.isdir(p) and os.path.exists(os.path.join(p, "config.json")):
        return p

    # 2) repo id 를 알아낼 수 있으면 repo id 를 쓴다 (오프라인이면 스냅샷 경로)
    rid = repo_id_of(raw)
    if rid:
        if offline:
            return snapshot_dir(raw) or rid
        return rid

    # 3) 그 밖(캐시 디렉터리 형태이나 repo id 를 못 딴 경우)은 스냅샷으로
    return snapshot_dir(raw) or raw


def pretty_model_name(path: str) -> str:
    rid = repo_id_of(path)
    if rid:
        return rid
    m = re.search(r"models--([^/]+)", path or "")
    if m:
        return m.group(1).replace("--", "/")
    return os.path.basename((path or "").rstrip("/")) or path


# ---------------------------------------------------------------------------
# 캐시 상태 / 다운로드
# ---------------------------------------------------------------------------
def hf_token() -> str | None:
    """HF_TOKEN / HUGGING_FACE_HUB_TOKEN 환경변수 또는 huggingface-cli login 토큰."""
    for k in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACEHUB_API_TOKEN"):
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip()
    try:
        from huggingface_hub import HfFolder
        return HfFolder.get_token()
    except Exception:  # noqa: BLE001
        return None


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                total += os.stat(fp, follow_symlinks=True).st_size
            except OSError:
                pass
    return total


def model_status(path_or_repo: str) -> dict:
    """웹 UI 표시용 모델 상태(입력/repo id/캐시 여부/스냅샷 경로/용량)."""
    raw = (path_or_repo or "").strip()
    rid = repo_id_of(raw)
    snap = snapshot_dir(raw)
    local = os.path.isdir(os.path.expanduser(raw.rstrip("/")))
    cdir = cache_dir_for(rid) if rid else None
    return {
        "input": raw,
        "repo_id": rid,
        "resolved": resolve_model_path(raw),
        "kind": "repo_id" if (rid and not local) else "local_path",
        "cached": snap is not None,
        "snapshot": snap,
        "cache_dir": cdir,
        "size_bytes": _dir_size(cdir) if (cdir and os.path.isdir(cdir))
                      else (_dir_size(snap) if snap else 0),
        "downloadable": bool(rid),
        "hf_token": bool(hf_token()),
    }


def download_model(path_or_repo: str, log=print, max_workers: int = 8) -> str:
    """
    캐시에 없으면 내려받고 스냅샷 경로를 돌려준다. 이미 있으면 빠진 파일만 받는다.
    gated 모델(gemma 계열)은 HF_TOKEN 이 없으면 401/403 으로 실패한다.
    """
    rid = repo_id_of(path_or_repo)
    if not rid:
        snap = snapshot_dir(path_or_repo)
        if snap:
            return snap
        raise FileNotFoundError(
            f"모델을 찾을 수 없습니다: {path_or_repo} "
            f"(로컬 경로가 없고 'org/name' 형태의 repo id 도 아님)")

    from huggingface_hub import snapshot_download

    token = hf_token()
    snap = snapshot_dir(rid)
    if snap:
        log(f"[download] 캐시 확인: {rid} → {snap}")
    else:
        log(f"[download] 캐시에 없습니다. 내려받는 중: {rid} "
            f"(HF_TOKEN={'설정됨' if token else '없음'})")

    # *.pth / 원본 체크포인트 등 평가에 불필요한 대용량 파일은 제외한다.
    ignore = ["*.pth", "*.msgpack", "*.h5", "*.onnx", "*.tflite",
              "original/*", "*.gguf"]
    try:
        path = snapshot_download(repo_id=rid, token=token, ignore_patterns=ignore,
                                 max_workers=max_workers)
    except Exception as e:  # noqa: BLE001
        # 캐시본이 이미 있으면 무슨 오류든(네트워크 단절, gated 401 …) 캐시로 진행한다.
        if snap:
            log(f"[download] 허브 확인 실패({type(e).__name__}: {e}) — 캐시본으로 진행합니다.")
            return snap
        msg = str(e)
        if any(s in msg for s in ("401", "403", "404", "gated", "Unauthorized",
                                  "restricted", "RepositoryNotFound")):
            raise RuntimeError(
                f"'{rid}' 를 내려받지 못했습니다. 아래를 확인하세요.\n"
                f"  1) repo id 오타 (https://huggingface.co/{rid} 가 실제로 있는지)\n"
                f"  2) gated 모델이면 HF 사이트에서 라이선스에 동의한 뒤 토큰 설정:\n"
                f"     export HF_TOKEN=hf_xxx   (현재 토큰: {'있음' if token else '없음'})\n"
                f"원본 오류: {e}") from e
        raise
    log(f"[download] 준비 완료: {path}")
    return path


def load_tokenizer(model_path: str, trust_remote_code: bool = True):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(
        model_path, trust_remote_code=trust_remote_code)
    if tok.pad_token is None and tok.eos_token is not None:
        tok.pad_token = tok.eos_token
    return tok


def _dtype(name: str):
    import torch
    return {
        "bfloat16": torch.bfloat16, "bf16": torch.bfloat16,
        "float16": torch.float16, "fp16": torch.float16,
        "float32": torch.float32, "fp32": torch.float32,
        "auto": "auto",
    }.get(str(name).lower(), torch.bfloat16)


def load_model(
    model_path: str,
    dtype: str = "bfloat16",
    device_map: str | dict | None = "auto",
    trust_remote_code: bool = True,
    text_only: bool = True,
    log=print,
) -> Any:
    """
    모델을 로드해 반환. 여러 Auto 클래스를 순차 시도한다.
    text_only=True 이면 멀티모달 래퍼에서 텍스트 디코더를 꺼내 반환(가능한 경우).
    """
    import transformers
    from transformers import AutoConfig

    torch_dtype = _dtype(dtype)
    cfg = AutoConfig.from_pretrained(model_path, trust_remote_code=trust_remote_code)
    arch = (getattr(cfg, "architectures", None) or ["?"])[0]
    log(f"[loader] architecture={arch} model_type={getattr(cfg, 'model_type', '?')}")

    candidates = []
    for name in ("AutoModelForCausalLM", "AutoModelForImageTextToText",
                 "AutoModelForVision2Seq", "AutoModelForSeq2SeqLM", "AutoModel"):
        klass = getattr(transformers, name, None)
        if klass is not None:
            candidates.append((name, klass))

    kwargs = dict(dtype=torch_dtype, device_map=device_map,
                  trust_remote_code=trust_remote_code, low_cpu_mem_usage=True)

    last_err = None
    for name, klass in candidates:
        try:
            log(f"[loader] trying {name} ...")
            try:
                model = klass.from_pretrained(model_path, **kwargs)
            except TypeError:
                # 구버전 transformers 는 dtype= 대신 torch_dtype=
                kw2 = dict(kwargs)
                kw2["torch_dtype"] = kw2.pop("dtype")
                model = klass.from_pretrained(model_path, **kw2)
            log(f"[loader] loaded with {name}: {type(model).__name__}")
            if text_only:
                model = _unwrap_text_model(model, log)
            model.eval()
            return model
        except Exception as e:  # noqa: BLE001
            last_err = e
            log(f"[loader] {name} failed: {type(e).__name__}: {e}")

    raise RuntimeError(f"모델 로드 실패: {model_path} ({last_err})")


def _unwrap_text_model(model, log=print):
    """멀티모달 래퍼에서 언어 모델(causal LM)만 꺼낸다. 실패하면 원본 반환."""
    # 이미 lm_head 를 가진 causal LM 이면 그대로 사용
    if hasattr(model, "lm_head") and hasattr(model, "prepare_inputs_for_generation"):
        return model
    for attr in ("language_model", "text_model", "model"):
        sub = getattr(model, attr, None)
        if sub is not None and hasattr(sub, "lm_head"):
            log(f"[loader] using text decoder: model.{attr}")
            return sub
    log("[loader] 멀티모달 래퍼를 그대로 사용합니다(텍스트 입력만 전달).")
    return model
