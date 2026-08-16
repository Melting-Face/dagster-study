# Terraform·프로바이더 버전 고정 (재현성 — latest 금지, docs/conventions 원칙)
# 설치 시점 최신 확인: https://registry.terraform.io/providers/oracle/oci/latest
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 6.0"
    }
  }
}
