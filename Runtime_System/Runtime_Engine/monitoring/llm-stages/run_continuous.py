#!/usr/bin/env python3
"""Keep the Grafana observation workload running; rotate only its own records."""

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import pathlib
import shutil
import signal
import sys
import tarfile
import time
import uuid

from run_campaign import install_cancellation_handlers, run_runner, sha256


def verify_archive(archive, sources):
    with tarfile.open(archive, "r:gz") as stream:
        actual = {}
        for member in stream:
            if member.isfile():
                digest = hashlib.sha256()
                with stream.extractfile(member) as content:
                    for chunk in iter(lambda: content.read(1024*1024), b""):
                        digest.update(chunk)
                actual[member.name] = digest.hexdigest()
    if actual != sources:
        raise ValueError("archive verification failed; loose records retained")


def archive_campaign(root, campaign):
    if campaign.parent != root/"campaigns" or not campaign.name.startswith("continuous-"):
        raise ValueError("not a continuous observation campaign")
    runs = [pathlib.Path(path) for path in json.loads((campaign/"runs.json").read_text())]
    if any(path.parent != root/"runs" or not path.name.startswith(campaign.name+"-")
           for path in runs):
        raise ValueError("campaign refers to an unrelated run")
    paths = [campaign, *runs]
    files = [path for directory in paths for path in directory.rglob("*") if path.is_file()]
    sources = {str(path.relative_to(root)): sha256(path) for path in files}
    archives = root/"continuous-archives"
    archives.mkdir(exist_ok=True)
    archive = archives/(campaign.name+".tar.gz")
    temporary = archive.with_suffix(".gz.tmp")
    with tarfile.open(temporary, "w:gz") as stream:
        for path in paths:
            stream.add(path, arcname=str(path.relative_to(root)))
    verify_archive(temporary, sources)
    temporary.replace(archive)
    archive.with_suffix(".gz.sha256").write_text(sha256(archive)+"  "+archive.name+"\n")
    # Only delete after the compressed content matches every original file.
    for path in paths:
        shutil.rmtree(path)
    return archive


def trim_archives(directory, max_bytes=512*1024**2, max_age=48*3600):
    archives = sorted(directory.glob("continuous-*.tar.gz"), key=lambda p: p.stat().st_mtime)
    total = sum(path.stat().st_size for path in archives)
    cutoff = time.time()-max_age
    for path in archives:
        size = path.stat().st_size
        if total > max_bytes or path.stat().st_mtime < cutoff:
            path.unlink()
            path.with_suffix(".gz.sha256").unlink(missing_ok=True)
            total -= size


def rotate(root):
    # Keep the latest completed cycle loose for inspection. Earlier cycles have
    # been idle for a full cycle, so exporter acknowledgement writes are done.
    campaigns = sorted(path for path in (root/"campaigns").glob("continuous-*")
                       if (path/"outcome.json").is_file())
    for campaign in campaigns[:-1]:
        print("ARCHIVE", archive_campaign(root, campaign), flush=True)
    trim_archives(root/"continuous-archives")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path,
                        default=pathlib.Path("/home/rtst/tango2-llm-stages"))
    args = parser.parse_args()
    root = args.root.resolve()
    with (root/"continuous.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cancelled = [False]
        previous = install_cancellation_handlers(cancelled)
        try:
            while not cancelled[0]:
                rotate(root)
                stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                campaign = "continuous-"+stamp+"-"+uuid.uuid4().hex[:8]
                command = [sys.executable, str(root/"source/run_campaign.py"),
                           "--root", str(root), "--campaign", campaign,
                           "--blocks", "1", "--warmups", "1", "--modes", "detail"]
                print("CYCLE", campaign, flush=True)
                code, reason = run_runner(command, dict(os.environ), sys.stdout, cancelled,
                                          timeout=1800)
                print("CYCLE_FINISH", campaign, code, reason, flush=True)
                deadline = time.monotonic()+(60 if code else 2)
                while not cancelled[0] and time.monotonic() < deadline:
                    time.sleep(.2)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
