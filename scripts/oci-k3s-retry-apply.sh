#!/usr/bin/env bash
# A1 용량 부족(500 Out of host capacity)을 시간차 재시도로 넘긴다.
# Always Free A1은 인기가 높아 LaunchInstance가 간헐적으로만 성공한다(shape 크기를 줄여도 동일).
# 사용: ./scripts/oci-k3s-retry-apply.sh
#   override 예: INTERVAL=180 MAX_ATTEMPTS=100 TF_DIR=terraform/oci-k3s ./scripts/oci-k3s-retry-apply.sh
#   중단: Ctrl-C (terraform state는 각 시도마다 정합 유지 — 네트워크는 이미 생성돼 있고 인스턴스만 추가된다)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TF_DIR="${TF_DIR:-${REPO_ROOT}/terraform/oci-k3s}"
INTERVAL="${INTERVAL:-300}"          # 재시도 간격(초)
MAX_ATTEMPTS="${MAX_ATTEMPTS:-72}"   # 기본 72회 × 300초 ≈ 6시간
LOG_FILE="${LOG_FILE:-${TF_DIR}/retry-apply.log}"

log() {
    printf '\033[1;34m[oci-k3s-retry]\033[0m %s %s\n' "$(TZ=Asia/Seoul date '+%H:%M:%S')" "$*"
}

command -v terraform >/dev/null 2>&1 || {
    printf '필수 CLI 없음: terraform\n' >&2
    exit 1
}

# 무인 -auto-approve 루프의 위험: 도는 동안 누군가 .tf/tfvars를 고치면 그 변경이 검토 없이 적용된다
# (destroy/replace 포함). 착수 시점 설정의 해시를 고정해 두고, 달라지면 즉시 중단한다.
config_hash() {
    find "${TF_DIR}" -maxdepth 1 \( -name '*.tf' -o -name '*.tfvars' -o -name '*.tftpl' \) -type f \
        -exec shasum -a 256 {} + | sort | shasum -a 256 | cut -d' ' -f1
}

BASELINE_HASH="$(config_hash)"

log "재시도 시작 — 간격 ${INTERVAL}초, 최대 ${MAX_ATTEMPTS}회, 로그 ${LOG_FILE}"
log "설정 해시 고정: ${BASELINE_HASH:0:12} (변경 감지 시 중단)"

attempt=1
while [ "${attempt}" -le "${MAX_ATTEMPTS}" ]; do
    if [ "$(config_hash)" != "${BASELINE_HASH}" ]; then
        log "❌ 착수 이후 terraform 설정이 변경됨 — 무인 적용을 중단한다. 변경을 검토하고 재실행할 것"
        exit 3
    fi

    log "시도 ${attempt}/${MAX_ATTEMPTS}"

    # 성공/실패를 종료코드로 판정하고, 원문은 로그 파일에 남긴다.
    if terraform -chdir="${TF_DIR}" apply -auto-approve -no-color >>"${LOG_FILE}" 2>&1; then
        log "✅ 성공 — 인스턴스 생성 완료 (시도 ${attempt}회)"
        terraform -chdir="${TF_DIR}" output
        log "다음: ./scripts/oci-k3s-kubeconfig.sh 로 kubeconfig 회수"
        exit 0
    fi

    # 용량 부족 외의 오류는 재시도해도 소용없으므로 즉시 중단한다.
    if ! tail -40 "${LOG_FILE}" | grep -q "Out of host capacity"; then
        log "❌ 용량 부족이 아닌 오류 — 재시도 중단. ${LOG_FILE} 확인"
        tail -20 "${LOG_FILE}" >&2
        exit 1
    fi

    log "용량 부족 — ${INTERVAL}초 후 재시도"
    sleep "${INTERVAL}"
    attempt=$((attempt + 1))
done

log "⏱ 최대 시도(${MAX_ATTEMPTS}회) 소진 — 용량 미확보. 시간대를 바꿔 다시 실행한다."
exit 2
