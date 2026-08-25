#!/usr/bin/env python3
"""LogicKor 심판 모델을 오프라인 캐시에 적재한다.

채점 컨테이너(evaluate-logickor-judge)는 ``HF_HUB_OFFLINE=1`` 로 뜨고 ``/hf-cache`` 를
읽기전용으로 마운트한다. 즉 **미리 캐시에 있는 모델만** 심판으로 쓸 수 있고, 캐시에 없는
모델을 고르면 GPU 를 잡은 뒤 기동 단계에서 죽는다. 그래서 심판을 늘리는 순서는 정해져
있다 — ① 이 스크립트로 캐시 적재 → ② 화이트리스트에 추가.

그 순서를 사람이 기억하지 않아도 되도록, 받을 목록을 여기 복제하지 않고
``apps/llm_evaluation/src/evaluation/constants.py`` 의 ``LOGICKOR_JUDGE_MODELS`` 를 읽는다.
표에 한 줄 넣고 이 스크립트를 돌리면 그게 곧 적재다. 목록이 두 곳에 있으면 반드시
어긋나고, 어긋난 결과가 바로 위의 "GPU 잡고 죽는" 실패다.

사용:
    python3 fetch_judge_models.py --list           # 목록 + 캐시 여부만
    python3 fetch_judge_models.py                  # 빠진 것 전부 받기
    python3 fetch_judge_models.py --only qwen3-14b # 일부만
    python3 fetch_judge_models.py --dry-run

huggingface_hub 이 없으면:
    uv run --with huggingface_hub python3 fetch_judge_models.py

게이트된 모델(현 목록엔 없음)을 추가하면 ``HF_TOKEN`` 을 환경변수로 넘겨야 한다.
토큰은 절대 이 파일에 적지 않는다.
"""
from __future__ import annotations

import argparse
import ast
import os
import shutil
import sys
from pathlib import Path

# 이 파일 위치 기준(worktree/체크아웃 위치 무관) — Evaluation/serve/env.sh 와 같은 규약.
SERVE_DIR = Path(__file__).resolve().parent
LLMOPS_ROOT = SERVE_DIR.parent.parent
CONSTANTS = LLMOPS_ROOT / "apps/llm_evaluation/src/evaluation/constants.py"

# 채점 컨테이너의 /hf-cache 뒷단. PV hf-model-cache-tango-dev-2-pv 의 NFS 경로이며,
# 캐시 레이아웃은 <root>/hub/models--<org>--<name> 이다.
#   kubectl get pv hf-model-cache-tango-dev-2-pv -o jsonpath='{.spec.nfs.path}'
DEFAULT_CACHE_ROOT = os.environ.get(
    "HF_CACHE_ROOT", "/home/julian/tango-storage/huggingface-dev")

# 심판 추론에 쓰지 않는 포맷. 같은 가중치를 여러 포맷으로 올려 둔 저장소에서 캐시가
# 두 배로 불어나는 것을 막는다(.bin 은 safetensors 가 없는 저장소가 있어 남긴다).
IGNORE_PATTERNS = ["*.h5", "*.msgpack", "*.tflite", "*.ot", "original/*"]

# 여유 공간 안전마진(GB) — 받다가 디스크를 꽉 채우면 이 디스크를 쓰는 다른 것들이 같이 죽는다.
DISK_MARGIN_GB = 30


def load_catalog() -> tuple[list[dict], str]:
    """BE 화이트리스트를 읽는다. constants.py 는 순수 리터럴이라 import 없이 파싱된다."""
    if not CONSTANTS.is_file():
        sys.exit(f"화이트리스트를 찾을 수 없다: {CONSTANTS}")
    tree = ast.parse(CONSTANTS.read_text(encoding="utf-8"))
    found: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            name = getattr(target, "id", None)
            if name in ("LOGICKOR_JUDGE_MODELS", "LOGICKOR_DEFAULT_JUDGE_ID"):
                try:
                    found[name] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    models = found.get("LOGICKOR_JUDGE_MODELS")
    if not models:
        sys.exit(f"LOGICKOR_JUDGE_MODELS 를 {CONSTANTS} 에서 읽지 못했다")
    return [dict(m) for m in models], str(found.get("LOGICKOR_DEFAULT_JUDGE_ID") or "")


def cache_path(root: Path, hf_id: str) -> Path:
    return root / "hub" / ("models--" + hf_id.replace("/", "--"))


def is_cached(root: Path, hf_id: str) -> bool:
    """스냅샷이 실제로 존재해야 캐시된 것으로 본다 — 빈 디렉터리만 남는 경우가 있다."""
    snapshots = cache_path(root, hf_id) / "snapshots"
    return snapshots.is_dir() and any(snapshots.iterdir())


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1024 ** 3


def main() -> int:
    ap = argparse.ArgumentParser(description="LogicKor 심판 모델 캐시 적재")
    ap.add_argument("--cache-root", default=DEFAULT_CACHE_ROOT,
                    help=f"HF 캐시 루트 (기본: {DEFAULT_CACHE_ROOT})")
    ap.add_argument("--only", default="",
                    help="쉼표로 구분한 심판 id (기본: 캐시에 없는 것 전부)")
    ap.add_argument("--list", action="store_true", help="목록과 캐시 여부만 출력")
    ap.add_argument("--dry-run", action="store_true", help="받지 않고 계획만 출력")
    ap.add_argument("--force", action="store_true", help="이미 캐시된 것도 다시 받기")
    args = ap.parse_args()

    models, default_id = load_catalog()
    root = Path(args.cache_root)

    print(f"화이트리스트 : {CONSTANTS}")
    print(f"캐시 루트    : {root}")
    if not root.is_dir():
        print(f"  ⚠️ 캐시 루트가 없다. 만들려면: mkdir -p {root}/hub")
    print()

    rows = []
    for m in models:
        cached = root.is_dir() and is_cached(root, m["hf_id"])
        rows.append((m, cached))
        mark = "캐시됨" if cached else "없음  "
        star = " (기본)" if m["id"] == default_id else ""
        print(f"  [{mark}] {m['id']:<16} {m['hf_id']:<42} ~{m.get('size_gb', '?')}GB{star}")
    print()

    if args.list:
        return 0

    wanted = [s.strip() for s in args.only.split(",") if s.strip()]
    if wanted:
        known = {m["id"] for m in models}
        unknown = [w for w in wanted if w not in known]
        if unknown:
            sys.exit(f"모르는 심판 id: {unknown} (가능: {sorted(known)})")
        targets = [(m, c) for m, c in rows if m["id"] in wanted]
    else:
        targets = rows

    todo = [m for m, cached in targets if args.force or not cached]
    if not todo:
        print("받을 것이 없다 — 대상이 전부 캐시에 있다.")
        return 0

    need = sum(int(m.get("size_gb") or 0) for m in todo)
    have = free_gb(root if root.is_dir() else Path("/"))
    print(f"받을 대상 {len(todo)}개 · 예상 {need}GB · 여유 {have:.0f}GB")
    for m in todo:
        print(f"    - {m['id']} ({m['hf_id']})")
    if have - need < DISK_MARGIN_GB:
        sys.exit(f"공간 부족: {need}GB 를 받으면 여유가 {DISK_MARGIN_GB}GB 미만이 된다. "
                 f"불필요한 캐시를 지우거나 --only 로 나눠 받을 것.")

    if args.dry_run:
        print("\n--dry-run: 실제로 받지 않았다.")
        return 0

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        sys.exit("huggingface_hub 이 없다. 예: "
                 "uv run --with huggingface_hub python3 fetch_judge_models.py")

    token = os.environ.get("HF_TOKEN") or None   # 게이트 저장소용. 파일에 적지 않는다.
    hub = root / "hub"
    hub.mkdir(parents=True, exist_ok=True)

    failed = []
    for m in todo:
        print(f"\n=== {m['id']} · {m['hf_id']} ===")
        try:
            snapshot_download(
                repo_id=m["hf_id"], cache_dir=str(hub),
                ignore_patterns=IGNORE_PATTERNS, token=token,
                max_workers=4,
            )
        except Exception as e:                    # 하나 실패해도 나머지는 계속 받는다.
            print(f"  실패: {type(e).__name__}: {e}")
            failed.append(m["id"])
            continue
        ok = is_cached(root, m["hf_id"])
        print(f"  완료 (검증: {'OK' if ok else '스냅샷 없음 — 확인 필요'})")
        if not ok:
            failed.append(m["id"])

    print()
    if failed:
        print(f"실패: {failed}")
        print("게이트된 저장소라면 HF_TOKEN 을 환경변수로 넘길 것.")
        return 1
    print("전부 완료. 화이트리스트에 있는 심판이 모두 캐시에 있다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
