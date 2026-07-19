# Apache Flink (아키텍처 · 프로젝트 관점)

## 개요

Flink는 **상태 기반 스트림 처리 엔진**이다. 무한 스트림을 이벤트 시간(event-time) 기준으로 낮은
지연에 처리하고, 체크포인트로 **정확히 한 번(exactly-once)** 상태를 보장한다. JobManager가 조율하고
TaskManager가 병렬 처리하며, 배치는 스트림의 특수 경우로 취급한다(통합 API).

- 최신 안정: **Flink 2.3.0**(2026-06). (2.0은 2025-03의 메이저 마일스톤)

## 이 프로젝트에서의 위치 — 🔎 미채택

- **현재 불필요**: 수집·변환이 **배치**(시간별 스케줄 `dbt_all_schedule`)라 진짜 스트리밍이 필요 없다.
  상태 있는 저지연 처리의 복잡도는 YAGNI.
- **도입 시나리오**: 실시간 수집(CDC·IoT/센서 스트림), 낮은 지연 집계·알림, 이벤트 시간 윈도우 분석.
- **Spark 스트리밍 대비**: Flink=네이티브 스트림(레코드 단위·낮은 지연·풍부한 상태) /
  Spark Structured Streaming=마이크로배치. 저지연·상태 중심이면 Flink.

## 운영 메모 (도입 시)

- 체크포인트 저장소는 S3 호환 **SeaweedFS 재사용** 가능, 상태 백엔드는 RocksDB.
- 오케스트레이션은 Dagster를 유지하고, Flink 잡은 외부 트리거/센서로 연계한다.

## 참고

- Flink 문서(stable): https://flink.apache.org/documentation/flink-stable/
- 다운로드/릴리스: https://flink.apache.org/downloads/
