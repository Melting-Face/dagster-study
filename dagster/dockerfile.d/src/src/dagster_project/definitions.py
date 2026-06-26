from pathlib import Path

from dagster import (
    AssetSelection,
    Definitions,
    ScheduleDefinition,
    define_asset_job,
    load_from_defs_folder,
)


dbt_all_job = define_asset_job(
    "dbt_all_job",
    selection=AssetSelection.groups("dbt_ingest"),
)

dbt_all_schedule = ScheduleDefinition(
    name="dbt_all_schedule",
    job=dbt_all_job,
    cron_schedule="0 * * * *",
)

defs = Definitions.merge(
    load_from_defs_folder(path_within_project=Path(__file__).parent),
    Definitions(
        jobs=[dbt_all_job],
        schedules=[dbt_all_schedule],
    ),
)
