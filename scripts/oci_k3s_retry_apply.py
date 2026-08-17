#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["oci>=2.184,<3"]
# ///
"""A1 용량이 실제로 열린 순간에만 terraform apply를 던지는 재시도 루프.

왜 이 스크립트인가:
    이전 방식(5분마다 무조건 `terraform apply`)은 apply 1회가 plan 재계산까지
    포함해 무겁다. 그래서 폴링 간격을 좁힐 수 없는데, Always Free A1 용량은
    초 단위로 열렸다 닫힌다 → 대부분의 창구를 놓친다. 실패하는 LaunchInstance를
    반복하면 API 스로틀링(429)도 자초한다.

    CreateComputeCapacityReport는 읽기 전용·경량이라 촘촘히 폴링할 수 있다.
    availability_status가 "AVAILABLE"인 순간에만 apply를 실행한다
    → 감시는 조밀하게, LaunchInstance는 성공 가능성이 있을 때만.

인증·shape·AD는 모두 terraform.tfvars에서 읽는다(단일 출처).
terraform이 만들 인스턴스와 용량 조회 대상이 어긋나면 폴링 자체가 무의미하다.

참고: 도쿄(ap-tokyo-1)는 AD가 1개라 "다른 AD로 시도" 권고가 적용되지 않는다.
    그래서 AD 전체를 조회하되, terraform이 실제로 쓸 AD가 열렸을 때만 apply한다.

실행(의존성은 위 PEP 723 블록에 선언 — uv가 자동 provisioning):
    uv run scripts/oci_k3s_retry_apply.py
    INTERVAL=30 MAX_ATTEMPTS=1440 uv run scripts/oci_k3s_retry_apply.py
    ONCE=1 uv run scripts/oci_k3s_retry_apply.py   # 1회 조회만(스모크/크론)

중단은 Ctrl-C. 네트워크는 이미 생성돼 있고 인스턴스만 추가되므로 state는 정합 유지.

스타일: 스크립트 컨벤션(docs/conventions/python.md)에 따라 절차형으로 쓴다.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import oci

KST = ZoneInfo("Asia/Seoul")
REPO_ROOT = Path(__file__).resolve().parent.parent
TF_DIR = Path(os.environ.get("TF_DIR", REPO_ROOT / "terraform" / "oci-k3s"))
TFVARS_FILE = TF_DIR / "terraform.tfvars"
LOG_FILE = Path(os.environ.get("LOG_FILE", TF_DIR / "retry-apply.log"))
INTERVAL = int(os.environ.get("INTERVAL", "60"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "720"))  # 720회 x 60초 = 12시간
ONCE = os.environ.get("ONCE", "") not in ("", "0", "false")
THROTTLE_BACKOFF = 300  # 429(TooManyRequests) 응답 시 추가 대기(초)

# 무인 apply가 집어삼킬 수 있는 파일 — 착수 시점 해시를 고정해 두고 바뀌면 중단한다.
CONFIG_GLOBS = ("*.tf", "*.tfvars", "*.tftpl")

# tfvars에 없으면 쓰는 값 — terraform/oci-k3s/variables.tf의 default와 동기화한다.
# (실행 시작 시 확정값을 로그로 남기므로 어긋나면 눈에 띈다)
SHAPE_DEFAULTS = {
    "instance_shape": "VM.Standard.A1.Flex",
    "instance_ocpus": "2",
    "instance_memory_gbs": "12",
    "availability_domain": "",
}

TFVARS_REQUIRED = (
    "tenancy_ocid",
    "user_ocid",
    "fingerprint",
    "private_key_path",
    "region",
    "compartment_ocid",
)

# 공식 enum (oci.core.models.CapacityReportShapeAvailability)
STATUS_AVAILABLE = "AVAILABLE"
STATUS_OUT_OF_CAPACITY = "OUT_OF_HOST_CAPACITY"
STATUS_HARDWARE_NOT_SUPPORTED = "HARDWARE_NOT_SUPPORTED"


def log(message: str) -> None:
    """KST 타임스탬프를 붙여 진행 상황을 표준출력에 남긴다."""
    stamp = datetime.now(tz=KST).strftime("%H:%M:%S")
    print(f"\033[1;34m[oci-k3s-retry]\033[0m {stamp} {message}", flush=True)


def config_hash() -> str:
    """Terraform 설정 파일 내용의 해시.

    루프 도중 설정이 바뀌면 무인 적용을 멈추기 위한 기준값이다.
    """
    digest = hashlib.sha256()
    paths = sorted(
        path for glob in CONFIG_GLOBS for path in TF_DIR.glob(glob) if path.is_file()
    )
    for path in paths:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    """용량을 폴링하다가 재고가 잡히면 terraform apply를 실행한다."""
    terraform_bin = shutil.which("terraform")
    if terraform_bin is None:
        print("필수 CLI 없음: terraform", file=sys.stderr)
        return 1
    if not TFVARS_FILE.is_file():
        print(f"설정 파일 없음: {TFVARS_FILE}", file=sys.stderr)
        return 1

    # --- tfvars 파싱 → SDK 인증 정보와 조회 대상 확정 ---
    # `key = "값"` / `key = 숫자`만 읽는다. 주석(`#`)으로 시작하는 줄은 건너뛴다.
    tfvars = dict(SHAPE_DEFAULTS)
    for raw_line in TFVARS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split("#", 1)[0].strip().strip('"')
        tfvars[key.strip()] = value

    missing = [key for key in TFVARS_REQUIRED if not tfvars.get(key)]
    if missing:
        print(f"tfvars에 필수 값 없음: {', '.join(missing)}", file=sys.stderr)
        return 1

    oci_config = {
        "tenancy": tfvars["tenancy_ocid"],
        "user": tfvars["user_ocid"],
        "fingerprint": tfvars["fingerprint"],
        "key_file": str(Path(tfvars["private_key_path"]).expanduser()),
        "region": tfvars["region"],
    }
    oci.config.validate_config(oci_config)

    shape = tfvars["instance_shape"]
    ocpus = float(tfvars["instance_ocpus"])
    memory_gbs = float(tfvars["instance_memory_gbs"])

    identity = oci.identity.IdentityClient(oci_config)
    compute = oci.core.ComputeClient(oci_config)

    # 용량 리포트는 AD 단위 조회다. terraform이 쓸 AD(미지정 시 첫 번째)를 기준으로
    # 삼고, 나머지 AD도 참고용으로 본다 — 거기에 재고가 있으면 변수로 옮길 수 있다.
    domains = identity.list_availability_domains(
        compartment_id=tfvars["tenancy_ocid"]
    ).data
    ad_names = [domain.name for domain in domains]
    target_ad = tfvars["availability_domain"] or ad_names[0]

    baseline_hash = config_hash()

    log(f"용량 폴링 시작 — {shape} {ocpus:g} OCPU / {memory_gbs:g} GB")
    log(f"리전 {tfvars['region']} · 대상 AD {target_ad} (리전 내 AD {len(ad_names)}개)")
    log(f"간격 {INTERVAL}초, 최대 {MAX_ATTEMPTS}회, 로그 {LOG_FILE}")
    log(f"설정 해시 고정: {baseline_hash[:12]} (변경 감지 시 중단)")

    report_details = oci.core.models.CreateComputeCapacityReportDetails(
        compartment_id=tfvars["compartment_ocid"],
        availability_domain=target_ad,
        shape_availabilities=[
            # fault_domain 미지정 → 리포트가 모든 fault domain 정보를 담는다.
            oci.core.models.CreateCapacityReportShapeAvailabilityDetails(
                instance_shape=shape,
                instance_shape_config=oci.core.models.CapacityReportInstanceShapeConfig(
                    ocpus=ocpus,
                    memory_in_gbs=memory_gbs,
                ),
            )
        ],
    )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if config_hash() != baseline_hash:
            log("❌ 착수 이후 terraform 설정이 변경됨 — 무인 적용을 중단한다")
            log("   변경을 검토하고 다시 실행할 것")
            return 3

        # --- 1) 재고 조회 (읽기 전용 — LaunchInstance를 쓰지 않는다) ---
        # 관측값을 모아 뒀다가 매 회차 로그에 남긴다. 응답이 비어 있는 경우와
        # "재고 없음"이 로그상 구분되지 않으면 폴링이 도는지조차 확인할 수 없다.
        observed: list[str] = []
        for ad_name in ad_names:
            report_details.availability_domain = ad_name
            try:
                report = compute.create_compute_capacity_report(report_details).data
            except oci.exceptions.ServiceError as error:
                if error.status == 429:
                    log(f"⏳ API 스로틀링(429) — {THROTTLE_BACKOFF}초 대기")
                    time.sleep(THROTTLE_BACKOFF)
                    break
                log(f"❌ 용량 조회 실패({error.status} {error.code}) — 중단")
                log(f"   {error.message}")
                return 1

            for availability in report.shape_availabilities:
                status = availability.availability_status
                # available_count는 비어 오는 경우가 있다(실측: 무료 테넌시 도쿄 AD-1).
                # 판정은 status로만 하고 count는 표시용으로만 쓴다 —
                # count를 조건에 넣으면 AVAILABLE인데도 apply를 건너뛴다.
                count = availability.available_count
                count_text = "?" if count is None else str(count)
                fault_domain = availability.fault_domain
                scope = ad_name if fault_domain is None else f"{ad_name}/{fault_domain}"
                observed.append(f"{scope}={status}({count_text})")

                if status == STATUS_HARDWARE_NOT_SUPPORTED:
                    log(f"❌ {scope}: HARDWARE_NOT_SUPPORTED")
                    log("   이 리전에 해당 shape 하드웨어가 없다 — 설정을 바꿔야 한다")
                    return 4

                if status != STATUS_AVAILABLE:
                    continue

                if ad_name != target_ad:
                    log(f"💡 {scope}: 재고 {count_text}개 — terraform 대상 AD가 아니다")
                    log("   availability_domain 변수를 이 AD로 지정하면 잡을 수 있다")
                    continue

                # --- 2) 대상 AD에 재고가 있을 때만 apply ---
                log(f"🟢 {scope}: 재고 {count_text}개 확인 — terraform apply 실행")
                with LOG_FILE.open("a", encoding="utf-8") as log_handle:
                    # terraform 경로·인자는 모두 이 파일에서 고정한다(외부 입력 없음).
                    applied = subprocess.run(  # noqa: S603
                        [
                            terraform_bin,
                            f"-chdir={TF_DIR}",
                            "apply",
                            "-auto-approve",
                            "-no-color",
                        ],
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                if applied.returncode == 0:
                    log(f"✅ 성공 — 인스턴스 생성 완료 (시도 {attempt}회)")
                    subprocess.run(  # noqa: S603
                        [terraform_bin, f"-chdir={TF_DIR}", "output"],
                        check=False,
                    )
                    log("다음: ./scripts/oci-k3s-kubeconfig.sh 로 kubeconfig 회수")
                    return 0

                # 재고를 보고도 실패했다면 대개 경합에서 밀린 것이다.
                # 용량 오류가 아니라면 재시도해도 소용없으므로 즉시 멈춘다.
                tail = LOG_FILE.read_text(encoding="utf-8").splitlines()[-40:]
                if not any("Out of host capacity" in line for line in tail):
                    log(f"❌ 용량 부족이 아닌 오류 — 재시도 중단. {LOG_FILE} 확인")
                    print("\n".join(tail[-20:]), file=sys.stderr)
                    return 1
                log("경합에서 밀림(다른 테넌시가 선점) — 폴링 계속")

        summary = " ".join(observed) if observed else "응답에 shape_availabilities 없음"
        if ONCE:
            log(f"ONCE 지정 — 1회 조회 후 종료 · {summary}")
            return 2

        log(f"재고 없음 [{summary}]")
        log(f"   시도 {attempt}/{MAX_ATTEMPTS} — {INTERVAL}초 후 재조회")
        time.sleep(INTERVAL)

    log(f"⏱ 최대 시도({MAX_ATTEMPTS}회) 소진 — 용량 미확보")
    log("   시간대를 바꿔 다시 실행한다")
    return 2


if __name__ == "__main__":
    sys.exit(main())
