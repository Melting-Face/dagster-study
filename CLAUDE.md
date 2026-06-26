# 프로젝트 CLAUDE.md (dagster-study)

## Dagster 코딩 컨벤션

### 에셋 생성은 클래스화를 지양한다

- Dagster 에셋은 **함수 + 데코레이터**(`@asset`, `@multi_asset`, `@dbt_assets`)로 정의한다.
  클래스 기반 정의나 커스터마이징을 위한 **불필요한 서브클래싱은 지양**한다.
- 커스터마이징이 필요하면 **선언적 설정**(데코레이터 인자, 메타데이터, dbt config 등)을 우선한다.
  - 예: dbt 에셋의 group은 `DagsterDbtTranslator` 서브클래스 대신
    dbt 모델/프로젝트의 config(`meta.dagster.group` 또는 `+group`)로 선언한다.
- 이유: 가독성·테스트 용이성·낮은 결합도. 함수형 정의가 Dagster의 권장 패턴이며 보일러플레이트가 적다.

## 프로젝트 구조 컨벤션

### 기능별 모듈 구성 (`dagster_project/template/` 패턴)

기능 단위 모듈은 역할별로 파일을 분리한다.

- `constants.py` — 상수/기본값
- `utils.py` — 외부 접속(카탈로그·파일시스템 등) 유틸
- `helper.py` — 핵심 처리 로직(순수 함수)
- `assets.py` — Dagster 에셋(팩토리 함수로 생성)

### S3 → Iceberg 적재

- `csv.gz` → Iceberg 적재는 `template.assets.build_csv_to_iceberg_asset` **팩토리**를 사용한다(클래스 지양).
- **메타스토어를 두지 않는다**: pyiceberg가 Trino와 동일한 Iceberg JDBC 카탈로그를 재사용한다.
- 무거운 파일은 스트리밍 + 청크 append로 처리한다(IO manager로 전량 메모리 적재 금지).
- 자세한 흐름·사용법은 [`docs/architecture.md`](docs/architecture.md) 참고.
