# Claude Code 스킬 (Agent Skills)

이 프로젝트가 의존하는 **Claude Code Agent Skills**(작업별 전문 지식·절차 묶음)와 사용 규칙을 정리한다.
**단일 출처는 저장소 루트 [`skills-lock.json`](../skills-lock.json)** 이며, 스킬 CLI가 설치·해시를 관리한다.

> 전역 규칙(`~/.claude/CLAUDE.md`) *Preferences #4* — **관련 스킬이 있으면 사용한다.**

스킬은 두 부류다: **① 잠긴 스킬**(`skills-lock.json`에 고정·커밋 → 재현성)과
**② 잠기지 않은 스킬**(lock 미고정 → 무결성·재현성 미보장).

> 🔴 **분류 정정(2026-08-19 실측)** — 이전 문서는 ②를 "런타임 제공(Claude Code 환경이 제공)"으로 적었으나
> **사실이 아니다.** ②도 대부분 **`~/.claude/skills/`에 실제 설치된 디스크 파일**이다. 즉 "환경이 주는 것"이
> 아니라 **"설치했는데 lock에만 없는 것"** 이다. 아래 §실측 참조.

### 실측 (2026-08-19)

| 항목 | 값 | 함의 |
| --- | --- | --- |
| `~/.claude/skills/` 실제 설치 | **24개** | 전부 디스크 상주 — 세션 제공이 아니다 |
| `skills-lock.json` 등재 | **3개** | `computedHash` 무결성 고정이 **12.5%** 에만 적용 |
| `.claude/skills/`(프로젝트 스코프) | **없음** | 스킬은 전부 **전역**(`~/.claude/`) — 저장소를 클론해도 따라오지 않는다 |
| 스킬 CLI | **PATH에 없음** | §관리의 "CLI로 설치하면 lock에 기록" 절차가 **현재 환경에서 실행 불가** |

- 따라서 **"lock을 커밋해 팀·CI가 동일 스킬 버전을 쓴다"는 재현성 주장은 현재 3/24에만 성립**한다.
- 배선·드리프트 감사는 **[`skill-matcher`](../.claude/agents/skill-matcher.md)** 워커가 담당한다(§③).

## ① 잠긴 스킬 (skills-lock.json — 커밋·재현성)

| 스킬 | 출처 | 언제 쓰나 |
| --- | --- | --- |
| **dagster-expert** | `dagster-io/skills` (github) | Dagster·`dg` CLI 관련 모든 작업 — 프로젝트 구조 파악, 에셋/스케줄/센서/잡 정의·검색, 디버깅, 개념 질의 |
| **dagster-integrations** | `dagster-io/skills` (github) | `dagster-*` 통합 라이브러리 탐색·이해(S3·Iceberg·dbt·k8s 등 연동) |
| **dignified-python** | `dagster-io/skills` (github) | 범용 프로덕션 Python 표준(타입 문법·예외·pathlib 등). **본 프로젝트 컨벤션이 우선** — 아래 §충돌 규칙 |

> `sourceType: github`, 각 스킬은 `computedHash`로 무결성을 고정한다(락 파일이 진실의 출처).

## ② 작업 유형별 스킬 매핑

이 프로젝트 스택에 대응하는 스킬. 🔒=잠긴 스킬(lock 등재), ⚙️=**잠기지 않은 스킬**(디스크 설치·lock 미고정).

| 작업 영역 | 스킬 | 구분 |
| --- | --- | --- |
| Dagster 오케스트레이션·에셋 | `dagster-expert` · `dagster-integrations` | 🔒 |
| Python 코드 품질 | `dignified-python`(프로젝트 컨벤션 우선) | 🔒 |
| dbt 모델링·테스트·실행 | `using-dbt-for-analytics-engineering` · `adding-dbt-unit-test` · `running-dbt-commands` · `building-dbt-semantic-layer` · `troubleshooting-dbt-job-errors` · `fetching-dbt-docs` | ⚙️ |
| dbt 엔진·플랫폼 이행(저빈도) | `migrating-dbt-core-to-fusion` · `migrating-dbt-project-across-platforms` | ⚙️ **★3 이하** — 워커 지시문 미등재(§③ 임계) |
| dbt MCP 서버 설정 | `configuring-dbt-mcp-server` | ⚙️ **★3 이하** — 본 저장소는 dbt MCP 미사용 |
| Spark 배치·성능 튜닝 | `spark-engineer` · `spark-optimization` | ⚙️ |
| SQL 성능 최적화 | `sql-optimization` | ⚙️ |
| 분석·애드혹 질의 | `answering-natural-language-questions-with-dbt` · `duckdb` | ⚙️ |
| 차트·시각화(리포트 그림) | `dataviz` | ⚙️ |
| 컨테이너·Compose | `docker-expert` | ⚙️ |
| Kubernetes·k3s·Helm | `kubernetes-specialist` · `helm-chart-scaffolding` | ⚙️ |
| CI/CD(GitHub Actions) | `github-actions-templates` | ⚙️ |
| 쉘 스크립트 품질 | `shellcheck-configuration` | ⚙️ |
| Terraform/IaC | **전용 스킬 없음** → [conventions/terraform.md](conventions/terraform.md) 규칙 준수 | — |

- **워크플로 스킬**(도메인 아님, 슬래시 커맨드): `code-review` · `simplify` · `security-review` · `run` ·
  `find-skills` · `auditing-skills` · 프로젝트 자체 커맨드 `journal` — 검토·검증·실행 보조에 쓴다.
  ⚠️ 이전 문서에 있던 **`verify`는 2026-08-19 세션 목록·디스크 어디에도 없다** — 죽은 참조로 판단해 제거했다.
- **주의**: ⚙️ 스킬은 `skills-lock.json`에 고정되지 않아 **무결성(`computedHash`)이 검증되지 않으며**,
  하네스가 제공하는 슬래시 커맨드는 **세션마다 가용성이 다를 수 있다**.
  자주 쓰는 스킬은 lock에 추가할지 검토한다(§관리).
- 하네스 기본 제공 커맨드(`update-config`·`loop`·`schedule`·`claude-api`·`artifact-*` 등)는 **프로젝트 스택 스킬이 아니므로**
  이 표에서 관리하지 않는다.

## ③ 전문 워커별 참고 스킬 (`.claude/agents/`)

각 전문 워커([conventions/agents.md](conventions/agents.md) §네이티브 구현)는 지시문에 **자기 작업에 해당하는 스킬만**
추려 담고, **이 문서를 정본으로 링크**한다. 스킬 목록을 워커 파일마다 복제하면 스킬 추가·제거 때 여러 곳이 드리프트한다.

**등재 기준은 별점(★)이다** — 워커×스킬을 5축 루브릭(스택 일치·권한 정합·정본 무충돌·호출 빈도·대체 불가)으로
채점해 **★4 이상만 등재**하고, ★3 이하는 등재하지 않는다. 축 2·3(권한·정본 충돌)이 0점이면 합계와 무관하게 제외한다.
🔴 **출처 신뢰성은 별점 축이 아니라 별개 게이트**다(별점에 섞으면 "★5인데 출처 불명"을 못 잡는다) — `security` 판정 대상.
루브릭 전문과 채점 매트릭스는 **[`skill-matcher`](../.claude/agents/skill-matcher.md)** 가 정본이며,
이 표는 그 결과 중 **등재분만** 옮긴 것이다.

| 워커 | 주 스킬 | 제약 |
| --- | --- | --- |
| `data-engineer` | `dagster-expert` · `dagster-integrations` · `using-dbt-for-analytics-engineering` · `running-dbt-commands` · `sql-optimization` · `dignified-python` | 범용 Python 스킬은 **프로젝트 컨벤션 우선** |
| `data-verifier` | `sql-optimization` · `answering-natural-language-questions-with-dbt` · `duckdb` · `fetching-dbt-docs` | **읽기 질의만** — 모델 생성·대용량 전량 로드 금지 |
| `data-qa` | `adding-dbt-unit-test`(핵심) · `using-dbt-for-analytics-engineering` · `fetching-dbt-docs` · `running-dbt-commands` · `troubleshooting-dbt-job-errors` | dbt CLI는 `parse`·`ls`·`compile`만(`build`/`run` 금지) |
| `devops-engineer` | `docker-expert` · `kubernetes-specialist` · `helm-chart-scaffolding` · `github-actions-templates` · `shellcheck-configuration` | Terraform은 전용 스킬 없음 → [conventions/terraform.md](conventions/terraform.md) |
| `devops-verifier` | `docker-expert` · `kubernetes-specialist` | **진단·해석까지만** — 스킬이 권하는 수정·재기동 실행 금지 |
| `devops-qa` | `docker-expert` · `kubernetes-specialist` · `github-actions-templates` · `shellcheck-configuration` | 감사 기준은 **스킬이 아니라 정본** (아래 충돌 규칙) |
| `analyst` | `answering-natural-language-questions-with-dbt` · `using-dbt-for-analytics-engineering`(초안만) · `duckdb` · `dataviz` · `sql-optimization` · `spark-optimization` | **읽기 질의만** — `dbt build`/`run`·정의 파일 수정 금지, gold 모델은 **제안만** |
| `security` | **전용 스킬 없음** → [security.md](security.md)·[conventions/general.md](conventions/general.md) | 도메인 스킬은 설정 해석 목적의 **읽기 참조만** |
| `skill-matcher` | `find-skills` · `auditing-skills` | **조회·평가까지만** — 설치·lock 편집·워커 정의 수정 금지. 외부 스킬 신뢰성 **최종 판정은 `security`** |
| `director` | 도메인별 — [.claude/agents/director.md](../.claude/agents/director.md) §도메인 지식 표 | 도메인 지식은 인라인하지 않고 참조 |
| `archivist` | **없음(의도)** | 관측·기록만 하는 계층 밖 워커 — 도메인 스킬이 필요 없다 |

- **외부 표준·공식 문서 URL은 [references.md](references.md)에 단일 관리**한다. 워커 지시문은 **URL을 복제하지 않고**
  references.md 항목명(또는 정본 문서 경로)을 가리킨다 — 링크가 바뀌면 한 곳만 고치면 된다.
- **스킬의 범용 권고 ≠ 이 저장소의 결정.** 근거와 함께 다르게 정한 항목(예: `profiles` 채택, `.tf` 2-space,
  `chrislusf/seaweedfs` 태그 미고정, Dagster 호스트 유지)은 스킬 권고와 어긋나더라도 **정본이 이긴다**.
  판정 워커(`*-qa`·`*-verifier`)가 이를 갭으로 올리지 않도록 각 지시문에 예외를 명시했다.

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
  ⚠️ **그 CLI가 현재 환경 PATH에 없다**(§실측) — 이 절차는 지금 실행 불가이며, 그래서 21/24가 lock 밖에 있다.
- **감사**: 외부 스킬은 도입 전 내용을 검토한다(보안·품질). 신뢰 출처(`dagster-io/skills`)만 사용한다.
- **재현성**: `skills-lock.json`은 **커밋**해 팀·CI가 동일 스킬 버전을 쓰게 한다(락은 진실의 출처).
- **배선 감사 주기**: 스킬 추가·제거 후, 워커 신설·개편 시 **[`skill-matcher`](../.claude/agents/skill-matcher.md)** 를 배정한다.

### 출처 실측 (2026-08-19) — 24개 인벤토리

| 출처 | 개수 | 무결성 고정 | 판정 |
| --- | --- | --- | --- |
| `dagster-io/skills` | 3 | ✅ `computedHash` | 신뢰 출처 — lock 등재분 |
| `metadata.author: dbt-labs` | 10 | ❌ 없음 | 벤더 공식 — 신뢰 가능하나 **lock 미등재** |
| **`metadata.author: https://github.com/Jeffallan`**(개인) | **2** | ❌ 없음 | 🔴 `kubernetes-specialist`·`spark-engineer` — **신뢰 출처 규약 위반**, `security` 판정 대상 |
| 출처 메타 없음 | 9 | ❌ 없음 | ⚠️ `auditing-skills`·`docker-expert`·`duckdb`·`find-skills`·`github-actions-templates`·`helm-chart-scaffolding`·`shellcheck-configuration`·`spark-optimization`·`sql-optimization` — 출처 `미확인` |

- 🔴 **`kubernetes-specialist`·`spark-engineer`는 `devops-engineer`·`devops-qa`·`devops-verifier`·`analyst`에 등재된 상태**다.
  개인 저장소 출처가 무결성 검증 없이 인프라 워커에 물려 있다 — **도입 가부 재판정을 `security`에 올린다**.
- **재채점 대상**(축1·4 의심, `skill-matcher` 첫 미션): `analyst`의 `spark-optimization`(읽기 질의 워커에 튜닝 스킬),
  `data-verifier`의 `duckdb`(조회 엔진은 Trino).

## 참고

- Claude Code Skills 문서: https://docs.claude.com/en/docs/claude-code/skills
- dagster-io/skills: https://github.com/dagster-io/skills
