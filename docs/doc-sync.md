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
| 코딩 철학(핵심 가치) | `docs/philosophy.md` | `CLAUDE.md` §코딩 철학 **번호까지 일치**시킨다(요약 목록이 원칙 표와 1:1) · `docs/references.md`(출처) |
| 아키텍처·데이터 흐름 | `docs/architectures/overview.md` | `CLAUDE.md` · 관련 `conventions/*` 링크 |
| 처리·배포 기술(개별) | `docs/architectures/<tech>.md`(trino·docker·spark·flink·k8s) | `docs/architectures/README.md` 목차 · `docs/references.md`(기술 출처) |
| 프로젝트 구조 | `docs/conventions/dagster.md` | `CLAUDE.md` 구조 섹션 |
| 운영·리소스 | `docs/operations.md` · `docs/resource-sizing.md` | `CLAUDE.md` · `compose.yml` 주석 |
| 관측·모니터링 | `docs/conventions/monitoring.md` | `docs/architectures/monitoring.md`(현행 실태·기술 결정) · `CLAUDE.md` 운영 섹션 · `docs/README.md` 목차 · `docs/security.md`(2.11 사고 예방·대응, 2.10 감사 로그)<br/>🔴 **규칙 정본과 실태 문서를 가른다** — 관측 *수단*의 작성법은 이미 소유자가 있다(compose healthcheck는 `docs/conventions/docker.md`, K8s probe는 `docs/conventions/k8s.md`, 로그 보존은 `docs/operations.md`, 자원 실측 수치는 `docs/resource-sizing.md`). 새 문서에 **다시 쓰지 말고 링크**한다. |
| 보안·거버넌스 | `docs/security.md` | `CLAUDE.md` 운영 섹션 · `docs/references.md`(규제 출처) · `.claude/agents/security.md`(점검 항목) |
| 환경변수 추가 | `.env.example` | `compose.yml`(앵커) → 코드(`EnvVar`) → `docs/operations.md` 전파 체인 |
| 데이터셋 스키마·피처 | `docs/dataset_schema.md` | 해당 `models/<dataset>/source.yml` · `schema.yml` |
| 분석 규칙(gold·노트북·리포트) | `docs/conventions/analysis.md` | `CLAUDE.md` 분석 섹션 · `docs/conventions/dbt.md`(gold 레이어) · `docs/test.md`(grain 테스트) · `notebooks/README.md` |
| 외부 공개(블로그·공유 자료) | `docs/conventions/publishing.md` | `CLAUDE.md` 운영 섹션 · `docs/README.md` 목차 · `docs/posts/README.md` · `.claude/agents/tech-writer.md`(포맷 프로파일·경계) · `docs/security.md`(반출 통제) |
| Claude Code 스킬 | `docs/skills.md` | `skills-lock.json`(등재·`computedHash`) · `.claude/agents/*.md` 프론트매터 `skills:`(프리로드는 **lock 등재분만**) · `.claude/agents/skill-matcher.md`(채점 루브릭) · `CLAUDE.md` 운영 섹션 |
| 에이전트 오케스트레이션·기록관 | `docs/conventions/agents.md` | `CLAUDE.md` 운영 섹션 · `docs/README.md` 목차 · `.claude/agents/*.md` · `.claude/commands/journal.md` · **`scripts/journal_guard.py`·`scripts/protected_paths_guard.py`·`scripts/session_sync_guard.py`·`scripts/analyst_path_guard.py`(← 배선처가 `settings.json`이 아니라 `.claude/agents/analyst.md` 프론트매터)·`scripts/worker_path_guard.py`(← 배선처가 `settings.json`이 아니라 `.claude/agents/{director,tech-writer,researcher,data-engineer,devops-engineer,archivist,data-extractor}.md` 프론트매터 — 🔴 **`BOUNDARIES`에 워커를 추가하면 그 워커 정의의 `hooks`도 함께 잇는다.** 2026-08-20까지 7종 중 3종이 미배선이라 **정의만 있고 실행된 적이 없었다**. 🔴 **`OUTSIDE_ALLOW`·`OUTSIDE_STRICT`(저장소 밖 경로)도 같은 규칙**이다 — `data-extractor`는 셋 다에 걸린다)·`.claude/settings.json`(기계 강제 가능한 규약은 hook·권한 규칙에 반영)·`.claude/settings.json`의 가드 스크립트 보호 규칙(`Edit(scripts/*_guard.py)`·`Edit(scripts/**/*_guard.py)`)·`docs/conventions/git.md`(커밋 대상·금지)·`.gitignore`** (저널 원문은 볼트 `$OBSIDIAN_VAULT/agents/`, repo 미커밋)<br/>🔴 **가드 배선을 바꿨으면 3셀 대조**(위반 2 + 대조군 1)로 실발동을 확인한다 — 프론트매터 `hooks`는 **정의 로드 시점 스냅샷**이라 편집한 세션의 음성 결과는 근거가 아니고 **새 세션에서** 돌린다(§실무 규칙 5). |

## 실무 규칙

1. **정본을 먼저 고치고**, 그 규칙을 요약·참조하는 문서를 뒤이어 맞춘다.
2. 코드·설정과 문서가 어긋나면 **코드/설정이 사실**이다. 문서를 코드에 맞춘다(반대 아님).
3. 새 규칙·결정은 근거(왜)와 함께 남긴다. 외부 표준은 [`references.md`](references.md)에 등록하고 링크한다.
4. 문서는 한국어로 쓰고, 코드 식별자·명령어·경로는 원문 그대로 표기한다.
5. 🔴 **체인에 항목을 추가하는 것과 그 항목이 집행되는지는 다른 축이다.** 가드·권한 규칙을 체인에
   넣을 때는 **어떻게 위반시켜 확인하는지**(위반 2 + 대조군 1의 3셀 대조)를 같은 행·문단에 함께
   적는다. 안 적으면 "설정은 넣었는데 실효가 없는" 상태가 조용히 남는다 — 2026-08-20까지 실측된
   계열이 이미 셋이다(존재하지 않는 hook 결정값 `escalate`·매칭기가 무시하는 `Write(<경로>)` 규칙·
   헤드리스 세션에서 판정 불가인 `cleanupPeriodDays`).

## 참고

- 문서화 원칙: 프로젝트 [`CLAUDE.md`](../CLAUDE.md) · 전역 규칙
- 외부 표준 인덱스: [`references.md`](references.md)
