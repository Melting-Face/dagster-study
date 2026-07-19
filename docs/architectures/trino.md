# Trino (아키텍처 · 프로젝트 관점)

## 개요

Trino는 **MPP(대규모 병렬 처리) 분산 SQL 쿼리 엔진**이다. 데이터를 자체 저장하지 않고
(무상태), 여러 소스(Iceberg·Hive·RDB 등)에 **연합 쿼리(federated query)** 한다.
coordinator가 SQL을 분해해 worker들에 분산하고, 메모리 기반 파이프라인으로 배치 SQL을
빠르게 처리한다.

## 이 프로젝트에서의 위치 — ✅ 채택

- **역할**: dbt(`dbt-trino`)가 접속하는 쿼리 엔진. Iceberg 테이블을 읽고 써서 silver 모델을 만든다.
- **채택 이유**:
  - **Iceberg JDBC 카탈로그 공유** — Trino와 Dagster(pyiceberg)가 **같은 Postgres `iceberg_catalog`** 를
    재사용한다(별도 메타스토어 불필요, [overview.md](overview.md)).
  - **dbt 친화** — `dbt-trino` 어댑터로 SQL 변환을 선언적으로 관리.
  - **경량 SQL 전용** — 배치 SQL 변환이 주 워크로드라 범용 엔진(Spark)보다 단순(YAGNI).
- **Spark 대비**: Trino=SQL 쿼리·연합·무상태(낮은 오버헤드) / Spark=범용 처리(코드 기반 변환·ML·대규모 셔플).
  현재 워크로드(csv→Iceberg 적재 후 SQL 변환)엔 Trino가 적합. 대규모 rewrite/compaction·ML은 [spark.md](spark.md) 검토.

## 운영 메모

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
