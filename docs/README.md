# dagster-study 문서

이 프로젝트의 아키텍처와 코딩 규칙을 정리한 문서 모음입니다.
(GitHub Wiki로 이식 가능하도록 평면 구조로 작성)

## 목차

### 아키텍처

- [전체 아키텍처 / 데이터 흐름](architecture.md) — Dagster · dbt · Trino · Iceberg · SeaweedFS 스택과 레이크하우스 구조, **bronze 적재 템플릿(S3→Iceberg)**

### 코딩 규칙 (conventions)

| 문서                                | 내용                                                   |
| ----------------------------------- | ------------------------------------------------------ |
| [공통 규칙](conventions/general.md) | 언어, 들여쓰기, 커밋 메시지, 디렉토리 규칙             |
| [Python](conventions/python.md)     | ruff, 타입 힌트, 예외 처리, 의존성 관리                |
| [Dagster](conventions/dagster.md)   | 에셋 정의(함수형), 컴포넌트, 잡·스케줄, 그룹           |
| [dbt](conventions/dbt.md)           | 모델 레이어링, 네이밍, 테스트, sqlfluff, Trino/Iceberg |

## 핵심 원칙 요약

1. **에셋은 함수 + 데코레이터로 정의** — 클래스/서브클래싱 지양, 선언적 설정 우선
2. **주석은 한국어, 식별자(변수·함수·모델명)는 영어**
3. **들여쓰기 스페이스 4칸** (Python·YAML·SQL 공통)
4. **포매터/린터 고정** — Python: `ruff`, SQL: `sqlfluff`
5. **커밋 메시지는 한국어 `type: 설명`** 형식

## 문서 작성·유지 규칙

- 문서는 한국어로 작성한다.
- 코드 식별자·명령어·경로는 영어/원문 그대로 표기한다.
- 규칙을 바꿀 때는 **이 docs와 `CLAUDE.md`를 함께 갱신**하여 단일 출처(single source of truth)를 유지한다.
- 외부 레퍼런스는 각 문서 하단 `참고` 섹션에 링크와 함께 남긴다.
