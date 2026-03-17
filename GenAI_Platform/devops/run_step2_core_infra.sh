#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./run_step2_core_infra.sh [--kong <values.yaml>] [--registry <values.yaml>] [--mariadb <values.yaml>]

Options:
  --kong      Kong values file (default: ./gaip_kong/values.yaml)
  --registry  Registry values file (default: ./gaip_registry/values.yaml)
  --mariadb   MariaDB init values file (default: ./gaip_maraidb/values.yaml)
  -h, --help  Show this help

Notes:
  - Run this script from the devops directory.
  - Values paths should be relative to devops (e.g. ./gaip_kong/values.yaml).
EOF
}

KONG_VALUES="./gaip_kong/values.yaml"
REGISTRY_VALUES="./gaip_registry/values.yaml"
MARIADB_VALUES="./gaip_maraidb/values.yaml"

if [[ ! -f "./gaip_kong/run.sh" ]]; then
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
    --kong)
      KONG_VALUES="$2"
      shift 2
      ;;
    --registry)
      REGISTRY_VALUES="$2"
      shift 2
      ;;
    --mariadb)
      MARIADB_VALUES="$2"
      shift 2
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

if [[ ! -f "$KONG_VALUES" ]]; then
  echo "ERROR: values file not found: $KONG_VALUES" >&2
  exit 1
fi

if [[ ! -f "$REGISTRY_VALUES" ]]; then
  echo "ERROR: values file not found: $REGISTRY_VALUES" >&2
  exit 1
fi

if [[ ! -f "$MARIADB_VALUES" ]]; then
  echo "ERROR: values file not found: $MARIADB_VALUES" >&2
  exit 1
fi

echo "[STEP2] Kong install"
(
  cd "./gaip_kong"
  ./run.sh install -f "$(child_path_from_devops "$KONG_VALUES")"
)

echo "[STEP2] Registry install"
(
  cd "./gaip_registry"
  ./run.sh install -f "$(child_path_from_devops "$REGISTRY_VALUES")"
)

echo "[STEP2] MariaDB install and init"
(
  cd "./gaip_maraidb"
  ./run.sh install
  ./run.sh init -f "$(child_path_from_devops "$MARIADB_VALUES")"
)

echo "[STEP2] Kafka install"
(
  cd "./gaip_kafka"
  ./run.sh install
)

echo "[STEP2] Redis install"
(
  cd "./gaip_redis"
  ./run.sh install
)

echo "[STEP2] MongoDB install"
(
  cd "./gaip_mongodb"
  ./run.sh install
)
