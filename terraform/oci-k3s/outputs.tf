# 출력 — 공인 IP·접속·kubeconfig 회수 안내

output "public_ip" {
  description = "인스턴스 공인 IP"
  value       = oci_core_instance.k3s.public_ip
}

output "instance_id" {
  description = "인스턴스 OCID"
  value       = oci_core_instance.k3s.id
}

output "ssh_command" {
  description = "SSH 접속 명령"
  value       = "ssh ubuntu@${oci_core_instance.k3s.public_ip}"
}

output "kubeconfig_hint" {
  description = "kubeconfig 회수(공인 IP 반영본). 편의 스크립트는 scripts/oci-k3s-kubeconfig.sh"
  value       = "scp ubuntu@${oci_core_instance.k3s.public_ip}:/home/ubuntu/.kube/config-public ./kubeconfig-oci"
}
