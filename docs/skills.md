# Claude Code 스킬 (Agent Skills)

이 프로젝트가 의존하는 **Claude Code Agent Skills**(작업별 전문 지식·절차 묶음)와 사용 규칙을 정리한다.
**단일 출처는 저장소 루트 [`skills-lock.json`](../skills-lock.json)** 이며, 스킬 CLI(`npx skills`)가 설치·기록을 관리한다.

> 전역 규칙(`~/.claude/CLAUDE.md`) *Preferences #4* — **관련 스킬이 있으면 사용한다.**

스킬은 **세 축**으로 읽는다. 축을 섞으면 통제가 새므로 반드시 따로 본다.

| 축 | 값 | 무엇을 말하나 |
| --- | --- | --- |
| **고정** | 🔒 lock 등재 / ⚙️ lock 밖 / 🌐 런타임 제공(디스크에 없음) | **조용히 바뀔 수 있는가** |
| **출처 등급** | A 벤더 공식 / B 준벤더 / C 개인 / D 미상 | **누가 썼는가** (§출처 등급별 통제) |
| **설치 범위** | 전역(`~/.agents/skills/`) / 프로젝트(`<repo>/.agents/skills/`) | **클론에 따라오는가** |

> 🔴 **2026-08-21 — 앞의 두 축이 섞여 있었다.** 구 A등급이 *"lock 등재 + 해시 고정"* 으로 정의돼
> **개인 저장소 스킬을 lock에 넣기만 하면 C등급 통제를 우회**했다. 축을 갈랐다(§출처 등급별 통제).

> 🔴 **분류 정정(2026-08-19 실측)** — 이전 문서는 ⚙️를 "런타임 제공(Claude Code 환경이 제공)"으로 적었으나
> **사실이 아니다.** ⚙️도 대부분 **디스크에 실제 설치된 파일**이다. 즉 "환경이 주는 것"이
> 아니라 **"설치했는데 lock에만 없는 것"** 이다. 🌐만이 진짜 런타임 제공이다.

### 실측 (2026-08-21 01:14 KST)

🔴 **이 표는 스냅샷이다 — 관측 시각을 함께 읽는다.** 한 세션(약 40분) 안에
프로젝트 스코프가 **0→1→2→6**, lock이 **3→4→5→9**로 계속 변했다(사용자가 설치 중이었다).
수치만 옮기고 시각을 떼면 **낡은 값이 검산을 통과하며 남는다**([philosophy.md](philosophy.md) §계측 단위).
이 문서를 인용할 때는 **"어느 시각의 값인가"** 를 반드시 함께 옮긴다.

| 항목 | 값 | 함의 |
| --- | --- | --- |
| **고유 스킬 종수** | **26종** | 전역 24 + 프로젝트 6 − 중복 4 |
| **설치 슬롯 수** | **30** | 같은 스킬이 두 스코프에 있으면 2로 센다 |
| `~/.agents/skills/`(전역) | **24** | `~/.claude/skills/`는 여기로 향하는 **심볼릭 링크** |
| `.claude/skills/`(**프로젝트 스코프**) | **6** | 🔴 2026-08-19의 "없음"에서 바뀌었다(§프로젝트 스코프) |
| ↳ 그중 **전역과 중복** | **4** | `kubernetes-specialist`·`spark-engineer`·`spark-optimization`·`sql-optimization` |
| ↳ 프로젝트 **전용** | **2** | `brainstorming`·`multi-stage-dockerfile` |
| `skills-lock.json`(프로젝트) 등재 | **9** | 고유 26종 기준 **35%** |
| 스킬 CLI | PATH에 없음 | 설치는 `npx skills` 경유 — §관리 |
| **해시 재계산** | 🔴 **불가(`판정 불가`)** | 두 스키마 **모두** 재현 실패 — 아래 §해시 재계산 |
| **출처 미상(D등급)** | 🔴 **9종 → 0종** | 전역 lock으로 **전부 규명** — §출처 실측 |

🔴 **분모가 무엇을 세는지 함께 읽는다.** `26`은 **고유 종수**, `30`은 **설치 슬롯**이다.
둘 다 맞는 값이고 **세는 단위만 다르다** — 단위를 떼면 둘 다 오독된다.

#### 🔴 lock 파일은 **세 벌**이고 스키마는 **두 종류**다 (2026-08-21)

| 파일 | 항목 | 해시 필드 | 길이 | 부가 정보 | 커밋 |
| --- | --- | --- | --- | --- | --- |
| `<repo>/skills-lock.json` | **9** | `computedHash` | 64(SHA256 계열) | `skillPath` | ✅ 대상 |
| `~/.agents/.skill-lock.json` | **24** | `skillFolderHash` | **40(SHA1 계열)** | `sourceUrl`·`skillPath`·`installedAt`/`updatedAt` | ❌ 저장소 밖 |
| `$HOME/skills-lock.json` | **1** (`docker-expert`만) | `computedHash` | 64 | — | ❌ 저장소 밖 · **미아 파일** |

- ⚠️ **정정**: 이 문서가 앞서 전역 lock을 *"출처만 기록한다"* 고 적은 것은 **부정확**했다.
  `skillFolderHash`라는 **해시가 있다** — `computedHash` 키만 찾아보고 "없음"으로 읽은 것이다.
  **키 이름으로 존재를 판정하면 같은 함정을 반복한다**(가드의 `file_path`/`notebook_path` 사례와 같은 계열).
- `~/.agents/.skill-lock.json`이 **실질 레지스트리**다 — `sourceUrl`·설치 시각까지 있어 출처 추적의 정본이다.
- `$HOME/skills-lock.json`은 항목 1개짜리 **미아**다. 어느 CLI 실행이 홈 디렉터리를 프로젝트로 착각해
  만든 것으로 보인다(`판정 불가`). **정리 대상**이며, 남겨두면 다음 감사가 또 "세 번째 lock"을 발견한다.

🔴 **관측 경로가 하나뿐이면 부정 결과를 믿을 수 없다**(원칙 7). 2026-08-19의 "출처 미상 9종"은
`SKILL.md` frontmatter의 `metadata.author` **한 경로만** 본 결과였다. 같은 정보가
`~/.agents/.skill-lock.json`에 **처음부터 있었고**, 그 파일은 dotfile이라 `ls`·글롭에 걸리지 않았다.
**"없다"가 아니라 "안 봤다"** 였다 — 그래서 9종이 "출처 미상"으로 **C등급 통제를 받지 않았다**
(오분류 시점 2026-08-19, 설치 시점은 2026-02~03. 기간이 아니라 **통제 공백 자체**가 요지다).

- 따라서 **"lock을 커밋해 팀·CI가 동일 스킬 버전을 쓴다"는 재현성 주장은 9/26에만 성립**하고,
  그마저 §해시 재계산이 막혀 **"어디서 받아왔는지의 기록"까지**다.
- 배선·드리프트 감사는 **[`skill-matcher`](../.claude/agents/skill-matcher.md)** 워커가 담당한다(§③).

#### 🔴 해시 재계산은 불가능하다 — **두 스키마 모두** (2026-08-21 실측)

lock의 해시가 **무엇의 해시인지 모른다.** 두 스키마 각각에 후보를 대조했고 **전부 불일치**다.

| 스키마 | 대상 | 후보 알고리즘 | 결과 |
| --- | --- | --- | --- |
| `computedHash`(64) | `dagster-integrations` | `SKILL.md` sha256 / 전 파일 정렬연결 sha256 / frontmatter 제외 sha256 | **3종 전부 불일치** |
| `skillFolderHash`(40) | `sql-optimization` | `SKILL.md` sha1 / 전 파일 정렬연결 sha1 / `git hash-object` | **3종 전부 불일치** |

- 병렬 세션의 `skill-matcher`가 **독립적으로 같은 결론**에 도달했다(`tar --sort=name` 포함 5건 전부 실패).
  서로 다른 관측자·다른 후보 집합이 같은 결과를 냈으므로 **`판정 불가`는 우연이 아니다.**
- ⚠️ **이 사실을 모른 채 신규 스킬의 sha256 불일치를 봤다면 "변조"로 오진했을 것이다.**
  값 자체는 정확했고 **단위(무엇의 해시인가)만 어긋난** 계열이다 — 틀린 값보다 위험하다.
- 🔴 **따라서 lock 등재분을 "고정됨"으로 읽지 않는다.** 정확한 표현은
  **"고정을 주장하나 검증 불가"** 다. lock이 실제로 보장하는 것은
  **"CLI가 그 출처에서 받아왔다는 기록"** 까지이고, **받아온 뒤 로컬 파일이 바뀌지 않았음은 검증되지 않는다.**
- 🔴 파급 ①: §출처 등급별 통제의 *"해시를 기록하고 감사 시 재계산·대조"* 조항은 **죽은 규칙**이라 폐기했다.
- 🔴 파급 ②: 프리로드 조건 *"lock 등재 ∧ `security` 검토 완료"* 의 **첫 항이 실효를 주장할 수 없다.**
  현재 프리로드의 안전성은 **사실상 `security` 검토 하나에 의존**한다.
- **재대조 조건**: 스킬 CLI 확보 또는 해시 정규화 규칙(대상 파일 범위·프론트매터 포함 여부·개행 처리) 문서화.
  그 전까지 이 항목은 `판정 불가`이며, **"확인했더니 문제없었다"로 적지 않는다.**

## ① 잠긴 스킬 (skills-lock.json — 커밋·재현성)

| 스킬 | 출처 | 언제 쓰나 |
| --- | --- | --- |
| **dagster-expert** | `dagster-io/skills` (github) | Dagster·`dg` CLI 관련 모든 작업 — 프로젝트 구조 파악, 에셋/스케줄/센서/잡 정의·검색, 디버깅, 개념 질의 |
| **dagster-integrations** | `dagster-io/skills` (github) | `dagster-*` 통합 라이브러리 탐색·이해(S3·Iceberg·dbt·k8s 등 연동) |
| **dignified-python** | `dagster-io/skills` (github) | 범용 프로덕션 Python 표준(타입 문법·예외·pathlib 등). **본 프로젝트 컨벤션이 우선** — 아래 §충돌 규칙 |
| **sql-optimization** | `github/awesome-copilot` (B) | 범용 SQL 성능 튜닝(실행계획·인덱스·페이지네이션). ✅ **lock 등재로 출처가 규명**됐다 — 2026-08-19엔 D등급("출처 미상")이었다 |
| **multi-stage-dockerfile** | `github/awesome-copilot` (B) | 멀티스테이지 Dockerfile 작성. 문서 1파일·실행 파일 없음 |
| **kubernetes-specialist** | `jeffallan/claude-skills` (**C**) | K8s 워크로드·매니페스트. ✅ `security` 검토 완료 — **단서 필수**(§C등급 단서 표) |
| **spark-engineer** | `jeffallan/claude-skills` (**C**) | Spark 잡 작성·튜닝. ✅ 검토 완료(위험 패턴 0건) |
| **spark-optimization** | `wshobson/agents` (**C**) | Spark 성능 최적화. 🔴 **미검토** |
| **brainstorming** ❌ | `obra/superpowers` (**C**) | 구현 전 설계·기획 대화. 🔴 **`security` 판정 「거부」**(2026-08-21) — 개인 계정 × 실행 파일 1,432행. §brainstorming 판정 참조 |

> 🔴 **이 표를 "검증된 스킬 목록"으로 읽지 않는다.** 9건 중 **5건이 C등급**이고, `security` 검토를
> 통과한 것은 **A등급 3종 + `jeffallan` 2종뿐**이며 1종은 **거부**됐다.
> 해시는 **재계산·대조할 수 없어**(§해시 재계산) 무결성이 검증되지 않는다.
> 이 표가 말하는 것은 **"어디서 받아왔는지 기록이 있다"** 까지다.

> 🔴 **lock의 `skillPath`는 `SKILL.md` 한 장만 가리킨다** — `brainstorming`의 경우
> **실행 파일 1,432행(`scripts/**` 5종)은 이름조차 lock에 없다**(2026-08-21 `security` 실측 B-2).
> 즉 위험의 급소인 코드에 대해 🔒는 **무결성을 0% 보장**한다. *"🔒는 C등급을 면제하지 않는다"* 가
> 여기서 실증됐다 — 면제하지 않는 정도가 아니라 **덮는 범위가 애초에 문서 한 장**이다.

## ② 작업 유형별 스킬 매핑

이 프로젝트 스택에 대응하는 스킬. 🔒=잠긴 스킬(lock 등재), ⚙️=**잠기지 않은 스킬**(디스크 설치·lock 미고정),
🌐=**런타임 제공 스킬**(하네스 내장 — **디스크에 없다**).

🔴 **⚙️와 🌐를 가르는 이유 (2026-08-20 신설).** 둘 다 "lock 밖"이라 같은 칸에 묶여 있었으나
**워커가 쓸 수 있느냐가 정반대**다. 워커에는 `Skill` 도구가 없어 ⚙️는 `Read`로 `SKILL.md`를 직접
열어 쓰지만, 🌐는 **디스크에 파일 자체가 없어 `Read`도 불가**하다 → **워커 지시문에 적으면 죽은 참조**이고
**supervisor 세션에서만** 쓸 수 있다. `skill-matcher`가 `dataviz`를 "죽은 참조"로 올린 것(2026-08-20)이
계기였는데, 실제 원인은 **없어진 스킬이 아니라 분류 축이 하나 빠진 것**이었다 —
"디스크에 없다"를 "존재하지 않는다"로 읽으면 오진이다.

| 작업 영역 | 스킬 | 구분 |
| --- | --- | --- |
| Dagster 오케스트레이션·에셋 | `dagster-expert` · `dagster-integrations` | 🔒 |
| Python 코드 품질 | `dignified-python`(프로젝트 컨벤션 우선) | 🔒 |
| dbt 모델링·테스트·실행 | `using-dbt-for-analytics-engineering` · `adding-dbt-unit-test` · `running-dbt-commands` · `building-dbt-semantic-layer` · `troubleshooting-dbt-job-errors` · `fetching-dbt-docs` | ⚙️ |
| dbt 엔진·플랫폼 이행(저빈도) | `migrating-dbt-core-to-fusion` · `migrating-dbt-project-across-platforms` | ⚙️ **★3 이하** — 워커 지시문 미등재(§③ 임계) |
| dbt MCP 서버 설정 | `configuring-dbt-mcp-server` | ⚙️ **★3 이하** — 본 저장소는 dbt MCP 미사용 |
| Spark 배치·성능 튜닝 | `spark-engineer` · `spark-optimization` | 🔒 **(C등급)** — 둘 다 2026-08-21 lock 등재. 🔴 **전역/프로젝트 버전 상이**(§프로젝트 스코프) |
| SQL 성능 최적화 | `sql-optimization` | 🔒 — 전역·프로젝트 중복이나 **내용 동일** |
| Docker 이미지 빌드 | `multi-stage-dockerfile` | 🔒 **(2026-08-21 신규)** — [conventions/docker.md](conventions/docker.md) 태그 고정 규약이 스킬 예시보다 우선 |
| 설계·기획(구현 전 대화) | `brainstorming` | 🔒 ⚠️ **도입 미결** — C등급 × 실행 파일 × `security` 미검토. 아래 단서 |
| 분석·애드혹 질의 | `answering-natural-language-questions-with-dbt` · `duckdb` | ⚙️ |
| 차트·시각화(리포트 그림) | `dataviz` | 🌐 **워커 등재 불가** — 디스크에 없어 `Read` 불가. supervisor 전용 |
| 외부 1차 출처 확인(범용) | **전용 스킬 없음** → [.claude/agents/researcher.md](../.claude/agents/researcher.md) §출처 등급 | — |
| 기술 글쓰기·매체 포맷(공개물) | **전용 스킬 없음** → [conventions/publishing.md](conventions/publishing.md) | — |
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

#### ❌ `brainstorming` — `security` 판정 **「거부」** (2026-08-21)

**정본 집행 결과다.** §출처 등급별 통제 C등급 *"실행 파일 포함 시 도입 금지"* + 등급 무관 공통 조항 +
*"🔒는 C등급을 면제하지 않는다"* 의 조건이 **전부 성립**한다(개인 계정 · 실행 파일 5종 · lock 등재는 면제 아님).

**주요 발견**(8파일 2,030행 전수 정독 + 패턴 스윕 37종)

| # | 심각도 | 발견 |
| --- | --- | --- |
| B-1 | High | **무조건 커밋 지시** — `SKILL.md:210` *"Commit the design document to git"*, `:224`는 커밋을 기정사실로 통보하는 문구까지 제공. 아키텍처 경로의 **필수 단계 6번**이다. `dagster-expert`의 "no verification needed"와 같은 계열이나 **이쪽은 비가역 행위**라 더 무겁다 |
| B-2 | High | **lock이 실행 파일을 안 덮는다** — `skillPath`가 `SKILL.md` 하나. `scripts/**` 1,432행은 lock 밖 |
| B-3 | Medium | **미고지 텔레메트리 비콘** — `server.cjs:106,249` `primeradiant.com` 이미지를 **모든 화면**에 삽입. `SUPERPOWERS_DISABLE_TELEMETRY`로 꺼지는 것이 성격을 규정한다(로고가 아니라 **트래킹 픽셀**). ✅ `no-referrer`로 **세션 키는 새지 않는다**. 남는 것은 "브레인스토밍 중"이 제3자에 관측되고 **기본이 켜짐**이라는 점 |
| B-4 | Medium | **`BRAINSTORM_OPEN_CMD` → `child_process.exec`** — env 값이 셸에 그대로. `JSON.stringify(url)`은 큰따옴표라 `$(…)`·백틱이 **전개된다**. ✅ 대조: 다른 경로는 `execFile`(셸 없음)로 하딩돼 있어 **이 한 갈래만 의도적으로 열림** |
| B-6 | Medium | **세션 토큰을 매 턴 대화로 옮기라고 지시**(`visual-companion.md:116`) → 이 저장소는 대화를 **저널로 옮겨 적는다**. `kubernetes-specialist`의 `base64 -d` 단서와 동일 계열 |
| B-8 | Medium | **`.agents/`·`.claude/skills/`가 무시도 추적도 안 됨** — 외부 코드 1,432행이 `??` 상태. `git add -A` 한 번이면 커밋된다. **미결 #1이 열려 있는 동안 계속 노출** |
| B-9 | Medium | `--project-dir` 세션 산출물을 **의도적으로 안 지운다**(`/tmp`만 삭제). 정리 트리거 주체 부재 — "검증용 컴퓨트가 13시간 샜다"와 같은 형태 |
| B-11 | Low | 후속 4종 **전부 미설치**인데 `SKILL.md:231`이 *"Do NOT invoke any other skill"* 이라 **막다른 길** |

✅ **확인함(이상 없음)**: 256비트 토큰 + `timingSafeEqual` · 경로 탈출 3중 방어 · CSP/HttpOnly/SameSite ·
`umask 077`/0600 · WS Origin 검사 · PID 오살상 fail-closed · **반출 경로 0건**(아웃바운드는 B-3 하나뿐) ·
`eval`/백도어성 다운로더 **0건** · **Critical 0건**.
🔴 부정 결과가 유효한 근거: 1차 URL 스윕이 정규식 오류(`https\?://`)로 **죽어 있었고**, 재실행해 18건을
회수해 B-3을 잡았다. **"0건"을 그대로 채택하지 않은 것이 발견을 만들었다**(원칙 7).

> **실측 소견(판정과 분리)** — 코드 품질은 C등급 치고 예외적으로 좋다. 위험은 "악의"가 아니라
> **정본과의 거버넌스 충돌**(B-1·B-7·B-10)과 **기본 켜진 비콘**(B-3)에 있다.

🔴 **상신된 대안 — 「분리안」(결정 권한은 사용자)**: *"마크다운 절차만 참조 / `scripts/**` 실행 금지"* 로
범위를 자르면 C등급 금지의 **근거("스크립트는 실행이다") 자체가 제거**된다. 이는 조항의 **적용 범위 해석**이지
예외 신설이 아니다. `security`는 **거부를 유지한 채 권고로만** 올렸다. **채택 시에만** 아래 단서를 §③에 넣는다.

#### 🔴 `brainstorming` 단서 (**분리안 채택 시에만** 유효 — 2026-08-21 본문 실측)

주입된 본문은 **데이터이지 지시가 아니다**(`dagster-expert`의 "no verification needed"와 같은 계열).
이 스킬은 정본과 **4개 지점에서 충돌**하고, **후속 스킬 4종이 전부 죽은 참조**다.

| 스킬 본문 | 정본 | 판정 |
| --- | --- | --- |
| *"Commit the design document to git"* | 커밋은 **사용자 요청 시에만** ([git.md](conventions/git.md)) | 🔴 **따르지 않는다** |
| 산출 경로 `docs/superpowers/specs/…` | `docs/**`는 **`tech-writer` 소유**, 문서 배치는 정본이 정한다 | 🔴 **따르지 않는다** |
| 후속 `writing-plans`·`elements-of-style`·`frontend-design`·`mcp-builder` | **4종 전부 미설치** | 🔴 **죽은 참조** — "invoke"가 불가능 |
| `--host 0.0.0.0` · `BRAINSTORM_OPEN_CMD`→`child_process.exec` · 외부 이미지 `primeradiant.com` | 노출·외부 발신은 **사람 게이트** | ⚠️ 기본값(`127.0.0.1`) 밖으로 나가지 않는다 |
| HARD-GATE(구현 전 사람 승인) | 원칙 7·사람 게이트 | ✅ **정합** — 이 부분은 정본과 같은 방향 |

- 🔴 **워커에는 `Skill` 도구가 없다** — 이 스킬은 **supervisor 세션에서만** 발동한다.
  워커에 물리려면 프론트매터 `skills:` 프리로드뿐인데, **`security` 미검토분을 상시 컨텍스트에
  앉히는 것**이라 검토 전에는 하지 않는다(§③ 프리로드 규칙).

## ③ 전문 워커별 참고 스킬 (`.claude/agents/`)

각 전문 워커([conventions/agents.md](conventions/agents.md) §네이티브 구현)는 지시문에 **자기 작업에 해당하는 스킬만**
추려 담고, **이 문서를 정본으로 링크**한다. 스킬 목록을 워커 파일마다 복제하면 스킬 추가·제거 때 여러 곳이 드리프트한다.

**등재 기준은 별점(★)이다** — 워커×스킬을 5축 루브릭(스택 일치·권한 정합·정본 무충돌·호출 빈도·대체 불가)으로
채점해 **★4 이상만 등재**하고, ★3 이하는 등재하지 않는다. 축 2·3(권한·정본 충돌)이 0점이면 합계와 무관하게 제외한다.
🔴 **출처 신뢰성은 별점 축이 아니라 별개 게이트**다(별점에 섞으면 "★5인데 출처 불명"을 못 잡는다) — `security` 판정 대상.
루브릭 전문과 채점 매트릭스는 **[`skill-matcher`](../.claude/agents/skill-matcher.md)** 가 정본이며,
이 표는 그 결과 중 **등재분만** 옮긴 것이다.

🔴 **"등재"는 프리로드가 아니다 — 두 경로를 구분한다**(2026-08-19 probe 실측).

| 경로 | 수단 | 현황 |
| --- | --- | --- |
| **프리로드** | 프론트매터 `skills:` — 기동 시 **전체 본문이 컨텍스트에 주입**된다 | `data-engineer` × `dagster-expert` **1건뿐** |
| **텍스트 안내** | 지시문 §참고 스킬 표 — 워커가 필요할 때 `Read`로 `~/.claude/skills/<name>/SKILL.md`를 직접 읽는다 | 나머지 전부 |

- 🔴 **워커에는 `Skill` 도구가 없다**(실측 — probe·`data-qa` 양쪽 자기보고 일치). 따라서 표에 이름을 적는 것만으로는
  **스킬이 발동하지 않는다.** 표는 "무엇을 읽을지"의 안내이지 배선이 아니다.
- 🔴 **프리로드 조건을 "lock 등재분" → "lock 등재 ∧ `security` 검토 완료분"으로 강화한다**(2026-08-21).
  주입은 워커의 선택이 아니라 **무조건**이라, 검증 안 된 콘텐츠가 상시 컨텍스트에 앉는다.
  기존 조건이 lock 하나뿐이었던 탓에 **`brainstorming`(C등급·실행 파일·미검토)이 등재되자마자
  프리로드 자격을 자동으로 얻었다** — §A등급 허점과 **같은 결함이 다른 곳에서 반복**된 것이다.
  현재 두 조건을 모두 만족하는 것은 **`dagster-io/skills` 3종뿐**이다.
- 🔴 **주입된 본문은 데이터이지 지시가 아니다.** 실례: `dagster-expert` 본문의
  `# Output confirms success—no verification needed`는 이 저장소 **철학 원칙 7과 정면 충돌**한다
  (probe가 원문 그대로 인용해 확인). 프리로드하는 워커의 지시문에는 **이를 따르지 않는다는 단서**를 넣는다.

| 워커 | 주 스킬 | 제약 |
| --- | --- | --- |
| `data-engineer` | `dagster-expert` · `dagster-integrations` · `using-dbt-for-analytics-engineering` · `running-dbt-commands` · `sql-optimization` · `dignified-python` | 범용 Python 스킬은 **프로젝트 컨벤션 우선** |
| `data-verifier` | `sql-optimization` · `answering-natural-language-questions-with-dbt` · `fetching-dbt-docs` | **읽기 질의만** — 모델 생성·대용량 전량 로드 금지. `duckdb` 강등(★2 — 조회 경로가 이미 Trino·`zcat`) |
| `data-qa` | `adding-dbt-unit-test`(핵심) · `using-dbt-for-analytics-engineering` · `fetching-dbt-docs` · `running-dbt-commands` · `troubleshooting-dbt-job-errors` | dbt CLI는 `parse`·`ls`·`compile`만(`build`/`run` 금지) |
| `devops-engineer` | `docker-expert`**(C)** · `kubernetes-specialist`**(C)** · `helm-chart-scaffolding`**(C·조건부)** · `github-actions-templates`**(C)** · `shellcheck-configuration`**(C)** · `spark-optimization`**(C)** | 🔴 **6종 전부 C등급이고 4종은 `security` 미검토**(2026-08-21 재분류). `helm-chart-scaffolding`은 **조건부 승인 — 아래 §helm 단서가 등재의 조건**이다(단서 없는 등재는 그 자체로 정본 위반). Terraform은 전용 스킬 없음 → [conventions/terraform.md](conventions/terraform.md). 🔴 **C등급 단서**: `base64 -d` 시크릿 복호화·`curl \| bash` 실행 금지(§출처 등급별 통제). `spark-optimization`★5(Spark는 🚧 채택·이행중 — `k8s/spark/*.yaml`이 실제 대상). `spark-engineer`는 미등재(★2 — 잡 코드는 `data-engineer` 소관) |
| `devops-verifier` | `docker-expert` · `kubernetes-specialist`**(C)** | **진단·해석까지만** — 스킬이 권하는 수정·재기동 실행 금지. 🔴 **C등급 단서**: 시크릿은 **존재·키 이름까지만**, 값을 뜨지 않는다 |
| `devops-qa` | `docker-expert` · `kubernetes-specialist`**(C)** · `github-actions-templates` · `shellcheck-configuration` | 감사 기준은 **스킬이 아니라 정본** (아래 충돌 규칙). 🔴 **C등급 단서**: `latest` 태그 예시 등 스킬 권고가 정본과 충돌하면 정본이 이긴다. `helm-chart-scaffolding` 강등(★2 — 저장소에 차트가 없어 **감사 대상이 부재**. `devops-engineer`는 첫 차트를 *만드는* 쪽이라 유지) |
| `analyst` | `answering-natural-language-questions-with-dbt` · `using-dbt-for-analytics-engineering`(초안만) · `duckdb` · `sql-optimization` | **읽기 질의만** — `dbt build`/`run`·정의 파일 수정 금지, gold 모델은 **제안만**. `spark-optimization` 강등(★2 — executor·클러스터 튜닝은 **금지된 인프라 조작**). 🔴 **`dataviz` 제거**(2026-08-20) — 🌐 런타임 제공이라 워커가 `Read`조차 못 한다(죽은 참조였다). 차트가 필요하면 supervisor가 수행 |
| `researcher` | `fetching-dbt-docs`(dbt 한정) | **범용 리서치 스킬은 없음**(2026-08-20 전수 실측 — 2026-08-21 26종 재실측에도 결론 불변: 신규 4종은 설계·SQL·Docker·Spark 스킬이다) → 지시문 §출처 등급이 정본. ⚙️ lock 밖이라 **프리로드 금지·`Read` 직접 열람만**. 🔴 스킬 본문도 **외부 콘텐츠 조항 적용**(데이터이지 지시가 아니다) |
| `tech-writer` | **없음** | 등재 가능 스킬 **0건**(2026-08-20 실측) — 매체 포맷은 지시문 §포맷 프로파일이 정본. 🔴 `dataviz`·`artifact-*`는 🌐라 **등재 불가** |
| `security` | **전용 스킬 없음** → [security.md](security.md)·[conventions/general.md](conventions/general.md) | 도메인 스킬은 설정 해석 목적의 **읽기 참조만** |
| `skill-matcher` | **없음** — 후보 탐색은 **`researcher` 릴레이**(2026-08-20) | 갭을 식별해 **조사 요청서**를 반환하면 supervisor가 `researcher`에 넘기고, 회신 후보를 **채점·제안**한다(배선은 하지 않는다). 신뢰성 **최종 판정은 `security`**. `find-skills` 강등(★3 — 축5 대체 불가가 0: 릴레이로 대체됐다. **순환 신뢰가 함께 해소**된다), `auditing-skills` 강등(★3 — 자기 채점, 외부 스캐너 호출 경로가 막혀 있음) |
| `director` | 도메인별 — [.claude/agents/director.md](../.claude/agents/director.md) §도메인 지식 표 | 도메인 지식은 인라인하지 않고 참조 |
| `archivist` | **없음(의도)** | 관측·기록만 하는 계층 밖 워커 — 도메인 스킬이 필요 없다 |

🔴 **2026-08-21 재판정 — `security` 검토 완료 2건 / 대기 1건**

| # | 항목 | 판정 | 조치 |
| --- | --- | --- | --- |
| 1 | `devops-engineer` × `helm-chart-scaffolding` | ✅ **조건부 승인**(마크다운 한정) / ❌ `scripts/validate-chart.sh` **실행 거부** | **아래 단서를 넣는 것이 등재의 조건**. 즉시 제외는 불필요 — 급소가 스크립트 2줄에 응집돼 있고, 저장소에 차트가 **0건**이라 아직 발동 대상이 없다 |
| 2 | `director` × `brainstorming` | ❌ **거부**(§brainstorming 판정) | **등재하지 않는다.** 「분리안」이 승인되면 §단서와 함께 재검토 |
| 3 | `data-engineer`·`analyst` × `sql-optimization` | — | 등재 자체는 유효(두 벌 **내용 동일**). ★ 재채점은 `skill-matcher` 소관 |

##### 🔴 `helm-chart-scaffolding` 단서 (등재의 **조건** — 2026-08-21 `security`)

```
🔴 `scripts/validate-chart.sh` 실행 금지 — :108이 `helm install`(비가역 목록, 이 워커는 계획만 반환)을
   돌리고 `.claude/settings.json`에 helm install 게이트가 없어 스크립트 이름 뒤로 통과한다.
   검증은 `helm lint`·`helm template`만 직접 실행한다.
🔴 helm v4의 `--dry-run`은 불리언이 아니라 기본값이 `none`(=실제 반영)인 문자열 플래그다(실측 v4.2.0)
   — 반드시 값을 붙여 `--dry-run=client`로 쓴다. 무값형에 의존하지 않는다.
🔴 helm 명령에는 `--kube-context`·`--namespace`를 항상 명시한다 — 미지정 시 현재 컨텍스트를 그대로 탄다.
🔴 렌더 결과를 통째로 출력하지 않는다 — `helm template`·`--debug` 출력은 렌더된 Secret 평문을 포함한다
   (helm 공식 경고, `--hide-secret` 사용). 문제 지점은 validate-chart.sh:101이다.
🔴 `password: changeme` 예시(SKILL.md:297·assets/values.yaml.template:156)를 그대로 옮기지 않는다.
🔴 무태그 이미지 예시(`image: busybox`)는 따르지 않는다 — docker.md 태그 고정 규약이 이긴다.
🔴 `aws s3 sync … s3://`(SKILL.md:362)·`helm package` 배포는 외부 발신이다 — 실행하지 않는다.
🔴 `k8s-manifest-generator`·`gitops-workflow`(SKILL.md:559-560)는 미설치 죽은 참조다.
```

- 🔴 **H-1의 급소는 결과가 아니라 구조**다 — 현 helm 버전에서 실제 설치는 일어나지 않지만,
  *"검증 스크립트"라는 이름 뒤에 게이트 없는 비가역 명령이 의미론이 바뀐 플래그 하나에 의지해* 들어 있다.
  **`deny` 패턴은 선두 앵커**라 스크립트 안의 명령을 매처가 **원리상 보지 못한다**(하네스가 보는 것은 파일명 한 토큰).
- ✅ **확인함**: 셸 인젝션 0건 · 네트워크 다운로드 0건 · 비밀 하드코딩 0건 · 저장소 오염 경로 0건.
  보안 기본값 권고(`runAsNonRoot`·`drop: ALL`·`seccompProfile`)는 **정본과 같은 방향**이고 스크립트가 이를 감사한다.

✅ **별건 해소 — 권한 규칙 갭**(`security` O-3): 2026-08-21 `ask` 규칙 **10종 추가**.
🔴 **갭은 helm보다 넓었다** — `CLAUDE.md`가 *"`ask`로 못 박는다"* 고 명시한 비가역 작업 중
**`kubectl apply`·`terraform apply`·`terraform destroy`에는 규칙이 아예 없었다**(감사로 발견).
`git push`·`DROP`·`.env` 등은 있었으므로, **선언 목록과 구현 목록을 대조한 적이 없었던 것**이다.

추가분: `*helm install*`·`*helm upgrade*`·`*helm uninstall*`·`*helm delete*`·`*helm rollback*`·
`*helm dependency update*`·`*kubectl apply*`·`*kubectl delete*`·`*terraform apply*`·`*terraform destroy*`.
전부 **앞뒤 `*`로 두른다** — `Bash(helm install*)` 형태는 선두 앵커라 `bash -c '…'`·`cd chart && helm …`를 놓친다.

##### 🔴 `ask` 규칙은 auto 모드에서 **검증할 수 없다** (2026-08-21 실측)

규약대로 변형 3개로 재위반했는데 **전부 통과**했고, 원인을 가르는 데 실험 설계가 한 번 틀렸다.

| 셀 | 명령 | 규칙 | 결과 |
| --- | --- | --- | --- |
| 1 | `helm install --help` | 신규 `ask` | **통과** |
| 2 (대조) | `git commit --help` | **기존** `ask`(세션 시작 전부터 존재) | **통과** |
| 3 (판별) | `helm install --help` | **임시 `deny`** | 🔴 **차단** |
| 4 | `bash -c 'helm install --help'` | 임시 `deny` | 🔴 **차단** |
| 5 | `cd /tmp && helm install --help` | 임시 `deny` | 🔴 **차단** |
| 6 (과차단) | `helm version --short` | — | ✅ 통과 |

- **셀 2가 결정적이었다** — 기존 규칙도 통과했으므로 "내 새 규칙이 틀렸다"·"세션이 설정을 안 읽는다"가 **둘 다 기각**된다.
- 셀 3이 변인 하나(`ask`→`deny`)만 바꿔 차단됐으므로 **`permissions`는 세션 도중 반영된다**
  (🔴 **`hooks`와 반대다** — hooks는 정의 로드 시점 스냅샷이라 새 세션이 필요하다. **둘을 같이 묶어 기억하면 틀린다**).
- 따라서 셀 1·2의 통과는 **auto 모드 분류기가 `ask`를 흡수한 것**이다.
- 🔴 **내 시험 설계가 틀렸다** — 안전하려고 `--help`를 골랐는데, **그 안전함이 바로 분류기가 삼키는 조건**이었다.
  `ask`를 무해한 프로브로 검증하려는 시도는 **원리상 성립하지 않는다**: 프로브가 위험해야 프롬프트가 뜨고,
  위험하면 실행할 수 없다. **`ask`의 실효는 `deny` 임시 전환으로만 간접 확인된다.**
- 🔴 **남는 결론**: 위 10종은 **분류기가 그 호출을 위험하다고 볼 때** 사람에게 올라온다.
  규칙이 있다는 사실이 **"반드시 멈춘다"를 뜻하지 않는다** — 멈추는 것은 규칙과 분류기의 **곱**이다.
- 앵커링(변형 2·3)은 `deny` 하에서 **3/3 차단 · 과차단 0**으로 확인됐으므로, 패턴 자체는 유효하다.

⚠️ **위 결론은 한 방향으로 과했다 — 도구 축에 따라 갈린다**(2026-08-21 병렬 세션 보완 실측, 사용자 확인).

| 축 | 관측 | 함의 |
| --- | --- | --- |
| **`Bash` + 실제 위험 호출** | `git push origin main` → **프롬프트 떴음** ✅ | `ask`는 **죽은 규칙이 아니다**. 진짜 위험한 호출은 올라온다 |
| **`Bash` + 무해 호출** | `helm install --help`·`git commit --help` → 흡수 | 내 프로브가 여기 속했다 |
| 🔴 **파일 도구(`Edit`/`Write`)** | `docs/conventions/**`·`.claude/agents/**`·**`.env.*`** 쓰기 → **3/3 안 뜸** | **경로 민감도와 무관하게 흡수**된다 |

- 🔴 **급소는 "경로가 민감한가"가 아니라 "어느 도구인가"다.** `.env` 계열조차 흡수됐다.
  → **파일 경로 경계를 확실히 막으려면 `ask`가 아니라 `deny`여야 한다.**
- 🔴 이 관측은 **`escalate` 죽은 규칙·`Write(<경로>)` 죽은 규칙과 같은 계열**이고 **이번이 더 조용하다** —
  에러 배너조차 없다. 기존 기록의 *"4종 전부 확인 프롬프트 발동을 확인했다"* 는 **auto 모드가 아닌 조건**의
  관측이었고, 조건을 안 적으면 **"항상 막힌다"로 읽힌다.**
- **출처 구분**: `Bash` 축 6셀은 이 세션의 직접 실측, **파일 도구 축 4셀은 병렬 세션 관측**(사용자가 프롬프트
  발생 여부를 직접 확인). 재현이 필요하면 새 세션에서 `deny` 전환 대조로 다시 돌린다.

- 위 3건은 **`skill-matcher` 채점(5축 루브릭) 대상**이며 이 표는 결과를 옮기는 곳이다.
  등급·검토 상태는 별점 축이 아니라 **별개 게이트**(`security`)라, ★4 이상이어도 미검토면 등재하지 않는다.

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

- **추가/갱신**: 스킬 CLI로 설치하면 lock에 source·`computedHash`가 기록된다(수동 편집 금지).
  CLI는 **PATH에 없고 `npx skills` 경유**로 돈다 — 즉 로컬 명령이 아니라 **네트워크 접촉**이다
  (설치 행위 자체가 §외부 발신 규율의 대상).
  ⚠️ 2026-08-19 문서는 이를 "절차 실행 불가"로 적었으나 **틀렸다** — 2026-08-21 실제로 설치가 돌았다.
  "PATH에 없다"를 "쓸 수 없다"로 읽은 오독이다.
- 🔴 **lock은 두 벌이고 성격이 다르다.**

  | 파일 | 범위 | 등재 | `computedHash` | 커밋 |
  | --- | --- | --- | --- | --- |
  | `skills-lock.json` | 저장소(프로젝트 스코프) | 5 | **있음**(단 재계산 불가) | ✅ 대상 |
  | `~/.agents/.skill-lock.json` | 홈(전역) | 24 | **없음** | ❌ 저장소 밖 |

  전역 lock은 **출처만** 기록한다. 그래서 재현성에는 기여하지 않지만 **출처 규명에는 결정적**이고,
  실제로 D등급 9종을 전부 해소했다(§출처 실측).
- **감사**: 외부 스킬은 도입 전 내용을 검토한다(보안·품질). 판정은 아래 **§출처 등급별 통제**를 따른다.
- **재현성**: `skills-lock.json`은 **커밋**해 팀·CI가 동일 스킬 버전을 쓰게 한다.
  🔴 단 **락이 "진실의 출처"인 범위는 출처·버전까지**다 — 무결성은 §해시 재계산이 막혀 있어 검증되지 않는다.
- **배선 감사 주기**: 스킬 추가·제거 후, 워커 신설·개편 시 **[`skill-matcher`](../.claude/agents/skill-matcher.md)** 를 배정한다.

### 출처 등급별 통제 (2026-08-19 개정)

> **왜 바꿨나** — 이전 조항은 "신뢰 출처(`dagster-io/skills`)만 사용한다"였는데, 실측상
> **24개 중 21개가 이 조항을 위반**하는 상태였다. 전원이 위반하는 규칙은 규칙이 아니다.
> 개인 저장소 2종만 떼어내 금지하는 것도 **위험 감소 없이 형식만 맞추는 것**이라
> `security` 판정([미션 13](../.claude/agents/skill-matcher.md))에서 **등급별 통제로의 개정**이 상신됐다.
> 급소는 "출처가 개인이냐"가 아니라 **"고정되지 않아 조용히 바뀔 수 있느냐"** 다.

> 🔴 **재개정 (2026-08-21) — 등급은 "출처"만 판정한다. lock 등재는 등급이 아니다.**
> 기존 A등급 정의(*"lock 등재 + `computedHash` 고정"*)는 **두 개의 다른 축을 한 칸에 섞었다**:
> ⓐ 출처가 믿을 만한가 ⓑ 조용히 바뀔 수 있는가. 그 결과 **개인 저장소 스킬을 lock에 넣기만 하면
> C등급 통제("실행 파일 포함 시 도입 금지")를 건너뛰고 "제한 없이 사용"으로 자동 승격**된다.
> 2026-08-21 실제로 그 경로가 발생했다 — `brainstorming`(`obra/superpowers`, 개인 계정, 실행 파일 4종)이
> lock에 등재됐다. **lock은 "안 바뀜"을 보장하지 "안전함"을 보장하지 않는다.**
> 그래서 축을 갈라 **출처 등급(A~C) × 고정 상태(🔒/⚙️)** 2차원으로 읽는다.

| 등급 | 정의 | 통제 | 현재(26종) |
| --- | --- | --- | --- |
| **A · 도구 벤더 공식** | 그 스킬이 다루는 **도구 자체의 벤더** | 제한 없이 사용 | `dagster-io/skills` **3** |
| **B · 준벤더·플랫폼 조직** | 벤더 조직이되 해당 도구의 벤더는 아님 | 사용 가능. **lock 편입 검토**, 실행 파일 포함 시 `security` 검토 | `dbt-labs` **11** · `github`·`vercel-labs` **2** |
| **C · 개인·커뮤니티** | 개인 GitHub 계정 | 🔴 도입 전 **`security` 본문 검토 필수** + 워커 지시문 **단서 문구 필수**. **실행 파일 포함 시 도입 금지** | **9** (§출처 실측) |
| **D · 출처 미상** | 어느 lock에도 출처가 없음 | 실행 파일 포함이면 **검토 전 사용 금지**, 문서 전용이면 **관찰** | ✅ **0** (전부 규명) |

**고정 상태는 별개 축이다** — 🔒 lock 등재(출처·버전 기록) / ⚙️ lock 밖.
🔴 **🔒는 C등급을 면제하지 않는다.** `brainstorming`·`sql-optimization`은 🔒이면서 C다.

**등급 무관 공통 조항**
- 🔴 **실행 파일을 포함한 스킬은 등급과 무관하게 `security` 검토 대상**이다 —
  마크다운은 제안이지만 스크립트는 **실행**이다. 현재 해당 **3종**(2026-08-21 전수 스캔):

  | 스킬 | 등급 | 실행 파일 | 상태 |
  | --- | --- | --- | --- |
  | `fetching-dbt-docs` | B | `scripts/search-dbt-docs.sh` | 기존 인지 |
  | `helm-chart-scaffolding` | **C**(← D에서 재분류) | `scripts/validate-chart.sh` | 🔴 **C + 실행 파일 = 도입 금지 대상인데 `devops-engineer`에 등재 중** — §③ 충돌 |
  | `brainstorming` | **C** | `server.cjs`·`helper.js`·`start-server.sh`·`stop-server.sh` | 🔴 **`security` 미검토**. §① 참고 |

- 🔴 **해시 미고정 스킬은 "오늘 안전"이 "내일 안전"을 보장하지 않는다.** lock 밖 스킬은 조용히 바뀌어도
  탐지 수단이 없고, **에러 없이 그냥 최신을 쓴다**([philosophy.md](philosophy.md) 원칙 7 "성공 신호를 의심한다" 계열).
  ⚠️ **이전 판의 대안 조항("해시를 기록하고 감사 시 재계산·대조")은 폐기한다** — §해시 재계산에서
  알고리즘이 `미확인`으로 확인돼 **실행 불가한 죽은 규칙**이었다. 대체 수단은 아직 없다(`미해결`).
- **C·D 등급 스킬을 워커에 등재할 때는 §③ 표의 제약 칸에 단서를 명시**한다(무해화 문구가 없으면 등재하지 않는다).

**`security` 검토를 마친 C등급 2종의 단서**(2026-08-19 실측 — 8,989행 스캔 결과 인젝션·반출·비밀노출 유도 **0건**, 단 아래 패턴 존재)

🔴 **이 표는 C등급 9종 중 2종만 덮는다** — 나머지 7종은 2026-08-19에 D("출처 미상")로 분류돼
**C등급 통제를 한 번도 받지 않았다**(§출처 실측 재분류). 미검토분은 그 표의 "검토 상태" 칸에 있다.

| 스킬 | 위치 | 패턴 | 단서 |
| --- | --- | --- | --- |
| `kubernetes-specialist` | `references/troubleshooting.md:96` | 시크릿 평문 복호화(`base64 -d`)를 **표준 절차로 안내** | 🔴 **실행 금지** — 진단은 값이 아니라 **존재·키 이름까지만**. 값을 뜨면 트랜스크립트·저널에 박제된다 |
| `kubernetes-specialist` | `references/multi-cluster.md:151` | `curl -Ls … \| bash` | 🔴 실행 금지 — 설치는 `security` 컨펌 + 사용자 승인 경로로만 |
| `kubernetes-specialist` | `references/configuration.md:74,137,271` | 평문 비밀 예시(`db-password: "…"`) | philosophy #4 위반 패턴 — **예시를 그대로 옮기지 않는다** |
| `kubernetes-specialist` | `references/helm-charts.md:453` | `image: curlimages/curl:latest` | [docker.md](conventions/docker.md) 태그 고정 규약이 이긴다 |
| `spark-engineer` | — | 위험 패턴 **0건** | — |

### 출처 실측 (2026-08-21 01:14 KST) — 고유 26종 전수 · **전면 개정**

> 🔴 **개정 사유 — "출처 미상 9종"은 사실이 아니었다.**
> 2026-08-19 실측은 `SKILL.md` frontmatter의 `metadata.author` **한 경로만** 봤다. 같은 정보가
> **`~/.agents/.skill-lock.json`(전역 lock)에 처음부터 있었고**, 그 파일은 dotfile이라
> `ls ~/.agents/`·`cat ~/.agents/*.json` 어느 쪽에도 걸리지 않았다.
> **"출처가 없다"가 아니라 "출처를 안 봤다"** 였다 — 부정 결과를 낼 때는 **관측 경로가 살아 있었는지**를
> 함께 확인해야 한다([philosophy.md](philosophy.md) 원칙 7). 그 9종은 그동안 **C등급 통제를 받지 않았다.**

| 등급 | 출처 | 종수 | 스킬 | 🔒 | 검토 상태 |
| --- | --- | --- | --- | --- | --- |
| **A** | `dagster-io/skills` | **3** | `dagster-expert`·`dagster-integrations`·`dignified-python` | 🔒 | ✅ |
| **B** | `dbt-labs/dbt-agent-skills` | **11** | dbt 계열 10종 + **`auditing-skills`**(← D에서 재분류) | ⚙️ | lock 편입 검토 대상 |
| **B** | `github/awesome-copilot` | **2** | `sql-optimization` · `multi-stage-dockerfile` | 🔒 | — |
| **B** | `vercel-labs/skills` | **1** | `find-skills` | ⚙️ | — |
| **C** | `wshobson/agents` | **4** | `github-actions-templates`·**`helm-chart-scaffolding`**·`shellcheck-configuration`·`spark-optimization` | 일부 🔒 | 🔴 **미검토** |
| **C** | `jeffallan/claude-skills` | **2** | `kubernetes-specialist`·`spark-engineer` | 🔒 | ✅ 검토 완료(위 단서 표) |
| **C** | `sickn33/antigravity-awesome-skills` | **1** | `docker-expert` | ⚙️ | 🔴 **미검토** |
| **C** | `silvainfm/claude-skills` | **1** | `duckdb` | ⚙️ | 🔴 **미검토** |
| **C** | `obra/superpowers` | **1** | `brainstorming` | 🔒 | 🔴 **미검토 · 실행 파일 4종** |
| **D** | — | **0** | — | — | ✅ 전부 규명 |

- **합계 26종** = A 3 + B 14 + C 9. 설치 **슬롯**으로는 30(전역 24 + 프로젝트 6, 중복 4).
- 🔴 **lock 등재(🔒)가 C등급에도 붙었다** — `kubernetes-specialist`·`spark-engineer`·`spark-optimization`·
  `brainstorming`이 2026-08-21에 프로젝트 lock에 들어왔다. **9건 중 5건이 C등급**이다.
  이것이 §A등급 허점의 규모다 — 예외 하나가 아니라 **lock의 과반이 그 경로로 들어왔다.**
- 🔴 **C등급이 2종 → 9종으로 늘었다.** 규칙이 바뀐 게 아니라 **보이지 않던 7종이 드러난 것**이다.
  그중 **`helm-chart-scaffolding`은 C + 실행 파일**이라 정본상 **도입 금지 대상**인데
  현재 `devops-engineer`에 등재돼 있다 → §③ 재판정 필요.
- ⚙️ **무결성 고정은 어느 등급에서도 실효가 없다** — 🔒 5종조차 §해시 재계산이 막혀 있다.

#### 프로젝트 스코프 스킬 (`.claude/skills/`) — 2026-08-21 신설

2026-08-19 실측의 *"프로젝트 스코프: 없음 — 스킬은 전부 전역"* 은 **더 이상 참이 아니다.**

| 스킬 | 전역에도 있나 | 두 벌 비교 | git |
| --- | --- | --- | --- |
| `brainstorming` | ❌ 프로젝트 전용 | — | untracked |
| `multi-stage-dockerfile` | ❌ 프로젝트 전용 | — | untracked |
| `sql-optimization` | ✅ 중복 | **동일**(트리 전체) | untracked |
| `kubernetes-specialist` | ✅ 중복 | 🔴 **상이** — 프로젝트가 +2행(문서 링크) | untracked |
| `spark-engineer` | ✅ 중복 | 🔴 **상이** — 프로젝트가 +2행(문서 링크) | untracked |
| `spark-optimization` | ✅ 중복 | 🔴 **상이** — 전역 411행 1파일 / 프로젝트 95행 + `references/details.md` 321행 | untracked |

- `.claude/skills/<name>` → `../../.agents/skills/<name>` **상대 심볼릭 링크**다(전역과 같은 구조).
- 🔴 **중복 4종 중 3종이 실제로 다르다 — 이것은 중복이 아니라 버전 드리프트다.**
  전역은 2026-02~03 설치분, 프로젝트는 2026-08-21 설치분이다(전역 lock `installedAt` 대조).
  즉 **프로젝트 쪽이 신판**이고, `spark-optimization`은 본문을 `references/`로 분리한
  **progressive disclosure 재구성**이다(411행 → 95+321행, 내용은 보존).
- 🔴 **어느 쪽이 로드되는지는 `판정 불가`**이고, 이제 그 답이 **실제로 갈린다.**

  | 경로 | 무엇을 읽나 | 결과 |
  | --- | --- | --- |
  | 세션 스킬 로드(`Skill` 도구) | 스코프 우선순위 `판정 불가` | 신판/구판 미상 |
  | **워커 `Read`**(§③ 안내) | `~/.claude/skills/<name>/SKILL.md` = **전역 = 구판** | 🔴 **확정적으로 구판을 읽는다** |

  → **워커는 구판을, 세션은 미상판을 볼 수 있다.** 같은 스킬 이름이 **읽는 주체에 따라 다른 내용**을
  가리키는 상태이며, 어느 쪽도 에러를 내지 않는다(원칙 7 "실패가 실패로 안 보인다" 계열).
- ✅ `.gitignore`에 **`.superpowers`** 등재(2026-08-21) — `brainstorming` 서버가 `--project-dir` 사용 시
  저장소 안에 세션 파일·**세션 토큰**을 만든다. 게이트 검증: 처리군 4/4 차단 · 대조군 5/5 통과(과차단 0,
  접두어 트랩 `superpowers.md`·`docs/superpowers-notes.md` 포함).

##### 중복 4종 해소 계획 (2026-08-21 · **실행은 사용자 승인 후**)

> 🔴 **이 계획은 한 번 뒤집혔다.** 초안은 *"프로젝트 사본을 지우고 전역으로 폴백"* 이었고,
> 근거는 **"두 벌이 바이트 동일이라 동작 무변화"** 였다. 그 전제가 **`sql-optimization` 한 종만
> 보고 세운 것**이었고, 나머지 3종을 `diff -r`로 확인하자 **전부 달랐다**.
> 프로젝트 쪽이 **신판**이므로 초안대로 지웠으면 **조용히 구판으로 되돌리는** 작업이 됐을 것이다.
> — 표본 하나로 세운 전제는 전수 확인 전까지 결론이 아니다([philosophy.md](philosophy.md) 원칙 7).

| 안 | 조치 | 영향 | 평가 |
| --- | --- | --- | --- |
| **A(권장)** | **전역을 최신으로 재설치**해 두 벌을 같게 만든다 | 워커 `Read` 경로(전역) 유지 + 신판 확보. 중복 자체는 남지만 **드리프트가 사라져 무해**해진다 | ★★★★★ |
| B | 프로젝트 사본 제거 | 🔴 **구판으로 되돌아간다**(3종). 초안이었으나 실측으로 기각 | ★☆☆☆☆ |
| C | 전역 사본 제거 + 워커 참조 경로를 프로젝트로 변경 | 근본적이나 지시문 4종 + 정본 수정, **미결 #1(커밋 여부)이 먼저 정해져야** 한다 | ★★★☆☆ |
| D | 유지 + 드리프트 감시 | 비용 0이나 **감시 주체가 없다**. 이미 드리프트가 발생한 상태 | ★☆☆☆☆ |

- **A 실행**(네트워크 접촉 — 승인 후): 전역 스코프에서 `kubernetes-specialist`·`spark-engineer`·
  `spark-optimization` 3종을 재설치한다. `sql-optimization`은 이미 동일하다.
- **선행 확인**: 재설치 후 `diff -r ~/.agents/skills/<n> .agents/skills/<n>`로 **4종 전부 무차이**를 확인한다.
- 🔴 **C안이 진짜 해법이지만 미결 #1에 묶여 있다** — 프로젝트 스코프를 정본으로 삼으려면
  `.agents/`가 **커밋돼야** 하고(안 그러면 클론에 안 따라온다), 그건 외부 코드를 저장소에 넣는 결정이다.
  A안은 그 결정이 날 때까지의 **완충재**이지 종착점이 아니다.
- `$HOME/skills-lock.json`(1항목 미아 파일)도 같이 정리 대상이다.

- 🔴 **미결 2건**(사용자 결정 대기):
  1. `.agents/`·`.claude/skills/` **커밋 여부** — 커밋하면 프로젝트 스킬이 클론에 따라와 재현성이 오르지만,
     **외부 코드가 저장소에 들어온다**. `skills-lock.json`만 커밋하는 현행과 어느 쪽이 정본인지 결정 필요.
     🔴 이 결정이 나기 전까지 **프로젝트 스코프는 재현성에 기여하지 않는다**(위 A안의 근거).
  2. `brainstorming` **도입 가부** — C등급 × 실행 파일 × `security` 검토 진행 중(2026-08-21 배정).

- 🔴 **설치 경로는 심볼릭 링크다** — `~/.claude/skills/<name>` → `~/.agents/skills/<name>`.
  한쪽 형태에만 규칙을 걸면 **죽은 규칙**이 되므로 `.claude/settings.json`의 `ask`에
  `**/…`·`~/…`·상대형 **3형태를 병기**했다(도구층 글롭 의미론이 `미확인`이라 하나를 고르지 않는다).
- 🔴 **1차 검증은 편향돼 있었다(2026-08-19 `security` 반려).** 테스트 payload가 전부 `~`·절대경로여서
  **상대경로를 한 건도 보지 않았고**, 그 결과 `protected_paths_guard.py`의 선두 `**/`가 후행 `/`를
  리터럴로 남겨 `.claude/skills/x`를 **원리상 못 잡는 것**을 놓쳤다. 같은 버그로
  `terraform/**/*.tfstate*`가 `terraform/foo.tfstate`를 놓치고 있었다.
  **반려 원인은 코드가 아니라 테스트 집합의 편향**이었다 — [philosophy.md](philosophy.md) 원칙 7.
  → 이후 5형태로 확장했으나 **그 매트릭스에도 빠진 형태가 있었다**(병렬 세션이 자기 가드를 같은
  매트릭스로 시험하다 발견해 통지). 최종 **6형태**로 다시 확장했다:

  | # | 형태 | 예 | 왜 필요한가 |
  | --- | --- | --- | --- |
  | 1 | 상대 | `.claude/skills/x` | 선두 `**/`가 후행 `/`를 리터럴로 남김 |
  | 2 | 절대 | `/Users/…/.agents/skills/x` | resolve된 심볼릭 링크 실체 |
  | 3 | 틸드 | `~/.claude/skills/x` | 선언 그대로의 형태 |
  | 4 | **셸 변수** | `$CLAUDE_PROJECT_DIR/.claude/agents/x` | 토큰 정규식이 `$`를 제외해 `VAR/경로`로 남아 **앵커된 패턴에 안 걸림** |
  | 5 | 디렉터리형 | `tar -C ~/.claude/skills` | 대상이 디렉터리 자체면 `/**` 뒷부분이 비어 실패 |
  | 6 | **상위 디렉터리** | `tar -C .claude` | 부모에 풀면 보호 대상이 생성·덮어쓰기됨 |

  최종 검증: **위반 23종 전부 차단 / 대조군 20종 전부 통과**(과차단 0).
  대조군에는 `README.md`·`docs/`·`dbt/models/`·`scripts/` 쓰기와 `git checkout main`·
  `cd terraform && terraform fmt` 같은 **일상 명령**을 넣어 과차단을 측정했다.
  🔴 경로 규칙이나 매칭 로직을 바꾸면 **이 6형태 매트릭스를 통째로 다시 돌린다.**
- ✅ 부수 확인: `security`가 "가드로는 못 막을 수 있다"고 본 **토큰 쪼개기**
  (`cd ~/.claude/skills && cat > evil/SKILL.md`·`D=~/…; echo x > $D/…`)는
  **디렉터리형·접미어 전개 수정으로 함께 막혔다** — 별도 대응이 필요 없었다.
- **`security` 검토 대기열 (2026-08-21 개정 — 구 "D등급 우선순위")**
  D등급이 사라져 목록의 **근거가 "출처 미상"에서 "C등급 미검토"로 바뀌었다**. 우선순위는 공격면 기준:

  | 순위 | 스킬 | 등급 | 사유 |
  | --- | --- | --- | --- |
  | ✅ | `brainstorming` | C | **검토 완료(2026-08-21) → 「거부」**. 「분리안」 상신 중 |
  | ✅ | `helm-chart-scaffolding` | C | **검토 완료(2026-08-21) → 「조건부 승인」**(마크다운 한정, 스크립트 실행 거부) |
  | 2 | `docker-expert`·`github-actions-templates` | C | 크리덴셜을 다루는 산출물을 생성 |
  | 3 | `shellcheck-configuration`·`spark-optimization`·`duckdb` | C | 문서 전용 — 관찰 |
  | — | `auditing-skills` | **B**(← D) | ✅ **강등 해소** — dbt-labs 벤더 공식으로 밝혀졌다. 단 `skill-matcher`가 로드하면 **순환 신뢰**는 그대로라 등재 판단은 별개 |
  | — | `find-skills` | **B**(← D) | ✅ `vercel-labs`로 규명. 2026-08-20에 이미 대기열에서 빠졌다(후보 탐색이 `researcher` 릴레이로 이동 — 🔴 **검토가 끝나서가 아니라 경로가 사라져서**) |
- **재채점 대상**(축1·4 의심, `skill-matcher` 첫 미션): `analyst`의 `spark-optimization`(읽기 질의 워커에 튜닝 스킬),
  `data-verifier`의 `duckdb`(조회 엔진은 Trino).

## 참고

- Claude Code Skills 문서: https://docs.claude.com/en/docs/claude-code/skills
- 설치 출처(2026-08-21 전역 lock 실측):
  - A `dagster-io/skills` — https://github.com/dagster-io/skills
  - B `dbt-labs/dbt-agent-skills` · `github/awesome-copilot` · `vercel-labs/skills`
  - C `wshobson/agents` · `jeffallan/claude-skills` · `sickn33/antigravity-awesome-skills` ·
    `silvainfm/claude-skills` · `obra/superpowers`
- 🔴 **URL은 [references.md](references.md)에 단일 관리**한다 — 위 목록은 *어느 저장소에서 받았는가*의
  실측 기록이지 참고 링크 카탈로그가 아니다. 워커 지시문은 이 목록을 복제하지 않는다.
