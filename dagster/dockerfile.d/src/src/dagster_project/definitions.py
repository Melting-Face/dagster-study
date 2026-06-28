"""코드 로케이션 진입점 — 단일 Definitions로 모든 wiring을 한 곳에 모은다.

데이터셋 폴더(`<dataset>/`)에는 **정의만** 둔다(constants·assets·dbt_assets).
자산 등록·리소스 바인딩·잡/스케줄을 모두 이 파일에서 선언한다(중간 레이어 없음).
모듈 스코프 Definitions는 `defs` 1개(autodiscovery 제약).
"""

import dagster as dg
from dagster_project.common.dbt import build_dbt_resource
from dagster_project.common.resources import (
    build_io_manager,
    build_s3_resource,
    build_table_resource,
)
from dagster_project.eicu import assets as eicu_assets
from dagster_project.eicu import dbt_assets as eicu_dbt
from dagster_project.eicu.constants import NAMESPACE as EICU_NS
from dagster_project.mimic_iv import assets as mimic_assets
from dagster_project.mimic_iv import dbt_assets as mimic_dbt
from dagster_project.mimic_iv.constants import NAMESPACE as MIMICIV_NS

dbt_all_job = dg.define_asset_job(
    "dbt_all_job",
    selection=dg.AssetSelection.groups("dbt_ingest"),
)

dbt_all_schedule = dg.ScheduleDefinition(
    name="dbt_all_schedule",
    job=dbt_all_job,
    cron_schedule="0 * * * *",
)

defs = dg.Definitions(
    assets=[
        # bronze 적재(@asset)는 데이터셋 assets 모듈에서 수집
        *dg.load_assets_from_modules([eicu_assets, mimic_assets]),
        # 데이터셋 dbt 모델(@dbt_assets)
        eicu_dbt.eicu_dbt_models,
        mimic_dbt.mimic_iv_dbt_models,
    ],
    resources={
        # 공유
        "s3": build_s3_resource(),
        "dbt": build_dbt_resource(),
        # 데이터셋 전용 IO 매니저
        "io_manager_eicu": build_io_manager(EICU_NS),
        "io_manager_mimiciv": build_io_manager(MIMICIV_NS),
        # 대용량 경로(chartevents) 청크 append용 테이블 바인딩
        "mimiciv_chartevents_table": build_table_resource(MIMICIV_NS, "chartevents"),
    },
    jobs=[dbt_all_job],
    schedules=[dbt_all_schedule],
)
