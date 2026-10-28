#!/usr/bin/env python3

import json
import subprocess
from dataclasses import asdict, dataclass

from common import read_proc_start_ticks


@dataclass(frozen=True)
class ContainerTarget:
    namespace: str
    pod_name: str
    pod_uid: str
    pod_ip: str
    container_name: str
    container_id: str
    pid: int
    start_ticks: int

    def to_dict(self):
        return asdict(self)


def _run_json(command, runner=subprocess.run):
    completed = runner(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(completed.stdout)


def resolve_container(
    namespace,
    pod_name,
    container_name,
    kubeconfig,
    runner=subprocess.run,
    require_ready=True,
):
    pod = _run_json(
        [
            "kubectl",
            "--kubeconfig",
            kubeconfig,
            "-n",
            namespace,
            "get",
            "pod",
            pod_name,
            "-o",
            "json",
        ],
        runner,
    )
    if pod.get("status", {}).get("phase") != "Running":
        raise RuntimeError(f"pod {namespace}/{pod_name} is not Running")

    statuses = pod.get("status", {}).get("containerStatuses", [])
    status = next((item for item in statuses if item.get("name") == container_name), None)
    if not status:
        raise RuntimeError(f"container {container_name} status is missing")
    if require_ready and not status.get("ready"):
        raise RuntimeError(f"container {container_name} is not Ready")
    raw_id = status.get("containerID", "")
    prefix = "containerd://"
    if not raw_id.startswith(prefix):
        raise RuntimeError(f"unexpected container ID: {raw_id}")
    container_id = raw_id[len(prefix) :]

    inspected = _run_json(["crictl", "inspect", container_id], runner)
    cri_status = inspected.get("status", {})
    cri_info = inspected.get("info", {})
    labels = cri_status.get("labels", {})
    expected_labels = {
        "io.kubernetes.pod.name": pod_name,
        "io.kubernetes.pod.namespace": namespace,
        "io.kubernetes.pod.uid": pod["metadata"]["uid"],
        "io.kubernetes.container.name": container_name,
    }
    if cri_status.get("state") != "CONTAINER_RUNNING":
        raise RuntimeError(f"container {container_id} is not running")
    if cri_status.get("id") != container_id:
        raise RuntimeError("kubectl and CRI container IDs differ")
    for key, expected in expected_labels.items():
        if labels.get(key) != expected:
            raise RuntimeError(f"CRI label {key} does not match Pod metadata")

    pid = int(cri_info.get("pid", 0))
    if pid <= 0:
        raise RuntimeError("CRI did not return a valid init PID")
    return ContainerTarget(
        namespace=namespace,
        pod_name=pod_name,
        pod_uid=pod["metadata"]["uid"],
        pod_ip=pod["status"]["podIP"],
        container_name=container_name,
        container_id=container_id,
        pid=pid,
        start_ticks=read_proc_start_ticks(pid),
    )
