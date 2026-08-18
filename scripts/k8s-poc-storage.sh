#!/usr/bin/env bash
# PoC 스토리지 배포: Secret(크리덴셜) → SeaweedFS(S3) + Catalog Postgres → warehouse 버킷
# 사용: ./scripts/k8s-poc-storage.sh
# 크리덴셜은 로컬 PoC 기본값(env override 가능). 실인프라는 외부 시크릿 매니저 사용.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=scripts/k8s-env.sh
source "${SCRIPT_DIR}/k8s-env.sh"

require_cli kubectl
kubectl config use-context "kind-${CLUSTER_NAME}"

# 로컬 PoC 크리덴셜(placeholder — 실값은 env로 주입)
S3_ACCESS_KEY="${S3_ACCESS_KEY:-poc-access}"          # pragma: allowlist secret
S3_SECRET_KEY="${S3_SECRET_KEY:-poc-local-secret}"    # pragma: allowlist secret
PG_USER="${PG_USER:-iceberg}"
PG_PASSWORD="${PG_PASSWORD:-iceberg-local}"           # pragma: allowlist secret

S3_JSON="$(cat <<JSON
{"identities":[{"name":"poc","credentials":[{"accessKey":"${S3_ACCESS_KEY}","secretKey":"${S3_SECRET_KEY}"}],"actions":["Admin","Read","Write","List","Tagging"]}]}
JSON
)"

# 1) Secret (SeaweedFS s3.json + PG/S3 접속 키)
log "Secret 생성/갱신: lakehouse-creds"
kubectl create secret generic lakehouse-creds -n default \
    --from-literal=pg-user="${PG_USER}" \
    --from-literal=pg-password="${PG_PASSWORD}" \
    --from-literal=s3-access-key="${S3_ACCESS_KEY}" \
    --from-literal=s3-secret-key="${S3_SECRET_KEY}" \
    --from-literal=s3.json="${S3_JSON}" \
    --dry-run=client -o yaml | kubectl apply -f -

# 2) 스토리지 배포
log "SeaweedFS + Catalog Postgres 배포"
kubectl apply -f "${REPO_ROOT}/k8s/seaweedfs.yaml"
kubectl apply -f "${REPO_ROOT}/k8s/catalog-postgres.yaml"
kubectl -n default rollout status statefulset/seaweedfs --timeout=180s
kubectl -n default rollout status deploy/catalog-postgres --timeout=120s

# 3) warehouse 버킷 생성(멱등) — weed shell은 filer 자동발견 실패가 있어 -filer 명시
#    파드가 Ready여도 filer의 gRPC(포트+10000)는 아직 안 열려 있을 수 있다
#    (2026-08-19 실측: `dial tcp [::1]:18888 connect: connection refused`) → 재시도한다.
log "warehouse 버킷 생성"
for attempt in $(seq 1 12); do
    if kubectl -n default exec statefulset/seaweedfs -- \
        sh -c 'echo "s3.bucket.create -name warehouse" | weed shell -master localhost:9333 -filer localhost:8888' \
        >/dev/null 2>&1; then
        log "warehouse 버킷 준비 완료 (시도 ${attempt})"
        break
    fi
    sleep 5
done

log "완료. 다음: 이미지 빌드·push → kubectl apply -f k8s/spark/sparkapplication-poc.yaml"
