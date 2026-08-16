# Claude Code 스킬 (Agent Skills)

이 프로젝트가 의존하는 **Claude Code Agent Skills**(작업별 전문 지식·절차 묶음)와 사용 규칙을 정리한다.
**단일 출처는 저장소 루트 [`skills-lock.json`](../skills-lock.json)** 이며, 스킬 CLI가 설치·해시를 관리한다.

> 전역 규칙(`~/.claude/CLAUDE.md`) *Preferences #4* — **관련 스킬이 있으면 사용한다.**

스킬은 두 부류다: **① 잠긴 스킬**(`skills-lock.json`에 고정·커밋 → 재현성)과
**② 런타임 제공 스킬**(Claude Code 환경이 제공, lock 미고정 → 세션 가용성에 의존).

## ① 잠긴 스킬 (skills-lock.json — 커밋·재현성)

| 스킬 | 출처 | 언제 쓰나 |
| --- | --- | --- |
| **dagster-expert** | `dagster-io/skills` (github) | Dagster·`dg` CLI 관련 모든 작업 — 프로젝트 구조 파악, 에셋/스케줄/센서/잡 정의·검색, 디버깅, 개념 질의 |
| **dagster-integrations** | `dagster-io/skills` (github) | `dagster-*` 통합 라이브러리 탐색·이해(S3·Iceberg·dbt·k8s 등 연동) |
| **dignified-python** | `dagster-io/skills` (github) | 범용 프로덕션 Python 표준(타입 문법·예외·pathlib 등). **본 프로젝트 컨벤션이 우선** — 아래 §충돌 규칙 |

> `sourceType: github`, 각 스킬은 `computedHash`로 무결성을 고정한다(락 파일이 진실의 출처).

## ② 작업 유형별 스킬 매핑 (런타임 제공 포함)

이 프로젝트 스택에 대응하는 스킬. 🔒=잠긴 스킬, ⚙️=런타임 제공(lock 미고정).

| 작업 영역 | 스킬 | 구분 |
| --- | --- | --- |
| Dagster 오케스트레이션·에셋 | `dagster-expert` · `dagster-integrations` | 🔒 |
| Python 코드 품질 | `dignified-python`(프로젝트 컨벤션 우선) | 🔒 |
| dbt 모델링·테스트·실행 | `using-dbt-for-analytics-engineering` · `adding-dbt-unit-test` · `running-dbt-commands` · `building-dbt-semantic-layer` · `troubleshooting-dbt-job-errors` · `fetching-dbt-docs` | ⚙️ |
| Spark 배치·성능 튜닝 | `spark-engineer` · `spark-optimization` | ⚙️ |
| SQL 성능 최적화 | `sql-optimization` | ⚙️ |
| 분석·애드혹 질의 | `answering-natural-language-questions-with-dbt` · `duckdb` | ⚙️ |
| 컨테이너·Compose | `docker-expert` | ⚙️ |
| Kubernetes·k3s·Helm | `kubernetes-specialist` · `helm-chart-scaffolding` | ⚙️ |
| CI/CD(GitHub Actions) | `github-actions-templates` | ⚙️ |
| 쉘 스크립트 품질 | `shellcheck-configuration` | ⚙️ |
| Terraform/IaC | **전용 스킬 없음** → [conventions/terraform.md](conventions/terraform.md) 규칙 준수 | — |

- **워크플로 스킬**(도메인 아님, 슬래시 커맨드): `code-review` · `simplify` · `verify` · `security-review` · `run` ·
  `find-skills` · `auditing-skills` — 검토·검증·실행 보조에 쓴다.
- **주의**: ⚙️ 런타임 스킬은 `skills-lock.json`에 고정되지 않아 **세션마다 가용성이 다를 수 있다**.
  자주 쓰는 스킬은 lock에 추가할지 검토한다(§관리).

## 사용 규칙

1. **작업–스킬 매핑**(§②)을 우선 확인해 해당 스킬을 사용한다(관련 스킬이 있으면 반드시 활용).
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
