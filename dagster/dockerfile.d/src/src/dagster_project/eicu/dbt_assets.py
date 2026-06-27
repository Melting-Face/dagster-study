"""eICU dbt 모델 자산.

단일 dbt 프로젝트(dbt_pipelines)에서 `models/eicu`의 모델만 select로 소유한다.
공유 DbtProject·리소스는 common.dbt에서 참조한다(dbt subproject = 코드 소유권 분리).

주의: Dagster context 클래스 identity 검사 때문에 자산 모듈에서는
`from __future__ import annotations`를 사용하지 않는다.
"""

from collections.abc import Iterator
from typing import Any

from dagster_dbt import DbtCliResource, dbt_assets

import dagster as dg
from dagster_project.common.dbt import dbt_project


@dbt_assets(manifest=dbt_project.manifest_path, select="path:models/eicu")
def eicu_dbt_models(
    context: dg.AssetExecutionContext, dbt: DbtCliResource
) -> Iterator[Any]:
    """models/eicu의 dbt 모델을 빌드해 Iceberg(Trino)에 적재한다."""
    yield from dbt.cli(["build"], context=context).stream()
