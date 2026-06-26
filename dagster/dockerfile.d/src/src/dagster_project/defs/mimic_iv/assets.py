"""MIMIC-IV bronze 적재 에셋 (S3 csv.gz → Iceberg).

각 에셋은 팩토리 없이 **명시적으로 분리 정의**한다(프로젝트 컨벤션).
공통 적재 로직은 dagster_project.common.helper 에서 재사용한다(DRY).
새 테이블 = load_csv_gz_to_iceberg()를 호출하는 @dg.asset 함수를 하나 더 명시적으로 작성한다.
"""

from __future__ import annotations

import dagster as dg

from dagster_project.common.helper import load_csv_gz_to_iceberg
from dagster_project.defs.mimic_iv.constants import GROUP_NAME, NAMESPACE, SOURCE_BASE


@dg.asset(group_name=GROUP_NAME, kinds={"python", "iceberg"})
def mimiciv_hosp_patients(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """S3 csv.gz → bronze_mimiciv.patients 적재."""
    return load_csv_gz_to_iceberg(
        context,
        identifier=f"{NAMESPACE}.patients",
        source_glob=f"{SOURCE_BASE}/hosp/patients.csv.gz",
    )


@dg.asset(group_name=GROUP_NAME, kinds={"python", "iceberg"})
def mimiciv_hosp_admissions(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """S3 csv.gz → bronze_mimiciv.admissions 적재."""
    return load_csv_gz_to_iceberg(
        context,
        identifier=f"{NAMESPACE}.admissions",
        source_glob=f"{SOURCE_BASE}/hosp/admissions.csv.gz",
    )
