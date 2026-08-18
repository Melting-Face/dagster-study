# Kubernetes (아키텍처 · 프로젝트 관점)

## 개요

Kubernetes(K8s)는 **컨테이너 오케스트레이션 플랫폼**이다. 다중 노드 클러스터에서 파드(pod)를
스케줄링하고, 선언적 desired-state로 **자가치유·오토스케일·롤링 업데이트·서비스 디스커버리**를
제공한다. control plane(API server·scheduler·controller·etcd)과 worker(kubelet)로 구성된다.

- 최신 안정: **v1.36**(2026-06). N-2 지원(최근 3개 마이너에 유지보수 제공).

## 이 프로젝트에서의 위치 — 🚧 채택·이행중(PoC 게이트)

- **채택 방향**: 확장성/성능 한계 극복 + 학습·포트폴리오를 위해 **컴퓨트·데이터 서비스를 K8s로 이전**한다.
  단, **Dagster는 호스트 PC**(컨트롤 플레인)에 남기고 클러스터를 **원격 컴퓨트**로 트리거한다(오케스트레이터↔컴퓨트 분리).
  전면 이행은 **PoC 성공을 전제**로 단계적으로 진행한다. 전체 로드맵은 [../redesign.md](../redesign.md).
- **로컬 배포판**: **kind on Podman(rootful)** + 로컬 레지스트리. 호스트 Dagster는 kubeconfig로 클러스터 API에 접근한다.
- **핵심 컴포넌트**: **Spark Operator**(배치)·**Flink Operator**(스트림)로 `SparkApplication`·`FlinkDeployment`(CRD) 실행,
  Redpanda·SeaweedFS·카탈로그 Postgres를 K8s에 배포한다(**Trino 제거**). Iceberg 테이블은 Spark·Flink가 공유한다.
  **웹 UI 진입점은 ingress-nginx**로 고정 URL화한다(`*.localtest.me:8080`).
- **구축 현황(2026-08-19 실측)**: 클러스터 k8s **v1.36.1** 단일 노드.
  **Spark Operator 1.0.0**(chart 1.8.0) / **Flink Operator 1.15.0**(+cert-manager) 기동,
  **Spark Connect 서버**(dbt 접속용) 상주, SeaweedFS·카탈로그 Postgres 운영 중.
  **ingress-nginx v1.15.1**(kind provider)로 Spark·Flink UI를 `port-forward` 없이 노출.
  Dagster 자산이 `SparkApplication`을 제출해 Iceberg에 적재하고(Phase 0 게이트 통과),
  **Flink이 같은 Iceberg 카탈로그를 조회**하는 것까지 확인.
- **노출 경로의 분리**: **HTTP UI는 Ingress**, **비 HTTP(gRPC·JDBC·S3 API)는 `port-forward`**.
  kind는 **공개 포트를 클러스터 생성 시점에만** 정할 수 있어 `extraPortMappings`가 전제다
  (규칙·함정은 [../conventions/k8s.md](../conventions/k8s.md) §10).
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
  | `ports:`(호스트 퍼블리시) | `Service` + **`Ingress`**(HTTP UI) / **`port-forward`**(gRPC·JDBC·S3) |

- 배포·보안 **규칙**은 [conventions/k8s.md](../conventions/k8s.md).

## 운영 메모 (이행)

- 패키징은 **Helm 차트**(값 분리·환경별 오버라이드). 이미지 태그 고정(`latest` 금지).
- 상태 저장(Postgres·SeaweedFS)은 `StatefulSet`+PVC.
- **Spark 실행**: Apache 공식 **Spark Kubernetes Operator**(GA 1.0.0, Kubeflow에서 이전)를 Helm으로 설치(`ns=spark-operator`),
  Dagster 자산이 `PipesK8sClient`로 `SparkApplication`(CRD, `spark.apache.org/v1`)을 제출·폴링한다. 규칙은 [../conventions/k8s.md](../conventions/k8s.md) §9~11.
- **Dagster 위치 주의**: 본 프로젝트는 Dagster를 **호스트에 유지**한다. `dagster-k8s`의 `K8sRunLauncher`는
  Dagster를 **클러스터 내부에 배포**할 때 run을 파드로 실행하는 옵션으로, 본 토폴로지의 Spark 트리거 수단이
  아니다(후속 비교 과제, [../redesign.md](../redesign.md) Phase 4).

## 참고

- Kubernetes 문서: https://kubernetes.io/docs/home/
- 릴리스: https://kubernetes.io/releases/
- dagster-k8s: https://docs.dagster.io/deployment/oss/deployment-options/kubernetes
- Apache Spark Kubernetes Operator: https://apache.github.io/spark-kubernetes-operator/
- Apache Flink Kubernetes Operator: https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-main/
- kind(로컬 K8s, Podman provider): https://kind.sigs.k8s.io/
