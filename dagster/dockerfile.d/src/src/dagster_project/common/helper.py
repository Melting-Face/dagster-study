"""csv.gz → Iceberg 스트리밍 적재 헬퍼 (데이터셋 무관 공통).

무거운 파일은 pyarrow 블록 스트리밍 + 청크 단위 append로 메모리를 일정하게 유지한다.
서브프로젝트의 명시적 @asset 본문은 load_csv_gz_to_iceberg()를 호출해 중복을 제거한다(DRY).
"""

from __future__ import annotations

from collections.abc import Iterable

import dagster as dg

from dagster_project.common.constants import DEFAULT_CHUNK_ROWS
from dagster_project.common.utils import get_s3_filesystem, load_iceberg_catalog


def _table_exists(catalog, identifier: str) -> bool:
    # pyiceberg 버전별 table_exists 유무에 의존하지 않도록 load_table로 판별
    from pyiceberg.exceptions import NoSuchTableError

    try:
        catalog.load_table(identifier)
        return True
    except NoSuchTableError:
        return False


def _ensure_table(catalog, identifier: str, schema):
    from pyiceberg.exceptions import NamespaceAlreadyExistsError, NoSuchTableError

    namespace = identifier.rsplit(".", 1)[0]
    try:
        catalog.create_namespace(namespace)
    except NamespaceAlreadyExistsError:
        pass
    try:
        return catalog.load_table(identifier)
    except NoSuchTableError:
        return catalog.create_table(identifier, schema=schema)


def stream_csv_gz_to_iceberg(
    catalog,
    identifier: str,
    source_paths: Iterable[str],
    fs,
    *,
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    mode: str = "replace",
) -> int:
    """csv.gz 파일들을 스트리밍으로 읽어 Iceberg 테이블에 청크 단위로 적재한다.

    - chunk_rows 단위로 모아 한 번에 append → 작은 파일/스냅샷 폭증 방지
    - mode="replace": 기존 테이블 제거 후 재적재(멱등), "append": 누적
    반환값: 적재한 총 행 수
    """
    import pyarrow as pa
    import pyarrow.csv as pacsv

    if mode == "replace" and _table_exists(catalog, identifier):
        catalog.drop_table(identifier)

    table = None
    pending: list = []
    pending_rows = 0
    total_rows = 0

    def flush() -> None:
        nonlocal table, pending, pending_rows
        if not pending:
            return
        arrow = pa.Table.from_batches(pending)
        if table is None:
            table = _ensure_table(catalog, identifier, arrow.schema)
        table.append(arrow)
        pending = []
        pending_rows = 0

    for path in source_paths:
        with fs.open(path, "rb") as raw:
            # gzip 해제를 스트림으로 처리 → 전량 메모리 적재 회피
            stream = pa.CompressedInputStream(raw, "gzip")
            reader = pacsv.open_csv(stream)
            for batch in reader:
                pending.append(batch)
                pending_rows += batch.num_rows
                total_rows += batch.num_rows
                if pending_rows >= chunk_rows:
                    flush()
    flush()
    return total_rows


def load_csv_gz_to_iceberg(
    context: dg.AssetExecutionContext,
    *,
    identifier: str,
    source_glob: str,
    mode: str = "replace",
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
) -> dg.MaterializeResult:
    """S3 csv.gz → Iceberg 적재 공통 오케스트레이션 (에셋 본문이 호출).

    identifier: Iceberg 식별자 "<namespace>.<table>" (예: bronze_mimiciv.patients)
    source_glob: 소스 경로/글롭 (예: s3://warehouse/raw/mimiciv/hosp/patients.csv.gz)
    """
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
