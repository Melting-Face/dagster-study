"""eICU-CRD 데이터셋 전용 상수."""

# Iceberg 네임스페이스 / Dagster 그룹
NAMESPACE = "bronze_eicu"
GROUP_NAME = "bronze_eicu"

# 원천 csv.gz 루트 (eICU는 플랫 구조)
SOURCE_BASE = "s3://warehouse/raw/eicu"
