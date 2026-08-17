# 입력 변수 — 실제 값은 terraform.tfvars(커밋 금지)에 둔다. 예시는 terraform.tfvars.example.

# --- OCI 인증 (API 키) ---
variable "tenancy_ocid" {
  description = "테넌시 OCID"
  type        = string
}

variable "user_ocid" {
  description = "사용자 OCID"
  type        = string
}

variable "fingerprint" {
  description = "API 키 지문(fingerprint)"
  type        = string
}

variable "private_key_path" {
  description = "API 개인키 경로(예: ~/.oci/oci_api_key.pem) — 저장소 밖에 둔다"
  type        = string
}

variable "region" {
  description = "OCI 리전 식별자. Always Free는 테넌시 홈 리전에서만 생성되며 홈 리전은 변경 불가(예: ap-tokyo-1)"
  type        = string
}

variable "compartment_ocid" {
  description = "리소스를 생성할 구획(compartment) OCID. 루트를 쓰면 tenancy_ocid와 동일"
  type        = string
}

# --- 네트워크 ---
variable "vcn_cidr" {
  description = "VCN CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "퍼블릭 서브넷 CIDR"
  type        = string
  default     = "10.0.1.0/24"
}

variable "allowed_ssh_cidr" {
  description = "SSH(22) 허용 소스 CIDR. 보안상 본인 IP/32로 좁히길 권장(기본 전체 개방)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "allowed_api_cidr" {
  description = "Kubernetes API(6443) 허용 소스 CIDR. 본인 IP/32 권장(기본 전체 개방)"
  type        = string
  default     = "0.0.0.0/0"
}

# --- 컴퓨트 (Always Free A1 Flex, ARM) ---
variable "name_prefix" {
  description = "리소스 이름 접두어"
  type        = string
  default     = "dagster-k3s"
}

variable "availability_domain" {
  description = "가용 도메인 이름. 빈 문자열이면 첫 번째 AD 자동 선택"
  type        = string
  default     = ""
}

variable "instance_shape" {
  description = "인스턴스 shape. Always Free ARM은 VM.Standard.A1.Flex"
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  description = "OCPU 수. A1 무료 한도 총 2(2026-06-15 4→2 축소). 초과 시 초과분 과금"
  type        = number
  default     = 2

  validation {
    condition     = var.instance_ocpus <= 2
    error_message = "A1 Always Free 한도는 총 2 OCPU다(월 1,500 OCPU시간). 초과하면 과금되므로 의도적일 때만 이 검증을 완화한다."
  }
}

variable "instance_memory_gbs" {
  description = "메모리 GB. A1 무료 한도 총 12(2026-06-15 24→12 축소). 초과 시 초과분 과금"
  type        = number
  default     = 12

  validation {
    condition     = var.instance_memory_gbs <= 12
    error_message = "A1 Always Free 한도는 총 12 GB다(월 9,000 GB시간). 초과하면 과금되므로 의도적일 때만 이 검증을 완화한다."
  }
}

variable "boot_volume_gbs" {
  description = "부트 볼륨 GB(최소 50, 무료 블록스토리지 총 200)"
  type        = number
  default     = 50
}

variable "operating_system" {
  description = "이미지 OS(oci_core_images 필터)"
  type        = string
  default     = "Canonical Ubuntu"
}

variable "operating_system_version" {
  description = "이미지 OS 버전"
  type        = string
  default     = "24.04"
}

variable "ssh_public_key_path" {
  description = "인스턴스에 주입할 SSH 공개키 경로(예: ~/.ssh/id_ed25519.pub)"
  type        = string
}

# --- k3s ---
variable "k3s_version" {
  description = "k3s 버전 핀(예: v1.31.5+k3s1). 빈 문자열이면 stable 채널 최신. 권장: 릴리스에서 핀 https://github.com/k3s-io/k3s/releases"
  type        = string
  default     = ""
}
