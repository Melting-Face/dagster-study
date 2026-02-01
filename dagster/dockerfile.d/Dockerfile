FROM python:3.13-slim

ENV DAGSTER_HOME=/opt/dagster/dagster_home/

WORKDIR $DAGSTER_HOME

COPY src/ $DAGSTER_HOME/

RUN pip install --no-cache-dir -e ".[dev]"

ENTRYPOINT ["dg"]