#!/usr/bin/env python3
"""Run on AGX: resident batch-one observations, disjoint from official tests."""

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import pathlib
import pwd
import shutil
import signal
import subprocess
import sys
import time

from metrics import CASES


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def field_control_lock(lock_path=pathlib.Path("/run/lock/tango2-field-control.lock"),
                       active_path=pathlib.Path("/run/tango2-bash/active")):
    lock = pathlib.Path(lock_path).open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    active = pathlib.Path(active_path)
    if active.exists():
        lock.close()
        raise RuntimeError("official field session is active: "+active.read_text().strip())
    return lock


def create_runs_root(root):
    runs = pathlib.Path(root)/"runs"
    runs.mkdir(parents=True, exist_ok=True)
    return runs


def stop_process(process, timeout=30):
    if process.poll() is not None:
        return process.returncode
    os.killpg(process.pid, signal.SIGTERM)
    deadline = time.monotonic()+timeout
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(.1)
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL)
    return process.wait()


def run_runner(command, env, log, cancelled, timeout=1800):
    process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic()+timeout
    while process.poll() is None:
        if cancelled[0] or time.monotonic() >= deadline:
            return stop_process(process), "campaign_cancelled" if cancelled[0] else "runner_timeout"
        time.sleep(.1)
    return process.returncode, ""


def install_cancellation_handlers(cancelled):
    def cancel(_signal, _frame):
        cancelled[0] = True
    return {sig: signal.signal(sig, cancel)
            for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)}


def write_campaign_evidence(campaign, runs, outcomes, cancelled):
    (campaign/"runs.json").write_text(json.dumps([str(path) for path in runs], indent=2)+"\n")
    (campaign/"outcome.json").write_text(
        json.dumps(dict(cancelled=cancelled[0], runs=outcomes), indent=2)+"\n")


def audit(root, run):
    return subprocess.run(["python3", str(root/"source/audit.py"), str(run)], check=False).returncode


def runner_command(root, engine, run, mode, run_id, blocks, warmups, selected, cpu_observation):
    # CASE must retain its positional slot even when all cases are selected.
    return [str(root/"bin/runner"), str(engine), str(root/"workload.json"), str(run),
            mode, run_id, "/dev/shm/tango2-llm-heartbeat.json", str(blocks), str(warmups),
            selected, cpu_observation]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/home/rtst/tango2-llm-stages"))
    parser.add_argument("--engine", type=pathlib.Path, default=pathlib.Path("/home/rtst/work/engines/qwen3-1.7b"))
    parser.add_argument("--campaign", default=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--overhead", action="store_true")
    parser.add_argument("--blocks", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--modes", nargs="+", choices=("live", "detail"), default=("live", "detail"))
    parser.add_argument("--cpu-observation", choices=("on", "off"), default="on",
                        help="Collect instrumented-thread CPU counters in detail mode")
    args = parser.parse_args()
    if args.blocks < 1 or not 0 <= args.warmups <= 10:
        parser.error("blocks must be positive and warmups must be between 0 and 10")
    # Only the field guard requires root. Drop back to the board account before
    # creating run files or launching inference; retain the locked descriptor.
    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo", "-n", "env", "PYTHONDONTWRITEBYTECODE=1",
                           sys.executable, str(pathlib.Path(__file__).resolve()), *sys.argv[1:]])
    field_lock = field_control_lock()
    account = pwd.getpwnam("rtst")
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    root = args.root.resolve()
    lock = (root/"observation.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    create_runs_root(root)
    if shutil.disk_usage(root).free < 5*1024**3:
        raise RuntimeError("less than 5GiB free")
    for pid in pathlib.Path("/proc").iterdir():
        if not pid.name.isdigit() or int(pid.name) == os.getpid():
            continue
        try:
            argv = (pid/"cmdline").read_bytes().replace(b"\0", b" ")
        except OSError:
            continue
        if any(pattern in argv for pattern in (b"bin/runner ", b"/llm_stream ", b"cyclictest ", b"/tc2/procedures/", b"/tc1/procedures/")):
            raise RuntimeError("existing inference or official test worker")
    affinity = set(os.sched_getaffinity(0))-{4}
    os.sched_setaffinity(0, affinity)
    env = dict(os.environ,
               LD_LIBRARY_PATH="/usr/local/cuda/targets/sbsa-linux/lib:/usr/lib/aarch64-linux-gnu",
               EDGELLM_PLUGIN_PATH="/home/rtst/TensorRT-Edge-LLM/build/libNvInfer_edgellm_plugin.so")
    manifest = dict(schema_version=1, engineering=True,
                    cpu_observation_requested=args.cpu_observation,
                    runtime_commit=subprocess.check_output(["git", "-C", "/home/rtst/TensorRT-Edge-LLM", "rev-parse", "HEAD"], text=True).strip(),
                    cpu_affinity=sorted(affinity), model_hashes={p.name: sha256(p) for p in args.engine.iterdir() if p.is_file()},
                    binary_sha256=sha256(root/"bin/runner"), workload_sha256=sha256(root/"workload.json"),
                    engine_path=str(args.engine), boot_id=pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                    governor=pathlib.Path("/sys/devices/system/cpu/cpufreq/policy0/scaling_governor").read_text().strip())
    campaign = root/"campaigns"/args.campaign
    campaign.mkdir(parents=True, exist_ok=False)
    (campaign/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    cancelled = [False]
    previous = install_cancellation_handlers(cancelled)
    runs, outcomes = [], []
    schedules = [(mode, args.blocks, "") for mode in args.modes]
    if args.overhead:
        schedules = [(mode, 1, "i64_o64,i256_o128,i1024_o128")
                     for block in range(3) for mode in ("baseline", "live", "detail")[block:]+("baseline", "live", "detail")[:block]]
    try:
        for index, (mode, blocks, selected) in enumerate(schedules):
            if cancelled[0] or shutil.disk_usage(root).free < 5*1024**3:
                break
            run_id = args.campaign+f"-{index:02d}-{mode}"
            run = root/"runs"/run_id
            run.mkdir()
            started = time.time_ns()
            (run/"manifest.json").write_text(json.dumps(dict(manifest, run_id=run_id, mode=mode,
                cpu_observation_enabled=mode == "detail" and args.cpu_observation == "on",
                started_utc_ns=started, evidence_path=str(run),
                expected_cases=selected.split(",") if selected else list(CASES),
                expected_attempts_per_case=10*blocks, warmups_per_case=args.warmups), indent=2)+"\n")
            command = runner_command(root, args.engine, run, mode, run_id, blocks,
                                     args.warmups, selected, args.cpu_observation)
            print("START", run_id, flush=True)
            with (run/"runner.log").open("w") as log:
                code, reason = run_runner(command, env, log, cancelled)
            audit_code = audit(root, run)
            outcomes.append(dict(run_id=run_id, exit_code=code, incomplete_reason=reason,
                                 audit_exit_code=audit_code))
            print("FINISH", run_id, "exit", code, flush=True)
            runs.append(run)
            if reason:
                break
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        write_campaign_evidence(campaign, runs, outcomes, cancelled)
        field_lock.close()
    comparison_code = 0
    if args.overhead and not cancelled[0] and len(runs) == len(schedules):
        comparison_code = subprocess.run(["python3", str(root/"source/audit.py"), *map(str, runs),
                        "--overhead-output", str(campaign/"overhead.json")], check=False).returncode
    failed = (cancelled[0] or len(runs) != len(schedules) or comparison_code
              or any(item["exit_code"] or item["audit_exit_code"] for item in outcomes))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
