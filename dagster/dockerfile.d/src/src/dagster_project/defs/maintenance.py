"""Iceberg 유지보수 잡·스케줄 — `defs/` 자동발견 대상.

작은 파일을 병합(컴팩션)하고, 보존기간이 지난 스냅샷을 만료하며, orphan 파일을 정리해
메타데이터·데이터 파일이 무제한 누적되는 것을 막는다
(docs/operations.md §2 · docs/security.md §4-1). 안전 순서
**compact → expire snapshots → remove orphan files** 를 op 의존성으로 강제한다.
대용량 append 3테이블(chartevents·labevents·nurse_charting)이 우선 대상이며,
이미 등록된 IcebergTableResource 바인딩을 단일 출처로 재사용한다.

- 컴팩션·orphan 정리: pyiceberg 0.11.x 미지원 → **Spark Iceberg 프로시저**
  (`rewrite_data_files`·`remove_orphan_files`). 재설계에서 Trino를 빼면서
  `ALTER TABLE ... EXECUTE`(Trino)에서 옮겨왔다(docs/architectures/trino.md).
- 스냅샷 만료: pyiceberg(`table.maintenance.expire_snapshots()`).

`remove_orphan_files`는 warehouse를 **Hadoop FileSystem으로 나열**한다(Iceberg의
S3FileIO로는 대체 불가 — 카탈로그가 모르는 파일을 찾는 게 목적이므로). Spark Connect
서버에 `spark.hadoop.fs.s3*` 설정이 있어야 하며, 없으면
`UnsupportedFileSystemException: No FileSystem for scheme "s3"`로 죽는다.

모듈 스코프의 잡/스케줄 객체는 `load_defs`가 자동 수집한다(@dg.definitions 불필요).

주의: Dagster가 context를 클래스 identity로 검사하므로, op 모듈에서는
`from __future__ import annotations`(어노테이션 문자열화)를 사용하지 않는다.
"""

from datetime import datetime, timedelta, timezone

from dagster_iceberg.resource import IcebergTableResource
from dagster_pyspark import LazyPySparkResource

import dagster as dg
from dagster import OpExecutionContext
from dagster_project.common.constants import CATALOG_NAME

# 스냅샷 보존기간(일). 이보다 오래된(timestamp <) 스냅샷을 만료한다.
# 현재 스냅샷·브랜치·태그가 가리키는 스냅샷은 pyiceberg가 자동 보호한다.
SNAPSHOT_RETENTION_DAYS = 7

# orphan 파일 보존기간(일). 이보다 **오래된** 파일만 삭제한다.
# Spark 기본값은 3일인데, 진행 중인 쓰기를 지울 위험을 줄이려 스냅샷 보존기간과 맞춘다
# (Trino는 min-retention 기본 7일이었다 — 이관 후에도 같은 값을 유지).
ORPHAN_RETENTION_DAYS = SNAPSHOT_RETENTION_DAYS

# 컴팩션 임계값(bytes). 이 크기 **미만** 파일이 bin-packing 대상이다.
# Trino `optimize(file_size_threshold => '100MB')`와 같은 의미이나, Spark는
# `min-input-files`(기본 5) 미만이면 그룹을 통째로 건너뛴다 — 파일이 몇 개뿐인
# 테이블에서 "0건 재작성"이 나오는 건 정상이다.
COMPACTION_MIN_FILE_SIZE_BYTES = 100 * 1024 * 1024


@dg.op
def optimize_iceberg_files(
    context: OpExecutionContext,
    spark: LazyPySparkResource,
    mimiciv_chartevents_table: IcebergTableResource,
    mimiciv_labevents_table: IcebergTableResource,
    eicu_nurse_charting_table: IcebergTableResource,
) -> None:
    """작은 파일을 큰 파일로 병합한다(안전 순서상 1단계, 컴팩션).

    청크 append로 쌓인 small-files를 Spark `rewrite_data_files` 프로시저로
    bin-packing한다. pyiceberg 0.11.x는 이 API를 지원하지 않는다.

    프로시저의 `table` 인자는 **카탈로그를 제외한** `<schema>.<table>` 형식이다
    (카탈로그는 `iceberg.system.` 접두로 이미 지정된다).
    """
    for resource in (
        mimiciv_chartevents_table,
        mimiciv_labevents_table,
        eicu_nurse_charting_table,
    ):
        qualified = f"{resource.schema_}.{resource.table}"
        rows = spark.spark_session.sql(
            f"CALL {CATALOG_NAME}.system.rewrite_data_files("
            f"table => '{qualified}', "
            f"options => map('min-file-size-bytes', "
            f"'{COMPACTION_MIN_FILE_SIZE_BYTES}'))"
        ).collect()
        # 프로시저는 재작성 통계 1행을 돌려준다(rewritten/added 파일 수·바이트).
        stats = rows[0].asDict() if rows else {}
        context.log.info("%s 컴팩션 완료 — %s", qualified, stats)


@dg.op(ins={"start": dg.In(dg.Nothing)})
def expire_iceberg_snapshots(
    context: OpExecutionContext,
    mimiciv_chartevents_table: IcebergTableResource,
    mimiciv_labevents_table: IcebergTableResource,
    eicu_nurse_charting_table: IcebergTableResource,
) -> None:
    """대용량 테이블의 보존기간 지난 스냅샷을 만료한다(안전 순서상 2단계).

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
    spark: LazyPySparkResource,
    mimiciv_chartevents_table: IcebergTableResource,
    mimiciv_labevents_table: IcebergTableResource,
    eicu_nurse_charting_table: IcebergTableResource,
) -> None:
    """스냅샷이 참조하지 않는 orphan 데이터 파일을 정리한다(안전 순서상 3단계).

    pyiceberg 0.11.x는 remove_orphan_files 미지원이라 Spark 프로시저로 실행한다.
    `older_than`은 **명시**한다 — Spark 기본값은 3일이라 Trino(7일)보다 공격적이다.

    이 프로시저만 warehouse를 Hadoop FileSystem으로 나열한다(모듈 docstring 참고).
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=ORPHAN_RETENTION_DAYS)
    for resource in (
        mimiciv_chartevents_table,
        mimiciv_labevents_table,
        eicu_nurse_charting_table,
    ):
        qualified = f"{resource.schema_}.{resource.table}"
        rows = spark.spark_session.sql(
            f"CALL {CATALOG_NAME}.system.remove_orphan_files("
            f"table => '{qualified}', "
            f"older_than => TIMESTAMP '{cutoff.strftime('%Y-%m-%d %H:%M:%S')}')"
        ).collect()
        # 삭제된 파일 경로가 행으로 돌아온다(0행 = 지울 것 없음).
        context.log.info(
            "%s orphan 파일 %d건 정리(older_than=%s UTC)",
            qualified,
            len(rows),
            cutoff.isoformat(),
        )


@dg.job
def iceberg_maintenance_job() -> None:
    """Iceberg 보존정책 적용: 컴팩션 → 스냅샷 만료 → orphan 정리(순서 강제)."""
    remove_iceberg_orphan_files(
        start=expire_iceberg_snapshots(start=optimize_iceberg_files())
    )


iceberg_maintenance_schedule = dg.ScheduleDefinition(
    name="iceberg_maintenance_schedule",
    job=iceberg_maintenance_job,
    # 매주 일요일 03:00 KST. cron은 KST로 해석(docs/conventions/timezone.md).
    cron_schedule="0 3 * * 0",
    execution_timezone="Asia/Seoul",
)
