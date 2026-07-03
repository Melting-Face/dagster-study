# dagster-study 문서

이 프로젝트의 아키텍처와 코딩 규칙을 정리한 문서 모음입니다.
(GitHub Wiki로 이식 가능하도록 평면 구조로 작성)

## 목차

### 아키텍처

- [전체 아키텍처 / 데이터 흐름](architecture.md) — Dagster · dbt · Trino · Iceberg · SeaweedFS 스택과 레이크하우스 구조, **bronze 적재 템플릿(S3→Iceberg)**

### 데이터셋

- [데이터셋 스키마·피처 레퍼런스](dataset_schema.md) — MIMIC-IV(icu·hosp 11테이블)·eICU(3테이블) 원천 스키마와 **SOFA→Sepsis-3 실버 파이프라인(22 모델)** 매핑

### 철학

- [코딩 철학](philosophy.md) — 단순함·명시적·가독성·비밀정보 참조·재사용 추출 (PEP 20 / 12-Factor / Rule of Three)

### 코딩 규칙 (conventions)

| 문서                                | 내용                                                   |
| ----------------------------------- | ------------------------------------------------------ |
| [공통 규칙](conventions/general.md) | 언어, 들여쓰기, 커밋 메시지, 디렉토리 규칙             |
| [Python](conventions/python.md)     | ruff, 타입 힌트, 예외 처리, 의존성 관리                |
| [Dagster](conventions/dagster.md)   | 에셋 정의(함수형), 메타데이터, 서브프로젝트 체크리스트, 잡·스케줄 |
| [dbt](conventions/dbt.md)           | 모델 레이어링, 네이밍, 테스트, sqlfluff, Trino/Iceberg |
| [타임존](conventions/timezone.md)   | 저장=UTC / 표시·스케줄=KST, `execution_timezone`, tz-aware datetime |
| [Docker](conventions/docker.md)     | Compose 앵커, `latest` 금지, healthcheck, `deploy.resources`, Dockerfile |

### 운영 (operations)

- [환경변수·운영 정책](operations.md) — `.env`→compose→`EnvVar` 전파 체인, Iceberg snapshot·로그 보존 정책
- [리소스 산정](resource-sizing.md) — 호스트 자원에 따른 서비스 옵션 조정(Trino 3파일 결합·daemon OOM 계산·Postgres·SeaweedFS)

## 핵심 원칙 요약

> 가치(왜)는 [코딩 철학](philosophy.md), 아래는 빠른 규칙 참조(어떻게).

1. **주석은 한국어, 식별자(변수·함수·모델명)는 영어**
2. **들여쓰기 스페이스 4칸** (Python·YAML·SQL 공통)
3. **포매터/린터 고정** — Python: `ruff`, SQL: `sqlfluff`
4. **커밋 메시지는 한국어 `type: 설명`** 형식

## 문서 작성·유지 규칙

- 이 프로젝트에서 정한 **규칙·결정·작업 패턴은 최대한 문서로 남긴다**.
- 문서는 한국어로 작성한다.
- 코드 식별자·명령어·경로는 영어/원문 그대로 표기한다.
- 규칙을 바꿀 때는 **`CLAUDE.md`·이 `docs/`·`README.md`를 함께 갱신**하여 단일 출처(single source of truth)를 유지한다.
- 외부 레퍼런스는 각 문서 하단 `참고` 섹션에 링크와 함께 남긴다.

상세 규칙과 인덱스:

- [문서 동기화(doc-sync)](doc-sync.md) — 단일 출처 원칙, 변경 유형별 동기화 체인
- [참고 문서(references)](references.md) — 규칙·설계가 근거로 삼는 외부 표준 인덱스
