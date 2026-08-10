#!/usr/bin/env bash
# 로컬 K8s 정리: kind 클러스터 + 레지스트리 삭제. podman machine은 기본 보존.
# 사용: ./scripts/k8s-down.sh
#       STOP_MACHINE=true   ./scripts/k8s-down.sh   # 머신 중지(자원 회수, 데이터 보존)
#       REMOVE_MACHINE=true ./scripts/k8s-down.sh   # 머신 삭제(데이터 소멸)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/k8s-env.sh
source "${SCRIPT_DIR}/k8s-env.sh"

STOP_MACHINE="${STOP_MACHINE:-false}"
REMOVE_MACHINE="${REMOVE_MACHINE:-false}"

require_cli kind podman

if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
    log "kind 클러스터 삭제: ${CLUSTER_NAME}"
    kind delete cluster --name "${CLUSTER_NAME}"
fi

if podman inspect "${REGISTRY_NAME}" >/dev/null 2>&1; then
    log "레지스트리 삭제: ${REGISTRY_NAME}"
    podman rm -f "${REGISTRY_NAME}"
fi

if [ "${REMOVE_MACHINE}" = "true" ]; then
    log "podman machine 삭제: ${MACHINE_NAME} (데이터 소멸)"
    podman machine rm -f "${MACHINE_NAME}"
elif [ "${STOP_MACHINE}" = "true" ]; then
    log "podman machine 중지: ${MACHINE_NAME}"
    podman machine stop "${MACHINE_NAME}"
else
    log "podman machine 보존: ${MACHINE_NAME} (중지=STOP_MACHINE=true / 삭제=REMOVE_MACHINE=true)"
fi
