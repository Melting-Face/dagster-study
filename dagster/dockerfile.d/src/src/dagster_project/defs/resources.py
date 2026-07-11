"""공유 리소스 정의 — `defs/` 자동발견 대상.

`@dg.definitions`로 리소스만 담은 Definitions를 반환하면 `load_defs`가 수집·merge한다.
S3 접속·dbt·데이터셋별 IO 매니저·대용량 테이블 바인딩을 한 곳에서 선언한다.
접속 파라미터는 `common.constants`에서 참조하고, Iceberg 카탈로그 설정
(`IcebergCatalogConfig`)은 각 리소스에 직접 명시한다.

주의: dagster-iceberg의 IcebergCatalogConfig는 아직 dg.EnvVar를 지원하지 않으므로
(properties는 평문 문자열), 비밀값은 정의 로드 시점(컨테이너)의 os.environ에서 읽는다.
Trino의 iceberg JDBC 카탈로그와 동일한 pyiceberg properties를 쓴다.
"""

import os

from dagster_aws.s3 import S3Resource
from dagster_iceberg.config import IcebergCatalogConfig
from dagster_iceberg.io_manager.arrow import PyArrowIcebergIOManager
from dagster_iceberg.resource import IcebergTableResource

import dagster as dg
from dagster_project.common.constants import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    CATALOG_NAME,
    ICEBERG_CATALOG_DB,
    S3_ENDPOINT,
    WAREHOUSE,
)
from dagster_project.common.dbt import build_dbt_resource
from dagster_project.defs.eicu.constants import NAMESPACE as EICU_NS
from dagster_project.defs.mimic_iv.constants import NAMESPACE as MIMICIV_NS


@dg.definitions
def resources() -> dg.Definitions:
    """공유 리소스를 Definitions로 반환한다(load_defs가 자동 수집)."""
    # 비밀값은 정의 로드 시점(컨테이너)의 os.environ에서 읽는다(EnvVar 미지원).
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
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
                name=CATALOG_NAME,
                namespace=EICU_NS,
                config=IcebergCatalogConfig(
                    properties={
                        "type": "sql",
                        "uri": f"postgresql+psycopg2://{user}:{password}@postgres:5432/{ICEBERG_CATALOG_DB}",
                        "warehouse": WAREHOUSE,
                        "s3.endpoint": S3_ENDPOINT,
                        "s3.access-key-id": AWS_ACCESS_KEY_ID,
                        "s3.secret-access-key": AWS_SECRET_ACCESS_KEY,
                        "s3.region": AWS_REGION,
                        "s3.path-style-access": "true",
                    }
                ),
            ),
            "io_manager_mimiciv": PyArrowIcebergIOManager(
                name=CATALOG_NAME,
                namespace=MIMICIV_NS,
                config=IcebergCatalogConfig(
                    properties={
                        "type": "sql",
                        "uri": f"postgresql+psycopg2://{user}:{password}@postgres:5432/{ICEBERG_CATALOG_DB}",
                        "warehouse": WAREHOUSE,
                        "s3.endpoint": S3_ENDPOINT,
                        "s3.access-key-id": AWS_ACCESS_KEY_ID,
                        "s3.secret-access-key": AWS_SECRET_ACCESS_KEY,
                        "s3.region": AWS_REGION,
                        "s3.path-style-access": "true",
                    }
                ),
            ),
            # 대용량 경로 청크 append용 테이블 바인딩(IO 매니저 미사용).
            "mimiciv_chartevents_table": IcebergTableResource(
                name=CATALOG_NAME,
                namespace=MIMICIV_NS,
                table="chartevents",
                config=IcebergCatalogConfig(
                    properties={
                        "type": "sql",
                        "uri": f"postgresql+psycopg2://{user}:{password}@postgres:5432/{ICEBERG_CATALOG_DB}",
                        "warehouse": WAREHOUSE,
                        "s3.endpoint": S3_ENDPOINT,
                        "s3.access-key-id": AWS_ACCESS_KEY_ID,
                        "s3.secret-access-key": AWS_SECRET_ACCESS_KEY,
                        "s3.region": AWS_REGION,
                        "s3.path-style-access": "true",
                    }
                ),
            ),
            "mimiciv_labevents_table": IcebergTableResource(
                name=CATALOG_NAME,
                namespace=MIMICIV_NS,
                table="labevents",
                config=IcebergCatalogConfig(
                    properties={
                        "type": "sql",
                        "uri": f"postgresql+psycopg2://{user}:{password}@postgres:5432/{ICEBERG_CATALOG_DB}",
                        "warehouse": WAREHOUSE,
                        "s3.endpoint": S3_ENDPOINT,
                        "s3.access-key-id": AWS_ACCESS_KEY_ID,
                        "s3.secret-access-key": AWS_SECRET_ACCESS_KEY,
                        "s3.region": AWS_REGION,
                        "s3.path-style-access": "true",
                    }
                ),
            ),
            "eicu_nurse_charting_table": IcebergTableResource(
                name=CATALOG_NAME,
                namespace=EICU_NS,
                table="nurse_charting",
                config=IcebergCatalogConfig(
                    properties={
                        "type": "sql",
                        "uri": f"postgresql+psycopg2://{user}:{password}@postgres:5432/{ICEBERG_CATALOG_DB}",
                        "warehouse": WAREHOUSE,
                        "s3.endpoint": S3_ENDPOINT,
                        "s3.access-key-id": AWS_ACCESS_KEY_ID,
                        "s3.secret-access-key": AWS_SECRET_ACCESS_KEY,
                        "s3.region": AWS_REGION,
                        "s3.path-style-access": "true",
                    }
                ),
            ),
        },
    )
