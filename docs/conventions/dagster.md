# Dagster 코딩 규칙

버전: `dagster==1.12.12` 계열 / `dagster-dg-cli` 기반 프로젝트 구조.

## 핵심 원칙: 에셋은 함수 + 데코레이터로 정의한다

> **클래스 기반 정의나 커스터마이징을 위한 불필요한 서브클래싱을 지양한다.**

- 에셋은 **함수 + 데코레이터**로 정의한다: `@asset`, `@multi_asset`, `@dbt_assets`.
- 커스터마이징이 필요하면 **선언적 설정**(데코레이터 인자, 메타데이터, dbt config)을 우선한다.
- 이유: 가독성 · 테스트 용이성 · 낮은 결합도. 함수형 정의가 Dagster 권장 패턴이며 보일러플레이트가 적다.

```python
# 권장: 함수 + 데코레이터
from dagster import asset


@asset(group_name="bronze")
def raw_events() -> None:
    # 원천 이벤트를 적재한다.
    ...
```

```python
# 지양: 커스터마이징을 위한 서브클래싱
class MyDbtTranslator(DagsterDbtTranslator):   # ← 가급적 사용하지 않는다
    def get_group_name(self, ...):
        ...
```

→ group 같은 설정은 서브클래스(`DagsterDbtTranslator`) 대신 **dbt config**로 선언한다:
`dbt_project.yml`의 `+meta.dagster.group`(또는 모델 `meta.dagster.group`). (아래 예시 참고)

## 자산 모듈에서는 `from __future__ import annotations` 금지

> Dagster는 `@asset`/op의 `context` 파라미터를 **클래스 identity**로 검사한다.
> future annotations를 켜면 어노테이션이 **문자열**이 되어 검사가 실패한다.

- 증상: `DagsterInvalidDefinitionError: Cannot annotate context parameter ... must be annotated with AssetExecutionContext ...`
- 규칙: **자산/op 정의가 있는 모듈**에서는 `from __future__ import annotations`를 쓰지 않는다.
  `context`는 임포트한 실제 클래스로 표기한다: `context: AssetExecutionContext` (또는 생략).
- 공통 helper 등 **자산이 아닌** 모듈은 future annotations를 써도 무방하다.
  (같은 맥락: `TC`(flake8-type-checking)도 Dagster introspection과 충돌해 보류 — `docs/conventions/python.md`)

## 각 에셋은 명시적으로 분리 정의한다

> **팩토리로 동적 생성하지 않고, 각 에셋을 `@asset` 함수로 명시적으로 정의한다.**

- 이유: 탐색성(에셋 이름 grep/IDE 점프) · per-asset 커스터마이징 용이 · 자기문서화.
- 공통 처리 로직은 일반 함수로 분리해 재사용하되(DRY), 에셋 정의 자체는 각각 명시한다.
- 에셋은 **데이터셋별 서브프로젝트** `dagster_project/<dataset>/assets.py`로 분리 관리한다.

```python
# 권장: 명시적 에셋 + 공통 로직 재사용
from dagster_project.common.helper import load_csv_gz_to_iceberg


@asset(group_name=GROUP_NAME, kinds={"python", "iceberg"})
def mimiciv_hosp_patients(context) -> MaterializeResult:
    return load_csv_gz_to_iceberg(
        context, identifier=f"{NAMESPACE}.patients",
        source_glob=f"{SOURCE_BASE}/hosp/patients.csv.gz",
    )
```

```python
# 지양: 팩토리 + 목록 루프로 에셋 동적 생성 (탐색성 저하)
bronze_assets = [build_csv_to_iceberg_asset(...) for ... in TABLES]   # ← 사용하지 않는다
```

## 프로젝트 구조

```text
src/dagster_project/
├── definitions.py          # 최상위 진입점: 서브프로젝트 Definitions를 merge (모듈 스코프 Definitions 1개)
├── common/                 # 공통 재사용 라이브러리 (데이터셋 무관)
│   ├── constants.py        # 공통 상수/기본값
│   ├── resources.py        # S3/Iceberg 리소스 빌더 (dagster-aws · dagster-iceberg)
│   ├── helper.py           # read_csv_gz_table(일반) · load_heavy_csv_gz_to_iceberg(대용량)
│   └── dbt.py              # 공유 DbtProject · build_dbt_resource (단일 dbt 프로젝트)
├── mimic_iv/               # 데이터셋 서브프로젝트
│   ├── constants.py        # NAMESPACE · GROUP_NAME · SOURCE_BASE
│   ├── assets.py           # 명시적 @asset (bronze 적재)
│   ├── dbt_assets.py       # @dbt_assets(select="path:models/mimic_iv")
│   └── definitions.py      # 서브프로젝트 Definitions (자산 + 전용 리소스)
└── eicu/
    ├── constants.py
    ├── assets.py
    ├── dbt_assets.py       # @dbt_assets(select="path:models/eicu")
    └── definitions.py
```

- 자동발견(`load_from_defs_folder`)·컴포넌트(`defs/`)를 쓰지 않는다. 각 서브프로젝트
  `definitions.py`가 `Definitions`(자산 + 전용 리소스)를 노출하고, 최상위 `definitions.py`가
  `Definitions.merge`로 합친다. 공유 리소스(s3·dbt)·잡·스케줄만 최상위에 인라인한다.
- **공통 로직은 `common/`** 에 두고 서브프로젝트가 import해 재사용한다(DRY).
- 코드 로케이션 모듈은 **모듈 스코프에 `Definitions` 1개(`defs`)** 만 둔다. 하위 defs는 이름이
  아닌 **모듈**로 import해 `<module>.defs`로 인라인 참조한다(autodiscovery 제약).

```python
from dagster_project.eicu import definitions as eicu_definitions
from dagster_project.mimic_iv import definitions as mimic_definitions

defs = Definitions.merge(
    eicu_definitions.defs,
    mimic_definitions.defs,
    Definitions(
        resources={"s3": build_s3_resource(), "dbt": build_dbt_resource()},
        jobs=[dbt_all_job],
        schedules=[dbt_all_schedule],
    ),
)
```

## dbt 통합 (pythonic `@dbt_assets`)

단일 dbt 프로젝트(`dbt_pipelines`)를 데이터셋 서브프로젝트가 **`@dbt_assets`로 분할 소유**한다.
공유 `DbtProject`·리소스는 `common/dbt.py`에 두고, 각 `<dataset>/dbt_assets.py`가 `select`로
자기 모델만 소유한다(컴포넌트/`defs.yaml` 미사용).

```python
# eicu/dbt_assets.py
from dagster_dbt import DbtCliResource, dbt_assets

from dagster_project.common.dbt import dbt_project


@dbt_assets(manifest=dbt_project.manifest_path, select="path:models/eicu")
def eicu_dbt_models(context, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
```

- **group은 서브클래싱 없이 dbt config로 선언**: `dbt_project.yml`의 `+meta.dagster.group`
  (기본 `DagsterDbtTranslator`가 읽는다).
- **schema는 접두어 없이** `generate_schema_name` 매크로로 그대로 사용(데이터셋 = Iceberg 네임스페이스).
- **manifest**: dev는 `DbtProject.prepare_if_dev()`가 생성, 비-dev(`dg check`·프로덕션)는 이미지 빌드 시
  `dbt parse`로 사전생성. 상세 [`dbt.md`](dbt.md) · [`../architecture.md`](../architecture.md).

## 잡 / 스케줄

- 잡은 `define_asset_job` + `AssetSelection`으로 선언적으로 구성한다.
- 그룹 단위 선택을 활용한다.

```python
dbt_all_job = define_asset_job(
    "dbt_all_job",
    selection=AssetSelection.groups("dbt_ingest"),
)

dbt_all_schedule = ScheduleDefinition(
    name="dbt_all_schedule",
    job=dbt_all_job,
    cron_schedule="0 * * * *",   # 매시 정각
)
```

## 그룹 / 네이밍

- 에셋 그룹명은 `snake_case`. 적재 자산은 **데이터셋 단위로 그룹화**한다(예: `eicu`, `mimiciv`).
- **메달리온 레이어는 그룹·네임스페이스 접두어가 아니라 `kinds`로 표기**한다
  (예: `kinds={"python", "iceberg", "bronze"}`). dbt 쪽에서는 동일 레이어를 tag로 관리한다.
  → 네임스페이스/스키마에는 `bronze_` 같은 레이어 접두어를 넣지 않는다(`NAMESPACE = "eicu"`).
- 잡·스케줄 이름은 역할이 드러나게 (`dbt_all_job`, `dbt_all_schedule`).

## 실행

```bash
dg dev        # 로컬 ad-hoc 개발 (webserver+daemon+code 일체형, http://localhost:3000)
```

> 컨테이너 스택(`compose.yml`)은 `dg dev` 대신 **`dagster-webserver` + `dagster-daemon`** 으로
> 분리해 기동한다(운영 토폴로지). 상세 [`../architecture.md`](../architecture.md#dagster-프로세스-분리-webserver--daemon).

## 참고

- Dagster 에셋: https://docs.dagster.io/guides/build/assets
- 컴포넌트(`dg`): https://docs.dagster.io/guides/build/components
- dagster-dbt: https://docs.dagster.io/integrations/libraries/dbt
- `dagster.yaml`: https://docs.dagster.io/deployment/oss/dagster-yaml
