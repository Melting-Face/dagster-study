#!/usr/bin/env bash
# Spark Operator(필수) + Flink Operator(선택, INSTALL_FLINK=true) 설치
# 사용: ./scripts/k8s-operators.sh
#       INSTALL_FLINK=true ./scripts/k8s-operators.sh   # Phase 3
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/k8s-env.sh
source "${SCRIPT_DIR}/k8s-env.sh"

require_cli helm kubectl

kubectl config use-context "kind-${CLUSTER_NAME}"

# 1) Spark Operator (Kubeflow) — SparkApplication CRD 제공
# 자원값 근거: docs/resource-sizing.md "Kubernetes 재설계 시나리오"
log "Spark Operator 설치 (ns=${SPARK_OPERATOR_NS}, ver=${SPARK_OPERATOR_CHART_VERSION})"
helm repo add spark-operator https://kubeflow.github.io/spark-operator >/dev/null 2>&1 || true
helm repo update >/dev/null
helm upgrade --install spark-operator spark-operator/spark-operator \
    --version "${SPARK_OPERATOR_CHART_VERSION}" \
    --namespace "${SPARK_OPERATOR_NS}" --create-namespace \
    --set webhook.enable=true \
    --set 'spark.jobNamespaces={default}' \
    --set controller.resources.requests.cpu=100m \
    --set controller.resources.requests.memory=256Mi \
    --set controller.resources.limits.cpu=250m \
    --set controller.resources.limits.memory=512Mi \
    --wait
# 주의: 차트 버전에 따라 값 키가 다를 수 있음(구버전 sparkJobNamespaces).
#       helm show values spark-operator/spark-operator --version <ver> 로 확인.

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
