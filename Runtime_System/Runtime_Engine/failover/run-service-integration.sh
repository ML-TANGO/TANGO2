#!/usr/bin/env bash

set -euo pipefail

evidence_dir=${1:-}
event_id=${2:-service-integration-001}
fault_mode=${3:-hang}
fence_timeout_ms=${4:-5}
exit_timeout_ms=${5:-100}
soak_seconds=${6:-1800}
health_confirm_timeout_ms=${7:-10}
health_final_timeout_ms=${8:-5}
reset_mode=${9:-full}
accept_kpi_failures=${ACCEPT_KPI_FAILURES:-0}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
namespace=tango2-tc2-service
kubeconfig=${KUBECONFIG:-/home/rtst/.kube/config}
node_name=${TC2_NODE_NAME:-mic711-rt}
node_ip=${TC2_NODE_IP:-10.2.58.155}
service_manifest=${TC2_SERVICE_MANIFEST:-${script_dir}/service.yaml}
created_namespace=0
owns_resources=0
cleanup_verified=0
namespace_creation_pending=0
pending_signal=0
pods=(tc2-service-active tc2-service-backup tc2-service-client)
timing_marks=()
timing_clock=proc_uptime

mark_phase()
{
    local now unused
    if [[ -r /proc/uptime ]]; then
        read -r now unused </proc/uptime
    else
        timing_clock=monotonic
        now=$(python3 -c 'import time; print(time.monotonic())')
    fi
    timing_marks+=("$1=${now}")
}

save_timing()
{
    python3 "${script_dir}/runner_timing.py" \
        "${evidence_dir}.staging/runner-timing.json" "${event_id}" \
        "${timing_clock}" "$1" "${timing_marks[@]}"
}

[[ -n ${evidence_dir} && ! -e ${evidence_dir} ]]
[[ ! -e ${evidence_dir}.staging ]]
[[ ${event_id} =~ ^[a-zA-Z0-9._-]+$ ]]
[[ ${fault_mode} == kill || ${fault_mode} == hang || ${fault_mode} == none ]]
[[ ${fence_timeout_ms} =~ ^[1-9][0-9]*$ ]]
[[ ${exit_timeout_ms} =~ ^[1-9][0-9]*$ ]]
[[ ${soak_seconds} =~ ^[1-9][0-9]*$ ]]
[[ ${health_confirm_timeout_ms} =~ ^[1-9][0-9]*$ ]]
[[ ${health_final_timeout_ms} =~ ^[1-9][0-9]*$ ]]
[[ ${reset_mode} == full || ${reset_mode} == pods ]]
[[ ${accept_kpi_failures} == 0 || ${accept_kpi_failures} == 1 ]]
[[ -r ${kubeconfig} ]]
mark_phase start

cleanup_reused_resources()
{
    local rc=0
    kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" delete \
        endpointslice tc2-service-manual --ignore-not-found=true \
        --wait=true --timeout=30s >/dev/null 2>&1 || rc=$?
    mark_phase endpointslice_cleanup
    kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" delete pod \
        "${pods[@]}" --ignore-not-found=true --wait=true \
        --grace-period=1 --timeout=30s >/dev/null 2>&1 || rc=$?
    mark_phase pod_cleanup
    return "${rc}"
}

cleanup()
{
    local rc=$?
    trap - EXIT INT TERM

    if ((owns_resources == 1 && cleanup_verified == 0)); then
        sudo -n python3 "${script_dir}/service_chain.py" cleanup --node-ip "${node_ip}" \
            >/dev/null 2>&1 || true
        if ((created_namespace == 1)); then
            kubectl --kubeconfig "${kubeconfig}" delete namespace "${namespace}" \
                --wait=true --timeout=120s >/dev/null 2>&1 || true
        elif [[ ${reset_mode} == pods ]]; then
            cleanup_reused_resources || true
        fi
    fi
    if ((rc != 0)) && [[ -d ${evidence_dir}.staging ]]; then
        mark_phase failed_cleanup
        save_timing "${rc}" || true
    fi
    return "${rc}"
}

handle_signal()
{
    local status=$1
    if ((namespace_creation_pending == 1)); then
        pending_signal=${status}
        return
    fi
    exit "${status}"
}

trap cleanup EXIT
trap 'handle_signal 130' INT
trap 'handle_signal 143' TERM

if [[ ${reset_mode} == full ]]; then
    existing_namespace=$(kubectl --kubeconfig "${kubeconfig}" get \
        namespace "${namespace}" --ignore-not-found=true -o name)
    if [[ -n ${existing_namespace} ]]; then
        printf 'namespace %s already exists; refusing to reuse it\n' \
            "${namespace}" >&2
        exit 1
    fi
    namespace_creation_pending=1
    kubectl --kubeconfig "${kubeconfig}" create namespace "${namespace}" \
        >/dev/null
    created_namespace=1
    owns_resources=1
    namespace_creation_pending=0
    if ((pending_signal != 0)); then
        exit "${pending_signal}"
    fi
else
    kubectl --kubeconfig "${kubeconfig}" get namespace "${namespace}" \
        >/dev/null
    existing_pods=$(kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" \
        get pod -o name)
    if [[ -n ${existing_pods} ]]; then
        printf 'pods already exist in reusable namespace\n' >&2
        exit 1
    fi
    existing_slice=$(kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" \
        get endpointslice tc2-service-manual --ignore-not-found=true -o name)
    if [[ -n ${existing_slice} ]]; then
        printf 'target EndpointSlice already exists in reusable namespace\n' >&2
        exit 1
    fi
    owns_resources=1
fi
mark_phase namespace_precheck
install -d -m 0755 "${evidence_dir}.staging"

python3 "${script_dir}/prepare_service_configmaps.py" \
    --kubeconfig "${kubeconfig}" --namespace "${namespace}"
mark_phase configmaps
kubectl --kubeconfig "${kubeconfig}" apply -f "${service_manifest}" \
    >/dev/null
mark_phase pod_apply
kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" wait \
    --for=condition=Ready pod/tc2-service-active \
    pod/tc2-service-backup pod/tc2-service-client --timeout=120s >/dev/null
mark_phase pod_ready

{
    date -u +%Y-%m-%dT%H:%M:%SZ
    uname -a
    sudo -n nvpmodel -q --verbose
    cat /sys/kernel/sched_ext/state
    kubectl --kubeconfig "${kubeconfig}" get node "${node_name}" -o wide
    kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" get all -o wide
    sudo -n iptables --version
    sudo -n crictl --version
} >"${evidence_dir}.staging/platform.txt" 2>&1

cp "${script_dir}"/*.py "${script_dir}"/*.yaml \
    "${script_dir}"/run-*.sh "${evidence_dir}.staging/"
mark_phase platform_snapshot
controller_args=(
    "${script_dir}/service_controller.py"
    --node-name "${node_name}"
    --node-ip "${node_ip}"
    --event-id "${event_id}"
    --fault-mode "${fault_mode}"
    --fence-timeout-ms "${fence_timeout_ms}"
    --exit-timeout-ms "${exit_timeout_ms}"
    --health-confirm-timeout-ms "${health_confirm_timeout_ms}"
    --health-final-timeout-ms "${health_final_timeout_ms}"
    --soak-seconds "${soak_seconds}"
    --kubeconfig "${kubeconfig}"
    --evidence-dir "${evidence_dir}.staging/event"
)
if [[ ${accept_kpi_failures} == 1 ]]; then
    controller_args+=(--accept-kpi-failure)
fi
controller_env=("KUBECONFIG=${kubeconfig}")
if [[ -n ${TANGO2_STEP_CONTROL:-} ]]; then
    # sudo may reset the caller's environment. Forward only the explicit
    # manual-step protocol namespace, including its session identity fields.
    for name in "${!TANGO2_STEP_@}"; do
        controller_env+=("${name}=${!name}")
    done
fi
sudo -n env "${controller_env[@]}" python3 "${controller_args[@]}"
mark_phase controller

kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" get all -o wide \
    >"${evidence_dir}.staging/resources.after.txt"
kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" get endpointslice \
    -o yaml >"${evidence_dir}.staging/endpointslice.after.yaml"
sudo -n iptables -t nat -S >"${evidence_dir}.staging/iptables.after.txt"
mark_phase postcheck
sudo -n python3 "${script_dir}/service_chain.py" cleanup --node-ip "${node_ip}"
mark_phase chain_cleanup
if [[ ${reset_mode} == full ]]; then
    kubectl --kubeconfig "${kubeconfig}" delete namespace "${namespace}" \
        --wait=true --timeout=120s >/dev/null
    mark_phase namespace_cleanup
    {
        remaining_namespace=$(kubectl --kubeconfig "${kubeconfig}" get \
            namespace "${namespace}" --ignore-not-found=true -o name)
        if [[ -n ${remaining_namespace} ]]; then
            printf 'namespace_cleanup=FAIL\n'
            exit 1
        fi
        nat_rules=$(sudo -n iptables -t nat -S)
        if [[ ${nat_rules} == *TANGO2-TC2-SVC* ]]; then
            printf 'chain_cleanup=FAIL\n'
            exit 1
        fi
        printf 'namespace_cleanup=PASS\nchain_cleanup=PASS\n'
    } >"${evidence_dir}.staging/cleanup.verified.txt"
else
    cleanup_reused_resources
    {
        kubectl --kubeconfig "${kubeconfig}" get namespace "${namespace}" \
            >/dev/null
        printf 'namespace_reuse=PASS\n'
        remaining_pods=$(kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" \
            get pod -o name)
        if [[ -n ${remaining_pods} ]]; then
            printf 'pod_cleanup=FAIL\n'
            exit 1
        fi
        printf 'pod_cleanup=PASS\n'
        remaining_slice=$(kubectl --kubeconfig "${kubeconfig}" -n "${namespace}" \
            get endpointslice tc2-service-manual --ignore-not-found=true -o name)
        if [[ -n ${remaining_slice} ]]; then
            printf 'endpointslice_cleanup=FAIL\n'
            exit 1
        fi
        printf 'endpointslice_cleanup=PASS\n'
        nat_rules=$(sudo -n iptables -t nat -S)
        if [[ ${nat_rules} == *TANGO2-TC2-SVC* ]]; then
            printf 'chain_cleanup=FAIL\n'
            exit 1
        fi
        printf 'chain_cleanup=PASS\n'
    } >"${evidence_dir}.staging/cleanup.verified.txt"
fi
created_namespace=0
cleanup_verified=1
mark_phase cleanup_verification
save_timing 0
mv "${evidence_dir}.staging" "${evidence_dir}"
(
    cd "${evidence_dir}"
    find . -type f ! -name artifacts.sha256 -print0 |
        LC_ALL=C sort -z | xargs -0 sha256sum >artifacts.sha256
)
printf 'SERVICE_INTEGRATION_COMPLETE evidence=%s\n' "${evidence_dir}"
