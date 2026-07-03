"""공유 리소스 정의 — `defs/` 자동발견 대상.

`@dg.definitions`로 리소스만 담은 Definitions를 반환하면 `load_defs`가 수집·merge한다.
S3 접속·dbt·데이터셋별 IO 매니저·대용량 테이블 바인딩을 한 곳에서 선언한다.
접속 파라미터는 `common.constants`, 카탈로그 설정은 `common.resources`에서 참조한다.
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
from dagster_project.defs.eicu.constants import NAMESPACE as EICU_NS
from dagster_project.defs.mimic_iv.constants import NAMESPACE as MIMICIV_NS


@dg.definitions
def resources() -> dg.Definitions:
    """공유 리소스를 Definitions로 반환한다(load_defs가 자동 수집)."""
    return dg.Definitions(
        resources={
            # 공유: S3 접속(SeaweedFS). 파라미터는 common.constants에서 추적.
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
            # 대용량 경로 청크 append용 테이블 바인딩(IO 매니저 미사용).
            "mimiciv_chartevents_table": IcebergTableResource(
                name=CATALOG_NAME,
                config=build_catalog_config(),
                namespace=MIMICIV_NS,
                table="chartevents",
            ),
            "mimiciv_labevents_table": IcebergTableResource(
                name=CATALOG_NAME,
                config=build_catalog_config(),
                namespace=MIMICIV_NS,
                table="labevents",
            ),
            "eicu_nurse_charting_table": IcebergTableResource(
                name=CATALOG_NAME,
                config=build_catalog_config(),
                namespace=EICU_NS,
                table="nurse_charting",
            ),
        },
    )
