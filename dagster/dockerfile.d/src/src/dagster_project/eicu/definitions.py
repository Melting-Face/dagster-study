"""eICU subproject Definitions (flat 레이아웃).

dg 자동발견(load_from_defs_folder) 대신 subproject가 자체 Definitions를 노출하고,
최상위 definitions.py가 Definitions.merge로 합친다.
공유 리소스(s3)는 최상위에서 바인딩하므로 여기서는 eICU 전용 IO 매니저만 둔다.
"""

import dagster as dg
from dagster_project.common.resources import build_io_manager
from dagster_project.eicu import assets
from dagster_project.eicu.constants import NAMESPACE
from dagster_project.eicu.dbt_assets import eicu_dbt_models

defs = dg.Definitions(
    # bronze 적재(@asset) + eICU dbt 모델(@dbt_assets)을 함께 소유.
    assets=[*dg.load_assets_from_modules([assets]), eicu_dbt_models],
    resources={"io_manager_eicu": build_io_manager(NAMESPACE)},
)
