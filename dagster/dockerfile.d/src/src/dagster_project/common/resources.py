"""Iceberg 카탈로그 설정 (데이터셋 무관 공통).

dagster-iceberg IO 매니저/테이블 리소스가 공유하는 **카탈로그 설정**만 둔다.
리소스 인스턴스(IO 매니저·테이블 리소스·S3)는 단순 생성이라 빌더 없이
`definitions.py`에서 인라인하고, 이 모듈은 그들이 공유하는 substantive 설정만 제공한다.

주의: dagster-iceberg의 IcebergCatalogConfig는 아직 dg.EnvVar를 지원하지 않으므로
(properties는 평문 문자열), 비밀값은 정의 로드 시점(컨테이너)의 os.environ에서 읽는다.
"""

from __future__ import annotations

import os

from dagster_iceberg.config import IcebergCatalogConfig

from dagster_project.common.constants import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
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
    """공통 Iceberg 카탈로그 설정 (IO 매니저·테이블 리소스 공용)."""
    return IcebergCatalogConfig(properties=catalog_properties())
