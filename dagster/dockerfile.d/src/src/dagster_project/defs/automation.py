"""잡·스케줄 정의 — `defs/` 자동발견 대상.

모듈 스코프의 잡/스케줄 객체는 `load_defs`가 자동 수집한다(@dg.definitions 불필요).
dbt 인제스트 그룹 전체를 매시각 빌드하는 잡·스케줄을 선언한다.
"""

import dagster as dg

dbt_all_job = dg.define_asset_job(
    "dbt_all_job",
    selection=dg.AssetSelection.groups("dbt_ingest"),
)

dbt_all_schedule = dg.ScheduleDefinition(
    name="dbt_all_schedule",
    job=dbt_all_job,
    cron_schedule="0 * * * *",
)
