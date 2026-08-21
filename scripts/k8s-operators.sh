#!/usr/bin/env bash
# Spark Operator + Flink Operator(기본 설치, INSTALL_FLINK=false로 제외) 설치
# 사용: ./scripts/k8s-operators.sh
#       INSTALL_FLINK=false ./scripts/k8s-operators.sh   # Flink 제외
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
#
# 🔴 컨트롤러 자원은 **반드시 --set으로 명시**한다(docs/conventions/k8s.md §2).
#    2026-08-19까지 이 블록에는 근거 주석만 있고 --set이 없어 차트 기본값 **1000m/2048Mi**가
#    적용되고 있었다. 에러가 나지 않아 아무도 몰랐고, 노드 requests의 CPU 31%·메모리 38%를
#    유휴 오퍼레이터가 점유했다(실사용은 196Mi — 10.7배 과예약).
#
# 🔴 값 근거 — 문서의 옛 `100m/256Mi`를 쓰면 **오퍼레이터가 죽는다.**
#    그 수치는 **Kubeflow(Go) 오퍼레이터 시절** 것이고, 위 1)에서 이전한 Apache 오퍼레이터는
#    **JVM**이다. 차트 jvmArgs가 `-XX:MaxRAMPercentage=80`이라 힙 상한이 컨테이너 한도에
#    직접 연동돼, 한도 256Mi → 힙 205Mi인데 실측 anon이 이미 193MB라 즉시 OOMKill이다.
#    아래 값은 **실측 196Mi 기준 한도 1Gi(힙 819Mi)로 약 4배 여유**를 두었고,
#    `InitialRAMPercentage=80` 선점(AlwaysPreTouch)이 유효해지더라도 한도 안에 들어온다
#    (= 선점 유효/무효 **어느 가설에서도 안전**한 값).
#    키 경로는 `helm show values`로 확인했다 — helm은 **모르는 --set 키를 조용히 무시**하므로
#    경로를 추측하면 "설정했다고 믿는" 같은 함정을 반복하게 된다.
helm upgrade --install "${SPARK_OPERATOR_RELEASE}" "${SPARK_OPERATOR_REPO}/${SPARK_OPERATOR_CHART}" \
    --version "${SPARK_OPERATOR_CHART_VERSION}" \
    --namespace "${SPARK_OPERATOR_NS}" --create-namespace \
    --set "workloadResources.namespaces.data[0]=${SPARK_JOB_NS}" \
    --set "workloadResources.namespaces.create=false" \
    --set "workloadResources.serviceAccount.name=${SPARK_JOB_SA}" \
    --set "operatorDeployment.operatorPod.operatorContainer.resources.requests.cpu=250m" \
    --set "operatorDeployment.operatorPod.operatorContainer.resources.requests.memory=512Mi" \
    --set "operatorDeployment.operatorPod.operatorContainer.resources.limits.cpu=500m" \
    --set "operatorDeployment.operatorPod.operatorContainer.resources.limits.memory=1Gi" \
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
    #
    # 🔴 컨트롤러·웹훅 자원은 **반드시 --set으로 명시**한다(docs/conventions/k8s.md §2).
    #    차트 1.15.0은 `operatorPod.resources: {}` / `operatorPod.webhook.resources: {}`로
    #    자원을 **아예 선언하지 않는다**(2026-08-21 `helm show values` 실측 — 92행·101행).
    #    안 넣으면 파드가 **BestEffort**가 되어 `describe node`의 requests 합계에 **0으로 잡히는
    #    유령**이 된다(예약은 0인데 실제로는 먹는다 → 예산이 조용히 어긋난다).
    #    Spark 오퍼레이터에서 **거울상 함정**을 이미 겪었다(선언이 없어 차트 기본값 1000m/2048Mi가
    #    무자각 적용, 실사용 196Mi — 10.7배 과예약). 방향만 반대일 뿐 원인은 같다: **미선언**.
    #    수치 근거는 docs/resource-sizing.md(동시 기동 예산). 키 경로는 위 실측으로 확인했다 —
    #    helm은 **모르는 --set 키를 조용히 무시**하므로 경로를 추측하지 않는다.
    helm upgrade --install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator \
        --namespace "${FLINK_OPERATOR_NS}" --create-namespace \
        --set "watchNamespaces={${FLINK_JOB_NS}}" \
        --set "operatorPod.resources.requests.cpu=200m" \
        --set "operatorPod.resources.requests.memory=512Mi" \
        --set "operatorPod.resources.limits.cpu=500m" \
        --set "operatorPod.resources.limits.memory=1Gi" \
        --set "operatorPod.webhook.resources.requests.cpu=100m" \
        --set "operatorPod.webhook.resources.requests.memory=256Mi" \
        --set "operatorPod.webhook.resources.limits.cpu=200m" \
        --set "operatorPod.webhook.resources.limits.memory=512Mi" \
        --values "${REPO_ROOT}/k8s/flink/operator-values.yaml" \
        --version "${FLINK_OPERATOR_CHART_VERSION}" --wait

    # 2-2) 웹훅 보완 RBAC — watchNamespaces 지정 시 클러스터 스코프 조회 권한이 사라진다
    log "Flink Operator webhook 보완 RBAC 적용"
    kubectl apply -f "${REPO_ROOT}/k8s/flink/flink-operator-webhook-rbac.yaml"

    # 2-3) workload SA 보완 RBAC — 클러스터 내부 잡 제출 시 <name>-rest 서비스 조회가 필요하다
    log "Flink workload 보완 RBAC 적용 (ns=${FLINK_JOB_NS})"
    kubectl apply -f "${REPO_ROOT}/k8s/flink/flink-workload-rbac.yaml"
else
    log "Flink Operator 건너뜀 (INSTALL_FLINK=false 로 비활성화됨 — 기본값은 true)"
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
