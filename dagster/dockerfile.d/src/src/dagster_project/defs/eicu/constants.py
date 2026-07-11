"""eICU-CRD 데이터셋 전용 상수."""

# Iceberg 네임스페이스 / Dagster 그룹
# (메달리온 레이어는 네임스페이스가 아닌 kind로 표기)
NAMESPACE = "eicu"
GROUP_NAME = "eicu"

# 원천 csv.gz 루트 (eICU는 플랫 구조)
SOURCE_BASE = "s3://warehouse/raw/eicu"
