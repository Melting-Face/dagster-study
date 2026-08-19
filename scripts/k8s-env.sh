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

# --- Spark 오퍼레이터 (Apache 공식 — apache/spark-kubernetes-operator) ---
# Kubeflow spark-operator에서 이전. CRD는 apiVersion: spark.apache.org/v1 (sparkConf 중심).
# v1beta1도 served지만 storage 버전이 v1이라 v1이 정본이다(docs/conventions/k8s.md §9).
SPARK_OPERATOR_NS="${SPARK_OPERATOR_NS:-spark-operator}"
SPARK_OPERATOR_RELEASE="${SPARK_OPERATOR_RELEASE:-spark-kubernetes-operator}"
SPARK_OPERATOR_REPO="${SPARK_OPERATOR_REPO:-spark}"
SPARK_OPERATOR_REPO_URL="${SPARK_OPERATOR_REPO_URL:-https://apache.github.io/spark-kubernetes-operator}"
SPARK_OPERATOR_CHART="${SPARK_OPERATOR_CHART:-spark-kubernetes-operator}"
# 주의: chart 버전 ≠ appVersion. GA appVersion 1.0.0 = **chart 1.8.0**(chart 1.0.0은 appVersion 0.2.0).
# 확인: helm search repo spark/spark-kubernetes-operator --versions
SPARK_OPERATOR_CHART_VERSION="${SPARK_OPERATOR_CHART_VERSION:-1.8.0}"
# Spark 잡을 띄울 네임스페이스. 차트 기본값은 비어 있고 overrideWatchedNamespaces=true라,
# 비워두면 **감시 네임스페이스가 없고 workload SA/rolebinding도 안 생긴다** → 반드시 지정한다.
SPARK_JOB_NS="${SPARK_JOB_NS:-default}"
# driver가 쓰는 ServiceAccount (차트 workloadResources.serviceAccount.name 기본값)
SPARK_JOB_SA="${SPARK_JOB_SA:-spark}"

INSTALL_FLINK="${INSTALL_FLINK:-false}"              # Phase 3에서 true (cert-manager 의존)
FLINK_OPERATOR_NS="${FLINK_OPERATOR_NS:-flink-operator}"
FLINK_JOB_NS="${FLINK_JOB_NS:-default}"                # FlinkDeployment가 뜨는 ns(=SA·RBAC 생성 대상)

# --- CloudNativePG (Iceberg JDBC 카탈로그 Postgres) ---
# 카탈로그 PG를 오퍼레이터로 관리한다(구 Deployment+emptyDir 교체). Cluster CR은 k8s/catalog-postgres.yaml.
# 🔴 **chart 버전 ≠ appVersion** — Spark 오퍼레이터와 같은 함정이다.
# chart **0.29.0** = CNPG **1.30.0**. 대조: `helm search repo cnpg/cloudnative-pg --versions`
CNPG_NS="${CNPG_NS:-cnpg-system}"
CNPG_RELEASE="${CNPG_RELEASE:-cloudnative-pg}"
CNPG_REPO="${CNPG_REPO:-cnpg}"
CNPG_REPO_URL="${CNPG_REPO_URL:-https://cloudnative-pg.github.io/charts}"
CNPG_CHART="${CNPG_CHART:-cloudnative-pg}"
CNPG_CHART_VERSION="${CNPG_CHART_VERSION:-0.29.0}"
# 백업·PITR(선택) — Barman Cloud **플러그인**(CNPG-I). in-tree barman-cloud는 CNPG **1.31.0에서 제거 예정**이라
# 처음부터 플러그인으로 간다. 전제: CNPG ≥ 1.26 + cert-manager(Flink 웹훅과 공용 — ensure_cert_manager가
# 있으면 재사용·없으면 설치. 2026-08-19 현재 클러스터에는 없다).
INSTALL_CNPG_BACKUP="${INSTALL_CNPG_BACKUP:-false}"
CNPG_BARMAN_PLUGIN_VERSION="${CNPG_BARMAN_PLUGIN_VERSION:-v0.14.0}"

# ingress-nginx — UI를 고정 URL로 노출(port-forward 대체).
# kind provider 매니페스트를 쓴다(hostPort 80/443 사용). v1.15.1부터는 `ingress-ready` 노드 라벨을
# 요구하지 않는다(구버전 문서와 다르니 릴리스별로 확인할 것).
INSTALL_INGRESS="${INSTALL_INGRESS:-true}"
INGRESS_NGINX_VERSION="${INGRESS_NGINX_VERSION:-v1.15.1}"
# kind-cluster.yaml의 extraPortMappings와 **반드시 일치**해야 한다(안내 출력용).
INGRESS_HTTP_PORT="${INGRESS_HTTP_PORT:-8080}"
# Flink Operator는 차트 버전 = appVersion(Spark 오퍼레이터처럼 어긋나지 않는다).
# downloads.apache.org는 **현행 릴리스만** 보관한다 — 구버전은 404가 되어 설치가 깨진다
# (2026-08-18 실측: 1.10.0 → 404. 당시 제공분 1.12.1·1.13.0·1.14.0·1.15.0).
# 설치 전 `curl -s https://downloads.apache.org/flink/ | grep flink-kubernetes-operator`로 확인한다.
FLINK_OPERATOR_CHART_VERSION="${FLINK_OPERATOR_CHART_VERSION:-1.15.0}"
# cert-manager는 Flink Operator 웹훅 의존. k8s 버전과의 호환 때문에 최신 계열을 쓴다
# (클러스터가 k8s v1.36이라 2024년대 1.16.x는 검증 범위 밖).
CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.21.1}"

# kind Podman provider(experimental) — rootful 머신 필요
export KIND_EXPERIMENTAL_PROVIDER=podman

# --- 헬퍼 ---
log() {
    printf '\033[1;34m[k8s]\033[0m %s\n' "$*"
}

# cert-manager 보장(멱등) — Flink Operator 웹훅과 CNPG barman 플러그인이 **둘 다** 요구한다.
# 이미 있으면 재사용한다(두 오퍼레이터가 각자 깔아 버전이 갈리는 것을 막는다).
ensure_cert_manager() {
    if kubectl get deploy -n cert-manager cert-manager-webhook >/dev/null 2>&1; then
        log "cert-manager 이미 설치됨 — 재사용"
        return 0
    fi
    log "cert-manager 설치 (${CERT_MANAGER_VERSION})"
    kubectl apply -f \
        "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
    kubectl -n cert-manager rollout status deploy/cert-manager-webhook --timeout=180s
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
