"""External container helm-install trigger.

Forks the `apps/fb_scheduler/src/scheduler/llm_run.py` pattern
(`create_fine_tuning_pod`) for partner-supplied images that conform to
examples/hello-plugin/external-container-spec.md (SP-1 v2).

Why a values file instead of `--set` flags:
SP-Ext review (2026-05-19, codex CRITICAL #C1) flagged that building
`helm install ... --set env.{key}={val}` from partner-controlled dict
keys allows Helm strvals injection — a malicious manifest could splice
in extra `--set securityContext.runAsUser=0` via a comma in a key.
Dumping ExternalPodInfo as a YAML values file and passing it with
`-f` eliminates the entire class: every value lands in a pre-parsed
nested map, never on the shell command line.

Companion uninstall lives in `helm_run.py` as `delete_helm_external`.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from typing import Optional, Tuple

import yaml

from utils import redis_key as _redis_key
from scheduler.dto import Accelerator, ExternalPodInfo, Node

logger = logging.getLogger(__name__)

# SP-3 보안 하드닝(K8s Secret) — secret 값을 helm values(→PodSpec/Helm history 평문)가
# 아니라 helm 밖 K8s Secret 객체로 만들고 pod.yaml 은 valueFrom.secretKeyRef 로 참조.
# CoreV1Api 는 lazy 초기화(모듈 import 시 kube-config 부재로 죽지 않게).
_corev1 = None


def _get_corev1():
    global _corev1
    if _corev1 is None:
        from kubernetes import config, client
        from utils import settings
        config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
        _corev1 = client.CoreV1Api()
    return _corev1


def _external_secret_name(helm_release: str) -> str:
    # helm_release 는 이미 RFC1123 — Secret 이름으로 그대로 안전.
    return f"{helm_release}-secrets"


def _ensure_external_secret(pod_info: ExternalPodInfo) -> Optional[str]:
    """secret 값을 담은 K8s Secret 을 helm 밖에서 생성(있을 때만). 값은 PodSpec /
    Helm release manifest 에 들어가지 않고 Secret 객체(etcd, RBAC)에만 존재한다.
    helm install 전에 호출 — pod 가 valueFrom.secretKeyRef 로 마운트할 때 존재해야 함.
    반환: Secret 이름(생성 시) 또는 None(secret 없음 → dormant 경로 무변화)."""
    secrets = dict(pod_info.secrets or {})
    if not secrets:
        return None
    from kubernetes import client as k8s
    from kubernetes.client.rest import ApiException
    name = _external_secret_name(pod_info.helm_release)
    api = _get_corev1()
    body = k8s.V1Secret(
        metadata=k8s.V1ObjectMeta(
            name=name,
            labels={"app": "external-container", "helm-release": pod_info.helm_release},
        ),
        string_data={k: str(v) for k, v in secrets.items()},
        type="Opaque",
    )
    try:
        api.create_namespaced_secret(namespace=pod_info.namespace, body=body)
    except ApiException as e:
        if e.status == 409:  # 재launch idempotency — 기존 값 교체
            api.replace_namespaced_secret(name=name, namespace=pod_info.namespace, body=body)
        else:
            raise
    return name


def _delete_external_secret(helm_release: str, namespace: str) -> None:
    """uninstall 시 secret Secret 정리(best-effort, 없으면 무시)."""
    from kubernetes.client.rest import ApiException
    name = _external_secret_name(helm_release)
    try:
        _get_corev1().delete_namespaced_secret(name=name, namespace=namespace)
    except ApiException as e:
        if e.status != 404:
            logger.warning("failed to delete external secret %s in %s: %s", name, namespace, e)
    except Exception as e:
        logger.warning("error deleting external secret %s: %s", name, e)

# Where the chart lives inside the fb_scheduler image. fb_scheduler runs in
# /app and bundles all helm charts under /app/helm_chart/<chart_name>/. This
# matches `llm_run.create_fine_tuning_pod` and `helm_run.create_project_tool_pod`.
_HELM_CHART_ROOT = "/app/helm_chart"
_HELM_CHART_NAME = "external_container"

# Keys whose values we never print at INFO/DEBUG. Any logging of the helm
# command itself goes through `_redact_command_for_log` to keep secrets out
# of kubectl-visible stderr (SP-Ext review MEDIUM #C5).
_SENSITIVE_TOP_LEVEL_KEYS: frozenset[str] = frozenset({"secrets", "env", "env_overrides", "jf_env"})

# SP-Ext.4 C1: GPU pre-allocation reservation.
# 내부 학습은 fb_scheduler 의 Kafka consumer 가 lock+queue 로 직렬화 + live-pod
# gpu_ids scan 으로 중복 할당을 막지만, external 의 /external/launch 는 sync
# FastAPI handler 라 threadpool 에서 동시 실행돼 그 보호가 없다. nvidia.com/gpu
# 도 제거돼 device-plugin 의 admission 중복방지도 없다 → 두 launch 가 같은
# "free" GPU(monitoring 이 아직 used_info 갱신 전인 stale snapshot)를 잡으면
# double-book → CUDA OOM. per-GPU SETNX 예약 키로 원자적 claim 하여 직렬화한다
# (SETNX 자체가 atomic → 별도 분산 lock 불필요). TTL 은 helm install + 대용량
# image pull + 컨테이너 Running(= monitoring 이 used_info 기록) 까지 커버.
# 예약 키 포맷의 정본은 utils.redis_key.GPU_RESERVE_KEY 다 — 쓰는 쪽(여기)과
# 읽는 쪽(fb_resource 가용량 조회)이 갈리면 예약이 통째로 안 보인다. 지역 별칭만 둔다.
_GPU_RESERVE_KEY = _redis_key.GPU_RESERVE_KEY
_GPU_RESERVE_BY_RELEASE_KEY = "resource:gpu:reserved:by_release:{release}"
_GPU_RESERVE_TTL = 900  # seconds


class GpuAllocationError(Exception):
    """GPU job 의 pre-allocation 실패 — launch 를 실패시켜 all-GPU 노출 방지."""


def _release_gpu_reservations(redis_client, uuids) -> None:
    """예약한 GPU reservation 키 해제. best-effort."""
    if not redis_client or not uuids:
        return
    for u in uuids:
        if not u:
            continue
        try:
            redis_client.delete(_GPU_RESERVE_KEY.format(uuid=u))
        except Exception:
            pass


def _release_claimed_reservations(pod_info: ExternalPodInfo) -> None:
    """pod_info 에 claim 된 GPU uuid 들의 reservation 해제 (helm 실패 시).
    redis_client 를 새로 잡아 best-effort 로 정리 — Redis 오류는 무시 (TTL
    이 결국 회수)."""
    uuids = [u for u in (pod_info.gpu_uuids or "").split(",") if u]
    if not uuids:
        return
    try:
        from utils.redis import get_redis_client
        _release_gpu_reservations(get_redis_client(), uuids)
    except Exception:
        pass


def release_reservations_for_release(helm_release: str) -> None:
    """helm release uninstall/cancel 시 그 release 가 claim 한 GPU reservation
    을 즉시 해제. 역인덱스 키 한 개만 GET 하므로 cluster SCAN 불필요.
    delete_helm_external 에서 호출. best-effort (실패해도 TTL 이 회수)."""
    if not helm_release:
        return
    try:
        from utils.redis import get_redis_client
        rc = get_redis_client()
        idx_key = _GPU_RESERVE_BY_RELEASE_KEY.format(release=helm_release)
        raw = rc.get(idx_key)
        if raw is None:
            return
        uuids = [u for u in (raw.decode() if isinstance(raw, bytes) else raw).split(",") if u]
        _release_gpu_reservations(rc, uuids)
        rc.delete(idx_key)
    except Exception:
        pass


def create_external_pod(pod_info: ExternalPodInfo) -> Tuple[bool, str]:
    """Run `helm install` for the external container described by pod_info.

    Returns:
        (True, stdout) on success or when the release name is already in use
        (idempotent re-launch). (False, stderr) on real failure.

    Side-effects:
        Writes a values YAML file (perm 600) under /tmp and removes it in
        the `finally` block. ConfigMap rendering happens inside helm during
        template expansion, so the file is only needed for the install call.
    """
    # fb_monitoring 의 GPU usage 추적이 chart 의 device labels (device_type/
    # device_count/device_ids) join 으로 동작. internal fine_tuning chart
    # 들은 fb_scheduler 의 helm_run.create_fine_tuning_pod 가 cluster[N].
    # device.{type,count,uuids,ids} 를 사전 채워 chart 에 전달하는 패턴.
    # external 도 동일 패턴으로 통일 — cluster 가 비어있고 GPU 요청이 있으면
    # Redis GPU pool 에서 free GPU 를 SETNX 로 원자적 claim + node_db uuid→id.
    # SP-Ext.4 C1: GPU job 할당 실패는 launch 실패로 처리 (all-GPU 노출 방지).
    try:
        _ensure_gpu_allocation(pod_info)
    except GpuAllocationError as e:
        logger.error("external GPU allocation failed for %s: %s",
                     pod_info.helm_release, e)
        return False, f"GPU allocation failed: {e}"

    # SP-Ext.4 instance graph fix: BFF 가 instance_id 를 안 넘긴 경우
    # (CLI/programmatic launch) workspace 의 instance 로 fallback 해석 →
    # fb_dashboard instance 그래프에 external 학습이 잡히도록.
    _ensure_instance_label(pod_info)

    # SP-Ext.4 resource-bundle 정렬: 플랫폼은 GPU instance 를 "GPU 1개당
    # vCPU/vRAM 고정 번들" 로 가상화한다. internal 학습/배포는 instance 정의에서
    # cpu/ram 을 파생하지만 external 은 manifest spec.resources 의 임의값(예:
    # 1 GPU 에 16 vCPU/59Gi)을 써서 번들 비례가 깨졌다. 여기서 instance 의
    # cpu_allocate/ram_allocate × (gpu_count/gpu_allocate) 로 override 해
    # internal 과 동일한 번들 회계로 통일한다.
    _apply_instance_resource_bundle(pod_info)

    # SP-3 보안: secret 값을 helm 밖 K8s Secret 으로 먼저 만든다(있을 때만). values
    # 파일엔 ref 이름/키만 들어가고 값은 안 들어간다 → PodSpec/Helm history 평문 노출 X.
    try:
        _ensure_external_secret(pod_info)
    except Exception as e:
        logger.error("external secret creation failed for %s: %s",
                     pod_info.helm_release, e)
        release_reservations_for_release(pod_info.helm_release)
        return False, f"secret provisioning failed: {e}"

    values_file = _write_values_file(pod_info)
    command: list[str] = []
    try:
        os.chdir(_HELM_CHART_ROOT)
        command = [
            "helm", "install",
            pod_info.helm_release,
            f"{_HELM_CHART_NAME}/",
            "-n", pod_info.namespace,
            "-f", values_file,
        ]
        logger.info(
            "helm install %s -n %s -f <values redacted, %d keys>",
            pod_info.helm_release, pod_info.namespace,
            len(pod_info.model_dump(exclude={"secrets", "env", "env_overrides", "jf_env"})),
        )
        result = subprocess.run(
            command,
            shell=False,                      # no shell — argv list only
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,                      # SP-Ext Phase 2: helm install 상한(--wait 없어 보통 수초).
        )
        return True, result.stdout
    except subprocess.TimeoutExpired:
        # SP-Ext Phase 2: helm install 이 300s 초과(API 서버 지연 등). 무한 블로킹으로
        # 이벤트루프/health 를 막지 않도록 실패 처리. SIGKILL 된 install 은 pending-install
        # release(+partial Pod/GPU)를 남길 수 있고, launch 실패 경로엔 poll loop
        # (_cleanup→uninstall)이 없으므로 여기서 best-effort uninstall 로 직접 회수한다
        # (release 명은 job 별 unique → 오삭제 없음). 이어서 CalledProcessError 경로와
        # 동일하게 GPU reservation + secret 정리. (helm_run 은 순환회피 위해 함수레벨 import)
        try:
            from scheduler.helm_run import delete_helm_external
            delete_helm_external(pod_info.helm_release, pod_info.namespace)
        except Exception:
            logger.warning(
                "best-effort uninstall after install timeout failed for %s",
                pod_info.helm_release,
            )
        release_reservations_for_release(pod_info.helm_release)
        _delete_external_secret(pod_info.helm_release, pod_info.namespace)
        logger.error(
            "helm install timed out (>300s) for %s in %s",
            pod_info.helm_release, pod_info.namespace,
        )
        return False, "helm install timed out (>300s)"
    except subprocess.CalledProcessError as e:
        err_msg = (e.stderr or "").strip()
        # Idempotency: a duplicate release name means a prior launch already
        # placed the pod. Same convention as create_fine_tuning_pod.
        if "cannot re-use a name that is still in use" in err_msg:
            return True, ""
        # SP-Ext.4 C1: helm install 진짜 실패 → pod 안 떴으니 claim 한 GPU
        # reservation 즉시 해제 (TTL 900s 안 기다리고 회수). idempotent 재launch
        # (위) 는 기존 pod 가 GPU 쓰므로 해제 안 함. 역인덱스 기반 통일 경로.
        release_reservations_for_release(pod_info.helm_release)
        # SP-3: install 실패 → 방금 만든 secret Secret 도 정리(orphan 방지).
        _delete_external_secret(pod_info.helm_release, pod_info.namespace)
        # Log without secrets — the values file path goes to the log; the
        # contents do not. tempfile perms are 0600 so on-disk inspection is
        # limited to the scheduler container's own UID.
        logger.error(
            "helm install failed for %s in %s: %s",
            pod_info.helm_release, pod_info.namespace, err_msg,
        )
        return False, err_msg
    finally:
        if values_file and os.path.exists(values_file):
            try:
                os.remove(values_file)
            except OSError as cleanup_exc:
                logger.warning(
                    "failed to remove helm values tempfile %s: %s",
                    values_file, cleanup_exc,
                )


# ── Helpers ──────────────────────────────────────────────────────────────


def _ensure_instance_label(pod_info: ExternalPodInfo) -> None:
    """Resolve ``pod_info.labels['instance_id']`` from the workspace when the
    caller (BFF) did not supply it.

    fb_dashboard 의 get_workspace_instance_used 는 fine_tuning pod 를
    ``instance_status[int(label_instance_id)]`` 로 attribute 한다. external
    학습이 instance 그래프에 잡히려면 pod 에 실 instance_id 라벨이 필요.

    - 이미 set 되어 있으면 (UI FINETUNING 모달이 보낸 값) 그대로 둔다.
    - workspace 가 단일 instance 면 그것으로 attribute (협력기관 demo 의 일반).
    - multi-instance 면 allocated node 로 매칭 시도, 모호하면 비워둔다
      (잘못된 instance 에 귀속시키지 않음 — 그래프 정확성 우선).
    실패는 non-fatal: 라벨 없으면 dashboard 가 그 pod 만 instance graph 에서
    제외 (workspace resource bar 는 여전히 정확).
    """
    labels = pod_info.labels or {}
    if labels.get("instance_id"):
        return

    workspace_id = labels.get("workspace_id")
    if not workspace_id:
        return

    try:
        from utils.msa_db import db_node, db_workspace
    except Exception as exc:
        logger.warning("external instance-label resolution skipped (import): %s", exc)
        return

    try:
        ws_instances = db_workspace.get_workspace_instance_list(workspace_id) or []
    except Exception as exc:
        logger.warning("external instance-label resolution skipped (db): %s", exc)
        return

    if not ws_instances:
        return

    resolved: str = ""
    if len(ws_instances) == 1:
        resolved = str(ws_instances[0]["instance_id"])
    elif pod_info.node_name:
        # multi-instance workspace: chosen node 가 속한 instance 중 이 workspace
        # 의 것과 교집합. node_instance join 으로 후보를 좁힌다.
        try:
            node_row = db_node.get_node(node_name=pod_info.node_name)
            ws_instance_ids = {int(wi["instance_id"]) for wi in ws_instances}
            if node_row:
                node_instances = db_node.get_node_instance_list(node_id=node_row["id"]) or []
                matched = {
                    int(ni["instance_id"])
                    for ni in node_instances
                    if int(ni["instance_id"]) in ws_instance_ids
                }
                if len(matched) == 1:
                    resolved = str(next(iter(matched)))
        except Exception:
            resolved = ""

    if resolved:
        pod_info.labels["instance_id"] = resolved
        logger.info(
            "external instance-label: %s -> instance_id=%s",
            pod_info.helm_release, resolved,
        )


def _apply_instance_resource_bundle(pod_info: ExternalPodInfo) -> None:
    """external 의 cpu/memory 를 선택된 GPU instance 번들에서 파생 (Option B).

    플랫폼의 GPU 가상화: instance = (gpu_allocate, cpu_allocate, ram_allocate)
    고정 번들. units = gpu_count / gpu_allocate 만큼 번들을 곱해 cpu/memory 를
    정한다 — manifest spec.resources 의 cpu/memory 는 무시 (gpu / gpu_memory 는
    유지). internal 의 _resources.tpl 과 동일하게 kubelet/system 용 0.1 margin
    을 빼서 quota 경계에서 admission 실패를 막는다.

    instance_id 미해석(multi-instance 모호 등) 또는 GPU job 아님 / instance 조회
    실패 시 manifest 값 유지 (non-fatal — 번들 회계만 약화).
    """
    labels = pod_info.labels or {}
    instance_id = labels.get("instance_id")
    if not instance_id:
        logger.warning(
            "external resource-bundle skipped (%s): instance_id 미해석 — "
            "manifest cpu/memory 유지", pod_info.helm_release,
        )
        return
    gpu_count = int(pod_info.resources.gpu or 0)
    if gpu_count <= 0:
        return
    try:
        from utils.msa_db import db_node
        inst = db_node.get_instance(int(instance_id))
    except Exception as exc:
        logger.warning(
            "external resource-bundle skipped (%s): instance %s 조회 실패: %s",
            pod_info.helm_release, instance_id, exc,
        )
        return
    if not inst:
        return
    try:
        gpu_alloc = float(inst.get("gpu_allocate") or 1) or 1.0
        cpu_alloc = float(inst.get("cpu_allocate") or 0)
        ram_alloc = float(inst.get("ram_allocate") or 0)
    except (TypeError, ValueError):
        return
    if cpu_alloc <= 0 or ram_alloc <= 0:
        return

    units = gpu_count / gpu_alloc
    # internal _resources.tpl 과 동일한 0.1 margin (kubelet/system 예약).
    cpu_val = round(cpu_alloc * units - 0.1, 2)
    ram_val = round(ram_alloc * units - 0.1, 2)
    prev_cpu, prev_mem = pod_info.resources.cpu, pod_info.resources.memory
    pod_info.resources.cpu = str(cpu_val)
    pod_info.resources.memory = f"{ram_val}G"
    logger.info(
        "external resource-bundle: %s instance=%s units=%.2f → cpu %s→%s, "
        "memory %s→%s (manifest 값 무시, 번들 파생)",
        pod_info.helm_release, instance_id, units,
        prev_cpu, pod_info.resources.cpu, prev_mem, pod_info.resources.memory,
    )


def _ensure_gpu_allocation(pod_info: ExternalPodInfo) -> None:
    """Populate ``pod_info.cluster`` + ``gpu_uuids`` + ``node_name`` from
    Redis ``resource:gpu_info`` if the caller (BFF) did not pre-allocate.

    Mirrors the internal fine_tuning allocation flow:
        fb_scheduler/helm_run.create_fine_tuning_pod
        → fb_scheduler/scheduler.get_available_gpus_by_model
        → Node(Accelerator(uuids=..., ids=...))
        → helm chart label `device_ids` injection
        → fb_monitoring `update_pod_gpu_usage_from_labels` + `insert_gpu_usage`

    Failure modes are non-fatal — if Redis is unreachable or the node_db
    UUID lookup misses, we leave ``cluster`` empty and fall back to K8s
    ``nvidia-device-plugin`` auto-allocation. Monitoring will then show
    ``used=0`` for that GPU but the workload still runs.
    """
    if pod_info.cluster:
        # Caller (BFF / test) already filled in a cluster spec. Trust it.
        return

    # SP-Ext.4 review M2: caller (admin / test harness) 가 node_name 을 직접
    # 박아 온 경우엔 cluster auto-fill 을 skip. 우리가 chosen_node 를 override
    # 하면 placement 의도 무시. 진짜 의도는 BFF 가 cluster + node_name 둘 다
    # 채우거나 둘 다 비우는 것 — 빈 cluster + 채워진 node_name 은 admin 강제
    # 배치이므로 K8s device-plugin 자동 할당에 위임.
    if pod_info.node_name:
        logger.info(
            "external GPU pre-allocation: caller pinned node_name=%s, "
            "skipping Redis-based allocation (K8s nvidia-device-plugin auto)",
            pod_info.node_name,
        )
        return

    gpu_count = int(pod_info.resources.gpu or 0)
    if gpu_count <= 0:
        # CPU-only workload — nothing to allocate.
        return

    # SP-Ext.4 C1: GPU job 은 pre-allocation 이 성공해야만 NVIDIA_VISIBLE_DEVICES
    # 가 박혀 단일 GPU 로 격리된다. 실패 시(예전엔 silent return) cluster 가
    # 비어 → chart 가 NVIDIA_VISIBLE_DEVICES 미렌더 → nvidia 런타임이 노드의
    # 모든 GPU 를 노출 → 다른 작업과 충돌. 따라서 GPU job 의 모든 실패 경로는
    # GpuAllocationError 로 launch 자체를 실패시킨다 (all-GPU 노출 방지).
    try:
        # Local imports — these pull in DB / Redis clients that are heavy
        # at module load and only needed when actually allocating.
        from utils import redis_key
        from utils.msa_db import db_node
        from utils.redis import get_redis_client
    except Exception as exc:
        raise GpuAllocationError(
            f"{pod_info.helm_release}: utils import failed for GPU "
            f"pre-allocation: {exc}"
        )

    try:
        redis_client = get_redis_client()
        raw = redis_client.get(redis_key.GPU_INFO_RESOURCE)
        if not raw:
            raise GpuAllocationError(
                f"{pod_info.helm_release}: redis key "
                f"{redis_key.GPU_INFO_RESOURCE} missing — node_init not run?"
            )
        gpu_info: dict = json.loads(raw)
    except GpuAllocationError:
        raise
    except Exception as exc:
        raise GpuAllocationError(
            f"{pod_info.helm_release}: redis read failed for GPU "
            f"pre-allocation: {exc}"
        )

    # Bucket free GPUs per node so we can grab a contiguous block — single
    # node placement is the default for partner containers (no multi-node
    # collective comms unless they bring their own launcher).
    by_node: dict[str, list[str]] = defaultdict(list)
    for node_name, gpus in (gpu_info or {}).items():
        if not isinstance(gpus, dict):
            continue
        for gpu_uuid, gpu in gpus.items():
            if not isinstance(gpu, dict):
                continue
            # ``used_info`` empty == free GPU (same predicate the internal
            # scheduler.get_available_gpus_by_model uses).
            if not gpu.get("used_info"):
                by_node[node_name].append(gpu_uuid)

    # SP-Ext.4 C1: 노드별로 gpu_count 개를 SETNX 로 원자적 claim. claim 과
    # 동시에 uuid→platform id 매핑 (매핑 실패 GPU 는 claim 안 함). 한 노드에서
    # gpu_count 를 못 채우면 부분 claim 해제 후 다음 노드. 어느 노드도 못
    # 채우면 GpuAllocationError → launch 실패 (all-GPU 노출보다 안전).
    chosen_node: str = ""
    chosen_uuids: list[str] = []
    gpu_ids: list[str] = []
    for node_name, uuids in by_node.items():
        if len(uuids) < gpu_count:
            continue
        claimed: list[str] = []
        claimed_ids: list[str] = []
        for gpu_uuid in uuids:
            # uuid → platform integer id 먼저 (매핑 실패 GPU 는 skip — 라벨/
            # NVIDIA_VISIBLE_DEVICES 와 device_ids 정합 유지, Codex #3).
            try:
                gid = str(db_node.get_node_gpu(gpu_uuid=gpu_uuid)["id"])
            except Exception:
                continue
            # 원자적 claim — 이미 다른 launch 가 잡았으면 nx 실패 → skip.
            try:
                ok = redis_client.set(
                    _GPU_RESERVE_KEY.format(uuid=gpu_uuid),
                    pod_info.helm_release, nx=True, ex=_GPU_RESERVE_TTL,
                )
            except Exception:
                # Redis reserve 오류 — fail-open 으로 claim 간주 (best-effort;
                # 적어도 매핑된 GPU 라 정합은 유지). 동시성 보호만 약화.
                ok = True
            if not ok:
                continue
            claimed.append(gpu_uuid)
            claimed_ids.append(gid)
            if len(claimed) == gpu_count:
                break
        if len(claimed) == gpu_count:
            chosen_node, chosen_uuids, gpu_ids = node_name, claimed, claimed_ids
            break
        # 부분 claim → 해제 후 다음 노드 시도
        _release_gpu_reservations(redis_client, claimed)

    if not chosen_node:
        # 진단 문구는 **예약키까지 반영한** 스냅샷으로 쓴다. used_info 만 세면
        # external 잡이 claim 중인 GPU 가 free 로 잡혀 "free 2 인데 1장 실패" 라는
        # 모순된 메시지가 나온다(실측). 스냅샷 실패는 진단을 막지 않는다.
        try:
            from utils import gpu_pool
            snap = gpu_pool.snapshot(redis_client)
            detail = (f"total={snap['total']} in_use={snap['in_use']} "
                      f"reserved={snap['reserved']} free={snap['free']}")
        except Exception as exc:
            detail = f"pool snapshot unavailable: {exc}"
        raise GpuAllocationError(
            f"{pod_info.helm_release}: no single node could atomically claim "
            f"{gpu_count} free GPU(s) ({detail})"
        )

    matched_uuids = chosen_uuids

    # SP-Ext.4 C1: helm_release → claimed uuids 역인덱스. uninstall/cancel 시
    # cluster-wide SCAN 없이 이 키만 읽어 reservation 을 즉시 해제 (TTL 900s
    # 대기 회피). 순차 launch 가 GPU 수보다 많을 때 앞 작업의 미해제 예약이
    # SETNX 를 막던 문제 해소.
    try:
        redis_client.set(
            _GPU_RESERVE_BY_RELEASE_KEY.format(release=pod_info.helm_release),
            ",".join(matched_uuids), ex=_GPU_RESERVE_TTL,
        )
    except Exception:
        pass

    # Determine accelerator model name from the first matched row, if the
    # Redis snapshot carried it. Best-effort label only — chart does not
    # branch on it.
    first_node_gpus = gpu_info.get(chosen_node) or {}
    first_meta = first_node_gpus.get(matched_uuids[0]) or {}
    # SP-Ext.4 fix: K8s label values must match regex
    # `[A-Za-z0-9][-A-Za-z0-9_.]*[A-Za-z0-9]`. nvidia-smi reports
    # "NVIDIA RTX A6000" (spaces!) so we mirror internal scheduler.py:748
    # which replaces spaces with underscores before passing through to the
    # chart. Without this, helm install fails with K8s label validation.
    model_name = (first_meta.get("model_name") or "").strip().replace(" ", "_")

    pod_info.cluster = [
        Node(
            node_name=chosen_node,
            device=Accelerator(
                device_type="GPU",
                model=model_name,
                uuids=",".join(matched_uuids),
                ids=".".join(gpu_ids),
                count=len(matched_uuids),
            ),
        )
    ]
    # Pin the pod to the node we just allocated GPUs on. Without this the
    # K8s scheduler could place the pod on a different node and the
    # NVIDIA_VISIBLE_DEVICES we set below would point at GPUs the pod
    # never sees. ExternalPodInfo.node_name already feeds the chart's
    # spec.nodeName so the BFF override path keeps working.
    pod_info.node_name = chosen_node
    # NVIDIA_VISIBLE_DEVICES — letting K8s auto-pick would hand us a
    # different uuid than the ones we just claimed in the cluster spec.
    pod_info.gpu_uuids = ",".join(matched_uuids)
    logger.info(
        "external GPU pre-allocation: %s -> %d GPU(s) on %s (ids=%s)",
        pod_info.helm_release, len(matched_uuids), chosen_node,
        ".".join(gpu_ids),
    )


def _write_values_file(pod_info: ExternalPodInfo) -> str:
    """Persist ExternalPodInfo to a tmp YAML for `helm install -f`.

    Validating params_json here surfaces partner-side `/input/params.json`
    typos at helm-install time rather than once the container starts and
    crashes mid-read.

    `tempfile.mkstemp` defaults to mode 0600, which is what we want for
    a file that may carry partner-supplied secret env values.
    """
    data = _model_dump(pod_info)

    # SP-3 보안: secret 값은 values 파일/Helm release 에 절대 넣지 않는다. 값은 helm
    # 밖 K8s Secret(_ensure_external_secret)에 있고, pod.yaml 은 이름+키로
    # valueFrom.secretKeyRef 를 렌더한다. → 값 map 제거, ref 이름/키만 남김.
    secret_vals = data.pop("secrets", None) or {}
    if secret_vals:
        data["secret_ref_name"] = _external_secret_name(pod_info.helm_release)
        data["secret_keys"] = sorted(secret_vals.keys())
    else:
        data["secret_ref_name"] = ""
        data["secret_keys"] = []

    raw_params = (data.get("inputs") or {}).get("params_json") or "{}"
    try:
        json.loads(raw_params)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"inputs.params_json is not valid JSON for helm release "
            f"{pod_info.helm_release}: {exc}"
        ) from exc

    fd, path = tempfile.mkstemp(
        prefix=f"{pod_info.helm_release}-values-",
        suffix=".yaml",
    )
    with os.fdopen(fd, "w") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, default_flow_style=False)
    return path


def _model_dump(pod_info: ExternalPodInfo) -> dict:
    """Pydantic v2 model_dump with v1 fallback.

    fb_scheduler currently mixes v1 (`class Config`) and v2 (`ConfigDict`)
    syntax in dto.py; ExternalPodInfo is plain BaseModel so both `dict()`
    and `model_dump()` work. Prefer v2 to silence pydantic deprecation
    warnings (SP-Ext review HIGH #L3).
    """
    if hasattr(pod_info, "model_dump"):
        return pod_info.model_dump()
    return pod_info.dict()  # pydantic v1 fallback


def _redact_command_for_log(cmd: list[str]) -> str:
    """Render an argv command for logs, eliding the values file path."""
    parts: list[str] = []
    skip_next = False
    for token in cmd:
        if skip_next:
            parts.append("<values-file>")
            skip_next = False
            continue
        if token == "-f":
            parts.append(token)
            skip_next = True
            continue
        parts.append(token)
    return " ".join(parts)
