# Kubernetes 규칙 (이행)

> **상태**: 🚧 **채택·이행중**. 재설계로 **컴퓨트·데이터 서비스를 K8s로 이전**하되 **Dagster는 호스트에 유지**한다
> (오케스트레이터↔원격 컴퓨트 분리). 전체 로드맵은 [../redesign.md](../redesign.md), PoC 게이트는 그 Phase 0.
> 아래 §1~8은 [docker.md](docker.md)의 원칙(이미지 고정·자원 한도·비밀 참조·non-root)을 K8s 리소스로 옮긴 공통 규칙,
> §9~12는 **본 재설계 고유 규칙**(Spark Operator·호스트 Dagster 트리거·로컬 클러스터·CNPG 카탈로그 PG)이다.
> **연관**: 아키텍처 [../architectures/k8s.md](../architectures/k8s.md)·[../architectures/spark.md](../architectures/spark.md),
> 환경변수 전파 [../operations.md](../operations.md), 보안 통제 [../security.md](../security.md).

## 1. 워크로드 유형

- **오퍼레이터/컨트롤러**(Spark Operator·Flink Operator): `Deployment`.
- **컴퓨트 잡**(Spark driver/executor·Flink JM/TM): 오퍼레이터가 CRD(`SparkApplication`·`FlinkDeployment`)로 생성.
- **상태 저장**(seaweedfs·redpanda): `StatefulSet` + `PersistentVolumeClaim`(PVC)로 데이터 유실 방지.
  단 **카탈로그 postgres는 오퍼레이터(CNPG)** 가 관리한다(§12) — 파드·PVC·서비스를 오퍼레이터가 만든다.
  🔴 **`emptyDir`를 상태 저장에 쓰지 않는다** — 2026-08-19까지 카탈로그 PG가 `emptyDir`였고,
  파드 재기동만으로 Iceberg 테이블 메타가 전부 소멸하는 상태였다(S3 parquet은 남아 "부분 생존"으로 보인다).
- 노출은 `Service`(기본 ClusterIP), 외부 진입은 필요 시 `Ingress`. (**Dagster는 호스트**라 클러스터 밖, §8)

## 2. 리소스 requests/limits 필수 (compose `deploy.resources` 매핑)

모든 컨테이너에 `requests`(예약)·`limits`(상한)를 명시한다(compose와 동일 원칙).

```yaml
resources:
  requests: { cpu: "500m", memory: "1Gi" }
  limits:   { cpu: "1",    memory: "2Gi" }
```

- 수치의 단일 출처는 [../resource-sizing.md](../resource-sizing.md). `limits.memory` 합 ≤ 노드 할당가능 메모리.
- **예외는 외부 매니페스트를 그대로 적용하는 경우뿐**이고, 그때는 예외임을 기록한다.
  현재 유일한 예외는 **ingress-nginx**(kind provider `deploy.yaml`) — `requests` 100m/90Mi만 있고
  **`limits`가 없다**(2026-08-19 실측). 상주 부하가 작아 수용하되, 자체 오버레이로 값을 얹는 것은 후속 과제로 둔다.

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

- **실행 전제**(2026-08-18 배선 완료): 호스트 실행 시 `DAGSTER_HOME=dagster/dockerfile.d/src`(=`dagster.yaml` 위치),
  `POSTGRES_HOST=localhost`(`.env`), compose `postgres`는 `127.0.0.1:${POSTGRES_PORT}:5432`로 퍼블리시.
  값이 컨테이너/호스트에서 갈리는 이유는 [../operations.md](../operations.md) §1-2.
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

> ⏸ **현재 미설치**(2026-08-19). Phase 0 검증 후 `flink-session`·Flink Operator·cert-manager를
> 제거했다 — 잡 없는 세션 클러스터가 **1 CPU / 2Gi를 상주 점유**해 §9-3 시분할 규약을 어겼기 때문이다.
> 아래 규칙과 매니페스트·러너 이미지는 **Phase 3 재개용으로 그대로 유효**하며
> `INSTALL_FLINK=true ./scripts/k8s-operators.sh`로 복구한다(`INSTALL_FLINK` 기본값은 `false`).
> 🔴 세션 클러스터는 **잡이 없어도 JM이 상주**한다(아래 Web UI 항목) — 이게 자원이 조용히 새는 경로다.
> 검증이 끝나면 반드시 내린다.

- **오퍼레이터**: Apache **Flink Kubernetes Operator**를 Helm으로 설치하고, 스트리밍 잡은 **`FlinkDeployment`(CRD)** 로 선언한다.
  JobManager/TaskManager 자원(`memory`·`cpu`)을 명시한다(§2, 수치는 [../resource-sizing.md](../resource-sizing.md)).
  CRD는 `flink.apache.org/**v1beta1**` 단일(2026-08-18 실측, operator 1.15.0).
- **차트 버전은 설치 시점에 반드시 확인**한다 — `downloads.apache.org/flink/`는 **현행 릴리스만** 보관해
  구버전 차트 URL이 **404**가 된다(2026-08-18: 핀돼 있던 `1.10.0`이 사라져 설치 불가 → `1.15.0`으로 갱신).
  `curl -s https://downloads.apache.org/flink/ | grep flink-kubernetes-operator`로 대조 후 `k8s-env.sh`에 핀한다.
- **버전 짝은 엔진이 아니라 Iceberg가 정한다**: `iceberg-flink-runtime-<flinkMinor>` 아티팩트는
  **2.1까지만 존재**한다(`-2.2`는 Maven Central 404, 2026-08-18). 오퍼레이터 CRD가 `v2_2`를 받아줘도
  Iceberg가 없으면 무의미하므로 **Flink는 2.1 계열로 고정**한다(현재 `flink:2.1.3-java17` + Iceberg `1.11.0`).
- **`watchNamespaces={<잡 ns>}`를 반드시 준다** — 비우면 잡 SA(`flink`)와 Role이 **오퍼레이터 ns에만** 생겨
  잡 ns에서 파드가 못 뜬다(Spark 차트의 `workloadResources.namespaces`와 같은 함정).
  단, 지정하면 RBAC이 네임스페이스로 좁아지면서 **두 구멍**이 생긴다 → 아래 보완 매니페스트로 메운다.
  - `k8s/flink/flink-operator-webhook-rbac.yaml` — mutating webhook이 `flinkdeployments`를
    **클러스터 스코프로 list**한다. 없으면 `FlinkSessionJob` 생성 자체가 403으로 거부된다.
  - `k8s/flink/flink-workload-rbac.yaml` — JM 파드 **안에서** 잡을 제출하면 `<name>-rest` **Service를 조회**한다.
    없으면 **DDL·SHOW는 되는데 쿼리 실행만** `services ... is forbidden`으로 실패해 원인을 헷갈리게 한다.
- **`jarURI: local://`은 application 모드 전용**이다. `FlinkSessionJob`은 **오퍼레이터가 jar를 받아** JM에
  업로드하므로 Flink FileSystem 스킴(`https://` 등)이 필요하고, `local://`은
  `UnsupportedFileSystemSchemeException`으로 죽는다. (webhook 허용목록
  `kubernetes.operator.user.artifacts.allowed-schemes`를 통과시켜도 **아티팩트 단계에서 별도로** 막힌다 — 층이 다르다.)
  이미지에 구운 jar를 쓰려면 **application 모드**(`FlinkDeployment.spec.job`)로 선언한다.
- **Hadoop 클래스는 Flink 이미지에 없다**(Spark 이미지와 다른 지점). Iceberg의 `FlinkCatalogFactory`가
  `org.apache.hadoop.conf.Configuration`을 로드하므로 `CREATE CATALOG`에서 `ClassNotFoundException`이 난다.
  레거시 `flink-shaded-hadoop-2-uber` 대신 Spark 러너와 **같은 계열의 shaded 클라이언트**
  (`hadoop-client-api`·`hadoop-client-runtime` 3.3.4)를 `/opt/flink/lib`에 넣는다.
- **크리덴셜은 SQL DDL에 쓰지 않는다** — `sql-client`가 실행문을 **그대로 echo**해 터미널·로그에 평문이 남는다
  (2026-08-18 실측). S3 키는 표준 env(`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`)로 넣어 **S3FileIO의 기본
  자격증명 체인**이 집어가게 하고 DDL에서 뺀다. Secret→env 주입은 `podTemplate`으로 한다(§4).
- **Web UI**: 오퍼레이터가 `<name>-rest`(8081) Service를 만든다. 호스트에서는
  `kubectl port-forward svc/<name>-rest 8081:8081`(§10). **세션 클러스터는 잡이 없어도 JM이 상주**해
  UI가 계속 살아 있다(Spark의 driver UI가 잡 종료와 함께 사라지는 것과 대비 —
  [../architectures/flink.md](../architectures/flink.md)). TaskManager는 잡 제출 시 온디맨드로 뜬다.
- **검증 상태**(2026-08-18): 세션 클러스터(`k8s/flink/flinkdeployment-session.yaml`)에서
  **Spark가 쓴 Iceberg 테이블을 Flink가 읽는 것까지 확인** — `SHOW DATABASES`→`poc`,
  `SELECT * FROM poc.sample`→3행(alice/bob/carol). 카탈로그·S3는 Spark와 **동일한 JDBC 카탈로그 + SeaweedFS**.
- **소스·싱크·상태**: 소스=**Redpanda**(Kafka API), 싱크=Iceberg(§11 공유 카탈로그), 체크포인트=SeaweedFS(S3, path-style),
  상태 백엔드=RocksDB. 러너 이미지는 `iceberg-flink-runtime`+S3A 의존을 포함해 로컬 레지스트리에 push한다(§10 이름 규칙).
- **역할 경계**: **배치는 Spark, 스트림은 Flink**로 분리한다(엔진 중복 금지). ad-hoc SQL은 Spark SQL로 대체(Trino 제거).

## 9-3. 컴퓨트 시분할 (6/16 예산)

- **BATCH(Spark)와 STREAM(Flink)은 동시 실행하지 않는다**(단일 PC 6 CPU/16 GB에서 동시 피크가 예산 초과).
  한 번에 한 엔진만 띄우고, 대기 엔진 파드는 0으로 스케일한다. 근거·배분은 [../resource-sizing.md](../resource-sizing.md) "Kubernetes 재설계 시나리오".
- Redpanda·Flink JM/TM는 **스트리밍 데모 중에만** 상주시키고, 종료 후 스케일 0으로 자원을 회수한다.
- 🔴 **이 규칙은 2026-08-19에 실제로 깨져 있었다** — Phase 0 검증용 `flink-session`이 잡 없이 13시간
  상주하며 `spark-connect`와 **동시 점유**(합 1.5 CPU / 3.5Gi requests)했다. 발견 경로는 성능 이상이 아니라
  **"안 쓰는 것 정리"** 였다. 규약이 문서에만 있고 **회수 시점을 아무도 트리거하지 않으면** 이렇게 샌다.
  → 검증·데모가 끝나는 **그 자리에서** 내린다. 상주 컴퓨트는 주기적으로 `kubectl get pods -A`로 대조한다.

## 10. 호스트 Dagster → 로컬 K8s 트리거·연결 규칙

- **트리거 수단**: 자산은 `dagster-k8s`의 **`PipesK8sClient`** 로 파드/Job(또는 `SparkApplication`·`FlinkDeployment` 러너)을
  런칭하고, **로그·asset check·materialization을 Pipes 채널로 회수**한다. 컨텍스트는 env, 메시지는 파드 로그로 전달된다.
- **로컬 배포판**: **kind on Podman(rootful)**. macOS에선 Podman이 **VM(podman machine)** 안에서 동작하고 kind는 그 VM
  안 컨테이너로 노드를 만든다. kind Podman provider는 experimental이라 **rootful 머신이 필수**이며,
  `export KIND_EXPERIMENTAL_PROVIDER=podman` 후 `kind create cluster` 한다. VM 자원(6/16)은 [../resource-sizing.md](../resource-sizing.md).
- **로컬 레지스트리**: kind 공식 local-registry 방식을 쓴다 — containerd `config_path` 설정으로 **`localhost:5001`이
  호스트·클러스터 내부 공통**으로 동작한다. `spark.kubernetes.container.image` 등 매니페스트도 `localhost:5001/...` 로 참조한다.
  (참고: k3d는 내부/외부 이름이 달라 매니페스트에 내부 이름을 써야 하는 함정이 있으나, kind는 공통 이름으로 회피된다.)
- **러너 이미지 빌드·배포**: 레지스트리에 **직접 push**한다(`kind load` 불필요 — 위 배선 덕분).
  빌드 컨텍스트는 각 러너 디렉터리이고, 태그는 **구체 버전 고정**(§9)이다.

  ```shell
  podman build -f k8s/spark/Dockerfile.spark-runner -t localhost:5001/spark-runner:0.4.0 k8s/spark
  podman push --tls-verify=false localhost:5001/spark-runner:0.4.0
  ```

  **태그를 올렸으면 그 태그를 참조하는 매니페스트를 함께 올린다** — 한쪽만 올리면 구 이미지가 계속 돈다.
  참조처: `k8s/spark/spark-connect-server.yaml`·`k8s/spark/sparkapplication-poc.yaml`(Spark),
  `k8s/flink/flinkdeployment-session.yaml`(Flink).
  현행 태그는 **`spark-runner:0.4.0`**(Iceberg·S3A·Spark Connect) / **`flink-runner:0.2.0`**(Iceberg·shaded hadoop).
- 🔴 **Iceberg의 `io-impl`(S3FileIO)만으로는 부족한 작업이 있다** — `spark.hadoop.fs.s3*`(S3A)를 **함께** 준다.
  S3FileIO는 **카탈로그가 아는 파일**만 다루므로, warehouse 디렉터리를 직접 나열해야 하는
  `remove_orphan_files`(카탈로그가 *모르는* 파일을 찾는 게 목적)는 **Hadoop FileSystem**을 탄다.
  설정이 없으면 `UnsupportedFileSystemException: No FileSystem for scheme "s3"`로 죽는다(2026-08-19 실측).
  warehouse가 `s3://`라 **`fs.s3.impl`도 S3A로 매핑**해야 하고(`fs.s3a.impl`만으론 안 잡힌다),
  jar(`hadoop-aws`·`aws-java-sdk-bundle`)는 러너 이미지에 이미 있어 **설정만** 추가하면 된다.
  S3A는 AWS SDK **v1**이라 SeaweedFS의 aws-chunked 문제(SDK v2 flexible checksum)와는 무관하다.
  참조: `k8s/spark/spark-connect-server.yaml`.
- **서비스 접근**: **웹 UI는 Ingress**(고정 URL), **데이터 접속은 `port-forward`** 를 기본으로 한다.
  Dagster 리소스(SeaweedFS·카탈로그 DB 엔드포인트)는 이 노출 주소를 `EnvVar`로 주입한다(하드코딩 금지, §4).
- 🔴 **kind는 공개 포트를 클러스터 생성 시점에만 정할 수 있다.** 노드가 컨테이너라 사후에 포트를 추가할 수 없어,
  `kind-cluster.yaml`에 **`extraPortMappings`가 없으면 Ingress·NodePort 둘 다 호스트에서 닿지 않는다**
  (`hostNetwork: true`도 소용없다 — 노드는 podman VM 안이라 VM 네트워크까지만 닿는다).
  빠뜨렸다면 **클러스터 재생성**이 유일한 방법이므로 처음부터 넣어둔다(2026-08-19 실측 후 도입).
  - 호스트 포트는 **8080/8443**을 쓴다. macOS에서 1024 미만 바인딩은 root가 필요한데
    podman의 포트 포워딩(gvproxy)은 사용자 권한으로 돈다.
  - 재생성 시 **`k8s-down.sh`를 쓰지 말고 `kind delete cluster`만** 한다. down 스크립트는
    **레지스트리까지 지워** 러너 이미지를 잃는다(재빌드 수 분). 클러스터만 지우면 `k8s-up.sh`가 멱등적으로 다시 붙인다.
- **Ingress 규칙**: 컨트롤러는 **ingress-nginx**(kind provider 매니페스트, 버전은 `k8s-env.sh`에 핀).
  호스트명은 **`<service>.localtest.me`** — 공개 DNS가 127.0.0.1로 응답해 `/etc/hosts` 수정이 필요 없다.
  - Flink는 오퍼레이터 네이티브 **`FlinkDeployment.spec.ingress`**(`template`·`className`)를 쓴다.
  - Spark(Connect UI)는 일반 `Ingress` 리소스로 4040을 노출한다. **gRPC(15002)는 Ingress로 내보내지 않는다**
    — nginx의 gRPC 백엔드는 TLS 등 별도 설정이 필요하고, dbt는 port-forward/in-cluster 주소로 충분하다(YAGNI).
  - 설치 대기는 `wait --for=condition=ready pod`가 아니라 **`rollout status deploy/...`** 로 한다.
    파드 생성 전이면 전자는 `no matching resources found`로 **즉시 실패**한다(2026-08-19 실측).
  - 기동 직후 컨트롤러가 **liveness 실패로 1회 재시작**할 수 있다(노드가 다른 롤아웃으로 바쁠 때
    `/healthz` 타임아웃). 자체 회복하므로 곧바로 실패로 판단하지 않는다.
- **`kubectl proxy`는 UI 대안으로 쓰지 않는다**: Flink는 동작하지만 **Spark UI는 302 `Location`이
  프록시 포트가 아니라 API 서버 주소를 가리켜** 브라우저가 따라가지 못한다(2026-08-19 실측).

## 11. 오브젝트 스토어·Iceberg 카탈로그 정합

- **SeaweedFS는 path-style 전용**: Spark·Trino 양쪽에서 path-style 접근을 강제한다
  (Spark `spark.hadoop.fs.s3a.path.style.access=true`). 미설정 시 버킷 DNS 서브도메인 가정으로 접근 실패.
- **공유 JDBC 카탈로그**: Spark·Flink·Dagster(pyiceberg)·dbt가 **동일 Postgres 기반 Iceberg JDBC 카탈로그**를
  공유한다(낙관적 동시성). 메타 테이블(`iceberg_tables`·`iceberg_namespace_properties`) 스키마를 동일하게 유지한다.
  장기적으로 REST 카탈로그(Nessie·Polaris·lakekeeper) 이행은 후속 과제([../redesign.md](../redesign.md) 급소②).
- 🔴 **카탈로그 이름은 전 엔진이 같아야 한다 — 정본은 `iceberg`.**
  JDBC 카탈로그는 `catalog_name` 컬럼으로 네임스페이스·테이블 레지스트리를 **분할**한다.
  이름이 다르면 **같은 DB·같은 버킷을 봐도 서로의 테이블이 보이지 않는다**(빈 카탈로그처럼 동작).
  2026-08-18 실측: Spark/Flink가 `jdbccat`, Dagster/Trino가 `iceberg`로 갈려 있어
  Dagster 적재분이 Spark에서 보이지 않을 상태였다 → `iceberg`로 통일하고 기존 행을 마이그레이션했다.
  설정 위치: Spark `spark.sql.catalog.<name>`·`ICEBERG_CATALOG_NAME`(러너 env) / Flink `CREATE CATALOG <name>` /
  Dagster `common/constants.py:CATALOG_NAME` / Trino `iceberg.jdbc-catalog.catalog-name`.
- 🔴 **SeaweedFS는 AWS SDK의 flexible checksum(aws-chunked)을 풀지 못한다.**
  최신 SDK는 PutObject에 CRC64NVME 체크섬을 기본 적용하며 본문을 청크로 감싸는데, SeaweedFS가 이를
  해제하지 않아 **프레이밍 바이트가 객체 내용에 그대로 저장**된다
  (2026-08-18 실측: Iceberg `metadata.json`이 `11\r\n{...}\r\n0\r\nx-amz-checksum-...`로 저장 →
  다음 읽기에서 pyiceberg가 JSON 파싱 실패). **오류가 쓰기가 아니라 이후 읽기에서 나므로 추적이 어렵다.**
  → `AWS_REQUEST_CHECKSUM_CALCULATION=when_required`(+`AWS_RESPONSE_CHECKSUM_VALIDATION`)로 끈다.
  코드에도 `common/constants.py`가 `os.environ.setdefault`로 기본값을 못 박는다(환경 누락 시 조용한 손상 방지).
  Java SDK 경로(Spark·Flink의 iceberg-aws-bundle)는 영향받지 않는다 — 파이썬(pyiceberg/pyarrow·boto3) 경로만 해당.

## 12. 카탈로그 Postgres = CloudNativePG(CNPG) 규칙

- **오퍼레이터**: [CloudNativePG](https://cloudnative-pg.io/)(CNCF). `scripts/k8s-operators.sh`가 Helm으로
  `ns=cnpg-system`에 설치하고, `Cluster` CR은 `k8s/catalog-postgres.yaml`(적용은 `k8s-poc-storage.sh`).
- 🔴 **차트 버전 ≠ appVersion**(§9 Spark 오퍼레이터와 같은 함정): chart **0.29.0** = CNPG **1.30.0**.
  `helm search repo cnpg/cloudnative-pg --versions`로 대조하고 `k8s-env.sh`의 `CNPG_CHART_VERSION`에 핀한다.
- 🔴 **서비스 이름에 접미사가 붙는다** — `<cluster>-rw`(쓰기)·`-ro`(읽기 전용)·`-r`(전체)만 생기고
  `<cluster>` 이름의 서비스는 **만들어지지 않는다**. jdbc URI는 `catalog-postgres-rw:5432`다.
- 🔴 **자동생성 시크릿(`<cluster>-app`)을 쓰지 않는다** — 호스트 Dagster가 이 DB에 직접 붙으므로
  (`.env`의 `ICEBERG_CATALOG_*`) 오퍼레이터가 만든 비밀번호는 사람이 `.env`로 옮겨야 하고, 그 동기화가
  어긋나면 §11의 "부분 성공" 드리프트가 재현된다. → `bootstrap.initdb.secret`으로 **선언 시크릿**
  `catalog-pg-app`(type `kubernetes.io/basic-auth`, 키 `username`/`password` 고정)을 지정하고,
  값의 단일 출처는 `scripts/k8s-poc-storage.sh`(env override)로 둔다.
  PG 크리덴셜은 `lakehouse-creds`(S3 전용)와 **분리**한다 — 같은 비밀번호를 두 시크릿에 두지 않는다.
- 🔴 **`bootstrap.initdb.secret`은 "초기화 1회"다 — 스크립트 재실행으로 비밀번호가 회전되지 않는다.**
  `PG_PASSWORD=새값 ./scripts/k8s-poc-storage.sh`를 돌리면 **k8s Secret만 바뀌고 DB 롤은 옛 값 그대로**다.
  그러면 Secret을 읽는 Spark·Flink는 인증에 실패하고 `.env`를 읽는 호스트 Dagster는 성공해
  **위 "부분 성공" 드리프트가 축만 바꿔 재현된다**(2026-08-19 `security`·`devops-qa` 감사 공통 지적).
  CNPG가 시크릿 변경을 롤에 반영하는 것은 **`spec.managed.roles`로 선언한 롤뿐**이고
  `bootstrap.initdb`로 만든 계정은 대상이 아니다(CNPG `declarative_role_management` 문서).
  → **회전 절차**: ① `ALTER ROLE iceberg PASSWORD ...`(또는 `spec.managed.roles` 도입) ②`catalog-pg-app`
  갱신 ③ `.env` 갱신 ④ Spark·Flink 워크로드 재기동. **셋 중 하나라도 빠지면 부분 성공이 난다.**
- 🔴 **`bootstrap.initdb.owner`와 시크릿 `username`은 반드시 같아야 한다**(CNPG 문서 명시).
  CR의 `owner`는 리터럴이라 `PG_USER` env override와 자동으로 맞춰지지 않으므로,
  `k8s-poc-storage.sh`가 **적용 전에 CR의 `owner`와 `PG_USER`를 대조해 불일치 시 중단**한다.
- **probe(§3)·RBAC(§5)·securityContext(§6)는 CR에 쓰지 않는다 — 오퍼레이터가 채운다.**
  2026-08-19 `kubectl get pod catalog-postgres-1 -o yaml` 실측: `runAsNonRoot:true`·uid/gid `26`·
  `readOnlyRootFilesystem:true`·`capabilities.drop:[ALL]`·`seccompProfile:RuntimeDefault`,
  `/healthz`·`/readyz`·`/startupz` 3종 probe, 전용 SA·Role(자기 시크릿에 `resourceNames` 한정)이 모두 자동 생성된다.
  **CR에 없다고 위반으로 읽지 않는다**(정적 감사의 거짓 갭). 반대로 중복 선언해 오퍼레이터 값과 충돌시키지도 않는다.
- **operand 이미지 태그를 명시**한다(§4 `latest` 금지). 형식은 `MM.mm-TYPE-OS`
  ([postgres-containers](https://github.com/cloudnative-pg/postgres-containers)). `system` 타입은 deprecated이므로
  **`standard`** 를 쓴다(백업은 in-tree가 아닌 플러그인 경로라 barman 바이너리가 이미지에 필요 없다).
- **백업·PITR은 Barman Cloud 플러그인(CNPG-I)** 으로 한다 — in-tree barman-cloud는 **CNPG 1.31.0에서 제거 예정**.
  전제는 CNPG ≥ 1.26 + **cert-manager**다. cert-manager는 Flink Operator 웹훅과 **공용**이라
  `k8s-env.sh`의 `ensure_cert_manager` 헬퍼가 있으면 재사용·없으면 설치한다(멱등).
  ⚠️ 2026-08-19 현재 클러스터에 cert-manager는 **없다**(Flink 정리 시 함께 제거) — 백업을 켜면 이 헬퍼가 다시 깐다.
  백업 대상은 클러스터 내부 **SeaweedFS(S3)** 로 두어 외부 비용을 만들지 않는다.
  `INSTALL_CNPG_BACKUP=true`로 opt-in한다(§`profiles`와 같은 "뼈대는 항상 / 옵션은 opt-in" 원칙).
  ⚠️ **현재 백업은 미구성**이다(기본값 `false`, cert-manager도 부재).
  🔴 **이 백업은 DR이 아니다** — 백업본이 원본과 **같은 노드·같은 호스트 디스크**에 놓이므로
  노드/PVC 유실 시 함께 사라진다. 목적은 **논리 오류·실수 복구**로 한정한다. 또 SeaweedFS S3는 `http://`
  평문이라 WAL·base backup이 평문 전송·저장된다(카탈로그 DB는 테이블 식별자·메타 포인터만 담아
  PHI 경로는 아니다 — [security.md](../security.md) 4-4).
- 🔴 **PVC 사후 확장이 안 된다** — kind 기본 SC(`rancher.io/local-path`)는 `ALLOWVOLUMEEXPANSION=false`다
  (2026-08-19 실측). 용량은 처음에 넉넉히 잡고, 늘리려면 클러스터 재생성이다.
- **메타 Postgres(Dagster)는 이 규칙 밖**이다 — compose(호스트)에 남긴다(§8 호스트 Dagster, 순환 의존 회피).

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
- CloudNativePG: https://cloudnative-pg.io/ · 릴리스: https://cloudnative-pg.io/releases/ · 차트: https://github.com/cloudnative-pg/charts
- CloudNativePG Barman Cloud 플러그인: https://cloudnative-pg.io/plugin-barman-cloud/docs/installation/
- kind Podman provider(rootless/rootful): https://kind.sigs.k8s.io/docs/user/rootless/
- kind 로컬 레지스트리: https://kind.sigs.k8s.io/docs/user/local-registry/
