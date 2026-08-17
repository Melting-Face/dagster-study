# OCI Always Free A1 + k3s (Terraform)

OCI **Always Free**(Ampere A1, ARM64) 인스턴스 1대에 **k3s 단일 노드**를 cloud-init으로 부트스트랩한다.
호스트에서 `kubectl get nodes` 성공이 완료 게이트다. 결정 배경·대안 비교는
[`../../docs/architectures/oci.md`](../../docs/architectures/oci.md), K8s 규칙은
[`../../docs/conventions/k8s.md`](../../docs/conventions/k8s.md).

> **주의(비용/보안)**: A1은 무료 한도(**2 OCPU/12 GB**/블록스토리지 200 GB) 내에서만 무료다
> (2026-06-15부로 4/24 → **2/12 축소**, 월 1,500 OCPU시간·9,000 GB시간). 초과분은 **과금**되며
> `variables.tf`의 `validation`이 이를 막는다. `terraform.tfvars`·`*.tfstate`·
> 개인키·`kubeconfig-oci`는 **커밋 금지**(`.gitignore` 처리됨). `allowed_ssh_cidr`·`allowed_api_cidr`는
> **본인 공인 IP/32**로 좁히는 것을 권장한다.

## 구성 리소스

| 파일 | 리소스 |
| --- | --- |
| `network.tf` | VCN · Internet Gateway · Route Table · Security List · 퍼블릭 Subnet |
| `compute.tf` | A1 Flex 인스턴스(+ 최신 Ubuntu ARM 이미지 조회, AD 자동 선택) |
| `cloud-init.yaml.tftpl` | iptables 개방 → 공인 IP 발견 → k3s 설치 → 공인 IP 반영 kubeconfig 사본 |
| `provider.tf`·`variables.tf`·`outputs.tf`·`versions.tf` | 프로바이더·변수·출력·버전 고정 |

## 사전 준비

1. **OCI 계정** + Always Free 자격. ([가입](https://www.oracle.com/cloud/free/))
2. **API 키 등록**: 콘솔 > 프로필 > *User Settings* > *API Keys* > *Add API Key*.
   생성 후 내려받는 config 스니펫에 `tenancy`·`user`·`fingerprint`·`region`이 들어 있다.
   개인키(`.pem`)는 저장소 밖(예: `~/.oci/`)에 둔다.
3. **SSH 키쌍**: `ssh-keygen -t ed25519` (공개키 경로를 `ssh_public_key_path`에).
4. CLI: `terraform`(>= 1.5), `kubectl`.

## 사용

```bash
cd terraform/oci-k3s
cp terraform.tfvars.example terraform.tfvars   # 값 채우기(OCID·키 경로·리전)

terraform init
terraform validate
terraform plan
terraform apply        # A1 용량 부족(500)이면 잠시 후/다른 AD·리전으로 재시도

# kubeconfig 회수 후 접속 확인 (완료 게이트)
../../scripts/oci-k3s-kubeconfig.sh
export KUBECONFIG="$(git rev-parse --show-toplevel)/kubeconfig-oci"
kubectl get nodes -o wide      # STATUS=Ready 확인
```

정리:

```bash
terraform destroy
```

## 설계 메모

- **버전 핀**: `k3s_version`을 [릴리스](https://github.com/k3s-io/k3s/releases)에서 핀하길 권장(비우면 stable 채널).
  프로바이더는 `~> 6.0`으로 고정(`versions.tf`). *(latest 금지 — 프로젝트 컨벤션)*
- **공인 IP TLS SAN**: cloud-init이 메타데이터로 공인 IP를 발견해 `--tls-san`·`--node-external-ip`에 주입한다.
  인스턴스 중지→재시작으로 ephemeral 공인 IP가 바뀌면 SAN이 어긋나므로, 안정화가 필요하면
  **예약 공인 IP(reserved)** 로 승격한다(후속 개선).
- **호스트 방화벽**: OCI Ubuntu 이미지의 기본 iptables가 ingress를 막으므로 cloud-init에서 6443/10250/VXLAN(8472)/
  파드·서비스 CIDR를 명시 허용한다. 이 단계 누락이 "노드 NotReady"의 흔한 원인이다.
- **Traefik 비활성**: `--disable traefik`(기본 인그레스 미사용). 필요 시 별도 Ingress를 배포한다.

## 다음 단계 (후속)

k3s 위에 **Spark Operator·SeaweedFS·Iceberg 카탈로그**를 Helm으로 올려 로컬 kind 재설계
([`../../docs/redesign.md`](../../docs/redesign.md))를 클라우드로 이행한다. **arm64 러너 이미지 재빌드** 필요.
