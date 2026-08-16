# OCI 프로바이더 — API 키 인증. 값은 tfvars/환경변수로 주입한다(하드코딩·커밋 금지).
# API 키 발급: 콘솔 > 프로필 > User Settings > API Keys > Add API Key
#   생성 시 내려받는 config 스니펫에 tenancy/user/fingerprint/region이 포함된다.
provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}
