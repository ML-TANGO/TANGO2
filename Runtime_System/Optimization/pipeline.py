#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py — 배포탑재 파이프라인 드라이버

deploy.yaml 한 장을 입력으로 받아, 학습된 신경망을 실행 코드·모델·배포 이미지가
담긴 산출물 폴더로 만들어 Data/Output 아래에 남긴다.

처리 순서
    ① 정리       이전 수행의 잔여 폴더(Data/<service>, Output/*, tmp_*) 제거
    ② 모델 변환   입력 포맷이 대상 실행 엔진과 맞지 않을 때 수행 → Data/tmp_model
    ③ 모델 경량화 use_optimization: yes 일 때 프루닝·양자화 수행 → Data/tmp_model
    ④ 코드 생성   <SERVICE>-template 을 복사하고 모델을 동봉     → Data/tmp_code
    ⑤ 이미지 빌드 deploy_method 가 raw 가 아닐 때 수행          → Data/tmp_image
    ⑥ 산출물 저장 이미지가 있으면 이미지를, 없으면 코드를        → Data/Output/<service>
    ⑦ 임시 정리   tmp_code / tmp_image / tmp_model 제거

폴더 구조
    Data/
      SDS-template/      서비스 타입별 실행 코드 원본
      tmp_model/         변환·경량화 중간 산출물 (수행 후 삭제)
      tmp_code/          실행 코드 + 모델      (수행 후 삭제)
      tmp_image/         배포 이미지 구성물    (수행 후 삭제)
      Output/<service>/  최종 산출물

사용 예
    python pipeline.py deploy.sds.yaml --dry-run        # 계획만 확인
    python pipeline.py deploy.sds.yaml                  # 전체 수행
    python pipeline.py deploy.sds.yaml --keep-tmp       # 중간 산출물 보존
    python pipeline.py deploy.sds.yaml --enable-convert # 모델 변환 단계 활성화

종료 코드 : 0 성공 / 1 단계 실패 / 2 설정 오류
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 모듈 경로 부트스트랩
#   각 단계 모듈이 기능별 서브폴더에 나뉘어 있으므로, 어디서 실행하든
#   import 가 해결되도록 저장소 루트와 서브폴더를 검색 경로에 넣는다.
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent
for _sub in ("", "model_optimizer", "model_converter", "code_generator",
             "image_builder"):
    _p = str(_ROOT / _sub) if _sub else str(_ROOT)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml_parser
from yaml_parser import ConfigError, DeployConfig, ENGINE_SPECS, Plan

# ---------------------------------------------------------------------------
# 모델 변환 단계 기본 비활성
#   변환 기능 자체는 stage_convert() 에 구현되어 있으나, 파이프라인 연결
#   시험 단계에서는 수행하지 않는다. --enable-convert 로 켤 수 있다.
# ---------------------------------------------------------------------------
CONVERT_ENABLED_BY_DEFAULT = False

STAGES = ["cleanup", "convert", "optimize", "codegen", "imagebuild",
          "publish", "finalize"]

STAGE_LABEL = {
    "cleanup":    "① 정리",
    "convert":    "② 모델 변환",
    "optimize":   "③ 모델 경량화",
    "codegen":    "④ 실행 코드 생성",
    "imagebuild": "⑤ 이미지 빌드",
    "publish":    "⑥ 산출물 저장",
    "finalize":   "⑦ 임시 폴더 정리",
}

ICON = {"ok": "✓", "skipped": "·", "bypassed": "·", "info": "!", "failed": "✗"}


# ---------------------------------------------------------------------------
# 실행 결과 / 문맥
# ---------------------------------------------------------------------------
@dataclass
class StageResult:
    name: str
    status: str              # ok / skipped / bypassed / info / failed
    message: str = ""
    output: Optional[Path] = None
    seconds: float = 0.0

    @property
    def failed(self) -> bool:
        return self.status == "failed"


@dataclass
class Ctx:
    cfg: DeployConfig
    plan: Plan
    data: Path                          # Data 폴더
    service: str                        # 서비스 타입 (sds / sdf / sdm)
    dry_run: bool = False
    enable_convert: bool = False
    build_image: bool = False
    model_dir: Optional[Path] = None    # 변환·경량화를 거친 현재 모델 위치
    model_format: str = ""
    code_dir: Optional[Path] = None     # tmp_code/<service>
    image_dir: Optional[Path] = None    # tmp_image/<service>
    results: list = field(default_factory=list)

    @property
    def output(self) -> Path:
        return self.data / "Output"

    @property
    def tmp_model(self) -> Path:
        return self.data / "tmp_model"

    @property
    def tmp_code(self) -> Path:
        return self.data / "tmp_code"

    @property
    def tmp_image(self) -> Path:
        return self.data / "tmp_image"

    @property
    def template(self) -> Path:
        """서비스 타입별 실행 코드 원본 폴더 (예: Data/SDS-template)."""
        return self.data / f"{self.service.upper()}-template"


def _log(msg: str = "") -> None:
    print(msg, file=sys.stderr, flush=True)


def _banner(stage: str) -> None:
    _log(f"\n{'=' * 68}\n▶ {STAGE_LABEL[stage]}\n{'=' * 68}")


def _rm(path: Path, dry: bool = False) -> bool:
    """폴더 또는 파일을 지운다. 실제로 지웠으면 True."""
    if not path.exists():
        return False
    if not dry:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    return True


def _copytree(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _count(path: Path) -> tuple:
    """(파일 수, 총 바이트)."""
    n = size = 0
    for p in path.rglob("*"):
        if p.is_file():
            n += 1
            size += p.stat().st_size
    return n, size


def _human(b: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024 or unit == "GB":
            return f"{b:.0f}{unit}" if unit == "B" else f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}GB"


# ---------------------------------------------------------------------------
# ① 정리 — 이전 수행의 잔여물 제거
# ---------------------------------------------------------------------------
def stage_cleanup(ctx: Ctx) -> StageResult:
    removed = []

    # 서비스 타입과 같은 이름의 폴더가 Data 바로 아래 있으면 제거
    if _rm(ctx.data / ctx.service, ctx.dry_run):
        removed.append(f"Data/{ctx.service}")

    # Output 아래 내용 전부 제거 (Output 폴더 자체는 유지)
    if ctx.output.exists():
        for child in sorted(ctx.output.iterdir()):
            if _rm(child, ctx.dry_run):
                removed.append(f"Output/{child.name}")
    elif not ctx.dry_run:
        ctx.output.mkdir(parents=True, exist_ok=True)

    # 임시 폴더 제거
    for d in (ctx.tmp_code, ctx.tmp_image, ctx.tmp_model):
        if _rm(d, ctx.dry_run):
            removed.append(d.name)

    if not removed:
        return StageResult("cleanup", "ok", "제거할 잔여 폴더 없음")
    return StageResult("cleanup", "ok",
                       f"{len(removed)}건 제거 : " + ", ".join(removed))


# ---------------------------------------------------------------------------
# ② 모델 변환
# ---------------------------------------------------------------------------
def _needs_convert(ctx: Ctx):
    """입력 포맷이 대상 실행 엔진이 요구하는 포맷과 다른지 판정."""
    engine = ctx.plan.target_engine
    want = ENGINE_SPECS[engine].model_format
    have = ctx.model_format
    if have == want:
        return False, f"입력 포맷({have})이 {engine} 요구 포맷과 일치"
    return True, f"{have} → {want} (엔진 {engine})"


def stage_convert(ctx: Ctx) -> StageResult:
    need, why = _needs_convert(ctx)
    if not need:
        return StageResult("convert", "skipped", f"변환 불필요 — {why}")

    if not ctx.enable_convert:
        # 기능은 구현되어 있으나 파이프라인 연결 시험 단계에서는 수행하지 않는다
        return StageResult(
            "convert", "info",
            f"변환 필요 판정({why}) — 현재 단계에서는 미수행 "
            f"(--enable-convert 로 활성화). 원본 모델을 그대로 사용")

    out = ctx.tmp_model / ctx.service
    if ctx.dry_run:
        return StageResult("convert", "ok", f"[dry-run] {why}", out)

    src = ctx.model_dir
    if src is None or not src.is_dir():
        return StageResult("convert", "failed",
                           f"입력 모델 폴더를 찾을 수 없습니다 : {src}")

    import model_converter
    t0 = time.time()
    _rm(out)
    code, msg = model_converter.convert_model(
        input_format=ctx.model_format,
        input_dir=str(src),
        output_format=ENGINE_SPECS[ctx.plan.target_engine].model_format,
        output_dir=str(out),
        gguf_outtype=ctx.plan.gguf_outtype,
    )
    dt = time.time() - t0
    if code != 0:
        return StageResult("convert", "failed", msg, seconds=dt)

    ctx.model_dir = out
    ctx.model_format = ENGINE_SPECS[ctx.plan.target_engine].model_format
    return StageResult("convert", "ok", why, out, dt)


# ---------------------------------------------------------------------------
# ③ 모델 경량화 (프루닝 → 양자화)
# ---------------------------------------------------------------------------
def _promote(ctx: Ctx, staged: Path) -> Path:
    """작업 폴더를 tmp_model/<service> 로 승격하고 이전 중간 모델을 제거한다."""
    final = ctx.tmp_model / ctx.service
    if staged.resolve() == final.resolve():
        return final
    if final.exists():
        shutil.rmtree(final)
    staged.rename(final)
    return final


def stage_optimize(ctx: Ctx) -> StageResult:
    use_opt = yaml_parser._as_bool(ctx.cfg.code_generation.use_optimization)
    if not use_opt:
        return StageResult("optimize", "skipped", "use_optimization 미설정")

    p, q = ctx.plan.prune, ctx.plan.quant
    if not p and not q:
        return StageResult("optimize", "skipped",
                           "use_optimization=yes 이나 수행할 경량화 항목 없음")

    parts = []
    if p:
        parts.append("프루닝 " + (p.nm_pattern if p.nm_pattern
                                else f"{p.method} {p.sparsity:.0%}"))
    if q:
        parts.append(f"양자화 {q.method} {q.bits}bit")
    desc = " + ".join(parts)

    if ctx.dry_run:
        return StageResult("optimize", "ok", f"[dry-run] {desc}",
                           ctx.tmp_model / ctx.service)

    src = ctx.model_dir
    if src is None or not src.is_dir():
        return StageResult("optimize", "failed",
                           f"입력 모델 폴더를 찾을 수 없습니다 : {src}")

    t0 = time.time()
    cur = src
    staged = None

    if p:
        import pruner
        staged = ctx.tmp_model / f"{ctx.service}__prune"
        _rm(staged)
        code, msg = pruner.prune_model(
            model_dir=str(cur), output_dir=str(staged), method=p.method,
            sparsity=p.sparsity, target_layers=p.target_layers,
            nm_pattern=p.nm_pattern, dataset=p.dataset_path,
            num_samples=p.num_samples, max_len=p.max_len)
        if code != 0:
            return StageResult("optimize", "failed", msg,
                               seconds=time.time() - t0)
        cur = staged

    if q:
        import optimizer
        qout = ctx.tmp_model / f"{ctx.service}__quant"
        _rm(qout)
        code, msg = optimizer.optimize_model(
            model_dir=str(cur), output_dir=str(qout), method=q.method,
            bits=q.bits, group_size=q.group_size, zero_point=q.zero_point,
            dataset=q.dataset_path, num_samples=q.num_samples,
            max_len=q.max_len, damping=q.damping, act_order=q.act_order)
        if code != 0:
            return StageResult("optimize", "failed", msg,
                               seconds=time.time() - t0)
        if staged:
            _rm(staged)            # 프루닝 중간 산출물 제거
        staged = qout

    final = _promote(ctx, staged)
    ctx.model_dir = final
    ctx.model_format = "safetensors"       # 경량화 산출물은 HF safetensors
    n, size = _count(final)
    return StageResult("optimize", "ok",
                       f"{desc} — 파일 {n}개 / {_human(size)}",
                       final, time.time() - t0)


# ---------------------------------------------------------------------------
# ④ 실행 코드 생성
# ---------------------------------------------------------------------------
def stage_codegen(ctx: Ctx) -> StageResult:
    out = ctx.tmp_code / ctx.service

    if ctx.service != "sds":
        # 시험 단계에서는 sds 만 지원. sdf / sdm 은 템플릿 정비 후 추가 예정.
        return StageResult(
            "codegen", "failed",
            f"service_type='{ctx.service}' 는 아직 지원하지 않습니다. "
            f"현재는 sds 만 동작합니다 "
            f"(Data/{ctx.service.upper()}-template 준비 필요)")

    if ctx.dry_run:
        return StageResult("codegen", "ok",
                           f"[dry-run] {ctx.template.name} → tmp_code/{ctx.service}",
                           out)

    if not ctx.template.is_dir():
        return StageResult("codegen", "failed",
                           f"템플릿 폴더가 없습니다 : {ctx.template}")

    t0 = time.time()
    _rm(out)
    _copytree(ctx.template, out)
    ctx.code_dir = out
    detail = [f"{ctx.template.name} 복사"]

    # 변환·경량화를 거친 모델이 있으면 실행 코드와 함께 묶는다
    if ctx.model_dir and ctx.model_dir.is_dir() \
            and str(ctx.model_dir).startswith(str(ctx.tmp_model)):
        model_dst = out / "model"
        _rm(model_dst)
        _copytree(ctx.model_dir, model_dst)
        detail.append("모델 동봉 → model/")

    n, size = _count(out)
    return StageResult("codegen", "ok",
                       " · ".join(detail) + f" — 파일 {n}개 / {_human(size)}",
                       out, time.time() - t0)


# ---------------------------------------------------------------------------
# ⑤ 이미지 빌드
# ---------------------------------------------------------------------------
def stage_imagebuild(ctx: Ctx) -> StageResult:
    method = (ctx.cfg.image_build.deploy_method or "raw").lower()
    out = ctx.tmp_image / ctx.service

    if method == "raw":
        return StageResult("imagebuild", "bypassed",
                           "deploy_method=raw — 이미지 생성 없이 통과")

    if ctx.dry_run:
        return StageResult("imagebuild", "ok",
                           f"[dry-run] deploy_method={method}", out)

    if ctx.code_dir is None or not ctx.code_dir.is_dir():
        return StageResult("imagebuild", "failed",
                           "실행 코드 폴더가 없습니다 — 코드 생성 단계를 먼저 수행하세요")

    import imagebuild
    t0 = time.time()
    _rm(out)
    code, msg = imagebuild.build_artifacts(
        ctx.plan, ctx.cfg, out,
        service_dir=str(ctx.code_dir),
        model_dir="./model" if (ctx.code_dir / "model").is_dir() else None)
    if code != 0:
        return StageResult("imagebuild", "failed", msg, seconds=time.time() - t0)

    detail = [msg]

    # 컨테이너 이미지 실물은 docker 가 있을 때만 빌드한다
    if ctx.build_image:
        if shutil.which("docker") is None:
            detail.append("docker 미설치로 이미지 실물 빌드 생략")
        else:
            image = (ctx.cfg.image_build.build_info.image_file
                     or f"{ctx.service}:latest")
            r = subprocess.run(["docker", "build", "-t", image, "."],
                               cwd=str(out), capture_output=True, text=True)
            if r.returncode != 0:
                return StageResult(
                    "imagebuild", "failed",
                    f"docker build 실패 : {r.stderr.strip()[-300:]}",
                    seconds=time.time() - t0)
            tar = out / f"{ctx.service}-image.tar"
            subprocess.run(["docker", "save", "-o", str(tar), image],
                           check=False)
            detail.append(f"이미지 빌드·저장 : {tar.name}")
    else:
        detail.append("이미지 실물 빌드는 --build-image 로 수행")

    ctx.image_dir = out
    n, size = _count(out)
    return StageResult("imagebuild", "ok",
                       " · ".join(detail) + f" — 파일 {n}개 / {_human(size)}",
                       out, time.time() - t0)


# ---------------------------------------------------------------------------
# ⑥ 산출물 저장
# ---------------------------------------------------------------------------
def stage_publish(ctx: Ctx) -> StageResult:
    dst = ctx.output / ctx.service
    use_image = bool(ctx.image_dir and ctx.image_dir.is_dir())
    src = ctx.image_dir if use_image else ctx.code_dir
    kind = "배포 이미지" if use_image else "실행 코드"

    if ctx.dry_run:
        return StageResult("publish", "ok",
                           f"[dry-run] {kind} → Output/{ctx.service}", dst)

    if src is None or not src.is_dir():
        return StageResult("publish", "failed",
                           "저장할 산출물이 없습니다 (코드 생성 결과 없음)")

    t0 = time.time()
    _rm(dst)                      # 기존 산출물은 모두 지우고 새로 만든다
    _copytree(src, dst)
    n, size = _count(dst)
    return StageResult("publish", "ok",
                       f"{kind} 저장 — 파일 {n}개 / {_human(size)}",
                       dst, time.time() - t0)


# ---------------------------------------------------------------------------
# ⑦ 임시 폴더 정리
# ---------------------------------------------------------------------------
def stage_finalize(ctx: Ctx, keep: bool = False) -> StageResult:
    if keep:
        return StageResult("finalize", "skipped", "--keep-tmp — 임시 폴더 보존")
    if ctx.dry_run:
        return StageResult("finalize", "ok", "[dry-run] tmp_* 제거")

    removed = [d.name for d in (ctx.tmp_code, ctx.tmp_image, ctx.tmp_model)
               if _rm(d)]
    if not removed:
        return StageResult("finalize", "ok", "제거할 임시 폴더 없음")
    return StageResult("finalize", "ok", "제거 : " + ", ".join(removed))


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------
def run(ctx: Ctx, keep_tmp: bool = False):
    funcs = {
        "cleanup": stage_cleanup,
        "convert": stage_convert,
        "optimize": stage_optimize,
        "codegen": stage_codegen,
        "imagebuild": stage_imagebuild,
        "publish": stage_publish,
        "finalize": lambda c: stage_finalize(c, keep_tmp),
    }
    for name in STAGES:
        _banner(name)
        try:
            res = funcs[name](ctx)
        except Exception as e:
            res = StageResult(name, "failed", f"{type(e).__name__}: {e}")
        ctx.results.append(res)
        _log(f"{ICON[res.status]} {res.message or res.status}")
        if res.failed:
            _log(f"\n[중단] {STAGE_LABEL[name]} 단계에서 실패했습니다.")
            break
    return ctx.results


def summary(ctx: Ctx) -> None:
    _log(f"\n{'=' * 68}\n요약\n{'=' * 68}")
    for r in ctx.results:
        t = f"{r.seconds:6.1f}s" if r.seconds else "      -"
        _log(f"  {ICON[r.status]} {STAGE_LABEL[r.name]:<14} {t}  {r.message}")
    pub = next((r for r in ctx.results
                if r.name == "publish" and r.output and not r.failed), None)
    if pub:
        _log(f"\n최종 산출물 : {pub.output}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="배포탑재 파이프라인 — deploy.yaml 기반 실행 이미지 생성",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("config", help="deploy.yaml 경로")
    ap.add_argument("-d", "--data-dir", default=None,
                    help="Data 폴더 경로 (기본 : pipeline.py 옆의 Data)")
    ap.add_argument("--dry-run", action="store_true",
                    help="실제 수행 없이 단계 계획만 출력")
    ap.add_argument("--strict", action="store_true", help="검증 경고도 실패로 처리")
    ap.add_argument("--keep-tmp", action="store_true",
                    help="tmp_code / tmp_image / tmp_model 보존")
    ap.add_argument("--enable-convert", action="store_true",
                    default=CONVERT_ENABLED_BY_DEFAULT,
                    help="모델 변환 단계 활성화 (기본은 미수행)")
    ap.add_argument("--build-image", action="store_true",
                    help="docker 로 컨테이너 이미지 실물까지 빌드")
    args = ap.parse_args()

    # ── 설정 로드 ──────────────────────────────────────────────────
    try:
        cfg = DeployConfig.from_yaml(args.config)
    except (ConfigError, OSError) as e:
        _log(f"[FATAL] 설정을 읽을 수 없습니다 : {e}")
        return 2
    except Exception as e:
        _log(f"[FATAL] YAML 파싱 실패 : {e}")
        return 2

    # ── 검증 ───────────────────────────────────────────────────────
    _log(f"\n{'=' * 68}\n▶ 설정 검증\n{'=' * 68}")
    errors, warnings = cfg.validate()
    for w in warnings:
        _log(f"[WARN ] {w}")
    for e in errors:
        _log(f"[ERROR] {e}")
    if errors:
        _log(f"\n검증 실패 : 에러 {len(errors)}건")
        return 2
    if args.strict and warnings:
        _log(f"\n--strict : 경고 {len(warnings)}건을 실패로 처리")
        return 2
    _log(f"✓ 검증 통과 (경고 {len(warnings)}건)")

    plan = cfg.resolve_plan()
    service = (cfg.code_generation.service_info.service_type or "").lower()
    if not service:
        _log("[FATAL] code_generation.service_info.service_type 이 필요합니다.")
        return 2

    data = Path(args.data_dir) if args.data_dir else _ROOT / "Data"
    if not data.is_dir():
        _log(f"[FATAL] Data 폴더를 찾을 수 없습니다 : {data}")
        return 2

    ctx = Ctx(cfg=cfg, plan=plan, data=data, service=service,
              dry_run=args.dry_run, enable_convert=args.enable_convert,
              build_image=args.build_image,
              model_dir=Path(plan.input_model), model_format=plan.input_format)

    # 변환·경량화를 수행할 때만 입력 모델 실체가 필요하다
    need_model = args.enable_convert or bool(
        yaml_parser._as_bool(cfg.code_generation.use_optimization))
    if need_model and not args.dry_run and not ctx.model_dir.is_dir():
        _log(f"[FATAL] 입력 모델 폴더를 찾을 수 없습니다 : {ctx.model_dir}")
        return 2

    _log(f"\n--- 실행 계획 ---\n{plan.describe()}")
    _log(f"서비스 타입 : {service}  (템플릿 : {ctx.template.name})")
    _log(f"Data 폴더   : {data}")
    _log(f"배포 방식   : {cfg.image_build.deploy_method}")
    if not args.enable_convert:
        _log("모델 변환   : 미수행 (기능 구현 완료, 시험 단계에서 비활성)")
    if args.dry_run:
        _log("\n[dry-run] 실제 변경은 수행하지 않습니다.")

    # ── 수행 ───────────────────────────────────────────────────────
    run(ctx, keep_tmp=args.keep_tmp)
    summary(ctx)

    if any(r.failed for r in ctx.results):
        return 1
    print("success")
    return 0


if __name__ == "__main__":
    sys.exit(main())
