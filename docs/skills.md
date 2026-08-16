# Claude Code 스킬 (Agent Skills)

이 프로젝트가 의존하는 **Claude Code Agent Skills**(작업별 전문 지식·절차 묶음)와 사용 규칙을 정리한다.
**단일 출처는 저장소 루트 [`skills-lock.json`](../skills-lock.json)** 이며, 스킬 CLI가 설치·해시를 관리한다.

> 전역 규칙(`~/.claude/CLAUDE.md`) *Preferences #4* — **관련 스킬이 있으면 사용한다.**

## 설치된 스킬 (skills-lock.json)

| 스킬 | 출처 | 언제 쓰나 |
| --- | --- | --- |
| **dagster-expert** | `dagster-io/skills` (github) | Dagster·`dg` CLI 관련 모든 작업 — 프로젝트 구조 파악, 에셋/스케줄/센서/잡 정의·검색, 디버깅, 개념 질의 |
| **dagster-integrations** | `dagster-io/skills` (github) | `dagster-*` 통합 라이브러리 탐색·이해(S3·Iceberg·dbt·k8s 등 연동) |
| **dignified-python** | `dagster-io/skills` (github) | 범용 프로덕션 Python 표준(타입 문법·예외·pathlib 등). **본 프로젝트 컨벤션이 우선** — 아래 §충돌 규칙 |

> `sourceType: github`, 각 스킬은 `computedHash`로 무결성을 고정한다(락 파일이 진실의 출처).

## 사용 규칙

1. **작업–스킬 매핑**을 우선 확인한다.
   - Dagster 에셋/정의/디버깅 → `dagster-expert`
   - 외부 기술 연동(`dagster-*`) 탐색 → `dagster-integrations`
   - 순수 Python 작성·리팩터 → `dignified-python`(단, 프로젝트 컨벤션 우선)
2. **프로젝트 컨벤션 > 범용 스킬** (충돌 시).
   범용 스킬(`dignified-python`)과 본 저장소 규칙이 다르면 **저장소 규칙을 따른다**. 예:
   - 주석은 **한국어**, 식별자는 영어 ([conventions/python.md](conventions/python.md))
   - `scripts/`는 **절차형**(클래스/보조함수 최소화, C901 면제) ([conventions/python.md](conventions/python.md))
   - Dagster 에셋은 **함수+데코레이터**(클래스/서브클래싱 지양) ([conventions/dagster.md](conventions/dagster.md))
3. **문서화 원칙 적용**: 스킬을 새로 도입·제거하면 이 문서와 `skills-lock.json`을 함께 갱신한다([doc-sync.md](doc-sync.md)).

## 관리 (설치·갱신·감사)

- **추가/갱신**: 스킬 CLI로 설치하면 `skills-lock.json`에 source·`computedHash`가 기록된다(수동 편집 금지).
- **감사**: 외부 스킬은 도입 전 내용을 검토한다(보안·품질). 신뢰 출처(`dagster-io/skills`)만 사용한다.
- **재현성**: `skills-lock.json`은 **커밋**해 팀·CI가 동일 스킬 버전을 쓰게 한다(락은 진실의 출처).

## 참고

- Claude Code Skills 문서: https://docs.claude.com/en/docs/claude-code/skills
- dagster-io/skills: https://github.com/dagster-io/skills
