"""코드 로케이션 진입점 — 단일 Definitions로 모든 wiring을 한 곳에 모은다.

데이터셋 폴더(`<dataset>/`)에는 **정의만** 둔다(constants·assets·dbt_assets).
자산 등록·리소스 바인딩·잡/스케줄을 모두 이 파일에서 선언한다(중간 레이어 없음).
모듈 스코프 Definitions는 `defs` 1개(autodiscovery 제약).
"""

from dagster_aws.s3 import S3Resource
from dagster_iceberg.io_manager.arrow import PyArrowIcebergIOManager
from dagster_iceberg.resource import IcebergTableResource

import dagster as dg
from dagster_project.common.constants import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    CATALOG_NAME,
    S3_ENDPOINT,
)
from dagster_project.common.dbt import build_dbt_resource
from dagster_project.common.resources import build_catalog_config
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
        # 공유: S3 접속(SeaweedFS). 단순 리턴이라 인라인, 파라미터는 constants에서 추적.
        "s3": S3Resource(
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        ),
        "dbt": build_dbt_resource(),
        # 데이터셋 전용 IO 매니저 (일반 적재: pa.Table → namespace.<asset> write)
        "io_manager_eicu": PyArrowIcebergIOManager(
            name=CATALOG_NAME, config=build_catalog_config(), namespace=EICU_NS
        ),
        "io_manager_mimiciv": PyArrowIcebergIOManager(
            name=CATALOG_NAME, config=build_catalog_config(), namespace=MIMICIV_NS
        ),
        # 대용량 경로(chartevents) 청크 append용 테이블 바인딩
        "mimiciv_chartevents_table": IcebergTableResource(
            name=CATALOG_NAME,
            config=build_catalog_config(),
            namespace=MIMICIV_NS,
            table="chartevents",
        ),
    },
    jobs=[dbt_all_job],
    schedules=[dbt_all_schedule],
)
