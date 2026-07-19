# Apache Spark (아키텍처 · 프로젝트 관점)

## 개요

Spark는 **범용 분산 데이터 처리 엔진**이다. driver가 DAG를 스케줄링하고 여러 executor가 파티션을
병렬 처리한다. RDD/DataFrame API, 배치·마이크로배치 스트리밍(Structured Streaming), SQL, ML(MLlib)을
아우르며, 셔플·인메모리 캐시로 대규모 변환에 강하다.

- 최신 안정: **Spark 4.2.0**(2026-07). Arrow 최적화 Python UDF 기본화, CDC(`CHANGES`), 지오공간·
  벡터/AI 함수, Real-Time Mode 등.

## 이 프로젝트에서의 위치 — 🔎 미채택

- **현재 불필요**: 워크로드가 "csv.gz → Iceberg 적재 + SQL 변환(dbt)"인 **배치 SQL** 중심이라
  Trino+dbt로 충분하다. Spark의 범용 처리(코드 기반 복잡 변환·대규모 셔플·ML)는 현재 요구가 없다(YAGNI).
- **도입 시나리오**:
  - **대규모 Iceberg 유지보수** — 대용량 `rewrite_data_files`(compaction)·`remove_orphan_files`를
    Spark 프로시저로. 현재는 Trino로 대체([security.md](../security.md) §4-1).
  - **ML 피처·복잡 변환** — SQL로 표현이 어려운 대규모 파이프라인.
- **Trino 대비**: Spark=범용·상태 있는 처리·코드 API / Trino=SQL 연합 쿼리·무상태·낮은 오버헤드([trino.md](trino.md)).

## 운영 메모 (도입 시)

- Iceberg는 `iceberg-spark-runtime`으로 **동일 JDBC 카탈로그**에 접속 가능 → Trino와 카탈로그 공유.
- executor 메모리·셔플 파티션 튜닝이 성능 핵심.

## 참고

- Spark 문서: https://spark.apache.org/docs/latest/
- Spark 4.2.0 릴리스: https://spark.apache.org/releases/spark-release-4-2-0.html
- Iceberg + Spark: https://iceberg.apache.org/docs/latest/spark-getting-started/
