"""S3/Iceberg 접속 유틸 (데이터셋 무관 공통).

메타스토어 없이 Trino와 동일한 Iceberg JDBC 카탈로그(Postgres)를 pyiceberg로 재사용한다.
"""

from __future__ import annotations

import os

from dagster_project.common.constants import (
    CATALOG_NAME,
    ICEBERG_CATALOG_DB,
    S3_ENDPOINT,
    WAREHOUSE,
)


def load_iceberg_catalog():
    """Trino의 iceberg.jdbc-catalog과 동일 설정으로 pyiceberg SqlCatalog를 만든다."""
    from pyiceberg.catalog.sql import SqlCatalog

    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    return SqlCatalog(
        CATALOG_NAME,
        **{
            "uri": f"postgresql+psycopg2://{user}:{password}@postgres:5432/{ICEBERG_CATALOG_DB}",
            "warehouse": WAREHOUSE,
            "s3.endpoint": S3_ENDPOINT,
            "s3.access-key-id": os.environ["AWS_ACCESS_KEY_ID"],
            "s3.secret-access-key": os.environ["AWS_SECRET_ACCESS_KEY"],
            "s3.region": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "s3.path-style-access": "true",
        },
    )


def get_s3_filesystem():
    """SeaweedFS(S3 호환)용 s3fs 파일시스템."""
    import s3fs

    return s3fs.S3FileSystem(
        key=os.environ["AWS_ACCESS_KEY_ID"],
        secret=os.environ["AWS_SECRET_ACCESS_KEY"],
        client_kwargs={"endpoint_url": S3_ENDPOINT},
        config_kwargs={"s3": {"addressing_style": "path"}},
    )
