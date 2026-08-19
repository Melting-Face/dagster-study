# DAGSTER STUDY

MIMIC-IV·eICU 중환자 데이터를 **Dagster + dbt + Iceberg 레이크하우스**로 적재·변환하고,
그 위에서 **SOFA → Sepsis-3 같은 임상 질문에 답하는** 학습·포트폴리오 프로젝트다.

**파이프라인은 수단, 분석이 목적**이다. 두 축이 다음처럼 나뉜다.

| 축 | 하는 일 | 규칙 정본 |
| --- | --- | --- |
| **파이프라인** | S3 → Iceberg 적재, dbt 실버 피처(22모델), 오케스트레이션 | [`conventions/dagster.md`](docs/conventions/dagster.md) · [`conventions/dbt.md`](docs/conventions/dbt.md) |
| **분석** | gold 지표·코호트, 노트북 탐색, 리포트 | [`conventions/analysis.md`](docs/conventions/analysis.md) |

> **현재 이행 중**: 단일 호스트 Docker Compose → **호스트 Dagster + 로컬 Kubernetes(컴퓨트·스토리지)**.
> 로드맵·단계별 게이트는 [`docs/redesign.md`](docs/redesign.md).

## 문서 (docs)

아키텍처와 코딩 규칙은 [`docs/`](docs/README.md)에 정리되어 있다.
이 프로젝트에서 정한 **규칙·결정·작업 패턴은 최대한 문서로 남기며**, `CLAUDE.md`·`docs/`·`README.md`를 함께 갱신해 단일 출처(single source of truth)를 유지한다.

- [코딩 철학](docs/philosophy.md)
- [재설계 로드맵](docs/redesign.md) — 이행 단계와 성공 게이트
- [전체 아키텍처 / 데이터 흐름](docs/architectures/overview.md)
- [리소스 산정](docs/resource-sizing.md)
- [분석 컨벤션](docs/conventions/analysis.md) — gold 모델 / 노트북 / 리포트 3층과 결론의 재현 경로
- 코딩 규칙: [공통](docs/conventions/general.md) · [Python](docs/conventions/python.md) · [Dagster](docs/conventions/dagster.md) · [dbt](docs/conventions/dbt.md) · [Kubernetes](docs/conventions/k8s.md)

## 구성 요소

| 계층 | 현재 위치 | 비고 |
| --- | --- | --- |
| 오케스트레이션 | **호스트** — Dagster webserver·daemon | 메타 스토리지는 compose `postgres` |
| 배치 컴퓨트 | **K8s** — Apache Spark Operator → `SparkApplication` | 러너 이미지 `spark-runner:0.4.0`(Iceberg·S3A·Spark Connect) |
| SQL 엔드포인트 | **K8s** — Spark Connect 서버 | dbt-spark가 `spark.remote`로 접속(Phase 1) |
| 스트림 컴퓨트 | **K8s** — Flink Operator → `FlinkDeployment` | 러너 이미지 `flink-runner:0.2.0`(Iceberg) |
| 테이블 포맷 | Iceberg (JDBC 카탈로그 = `catalog-postgres`) | Spark·Flink가 **동일 카탈로그 공유**(카탈로그명 `iceberg`로 통일) |
| 오브젝트 스토어 | SeaweedFS (S3 호환, path-style) | Iceberg 웨어하우스 |
| UI 진입점 | **K8s** — ingress-nginx (`*.localtest.me:8080`) | HTTP UI만 Ingress, 데이터 접속은 `port-forward`(§2-1) |
| 변환 | dbt — `dbt-trino`(현행) → `dbt-spark`(이행 중) | 모델 22개(`models/mimic_iv/`), 방언은 내장·dispatch 매크로로 흡수(`macros/cross_engine.sql`) |
| 분석 | **호스트** — Jupyter Lab(:8889) → Spark Connect / dbt gold 모델 | 탐색=`notebooks/`, 지표=gold(**현재 0개**), 결론=`docs/analyses/`(미생성). 규칙 [`conventions/analysis.md`](docs/conventions/analysis.md) |

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

### 2-2. 컴퓨트 러너 이미지 빌드 (최초 1회 / Dockerfile 변경 시)

Spark·Flink 워크로드는 Iceberg·S3A 의존을 구운 **전용 이미지**로 돈다. 로컬 레지스트리에 직접 push하면
클러스터가 같은 이름으로 받는다(`kind load` 불필요). 태그·매니페스트 갱신 규칙은
[`docs/conventions/k8s.md`](docs/conventions/k8s.md) §10.

```shell
podman build -f k8s/spark/Dockerfile.spark-runner -t localhost:5001/spark-runner:0.4.0 k8s/spark
podman push --tls-verify=false localhost:5001/spark-runner:0.4.0

podman build -f k8s/flink/Dockerfile.flink-runner -t localhost:5001/flink-runner:0.2.0 k8s/flink
podman push --tls-verify=false localhost:5001/flink-runner:0.2.0
```

> 태그를 올렸으면 이를 참조하는 매니페스트(`k8s/spark/*.yaml`·`k8s/flink/*.yaml`)도 **함께** 올린다.
> 한쪽만 올리면 구 이미지가 계속 돈다.

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

### 4. 노트북 (호스트, 옵션)

ad-hoc 탐색은 **Jupyter Lab**으로 한다. Dagster와 **같은 venv**를 쓰므로 커널 하나로
Spark Connect·pyiceberg에 붙고 `dagster_project.common.*`를 그대로 import할 수 있다.

```shell
kubectl port-forward svc/spark-connect 15002:15002   # 별도 터미널

cd dagster/dockerfile.d/src
uv run --group notebook jupyter lab --port 8889 --notebook-dir ../../../notebooks
```

> **8889를 쓰는 이유**: 기본 포트 8888은 compose SeaweedFS filer UI가 게시한다.
> 스타터 노트북·주의사항은 [`notebooks/README.md`](notebooks/README.md),
> **작성 규칙(재현성·정의 배치·수치 인용)** 은 [`docs/conventions/analysis.md`](docs/conventions/analysis.md).
> SQL 엔진은 **Spark SQL**이다 — Trino는 재설계에서 제거 대상이라 기본 기동에서 빠졌다.

### 5. 모델 추가

dbt 모델은 `dbt_pipelines/models/<dataset>/`에 `.sql`을 추가하면 자동 반영된다.
각 데이터셋 subproject가 **`@dbt_assets(select="fqn:<dataset>")`** 로 자기 모델만 소유한다
(`path:` 셀렉터는 cwd 글롭이라 정의 로드 시 모델이 수집되지 않는다 — [`docs/conventions/dbt.md`](docs/conventions/dbt.md)).

## REF

규칙·설계가 근거로 삼는 외부 표준의 인덱스는 [`docs/references.md`](docs/references.md)에 있다.
아래는 이 저장소가 실제로 쓰는 스택의 1차 문서다.

### Dagster

- 배포 옵션(Kubernetes): https://docs.dagster.io/deployment/oss/deployment-options/kubernetes
- `dagster.yaml`(인스턴스 설정): https://docs.dagster.io/deployment/oss/dagster-yaml
- `workspace.yaml`(코드 로케이션): https://docs.dagster.io/guides/build/projects/workspaces/workspace-yaml
- Dagster Pipes / `PipesK8sClient`: https://docs.dagster.io/api/python-api/libraries/dagster-k8s

### dbt

- dbt-trino(현행): https://github.com/starburstdata/dbt-trino
- dbt-spark(이행 대상): https://docs.getdbt.com/docs/core/connect-data-platform/spark-setup
- 크로스 데이터베이스 매크로: https://docs.getdbt.com/reference/dbt-jinja-functions/cross-database-macros

### 레이크하우스 / 컴퓨트

- Apache Iceberg: https://iceberg.apache.org/docs/latest/
- Apache Spark Kubernetes Operator: https://apache.github.io/spark-kubernetes-operator/
- Apache Flink Kubernetes Operator: https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-main/
- SeaweedFS(S3 API): https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API

### 로컬 K8s

- kind(Podman provider): https://kind.sigs.k8s.io/
- kind 로컬 레지스트리: https://kind.sigs.k8s.io/docs/user/local-registry/
- ingress-nginx: https://kubernetes.github.io/ingress-nginx/
