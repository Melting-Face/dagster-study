# Apache Spark (아키텍처 · 프로젝트 관점)

## 개요

Spark는 **범용 분산 데이터 처리 엔진**이다. driver가 DAG를 스케줄링하고 여러 executor가 파티션을
병렬 처리한다. RDD/DataFrame API, 배치·마이크로배치 스트리밍(Structured Streaming), SQL, ML(MLlib)을
아우르며, 셔플·인메모리 캐시로 대규모 변환에 강하다.

- 최신 안정: **Spark 4.2.0**(2026-07). Arrow 최적화 Python UDF 기본화, CDC(`CHANGES`), 지오공간·
  벡터/AI 함수, Real-Time Mode 등.

## 이 프로젝트에서의 위치 — 🚧 채택·이행중(PoC 게이트)

- **채택 방향**: 재설계로 **K8s의 Apache Spark Operator**([apache/spark-kubernetes-operator](https://github.com/apache/spark-kubernetes-operator),
  GA 1.0.0 2026-07-26)를 컴퓨트로 도입한다(Kubeflow spark-operator에서 이전). 확장성 확보와 함께,
  오케스트레이터↔원격 컴퓨트 분리를 시연하는 **학습/포트폴리오** 목적이다. 전체 로드맵은 [../redesign.md](../redesign.md).
- **컴퓨트 분업(급소)**: Spark가 장식이 되지 않도록 역할을 분리한다.
  lineage는 **Spark(bronze·인제스트) → Iceberg → dbt-on-Trino(silver/gold)**.
  - **대용량 bronze 적재를 Spark로**: `mimiciv.chartevents`·`labevents`·`eicu.nurse_charting`의 적재를
    `SparkApplication`으로 옮겨 기존 `load_heavy_csv_gz_to_iceberg`(boto3 청크 append)를 **대체**한다.
    "대용량 CSV.gz 분산 읽기 → Iceberg write"는 Spark의 교과서적 유스케이스로, **커스텀 코드 은퇴 +
    Spark 존재이유 확보**를 동시에 달성한다([../redesign.md](../redesign.md) 급소①).
  - **silver/gold SQL 마트를 dbt-spark로**: Trino 제거에 따라 dbt 어댑터를 **`dbt-trino`→`dbt-spark`** 로 이관한다.
    22모델(SOFA→Sepsis-3)과 스키마테스트 자산은 보존하고, SQL 방언 차이만 교정한다([../redesign.md](../redesign.md) Phase 1).
  - **Iceberg 유지보수를 Spark로**: Trino `optimize` 대신 `rewrite_data_files`·`remove_orphan_files`를 Spark 프로시저로 실행.
  - **(후속) ML/윈도우 피처** — SQL로 표현이 어려운 계층(PySpark).
  - **실시간 스트리밍은 Flink 담당** — 배치=Spark, 스트림=Flink로 역할 분리([flink.md](flink.md)).
- **실행 방식**: 네이티브 `spark-submit`(명령형) 대신 **선언형 `SparkApplication`(CRD, `spark.apache.org/v1`)** 을 쓴다.
  오퍼레이터가 spark-submit을 대행하고 재시도·상태를 표면화해 GitOps/감사에 유리하다. 스펙은 `sparkConf` 중심이다([../conventions/k8s.md](../conventions/k8s.md) §9).
- **Trino 대비**: Spark=범용·상태 있는 처리·코드 API / Trino=SQL 연합 쿼리·무상태·낮은 오버헤드([trino.md](trino.md)).

## 운영 메모 (이행)

- **트리거**: Dagster(호스트) 자산이 `PipesK8sClient`로 `SparkApplication`을 제출·폴링하고 로그·materialization을 회수한다([../conventions/k8s.md](../conventions/k8s.md) §9~11).
- **Iceberg 접속**: `iceberg-spark-runtime`으로 Trino·**Flink와 동일 JDBC 카탈로그** 공유(낙관적 동시성).
  메타 테이블(`iceberg_tables`·`iceberg_namespace_properties`) 스키마 정합 유지.
  2026-08-18 **Flink가 Spark 적재분을 그대로 조회**하는 것까지 실증([flink.md](flink.md)).
- **S3 경로가 둘이고 역할이 다르다**(혼동 주의):
  - **Iceberg `S3FileIO`**(AWS SDK v2, `iceberg-aws-bundle`) — **테이블 데이터 I/O** 전담. 현재 적재 경로가 이것.
  - **S3A**(`hadoop-aws` + `aws-java-sdk-bundle`) — `s3a://`로 **원본 파일**(csv.gz)을 읽을 때 필요(Phase 2).
    2026-08-18까지 러너 이미지에 **없었다**(Iceberg만 쓰는 잡은 돌아서 부재를 눈치채기 어려움).
  - 둘 다 SeaweedFS라 **path-style 강제**(`s3.path-style-access` / `fs.s3a.path.style.access`).
  - ⚠️ **S3A 직접 쓰기(`df.write.parquet("s3a://…")`)는 실패한다** — 기본 committer가 rename에 의존.
    본 설계는 쓰기를 전부 Iceberg(S3FileIO)로 보내므로 영향 없음([../conventions/k8s.md](../conventions/k8s.md) §9).
- **상시 SQL 엔드포인트 — Spark Connect**(Phase 1): `SparkApplication`은 잡이 끝나면 사라져 dbt가 붙을 수 없다.
  그래서 **Spark Connect 서버**를 Deployment로 상주시키고 dbt-spark가 `spark.remote`로 접속한다
  (`k8s/spark/spark-connect-server.yaml`). Thrift(HiveServer2) 대비 클라이언트가 가볍고 어댑터 변경이 없다.
  **상주 자원을 쓰므로** 쓰지 않을 때는 `kubectl scale deploy/spark-connect --replicas=0`
  (시분할 규칙 [../resource-sizing.md](../resource-sizing.md)).
- **러너 이미지 버전(실측 고정)**: Spark **3.5.9** / Iceberg **1.6.1** / hadoop-aws **3.3.4** ↔ aws-java-sdk-bundle **1.12.262**.
  `hadoop-aws`는 베이스 이미지의 `hadoop-client-*`와 **정확히 같은 버전**이어야 한다.
- executor 메모리·셔플 파티션 튜닝이 성능 핵심.

## 심화: Iceberg 파일 컴팩션 (Spark vs Trino) — 이 프로젝트 관점

### 문제: small-files (파일 폭증)

이 프로젝트의 대용량 테이블(`mimiciv.chartevents`·`labevents`·`eicu.nurse_charting`)은
`load_heavy_csv_gz_to_iceberg`가 **청크(기본 100만 행) 단위로 `append`** 하며 적재한다
([overview.md](overview.md) 대용량 경로). append마다 데이터 파일이 생겨 **작은 파일이 다수**
쌓이고, 이는 메타데이터 팽창·파일 오픈 비용 증가로 쿼리를 느리게 한다. **컴팩션**(작은 파일을
큰 파일로 bin-packing)이 필요하다.

### 두 가지 컴팩션 수단

| 수단 | 호출 | 특징 | 이 프로젝트 적합성 |
| --- | --- | --- | --- |
| **Trino `optimize`** | `ALTER TABLE iceberg.<ns>.<t> EXECUTE optimize(file_size_threshold => '100MB')` | threshold 미만 파일을 파티션별 병합. 별도 인프라 불필요 | ✅ 현행 스택(추가 인프라 0). 단, 쿼리용 Trino와 자원 경합 |
| **Spark `rewrite_data_files`** | `CALL catalog.system.rewrite_data_files(...)` (binpack/sort, 목표 512MB~1GB) | Spark 잡으로 병렬 rewrite, 유지보수 전용 분리 가능 | 🔎 대규모·상시 컴팩션에서 쿼리 경합을 피하려는 경우 |

### 프로젝트 결정

- **지금**: **Spark `rewrite_data_files`** 로 처리한다(2026-08-19 Trino에서 이관 — Trino 제거의 선행조건①).
  `remove_orphan_files`도 함께 Spark로 옮겨 **유지보수 엔진을 하나로** 모았다.
  유지보수 잡의 **1·3단계 op로 구현**했다
  ([maintenance.py](../../dagster/dockerfile.d/src/src/dagster_project/defs/maintenance.py)).
  접속은 **공식 통합 `dagster-pyspark`의 `LazyPySparkResource`** 를 쓴다(커스텀 리소스를 만들지 않는다 —
  [conventions/dagster.md](../conventions/dagster.md)의 "불필요한 서브클래싱 지양"). Spark Connect로 붙이는
  방법은 **`spark_config={"spark.remote": ...}`** 한 줄이다 — 내부 `builder.config(k, v)`가 이 키를 받아
  `pyspark.sql.connect` 세션을 만든다(2026-08-19 실측). 카탈로그 설정은 **서버 측**에 있어
  Dagster는 주소만 갖는다(비밀정보 비노출).
  - **`Lazy~`를 쓰는 이유**: 세션을 `spark_session` **접근 시점**에 만든다. 비-Lazy(`PySparkResource`)는
    리소스 초기화에서 즉시 연결해, 유지보수와 무관한 run까지 Spark Connect 가용성(=port-forward)에 묶인다.
  - **`dagster-spark`는 직접 쓰지 않는다** — `spark-submit` 래퍼(`create_spark_op`)라 용도가 다르다.
    `dagster-pyspark`가 설정 스키마를 가져다 쓰므로 전이 의존으로만 설치된다.
  - **제약**: Spark Connect 세션은 `sparkContext`를 지원하지 않는다(`NOT_IMPLEMENTED`).
    RDD·`sc.parallelize`가 필요한 코드는 Connect로 못 옮긴다 — 유지보수는 SQL만 써서 무관하다.
- **Trino와 다른 지점(값에 영향)**: Spark bin-pack은 `min-input-files`(기본 5) 미만이면 그룹을
  **통째로 건너뛴다**. Trino `optimize`에는 이 문턱이 없다 → 파일이 몇 개뿐인 테이블에서
  "0건 재작성"이 나오는 건 정상이며, 같은 임계값을 줘도 **두 엔진의 결과가 같지 않다**.
- 🔴 **`remove_orphan_files`는 Hadoop FileSystem을 쓴다** — Iceberg의 `S3FileIO`(`io-impl`)는
  카탈로그가 아는 파일만 다루는데, 이 프로시저는 카탈로그가 **모르는** 파일을 찾는 게 목적이라
  warehouse 디렉터리를 직접 나열해야 한다. Spark Connect 서버에 `spark.hadoop.fs.s3*`(S3A) 설정이
  없으면 `UnsupportedFileSystemException: No FileSystem for scheme "s3"`로 죽는다(2026-08-19 실측).
  jar(`hadoop-aws`·`aws-java-sdk-bundle`)는 러너 이미지에 이미 있고 **설정만** 필요했다.
- **안전 순서**: **compact(`rewrite_data_files`) → expire snapshots → remove orphan files**(현행 잡이
  op 의존성으로 강제). 컴팩션이 새 파일·스냅샷을 만든 뒤 만료가 옛 작은 파일 참조를 풀고,
  orphan 정리가 잔여를 제거한다.

## 참고

- Spark 문서: https://spark.apache.org/docs/latest/
- Spark 4.2.0 릴리스: https://spark.apache.org/releases/spark-release-4-2-0.html
- Apache Spark Kubernetes Operator: https://apache.github.io/spark-kubernetes-operator/ · 릴리스: https://github.com/apache/spark-kubernetes-operator/releases
- Iceberg + Spark: https://iceberg.apache.org/docs/latest/spark-getting-started/
- Iceberg Spark 프로시저(`rewrite_data_files`): https://iceberg.apache.org/docs/latest/spark-procedures/
- Trino Iceberg `optimize`(컴팩션): https://trino.io/docs/current/connector/iceberg.html
