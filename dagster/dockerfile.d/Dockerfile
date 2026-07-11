FROM python:3.13-slim

ENV DAGSTER_HOME=/opt/dagster/dagster_home/

WORKDIR $DAGSTER_HOME

COPY src/ $DAGSTER_HOME/

RUN pip install --no-cache-dir -e ".[dev]"

# dbt 패키지 설치 + manifest 사전 생성.
# webserver/daemon은 비-dev라 prepare_if_dev()가 no-op → @dbt_assets 로드에
# target/manifest.json이 필요하므로 빌드 단계에서 미리 생성한다(parse는 DB 미접속).
RUN cd dbt_pipelines && dbt deps && dbt parse --profiles-dir .

ENTRYPOINT ["dg"]
