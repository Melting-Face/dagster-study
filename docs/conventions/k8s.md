# Kubernetes 규칙 (이행)

> **상태**: 🚧 **채택·이행중**. 재설계로 **컴퓨트·데이터 서비스를 K8s로 이전**하되 **Dagster는 호스트에 유지**한다
> (오케스트레이터↔원격 컴퓨트 분리). 전체 로드맵은 [../redesign.md](../redesign.md), PoC 게이트는 그 Phase 0.
> 아래 §1~8은 [docker.md](docker.md)의 원칙(이미지 고정·자원 한도·비밀 참조·non-root)을 K8s 리소스로 옮긴 공통 규칙,
> §9~11은 **본 재설계 고유 규칙**(Spark Operator·호스트 Dagster 트리거·로컬 클러스터)이다.
> **연관**: 아키텍처 [../architectures/k8s.md](../architectures/k8s.md)·[../architectures/spark.md](../architectures/spark.md),
> 환경변수 전파 [../operations.md](../operations.md), 보안 통제 [../security.md](../security.md).

## 1. 워크로드 유형

- **오퍼레이터/컨트롤러**(Spark Operator·Flink Operator): `Deployment`.
- **컴퓨트 잡**(Spark driver/executor·Flink JM/TM): 오퍼레이터가 CRD(`SparkApplication`·`FlinkDeployment`)로 생성.
- **상태 저장**(catalog postgres·seaweedfs·redpanda): `StatefulSet` + `PersistentVolumeClaim`(PVC)로 데이터 유실 방지.
- 노출은 `Service`(기본 ClusterIP), 외부 진입은 필요 시 `Ingress`. (**Dagster는 호스트**라 클러스터 밖, §8)

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

## 8. Dagster 배치 — 본 프로젝트는 호스트 유지

- **원칙**: Dagster(webserver·daemon)는 **호스트 PC**에서 `uv run dg dev`로 실행하고, 클러스터는
  kubeconfig로 접근하는 **원격 컴퓨트**로 다룬다. run은 호스트에서 돌고, 무거운 작업만 K8s로 위임한다.
- **`K8sRunLauncher`는 쓰지 않는다**(현 토폴로지 기준). 이는 Dagster를 **클러스터 내부에 배포**해
  run마다 파드로 실행할 때의 옵션으로, "호스트 Dagster가 원격 Spark를 트리거"하는 본 설계와 목적이 다르다.
  in-cluster 배포는 후속 비교 과제로 남긴다([../redesign.md](../redesign.md) Phase 4).

## 9. Spark Operator·SparkApplication 규칙

- **오퍼레이터**: Apache 공식 **Spark Kubernetes Operator**([apache/spark-kubernetes-operator](https://github.com/apache/spark-kubernetes-operator),
  GA **1.0.0** 2026-07-26)를 Helm으로 `ns=spark-operator`에 설치한다. Kubeflow spark-operator에서 이전했다
  (공식 생태계 무게중심 이동). 오퍼레이터가 `spark-submit`을 대행하므로 자산은 명령형 submit 대신
  **선언형 `SparkApplication`(CRD)** 을 제출한다.
- **차트 버전 ≠ appVersion**(설치 시 최다 실수): GA **appVersion 1.0.0**은 **chart 1.8.0**이다.
  `--version 1.0.0`을 주면 **appVersion 0.2.0**이 깔린다. `helm search repo spark/spark-kubernetes-operator --versions`로
  대조하고 `scripts/k8s-env.sh`의 `SPARK_OPERATOR_CHART_VERSION`에 **chart 버전**을 핀한다.
- **CRD**: `apiVersion: spark.apache.org/**v1**`, `kind: SparkApplication`.
  chart 1.8.0의 CRD는 **`v1beta1`(served) + `v1`(served·**storage**) 2버전**이고 `storedVersions=["v1"]`이라
  **`v1`이 정본**이다(2026-08-18 라이브 실측 — `kubectl get crd sparkapplications.spark.apache.org -o json`).
  `v1beta1`도 served라 apply 자체는 되지만, 저장 시 `v1`로 변환되고 **`v1` 전용 필드
  (`resourceRetainDurationMillis`·`ttlAfterStopMillis`)를 못 쓴다**. 버전은 추측하지 말고 클러스터에서 읽는다.
  Kubeflow(`sparkoperator.k8s.io/v1beta2`)와 **스펙이 다르다** — Apache는 **`spec.sparkConf` 중심**(spark-submit 설정 기반)이다.
  - **PySpark 진입점**: `spec.pyFiles`(문자열). `mainApplicationFile` 필드는 **없다**
    (근거: 공식 예제 `examples/pi-python.yaml`).
  - 이미지: `spark.kubernetes.container.image`
  - Spark 런타임: `spec.runtimeVersions.sparkVersion`
  - 자원: `spark.driver.{cores,memory}`·`spark.executor.{instances,cores,memory}`(§2 원칙, 수치는 [../resource-sizing.md](../resource-sizing.md))
  - ServiceAccount: `spark.kubernetes.authenticate.driver.serviceAccountName`
  - **Secret→env**: `spark.kubernetes.{driver,executor}.secretKeyRef.<ENV>=<secret>:<key>`(§4 비밀 참조, 평문 금지)
- **버전 고정**: 오퍼레이터 차트/이미지와 Spark 런타임 태그는 **구체 버전으로 고정**한다(`latest` 금지, §4).
  최신 릴리스는 설치 시점에 [releases](https://github.com/apache/spark-kubernetes-operator/releases)에서 확인해 핀한다.
- **러너 이미지**: PySpark + `iceberg-spark-runtime`/`iceberg-aws-bundle` + `postgresql`(JDBC 카탈로그)
  + **`hadoop-aws`/`aws-java-sdk-bundle`(S3A)** 를 포함한 **전용 이미지**를 빌드해 로컬 레지스트리에 push하고,
  `spark.kubernetes.container.image`가 이를 참조한다(§10 이름 규칙 주의).
  태그는 **구체 버전 고정**(`:0.2.0` 등) — `:poc` 같은 가변 채널 태그는 `pullPolicy: Always`와 만나면
  같은 태그가 다른 내용을 가리키는 드리프트를 만든다(§4 `latest` 금지와 같은 이유).
  - **S3 접근 경로가 둘이고 역할이 다르다**(혼동 주의):
    **Iceberg `S3FileIO`**(AWS SDK v2, `iceberg-aws-bundle`)는 **테이블 데이터 I/O** 전담이고,
    **S3A**(`hadoop-aws`, AWS SDK v1)는 `s3a://` 스킴으로 **원본 파일**(csv.gz)을 읽거나 이벤트로그를 쓸 때 쓴다.
    Iceberg만 쓰는 잡은 S3A가 없어도 돌기 때문에 **부재를 알아차리기 어렵다**(2026-08-18까지 이미지에 없었다).
  - **`hadoop-aws` 버전은 베이스 이미지의 `hadoop-client-*`와 정확히 일치**시킨다
    (Spark 3.5.9 → **3.3.4**). SDK 번들 버전은 추측하지 말고 `hadoop-project` pom의
    `<aws-java-sdk.version>`을 본다(3.3.4 → **1.12.262**).
  - **S3A로 직접 쓰기(`df.write.parquet("s3a://...")`)는 SeaweedFS에서 실패한다** — 기본
    `FileOutputCommitter`가 `_temporary` **rename**에 의존하는데 오브젝트 스토어에는 rename이 없다
    (2026-08-18 실측: `Could not rename ... _temporary/...`). 필요해지면 S3A committer(magic)와
    `spark-hadoop-cloud` 의존을 추가해야 한다.
    **다만 본 설계는 영향받지 않는다** — 쓰기는 전부 Iceberg 테이블(=S3FileIO, rename 미사용)로 나가고
    S3A는 **읽기 전용**으로만 쓴다. 검증: `s3a://` csv.gz 4행 read → Iceberg 테이블 write 4행 (2026-08-18).
  - **진입점 스크립트는 driver CWD 밖에 둔다** — 이미지 WORKDIR(`/opt/spark/work-dir`)에 두면
    `spark-submit`이 `local://` 진입점을 CWD로 복사하며 **대상을 먼저 삭제**해 소스가 사라지고
    `NoSuchFileException`으로 죽는다(2026-08-17 실측). 이 레포는 `/opt/spark/app/`을 쓴다.
- **잡 네임스페이스를 반드시 지정**한다 — 차트 기본값 `workloadResources.namespaces.data`는 비어 있고
  `overrideWatchedNamespaces: true`라, 비워두면 **감시 네임스페이스가 없고 workload SA·rolebinding도 생기지 않는다**.
  설치 시 `--set workloadResources.namespaces.data[0]=<ns>`.
- **정리 권한 보완(deletecollection)**: 차트의 `spark-workload-clusterrole`은 verbs가 템플릿에 하드코딩돼
  **`deletecollection`이 빠져 있다**(values로 조정 불가). driver는 종료 시 라벨 셀렉터로 일괄 삭제를 호출하므로,
  없으면 잡이 성공해도 `*-driver-svc`·PVC가 남고 ERROR가 찍힌다. 최소권한(§5)에 맞춰 **잡 네임스페이스 한정 Role**로
  `deletecollection`만 보완한다 → `k8s/spark/spark-workload-cleanup-rbac.yaml`.
- **로그 회수를 위한 retain 정책**: 호스트 Dagster가 **종료 후** driver 로그를 읽어 materialization 메타
  (행 수 등)를 남기므로 `applicationTolerations.resourceRetainPolicy: **Always**` + `resourceRetainDurationMillis`
  (예: `600000`=10분)를 준다. `OnFailure`면 **성공 즉시 driver 파드가 삭제**돼 로그가 사라진다.
  기본값 `-1`(무기한)은 파드가 계속 쌓이므로 쓰지 않는다.
- **정기 실행**은 원칙적으로 **Dagster(호스트)** 가 주기적으로 `SparkApplication`을 제출한다(단일 오케스트레이션).
- **Dagster 쪽 상태 판정**(`defs/poc/resources.py`): Apache는 **`status.currentState.currentStateSummary`** 를 쓴다
  (Kubeflow의 `status.applicationState.state`가 아니다). **성공·실패 모두 최종 `ResourceReleased`로 수렴**하므로
  최종 상태만으로는 결과를 구분할 수 없다 → **`status.stateTransitionHistory`에 `Succeeded`가 있었는지**로 판정한다.
  오퍼레이터를 갈아끼울 때는 매니페스트·스크립트뿐 아니라 **이 글루 코드까지 함께** 옮긴다
  (2026-08-17 이전 시 누락돼 자산이 죽어 있었다).
- **검증 상태**: PoC **잡**(`k8s/spark/sparkapplication-poc.yaml`)은 Apache 오퍼레이터에서 **동작 확인됨**
  (2026-08-17 — Iceberg write+read-back `rows=3`, exitCode 0, 정리 오류 0건).
  PoC **자산**(`defs/poc/`, 호스트 Dagster 제출 경로)도 2026-08-18 Apache 스펙 이전 후 **라이브 검증 통과**:
  호스트 `dagster asset materialize` → CRD 제출·폴링 → driver 로그 회수 → materialization 메타
  `rows=3`·`driver_pod=poc-ingest-0-driver` 기록, webserver GraphQL로 노출 확인.
  → [redesign.md](../redesign.md) **Phase 0 게이트 통과**.

## 9-2. Flink Operator·FlinkDeployment 규칙 (스트리밍)

- **오퍼레이터**: Apache **Flink Kubernetes Operator**를 Helm으로 설치하고, 스트리밍 잡은 **`FlinkDeployment`(CRD)** 로 선언한다.
  JobManager/TaskManager 자원(`memory`·`cpu`)을 명시한다(§2, 수치는 [../resource-sizing.md](../resource-sizing.md)).
- **소스·싱크·상태**: 소스=**Redpanda**(Kafka API), 싱크=Iceberg(§11 공유 카탈로그), 체크포인트=SeaweedFS(S3, path-style),
  상태 백엔드=RocksDB. 러너 이미지는 `iceberg-flink-runtime`+S3A 의존을 포함해 로컬 레지스트리에 push한다(§10 이름 규칙).
- **역할 경계**: **배치는 Spark, 스트림은 Flink**로 분리한다(엔진 중복 금지). ad-hoc SQL은 Spark SQL로 대체(Trino 제거).

## 9-3. 컴퓨트 시분할 (6/16 예산)

- **BATCH(Spark)와 STREAM(Flink)은 동시 실행하지 않는다**(단일 PC 6 CPU/16 GB에서 동시 피크가 예산 초과).
  한 번에 한 엔진만 띄우고, 대기 엔진 파드는 0으로 스케일한다. 근거·배분은 [../resource-sizing.md](../resource-sizing.md) "Kubernetes 재설계 시나리오".
- Redpanda·Flink JM/TM는 **스트리밍 데모 중에만** 상주시키고, 종료 후 스케일 0으로 자원을 회수한다.

## 10. 호스트 Dagster → 로컬 K8s 트리거·연결 규칙

- **트리거 수단**: 자산은 `dagster-k8s`의 **`PipesK8sClient`** 로 파드/Job(또는 `SparkApplication`·`FlinkDeployment` 러너)을
  런칭하고, **로그·asset check·materialization을 Pipes 채널로 회수**한다. 컨텍스트는 env, 메시지는 파드 로그로 전달된다.
- **로컬 배포판**: **kind on Podman(rootful)**. macOS에선 Podman이 **VM(podman machine)** 안에서 동작하고 kind는 그 VM
  안 컨테이너로 노드를 만든다. kind Podman provider는 experimental이라 **rootful 머신이 필수**이며,
  `export KIND_EXPERIMENTAL_PROVIDER=podman` 후 `kind create cluster` 한다. VM 자원(6/16)은 [../resource-sizing.md](../resource-sizing.md).
- **로컬 레지스트리**: kind 공식 local-registry 방식을 쓴다 — containerd `config_path` 설정으로 **`localhost:5001`이
  호스트·클러스터 내부 공통**으로 동작한다. `spark.kubernetes.container.image` 등 매니페스트도 `localhost:5001/...` 로 참조한다.
  (참고: k3d는 내부/외부 이름이 달라 매니페스트에 내부 이름을 써야 하는 함정이 있으나, kind는 공통 이름으로 회피된다.)
- **서비스 접근**: 호스트 → in-cluster 서비스는 `port-forward`(개발) 또는 `NodePort`/`Ingress`로 노출한다.
  Dagster 리소스(Trino·SeaweedFS·카탈로그 DB 엔드포인트)는 이 노출 주소를 `EnvVar`로 주입한다(하드코딩 금지, §4).

## 11. 오브젝트 스토어·Iceberg 카탈로그 정합

- **SeaweedFS는 path-style 전용**: Spark·Trino 양쪽에서 path-style 접근을 강제한다
  (Spark `spark.hadoop.fs.s3a.path.style.access=true`). 미설정 시 버킷 DNS 서브도메인 가정으로 접근 실패.
- **공유 JDBC 카탈로그**: Spark·Trino가 **동일 Postgres 기반 Iceberg JDBC 카탈로그**를 공유한다(낙관적 동시성).
  메타 테이블(`iceberg_tables`·`iceberg_namespace_properties`) 스키마를 양쪽이 동일하게 보게 유지한다.
  장기적으로 REST 카탈로그(Nessie·Polaris·lakekeeper) 이행은 후속 과제([../redesign.md](../redesign.md) 급소②).

## 참고

- Kubernetes 문서: https://kubernetes.io/docs/home/
- 리소스 관리(requests/limits): https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- Probe: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- ConfigMap·Secret: https://kubernetes.io/docs/concepts/configuration/secret/
- RBAC: https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- Helm: https://helm.sh/docs/
- dagster-k8s: https://docs.dagster.io/deployment/oss/deployment-options/kubernetes
- Dagster Pipes / PipesK8sClient: https://docs.dagster.io/api/python-api/libraries/dagster-k8s
- Apache Spark Kubernetes Operator: https://apache.github.io/spark-kubernetes-operator/ · 릴리스: https://github.com/apache/spark-kubernetes-operator/releases
- Apache Flink Kubernetes Operator: https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-main/
- kind Podman provider(rootless/rootful): https://kind.sigs.k8s.io/docs/user/rootless/
- kind 로컬 레지스트리: https://kind.sigs.k8s.io/docs/user/local-registry/
