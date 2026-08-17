# OCI + Terraform + k3s (아키텍처 · 프로젝트 관점)

## 개요

**OCI(Oracle Cloud Infrastructure) Always Free** 등급의 **Ampere A1(ARM64)** 컴퓨트에 **k3s**
(경량 CDN 인증 Kubernetes 배포판)를 **Terraform + cloud-init**으로 올려, 로컬 kind 재설계를
**클라우드로 이행**하는 경로다. Dagster는 여전히 **호스트(컨트롤 플레인)**, k3s는 **원격 컴퓨트**다
([redesign.md](../redesign.md)의 토폴로지 유지).

- **k3s**: 단일 바이너리 K8s. etcd 대신 기본 SQLite, containerd 내장, 인증받은 배포판(CNCF conformant).
  엣지·소규모·홈랩·CI에 적합.
- **Always Free A1**: 테넌시당 **월 1,500 OCPU시간 + 9,000 GB시간**(≈ **2 OCPU/12 GB** 상시), 블록스토리지 200 GB
  무료. ARM64이므로 컨테이너 이미지는 **arm64 빌드**가 필요하다.
  > **2026-06-15 한도 축소**: 4 OCPU/24 GB → **2 OCPU/12 GB**(절반). 기존 초과 사용분은 2026-08-18까지 축소하지 않으면
  > 종료된다고 Oracle이 통보했다. 초과 설정은 **과금**되므로 `variables.tf`에 `validation`으로 상한을 걸어뒀다.
  > 출처: [Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) ·
  > [Oracle Cloud Customer Connect 공지](https://community.oracle.com/customerconnect/discussion/970310/oci-always-free-updated-ampere-a1-compute-allocation)

## 이 프로젝트에서의 위치 — 🔎 학습·확장 경로(로컬 이후)

- **채택 방향**: 로컬 **kind on Podman**(6 CPU/16 GB 상한)으로 검증한 K8s 재설계를, **비용 0**의
  상시 클러스터(**2 OCPU/12 GB**)에서 재현한다. 포트폴리오상 "IaC(Terraform)로 클라우드 K8s 프로비저닝"
  경험을 더한다.
  > 한도 축소(2026-06) 이후 클라우드 쪽이 로컬(6 CPU/16 GB)보다 **작다**. "더 큰 클러스터"가 아니라
  > **상시 가동·IaC 경험**이 채택 이유로 남는다.
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

- **A1 용량 부족(Out of host capacity, HTTP 500)**: 무료 A1은 인기가 높아 `apply`가 용량 오류로 실패한다.
  **시간차 재시도가 유일한 무료 해법**이다 → [`scripts/oci-k3s-retry-apply.sh`](../../scripts/oci-k3s-retry-apply.sh)
  (기본 5분 간격·72회, 용량 부족 외 오류는 즉시 중단).
  - **shape을 줄여도 소용없다** — 2026-08-17 실측: 4/24·2/12·1/6 **모두 동일 실패**. 크기가 아니라 호스트 재고 문제다.
  - **쿼터와 용량은 다른 축이다** — 같은 시점 `oci_limits_resource_availability` 조회 결과 `standard-a1-core-count`
    한도 41·사용 0으로 **쿼터는 여유**였다. 500이 나와도 한도를 의심할 필요는 없다.
  - **AD·리전 우회는 사실상 불가** — Always Free는 **홈 리전 전용**이고 홈 리전은 **변경 불가**
    ([Managing Regions](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingregions.htm)).
    `ap-tokyo-1`은 AD도 1개라 AD 변경 여지도 없다.
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
