# Dagster 코딩 규칙

버전: `dagster==1.12.12` 계열 / `dagster-dg-cli` 기반 프로젝트 구조.

## 핵심 원칙: 에셋은 함수 + 데코레이터로 정의한다

> **클래스 기반 정의나 커스터마이징을 위한 불필요한 서브클래싱을 지양한다.**

- 에셋은 **함수 + 데코레이터**로 정의한다: `@asset`, `@multi_asset`, `@dbt_assets`.
- 커스터마이징이 필요하면 **선언적 설정**(데코레이터 인자, 메타데이터, dbt config, 컴포넌트 `defs.yaml`)을 우선한다.
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

→ group 같은 설정은 서브클래스 대신 **dbt config**(`meta.dagster.group` 또는 `+group`)나
**컴포넌트 `defs.yaml`의 `translation`** 으로 선언한다. (아래 예시 참고)

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
- 에셋은 **데이터셋별 서브프로젝트** `defs/<dataset>/assets.py`로 분리 관리한다.

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
├── definitions.py          # 최상위 Definitions (잡·스케줄 병합)
├── common/                 # 공통 재사용 (defs 밖 라이브러리, 데이터셋 무관)
│   ├── constants.py        # 공통 상수/기본값
│   ├── resources.py        # S3/Iceberg 리소스 빌더 (dagster-aws · dagster-iceberg)
│   └── helper.py           # read_csv_gz_table(일반) · load_heavy_csv_gz_to_iceberg(대용량)
└── defs/                    # 컴포넌트/에셋 정의 폴더 (자동 로드)
    ├── dbt_ingest/
    │   └── defs.yaml        # dagster_dbt.DbtProjectComponent 선언
    ├── mimic_iv/            # 데이터셋 서브프로젝트
    │   ├── constants.py     # NAMESPACE · GROUP_NAME · SOURCE_BASE
    │   └── assets.py        # 명시적 @asset
    └── eicu/
        ├── constants.py
        └── assets.py
```

- `definitions.py`는 `load_from_defs_folder`로 `defs/` 하위를 자동 로드하고,
  잡·스케줄만 추가로 `Definitions.merge`한다.
- **공통 로직은 `common/`**(defs 밖)에 두고 서브프로젝트가 import해 재사용한다(DRY).

```python
defs = Definitions.merge(
    load_from_defs_folder(path_within_project=Path(__file__).parent),
    Definitions(jobs=[dbt_all_job], schedules=[dbt_all_schedule]),
)
```

## 컴포넌트 (선언적 정의)

dbt 통합처럼 정형화된 정의는 **컴포넌트 + `defs.yaml`** 로 선언한다 (코드 작성 최소화).

```yaml
# defs/dbt_ingest/defs.yaml
type: dagster_dbt.DbtProjectComponent

attributes:
  project: "{{ context.project_root }}/dbt_pipelines"
  translation:
    group_name: dbt_ingest # ← 그룹은 여기서 선언 (서브클래싱 X)
```

스캐폴딩은 `dg` CLI로 한다:

```bash
dg scaffold defs dagster_dbt.DbtProjectComponent dbt_ingest \
  --project-path ./dbt_pipelines
```

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

- 에셋 그룹명은 `snake_case`. 레이크하우스 레이어와 일치시키면 추적이 쉽다.
  (예: `dbt_ingest`, 또는 medallion 레이어 `bronze` / `silver` / `gold`)
- 잡·스케줄 이름은 역할이 드러나게 (`dbt_all_job`, `dbt_all_schedule`).

## 실행

```bash
dg dev        # 개발 UI (http://localhost:3000)
```

## 참고

- Dagster 에셋: https://docs.dagster.io/guides/build/assets
- 컴포넌트(`dg`): https://docs.dagster.io/guides/build/components
- dagster-dbt: https://docs.dagster.io/integrations/libraries/dbt
- `dagster.yaml`: https://docs.dagster.io/deployment/oss/dagster-yaml
