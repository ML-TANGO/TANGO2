#!/usr/bin/env bash

set -euo pipefail

usage()
{
    cat <<'EOF'
Usage:
  admit-pod.sh admit <namespace> <pod> [scheduler-bin]
  admit-pod.sh revoke-id <cgroup-id> [scheduler-bin]

The Pod must have an rtst.io/class label with one of:
normal, critical, background.
EOF
}

die()
{
    printf 'admit-pod: %s\n' "$*" >&2
    exit 1
}

cpu_list_contains()
{
    local list=$1
    local wanted=$2
    local entry
    local first
    local last
    local -a entries

    IFS=',' read -r -a entries <<< "${list}"
    for entry in "${entries[@]}"; do
        if [[ ${entry} == *-* ]]; then
            first=${entry%-*}
            last=${entry#*-}
            if ((wanted >= first && wanted <= last)); then
                return 0
            fi
        elif [[ ${entry} == "${wanted}" ]]; then
            return 0
        fi
    done
    return 1
}

require_usable_cpu()
{
    local class=$1
    local effective=$2
    local cpu
    local candidates

    if [[ ${class} == background ]]; then
        candidates='5 6 7'
    else
        candidates='0 1 2 3 5 6 7'
    fi
    for cpu in ${candidates}; do
        if cpu_list_contains "${effective}" "${cpu}"; then
            return
        fi
    done
    die "class ${class} has no usable CPU in cpuset ${effective}"
}

resolve_container()
{
    local namespace=$1
    local pod=$2
    local class=$3
    local container_id=$4
    local scheduler_bin=$5
    local pid
    local start_time
    local cgroup_relative
    local cgroup_path
    local cgroup_id
    local effective_cpus
    local ack

    [[ ${container_id} == containerd://* ]] ||
        die "unsupported container runtime identity: ${container_id}"
    container_id=${container_id#containerd://}

    pid=$(
        sudo -n crictl inspect \
            --output go-template \
            --template '{{.info.pid}}' \
            "${container_id}"
    )
    [[ ${pid} =~ ^[1-9][0-9]*$ && -r /proc/${pid}/stat ]] ||
        die "invalid runtime PID for ${container_id}: ${pid}"

    start_time=$(
        sed 's/^.*) //' "/proc/${pid}/stat" |
            awk '{print $20}'
    )
    [[ ${start_time} =~ ^[0-9]+$ ]] ||
        die "invalid process start time for PID ${pid}"

    cgroup_relative=$(cut -d: -f3 "/proc/${pid}/cgroup")
    [[ ${cgroup_relative} == /* ]] ||
        die "invalid cgroup path for PID ${pid}: ${cgroup_relative}"
    cgroup_path="/sys/fs/cgroup${cgroup_relative}"
    [[ -d ${cgroup_path} ]] ||
        die "missing host cgroup path: ${cgroup_path}"

    cgroup_id=$(stat -Lc '%i' "${cgroup_path}")
    effective_cpus=$(<"${cgroup_path}/cpuset.cpus.effective")
    require_usable_cpu "${class}" "${effective_cpus}"

    ack=$(sudo -n "${scheduler_bin}" set "${class}" "${cgroup_path}")
    [[ ${ack} == ACK\ op=set\ cgroup_id="${cgroup_id}"\ class="${class}"* ]] ||
        die "scheduler admission ACK mismatch: ${ack}"

    printf '%s pod_uid=%s container_id=%s pid=%s start_time=%s cpuset=%s\n' \
        "${ack}" "${pod_uid}" "${container_id}" "${pid}" \
        "${start_time}" "${effective_cpus}"
}

command=${1:-}
case "${command}" in
    admit)
        [[ $# -eq 3 || $# -eq 4 ]] || {
            usage >&2
            exit 2
        }
        namespace=$2
        pod=$3
        scheduler_bin=${4:-/home/rtst/tango2-k1/scx_rtst_orin-s1b}

        class=$(
            kubectl -n "${namespace}" get pod "${pod}" \
                -o jsonpath='{.metadata.labels.rtst\.io/class}'
        )
        case "${class}" in
            normal|critical|background)
                ;;
            *)
                die "Pod ${namespace}/${pod} has invalid rtst.io/class: ${class}"
                ;;
        esac
        pod_uid=$(
            kubectl -n "${namespace}" get pod "${pod}" \
                -o jsonpath='{.metadata.uid}'
        )
        node_name=$(
            kubectl -n "${namespace}" get pod "${pod}" \
                -o jsonpath='{.spec.nodeName}'
        )
        [[ ${node_name} == "$(hostname)" ]] ||
            die "Pod is assigned to ${node_name}, not local node $(hostname)"

        mapfile -t container_ids < <(
            kubectl -n "${namespace}" get pod "${pod}" \
                -o jsonpath='{range .status.containerStatuses[*]}{.containerID}{"\n"}{end}'
        )
        ((${#container_ids[@]} > 0)) ||
            die "Pod ${namespace}/${pod} has no running container identity"

        for container_id in "${container_ids[@]}"; do
            [[ -n ${container_id} ]] || continue
            resolve_container \
                "${namespace}" \
                "${pod}" \
                "${class}" \
                "${container_id}" \
                "${scheduler_bin}"
        done
        ;;
    revoke-id)
        [[ $# -eq 2 || $# -eq 3 ]] || {
            usage >&2
            exit 2
        }
        scheduler_bin=${3:-/home/rtst/tango2-k1/scx_rtst_orin-s1b}
        sudo -n "${scheduler_bin}" delete-id "$2"
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
