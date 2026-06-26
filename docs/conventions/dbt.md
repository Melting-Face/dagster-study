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

### 설정은 `pyproject.toml`에서 관리한다

sqlfluff 명세는 별도 `.sqlfluff` 파일 대신 **`pyproject.toml`의 `[tool.sqlfluff.*]`** 섹션에 둔다.
(sqlfluff는 `tool.sqlfluff`로 시작하는 nested 섹션을 공식 지원한다.)

```toml
# pyproject.toml
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

## 모델 레이어링 (Medallion)

레이크하우스 계층을 디렉토리·스키마로 분리한다.

| 레이어                  | 의미                          | materialization 권장 |
| ----------------------- | ----------------------------- | -------------------- |
| `bronze` (staging)      | 원천 정제(타입·컬럼명 표준화) | `view`               |
| `silver` (intermediate) | 조인·비즈니스 로직            | `view` 또는 `table`  |
| `gold` (marts)          | 분석/소비용 집계              | `table`              |

```text
models/
├── bronze/
├── silver/
└── gold/
```

> 현재 `dbt_project.yml`은 bronze 레이어가 리셋된 상태(example 모델 제거).
> 새 모델은 `models/` 하위에 추가하고 필요 시 `+config`를 선언한다.

## 네이밍

- 모델 파일·이름은 `snake_case`, 영어.
- 레이어 접두어 권장: `bronze_<source>__<entity>`, `gold_<subject>` 등.
- 컬럼명은 `snake_case`.

## 모델 설정 (선언적)

- materialization·group 등은 **`dbt_project.yml`의 `+config`** 또는 모델 상단
  **`{{ config(...) }}`** 로 선언한다.
- Dagster 그룹도 dbt 쪽 config로 선언한다 (Dagster 서브클래싱 대신).

```yaml
# dbt_project.yml
models:
  dbt_pipelines:
    bronze:
      +materialized: view
      +schema: bronze
    gold:
      +materialized: table
      +schema: gold
      +meta:
        dagster:
          group: gold # ← Dagster 에셋 그룹을 dbt config로 선언
```

```sql
-- models/gold/gold_daily_sales.sql
{{ config(materialized='table') }}

select
    order_date,
    sum(amount) as total_amount
from {{ ref('silver_orders') }}
group by order_date
```

## ref / source

- 모델 간 참조는 항상 **`{{ ref('...') }}`**, 원천 참조는 **`{{ source('...') }}`** 를 쓴다.
  하드코딩된 테이블명을 금지한다 (lineage 보존).

## 테스트 (필수)

- 핵심 모델에는 스키마 테스트를 단다: `unique`, `not_null`, `relationships`, `accepted_values`.
- 추가 검증은 설치된 패키지 활용:
  - [`dbt_utils`](https://github.com/dbt-labs/dbt-utils) `1.3.3`
  - [`dbt_expectations`](https://github.com/metaplane/dbt-expectations) `0.10.10`

```yaml
# models/gold/_gold__models.yml
models:
  - name: gold_daily_sales
    columns:
      - name: order_date
        tests: [not_null, unique]
      - name: total_amount
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
