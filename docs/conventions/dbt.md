# dbt 코딩 규칙

어댑터: **`dbt-trino`** (Trino → Iceberg/SeaweedFS 레이크하우스).
프로젝트: `dagster/dockerfile.d/src/dbt_pipelines/`.

## 포매팅 / 린팅

- SQL은 [`sqlfluff`](https://docs.sqlfluff.com/)로 lint·format한다.
- dialect는 **`trino`** 로 설정한다.
- 들여쓰기 스페이스 4칸.

```bash
sqlfluff lint models/
sqlfluff fix models/
```

### 설정은 repo 루트 `pyproject.toml`에서 관리한다

sqlfluff 명세는 별도 `.sqlfluff` 파일 대신 **repo 루트 `pyproject.toml`의 `[tool.sqlfluff.*]`** 섹션에 둔다.
(sqlfluff는 `tool.sqlfluff`로 시작하는 nested 섹션을 공식 지원하며, 대상 파일에서 상위로
올라가며 pyproject를 병합 탐색하므로 루트 설정이 적용된다.)

```toml
# pyproject.toml (repo 루트)
[tool.sqlfluff.core]
templater = "dbt"
dialect = "trino"
max_line_length = 88

[tool.sqlfluff.indentation]
tab_space_size = 4

[tool.sqlfluff.rules.capitalisation.keywords]
capitalisation_policy = "lower"
```

> 참고: `templater = "dbt"`를 쓰려면 `sqlfluff-templater-dbt` 패키지가 필요하다.

## 디렉토리 / 레이어링 (Medallion)

- **`models/` 하위 디렉토리는 서브프로젝트(데이터셋)명으로 묶는다** — Dagster 데이터셋 서브프로젝트(`<dataset>/`)와 1:1.
  메달리온 레이어명(`bronze`/`silver`/`gold`)을 **디렉토리명으로 쓰지 않는다.**
- **메달리온 레이어는 tag로 표기**한다(스키마 접두어·디렉토리명으로 인코딩하지 않는다).
  Dagster 쪽에서는 동일 레이어를 `kinds`로 표기한다([dagster.md](dagster.md)).

| 레이어                  | 의미                          | materialization 권장 |
| ----------------------- | ----------------------------- | -------------------- |
| `bronze` (staging)      | 원천 정제(타입·컬럼명 표준화) | `view`               |
| `silver` (intermediate) | 조인·비즈니스 로직            | `view` 또는 `table`  |
| `gold` (marts)          | 분석/소비용 집계              | `table`              |

현재 구조(코드 기준):

```text
models/
├── eicu/              # 서브프로젝트(데이터셋)명 = dagster_project/defs/eicu
│   └── source.yml     # Dagster 적재분(dbt 미생성) source 선언 (실버 모델 미이식)
└── mimic_iv/          # = dagster_project/defs/mimic_iv
    ├── source.yml     # 적재 11테이블 source 선언
    └── tables/        # 실버 모델 22개 — config(tags=['silver'])
        ├── sofa.sql               # SOFA 6장기 점수
        ├── sepsis3.sql            # Sepsis-3 onset
        ├── suspicion_of_infection.sql
        └── ...                    # vitalsign · gcs · icustay_hourly 등 (mimic-code 포팅)
```

> - 새 모델은 해당 **데이터셋 디렉토리** 안에 추가하고, 레이어는 `+tags`(또는 모델 내
>   `config(tags=...)`)로 표기한다. `tables/`처럼 materialization 그룹용 하위 디렉토리는 가능하나,
>   메달리온 레이어명(`bronze`/`silver`/`gold`)을 디렉토리명으로 쓰지 않는다.
> - `mimic_iv/tables/`는 `dbt_project.yml`에서 `+materialized: table`(dbt 기본 view 재정의)로
>   물리 테이블로 구체화한다. 모델·피처 상세는 [`dataset_schema.md`](../dataset_schema.md).

## 네이밍

- 모델 파일·이름은 `snake_case`, 영어.
- 모델명에는 **데이터셋·엔티티**를 드러낸다(예: `stg_eicu__patient`, `eicu__patient_summary`).
  레이어는 파일명이 아니라 **tag**로 구분한다.
- 컬럼명은 `snake_case`.

## 모델 설정 (선언적)

- materialization·group 등은 **`dbt_project.yml`의 `+config`** 또는 모델 상단
  **`{{ config(...) }}`** 로 선언한다.
- Dagster 그룹도 dbt 쪽 config로 선언한다 (Dagster 서브클래싱 대신).

```yaml
# dbt_project.yml — 디렉토리는 데이터셋명, 레이어는 +tags로 표기
models:
  dbt_pipelines:
    eicu: # ← 서브프로젝트(데이터셋) 디렉토리
      +schema: eicu # 출력 스키마 = Iceberg 네임스페이스 (generate_schema_name로 접두어 없음)
      +meta:
        dagster:
          group: eicu # Dagster 에셋 그룹을 dbt config로 선언
```

> **출력 스키마**: 데이터셋 디렉토리에 `+schema: <namespace>`를 주면 커스텀 매크로
> `generate_schema_name`이 target schema(dev/prod) **접두어 없이** 그대로 적용한다
> (메달리온은 스키마가 아닌 tag/kind로 표기 — `macros/generate_schema_name.sql`).
> **소유**: 각 데이터셋 모델은 Dagster `defs/<dataset>/dbt_assets.py`의
> `@dbt_assets(select="fqn:<dataset>")`가 머티리얼라이즈한다([dagster.md](dagster.md)).

### `@dbt_assets` 셀렉터는 `fqn:` 을 쓴다 (`path:` 금지)

데이터셋 소유 셀렉터는 **`select="fqn:<dataset>"`** 로 쓴다(`manifest`만으로 해석).

```python
# defs/mimic_iv/dbt_assets.py
@dbt_assets(
    manifest=dbt_project.manifest_path,
    project=dbt_project,
    select="fqn:mimic_iv",   # models/mimic_iv/ 하위 모델 전체를 데이터셋 단위로 소유
)
def mimic_iv_dbt_models(context, dbt): ...
```

- **`path:models/<dataset>` 를 쓰지 말 것.** `path:` 셀렉터는 정의 빌드 시점의
  **cwd 기준 파일시스템 글롭**이라, Dagster가 프로젝트 밖 경로에서 정의를 로드하면
  `The selection criterion 'path:...' does not match any enabled nodes` 경고와 함께
  **모델이 하나도 수집되지 않는다**(모델이 0개일 땐 드러나지 않는 잠복 버그).
- `fqn:<dataset>` 은 manifest의 fqn(`dbt_pipelines.<dataset>.…`)만으로 매칭하므로
  cwd·파일시스템에 의존하지 않아 안전하다. `project=dbt_project` 는 런타임 `dbt build`
  의 작업 디렉토리를 프로젝트로 고정하기 위해 함께 넘긴다.

```sql
-- models/eicu/eicu__patient_summary.sql
-- 레이어는 디렉토리가 아니라 tag로 표기한다(gold).
{{ config(materialized='table', tags=['gold']) }}

select
    patient_id,
    count(*) as lab_count
from {{ ref('stg_eicu__patient') }}
group by patient_id
```

## ref / source

- 모델 간 참조는 항상 **`{{ ref('...') }}`**, 원천 참조는 **`{{ source('...') }}`** 를 쓴다.
  하드코딩된 테이블명을 금지한다 (lineage 보존).

### Dagster가 적재한(=dbt 미생성) 테이블은 `source()`로 참조한다

S3 → Iceberg 적재 테이블(`<dataset>/`)은 **dbt가 만들지 않으므로** dbt source로 선언하고
`{{ source(...) }}`로 참조한다. source 정의는 **데이터셋별 서브디렉토리**에 둔다
(`models/<dataset>/source.yml`). 현재: `models/eicu/source.yml`, `models/mimic_iv/source.yml`.

```yaml
# models/eicu/source.yml
version: 2
sources:
  - name: eicu
    database: iceberg # Trino 카탈로그 (= profiles.yml database)
    schema: eicu # Iceberg 네임스페이스 = Trino 스키마 (eicu NAMESPACE)
    tables:
      - name: patient
        meta:
          dagster:
            asset_key: ["patient"] # ← Dagster 자산키와 1:1 매핑(lineage 연결)
```

```sql
-- models/eicu/stg_eicu__patient.sql   (레이어는 tag로: config(tags=['silver']))
select * from {{ source('eicu', 'patient') }}
```

- **`schema`는 Iceberg 네임스페이스(= `defs/<dataset>/constants.py`의 `NAMESPACE`)와 반드시 일치**해야
  한다. 둘은 단일 출처로 함께 바뀐다.
- **`meta.dagster.asset_key`** 로 dbt source를 기존 Dagster 자산키에 매핑한다. 미지정 시 dagster-dbt
  기본값은 `[source_name, table]`(2-세그먼트)이라 단일 세그먼트 자산키(`patient` 등)와 어긋나 lineage가
  끊긴다. (근거: `dagster_dbt` `default_asset_key_fn` — `meta.dagster.asset_key` 우선)
- Dagster **서브클래싱 없이 dbt 선언만으로** 연결한다(프로젝트 컨벤션).

## 테스트 (필수)

- 핵심 모델에는 스키마 테스트를 단다: `unique`, `not_null`, `relationships`, `accepted_values`.
- 추가 검증은 설치된 패키지 활용:
  - [`dbt_utils`](https://github.com/dbt-labs/dbt-utils) `1.3.3`
  - [`dbt_expectations`](https://github.com/metaplane/dbt-expectations) `0.10.10`

```yaml
# models/eicu/_eicu__models.yml
models:
  - name: eicu__patient_summary
    columns:
      - name: patient_id
        tests: [not_null, unique]
      - name: lab_count
        tests:
          - dbt_expectations.expect_column_values_to_be_between:
              min_value: 0
```

## Trino / Iceberg 주의사항

- `profiles.yml`의 `database`(= `iceberg`)는 Trino 카탈로그명과 일치해야 한다.
  ([architecture.md](../architecture.md) 참고)
- 기본 target은 `dev`(schema `dev`). prod 배포 시 `--target prod`.
- Iceberg 테이블 속성(파티셔닝 등)이 필요하면 `+table_properties` / `+partitioned_by`를
  config로 선언한다 (dbt-trino 문서 참고).

## 실행

```bash
dbt deps              # packages.yml 설치
dbt run               # 모델 빌드 (기본 target: dev)
dbt test              # 테스트
dbt run --target prod # prod 빌드
```

> Dagster를 통해 실행할 때는 `dbt_all_job` / 스케줄로 트리거된다 ([dagster.md](dagster.md)).

## 참고

- dbt-trino: https://github.com/starburstdata/dbt-trino
- dbt 모델 설정: https://docs.getdbt.com/docs/build/models
- dbt 테스트: https://docs.getdbt.com/docs/build/data-tests
- sqlfluff: https://docs.sqlfluff.com/
- dbt_utils: https://github.com/dbt-labs/dbt-utils
- dbt_expectations: https://github.com/metaplane/dbt-expectations
