# Kubernetes (아키텍처 · 프로젝트 관점)

## 개요

Kubernetes(K8s)는 **컨테이너 오케스트레이션 플랫폼**이다. 다중 노드 클러스터에서 파드(pod)를
스케줄링하고, 선언적 desired-state로 **자가치유·오토스케일·롤링 업데이트·서비스 디스커버리**를
제공한다. control plane(API server·scheduler·controller·etcd)과 worker(kubelet)로 구성된다.

- 최신 안정: **v1.36**(2026-06). N-2 지원(최근 3개 마이너에 유지보수 제공).

## 이 프로젝트에서의 위치 — 🔎 향후 배포 옵션

- **현재 미채택**: 단일 호스트 compose로 충분하다(학습·개발). K8s의 다중 노드 복잡도는 YAGNI.
- **이행 기준(언제 K8s로)**: 다중 노드 스케일아웃, 무중단 배포, 오토스케일(HPA), 팀 다중 환경, SLA 요구.
- **compose → Kubernetes 매핑**:

  | compose | Kubernetes |
  | --- | --- |
  | service | `Deployment`(+`Service`) / `StatefulSet`(postgres·seaweedfs) |
  | `deploy.resources` | `resources.requests`·`resources.limits` |
  | healthcheck | `livenessProbe`·`readinessProbe`·`startupProbe` |
  | `depends_on` | initContainers / readiness gating |
  | profiles(옵션) | 오버레이(Kustomize)·values(Helm)로 토글 |
  | `${ENV}`·`.env` | `ConfigMap`·`Secret` 참조 |
  | volume(`:ro`) | `PersistentVolumeClaim` / configMap·secret 볼륨(readOnly) |

- 배포·보안 **규칙**은 [conventions/k8s.md](../conventions/k8s.md).

## 운영 메모 (도입 시)

- 패키징은 **Helm 차트**(값 분리·환경별 오버라이드). 이미지 태그 고정(`latest` 금지).
- 상태 저장(Postgres·SeaweedFS)은 `StatefulSet`+PVC. Dagster는 `dagster-k8s`의 run launcher로
  run을 파드로 실행할 수 있다.

## 참고

- Kubernetes 문서: https://kubernetes.io/docs/home/
- 릴리스: https://kubernetes.io/releases/
- dagster-k8s: https://docs.dagster.io/deployment/oss/deployment-options/kubernetes
