# 아키텍처 문서 (architectures)

이 프로젝트의 전체 스택과, 각 처리·배포 기술을 **프로젝트 결정 관점**으로 정리한다.
채택 ✅ / 채택·이행중(PoC 게이트) 🚧 / 미채택(참고·향후 검토) 🔎로 표기한다.

> **재설계 진행중**: 호스트 Dagster + K8s(Spark Operator)로의 이행 로드맵은 [../redesign.md](../redesign.md).

## 목차

| 문서 | 상태 | 내용 |
| --- | --- | --- |
| [overview.md](overview.md) | 🚧 | 현행 스택 스냅샷·데이터 흐름(Dagster·dbt·Iceberg·SeaweedFS) — **재설계 이행 중**이라 Trino 경로는 제거 대상이고, 스냅샷은 관측 시점과 함께 읽는다 |
| [docker.md](docker.md) | ✅ | 컨테이너·compose 배포(채택) |
| [spark.md](spark.md) | 🚧 | 배치 엔진 — 대용량 인제스트 + dbt-spark 마트 + 유지보수(이행중) |
| [flink.md](flink.md) | 🚧⏸ | 스트림 엔진 — 실시간 Sepsis-3 조기경보. 오퍼레이터는 **`scripts/k8s-operators.sh` 기본 설치**(제외하려면 `INSTALL_FLINK=false`)이고 **Iceberg 배치 왕복이 실증**됐다(2026-08-22, 오퍼레이터 1.15.0). ⏸는 **스트리밍 미착수**(Redpanda·체크포인트·RocksDB 미배포 — Phase 3)를 뜻하며, 세션 클러스터는 검증 후 회수 규율에 따라 내려 둔다 |
| [k8s.md](k8s.md) | 🚧 | 컨테이너 오케스트레이션 — 컴퓨트·데이터 서비스 이전(이행중) |
| [oci.md](oci.md) | 🔎 | 클라우드 이행 — OCI Always Free A1(ARM) + Terraform + k3s(학습·확장 경로) |
| [trino.md](trino.md) | 🔎 | MPP SQL 엔진 — 현행 compose까지 채택, **재설계로 제거**(dbt→dbt-spark) |
| [monitoring.md](monitoring.md) | 🔎 | 모니터링·관측 — Prometheus 선언이 compose에 남아 있고 `--profile monitoring`이면 **수집도 된다**. 그런데 **보는 대상이 정본이 아니라**(스토리지 정본은 K8s로 이전, 그쪽엔 메트릭 포트 없음) 미채택. 현행 관측 실태(healthcheck·probe·메트릭·알림)와 대안 미채택 사유. 규칙 정본은 [conventions/monitoring.md](../conventions/monitoring.md) |

## 각 문서 형식

**개요 / 이 프로젝트에서의 위치(채택 이유·대안 비교) / 운영 메모 / 참고(공식 문서)**.

> 배포·운영 **규칙**은 [conventions/docker.md](../conventions/docker.md)·[conventions/k8s.md](../conventions/k8s.md),
> 자원 **수치**는 [resource-sizing.md](../resource-sizing.md)에서 단일 관리한다.
