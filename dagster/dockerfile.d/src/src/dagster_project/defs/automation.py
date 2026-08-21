"""잡·스케줄 정의 — `defs/` 자동발견 대상.

모듈 스코프의 잡/스케줄 객체는 `load_defs`가 자동 수집한다(@dg.definitions 불필요).
dbt 인제스트 그룹 전체를 매시각 빌드하는 잡·스케줄을 선언한다.
"""

import dagster as dg

dbt_all_job = dg.define_asset_job(
    "dbt_all_job",
    selection=dg.AssetSelection.groups("dbt_ingest"),
)

dbt_all_schedule = dg.ScheduleDefinition(
    name="dbt_all_schedule",
    job=dbt_all_job,
    cron_schedule="0 * * * *",
    # cron을 KST로 해석(미지정 시 daemon 시스템 TZ 의존). docs/conventions/timezone.md
    execution_timezone="Asia/Seoul",
    # 기본 STOPPED를 명시한다 — 미지정일 때의 기본값과 값은 같지만, dbt 타깃이
    # spark_connect로 바뀌면서 실패 모드가 달라졌기 때문이다.
    # 전: 접속 자체가 실패 / 후: 접속은 성공하고 TABLE_OR_VIEW_NOT_FOUND
    # (카탈로그에 mimiciv 네임스페이스가 아직 없다). 매시각 실패가 쌓이면
    # 빨간불이 배경 소음이 되어 진짜 회귀를 가린다.
    #
    # 켜기 전 전제조건:
    #   1. Spark Connect 접속 경로 확보(kubectl port-forward svc/spark-connect 15002)
    #   2. bronze 적재로 Iceberg 카탈로그에 mimiciv 네임스페이스·소스 테이블 존재
    #   3. `dbt build --target spark_connect` 수동 1회 성공
    # 정의 자체는 배선 가치가 있으므로 삭제하지 않는다.
    default_status=dg.DefaultScheduleStatus.STOPPED,
)
