"""MIMIC-IV 데이터셋 전용 상수."""

# Iceberg 네임스페이스 / Dagster 그룹
NAMESPACE = "bronze_mimiciv"
GROUP_NAME = "bronze_mimiciv"

# 원천 csv.gz 루트 (모듈별 하위 경로: hosp/, icu/)
SOURCE_BASE = "s3://warehouse/raw/mimiciv"
