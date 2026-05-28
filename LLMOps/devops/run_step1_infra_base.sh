#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./run_step1_infra_base.sh [--system <values-system.yaml>] [--marker <values-marker.yaml>] [--efk <values-efk.yaml>] [--metallb]

Options:
  --system   NFS system values file (default: ./gaip_nfs_provisioner/values-system.yaml)
  --marker   NFS marker values file (optional)
  --efk      NFS EFK values file (optional)
  --metallb  Install MetalLB (optional)
  -h, --help Show this help

Notes:
  - Run this script from the devops directory.
  - Values paths should be relative to devops (e.g. ./gaip_nfs_provisioner/values-system.yaml).
EOF
}

SYSTEM_VALUES="./gaip_nfs_provisioner/values-system.yaml"
MARKER_VALUES=""
EFK_VALUES="./gaip_nfs_provisioner/values-efk.yaml"
INSTALL_METALLB="false"

if [[ ! -f "./gaip_nfs_provisioner/run.sh" ]]; then
  echo "ERROR: run from GenAI_Platform/devops directory." >&2
  exit 1
fi

child_path_from_devops() {
  local p="$1"
  p="${p#./}"
  echo "../$p"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --system)
      SYSTEM_VALUES="$2"
      shift 2
      ;;
    --marker)
      MARKER_VALUES="$2"
      shift 2
      ;;
    --efk)
      EFK_VALUES="$2"
      shift 2
      ;;
    --metallb)
      INSTALL_METALLB="true"
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$SYSTEM_VALUES" ]]; then
  echo "ERROR: values file not found: $SYSTEM_VALUES" >&2
  exit 1
fi

if [[ -n "$MARKER_VALUES" && ! -f "$MARKER_VALUES" ]]; then
  echo "ERROR: values file not found: $MARKER_VALUES" >&2
  exit 1
fi

if [[ -n "$EFK_VALUES" && ! -f "$EFK_VALUES" ]]; then
  echo "ERROR: values file not found: $EFK_VALUES" >&2
  exit 1
fi

echo "[STEP1] NFS Provisioner install"
(
  cd "./gaip_nfs_provisioner"
  ./run.sh install --values "$(child_path_from_devops "$SYSTEM_VALUES")"
)

if [[ -n "$MARKER_VALUES" ]]; then
  (
    cd "./gaip_nfs_provisioner"
    ./run.sh install --values "$(child_path_from_devops "$MARKER_VALUES")"
  )
fi

if [[ -n "$EFK_VALUES" ]]; then
  (
    cd "./gaip_nfs_provisioner"
    ./run.sh install --values "$(child_path_from_devops "$EFK_VALUES")"
  )
fi

if [[ "$INSTALL_METALLB" == "true" ]]; then
  echo "[STEP1] MetalLB install"
  (
    cd "./gaip_metallb"
    ./install.sh
  )
fi
