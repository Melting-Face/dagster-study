#!/usr/bin/env bash
# 로컬 K8s 부트스트랩 공용 설정·헬퍼 (k8s-up/operators/down.sh가 source)
# 값은 이 파일 한 곳에서 관리(단일 출처). 자원 수치 근거: docs/resource-sizing.md
# 모든 값은 환경변수로 override 가능(예: MACHINE_MEMORY_MIB=24576 ./scripts/k8s-up.sh)

# --- 클러스터 / podman machine ---
CLUSTER_NAME="${CLUSTER_NAME:-lakehouse}"
MACHINE_NAME="${MACHINE_NAME:-dagster-k8s}"
MACHINE_CPUS="${MACHINE_CPUS:-6}"
MACHINE_MEMORY_MIB="${MACHINE_MEMORY_MIB:-16384}"    # 16 GB (Apple Silicon은 생성 시 확정)
MACHINE_DISK_GIB="${MACHINE_DISK_GIB:-120}"

# --- 로컬 레지스트리 (호스트·클러스터 공통 이름 localhost:5001) ---
REGISTRY_NAME="${REGISTRY_NAME:-kind-registry}"
REGISTRY_PORT="${REGISTRY_PORT:-5001}"
REGISTRY_IMAGE="${REGISTRY_IMAGE:-docker.io/library/registry:2.8.3}"

# --- 오퍼레이터 ---
SPARK_OPERATOR_NS="${SPARK_OPERATOR_NS:-spark-operator}"
# 설치 전 최신 확인: helm search repo spark-operator/spark-operator --versions
SPARK_OPERATOR_CHART_VERSION="${SPARK_OPERATOR_CHART_VERSION:-2.5.2}"

INSTALL_FLINK="${INSTALL_FLINK:-false}"              # Phase 3에서 true (cert-manager 의존)
FLINK_OPERATOR_NS="${FLINK_OPERATOR_NS:-flink-operator}"
FLINK_OPERATOR_CHART_VERSION="${FLINK_OPERATOR_CHART_VERSION:-1.10.0}"
CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.16.2}"

# kind Podman provider(experimental) — rootful 머신 필요
export KIND_EXPERIMENTAL_PROVIDER=podman

# --- 헬퍼 ---
log() {
    printf '\033[1;34m[k8s]\033[0m %s\n' "$*"
}

# 필수 CLI 존재 확인, 없으면 종료
require_cli() {
    local missing=0 cli
    for cli in "$@"; do
        if ! command -v "${cli}" >/dev/null 2>&1; then
            printf '필수 CLI 없음: %s\n' "${cli}" >&2
            missing=1
        fi
    done
    if [ "${missing}" -ne 0 ]; then
        printf '설치 후 재시도: brew install podman kind kubectl helm\n' >&2
        exit 1
    fi
}
