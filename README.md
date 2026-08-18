# DAGSTER STUDY

MIMIC-IV·eICU 중환자 데이터를 **Dagster + dbt + Iceberg 레이크하우스**로 적재·변환하고,
SOFA → Sepsis-3 실버 피처를 만드는 학습·포트폴리오 프로젝트다.

> **현재 이행 중**: 단일 호스트 Docker Compose → **호스트 Dagster + 로컬 Kubernetes(컴퓨트·스토리지)**.
> 로드맵·단계별 게이트는 [`docs/redesign.md`](docs/redesign.md).

## 문서 (docs)

아키텍처와 코딩 규칙은 [`docs/`](docs/README.md)에 정리되어 있다.
이 프로젝트에서 정한 **규칙·결정·작업 패턴은 최대한 문서로 남기며**, `CLAUDE.md`·`docs/`·`README.md`를 함께 갱신해 단일 출처(single source of truth)를 유지한다.

- [코딩 철학](docs/philosophy.md)
- [재설계 로드맵](docs/redesign.md) — 이행 단계와 성공 게이트
- [전체 아키텍처 / 데이터 흐름](docs/architectures/overview.md)
- [리소스 산정](docs/resource-sizing.md)
- 코딩 규칙: [공통](docs/conventions/general.md) · [Python](docs/conventions/python.md) · [Dagster](docs/conventions/dagster.md) · [dbt](docs/conventions/dbt.md) · [Kubernetes](docs/conventions/k8s.md)

## 구성 요소

| 계층 | 현재 위치 | 비고 |
| --- | --- | --- |
| 오케스트레이션 | **호스트** — Dagster webserver·daemon | 메타 스토리지는 compose `postgres` |
| 배치 컴퓨트 | **K8s** — Apache Spark Operator → `SparkApplication` | 러너 이미지 `spark-runner`(Iceberg·S3A·Spark Connect 포함) |
| SQL 엔드포인트 | **K8s** — Spark Connect 서버 | dbt-spark가 `spark.remote`로 접속(Phase 1) |
| 스트림 컴퓨트 | **K8s** — Flink Operator → `FlinkDeployment` | 러너 이미지 `flink-runner`(Iceberg 포함) |
| 테이블 포맷 | Iceberg (JDBC 카탈로그 = `catalog-postgres`) | Spark·Flink가 **동일 카탈로그 공유** |
| 오브젝트 스토어 | SeaweedFS (S3 호환, path-style) | Iceberg 웨어하우스 |
| 변환 | dbt — `dbt-trino`(현행) → `dbt-spark`(이행 중) | 모델 22개(`models/mimic_iv/`) |

## 실행방법

### 1. 환경변수

[`.env.example`](.env.example)을 `.env`로 복사해 값을 채운다(커밋 금지).
키가 컨테이너/호스트에서 갈리는 이유는 [`docs/operations.md`](docs/operations.md) §1-2 참고.

```shell
cp .env.example .env
```

### 2. 로컬 Kubernetes(컴퓨트·스토리지) 기동

**kind on Podman**(rootful 머신 필수) + 로컬 레지스트리 `localhost:5001`.
설정 단일 출처는 [`scripts/k8s-env.sh`](scripts/k8s-env.sh).

```shell
./scripts/k8s-up.sh                       # podman machine + kind 클러스터 + 레지스트리
INSTALL_FLINK=true ./scripts/k8s-operators.sh   # Spark Operator (+ cert-manager·Flink Operator)
./scripts/k8s-poc-storage.sh              # SeaweedFS + Iceberg 카탈로그 Postgres
./scripts/k8s-down.sh                     # 정리
```

### 2-1. Web UI 접근 (port-forward 불필요)

`k8s-up.sh`가 ingress-nginx까지 설치하므로 브라우저에서 바로 열린다.
(`localtest.me`는 공개 DNS가 127.0.0.1로 응답 — `/etc/hosts` 수정 불필요)

| URL | 대상 |
| --- | --- |
| http://flink.localtest.me:8080 | Flink Web UI (JobManager) |
| http://spark.localtest.me:8080 | Spark Web UI (Connect 서버, 쿼리 이력 누적) |

데이터 접속(카탈로그 Postgres·SeaweedFS·Spark Connect gRPC)은 `port-forward`를 쓴다.

```shell
kubectl port-forward svc/catalog-postgres 15432:5432   # Iceberg JDBC 카탈로그
kubectl port-forward svc/seaweedfs        18333:8333   # S3 API
kubectl port-forward svc/spark-connect    15002:15002  # dbt(spark_connect 타깃)
```

### 3. Dagster (호스트)

Dagster는 **클러스터 밖 호스트**에서 돌며 K8s를 원격 컴퓨트로 트리거한다
([`docs/conventions/k8s.md`](docs/conventions/k8s.md) §8).

```shell
docker compose up -d postgres             # 메타 스토리지만 기동 (127.0.0.1 바인딩)

cd dagster/dockerfile.d/src
export DAGSTER_HOME="$PWD"                # dagster.yaml이 있는 디렉터리
uv run dg dev                             # http://localhost:3000
```

> 컨테이너로 통째 띄우려면 `docker compose up -d --build`(webserver·daemon 분리 기동).
> 이 경우 Dagster가 클러스터를 트리거하는 경로는 별도 배선이 필요하다.

### 4. 모델 추가

dbt 모델은 `dbt_pipelines/models/<dataset>/`에 `.sql`을 추가하면 자동 반영된다.
각 데이터셋 subproject가 **`@dbt_assets(select="fqn:<dataset>")`** 로 자기 모델만 소유한다
(`path:` 셀렉터는 cwd 글롭이라 정의 로드 시 모델이 수집되지 않는다 — [`docs/conventions/dbt.md`](docs/conventions/dbt.md)).

## REF

### dagster

https://docs.dagster.io/deployment/oss/deployment-options/docker
https://docs.dagster.io/deployment/oss/dagster-yaml
https://docs.dagster.io/guides/build/projects/workspaces/workspace-yaml

### dbt

https://github.com/duckdb/dbt-duckdb

### dlthub

https://dlthub.com/docs

### gemini

https://aistudio.google.com/app/api-keys

### dockerhub

https://hub.docker.com/r/minio/minio
https://hub.docker.com/_/postgres
