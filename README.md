# DAGSTER STUDY

## 실행방법

1. 디렉토리 하위에 `./.env` 생성 후 아래의 정보 기입

```plaintext
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=

DAGSTER_POSTGRES_USER=
DAGSTER_POSTGRES_PASSWORD=
DAGSTER_POSTGRES_DB=

GENERIC_TIMEZONE=
TZ=
N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=
N8N_RUNNERS_ENABLED=

DISCORD_BOT_TOKEN=

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
ENDPOINT_URL=
REGION_NAME=

KMI_API_KEY=
```

2. dagster pipeline 생성

```shell
# dlt
dg scaffold defs dagster_dlt.DltLoadCollectionComponent dlt_ingest \
  --source rest_api \
  --destination filesystem

# dbt
dg scaffold defs dagster_dbt.DbtProjectComponent dbt_ingest \
--project-path ./dbt_pipelines
```

3. 도커(파드맨) 환경 실행

```shell
# docker 환경일 경우
docker compose up -d --build

# podman 환경일 경우
podman-compose up -d --build
```

```mermaid

```

## REF

### dagster

https://docs.dagster.io/deployment/oss/deployment-options/docker
https://docs.dagster.io/deployment/oss/dagster-yaml
https://docs.dagster.io/guides/build/projects/workspaces/workspace-yaml

### dbt

https://github.com/duckdb/dbt-duckdb

### dlthub

https://dlthub.com/docs

### discord

https://discord.com/developers/applications
https://discordpy.readthedocs.io/en/stable

### n8n

https://docs.n8n.io

### gemini

https://aistudio.google.com/app/api-keys

### dockerhub

https://hub.docker.com/r/minio/minio
https://hub.docker.com/_/postgres
