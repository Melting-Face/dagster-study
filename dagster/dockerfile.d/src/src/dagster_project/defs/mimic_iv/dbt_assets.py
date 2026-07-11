"""MIMIC-IV dbt 모델 자산.

단일 dbt 프로젝트(dbt_pipelines)에서 `models/mimic_iv`의 모델만 select로 소유한다.
공유 DbtProject·리소스는 common.dbt에서 참조한다(dbt subproject = 코드 소유권 분리).

주의: Dagster context 클래스 identity 검사 때문에 자산 모듈에서는
`from __future__ import annotations`를 사용하지 않는다.
"""

from collections.abc import Iterator
from typing import Any

from dagster_dbt import DbtCliResource, dbt_assets

import dagster as dg
from dagster_project.common.dbt import dbt_project


# 셀렉터는 fqn 기반을 쓴다(manifest만으로 해석).
# path: 셀렉터는 정의 빌드 시 cwd 기준 파일시스템 글롭이라
# "does not match any enabled nodes"로 매칭에 실패한다.
# fqn:<dataset>은 models/<dataset>/ 하위 모델 전체를 데이터셋 단위로 소유한다.
@dbt_assets(
    manifest=dbt_project.manifest_path,
    project=dbt_project,
    select="fqn:mimic_iv",
)
def mimic_iv_dbt_models(
    context: dg.AssetExecutionContext, dbt: DbtCliResource
) -> Iterator[Any]:
    """models/mimic_iv의 dbt 모델을 빌드해 Iceberg(Trino)에 적재한다."""
    yield from dbt.cli(["build"], context=context).stream()
