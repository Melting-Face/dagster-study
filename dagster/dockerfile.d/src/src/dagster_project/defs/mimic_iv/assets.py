"""MIMIC-IV bronze 적재 에셋 (S3 csv.gz → Iceberg).

각 테이블은 **개별 명시적 @dg.asset**으로 정의한다(프로젝트 컨벤션).
- 일반(부하 없는) 파일: pa.Table 반환 → dagster-iceberg IO 매니저가 자동 적재.
- 대용량 파일(예: icu.chartevents): boto3 스트리밍 + 청크 append(IO 매니저 미사용).

주의: Dagster가 context를 클래스 identity로 검사하므로, 자산 모듈에서는
`from __future__ import annotations`(어노테이션 문자열화)를 사용하지 않는다.
"""

import dagster as dg
import pyarrow as pa
from dagster import AssetExecutionContext
from dagster_aws.s3 import S3Resource
from dagster_iceberg.resource import IcebergTableResource

from dagster_project.common.helper import (
    load_heavy_csv_gz_to_iceberg,
    read_csv_gz_table,
)
from dagster_project.defs.mimic_iv.constants import GROUP_NAME, SOURCE_BASE

# 일반 경로 에셋은 이 데이터셋 전용 IO 매니저(namespace=mimiciv)로 적재한다.
IO_MANAGER_KEY = "io_manager_mimiciv"


@dg.asset(
    group_name=GROUP_NAME,
    io_manager_key=IO_MANAGER_KEY,
    kinds={"python", "iceberg", "bronze"},
)
def patients(s3: S3Resource) -> pa.Table:
    """MIMIC-IV hosp.patients 원본을 bronze Iceberg 테이블로 적재한다."""
    return read_csv_gz_table(s3, f"{SOURCE_BASE}/hosp/patients.csv.gz")


@dg.asset(
    group_name=GROUP_NAME,
    io_manager_key=IO_MANAGER_KEY,
    kinds={"python", "iceberg", "bronze"},
)
def admissions(s3: S3Resource) -> pa.Table:
    """MIMIC-IV hosp.admissions 원본을 bronze Iceberg 테이블로 적재한다."""
    return read_csv_gz_table(s3, f"{SOURCE_BASE}/hosp/admissions.csv.gz")


@dg.asset(group_name=GROUP_NAME, kinds={"python", "iceberg", "bronze"})
def chartevents(
    context: AssetExecutionContext,
    s3: S3Resource,
    mimiciv_chartevents_table: IcebergTableResource,
) -> dg.MaterializeResult:
    """대용량 icu.chartevents를 청크 단위로 bronze Iceberg에 적재한다.

    IO 매니저를 사용하지 않고 boto3 스트리밍 + 청크 append로 처리한다.
    """
    return load_heavy_csv_gz_to_iceberg(
        context,
        s3=s3,
        iceberg_table=mimiciv_chartevents_table,
        source_uri=f"{SOURCE_BASE}/icu/chartevents.csv.gz",
    )
