from pathlib import Path

from dagster import (
    AssetSelection,
    Definitions,
    ScheduleDefinition,
    define_asset_job,
    load_from_defs_folder,
)

from dagster_project.common.resources import (
    build_io_manager,
    build_s3_resource,
    build_table_resource,
)
from dagster_project.defs.eicu.constants import NAMESPACE as EICU_NS
from dagster_project.defs.mimic_iv.constants import NAMESPACE as MIMICIV_NS

dbt_all_job = define_asset_job(
    "dbt_all_job",
    selection=AssetSelection.groups("dbt_ingest"),
)

dbt_all_schedule = ScheduleDefinition(
    name="dbt_all_schedule",
    job=dbt_all_job,
    cron_schedule="0 * * * *",
)

# S3/Iceberg 리소스 (데이터셋별 IO 매니저 + 대용량 테이블 바인딩)
_resources = {
    "s3": build_s3_resource(),
    "io_manager_mimiciv": build_io_manager(MIMICIV_NS),
    "io_manager_eicu": build_io_manager(EICU_NS),
    # 대용량 경로(chartevents)용 테이블 바인딩 리소스
    "mimiciv_chartevents_table": build_table_resource(MIMICIV_NS, "chartevents"),
}

defs = Definitions.merge(
    load_from_defs_folder(path_within_project=Path(__file__).parent),
    Definitions(
        jobs=[dbt_all_job],
        schedules=[dbt_all_schedule],
        resources=_resources,
    ),
)
