# Apache Flink (아키텍처 · 프로젝트 관점)

## 개요

Flink는 **상태 기반 스트림 처리 엔진**이다. 무한 스트림을 이벤트 시간(event-time) 기준으로 낮은
지연에 처리하고, 체크포인트로 **정확히 한 번(exactly-once)** 상태를 보장한다. JobManager가 조율하고
TaskManager가 병렬 처리하며, 배치는 스트림의 특수 경우로 취급한다(통합 API).

- 최신 안정: **Flink 2.3.0**(2026-06). (2.0은 2025-03의 메이저 마일스톤)

## 이 프로젝트에서의 위치 — 🚧 채택·이행중(스트리밍 계층)

- **채택 방향**: [재설계](../redesign.md)에서 컴퓨트를 **Spark(배치)+Flink(스트림)** 으로 나누며 Flink를 도입한다.
  Trino는 제거한다. 전체 로드맵은 [redesign.md](../redesign.md) Phase 3.
- **역할(Flink의 존재이유)**: MIMIC/eICU는 본래 배치 데이터지만, **`vitalsign` 등을 Redpanda로 리플레이**해
  스트림을 만들고 **이벤트타임 윈도우로 실시간 SOFA/Sepsis-3 조기경보**를 계산한다. 배치(Spark/dbt-spark)와
  **역할이 겹치지 않는** 스트리밍 유스케이스를 부여해 "엔진을 위한 엔진"을 피한다([redesign.md](../redesign.md) 급소①).
- **실행 방식**: **Flink Kubernetes Operator**(Helm)로 **`FlinkDeployment`(CRD)** 를 배포한다.
  JobManager/TaskManager를 선언적으로 관리하고, Dagster(호스트)가 잡 수명주기를 트리거·관측한다.
- **Spark 스트리밍 대비**: Flink=네이티브 스트림(레코드 단위·낮은 지연·풍부한 상태) /
  Spark Structured Streaming=마이크로배치. 저지연·상태 중심이라 Flink를 택한다.

## 운영 메모 (이행)

- **소스**: Redpanda(Kafka API, 경량). **싱크**: Iceberg(Spark와 동일 JDBC 카탈로그 공유, 낙관적 동시성).
- **체크포인트**: S3 호환 **SeaweedFS 재사용**(path-style 강제), 상태 백엔드 RocksDB.
- **자원·시분할**: JM+TM는 6/16 예산에서 **배치(Spark)와 동시 실행 금지**(시분할). 배분은
  [resource-sizing.md](../resource-sizing.md) "Kubernetes 재설계 시나리오".
- **카탈로그 정합**: Spark·Flink 동시 writer 구조라 장기적으로 REST 카탈로그 이행 유인이 크다([redesign.md](../redesign.md) 급소②).

## 참고

- Flink 문서(stable): https://flink.apache.org/documentation/flink-stable/
- 다운로드/릴리스: https://flink.apache.org/downloads/
- Flink Kubernetes Operator: https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-main/
- Flink + Iceberg connector: https://iceberg.apache.org/docs/latest/flink/
- Redpanda: https://docs.redpanda.com/
