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

- **지금**: **Trino `optimize`** 로 처리한다. `remove_orphan_files`를 Trino로 실행한 결정과 일관되며
  (Spark 미도입, [security.md](../security.md) §4-1), 유지보수 잡의 **1단계 op로 구현**했다
  ([maintenance.py](../../dagster/dockerfile.d/src/src/dagster_project/defs/maintenance.py)의 `optimize_iceberg_files`).
- **언제 Spark로**: 데이터·컴팩션 빈도가 커져 쿼리용 Trino와의 **자원 경합**이 문제되면, 유지보수를
  별도 Spark(또는 전용 Trino 클러스터)로 분리한다.
- **안전 순서**: **compact(optimize) → expire snapshots → remove orphan files**(현행 잡이 op 의존성으로
  강제). 컴팩션이 새 파일·스냅샷을 만든 뒤 만료가 옛 작은 파일 참조를 풀고, orphan 정리가 잔여를 제거한다.

## 참고

- Spark 문서: https://spark.apache.org/docs/latest/
- Spark 4.2.0 릴리스: https://spark.apache.org/releases/spark-release-4-2-0.html
- Iceberg + Spark: https://iceberg.apache.org/docs/latest/spark-getting-started/
- Iceberg Spark 프로시저(`rewrite_data_files`): https://iceberg.apache.org/docs/latest/spark-procedures/
- Trino Iceberg `optimize`(컴팩션): https://trino.io/docs/current/connector/iceberg.html
