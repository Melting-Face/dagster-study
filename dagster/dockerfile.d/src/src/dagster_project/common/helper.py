"""S3 csv.gz → Iceberg 적재 헬퍼 (데이터셋 무관 공통).

두 가지 경로를 제공한다.
- read_csv_gz_table: 일반(부하 없는) 파일을 통째로 읽어 pa.Table 반환
  → IO 매니저가 write.
- load_heavy_csv_gz_to_iceberg: 대용량 csv.gz(예: 3.3GB)를 boto3 스트리밍 +
  청크 append로 메모리를 일정하게 유지하며 적재(IO 매니저 미사용).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pyarrow as pa
import pyarrow.csv as pacsv
from dagster_aws.s3 import S3Resource
from dagster_iceberg.resource import IcebergTableResource

import dagster as dg
from dagster_project.common.constants import DEFAULT_CHUNK_ROWS

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog
    from pyiceberg.table import Table


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """s3://bucket/key → (bucket, key)."""
    if not uri.startswith("s3://"):
        message = f"s3:// URI가 아님: {uri}"
        raise ValueError(message)
    bucket, _, key = uri[len("s3://") :].partition("/")
    return bucket, key


def open_csv_gz_stream(
    s3: S3Resource,
    source_uri: str,
    column_types: dict[str, pa.DataType] | None = None,
) -> pacsv.CSVStreamingReader:
    """boto3로 s3 객체를 받아 gzip 해제 스트림을 pyarrow CSV 리더로 연다.

    Args:
        s3: dagster-aws S3Resource.
        source_uri: 원본 csv.gz의 s3 URI.
        column_types: 특정 컬럼의 추론 타입을 강제할 매핑(예: 자유형 value 컬럼을
            string으로 고정). 미지정 컬럼은 pyarrow가 자동 추론한다.
    """
    bucket, key = parse_s3_uri(source_uri)
    body = s3.get_client().get_object(Bucket=bucket, Key=key)["Body"]
    # StreamingBody(file-like)를 pyarrow로 감싸 gzip 스트리밍 해제
    stream = pa.CompressedInputStream(pa.PythonFile(body, mode="r"), "gzip")
    convert_options = (
        pacsv.ConvertOptions(column_types=column_types) if column_types else None
    )
    return pacsv.open_csv(stream, convert_options=convert_options)


def read_csv_gz_table(
    s3: S3Resource,
    source_uri: str,
    column_types: dict[str, pa.DataType] | None = None,
) -> pa.Table:
    """일반 파일을 통째로 읽어 Arrow 테이블로 반환한다(IO 매니저가 적재).

    대용량 파일에는 사용하지 말 것(전량 메모리 적재). 그 경우
    load_heavy_csv_gz_to_iceberg를 쓴다.

    Args:
        s3: dagster-aws S3Resource.
        source_uri: 원본 csv.gz의 s3 URI.
        column_types: 컬럼 타입 강제 매핑(선택). 자유형 문자열 컬럼이 숫자로
            잘못 추론되는 것을 막을 때 쓴다.
    """
    reader = open_csv_gz_stream(s3, source_uri, column_types=column_types)
    return reader.read_all()


def table_exists(catalog: Catalog, identifier: str) -> bool:
    """식별자에 해당하는 테이블이 카탈로그에 존재하는지 확인한다."""
    from pyiceberg.exceptions import NoSuchTableError

    try:
        catalog.load_table(identifier)
        return True
    except NoSuchTableError:
        return False


def ensure_table(catalog: Catalog, identifier: str, schema: pa.Schema) -> Table:
    """테이블을 로드하고, 없으면 네임스페이스·테이블을 생성해 반환한다."""
    from pyiceberg.exceptions import NamespaceAlreadyExistsError, NoSuchTableError

    namespace = identifier.rsplit(".", 1)[0]
    with contextlib.suppress(NamespaceAlreadyExistsError):
        catalog.create_namespace(namespace)
    try:
        return catalog.load_table(identifier)
    except NoSuchTableError:
        return catalog.create_table(identifier, schema=schema)


def load_heavy_csv_gz_to_iceberg(
    context: dg.AssetExecutionContext,
    *,
    s3: S3Resource,
    iceberg_table: IcebergTableResource,
    source_uri: str,
    mode: str = "replace",
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    column_types: dict[str, pa.DataType] | None = None,
) -> dg.MaterializeResult:
    """대용량 csv.gz를 청크 단위로 Iceberg 테이블에 적재한다.

    IcebergTableResource.load()는 기존 테이블만 로드하므로, 생성/append를 위해
    리소스의 config(properties)로 pyiceberg 카탈로그를 재구성한다.

    Args:
        context: 에셋 실행 컨텍스트.
        s3: dagster-aws S3Resource.
        iceberg_table: 대상 테이블 바인딩 리소스(name·config·table·namespace).
        source_uri: 원본 csv.gz의 s3 URI.
        mode: "replace"(재적재) 또는 "append"(누적).
        chunk_rows: 한 번에 append 할 행 수.
        column_types: 컬럼 타입 강제 매핑(선택). 자유형 value 컬럼(chartevents·
            labevents)이 청크마다 다른 타입으로 추론돼 스키마가 어긋나는 것을 막는다.

    Returns:
        적재 메타데이터(테이블·원본·행 수)를 담은 MaterializeResult.
    """
    from pyiceberg.catalog import load_catalog

    properties = iceberg_table.config.model_dump()["properties"]
    catalog = load_catalog(iceberg_table.name, **properties)
    identifier = f"{iceberg_table.schema_}.{iceberg_table.table}"

    if mode == "replace" and table_exists(catalog, identifier):
        catalog.drop_table(identifier)

    reader = open_csv_gz_stream(s3, source_uri, column_types=column_types)
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
            table = ensure_table(catalog, identifier, arrow.schema)
        table.append(arrow)
        pending = []
        pending_rows = 0

    for batch in reader:
        pending.append(batch)
        pending_rows += batch.num_rows
        total_rows += batch.num_rows
        if pending_rows >= chunk_rows:
            flush()
    flush()

    context.log.info(
        f"{identifier} ← {source_uri} 적재 완료 ({total_rows} rows, mode={mode})"
    )
    return dg.MaterializeResult(
        metadata={
            "table": identifier,
            "source_uri": source_uri,
            "rows": total_rows,
            "mode": mode,
        }
    )
