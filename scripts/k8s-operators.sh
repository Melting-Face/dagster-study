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

# 1) Spark Operator (Apache 공식) — SparkApplication CRD(spark.apache.org/v1) 제공
#    Kubeflow spark-operator에서 이전. GA 1.0.0(2026-07-26).
log "Spark Operator(Apache) 설치 (ns=${SPARK_OPERATOR_NS}, ver=${SPARK_OPERATOR_CHART_VERSION})"
helm repo add "${SPARK_OPERATOR_REPO}" "${SPARK_OPERATOR_REPO_URL}" >/dev/null 2>&1 || true
helm repo update >/dev/null
helm upgrade --install "${SPARK_OPERATOR_RELEASE}" "${SPARK_OPERATOR_REPO}/${SPARK_OPERATOR_CHART}" \
    --version "${SPARK_OPERATOR_CHART_VERSION}" \
    --namespace "${SPARK_OPERATOR_NS}" --create-namespace \
    --wait
# 주의: Apache 차트 values 키는 Kubeflow와 다르다(job 네임스페이스·컨트롤러 자원 한도 등).
#       설치 대상 네임스페이스·컨트롤러 requests/limits는 아래로 확인 후 --set 추가한다
#       (자원값 근거: docs/resource-sizing.md):
#       helm show values "${SPARK_OPERATOR_REPO}/${SPARK_OPERATOR_CHART}" --version "${SPARK_OPERATOR_CHART_VERSION}"

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
