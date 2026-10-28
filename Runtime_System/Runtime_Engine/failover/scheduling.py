#!/usr/bin/env python3

import os


POLICY_NAMES = {
    os.SCHED_OTHER: "SCHED_OTHER",
    os.SCHED_FIFO: "SCHED_FIFO",
    os.SCHED_RR: "SCHED_RR",
}
if hasattr(os, "SCHED_BATCH"):
    POLICY_NAMES[os.SCHED_BATCH] = "SCHED_BATCH"
if hasattr(os, "SCHED_IDLE"):
    POLICY_NAMES[os.SCHED_IDLE] = "SCHED_IDLE"


def scheduling_snapshot(pid=0):
    policy = os.sched_getscheduler(pid)
    return {
        "affinity": sorted(os.sched_getaffinity(pid)),
        "policy": POLICY_NAMES.get(policy, f"UNKNOWN({policy})"),
        "priority": os.sched_getparam(pid).sched_priority,
    }


def require_unmodified_scheduling(pid=0, label="process"):
    snapshot = scheduling_snapshot(pid)
    if snapshot["policy"] != "SCHED_OTHER" or snapshot["priority"] != 0:
        raise RuntimeError(
            f"{label} is not using default scheduling: {snapshot}"
        )
    if len(snapshot["affinity"]) < 2:
        raise RuntimeError(
            f"{label} is unexpectedly pinned to {snapshot['affinity']}"
        )
    return snapshot
