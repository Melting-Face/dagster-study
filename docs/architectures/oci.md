# OCI + Terraform + k3s (아키텍처 · 프로젝트 관점)

## 개요

**OCI(Oracle Cloud Infrastructure) Always Free** 등급의 **Ampere A1(ARM64)** 컴퓨트에 **k3s**
(경량 CDN 인증 Kubernetes 배포판)를 **Terraform + cloud-init**으로 올려, 로컬 kind 재설계를
**클라우드로 이행**하는 경로다. Dagster는 여전히 **호스트(컨트롤 플레인)**, k3s는 **원격 컴퓨트**다
([redesign.md](../redesign.md)의 토폴로지 유지).

- **k3s**: 단일 바이너리 K8s. etcd 대신 기본 SQLite, containerd 내장, 인증받은 배포판(CNCF conformant).
  엣지·소규모·홈랩·CI에 적합.
- **Always Free A1**: 테넌시당 **월 3,000 OCPU시간 + 18,000 GB시간**(≈ 4 OCPU/24 GB 상시), 블록스토리지 200 GB
  무료. ARM64이므로 컨테이너 이미지는 **arm64 빌드**가 필요하다.

## 이 프로젝트에서의 위치 — 🔎 학습·확장 경로(로컬 이후)

- **채택 방향**: 로컬 **kind on Podman**(6 CPU/16 GB 상한)으로 검증한 K8s 재설계를, **비용 0**으로
  더 큰 상시 클러스터(4 OCPU/**24 GB**)에서 재현한다. 포트폴리오상 "IaC(Terraform)로 클라우드 K8s 프로비저닝"
  경험을 더한다.
- **범위(현재)**: VCN·보안·A1 인스턴스·k3s 부트스트랩·kubeconfig 회수까지. 데이터스택(Spark Operator 등)은 후속.
- **코드 위치**: [`terraform/oci-k3s/`](../../terraform/oci-k3s/README.md), 회수 스크립트 `scripts/oci-k3s-kubeconfig.sh`.

### 결정 근거 — 대안 비교 (선호 순 ★)

**1) 관리형 vs 자체설치 K8s** — *자체설치 k3s 채택*

| 선택지 | 평가 | 비고 |
| --- | --- | --- |
| **k3s(자체설치)** ★★★★★ | 무료·경량·학습가치 높음 | Always Free VM에 그대로. 운영 책임은 본인 |
| OKE(관리형) ★★★☆☆ | control plane 편의 | Basic OKE control plane은 무료지만 워커는 A1, 학습상 "직접 부트스트랩" 가치가 줄어듦 |
| kubeadm ★★☆☆☆ | 표준에 가까움 | 무겁고 부트스트랩 수고 큼, 단일노드 학습엔 과함 |

**2) 자원 등급** — *Always Free A1(ARM) 채택*

| 선택지 | 평가 | 비고 |
| --- | --- | --- |
| **A1 Flex(ARM) 4/24** ★★★★★ | 비용 0·자원 최대 | **arm64 이미지 필요**. Apple Silicon 로컬과 arch 일치 |
| x86 마이크로 2대 ★★☆☆☆ | amd64 | 1 GB RAM×2로 데이터스택 부적합 |
| 유료 소형 x86 ★★★☆☆ | 자원 자유 | 과금 발생, 학습엔 과투자 |

**3) 프로비저닝** — *cloud-init 채택*

| 선택지 | 평가 | 비고 |
| --- | --- | --- |
| **cloud-init(user_data)** ★★★★★ | 선언적·재현성·SSH 비의존 | 부팅 시 1회 실행. IaC 원칙 부합 |
| remote-exec ★★★☆☆ | 직관적 | SSH 연결·순서 의존, 재현성 약함 |
| Terraform+Ansible ★★★☆☆ | 관심사 분리 | 다중노드·복잡 구성엔 유리, 단일노드엔 과함 |

**4) 토폴로지** — *단일 노드 채택* (다중/HA는 자원상 후속)

## 운영 메모

- **A1 용량 부족(Out of host capacity, HTTP 500)**: 무료 A1은 인기가 높아 `apply`가 용량 오류로 실패할 수 있다.
  다른 AD/리전 재시도 또는 시간차 재시도. (자동 재시도 루프는 미구현 — 필요 시 후속.)
- **호스트 방화벽**: OCI Ubuntu 기본 iptables가 ingress를 막는다 → cloud-init에서 6443·10250·VXLAN(8472)·
  파드/서비스 CIDR 허용(누락 시 노드 NotReady). 규칙은 [conventions/k8s.md](../conventions/k8s.md)와 정합.
- **공인 IP**: ephemeral 공인 IP는 재시작 시 변경 → kubeconfig TLS SAN 어긋남. 안정화 시 **예약 공인 IP**로 승격.
- **비밀·상태**: `terraform.tfvars`·`*.tfstate`·API 개인키·`kubeconfig-oci`는 커밋 금지([security.md](../security.md)).
  state에 민감정보가 저장되므로 장기적으로 원격 백엔드(OCI Object Storage) + 암호화 검토.
- **arm64**: 후속 데이터스택 이행 시 Spark/Flink 러너 이미지를 **arm64로 재빌드**해야 한다([redesign.md](../redesign.md)).

## 참고

- Oracle Cloud Free Tier: https://www.oracle.com/cloud/free/
- OCI Terraform Provider: https://registry.terraform.io/providers/oracle/oci/latest/docs
- oci_core_instance: https://registry.terraform.io/providers/oracle/oci/latest/docs/resources/core_instance
- k3s (공식): https://docs.k3s.io/
- k3s 릴리스(버전 핀): https://github.com/k3s-io/k3s/releases
- cloud-init: https://cloudinit.readthedocs.io/
- garutilorenzo/k3s-oci-cluster(참고 사례): https://github.com/garutilorenzo/k3s-oci-cluster
