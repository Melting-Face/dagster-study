# 재설계 로드맵 — 호스트 Dagster + Kubernetes(Spark Operator)

> **상태**: 🚧 **채택·이행중(PoC 게이트)**. 방향은 확정, 전면 이행은 **Phase 0 PoC 성공을 전제**로 단계적으로 진행한다.
> **동기**: 단일 호스트 compose의 확장성/성능 한계 극복 + **학습·포트폴리오**(K8s Operator·Spark-on-K8s 실전 패턴 시연).
> **연관**: 아키텍처 [architectures/k8s.md](architectures/k8s.md)·[architectures/spark.md](architectures/spark.md),
> 규칙 [conventions/k8s.md](conventions/k8s.md)·[conventions/docker.md](conventions/docker.md),
> 자원 수치 [resource-sizing.md](resource-sizing.md), 현행 스택 [architectures/overview.md](architectures/overview.md).

## 1. 배경과 목표

- **현행**: 단일 호스트 **Docker Compose**(dagster webserver/daemon·postgres·trino·seaweedfs·prometheus).
  Dagster가 in-process/subprocess로 실행하고, dbt-on-Trino가 모든 변환을 담당한다([overview.md](architectures/overview.md)).
- **한계**: 단일 노드 자원 상한(Trino 메모리 제약·[resource-sizing.md](resource-sizing.md)), 스케일아웃 경로 부재.
- **목표 지향점**: **학습/포트폴리오**. 실제 프로덕션 패턴인 **오케스트레이터(컨트롤 플레인) ↔ 원격 컴퓨트 분리**를
  로컬에서 재현한다. Dagster는 **호스트 PC**에 두고, 컴퓨트는 **로컬 K8s의 Spark Operator**로 옮긴다.

## 2. 목표 아키텍처 (토폴로지)

```
┌───────────────── 호스트 PC (control plane) ─────────────────────┐
│  Dagster webserver + daemon   (uv run dg dev)                    │
│    • 배치: PipesK8sClient로 SparkApplication(CRD) 제출·폴링         │
│    • 스트림: FlinkDeployment(CRD) 제출·수명주기 관리                 │
│    • dbt CLI(dbt-spark) → Spark(클러스터) 대상 실행                 │
│  Dagster 메타 Postgres (호스트/compose 유지)                       │
└───────────────┬──────────────── kubeconfig ────────────────────┘
                │ k8s API · (필요 시) port-forward
┌───────────────▼─────────── 로컬 K8s (kind on Podman) ───────────┐
│  Spark Operator (Helm) → SparkApplication → driver/executor      │  [BATCH]
│  Flink Operator (Helm) → FlinkDeployment → JobManager/TaskManager│  [STREAM]
│  Redpanda (Kafka API)   ← 스트림 소스(vitalsign 리플레이)          │  [STREAM]
│  SeaweedFS  (StatefulSet+PVC) ← S3(path-style)·IB 웨어하우스·체크포인트│
│  Catalog Postgres (StatefulSet+PVC) ← Iceberg JDBC 카탈로그        │
│  로컬 레지스트리 (kind local-registry)                             │
└──────────────────────────────────────────────────────────────────┘
   Iceberg 공유:  Spark(batch write) ↔ dbt-spark(마트) ↔ Flink(stream r/w)
   ※ BATCH(Spark)·STREAM(Flink)은 6/16 예산상 시분할(동시 실행 금지)
```

- **Dagster는 클러스터 밖(호스트)** 에서 컨트롤 플레인 역할만 한다. Databricks/EMR을 트리거하는 것과
  동일한 패턴이며, `dg dev` 기반 **빠른 개발 루프**를 유지한다.
- **컴퓨트·데이터 서비스는 K8s로 통일**한다(하이브리드 이중관리 회피). 컴퓨트는 **Spark(배치)+Flink(스트림)**.
- **Trino는 제거**한다. dbt는 **dbt-spark**로 이관하고, ad-hoc 조회는 Spark SQL로 대체한다.
- 자원 배분(6 CPU/16 GB, 시분할)은 [resource-sizing.md](resource-sizing.md) "Kubernetes 재설계 시나리오".

## 3. 핵심 결정 (설계 급소)

### 급소 ① — Spark에 "진짜 일"을 준다 (컴퓨트 분업)

현재 데이터 규모(최대 파일 ≈ 3.3GB)는 그 자체로 Spark/Flink가 필수는 아니다. 따라서 **역할이 겹치지 않도록**
분업을 명시해 "엔진을 위한 엔진"(오버엔지니어링)을 방지한다.
lineage(배치): **Spark(bronze·인제스트) → Iceberg → dbt-spark(silver/gold)** /
lineage(스트림): **Redpanda(리플레이) → Flink(실시간 피처·경보) → Iceberg**.

| 계층 | 엔진 | 대상(예) | 비고 |
| --- | --- | --- | --- |
| **bronze 적재(대용량)** | **Spark** `SparkApplication` | `mimiciv.chartevents`·`labevents`·`eicu.nurse_charting` | 기존 `load_heavy_csv_gz_to_iceberg`(boto3 청크 append) **대체** → 커스텀 코드 은퇴 + Spark 존재이유 확보 |
| bronze 적재(일반) | Dagster IO매니저(`pa.Table`) 유지 | 소형 테이블 | 현행 경로 유지(YAGNI) |
| **silver/gold 변환** | **dbt-spark**(Trino 대체) | `sofa`·`sepsis3`·`suspicion_of_infection` 등 22모델 | dbt 자산·스키마테스트 보존, 어댑터만 `dbt-trino`→`dbt-spark` |
| **실시간 스트리밍** | **Flink** `FlinkDeployment` | vitalsign 리플레이 → **실시간 SOFA/Sepsis-3 조기경보** | Flink의 존재이유(급소① 동일 논리). Redpanda 소스, Iceberg 싱크, 체크포인트=SeaweedFS |
| Iceberg 유지보수 | Spark `rewrite_data_files`·`remove_orphan_files` | maintenance job | Trino 제거로 컴팩션도 Spark로 이관([spark.md](architectures/spark.md)) |
| ad-hoc 조회 | Spark SQL(Trino 대체) | 검증·탐색 | 인터랙티브 편의는 Trino보다 낮음(트레이드오프) |

### 급소 ② — Trino+Spark 동시 쓰기용 카탈로그

- **지금**: 기존 **Postgres 기반 Iceberg JDBC 카탈로그를 Spark·Flink가 공유**한다. Iceberg 낙관적
  동시성(compare-and-swap)으로 병행 R/W가 가능하다. 메타데이터 테이블(`iceberg_tables`,
  `iceberg_namespace_properties`) 스키마를 양쪽이 동일하게 보게 정합을 유지한다.
- **후속(선택)**: JDBC 카탈로그는 향후 Iceberg breaking change에 취약할 수 있어 **REST 카탈로그**
  (Nessie·Polaris·lakekeeper)가 권장된다. Spark+Flink 동시 writer 구조라 REST 카탈로그 이행 유인이 크다(별도 과제).

### 그 외 결정

| 포인트 | 결정 | 근거 |
| --- | --- | --- |
| 로컬 K8s 배포판 | **kind on Podman(rootful)** | Docker Desktop 탈피. kind Podman provider는 experimental이라 rootful 머신 필수([conventions/k8s.md](conventions/k8s.md) §10) |
| 컴퓨트 엔진 | **Spark(배치) + Flink(스트림)**, **Trino 제거** | 배치=Spark(bronze+dbt-spark), 스트림=Flink(실시간 경보). 역할 분리 |
| dbt 실행 엔진 | **dbt-spark**(← dbt-trino) | Trino 제거 대응. dbt-spark는 dbt Labs 유지보수 어댑터 |
| Dagster↔컴퓨트 트리거 | **PipesK8sClient + SparkApplication/FlinkDeployment 제출·폴링** | Pipes가 로그·materialization 회수. `K8sRunLauncher`는 in-cluster 배포용이라 부적합 |
| 오브젝트 스토어 | **SeaweedFS 유지** + `path-style` 강제 | Spark·Flink S3A 모두 `fs.s3a.path.style.access=true` 필수 |
| 스트림 소스 | **Redpanda**(Kafka API) | Kafka보다 경량(ZK 불요). vitalsign 리플레이 → Flink 입력 |
| 데이터 서비스 위치 | SeaweedFS·카탈로그 Postgres **K8s로 이전** | 단일 패러다임(K8s) 통일 |
| Dagster 실행 위치 | **호스트 유지** | 개발 루프 속도 + 컨트롤/컴퓨트 분리 시연 |

## 4. 단계별 이행 플랜 (PoC 우선 · PDCA)

> 원칙: **커스텀 글루(Dagster↔Spark Operator)의 실현성을 PoC로 먼저 확인**해 리스크를 가장 크게 줄인 뒤 이행한다.
> 각 Phase는 **성공 게이트**를 통과해야 다음으로 넘어간다.

### Phase 0 — PoC (실현성 검증) 🚧 최우선

- **Plan**: kind(on Podman) 클러스터 + Spark Operator(Helm) 위에, 최소 SparkApplication을 **Dagster 자산이
  `PipesK8sClient`로 제출**하고 Iceberg 테이블에 write까지 성공시킨다.
- **Do**: ① podman machine(rootful,6/16) + kind + 로컬 레지스트리 ② Spark Operator Helm 설치
  ③ PySpark+Iceberg 러너 이미지 빌드·push ④ SeaweedFS/카탈로그 Postgres 최소 기동 ⑤ Dagster 자산에서 CRD 제출·폴링.
- **Check(성공 게이트)**: Iceberg 테이블 1개가 Spark로 append되고 **Spark SQL로 조회**되며, Dagster UI에
  로그·materialization이 회수된다.
- **Act**: 검증된 최소 골격을 리소스(`SparkOperatorResource`)·러너 이미지 규격으로 확정.

### Phase 1 — 데이터 서비스 K8s 이전 + dbt 엔진 전환

- **Plan/Do**: SeaweedFS·카탈로그 Postgres를 **Helm/매니페스트**로 K8s에 배포([conventions/k8s.md](conventions/k8s.md) 규칙 준수).
  dbt 어댑터를 **`dbt-trino`→`dbt-spark`** 로 교체하고 Spark SQL 엔드포인트(Thrift/Connect)에 연결.
- **Check**: 22모델이 dbt-spark로 `dbt build` 통과(SQL 방언 차이 교정), 스키마테스트 유지.
- **Act**: compose에서 Trino 제거·env 전파 체인 재확인([operations.md](operations.md)).

### Phase 2 — 대용량 bronze 인제스트 Spark 전환

- **Plan/Do**: `chartevents`·`labevents`·`eicu.nurse_charting` 적재를 **SparkApplication**으로 이전,
  `load_heavy_csv_gz_to_iceberg`(boto3 청크) **은퇴**.
- **Check**: 행 수·스키마가 기존 적재분과 일치(회귀), small-files 대비 파일 크기 개선 확인.
- **Act**: 유지보수(compaction) 순서 재점검(compact→expire→orphan, [spark.md](architectures/spark.md)).

### Phase 3 — Flink 실시간 스트리밍 (Flink의 존재이유)

- **Plan/Do**: Flink Operator(Helm) + Redpanda 배포. `vitalsign` 등을 Redpanda로 **리플레이**하고,
  **`FlinkDeployment`** 잡이 이벤트타임 윈도우로 **실시간 SOFA/Sepsis-3 조기경보**를 계산해 Iceberg에 싱크.
  체크포인트는 SeaweedFS(S3), 상태 백엔드 RocksDB. Dagster가 잡 수명주기를 관리.
- **Check**: 스트림 입력 대비 경보 산출 정확성·지연 관측, 배치(Spark)와 **시분할** 실행 확인([resource-sizing.md](resource-sizing.md)).
- **Act**: 배치 결과(dbt-spark)와 스트림 결과의 정합(동일 피처 정의) 교차검증.

### Phase 4 — 오케스트레이션 정착 + 문서·컨벤션 확정

- **Plan/Do**: `defs/` 자산·리소스를 Spark/Flink 경로로 재배선(`PipesK8sClient`·`SparkOperatorResource`·Flink 트리거),
  automation 갱신. Dagster **에셋 명시·분리 정의** 컨벤션 유지(팩토리 금지).
- **Check**: `dg check defs`·스모크(`dbt build`) 통과([test.md](test.md)). 에셋 pytest는 실인프라 미접속 격리 유지.
- **Act**: `CLAUDE.md`·`README.md`·`docs/`를 최종 동기화(단일 출처), 상태 마커 🚧→✅.
- **후속 과제**: ① REST 카탈로그(급소②) ② ML/윈도우 피처 계층 ③ (선택) Dagster in-cluster 배포(`K8sRunLauncher`) 비교.

## 5. 리스크·트레이드오프 (정직한 기록)

| 관점 | 평가 | 메모 |
| --- | --- | --- |
| 정확성/학습가치 | ★★★★★ | Spark/Flink 2개 K8s Operator(선언형 CRD)·배치+스트림 시연 = 강한 포트폴리오 신호 |
| 리스크 | ★★★☆☆ | Dagster↔Operator canonical 예제 부재(커스텀 글루) + **dbt-trino→dbt-spark SQL 방언 교정** 필요(Phase 0·1로 방어) |
| 비용 | ★★★☆☆ | 로컬이라 클라우드 비용 0, 단 **단일 PC RAM 압박**(2엔진+Redpanda+SeaweedFS). **시분할**로 6/16 내 수용([resource-sizing.md](resource-sizing.md)) |
| 효율(개발 루프) | ★★☆☆☆ | in-process 대비 느려짐(이미지 빌드→레지스트리 push→CRD 제출). **의도된 학습 트레이드오프**로 수용 |

- **데이터 규모 대비 Spark/Flink 과함**은 인정하고, 급소①의 분업(대용량 인제스트=Spark, 실시간 경보=Flink)으로 정당성을 확보한다.
- **Trino 제거 비용**: 성숙한 인터랙티브 SQL·`dbt-trino`를 잃는다. ad-hoc 조회 편의가 낮아지고 22모델 방언 교정이 필요하다(수용된 트레이드오프).

## 6. 참고 (공식 문서)

- Kubeflow Spark Operator: https://www.kubeflow.org/docs/components/spark-operator/ · 릴리스: https://github.com/kubeflow/spark-operator/releases
- Apache Flink Kubernetes Operator: https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-main/
- Dagster Pipes / dagster-k8s(PipesK8sClient): https://docs.dagster.io/api/python-api/libraries/dagster-k8s
- Dagster & Spark: https://docs.dagster.io/integrations/libraries/spark
- dbt-spark 어댑터: https://docs.getdbt.com/docs/core/connect-data-platform/spark-setup
- Spark on Kubernetes: https://spark.apache.org/docs/latest/running-on-kubernetes.html
- Redpanda(Kafka API): https://docs.redpanda.com/
- Iceberg JDBC 카탈로그: https://iceberg.apache.org/docs/latest/jdbc/ · REST 카탈로그 권고: https://trino.io/docs/current/object-storage/metastores.html
- kind Podman provider: https://kind.sigs.k8s.io/docs/user/rootless/ · 로컬 레지스트리: https://kind.sigs.k8s.io/docs/user/local-registry/
