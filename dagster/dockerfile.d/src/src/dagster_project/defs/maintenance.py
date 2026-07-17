"""Iceberg 유지보수 잡·스케줄 — `defs/` 자동발견 대상.

보존기간이 지난 스냅샷을 만료하고 orphan 파일을 정리해 메타데이터·데이터 파일이
무제한 누적되는 것을 막는다(docs/operations.md §2 · docs/security.md §4-1).
안전 순서 **expire snapshots → remove orphan files**를 op 의존성으로 강제한다.
대용량 append 3테이블(chartevents·labevents·nurse_charting)이 우선 대상이며,
이미 등록된 IcebergTableResource 바인딩을 단일 출처로 재사용한다.

- 스냅샷 만료: pyiceberg(`table.maintenance.expire_snapshots()`).
- orphan 정리: pyiceberg 0.11.x 미지원 → Trino 프로시저(`remove_orphan_files`)로 실행.

모듈 스코프의 잡/스케줄 객체는 `load_defs`가 자동 수집한다(@dg.definitions 불필요).

주의: Dagster가 context를 클래스 identity로 검사하므로, op 모듈에서는
`from __future__ import annotations`(어노테이션 문자열화)를 사용하지 않는다.
"""

from datetime import datetime, timedelta, timezone

from dagster_iceberg.resource import IcebergTableResource

import dagster as dg
from dagster import OpExecutionContext
from dagster_project.common.constants import CATALOG_NAME
from dagster_project.common.trino import TrinoResource

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
    """대용량 테이블의 보존기간 지난 스냅샷을 만료한다(안전 순서상 1단계).

    pyiceberg 0.11.x API:
    `table.maintenance.expire_snapshots().older_than(dt).commit()`
    (`older_than`는 tz-aware datetime을 받는다).
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


@dg.op(ins={"start": dg.In(dg.Nothing)})
def remove_iceberg_orphan_files(
    context: OpExecutionContext,
    trino: TrinoResource,
    mimiciv_chartevents_table: IcebergTableResource,
    mimiciv_labevents_table: IcebergTableResource,
    eicu_nurse_charting_table: IcebergTableResource,
) -> None:
    """스냅샷이 참조하지 않는 orphan 데이터 파일을 정리한다(안전 순서상 2단계).

    pyiceberg 0.11.x는 remove_orphan_files 미지원이라 Trino 프로시저로 실행한다.
    retention_threshold를 생략하면 Trino 기본값(min-retention 7일)이 적용된다
    (더 짧게 지정하면 프로시저가 거부한다). 테이블 목록은 스냅샷 만료 op와 동일하게
    IcebergTableResource 바인딩(schema_·table)을 단일 출처로 재사용한다.
    """
    for resource in (
        mimiciv_chartevents_table,
        mimiciv_labevents_table,
        eicu_nurse_charting_table,
    ):
        fqn = f"{CATALOG_NAME}.{resource.schema_}.{resource.table}"
        trino.execute(f"ALTER TABLE {fqn} EXECUTE remove_orphan_files")
        context.log.info("%s orphan 파일 정리 완료(retention 기본 7일)", fqn)


@dg.job
def iceberg_maintenance_job() -> None:
    """Iceberg 보존정책 적용: 스냅샷 만료 → orphan 파일 정리(순서 강제)."""
    remove_iceberg_orphan_files(start=expire_iceberg_snapshots())


iceberg_maintenance_schedule = dg.ScheduleDefinition(
    name="iceberg_maintenance_schedule",
    job=iceberg_maintenance_job,
    # 매주 일요일 03:00 KST. cron은 KST로 해석(docs/conventions/timezone.md).
    cron_schedule="0 3 * * 0",
    execution_timezone="Asia/Seoul",
)
