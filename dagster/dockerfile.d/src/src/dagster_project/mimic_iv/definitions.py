"""MIMIC-IV subproject Definitions (flat 레이아웃).

eICU와 동일 패턴. 대용량 chartevents용 테이블 바인딩 리소스는 이 데이터셋 전용이므로
여기서 IO 매니저와 함께 정의한다. 공유 리소스(s3)는 최상위에서 바인딩한다.
"""

import dagster as dg
from dagster_project.common.resources import build_io_manager, build_table_resource
from dagster_project.mimic_iv import assets
from dagster_project.mimic_iv.constants import NAMESPACE
from dagster_project.mimic_iv.dbt_assets import mimic_iv_dbt_models

defs = dg.Definitions(
    # bronze 적재(@asset) + MIMIC-IV dbt 모델(@dbt_assets)을 함께 소유.
    assets=[*dg.load_assets_from_modules([assets]), mimic_iv_dbt_models],
    resources={
        "io_manager_mimiciv": build_io_manager(NAMESPACE),
        # 대용량 경로(chartevents) 청크 append용 테이블 바인딩
        "mimiciv_chartevents_table": build_table_resource(NAMESPACE, "chartevents"),
    },
)
