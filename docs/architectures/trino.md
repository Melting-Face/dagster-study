> **이행 상태(2026-08-18)**: 대체 경로가 **동작 확인**됨 — `dbt-spark`가 Spark Connect 서버를 통해
> Iceberg를 조회하는 것까지 검증([../redesign.md](../redesign.md) Phase 1). 다만 22모델의 **실행 단계
> 방언 교정**과 bronze 데이터 이관이 남아 있어 compose의 `trino` 서비스는 아직 유지한다.

# Trino (아키텍처 · 프로젝트 관점)

## 개요

Trino는 **MPP(대규모 병렬 처리) 분산 SQL 쿼리 엔진**이다. 데이터를 자체 저장하지 않고
(무상태), 여러 소스(Iceberg·Hive·RDB 등)에 **연합 쿼리(federated query)** 한다.
coordinator가 SQL을 분해해 worker들에 분산하고, 메모리 기반 파이프라인으로 배치 SQL을
빠르게 처리한다.

## 이 프로젝트에서의 위치 — 🔎 재설계로 제거(현행 compose까지 채택)

> **상태 변경**: 현행 compose 스택에서는 ✅ 채택이었으나, [재설계](../redesign.md)에서 **제거**한다.
> dbt는 **`dbt-spark`** 로 이관하고, ad-hoc 조회는 **Spark SQL**로 대체한다.

- **(현행) 역할**: dbt(`dbt-trino`)가 접속하는 쿼리 엔진. Iceberg 테이블을 읽고 써서 silver 모델을 만든다.
- **(현행) 채택 이유**:
  - **Iceberg JDBC 카탈로그 공유** — Trino와 Dagster(pyiceberg)가 **같은 Postgres `iceberg_catalog`** 를
    재사용한다(별도 메타스토어 불필요, [overview.md](overview.md)).
  - **dbt 친화** — `dbt-trino` 어댑터로 SQL 변환을 선언적으로 관리.
  - **경량 SQL 전용** — 배치 SQL 변환이 주 워크로드라 범용 엔진(Spark)보다 단순(YAGNI).
- **제거 이유·트레이드오프**: 재설계에서 컴퓨트를 **Spark(배치)+Flink(스트림)** 2엔진으로 통일하며 Trino를 뺀다.
  단일 PC 자원(6/16) 절약과 엔진 수 축소가 목적이나, **성숙한 인터랙티브 SQL·`dbt-trino`를 잃는 비용**을 감수한다
  ([redesign.md](../redesign.md) §5). 배치 SQL은 dbt-spark, 대규모 rewrite/compaction은 Spark로 이관([spark.md](spark.md)).

## 운영 메모 (현행 compose 한정)

> 재설계 이행 완료 시 아래는 레거시 참조가 된다. 유지보수 프로시저(`rewrite_data_files`·`remove_orphan_files`)는
> Trino `ALTER TABLE ... EXECUTE`에서 **Spark 프로시저**로 이관한다([spark.md](spark.md)).

- **JVM 기반** — 힙이 메모리 최다 소비. `trino/etc/jvm.config`의 `Xmx`를 호스트 한도 내로 유지
  ([resource-sizing.md](../resource-sizing.md)의 "3파일 메모리 제약").
- **버전**: 현재 `trinodb/trino:468`. Trino는 주 단위 릴리스라 **LTS(현재 477 계열)** 를 우선한다
  (비-LTS는 다음 릴리스 후 패치 중단 — [conventions/docker.md](../conventions/docker.md) §1-3).
- **Iceberg 유지보수**: pyiceberg 미지원 프로시저(`remove_orphan_files`)를 Trino
  `ALTER TABLE ... EXECUTE`로 실행한다([security.md](../security.md) §4-1).

## 참고

- Trino 문서: https://trino.io/docs/current/
- Iceberg connector: https://trino.io/docs/current/connector/iceberg.html
- 릴리스 유형(LTS): https://trino.io/docs/current/release.html
