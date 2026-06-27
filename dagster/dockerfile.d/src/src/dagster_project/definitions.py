"""코드 로케이션 진입점 (flat 레이아웃).

dg 자동발견(load_from_defs_folder)·컴포넌트(defs/) 대신, 각 subproject
(eicu·mimic_iv)가 자체 Definitions를 노출하고 여기서 Definitions.merge로 합친다.
각 데이터셋 subproject는 bronze 적재(@asset)와 자기 dbt 모델(@dbt_assets)을 함께 소유.

데이터셋 무관 공유 리소스(s3·dbt)와 잡/스케줄만 shared Definitions에 둔다.
리소스 키 규칙: 공유 s3·dbt는 여기 한 번만, 데이터셋 전용 IO 매니저·테이블 바인딩은
각 subproject의 definitions.py에서 정의한다(merge 시 키 충돌 없음).
"""

import dagster as dg
from dagster_project.common.dbt import build_dbt_resource
from dagster_project.common.resources import build_s3_resource
from dagster_project.eicu.definitions import defs as eicu_defs
from dagster_project.mimic_iv.definitions import defs as mimic_defs

dbt_all_job = dg.define_asset_job(
    "dbt_all_job",
    selection=dg.AssetSelection.groups("dbt_ingest"),
)

dbt_all_schedule = dg.ScheduleDefinition(
    name="dbt_all_schedule",
    job=dbt_all_job,
    cron_schedule="0 * * * *",
)

# 데이터셋 무관 공유 리소스 + 잡/스케줄
shared_defs = dg.Definitions(
    resources={"s3": build_s3_resource(), "dbt": build_dbt_resource()},
    jobs=[dbt_all_job],
    schedules=[dbt_all_schedule],
)

defs = dg.Definitions.merge(eicu_defs, mimic_defs, shared_defs)
