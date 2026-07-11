# 문서 동기화 (doc-sync)

이 프로젝트는 **규칙·결정·작업 패턴을 문서로 남기고 단일 출처(single source of truth)를
유지**한다(프로젝트 [`CLAUDE.md`](../CLAUDE.md) 문서화 원칙). 규칙이 바뀌면 정본 문서와
그 규칙을 요약·참조하는 문서를 **함께** 갱신해 드리프트를 막는다.

## 단일 출처 원칙

- 한 규칙의 **정본은 한 곳**에만 둔다. 다른 문서는 요약하고 정본을 링크한다.
- [`CLAUDE.md`](../CLAUDE.md)는 **핵심 컨벤션의 요약/인덱스**, 상세 배경·흐름은 `docs/`에 둔다.
- 도구로 강제 가능한 규칙(lint·format)의 정본은 **도구 설정 파일**(repo 루트 `pyproject.toml`의
  `[tool.ruff.*]`·`[tool.sqlfluff.*]` 등)이다. 문서는 그 설정의 의도를 설명할 뿐 값을 중복 정의하지 않는다.

## 변경 유형별 동기화 체인

| 변경 | 정본(먼저 수정) | 함께 갱신 |
| --- | --- | --- |
| 코딩 규칙 | `docs/conventions/<topic>.md` | `CLAUDE.md` 요약 · `docs/README.md` 목차 |
| 아키텍처·데이터 흐름 | `docs/architecture.md` | `CLAUDE.md` · 관련 `conventions/*` 링크 |
| 프로젝트 구조 | `docs/conventions/dagster.md` | `CLAUDE.md` 구조 섹션 |
| 운영·리소스 | `docs/operations.md` · `docs/resource-sizing.md` | `CLAUDE.md` · `compose.yml` 주석 |
| 환경변수 추가 | `.env.example` | `compose.yml`(앵커) → 코드(`EnvVar`) → `docs/operations.md` 전파 체인 |
| 데이터셋 스키마·피처 | `docs/dataset_schema.md` | 해당 `models/<dataset>/source.yml` · `schema.yml` |

## 실무 규칙

1. **정본을 먼저 고치고**, 그 규칙을 요약·참조하는 문서를 뒤이어 맞춘다.
2. 코드·설정과 문서가 어긋나면 **코드/설정이 사실**이다. 문서를 코드에 맞춘다(반대 아님).
3. 새 규칙·결정은 근거(왜)와 함께 남긴다. 외부 표준은 [`references.md`](references.md)에 등록하고 링크한다.
4. 문서는 한국어로 쓰고, 코드 식별자·명령어·경로는 원문 그대로 표기한다.

## 참고

- 문서화 원칙: 프로젝트 [`CLAUDE.md`](../CLAUDE.md) · 전역 규칙
- 외부 표준 인덱스: [`references.md`](references.md)
