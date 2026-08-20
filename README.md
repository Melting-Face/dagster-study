# PIPELINE STUDY

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
- [에이전트 오케스트레이션·기록관](docs/conventions/agents.md) — 서브에이전트 계층·권한·저널 규약 (아래 §AI 에이전트 구조)
- 코딩 규칙: [공통](docs/conventions/general.md) · [Python](docs/conventions/python.md) · [Dagster](docs/conventions/dagster.md) · [dbt](docs/conventions/dbt.md) · [Kubernetes](docs/conventions/k8s.md)

## 구성 요소

| 계층 | 현재 위치 | 비고 |
| --- | --- | --- |
| 오케스트레이션 | **호스트** — Dagster webserver·daemon | 메타 스토리지는 compose `postgres` |
| 배치 컴퓨트 | **K8s** — Apache Spark Operator → `SparkApplication` | 러너 이미지 `spark-runner:0.4.0`(Iceberg·S3A·Spark Connect) |
| SQL 엔드포인트 | **K8s** — Spark Connect 서버 | dbt-spark가 `spark.remote`로 접속(Phase 1) |
| 스트림 컴퓨트 | **K8s** — Flink Operator → `FlinkDeployment` ⏸ **현재 미설치** | 러너 이미지 `flink-runner:0.2.0`(Iceberg). Phase 3에서 `INSTALL_FLINK=true`로 복구 |
| 테이블 포맷 | Iceberg (JDBC 카탈로그 = **CloudNativePG** `catalog-postgres`, 접속은 `-rw` 서비스) | Spark·Flink가 **동일 카탈로그 공유**(카탈로그명 `iceberg`로 통일) |
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
./scripts/k8s-operators.sh                # Spark Operator + CloudNativePG (Flink는 INSTALL_FLINK=true)
./scripts/k8s-poc-storage.sh              # SeaweedFS + Iceberg 카탈로그 Postgres(CNPG Cluster)
./scripts/k8s-down.sh                     # 정리
```

### 2-1. Web UI 접근 (port-forward 불필요)

`k8s-up.sh`가 ingress-nginx까지 설치하므로 브라우저에서 바로 열린다.
(`localtest.me`는 공개 DNS가 127.0.0.1로 응답 — `/etc/hosts` 수정 불필요)

| URL | 대상 |
| --- | --- |
| http://flink.localtest.me:8080 | Flink Web UI (JobManager) — ⏸ Flink 미설치라 현재 미응답 |
| http://spark.localtest.me:8080 | Spark Web UI (Connect 서버, 쿼리 이력 누적) |

데이터 접속(카탈로그 Postgres·SeaweedFS·Spark Connect gRPC)은 `port-forward`를 쓴다.

```shell
kubectl port-forward svc/catalog-postgres-rw 15432:5432   # Iceberg JDBC 카탈로그(CNPG 쓰기 서비스)
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

## AI 에이전트 구조 (Claude Code)

이 저장소는 작업 자체도 규약화한다 — **전문 서브에이전트에 역할·권한을 나눠 배정**하고,
"누가 무엇을 왜 했는가"를 기록관 저널에 남긴다. 규칙 정본은
[`docs/conventions/agents.md`](docs/conventions/agents.md), 요약은 `CLAUDE.md` 운영 섹션에 있다.

> 🔴 **아래 두 그림은 축약본이다.** 워커 목록·권한·게이트의 **정본은
> [`docs/conventions/agents.md`](docs/conventions/agents.md) §구조도**이고, 갈리면 그쪽이 사실이다.

### 구조 — 누가 누구를 배정하는가

```mermaid
flowchart TB
    U(["🚦 사용자 · 최종 게이트<br/>커밋 · 발행 · apply는 사람이 승인"])
    SUP["supervisor · 메인 루프<br/>미션 정의 · 배정 · 취합 · 보고"]
    DIR["director · 판정자 · 쓰기 X<br/>계획 · 권한 매니페스트 · 배정<br/>판정축: 계획 대비 실행 정합<br/>🔴 Agent 도구 실재 미확인"]

    subgraph impl["구현 축 · 쓰기 O · model=inherit"]
        DE["data-engineer<br/>Dagster 에셋 · dbt 모델"]
        OE["devops-engineer<br/>compose · k8s · Terraform"]
        AN["analyst<br/>notebooks/** · docs/analyses/**"]
    end

    subgraph judge["판정 축 · 읽기 전용 · model=sonnet"]
        DV["data-verifier<br/>값 실측 대조"]
        DQ["data-qa<br/>테스트·게이트 감사"]
        OV["devops-verifier<br/>런타임 실측 대조"]
        OQ["devops-qa<br/>선언·게이트 감사"]
    end

    RES["researcher · 외부 1차 출처<br/>저장소의 유일한 외부 네트워크 접점"]

    subgraph outside["director 관할 밖 · supervisor 직접 배정"]
        SEC["security · 반출 · 규제 컨펌 게이트<br/>계획 1회 · 작업내용 1회 · 델타 조건부"]
        ARC["archivist · 저널 기록 전담"]
        SKM["skill-matcher · 스킬 배선 감사"]
        TW["tech-writer · 쓰기 O<br/>docs/** · README.md · 발행 금지"]
    end
    JR[("미션 저널<br/>$OBSIDIAN_VAULT/agents/날짜/NN-미션.md")]

    U <-->|"요청 ⇅ 보고 · 비가역 승인"| SUP
    SUP <-.->|"자문 질의 ⇅ 계획 · 게이트 설계"| DIR
    SUP <-->|"배정 ⇅ 산출물"| impl
    SUP <-->|"배정 ⇅ 발견"| judge
    SUP <-->|"질의 ⇅ 근거 · 출처등급 A~D"| RES
    SUP <-->|"컨펌 요청 ⇅ 승인 · 반려"| SEC
    SUP <-->|"감사 요청 ⇅ 별점 판정"| SKM
    SUP <-->|"배정 ⇅ 문서 · 원고"| TW
    SUP -->|"체크포인트 이벤트"| ARC
    ARC -->|기록| JR
```

- 축(**구현 / 실측 대조 / 체계 감사**)은 도메인이 달라도 **동일**하다 — 판단 규칙을 하나로 유지하려는 것.
  분석·공개는 **새 축이 아니라 새 도메인**이라 구현 축 1명(`analyst`·`tech-writer`)만 두고 판정은 재사용한다.
- **판정자는 쓰지 않는다** — `disallowedTools: Write, Edit, NotebookEdit`으로 미부여(난이도)가 아니라 거부(강제).
  **`director`도 판정자다**(2026-08-20) — 도구로 직접 작업하지 않고 계획·배정·판정만 하며,
  판정 축은 **「계획 대비 실행 정합」**(값=`*-verifier` / 체계=`*-qa` / 노출=`security` / 배선=`skill-matcher` /
  기록=`archivist`와 중첩되지 않는다).
- **관할 밖 4종**(`security`·`archivist`·`skill-matcher`·`tech-writer`)은 supervisor가 직접 배정한다 —
  앞 3종은 **계층 자체를 감사·기록**하고, `tech-writer`는 **director의 행동 규칙이 담긴 정본**을 쓰기 때문이다.
- **`tech-writer`는 저장소의 문서 소유자**다 — `docs/**`와 최상위 `README.md`를 쓴다. 🔴 단 가드는 디렉터리
  단위라 `docs/analyses/**`(내용은 `analyst` 소관)와 `docs/conventions/**`(규칙 신설은 supervisor 소관)는
  **규율로만** 갈린다.
- **워커가 워커를 못 부르니 supervisor가 릴레이한다** — `skill-matcher`는 새 스킬 후보를 **직접 검색하지 않고**
  `researcher`에 보낼 **조사 요청서**를 반환한다(`skill-matcher`→supervisor→`researcher`→supervisor→채점·제안
  →`security`→🚦사람). 찾기는 `researcher`, 배선 판정은 `skill-matcher`, 출처 신뢰성은 `security`로 **셋이 갈린다** —
  🔴 **감사자가 배선까지 하면 자기가 배선한 것을 자기가 감사**하게 되어 이 워커의 존재 이유가 사라진다.
- ⚠️ **3계층(supervisor→director→subagent) 성립 여부는 `미확인`이다** — 2026-08-19엔 서브에이전트에 `Agent`
  도구가 없어 중첩 위임 불가로 봤으나, 그 에러 문구가 자기모순(같은 세션의 supervisor는 `Agent`를 썼다)이라
  **원인이 프론트매터 선언일 가능성**이 남는다. 새 세션에서 재측정할 때까지 배정은 supervisor가 대행한다.

### 파이프라인 — 미션 한 건이 흐르는 경로

```mermaid
flowchart LR
    A(["사용자 요청"]) --> B{"미션인가?<br/>파일변경 · 위임 · 결정 · 비가역"}
    B -->|아니오| Z(["단순 응답 · 기록 없음"])
    B -->|예| C["저널 개시<br/>NN 번호는 journal_guard가 발급"]
    C --> P["분해 · 계획<br/>권한 매니페스트"]
    P --> G1{"security 컨펌 ①<br/>계획 · 미션당 1회"}
    G1 -->|반려| P
    G1 -->|승인| D["배정<br/>도메인 × 축"]
    D --> E["구현 워커<br/>쓰기 · 경로 한정"]
    E -.->|"계획 밖 경로 · 비가역 · 외부발신"| GD{"Δ 델타 컨펌<br/>해당 항목만"}
    GD -.->|승인| E
    D --> F["판정 워커<br/>실측 대조 · 체계 감사"]
    D --> R["researcher<br/>외부 1차 출처"]
    R --> E
    E --> F
    F -->|"불일치 · 갭"| E
    F --> G{"security 컨펌 ②<br/>작업내용 · 미션당 1회"}
    G -->|반려| E
    G -->|승인| H{"비가역인가?<br/>커밋 · apply · 발행 · DROP"}
    H -->|예| I(["🚦 사람 승인 게이트"])
    H -->|아니오| J["적용"]
    I --> J
    J --> K["archivist 기록<br/>결과 · 상호작용 로그 · 실행 메타"]
    K --> L(["사용자 보고"])
```

- **`security` 컨펌은 배정마다가 아니라 2점 + 델타다**(2026-08-20 개정) — ①**계획 전체** 1회
  ②**미션 전체 작업내용** 1회 Δ계획 밖(쓰기 경로·비가역·외부 발신) 발생 시 그 항목만. 배정 시점엔
  산출물이 없어 **읽기 전용 `security`가 볼 재료가 없기** 때문이고, 비용 절감이 목적이 아니다(호출 `2N+`→`2+Δ`).
  🔴 둘 다 **"한 벌"이 단위**다 — 워커별로 쪼개면 **파일 사이의 조합에서 생기는 노출**을 못 본다.
  🔴 **비가역은 Δ/①에서 실행 *전에* 판정**하며 ②로 미루지 않는다. 개정 효력은 3셀 대조 전까지 **`미확인`**이다.

**기계 강제층(hook)** — 위 흐름의 규율 중 일부만 실제로 강제된다. 결정값은 `allow`·`deny`·`ask`·`defer` 넷뿐이다.

| 가드 | 배선 | 막는 것 |
| --- | --- | --- |
| [`journal_guard.py`](scripts/journal_guard.py) | `SessionStart` · `PreToolUse(Write)` · `Stop` | 저널 `NN` 넘버링 경합 · 규약 위반 생성 · 기록 누락 경고 |
| [`session_sync_guard.py`](scripts/session_sync_guard.py) | `PreToolUse(Bash·Agent·Edit\|Write\|NotebookEdit)` | 병렬 세션의 중복 작업 · 워킹트리 전역 git 명령 |
| [`protected_paths_guard.py`](scripts/protected_paths_guard.py) | `PreToolUse(Bash)` | 보호 경로(`.env`·lock 등) 우회 수정 |
| [`worker_path_guard.py`](scripts/worker_path_guard.py) | `tech-writer`·`researcher`·`director` 프론트매터 `hooks` | 워커별 쓰기 경로 이탈 (✅ `tech-writer` 3셀 대조로 실발동 확인 — 🔴 단 **2026-08-20 경계 확대·`director` 신규 배선분은 `미확인`**, 새 세션 재대조 필요) |
| [`analyst_path_guard.py`](scripts/analyst_path_guard.py) | `analyst` 프론트매터 `hooks` | 같은 목적 (✅ 실발동 확인 — 과거 미발동은 **`hooks`가 정의 로드 시점에 스냅샷**되기 때문) |

- 🔴 **`hooks`를 세션 도중 추가·수정하면 그 세션에는 반영되지 않는다** — 배선을 바꾸면 **새 세션에서** 3셀 대조를 다시 돌린다.
- 🔴 **`Bash` 경유 쓰기는 파일 가드를 우회**한다 — 그래서 "파일 수정을 `Bash`로 하라"는 지시는 거부한다.
- 🔴 **발행(업로드)은 어느 워커도 하지 않는다.** 외부 발신은 비가역이라 마지막 게이트는 **사람**이 갖는다
  (자동화하지 않는 것이 설계). 공개 기준은 [`docs/conventions/publishing.md`](docs/conventions/publishing.md).

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
