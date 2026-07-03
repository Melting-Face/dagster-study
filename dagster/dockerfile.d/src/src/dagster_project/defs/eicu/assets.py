"""eICU-CRD bronze 적재 에셋 (S3 csv.gz → Iceberg).

각 테이블은 **개별 명시적 @dg.asset**으로 정의한다(프로젝트 컨벤션).
- 일반(부하 없는) 파일: pa.Table 반환 → dagster-iceberg IO 매니저가 자동 적재.
- 대용량 파일(nurseCharting): boto3 스트리밍 + 청크 append(IO 매니저 미사용).

주의: Dagster context 클래스 identity 검사 때문에 자산 모듈에서는
`from __future__ import annotations`를 사용하지 않는다.
"""

import pyarrow as pa
from dagster_aws.s3 import S3Resource
from dagster_iceberg.resource import IcebergTableResource

import dagster as dg
from dagster import AssetExecutionContext
from dagster_project.common.helper import (
    load_heavy_csv_gz_to_iceberg,
    read_csv_gz_table,
)
from dagster_project.defs.eicu.constants import GROUP_NAME, SOURCE_BASE

# 일반 경로 에셋은 이 데이터셋 전용 IO 매니저(namespace=eicu)로 적재한다.
IO_MANAGER_KEY = "io_manager_eicu"

# eICU patient의 *time24 컬럼은 "HH:MM:SS" 문자열이라 숫자로 추론되면 안 된다.
# string으로 고정해 원문을 보존한다(offset 계산은 하위 dbt 모델에서 수행).
PATIENT_TIME_AS_STRING = {
    "hospitaladmittime24": pa.string(),
    "hospitaldischargetime24": pa.string(),
    "unitadmittime24": pa.string(),
    "unitdischargetime24": pa.string(),
}


@dg.asset(
    group_name=GROUP_NAME,
    io_manager_key=IO_MANAGER_KEY,
    kinds={"python", "iceberg", "bronze"},
)
def patient(s3: S3Resource) -> pa.Table:
    """EICU patient 원본을 bronze Iceberg 테이블로 적재한다."""
    return read_csv_gz_table(
        s3, f"{SOURCE_BASE}/patient.csv.gz", column_types=PATIENT_TIME_AS_STRING
    )


@dg.asset(
    group_name=GROUP_NAME,
    io_manager_key=IO_MANAGER_KEY,
    kinds={"python", "iceberg", "bronze"},
)
def diagnosis(s3: S3Resource) -> pa.Table:
    """EICU diagnosis 원본을 bronze Iceberg 테이블로 적재한다."""
    return read_csv_gz_table(s3, f"{SOURCE_BASE}/diagnosis.csv.gz")


@dg.asset(group_name=GROUP_NAME, kinds={"python", "iceberg", "bronze"})
def nurse_charting(
    context: AssetExecutionContext,
    s3: S3Resource,
    eicu_nurse_charting_table: IcebergTableResource,
) -> dg.MaterializeResult:
    """대용량 nurseCharting을 청크 단위로 bronze Iceberg에 적재한다.

    IO 매니저를 사용하지 않고 boto3 스트리밍 + 청크 append로 처리한다.
    """
    return load_heavy_csv_gz_to_iceberg(
        context,
        s3=s3,
        iceberg_table=eicu_nurse_charting_table,
        source_uri=f"{SOURCE_BASE}/nurseCharting.csv.gz",
    )
