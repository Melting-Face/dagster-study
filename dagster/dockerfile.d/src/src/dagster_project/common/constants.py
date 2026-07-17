"""S3(csv.gz) → Iceberg 적재 공통 상수 (데이터셋 무관)."""

import os

# Iceberg JDBC 카탈로그 — Trino iceberg.properties의 catalog-name과 반드시 일치
CATALOG_NAME = "iceberg"
ICEBERG_CATALOG_DB = "iceberg_catalog"
WAREHOUSE = os.environ.get("ICEBERG_WAREHOUSE", "s3://warehouse")

# SeaweedFS(S3 호환) 엔드포인트 (scheme 포함)
S3_ENDPOINT = os.environ.get("ICEBERG_S3_ENDPOINT", "http://seaweedfs:8333")

# S3 접속 자격증명/리전 (env 참조 — S3Resource·pyiceberg 카탈로그 공용)
# 값은 코드에 하드코딩하지 않고 env에서 읽는다(12-Factor Config).
AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Trino 쿼리 엔진 접속 (Iceberg 유지보수 프로시저 실행용)
# 컨테이너 내부망 값이라 비밀 아님 → 기본값 제공, 필요 시 env로 재정의.
TRINO_HOST = os.environ.get("TRINO_HOST", "trino")
TRINO_PORT = int(os.environ.get("TRINO_PORT", "8080"))
TRINO_USER = os.environ.get("TRINO_USER", "dagster")

# 적재 기본값
DEFAULT_CHUNK_ROWS = 1_000_000
DEFAULT_NAMESPACE = "bronze"
DEFAULT_GROUP_NAME = "bronze"
