"""MIMIC-IV 데이터셋 전용 상수."""

# Iceberg 네임스페이스 / Dagster 그룹
# (메달리온 레이어는 네임스페이스가 아닌 kind로 표기)
NAMESPACE = "mimiciv"
GROUP_NAME = "mimiciv"

# 원천 csv.gz 루트 (모듈별 하위 경로: hosp/, icu/)
SOURCE_BASE = "s3://warehouse/raw/mimiciv"
