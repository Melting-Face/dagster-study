# 아키텍처 문서 (architectures)

이 프로젝트의 전체 스택과, 각 처리·배포 기술을 **프로젝트 결정 관점**으로 정리한다.
현재 채택한 기술은 ✅, 미채택(참고·향후 검토)은 🔎로 표기한다.

## 목차

| 문서 | 상태 | 내용 |
| --- | --- | --- |
| [overview.md](overview.md) | ✅ | 현행 전체 스택·데이터 흐름(Dagster·dbt·Trino·Iceberg·SeaweedFS) |
| [trino.md](trino.md) | ✅ | MPP SQL 쿼리 엔진(채택) |
| [docker.md](docker.md) | ✅ | 컨테이너·compose 배포(채택) |
| [spark.md](spark.md) | 🔎 | 범용 분산 처리(미채택) |
| [flink.md](flink.md) | 🔎 | 스트림 처리(미채택) |
| [k8s.md](k8s.md) | 🔎 | 컨테이너 오케스트레이션(향후 배포 옵션) |

## 각 문서 형식

**개요 / 이 프로젝트에서의 위치(채택 이유·대안 비교) / 운영 메모 / 참고(공식 문서)**.

> 배포·운영 **규칙**은 [conventions/docker.md](../conventions/docker.md)·[conventions/k8s.md](../conventions/k8s.md),
> 자원 **수치**는 [resource-sizing.md](../resource-sizing.md)에서 단일 관리한다.
