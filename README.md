# DAGSTER STUDY

## 문서 (docs)

아키텍처와 코딩 규칙은 [`docs/`](docs/README.md)에 정리되어 있다.
이 프로젝트에서 정한 **규칙·결정·작업 패턴은 최대한 문서로 남기며**, `CLAUDE.md`·`docs/`·`README.md`를 함께 갱신해 단일 출처(single source of truth)를 유지한다.

- [코딩 철학](docs/philosophy.md)
- [전체 아키텍처 / 데이터 흐름](docs/architectures/overview.md)
- [리소스 산정](docs/resource-sizing.md)
- 코딩 규칙: [공통](docs/conventions/general.md) · [Python](docs/conventions/python.md) · [Dagster](docs/conventions/dagster.md) · [dbt](docs/conventions/dbt.md)

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

# dbt: 코드로 정의됨(컴포넌트 스캐폴딩 불필요).
# 단일 dbt_pipelines를 데이터셋 subproject가 @dbt_assets(select="path:models/<ds>")로 분할 소유.
# 모델은 models/<dataset>/ 에 .sql 추가하면 자동 반영.
```

3. 도커(파드맨) 환경 실행

```shell
# docker 환경일 경우
docker compose up -d --build

# podman 환경일 경우
podman-compose up -d --build
```

> Dagster 런타임은 `dg dev` 일체형이 아니라 **`dagster-webserver`(UI) + `dagster-daemon`(스케줄·런큐)** 로 분리해 기동한다.
> 두 컨테이너는 같은 이미지·`dagster.yaml`을 쓰고 Postgres 공유 storage로 협조하며, [`workspace.yaml`](dagster/dockerfile.d/src/workspace.yaml)로 코드 로케이션을 로드한다.
> 상세 토폴로지는 [`docs/architectures/overview.md`](docs/architectures/overview.md#dagster-프로세스-분리-webserver--daemon) 참고.

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
