# 프로젝트 CLAUDE.md (dagster-study)

## 문서화 원칙

- 이 프로젝트에서 정한 **규칙·결정·작업 패턴은 최대한 문서로 남긴다**.
- 규칙을 새로 정하거나 바꾸면 `CLAUDE.md`·`docs/`·`README.md`를 **함께 갱신**해 단일 출처(single source of truth)를 유지한다.
- `CLAUDE.md`는 핵심 컨벤션의 **요약/인덱스**, 상세 배경·흐름은 `docs/`에 둔다.
- 문서는 한국어로 작성하고, 코드 식별자·명령어·경로는 원문 그대로 표기한다.

## 커밋 컨벤션

- **Conventional Commits**를 따른다. (전역 `CLAUDE.md`와 동일 규약)
- 형식 `type(scope): 설명` — 설명은 한국어, 제목 72자 이내.
- type: `feat`·`fix`·`docs`·`style`·`refactor`·`perf`·`test`·`build`·`ci`·`chore`·`revert`.
- gitlint `contrib-title-conventional-commits`로 강제. 상세·매핑은 [`docs/conventions/general.md`](docs/conventions/general.md).

## 코딩 철학

핵심 가치 (상세 [`docs/philosophy.md`](docs/philosophy.md)):

1. **단순함** — 함수+데코레이터, 최소 인프라(YAGNI) *(PEP 20)*
2. **명시적** — 선언적 설정, 규칙은 문서로 *(PEP 20)*
3. **가독성** — 관심사 분리, 일관 네이밍, 포매터 고정 *(PEP 20)*
4. **비밀정보는 참조로** — 환경변수/시크릿 비노출 *(12-Factor Config)*
5. **재사용은 3회부터 추출** — 3회 이상 반복 시 함수화/상수화 *(Rule of Three / DRY)*
6. **추적 용이성** — wiring 집중·named constant·명시 정의로 grep/점프 용이, 단순 리턴은 인라인 *(Locality of Behaviour)*

## Dagster 코딩 컨벤션

### 에셋 생성은 클래스화를 지양한다

- Dagster 에셋은 **함수 + 데코레이터**(`@asset`, `@multi_asset`, `@dbt_assets`)로 정의한다.
  클래스 기반 정의나 커스터마이징을 위한 **불필요한 서브클래싱은 지양**한다.
- 커스터마이징이 필요하면 **선언적 설정**(데코레이터 인자, 메타데이터, dbt config 등)을 우선한다.
  - 예: dbt 에셋의 group은 `DagsterDbtTranslator` 서브클래스 대신
    dbt 모델/프로젝트의 config(`meta.dagster.group` 또는 `+group`)로 선언한다.
- 이유: 가독성·테스트 용이성·낮은 결합도. 함수형 정의가 Dagster의 권장 패턴이며 보일러플레이트가 적다.

### 각 에셋은 명시적으로 분리 정의한다

- 에셋은 **팩토리로 동적 생성하지 않고** 각각 `@asset` 함수로 **명시적으로 정의**한다.
  → 에셋 이름으로 바로 검색/점프(탐색성), per-asset 커스터마이징(deps·partition·description·automation)이 자연스럽다.
- 공통 처리 로직은 일반 함수(`common.helper`)로 분리해 재사용하되(DRY), **에셋 정의 자체는 분리·명시**한다.
- 에셋은 **데이터셋별 서브프로젝트 단위로 분리 관리**한다(`<dataset>/assets.py`).

## 프로젝트 구조 컨벤션

### 공통/서브프로젝트 분리 (`common/` + `<dataset>/`)

- **공통 재사용 로직**은 `dagster_project/common/`에 둔다(데이터셋 무관 공통 라이브러리).
  - `constants.py` — 공통 상수/기본값
  - `resources.py` — 공유 Iceberg 카탈로그 설정(`catalog_properties`·`build_catalog_config`). IO 매니저·테이블 리소스·`S3Resource`는 단순 생성이라 `definitions.py`에서 인라인, S3 파라미터는 `constants.py`
  - `helper.py` — 적재 헬퍼(`read_csv_gz_table` 일반 / `load_heavy_csv_gz_to_iceberg` 대용량)
  - `dbt.py` — 공유 dbt 설정(`DbtProject`·`build_dbt_resource`); 단일 dbt 프로젝트를 데이터셋 subproject가 공유
- **에셋은 데이터셋별 서브프로젝트** `dagster_project/<dataset>/`에 **정의만** 둔다.
  - `constants.py` — 데이터셋 전용 `NAMESPACE`·`GROUP_NAME`·`SOURCE_BASE`
  - `assets.py` — 테이블별 **명시적 `@asset`**(bronze 적재)
  - `dbt_assets.py` — 데이터셋 dbt 모델 소유(`@dbt_assets(select="path:models/<dataset>")`)
- **wiring은 최상위 `definitions.py` 한 곳**에 모은다: 자산 등록·리소스 바인딩·잡/스케줄을
  **단일 `Definitions`**로 선언한다(중간 definitions 레이어·자동발견·merge 없음, 모듈 스코프 `Definitions` 1개).

### S3 → Iceberg 적재 (리소스 기반, 2경로)

- S3/Iceberg 연결은 **Dagster 리소스로 관리**한다: `dagster-aws` `S3Resource` + `dagster-iceberg`(IO 매니저·`IcebergTableResource`). 연결을 자산이 아닌 리소스에 둔다.
- **일반(부하 없는) 파일**: 자산이 `pa.Table` 반환 → **dagster-iceberg IO 매니저**가 자동 create+적재.
- **대용량 파일(예: 3.3GB)**: boto3 스트리밍 + **청크 append**(`load_heavy_csv_gz_to_iceberg`, IO 매니저 미사용 — 전량 메모리 적재 금지).
- **메타스토어를 두지 않는다**: Trino와 동일한 Iceberg JDBC 카탈로그를 재사용한다.
- **dbt 미생성 테이블(=Dagster 적재분)은 dbt `source()`로 참조**한다. source는 데이터셋별
  `models/<dataset>/source.yml`에 두고 `meta.dagster.asset_key`로 Dagster 자산키와 매핑해 lineage를
  연결한다. 메달리온 레이어는 스키마 접두어가 아닌 **kind(Dagster)/tag(dbt)** 로 표기한다.
  상세 [`docs/conventions/dbt.md`](docs/conventions/dbt.md).
- 자세한 흐름·사용법은 [`docs/architecture.md`](docs/architecture.md) 참고.
