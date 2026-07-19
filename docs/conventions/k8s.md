# Kubernetes 규칙 (도입 시)

> **상태**: 현재 이 프로젝트는 **단일 호스트 compose**로 배포하며 K8s는 미사용이다.
> 아래는 **K8s로 이행할 때** 따를 규칙으로, [docker.md](docker.md)의 원칙(이미지 고정·자원 한도·
> 비밀 참조·non-root)을 K8s 리소스로 옮긴 것이다.
> **연관**: 아키텍처 개요·compose↔K8s 매핑은 [../architectures/k8s.md](../architectures/k8s.md),
> 환경변수 전파는 [../operations.md](../operations.md), 보안 통제는 [../security.md](../security.md).

## 1. 워크로드 유형

- **무상태**(dagster-webserver·daemon·trino): `Deployment`.
- **상태 저장**(postgres·seaweedfs): `StatefulSet` + `PersistentVolumeClaim`(PVC)로 데이터 유실 방지.
- 노출은 `Service`(기본 ClusterIP), 외부 진입은 필요 시 `Ingress`.

## 2. 리소스 requests/limits 필수 (compose `deploy.resources` 매핑)

모든 컨테이너에 `requests`(예약)·`limits`(상한)를 명시한다(compose와 동일 원칙).

```yaml
resources:
  requests: { cpu: "500m", memory: "1Gi" }
  limits:   { cpu: "1",    memory: "2Gi" }
```

- 수치의 단일 출처는 [../resource-sizing.md](../resource-sizing.md). `limits.memory` 합 ≤ 노드 할당가능 메모리.

## 3. 헬스체크는 probe로 (compose healthcheck 매핑)

- `readinessProbe`(트래픽 수용 준비), `livenessProbe`(교착 시 재시작), 느린 기동은 `startupProbe`.
- compose `depends_on: condition: service_healthy`는 K8s에서 **readiness gating**·initContainer로 대체한다.

## 4. 설정·비밀정보는 ConfigMap·Secret 참조 (하드코딩 금지)

- 비밀값(`POSTGRES_PASSWORD`·`AWS_*`)은 `Secret`, 일반 설정은 `ConfigMap` → `envFrom`/`valueFrom`으로 주입.
- Secret은 최소 노출: `readOnly` 볼륨·필요한 파드만. etcd 저장 암호화·외부 시크릿 매니저(External Secrets)
  검토([security.md](../security.md) §4-2 at-rest).
- **이미지 태그 고정**(`latest` 금지, [docker.md](docker.md) §1-3) + 구체 태그와 `imagePullPolicy`.

## 5. RBAC 최소권한

- 워크로드별 `ServiceAccount` 분리, 필요한 `Role`/`RoleBinding`만 부여([security.md](../security.md) 2.5).
  클러스터 전역 권한(`ClusterRole`) 남발 금지.
- `NetworkPolicy`로 파드 간 통신 최소화(기본 deny + 허용 리스트).

## 6. 보안 컨텍스트

- `securityContext`: `runAsNonRoot: true`·`runAsUser: 1000`([docker.md](docker.md) Dockerfile 규칙과 일관)·
  `readOnlyRootFilesystem`·`allowPrivilegeEscalation: false`·불필요 capability drop.

## 7. 패키징은 Helm

- 환경별 차이는 `values-<env>.yaml`로 분리(값 오버라이드), 템플릿은 공통. 차트 버전·appVersion을 관리한다.
- compose profiles(옵션 기능)는 Helm values 토글(`monitoring.enabled` 등)로 옮긴다.

## 8. Dagster on K8s

- run 실행은 `dagster-k8s`의 `K8sRunLauncher`(run마다 파드). 스케줄·센서는 daemon `Deployment`.
- daemon in-process 서브프로세스 모델에서 이탈하므로, run 파드에도 자원 requests/limits와
  **env 전파를 재확인**한다([operations.md](../operations.md) §1-1).

## 참고

- Kubernetes 문서: https://kubernetes.io/docs/home/
- 리소스 관리(requests/limits): https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- Probe: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- ConfigMap·Secret: https://kubernetes.io/docs/concepts/configuration/secret/
- RBAC: https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- Helm: https://helm.sh/docs/
- dagster-k8s: https://docs.dagster.io/deployment/oss/deployment-options/kubernetes
