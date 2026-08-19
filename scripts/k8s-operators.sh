#!/usr/bin/env bash
# Spark Operator(필수) + Flink Operator(선택, INSTALL_FLINK=true) 설치
# 사용: ./scripts/k8s-operators.sh
#       INSTALL_FLINK=true ./scripts/k8s-operators.sh   # Phase 3
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=scripts/k8s-env.sh
source "${SCRIPT_DIR}/k8s-env.sh"

require_cli helm kubectl

kubectl config use-context "kind-${CLUSTER_NAME}"

# 1) Spark Operator (Apache 공식) — SparkApplication CRD(spark.apache.org/v1beta1) 제공
#    Kubeflow spark-operator(sparkoperator.k8s.io/v1beta2)에서 이전.
#    chart 1.8.0 = appVersion 1.0.0(GA). chart≠appVersion 주의(k8s-env.sh 참고).
#
#    구 Kubeflow 릴리스가 남아 있으면 CRD 그룹이 달라 오퍼레이터가 이중으로 뜨므로 먼저 제거한다.
if helm status spark-operator -n "${SPARK_OPERATOR_NS}" >/dev/null 2>&1; then
    log "구 Kubeflow 릴리스(spark-operator) 감지 → 제거"
    helm uninstall spark-operator -n "${SPARK_OPERATOR_NS}"
    kubectl delete crd sparkapplications.sparkoperator.k8s.io \
        scheduledsparkapplications.sparkoperator.k8s.io \
        sparkconnects.sparkoperator.k8s.io --ignore-not-found
fi

log "Spark Operator(Apache) 설치 (ns=${SPARK_OPERATOR_NS}, chart=${SPARK_OPERATOR_CHART_VERSION}, job ns=${SPARK_JOB_NS})"
helm repo add "${SPARK_OPERATOR_REPO}" "${SPARK_OPERATOR_REPO_URL}" >/dev/null 2>&1 || true
helm repo update >/dev/null
# workloadResources.namespaces.data: 잡 네임스페이스(비우면 감시 대상·workload SA가 생기지 않는다)
# 컨트롤러 자원 한도 근거: docs/resource-sizing.md (Spark Operator 100m/256Mi req · 250m/512Mi lim)
helm upgrade --install "${SPARK_OPERATOR_RELEASE}" "${SPARK_OPERATOR_REPO}/${SPARK_OPERATOR_CHART}" \
    --version "${SPARK_OPERATOR_CHART_VERSION}" \
    --namespace "${SPARK_OPERATOR_NS}" --create-namespace \
    --set "workloadResources.namespaces.data[0]=${SPARK_JOB_NS}" \
    --set "workloadResources.namespaces.create=false" \
    --set "workloadResources.serviceAccount.name=${SPARK_JOB_SA}" \
    --wait
# values 전체 확인:
#   helm show values "${SPARK_OPERATOR_REPO}/${SPARK_OPERATOR_CHART}" --version "${SPARK_OPERATOR_CHART_VERSION}"

# 1-2) workload SA 보완 RBAC — 차트 clusterrole에 deletecollection이 없어 종료 정리가 실패한다
log "Spark workload 정리 권한 보완 (ns=${SPARK_JOB_NS})"
kubectl apply -f "${REPO_ROOT}/k8s/spark/spark-workload-cleanup-rbac.yaml"

# 2) Flink Operator (선택) — FlinkDeployment CRD, webhook가 cert-manager 의존
if [ "${INSTALL_FLINK}" = "true" ]; then
    # Flink Operator 웹훅이 cert-manager를 요구한다(CNPG barman 플러그인과 공용 — k8s-env.sh 헬퍼).
    ensure_cert_manager

    log "Flink Operator 설치 (ns=${FLINK_OPERATOR_NS}, ver=${FLINK_OPERATOR_CHART_VERSION})"
    helm repo add flink-operator-repo \
        "https://downloads.apache.org/flink/flink-kubernetes-operator-${FLINK_OPERATOR_CHART_VERSION}/" >/dev/null 2>&1 || true
    helm repo update >/dev/null
    # watchNamespaces를 반드시 지정한다 — 비우면 감시는 전 네임스페이스로 열리지만
    # 잡 SA(`flink`)와 Role/RoleBinding이 **오퍼레이터 ns에만** 생겨 잡 ns에서 파드가 못 뜬다
    # (Spark 차트의 workloadResources.namespaces와 같은 함정, 2026-08-18 실측).
    helm upgrade --install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator \
        --namespace "${FLINK_OPERATOR_NS}" --create-namespace \
        --set "watchNamespaces={${FLINK_JOB_NS}}" \
        --values "${REPO_ROOT}/k8s/flink/operator-values.yaml" \
        --version "${FLINK_OPERATOR_CHART_VERSION}" --wait

    # 2-2) 웹훅 보완 RBAC — watchNamespaces 지정 시 클러스터 스코프 조회 권한이 사라진다
    log "Flink Operator webhook 보완 RBAC 적용"
    kubectl apply -f "${REPO_ROOT}/k8s/flink/flink-operator-webhook-rbac.yaml"

    # 2-3) workload SA 보완 RBAC — 클러스터 내부 잡 제출 시 <name>-rest 서비스 조회가 필요하다
    log "Flink workload 보완 RBAC 적용 (ns=${FLINK_JOB_NS})"
    kubectl apply -f "${REPO_ROOT}/k8s/flink/flink-workload-rbac.yaml"
else
    log "Flink Operator 건너뜀 (INSTALL_FLINK=true 로 활성화 — Phase 3)"
fi

# 3) CloudNativePG — Iceberg JDBC 카탈로그 Postgres를 오퍼레이터로 관리
#    Cluster CR(k8s/catalog-postgres.yaml)은 scripts/k8s-poc-storage.sh가 적용한다.
#    🔴 chart 0.29.0 = CNPG 1.30.0 (chart 버전 ≠ appVersion — k8s-env.sh 참고)
log "CloudNativePG 설치 (ns=${CNPG_NS}, chart=${CNPG_CHART_VERSION})"
helm repo add "${CNPG_REPO}" "${CNPG_REPO_URL}" >/dev/null 2>&1 || true
helm repo update >/dev/null
# 컨트롤러 자원 한도 명시(docs/conventions/k8s.md §2, 수치 근거 docs/resource-sizing.md)
helm upgrade --install "${CNPG_RELEASE}" "${CNPG_REPO}/${CNPG_CHART}" \
    --version "${CNPG_CHART_VERSION}" \
    --namespace "${CNPG_NS}" --create-namespace \
    --set "resources.requests.cpu=100m" \
    --set "resources.requests.memory=200Mi" \
    --set "resources.limits.cpu=250m" \
    --set "resources.limits.memory=384Mi" \
    --wait

# 3-2) Barman Cloud 플러그인 — 백업·PITR. 백업 대상은 클러스터 내부 SeaweedFS(S3)라 외부 비용 0.
#      🔴 선택이 아니다 — Cluster CR이 `isWALArchiver: true`로 이 플러그인을 참조하므로
#      없으면 WAL 아카이빙이 실패한다(k8s-env.sh 주석 참고).
ensure_cert_manager
log "Barman Cloud 플러그인 설치 (${CNPG_BARMAN_PLUGIN_VERSION}) — 오퍼레이터와 같은 ns(${CNPG_NS})"
kubectl apply -f \
    "https://github.com/cloudnative-pg/plugin-barman-cloud/releases/download/${CNPG_BARMAN_PLUGIN_VERSION}/manifest.yaml"
kubectl rollout status deployment -n "${CNPG_NS}" barman-cloud --timeout=180s

log "설치 완료. 오퍼레이터 상태:"
kubectl get pods -n "${SPARK_OPERATOR_NS}"
kubectl get pods -n "${CNPG_NS}"
[ "${INSTALL_FLINK}" = "true" ] && kubectl get pods -n "${FLINK_OPERATOR_NS}" || true
