"""Iceberg Dagster 리소스 빌더 (데이터셋 무관 공통).

- Iceberg: dagster-iceberg PyArrowIcebergIOManager(일반 적재) /
  IcebergTableResource(대용량 경로)
- S3: dagster-aws S3Resource는 단순 리턴이라 빌더 없이 `definitions.py`에서 인라인하고,
  접속 파라미터(endpoint·키·region)는 `constants.py`에 둔다(추적 용이).

주의: dagster-iceberg의 IcebergCatalogConfig는 아직 dg.EnvVar를 지원하지 않으므로
(properties는 평문 문자열), 비밀값은 정의 로드 시점(컨테이너)의 os.environ에서 읽는다.
"""

from __future__ import annotations

import os

from dagster_iceberg.config import IcebergCatalogConfig
from dagster_iceberg.io_manager.arrow import PyArrowIcebergIOManager
from dagster_iceberg.resource import IcebergTableResource

from dagster_project.common.constants import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    CATALOG_NAME,
    ICEBERG_CATALOG_DB,
    S3_ENDPOINT,
    WAREHOUSE,
)


def catalog_properties() -> dict[str, str]:
    """Trino의 iceberg JDBC 카탈로그와 동일 설정(pyiceberg properties)."""
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    return {
        "type": "sql",
        "uri": f"postgresql+psycopg2://{user}:{password}@postgres:5432/{ICEBERG_CATALOG_DB}",
        "warehouse": WAREHOUSE,
        "s3.endpoint": S3_ENDPOINT,
        "s3.access-key-id": AWS_ACCESS_KEY_ID,
        "s3.secret-access-key": AWS_SECRET_ACCESS_KEY,
        "s3.region": AWS_REGION,
        "s3.path-style-access": "true",
    }


def build_catalog_config() -> IcebergCatalogConfig:
    """공통 Iceberg 카탈로그 설정."""
    return IcebergCatalogConfig(properties=catalog_properties())


def build_io_manager(namespace: str) -> PyArrowIcebergIOManager:
    """일반(부하 없는) 적재용 IO 매니저.

    자산이 반환한 pa.Table을 namespace.<asset>로 write 한다.
    """
    return PyArrowIcebergIOManager(
        name=CATALOG_NAME,
        config=build_catalog_config(),
        namespace=namespace,
    )


def build_table_resource(namespace: str, table: str) -> IcebergTableResource:
    """대용량 경로용 테이블 바인딩 리소스(청크 append 시 config로 카탈로그 재구성)."""
    return IcebergTableResource(
        name=CATALOG_NAME,
        config=build_catalog_config(),
        table=table,
        namespace=namespace,
    )
