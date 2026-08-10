#!/usr/bin/env bash
# 로컬 K8s(kind on Podman) 클러스터 + 로컬 레지스트리 기동 (재설계 PoC Phase 0)
# 사용: ./scripts/k8s-up.sh
# 자원 override 예: MACHINE_MEMORY_MIB=24576 ./scripts/k8s-up.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=scripts/k8s-env.sh
source "${SCRIPT_DIR}/k8s-env.sh"

REGISTRY_DIR="/etc/containerd/certs.d/localhost:${REGISTRY_PORT}"

require_cli podman kind kubectl

# 1) podman machine (rootful, 6/16/120) — Apple Silicon은 생성 시 자원 확정
if ! podman machine inspect "${MACHINE_NAME}" >/dev/null 2>&1; then
    log "podman machine 생성: ${MACHINE_NAME} (cpus=${MACHINE_CPUS}, mem=${MACHINE_MEMORY_MIB}MiB, disk=${MACHINE_DISK_GIB}GiB, rootful)"
    podman machine init "${MACHINE_NAME}" \
        --rootful \
        --cpus "${MACHINE_CPUS}" \
        --memory "${MACHINE_MEMORY_MIB}" \
        --disk-size "${MACHINE_DISK_GIB}"
else
    log "podman machine 존재: ${MACHINE_NAME} (자원 변경은 재생성 필요 — Apple Silicon applehv)"
fi

if [ "$(podman machine inspect "${MACHINE_NAME}" --format '{{.State}}' 2>/dev/null)" != "running" ]; then
    log "podman machine 시작: ${MACHINE_NAME}"
    podman machine start "${MACHINE_NAME}"
fi

# 2) 로컬 레지스트리 컨테이너 (127.0.0.1:5001)
if [ "$(podman inspect -f '{{.State.Running}}' "${REGISTRY_NAME}" 2>/dev/null || echo false)" != "true" ]; then
    log "로컬 레지스트리 기동: ${REGISTRY_NAME} → 127.0.0.1:${REGISTRY_PORT}"
    podman run -d --restart=always \
        -p "127.0.0.1:${REGISTRY_PORT}:5000" \
        --name "${REGISTRY_NAME}" "${REGISTRY_IMAGE}"
else
    log "로컬 레지스트리 실행중: ${REGISTRY_NAME}"
fi

# 3) kind 클러스터 생성
if ! kind get clusters | grep -qx "${CLUSTER_NAME}"; then
    log "kind 클러스터 생성: ${CLUSTER_NAME} (provider=podman)"
    kind create cluster --name "${CLUSTER_NAME}" --config "${REPO_ROOT}/k8s/kind-cluster.yaml"
else
    log "kind 클러스터 존재: ${CLUSTER_NAME}"
fi

# 4) 각 노드에 레지스트리 hosts.toml 주입 (localhost:5001 → kind-registry:5000)
log "노드 registry certs.d 설정: ${REGISTRY_DIR}"
for node in $(kind get nodes --name "${CLUSTER_NAME}"); do
    podman exec "${node}" mkdir -p "${REGISTRY_DIR}"
    podman exec -i "${node}" sh -c "cat > '${REGISTRY_DIR}/hosts.toml'" <<EOF
[host."http://${REGISTRY_NAME}:5000"]
EOF
done

# 5) 레지스트리를 kind 네트워크에 연결 (노드가 kind-registry 이름 해석)
if [ "$(podman inspect -f '{{json .NetworkSettings.Networks.kind}}' "${REGISTRY_NAME}" 2>/dev/null || echo null)" = "null" ]; then
    log "레지스트리를 kind 네트워크에 연결"
    podman network connect kind "${REGISTRY_NAME}"
fi

# 6) local-registry-hosting ConfigMap (도구 호환 표준)
log "local-registry-hosting ConfigMap 적용"
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
    name: local-registry-hosting
    namespace: kube-public
data:
    localRegistryHosting.v1: |
        host: "localhost:${REGISTRY_PORT}"
        help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

log "완료. 다음: ./scripts/k8s-operators.sh"
log "확인: kubectl cluster-info --context kind-${CLUSTER_NAME}"
