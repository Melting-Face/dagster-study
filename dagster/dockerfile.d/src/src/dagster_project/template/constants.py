"""S3(csv.gz) → Iceberg 적재 템플릿 상수."""

import os

# Iceberg JDBC 카탈로그 — Trino iceberg.properties의 catalog-name과 반드시 일치
CATALOG_NAME = "iceberg"
ICEBERG_CATALOG_DB = "iceberg_catalog"
WAREHOUSE = os.environ.get("ICEBERG_WAREHOUSE", "s3://warehouse")

# SeaweedFS(S3 호환) 엔드포인트 (scheme 포함)
S3_ENDPOINT = os.environ.get("ICEBERG_S3_ENDPOINT", "http://seaweedfs:8333")

# 적재 기본값
DEFAULT_CHUNK_ROWS = 1_000_000
DEFAULT_NAMESPACE = "bronze"
DEFAULT_GROUP_NAME = "bronze"
