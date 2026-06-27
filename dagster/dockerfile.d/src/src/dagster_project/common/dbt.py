"""dbt(Trino/Iceberg) 공유 설정 (데이터셋 무관 공통).

단일 dbt 프로젝트(dbt_pipelines)를 데이터셋 subproject가 공유한다.
데이터셋별 @dbt_assets는 각 subproject(eicu·mimic_iv)의 dbt_assets.py에서
select로 모델을 분할 소유하고, 여기의 공유 DbtProject·리소스를 참조한다.

manifest: dev에서는 prepare_if_dev()가 `dbt deps`+`dbt parse`로 생성한다.
비-dev(`dg check defs`·프로덕션)에서는 빌드 단계에서 manifest를 미리 생성해야 한다.
"""

from pathlib import Path

from dagster_dbt import DbtCliResource, DbtProject

# dbt 프로젝트 위치: 패키지 기준 .../dockerfile.d/src/dbt_pipelines
# (dbt.py → common → dagster_project → src(inner) → src(root, pyproject·dbt_pipelines))
DBT_PROJECT_DIR = Path(__file__).parents[3] / "dbt_pipelines"

dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR)
dbt_project.prepare_if_dev()


def build_dbt_resource() -> DbtCliResource:
    """공유 dbt 실행 리소스(DbtCliResource)."""
    return DbtCliResource(project_dir=dbt_project)
