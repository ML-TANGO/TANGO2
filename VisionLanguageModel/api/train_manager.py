"""
train_manager.py — 에바(Eva) VLM 학습 작업 관리자

역할:
  - train.py / train_text_lora.py 를 subprocess로 실행
  - 작업 상태(pending/running/completed/failed/stopped)를 in-memory로 추적
  - 로그 파일을 통해 현재 step/loss 파싱
  - 다중 학습 작업을 job_id로 관리 (동시 실행은 GPU 1장 환경에서는 1개만 허용)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from schemas import TrainParams, TrainStatus


# ── 작업 상태 레코드 ─────────────────────────────────────────────────────────

@dataclass
class TrainJob:
    job_id:       str
    phase:        str
    status:       TrainStatus = "pending"
    current_step: int         = 0
    total_steps:  int         = 0
    current_loss: Optional[float] = None
    output_dir:   Optional[str]   = None
    started_at:   Optional[float] = None
    finished_at:  Optional[float] = None
    error:        Optional[str]   = None
    log_path:     Optional[str]   = None
    _process:     Optional[asyncio.subprocess.Process] = field(
        default=None, repr=False, compare=False
    )

    @property
    def elapsed_sec(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.finished_at or time.time()
        return end - self.started_at

    @property
    def progress_pct(self) -> Optional[float]:
        if self.total_steps and self.total_steps > 0:
            return min(100.0, self.current_step / self.total_steps * 100)
        return None


# ── 학습 관리자 ───────────────────────────────────────────────────────────────

class TrainManager:
    """에바 VLM 학습 작업 관리자 (싱글톤)."""

    def __init__(self) -> None:
        self._jobs: Dict[str, TrainJob] = {}
        self._running_job_id: Optional[str] = None

    @property
    def has_running_job(self) -> bool:
        return self._running_job_id is not None

    def get_job(self, job_id: str) -> Optional[TrainJob]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[TrainJob]:
        return list(self._jobs.values())

    # ── 학습 시작 ─────────────────────────────────────────────────────────────

    async def start(self, params: TrainParams) -> str:
        """학습을 비동기로 시작하고 job_id를 반환한다."""
        if self.has_running_job:
            raise RuntimeError(
                f"이미 실행 중인 학습 작업이 있습니다: {self._running_job_id}. "
                "GPU 1장 환경에서는 동시 학습이 불가합니다."
            )

        job_id = str(uuid.uuid4())[:8]
        checkpoints_root = os.environ.get("EVA_CHECKPOINTS_ROOT", "/models/checkpoints")
        output_dir = os.path.join(checkpoints_root, params.output_checkpoint_name)
        log_path = os.path.join(output_dir, "train.log")

        job = TrainJob(
            job_id=job_id,
            phase=params.phase,
            status="pending",
            output_dir=output_dir,
            log_path=log_path,
        )
        self._jobs[job_id] = job
        self._running_job_id = job_id

        # 비동기로 subprocess 시작
        asyncio.create_task(self._run(job, params))
        return job_id

    async def _run(self, job: TrainJob, params: TrainParams) -> None:
        """실제 학습 subprocess를 실행하고 상태를 업데이트한다."""
        vlm_root = os.environ.get("EVA_VLM_ROOT", "/app/vlm")
        python   = os.environ.get("EVA_PYTHON", "python3")

        os.makedirs(job.output_dir, exist_ok=True)

        cmd = self._build_command(python, vlm_root, params, job.output_dir)

        job.status     = "running"
        job.started_at = time.time()

        try:
            with open(job.log_path, "w") as log_f:
                # A3: start_new_session=True — DeepSpeed 자식 프로세스를 새 세션으로
                # 분리하여 stop() 시 process group 전체에 시그널 전달 가능하게 함
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=log_f,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=vlm_root,
                    start_new_session=True,
                )
                job._process = process

                # A2: monitor를 별도 task로 실행하고 process 종료 후 cancel.
                # 기존 gather() 방식은 _monitor_log의 while 루프가 process 종료
                # 후에도 빠져나오지 못해 gather가 영원히 대기하는 deadlock 발생.
                monitor_task = asyncio.create_task(self._monitor_log(job))
                try:
                    await process.wait()
                finally:
                    monitor_task.cancel()
                    try:
                        await monitor_task
                    except asyncio.CancelledError:
                        pass

            returncode = process.returncode
            if returncode == 0:
                job.status = "completed"
                job.current_step = job.total_steps
            elif job.status != "stopped":
                job.status = "failed"
                job.error  = f"프로세스 종료 코드: {returncode}"

        except Exception as e:
            job.status = "failed"
            job.error  = str(e)
        finally:
            job.finished_at      = time.time()
            job._process         = None
            self._running_job_id = None

    def _build_command(
        self,
        python: str,
        vlm_root: str,
        params: TrainParams,
        output_dir: str,
    ) -> list[str]:
        """학습 단계별 CLI 명령을 생성한다."""
        ds_stage  = params.zero_stage if params.zero_stage in (2, 3) else 2
        ds_config = os.path.join(vlm_root, "scripts", f"zero{ds_stage}.json")

        if params.phase == "lora_marine":
            # train_text_lora.py (텍스트 전용, Phase 2b)
            cmd = [
                python, os.path.join(vlm_root, "train_text_lora.py"),
                "--llm_model",   params.llm_model_path,
                "--output_dir",  output_dir,
            ]
            if params.marine_data_path:
                cmd += ["--data_path", params.marine_data_path]
            if params.resume_lora_path:
                cmd += ["--lora_path", params.resume_lora_path]
            if params.num_epochs:
                cmd += ["--num_epochs",  str(params.num_epochs)]
            if params.batch_size:
                cmd += ["--batch_size",  str(params.batch_size)]
            if params.grad_accum:
                cmd += ["--grad_accum",  str(params.grad_accum)]
            if params.learning_rate:
                cmd += ["--learning_rate", str(params.learning_rate)]
        else:
            # train.py (이미지+텍스트, Phase 1/2a/3)
            train_type = "projector" if params.phase == "projector" else "lora"
            cmd = [
                python, os.path.join(vlm_root, "train.py"),
                "--train_type",  train_type,
                "--llm_model",   params.llm_model_path,
                "--output_dir",  output_dir,
                "--deepspeed",   ds_config,
            ]
            if params.data_path:
                cmd += ["--data_path", params.data_path]
            if params.image_dir:
                cmd += ["--image_dir",  params.image_dir]
            if params.projector_path:
                cmd += ["--projector_path", params.projector_path]
            if params.resume_lora_path:
                cmd += ["--resume_lora_path", params.resume_lora_path]
            if params.num_epochs:
                cmd += ["--num_epochs",  str(params.num_epochs)]
            if params.batch_size:
                cmd += ["--batch_size",  str(params.batch_size)]
            if params.grad_accum:
                cmd += ["--grad_accum",  str(params.grad_accum)]
            if params.learning_rate:
                cmd += ["--learning_rate", str(params.learning_rate)]
            if params.lora_r:
                cmd += ["--lora_r",     str(params.lora_r)]
            if params.lora_alpha:
                cmd += ["--lora_alpha", str(params.lora_alpha)]
            if params.max_steps:
                cmd += ["--max_steps",  str(params.max_steps)]
            if params.sds_scenario and params.phase == "lora_sds":
                cmd += ["--sds_scenario", params.sds_scenario]

        return cmd

    async def _monitor_log(self, job: TrainJob) -> None:
        """학습 로그 파일을 주기적으로 읽어 step/loss 정보를 파싱한다."""
        # HuggingFace Trainer 로그 패턴: "{'loss': 0.4321, ..., 'step': 100}"
        step_loss_re = re.compile(
            r"'loss':\s*([\d.]+).*?'step':\s*(\d+)", re.DOTALL
        )
        # "***** Running training *****" 이후 "  Num steps = N" 파싱
        total_re = re.compile(r"Num\s+(?:optimization\s+)?steps\s*=\s*(\d+)")

        while job.status == "running":
            await asyncio.sleep(5)
            try:
                if not job.log_path or not os.path.exists(job.log_path):
                    continue
                with open(job.log_path, "r", errors="replace") as f:
                    content = f.read()

                # total_steps 파싱
                if job.total_steps == 0:
                    m = total_re.search(content)
                    if m:
                        job.total_steps = int(m.group(1))

                # 마지막 step/loss 파싱
                matches = step_loss_re.findall(content)
                if matches:
                    last_loss, last_step = matches[-1]
                    job.current_loss = float(last_loss)
                    job.current_step = int(last_step)
            except Exception:
                pass

    # ── 학습 중지 ─────────────────────────────────────────────────────────────

    async def stop(self, job_id: str) -> None:
        """실행 중인 학습 작업을 중지한다."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"job_id를 찾을 수 없습니다: {job_id}")
        if job.status != "running":
            raise RuntimeError(f"실행 중이 아닌 작업입니다 (status={job.status})")

        if job._process and job._process.pid:
            try:
                # A3: process group 전체에 SIGTERM — DeepSpeed torchrun 자식까지 정리
                os.killpg(os.getpgid(job._process.pid), signal.SIGTERM)
                await asyncio.sleep(3)
                if job._process.returncode is None:
                    os.killpg(os.getpgid(job._process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

        job.status      = "stopped"
        job.finished_at = time.time()
        self._running_job_id = None


# ── 싱글톤 ────────────────────────────────────────────────────────────────────

_train_manager = TrainManager()


def get_train_manager() -> TrainManager:
    return _train_manager
