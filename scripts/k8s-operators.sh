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
    log "cert-manager 설치 (${CERT_MANAGER_VERSION}) — Flink Operator 웹훅 의존"
    kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
    kubectl -n cert-manager rollout status deploy/cert-manager-webhook --timeout=180s

    log "Flink Operator 설치 (ns=${FLINK_OPERATOR_NS}, ver=${FLINK_OPERATOR_CHART_VERSION})"
    helm repo add flink-operator-repo \
        "https://downloads.apache.org/flink/flink-kubernetes-operator-${FLINK_OPERATOR_CHART_VERSION}/" >/dev/null 2>&1 || true
    helm repo update >/dev/null
    helm upgrade --install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator \
        --namespace "${FLINK_OPERATOR_NS}" --create-namespace --wait
else
    log "Flink Operator 건너뜀 (INSTALL_FLINK=true 로 활성화 — Phase 3)"
fi

log "설치 완료. 오퍼레이터 상태:"
kubectl get pods -n "${SPARK_OPERATOR_NS}"
[ "${INSTALL_FLINK}" = "true" ] && kubectl get pods -n "${FLINK_OPERATOR_NS}" || true
