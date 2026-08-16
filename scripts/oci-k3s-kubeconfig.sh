#!/usr/bin/env bash
# OCI k3s 서버에서 kubeconfig(공인 IP 반영본)를 호스트로 회수한다.
# 사용: ./scripts/oci-k3s-kubeconfig.sh [출력경로]
#   기본 출력: <repo>/kubeconfig-oci  → export KUBECONFIG로 지정해 사용
#   override 예: SSH_USER=ubuntu TF_DIR=terraform/oci-k3s ./scripts/oci-k3s-kubeconfig.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TF_DIR="${TF_DIR:-${REPO_ROOT}/terraform/oci-k3s}"
OUT="${1:-${REPO_ROOT}/kubeconfig-oci}"
SSH_USER="${SSH_USER:-ubuntu}"

log() {
    printf '\033[1;34m[oci-k3s]\033[0m %s\n' "$*"
}

command -v terraform >/dev/null 2>&1 || {
    printf '필수 CLI 없음: terraform\n' >&2
    exit 1
}

PUBLIC_IP="$(terraform -chdir="${TF_DIR}" output -raw public_ip 2>/dev/null || true)"
if [ -z "${PUBLIC_IP}" ]; then
    printf 'public_ip output 없음 — 먼저 terraform apply 를 완료하세요.\n' >&2
    exit 1
fi

log "kubeconfig 회수: ${SSH_USER}@${PUBLIC_IP} → ${OUT}"

# cloud-init이 만든 공인 IP 반영본을 우선 회수, 없으면 원본을 받아 치환
if scp -o StrictHostKeyChecking=accept-new \
    "${SSH_USER}@${PUBLIC_IP}:/home/${SSH_USER}/.kube/config-public" "${OUT}" 2>/dev/null; then
    log "config-public 회수 완료"
else
    log "config-public 없음 — 원본을 받아 127.0.0.1 → ${PUBLIC_IP} 치환"
    ssh -o StrictHostKeyChecking=accept-new "${SSH_USER}@${PUBLIC_IP}" "sudo cat /etc/rancher/k3s/k3s.yaml" \
        | sed "s/127.0.0.1/${PUBLIC_IP}/g" >"${OUT}"
fi
chmod 600 "${OUT}"

log "완료. 사용: export KUBECONFIG=${OUT} && kubectl get nodes"
