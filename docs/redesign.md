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
- **로드맵의 종착지는 인프라가 아니라 분석이다.** Phase 0~4는 수단을 세우고, **Phase 5에서 gold 마트·
  리포트로 닫힌다**(§4). 인프라가 "도는 것"은 완료 조건이 아니다.

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
│  CloudNativePG (Helm) → Cluster(CRD) → Catalog Postgres(+PVC)     │
│                                       ← Iceberg JDBC 카탈로그      │
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
| 카탈로그 Postgres 관리 | **CloudNativePG 오퍼레이터**(← Deployment+emptyDir) | PVC·failover·PITR·튜닝이 CR 한 장. Spark·Flink 오퍼레이터와 **같은 선언형 패러다임**. 이전 구성은 재기동만으로 카탈로그가 소멸했다 |
| SeaweedFS 관리 | **StatefulSet 유지**(오퍼레이터 미채택 🔎) | 오퍼레이터는 master/volume/filer 분리로 **+500m/+1Gi** 상주 순증인데, 이미 PVC라 막을 유실 급소가 없다. Phase 2 이후 재검토 |
| Dagster 실행 위치 | **호스트 유지** | 개발 루프 속도 + 컨트롤/컴퓨트 분리 시연 |

## 4. 단계별 이행 플랜 (PoC 우선 · PDCA)

> 원칙: **커스텀 글루(Dagster↔Spark Operator)의 실현성을 PoC로 먼저 확인**해 리스크를 가장 크게 줄인 뒤 이행한다.
> 각 Phase는 **성공 게이트**를 통과해야 다음으로 넘어간다.

### Phase 0 — PoC (실현성 검증) ✅ 게이트 통과 (2026-08-18)

- **Plan**: kind(on Podman) 클러스터 + Spark Operator(Helm) 위에, 최소 SparkApplication을 **Dagster 자산이
  `PipesK8sClient`로 제출**하고 Iceberg 테이블에 write까지 성공시킨다.
- **Do**: ① `scripts/k8s-up.sh`(podman machine rootful 6/16 + kind + 로컬 레지스트리, config는 `k8s/kind-cluster.yaml`)
  ② `scripts/k8s-operators.sh`(Spark Operator Helm; Flink는 `INSTALL_FLINK=true`) ③ PySpark+Iceberg 러너 이미지 빌드·push
  ④ SeaweedFS/카탈로그 Postgres 최소 기동 ⑤ Dagster 자산에서 CRD 제출·폴링. 정리는 `scripts/k8s-down.sh`.
- **Check(성공 게이트)**: Iceberg 테이블 1개가 Spark로 append되고 **Spark SQL로 조회**되며, Dagster UI에
  로그·materialization이 회수된다.
- **Act**: 검증된 최소 골격을 리소스(`SparkOperatorResource`)·러너 이미지 규격으로 확정.
- **검증 결과(2026-08-18)**: 호스트 Dagster 자산 → `SparkApplication`(Apache CRD `spark.apache.org/v1`) 제출·폴링 →
  Iceberg `iceberg.poc.sample` write + Spark SQL read-back → driver 로그 회수 → materialization 메타
  `rows=3` 기록, webserver GraphQL 노출 확인. 당시 러너 이미지 `localhost:5001/spark-runner:0.2.0`(S3A 포함)
  — **현행은 `0.4.0`**(Spark Connect 추가, 빌드·push 절차는 [conventions/k8s.md](conventions/k8s.md) §10).
- **이 과정에서 고친 잠복 결함 3건**(모두 조용히 실패하던 것):
  ① Apache 이전이 `k8s/`·`scripts/`에만 적용되고 **Dagster 글루(`defs/poc/`)는 Kubeflow 스펙**으로 남아 있었다.
  ② `assets.py`에 `@dg.definitions`가 같이 있어 **자산이 자동발견에서 누락**됐다([conventions/dagster.md](conventions/dagster.md)).
  ③ driver 파드 이름을 `<app>-driver`로 조립했으나 Apache는 `<app>-<attempt>-driver`라 **로그 회수가 빈 문자열**이었다.

### Phase 1 — 데이터 서비스 K8s 이전 + dbt 엔진 전환 🚧 진행중 (2026-08-18 착수)

- **Plan/Do**: SeaweedFS·카탈로그 Postgres를 **Helm/매니페스트**로 K8s에 배포([conventions/k8s.md](conventions/k8s.md) 규칙 준수).
  dbt 어댑터를 **`dbt-trino`→`dbt-spark`** 로 교체하고 Spark SQL 엔드포인트(Thrift/Connect)에 연결.
- **Check**: 22모델이 dbt-spark로 `dbt build` 통과(SQL 방언 차이 교정), 스키마테스트 유지.
- **Act**: compose에서 Trino 제거·env 전파 체인 재확인([operations.md](operations.md)).
- **진행 상황(2026-08-18)**
  - 데이터 서비스는 **이미 K8s에 있음**(SeaweedFS·카탈로그 Postgres, PoC 단계에서 선행).
  - **(2026-08-19)** 카탈로그 Postgres를 **CloudNativePG `Cluster`로 재정의**했다 —
    기존 `Deployment`+`emptyDir`는 파드 재기동만으로 카탈로그가 소멸하는 구성이었다.
    보존할 데이터가 없는 시점이라 이행 비용이 최저(재적재 전제).
    **적용 완료** — CNPG 1.30.0(chart 0.29.0) 설치, `Cluster` 1인스턴스 + PVC 5Gi 기동,
    Spark 잡이 새 카탈로그에 `iceberg.poc.sample` 등록까지 확인. 접속은 `catalog-postgres-rw`.
  - `dbt-spark 1.11.0` 설치. **pyspark는 3.5 계열로 핀**(클러스터 러너 Spark 3.5.9와 맞춤).
  - 프로파일 2종 추가 — **`spark_session`**(호스트 로컬 Spark, 상시 서비스 0) /
    **`spark_connect`**(클러스터 **Spark Connect 서버**, 컴퓨트=K8s). 둘 다 **연결 확인 완료**.
    dbt-spark의 `server_side_parameters`가 세션 생성 시 `builder.config()`로 적용되므로
    Iceberg 설정 전체를 프로파일에 두면서 **비밀정보는 `env_var()` 참조**로 유지한다.
  - `dbt show --target spark_connect`로 **Iceberg 테이블 조회 성공**(dbt→Connect→Iceberg 전 구간).
  - **`dbt compile` 22모델 전부 통과**. 단, 그 전에 `source.yml`의 `database: iceberg`를 제거해야 했다
    (dbt-spark는 relation에 database 설정을 금지 — `Cannot set database in spark!`).
- **SQL 방언(정적 스캔) — 전부 해소** / 정본·규칙은 [conventions/dbt.md](conventions/dbt.md) "방언 차이는 크로스 어댑터 매크로로 흡수한다"

  | 구문 | 파일 수 | 상태 | Trino → Spark |
  | --- | --- | --- | --- |
  | `INTERVAL '1' HOUR` 리터럴 | 8 → **0** | ✅ 해소(`52e7cde`) | `{{ dbt.dateadd(...) }}` **내장** 매크로 |
  | `date_diff('unit', a, b)` | 3 → **0** | ✅ 해소(`589bd5a`) | `{{ elapsed(...) }}` **프로젝트 dispatch** 매크로 |
  | `CROSS JOIN UNNEST(...)` | 1 → **0** | ✅ 해소(`589bd5a`) | `{{ unnest_array(...) }}` **프로젝트 dispatch** 매크로 |
  | `sequence(...)`·`date_trunc(...)` | 3 | ✅ 무조치 | 양쪽 엔진에 동일 의미로 존재 |

  > 🔴 **`dbt.datediff`는 일부러 쓰지 않았다** — `spark__datediff`는 경과시간 `ceil`, Trino 네이티브는
  > **경계 교차**라 임계값 비교(`ventilation >= 14`·`urine_output_rate <= 5`)에서 silver 피처 값이 갈린다.
  > Trino를 정본으로 두고 Spark에 같은 수식을 재현했다. **"도는 것"이 아니라 "같은 값"이 이행 기준이다.**
  > 두 타깃 compile·렌더 대조는 통과했고 **실행 검증만 원천 데이터 부재로 보류**다.

- **선행 조건(로드맵에 없던 발견)**: bronze 테이블이 **K8s 카탈로그에 없다**(compose 쪽 카탈로그에만 존재).
  실행 단계 검증은 **Phase 2(대용량 적재 Spark 이전)와 순서가 얽힌다** — 데이터 이관이 먼저다.

### Phase 2 — 대용량 bronze 인제스트 Spark 전환 ⏸ **원천 일부 확보, 핵심 대용량은 미확보**

> 🔴 **2026-08-19 정정** — 2026-08-18의 "원천이 어디에도 없다"는 **오진이었다**.
> compose SeaweedFS의 `warehouse` 버킷에 원천 csv.gz **9개(압축 110.7MB)** 가 실재했다.
> 당시엔 **K8s SeaweedFS만** 조회했고 compose 쪽은 컨테이너가 `Exited`라 S3 API가 죽어 있어
> "버킷 0개"로 읽혔다. **죽은 엔드포인트의 조회 실패를 데이터 부재로 판정하면 안 된다** —
> 부재 판정은 **조회 경로가 살아 있을 때만** 유효하다.
> (`iceberg_catalog` DB 부재·호스트 csv.gz 부재는 사실이었다.)
>
> **2026-08-19 이관 완료**: compose SeaweedFS → K8s SeaweedFS로 S3→S3 스트리밍 복사.
> 크기 대조 9/9 + **gzip CRC 전수 검증 9/9** 통과(크기만으로는 SeaweedFS 체크섬 손상을 못 잡는다).
> 이제 원천은 **K8s SeaweedFS `s3://warehouse/raw/` 단일 소재**이고, compose SeaweedFS 컨테이너는 제거했다
> (호스트 바인드 마운트 `./seaweedfs/data` 309MB는 남아 사실상 원본 백업).
>
> **확보 현황** — `scripts/upload_raw_to_seaweedfs.py` 매니페스트(=자산이 실제로 읽는 파일) 14개 기준:
>
> | 구분 | 파일 |
> | --- | --- |
> | ✅ 확보(4) | `eicu/patient`·`eicu/diagnosis`·`mimiciv/hosp/admissions`·`mimiciv/hosp/d_labitems` |
> | ✖ **부재(10)** | `eicu/nurseCharting` · `mimiciv/icu/{icustays,chartevents,inputevents,outputevents,d_items}` · `mimiciv/hosp/{patients,labevents,prescriptions,microbiologyevents}` |
> | ➕ 여분(5) | `mimiciv/hosp/{diagnoses_icd,drgcodes,d_icd_diagnoses,d_icd_procedures,d_hcpcs}` — 매니페스트 밖 |
>
> → **이 단계가 겨냥한 대용량 3종**(`chartevents`·`labevents`·`nurseCharting`)이 **전부 부재**라
> Spark 인제스트 전환은 여전히 대기다. 22모델이 요구하는 7 source 중에도 `admissions` 하나뿐이라
> **`dbt build` 실행 검증도 불가**하다. 나머지는 **PhysioNet 자격증명 + DUA** 대상이라
> 사용자가 직접 받아야 한다(저장소 커밋 금지). 받은 뒤 `scripts/upload_raw_to_seaweedfs.py`로 올린다.
> → 다만 **eICU 2종은 실물이므로 bronze 적재 자산을 실제로 돌려볼 수 있다**(경로 검증 가능).
>
> **데이터 없이 미리 끝낸 것**(합성 3행으로 전 구간 검증 후 정리):
> S3(csv.gz) → Dagster 자산 → Iceberg 적재 → **Spark Connect에서 조회**까지 K8s 스택에서 통과.
> 이 과정에서 카탈로그 이름 분리·SeaweedFS 체크섬 두 결함을 찾아 고쳤다([conventions/k8s.md](conventions/k8s.md) §11).

- **Plan/Do**: `chartevents`·`labevents`·`eicu.nurse_charting` 적재를 **SparkApplication**으로 이전,
  `load_heavy_csv_gz_to_iceberg`(boto3 청크) **은퇴**.
- **Check**: 행 수·스키마가 기존 적재분과 일치(회귀), small-files 대비 파일 크기 개선 확인.
- **Act**: 유지보수(compaction) 순서 재점검(compact→expire→orphan, [spark.md](architectures/spark.md)).

### Phase 3 — Flink 실시간 스트리밍 (Flink의 존재이유) ⏸ **미착수 · 오퍼레이터 미설치**

> **2026-08-19 상태**: Phase 0에서 검증용으로 띄웠던 Flink 스택(`flink-session`·Flink Operator·
> cert-manager)을 **제거**했다. 잡 없는 세션 클러스터가 **1 CPU / 2Gi를 13시간 점유**하며
> "BATCH·STREAM 시분할(동시 실행 금지)" 규약을 어기고 있었다.
> **"중단"과 "삭제"의 분리**(trino 선례)와 같은 취지 — 검증 결과·매니페스트·러너 이미지는 전부
> 남아 있고 `INSTALL_FLINK=true ./scripts/k8s-operators.sh` 한 줄로 되돌아온다(롤백 비용 ≈ 0).
> `INSTALL_FLINK` 기본값이 이미 `false`라 **재기동해도 Flink는 뜨지 않는다**(스크립트가 정본).

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

### Phase 5 — 분석 계층 (로드맵의 종착지) ⏸ **원천 데이터 적재 이후**

> Phase 0~4는 **수단**(컴퓨트·스토리지·오케스트레이션)을 세운다. 이 저장소의 **목적은 분석**이므로
> 로드맵은 여기서 끝난다. 규칙 정본은 [conventions/analysis.md](conventions/analysis.md),
> 소비 계층 그림은 [architectures/overview.md](architectures/overview.md).

- **전제**: ① Phase 2(원천 적재)가 끝나 silver 22모델이 **실제 데이터로** 돌아야 한다.
  ② **연구 질문이 먼저 정해져야 한다** — 질문 없이 만든 gold는 재사용되지 않는 집계일 뿐이다.
- **Plan/Do**: ① 연구 질문 확정(예: Sepsis-3 발생률·SOFA 궤적·조기경보 지연) →
  ② 질문별 **gold 마트** 정의(`tags=['gold']`, grain을 `schema.yml` description에 명시) →
  ③ 노트북으로 탐색하고 반복되는 조회를 gold로 승격 → ④ 첫 리포트(`docs/analyses/01-*.md`) 작성.
- **Check(성공 게이트)**:
  - 리포트 1편이 **gold/dbt 모델만 인용**해 수치가 재현된다(노트북 임시 SQL 인용 0건).
  - 해당 gold 모델의 **grain 유니크·범위 테스트 통과**([test.md](test.md) §1).
  - 참조 노트북이 `nbconvert`로 **전 셀 실행 성공**([test.md](test.md) §6).
  - 코호트 **attrition 표**와 **한계 섹션**이 리포트에 있다.
- **Act**: 실사용에서 드러난 규칙의 빈틈을 `conventions/analysis.md`에 되먹인다.
- **연계**: Phase 3(Flink 실시간 경보)의 산출과 배치(dbt-spark) 산출의 **동일 피처 정의 교차검증**이
  여기서 리포트로 닫힌다. Phase 4 후속 과제의 **ML/윈도우 피처 계층**도 이 단계의 연장이다.

> **현재 상태(2026-08-19)**: 규칙(`conventions/analysis.md`)과 실행 환경(호스트 Jupyter Lab +
> Spark Connect)은 서 있고, **gold 0개 · 리포트 0편 · 연구 질문 미정**이다.
> 이 셋 중 **연구 질문이 병목**이며 데이터 부재(Phase 2)와는 별개로 지금 정할 수 있다.

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

- Apache Spark Kubernetes Operator(GA 1.0.0, Kubeflow에서 이전): https://apache.github.io/spark-kubernetes-operator/ · 릴리스: https://github.com/apache/spark-kubernetes-operator/releases
- Apache Flink Kubernetes Operator: https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-main/
- Dagster Pipes / dagster-k8s(PipesK8sClient): https://docs.dagster.io/api/python-api/libraries/dagster-k8s
- Dagster & Spark: https://docs.dagster.io/integrations/libraries/spark
- dbt-spark 어댑터: https://docs.getdbt.com/docs/core/connect-data-platform/spark-setup
- Spark on Kubernetes: https://spark.apache.org/docs/latest/running-on-kubernetes.html
- Redpanda(Kafka API): https://docs.redpanda.com/
- Iceberg JDBC 카탈로그: https://iceberg.apache.org/docs/latest/jdbc/ · REST 카탈로그 권고: https://trino.io/docs/current/object-storage/metastores.html
- kind Podman provider: https://kind.sigs.k8s.io/docs/user/rootless/ · 로컬 레지스트리: https://kind.sigs.k8s.io/docs/user/local-registry/
