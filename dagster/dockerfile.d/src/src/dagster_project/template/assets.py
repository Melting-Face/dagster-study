"""bronze 적재 에셋 (S3 csv.gz → Iceberg).

에셋은 클래스 없이 팩토리 함수로 생성한다(프로젝트 컨벤션: 에셋 클래스화 지양).
TABLES에 (asset_name, identifier, source_glob)을 추가하면 테이블별 에셋이 생성된다.
"""

from __future__ import annotations

import dagster as dg

from dagster_project.template.constants import DEFAULT_CHUNK_ROWS, DEFAULT_GROUP_NAME
from dagster_project.template.helper import stream_csv_gz_to_iceberg
from dagster_project.template.utils import get_s3_filesystem, load_iceberg_catalog


def build_csv_to_iceberg_asset(
    *,
    asset_name: str,
    identifier: str,
    source_glob: str,
    mode: str = "replace",
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    group_name: str = DEFAULT_GROUP_NAME,
    kinds: set[str] | None = None,
):
    """S3 csv.gz → Iceberg 테이블 적재 에셋을 만드는 팩토리.

    asset_name: Dagster 에셋 키
    identifier: Iceberg 식별자 "<namespace>.<table>" (예: bronze_mimiciv.patients)
    source_glob: 소스 경로/글롭 (예: s3://warehouse/raw/mimiciv/hosp/patients.csv.gz)
    """
    asset_kinds = kinds if kinds is not None else {"python", "iceberg"}

    @dg.asset(name=asset_name, group_name=group_name, kinds=asset_kinds)
    def _asset(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
        catalog = load_iceberg_catalog()
        fs = get_s3_filesystem()
        paths = sorted(fs.glob(source_glob))
        if not paths:
            raise dg.Failure(description=f"소스 파일 없음: {source_glob}")
        context.log.info(f"{len(paths)}개 파일 → {identifier} 적재 (mode={mode})")
        rows = stream_csv_gz_to_iceberg(
            catalog, identifier, paths, fs, chunk_rows=chunk_rows, mode=mode
        )
        return dg.MaterializeResult(
            metadata={
                "table": identifier,
                "source_glob": source_glob,
                "files": len(paths),
                "rows": rows,
            }
        )

    return _asset


# (asset_name, "<namespace>.<table>", source_glob)
# 예) ("mimiciv_hosp_patients", "bronze_mimiciv.patients",
#      "s3://warehouse/raw/mimiciv/hosp/patients.csv.gz")
TABLES: list[tuple[str, str, str]] = [
    # 적재할 테이블을 여기에 추가하세요.
]

bronze_assets = [
    build_csv_to_iceberg_asset(asset_name=name, identifier=identifier, source_glob=source_glob)
    for name, identifier, source_glob in TABLES
]
