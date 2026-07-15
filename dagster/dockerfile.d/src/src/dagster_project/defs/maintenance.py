"""Iceberg 유지보수 잡·스케줄 — `defs/` 자동발견 대상.

보존기간이 지난 스냅샷을 만료해 메타데이터·데이터 파일이 무제한 누적되는 것을 막는다
(docs/operations.md §2 보존정책 · docs/security.md §4-1). 대용량 append 테이블
(chartevents·labevents·nurse_charting)이 스냅샷을 가장 빠르게 쌓으므로 우선 대상이며,
이미 등록된 IcebergTableResource 바인딩을 재사용해 카탈로그 설정 중복 없이 처리한다.

모듈 스코프의 잡/스케줄 객체는 `load_defs`가 자동 수집한다(@dg.definitions 불필요).

주의: Dagster가 context를 클래스 identity로 검사하므로, op 모듈에서는
`from __future__ import annotations`(어노테이션 문자열화)를 사용하지 않는다.
"""

from datetime import datetime, timedelta, timezone

from dagster_iceberg.resource import IcebergTableResource

import dagster as dg
from dagster import OpExecutionContext

# 스냅샷 보존기간(일). 이보다 오래된(timestamp <) 스냅샷을 만료한다.
# 현재 스냅샷·브랜치·태그가 가리키는 스냅샷은 pyiceberg가 자동 보호한다.
SNAPSHOT_RETENTION_DAYS = 7


@dg.op
def expire_iceberg_snapshots(
    context: OpExecutionContext,
    mimiciv_chartevents_table: IcebergTableResource,
    mimiciv_labevents_table: IcebergTableResource,
    eicu_nurse_charting_table: IcebergTableResource,
) -> None:
    """대용량 테이블의 보존기간 지난 스냅샷을 만료한다.

    pyiceberg 0.11.x API:
    `table.maintenance.expire_snapshots().older_than(dt).commit()`
    (`older_than`는 tz-aware datetime을 받는다). orphan 파일 정리
    (remove_orphan_files)는 pyiceberg 0.11.x 미지원이라 필요 시 Trino/Spark
    프로시저로 대체한다(docs/security.md §4-1).
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    for resource in (
        mimiciv_chartevents_table,
        mimiciv_labevents_table,
        eicu_nurse_charting_table,
    ):
        table = resource.load()
        before = len(table.metadata.snapshots)
        table.maintenance.expire_snapshots().older_than(cutoff).commit()
        after = len(table.metadata.snapshots)
        context.log.info(
            "%s.%s 스냅샷 만료: %d → %d (cutoff=%s)",
            resource.schema_,
            resource.table,
            before,
            after,
            cutoff.isoformat(),
        )


@dg.job
def iceberg_maintenance_job() -> None:
    """Iceberg 스냅샷 보존정책을 적용하는 유지보수 잡."""
    expire_iceberg_snapshots()


iceberg_maintenance_schedule = dg.ScheduleDefinition(
    name="iceberg_maintenance_schedule",
    job=iceberg_maintenance_job,
    # 매주 일요일 03:00 KST. cron은 KST로 해석(docs/conventions/timezone.md).
    cron_schedule="0 3 * * 0",
    execution_timezone="Asia/Seoul",
)
