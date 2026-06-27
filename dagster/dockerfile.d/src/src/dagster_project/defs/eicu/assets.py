"""eICU-CRD bronze 적재 에셋 (S3 csv.gz → Iceberg).

각 테이블은 **개별 명시적 @dg.asset**으로 정의한다(프로젝트 컨벤션).
일반(부하 없는) 파일은 pa.Table 반환 → dagster-iceberg IO 매니저가 자동 적재한다.
대용량 파일이 생기면 mimic_iv의 chartevents처럼 load_heavy_csv_gz_to_iceberg로 처리한다.

주의: Dagster context 클래스 identity 검사 때문에 자산 모듈에서는
`from __future__ import annotations`를 사용하지 않는다.
"""

import dagster as dg
import pyarrow as pa
from dagster_aws.s3 import S3Resource

from dagster_project.common.helper import read_csv_gz_table
from dagster_project.defs.eicu.constants import GROUP_NAME, SOURCE_BASE

# 일반 경로 에셋은 이 데이터셋 전용 IO 매니저(namespace=eicu)로 적재한다.
IO_MANAGER_KEY = "io_manager_eicu"


@dg.asset(
    group_name=GROUP_NAME,
    io_manager_key=IO_MANAGER_KEY,
    kinds={"python", "iceberg", "bronze"},
)
def patient(s3: S3Resource) -> pa.Table:
    """EICU patient 원본을 bronze Iceberg 테이블로 적재한다."""
    return read_csv_gz_table(s3, f"{SOURCE_BASE}/patient.csv.gz")


@dg.asset(
    group_name=GROUP_NAME,
    io_manager_key=IO_MANAGER_KEY,
    kinds={"python", "iceberg", "bronze"},
)
def lab(s3: S3Resource) -> pa.Table:
    """EICU lab 원본을 bronze Iceberg 테이블로 적재한다."""
    return read_csv_gz_table(s3, f"{SOURCE_BASE}/lab.csv.gz")
