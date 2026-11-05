"""MixATIS UGEN 포맷 학습 드라이버 — ETRI `train_qwen3_mixatis.py` 를 그대로 돌린다.

왜 이 단계가 필요한가. UGEN 패러다임은 정답을 `"값 is one 슬롯명"` 같은 고정 형식으로
생성해야 채점된다. 형식을 배우지 않은 베이스 모델은 내용을 알아도 0 점이 나온다 —
Qwen3-8B 로 실측했을 때 828 발화 중 형식 준수 **0 건**(JSON 339 / 마크다운 443),
joint_acc 0.0 이었다. 원본 파이프라인도 [1/2] 학습 → [2/2] 평가 두 단계이고
ETRI README 의 95.89%/98.10% 는 학습 후 수치다.

**divergence 0**: 지표·프롬프트와 같은 이유로 학습 semantics 도 재구현하지 않는다.
원본 `main()` 을 argv 를 합성해 그대로 호출한다. 그래야 completion-only 라벨 마스킹
(-100), `enable_thinking=False`, LoRA 설정, TrainingArguments 가 원본과 한 글자도
어긋나지 않는다. 우리가 손대는 것은 두 군데뿐이다.
  1) `build_training_examples` 를 감싸 예제 수를 줄인다(원본 `--debug` 는 앞 200 개 고정).
  2) `Trainer` 를 감싸 진행률 콜백을 붙인다(플랫폼 /jobs 폴링용).

원본 기본값에서 바꾼 것은 optimizer 하나다. 원본은 40G 급을 상정해
`paged_adamw_8bit` 를 기본으로 두지만, 우리 잡은 bf16 로 올리고 학습 파라미터가
LoRA 43M 뿐이라 `adamw_torch` 가 더 단순하고 bitsandbytes 의존이 사라진다.
"""
from __future__ import annotations

import os
import random
import sys
from typing import Any, Callable, Dict, List, Optional

# 원본 학습 스크립트의 기본값(바꾸지 않는 것들은 여기 적지 않는다).
DEFAULT_TRAIN_EXAMPLES = 3000      # 발화 1500 x 2 문항. 1 에폭 10 분대에서 형식이 잡힌다.
DEFAULT_EPOCHS = 1.0
DEFAULT_BATCH_SIZE = 8
DEFAULT_GRAD_ACCUM = 2             # 유효 배치 16 = 원본(2 x 8)과 동일 → LR 스케줄 동형
DEFAULT_MAX_LEN = 768              # 원본 권장(슬롯 옵션 78 종이 길다)
DEFAULT_SEED = 42
DEFAULT_OPTIM = "adamw_torch"

# 파라미터 상한 — params 는 외부 입력이라 경계에서 막는다.
MAX_EXAMPLES = 100_000
MAX_EPOCHS = 10.0
MAX_BATCH_SIZE = 32
MAX_GRAD_ACCUM = 64


def _subset_wrapper(orig: Callable, limit: int, seed: int,
                    emit: Callable[[str], None]) -> Callable:
    """발화 단위로 시드 셔플 후 앞에서 자르는 래퍼.

    원본은 발화당 (intent QA, slot QA) 2 개를 이 순서로 연속 배치한다. 그냥 앞에서
    자르면 파일 순서 편향이 그대로 들어오므로 쌍을 유지한 채 섞는다 — 두 과제의
    비율(1:1)도 이렇게 해야 보존된다.
    """
    def wrapped(data_dir: str, split: str) -> List[Dict]:
        examples = orig(data_dir, split)
        if limit <= 0 or limit >= len(examples):
            emit(f"학습 예제 전체 {len(examples)}개 사용")
            return examples
        pairs = [examples[i:i + 2] for i in range(0, len(examples), 2)]
        for p in pairs:
            if [e["task"] for e in p] != ["intent", "slot"]:
                raise ValueError("원본 예제 배치가 (intent, slot) 쌍이 아니다 — "
                                 "train_qwen3_mixatis.py 변경 의심")
        random.Random(seed).shuffle(pairs)
        picked = [e for pair in pairs[:limit // 2] for e in pair]
        emit(f"학습 예제 {len(examples)}개 중 {len(picked)}개 사용 "
             f"(발화 {limit // 2}개 x 2문항, seed={seed})")
        return picked
    return wrapped


def _install_progress(mod, progress: Optional[Callable[[float, str], None]],
                      lo: float, hi: float) -> None:
    """원본이 내부에서 만드는 Trainer 에 진행률 콜백을 끼운다."""
    if progress is None:
        return
    from transformers import TrainerCallback

    class _Cb(TrainerCallback):
        def on_step_end(self, args, state, control, **kw):  # noqa: ANN001
            total = state.max_steps or 0
            if total:
                frac = state.global_step / total
                progress(lo + (hi - lo) * frac,
                         f"학습 {state.global_step}/{total} 스텝")
            return control

    orig_trainer = mod.Trainer

    def _factory(*a: Any, **kw: Any):
        trainer = orig_trainer(*a, **kw)
        trainer.add_callback(_Cb())
        return trainer

    mod.Trainer = _factory


def _clamp(value: Any, default, lo, hi, cast):
    try:
        v = cast(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def run_train(model_path: str, adapter_dir: str, data_dir: str,
              gpu_devices: str = "0", params: Optional[dict] = None,
              progress: Optional[Callable[[float, str], None]] = None,
              lo: float = 0.02, hi: float = 0.45) -> Dict[str, Any]:
    """`model_path` 에서 출발해 MixATIS train split 으로 LoRA SFT → `adapter_dir` 에 저장.

    돌려주는 dict 는 metrics.json 의 `train` 절에 그대로 실린다 — 어떤 레시피로 낸
    점수인지가 체크포인트 간 비교의 전제라 런에 새긴다.
    """
    params = params or {}
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_devices

    examples_limit = _clamp(params.get("train_examples"), DEFAULT_TRAIN_EXAMPLES,
                            0, MAX_EXAMPLES, int)
    epochs = _clamp(params.get("train_epochs"), DEFAULT_EPOCHS, 0.01, MAX_EPOCHS, float)
    batch_size = _clamp(params.get("train_batch_size"), DEFAULT_BATCH_SIZE,
                        1, MAX_BATCH_SIZE, int)
    grad_accum = _clamp(params.get("train_grad_accum"), DEFAULT_GRAD_ACCUM,
                        1, MAX_GRAD_ACCUM, int)
    seed = _clamp(params.get("train_seed"), DEFAULT_SEED, 0, 2**31 - 1, int)
    use_4bit = bool(params.get("use_4bit"))

    def emit(msg: str) -> None:
        if progress:
            progress(lo, msg)

    import train_qwen3_mixatis as T

    orig_build = T.build_training_examples
    orig_trainer = T.Trainer

    argv = [
        "train_qwen3_mixatis.py",
        "--model_name", model_path,
        "--data_dir", data_dir,
        "--output_dir", adapter_dir,
        "--epochs", str(epochs),
        "--batch_size", str(batch_size),
        "--grad_accum", str(grad_accum),
        "--max_len", str(DEFAULT_MAX_LEN),
        "--optim", DEFAULT_OPTIM,
        "--seed", str(seed),
        # 스텝 수보다 크게 둬 중간 체크포인트를 만들지 않는다(잡 디스크 절약).
        "--save_steps", "100000",
        "--logging_steps", "10",
    ]
    if use_4bit:
        argv.append("--use_4bit")

    # 패치는 반드시 try **안에서** 건다. 밖에서 걸면 그 사이에 예외가 나는 순간
    # (예: _install_progress 의 TrainerCallback import 실패) 패치가 복원 없이 남고,
    # 이 컨테이너는 잡이 끝나도 죽지 않으므로 **다음 잡이 오염된 모듈로 돈다**.
    saved_argv = sys.argv
    try:
        T.build_training_examples = _subset_wrapper(orig_build, examples_limit, seed, emit)
        _install_progress(T, progress, lo, hi)
        sys.argv = argv
        T.main()
    finally:
        # 셋 다 모듈 속성/전역 대입이라 실패할 여지가 없어 한 블록에 둔다.
        sys.argv = saved_argv
        T.build_training_examples = orig_build
        T.Trainer = orig_trainer

    return {
        "trained": True,
        "base_checkpoint": os.path.basename(model_path),
        "examples": examples_limit or "all",
        "epochs": epochs,
        "batch_size": batch_size,
        "grad_accum": grad_accum,
        "effective_batch": batch_size * grad_accum,
        "max_len": DEFAULT_MAX_LEN,
        "optim": DEFAULT_OPTIM,
        "seed": seed,
        "use_4bit": use_4bit,
        "split": "train",
        "adapter_dir": adapter_dir,
    }
