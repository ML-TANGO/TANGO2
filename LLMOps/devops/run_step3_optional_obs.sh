#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./run_step3_optional_obs.sh [--prometheus] [--gpu] [--efk] [--efk-init]

Options:
  --prometheus  Install Prometheus stack
  --gpu         Install GPU operators
  --efk         Install EFK (Elastic + Fluent)
  --efk-init    Run Elastic init + Fluent after Elastic is ready
  -h, --help    Show this help

Notes:
  --efk-init should be used only after Elastic pods are Running.
  - Run this script from the devops directory.
EOF
}

INSTALL_PROM="false"
INSTALL_GPU="false"
INSTALL_EFK="false"
RUN_EFK_INIT="false"

if [[ ! -f "./gaip_prometheus/run.sh" ]]; then
  echo "ERROR: run from GenAI_Platform/devops directory." >&2
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prometheus)
      INSTALL_PROM="true"
      shift 1
      ;;
    --gpu)
      INSTALL_GPU="true"
      shift 1
      ;;
    --efk)
      INSTALL_EFK="true"
      shift 1
      ;;
    --efk-init)
      RUN_EFK_INIT="true"
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

if [[ "$INSTALL_PROM" == "true" ]]; then
  echo "[STEP3] Prometheus install"
  (
    cd "./gaip_prometheus"
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    ./run.sh install
  )
fi

if [[ "$INSTALL_GPU" == "true" ]]; then
  echo "[STEP3] GPU Operators install"
  (
    cd "./gaip_gpu_operators"
    ./run.sh
  )
fi

if [[ "$INSTALL_EFK" == "true" ]]; then
  echo "[STEP3] EFK install"
  (
    cd "./gaip_efk"
    ./helm_repo_add.sh
    ./helm_upgrade_elastic.sh

    if [[ "$RUN_EFK_INIT" == "true" ]]; then
      echo "[STEP3] EFK init and Fluent install"
      ./elastic_init.sh
      ./helm_upgrade_fluent.sh
    else
      echo "[STEP3] Elastic install done. Run with --efk-init after pods are Running."
    fi
  )
fi
