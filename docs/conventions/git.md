# Git 워크플로 규칙

> **범위**: 이 문서는 **작업 흐름**(브랜치·커밋 단위·세션 협업)을 다룬다. 세션마다 반복되는 git 작업의
> **일관성** 확보가 목적이다.
> 커밋 메시지 규약(Conventional Commits)·릴리스/태그·pre-commit·비밀정보의 **단일 출처는 [general.md](general.md)** 이며,
> 여기서는 중복 없이 링크한다.

## 1. 브랜치 전략

- **`main` = 배포·릴리스 기준.** 태그·릴리스는 `main`에서만 만든다([general.md](general.md#릴리스--태그)).
- **피처 브랜치 우선**: 다중 파일·기능·리스크 있는 변경은 브랜치에서 작업한 뒤 병합한다.
  - 브랜치명 `<type>/<kebab-요약>` (type은 커밋 type과 동일 계열): `feat/oci-k3s-terraform`, `fix/iceberg-orphan`, `docs/git-convention`.
- **`main` 직접 커밋**은 오타·문서 소폭 등 **사소·저위험**에 한정한다.

## 2. 커밋 단위 — 논리적으로 쪼갠다

- **한 커밋 = 한 관심사.** 서로 다른 type(`feat`/`fix`/`docs`/`refactor`)을 한 커밋에 섞지 않는다.
- 기능과 **그 기능 전용 문서**는 함께 커밋해도 되지만, 무관한 변경은 분리한다.
- 리뷰·`revert` 용이성을 위해 큰 변경은 **의미 단위**로 나눈다.
- 스테이징은 경로 단위로 고른다(`git add <path>`). 이 저장소는 **대화형 플래그(`-i`/`-p`)를 쓰지 않으므로**,
  헝크 분리가 필요하면 **파일이 여러 관심사를 담지 않게 작성**해 파일 단위로 커밋을 설계한다.

## 3. 커밋 메시지

- **Conventional Commits** `type(scope): 설명`(한국어, 72자). 상세·type 표·기존 type 매핑은
  [general.md](general.md#커밋-메시지-conventional-commits). gitlint `commit-msg` 훅으로 강제된다.

## 4. 커밋 전 게이트 (pre-commit)

- 커밋 시 pre-commit이 `ruff`·`yamllint`·`gitleaks`·`gitlint` 등을 자동 실행한다([general.md](general.md#실행-pre-commit)).
- 훅 실패는 **수정 후 재커밋**한다. 우회(`--no-verify`)는 원칙적으로 금지(불가피하면 사유를 커밋 본문에 남긴다).

## 5. 커밋 금지 / 커밋 대상

- **커밋 금지**(비밀·상태·아티팩트):
  - `.env`·크리덴셜([general.md](general.md#비밀정보-secrets)),
  - Terraform `*.tfstate`·`terraform.tfvars`·API 개인키·`kubeconfig-oci`([terraform.md](terraform.md)),
  - 원천 진료 데이터([../security.md](../security.md)).
  - `.gitignore`로 강제하고, 예시는 `*.example`만 커밋한다.
  - **`.claude/settings.local.json`** — 세션 중 승인한 `allow` 누적(개인 설정).
- **커밋 대상**(재현성): 락 파일 — `.terraform.lock.hcl`·`skills-lock.json`.
  - ⚠️ **`uv.lock`은 예외로 커밋하지 않는다.** 락 파일을 커밋하는 이유는 **재현성**인데,
    이 저장소에서 `uv.lock`은 그 값을 주지 않는다 — 이미지 빌드가 `pip install -e`를 쓰고 락을
    참조하지 않으며, 루트 `pyproject.toml`은 `[project]`가 없는 **도구 설정 전용**이라 루트 락에는
    잠기는 의존성이 0개다. "락 파일이니 커밋" 규칙을 기계적으로 적용하지 않는다.
  - **`.claude/settings.json`** — 프로젝트 공유 권한 게이트·hook 배선
    ([agents.md §권한 게이트](agents.md#권한-게이트-permissions--기계-강제층)). 같은 `.claude/` 아래여도
    `settings.local.json`과 정책이 **반대**이므로 글롭으로 묶지 않는다.

## 6. AI 보조 세션에서의 git (Claude Code)

- **커밋·푸시는 사용자가 요청할 때만** 수행한다(임의 커밋·푸시 금지).
- 어시스턴트가 만든 커밋은 **`Co-Authored-By` 트레일러**를 남긴다(`Co-Authored-By: Claude ... <noreply@anthropic.com>`).
- **되돌리기 어려운 작업**(force push·history 재작성·브랜치/태그 삭제)은 **사전 확인** 후 진행한다.
- 세션 간 인계는 코드가 아니라 **문서·커밋 메시지**로 남긴다(추적성 — [philosophy.md](../philosophy.md)).

## 7. 병렬 세션 — git worktree (충돌 회피)

여러 세션/에이전트가 동시에 작업하면 **하나의 워킹트리·인덱스를 공유**해 충돌·오염이 발생한다.
**git worktree**로 브랜치마다 **독립 디렉터리**를 두어 물리적으로 격리한다(같은 저장소·공유 `.git`, 워킹트리만 분리).

- **원칙**: **세션/작업 = 브랜치 = worktree** 1:1:1. 각 세션은 자기 worktree에서만 작업한다.
- 한 브랜치는 **한 worktree에만** 체크아웃 가능하다 → 중복 작업이 자연스럽게 차단된다(암묵적 lock).
- 기본 명령:

  ```bash
  git worktree add ../<repo>-<branch> -b <type>/<요약>   # 새 브랜치+디렉터리 생성
  git worktree list                                      # 현황 확인
  git worktree remove <path>                             # 작업 종료 후 제거
  git worktree prune                                     # 잔여 메타 정리
  ```

- **이점**: 세션 간 working tree 충돌 0, `stash`/브랜치 스위치 불필요, 빌드·캐시 분리.
- **주의**: 디스크 사용↑. `.env`·`.venv` 등 **비커밋 파일은 worktree마다 별도 준비**한다(공유되지 않음).
  → 이 준비를 자동화한 것이 **`scripts/worktree-new.sh`** 다(아래 "도입 절차"). 맨손으로 `worktree add`만
  하면 **피어 감지가 조용히 꺼진다** — 반드시 스크립트를 쓰거나 아래 링크 목록을 직접 잇는다.
- **AI 보조**: 병렬 에이전트는 각자 worktree에서 격리 작업한다(§6과 함께 적용).
  Claude Code 서브에이전트는 `isolation: worktree`로 임시 worktree를 자동 사용할 수 있다.

### 왜 지켜지지 않는가 (2026-08-18 실측)

규칙이 있어도 **세션은 그냥 저장소 루트에서 시작**한다. 이 날 4개 세션이 전부 main 워킹트리에서
돌았고, 다음 증상이 나왔다.

| 증상 | 실제로 일어난 일 |
| --- | --- |
| **커밋 분리 불가** | `docs/conventions/agents.md` 한 파일에 4개 미션의 변경이 218줄 섞임 → §2("한 커밋 = 한 관심사")를 지킬 수 없음. `-i`/`-p` 미사용 규약이라 헝크 분리 경로도 없음 |
| **인덱스 경합** | 한 세션이 `git add` 해둔 것을 다른 세션이 `git status`에서 자기 것으로 오인 |
| **같은 파일 동시 생성** | `.claude/settings.json`을 두 세션이 각자 만듦(권한 게이트 / hook 배선). 겹치지 않아 무사했으나 **우연**이다 |
| **브랜치 전환 불가** | 다른 세션이 같은 트리를 쓰는 중이라 `git switch`가 그들의 발밑을 흔든다 → main 직접 커밋 외 선택지가 없어짐(§1 위반) |

**규칙**:

- **세션 시작 시 `git worktree list`로 자기 위치를 확인**한다. main 워킹트리에 다른 세션이 있으면
  자기 worktree를 만들고 옮긴다 — 작업을 시작한 **뒤에는 늦다**(옮기려면 워킹트리를 건드려야 하고,
  그 순간 다른 세션의 변경이 위험해진다).
- **이미 섞여버렸다면 브랜치를 옮기지 말고**, 관심사별로 나눠 커밋한 뒤 정리한다. 되돌리기 전에
  `git stash create` + `git update-ref refs/backup/<이름>`으로 **워킹트리를 건드리지 않는 스냅샷**을
  떠둔다(`stash push`와 달리 작업 내용이 되돌아가지 않는다).
- 🔴 **공유 트리에서는 `git commit -- <경로…>`로 pathspec을 못 박는다**(2026-08-19 사고 후 신설).
  인덱스는 세션 간 **공유 자원**이라, 내가 `git add` 한 것만 인덱스에 있다는 보장이 없다.
  pathspec을 주면 커밋 대상이 **명령 안에서 확정**되고 다른 세션의 스테이징분이 딸려갈 수 없다.
  ```bash
  git commit -- docs/skills.md .claude/agents/skill-matcher.md   # ✅ 대상이 명령에 박힌다
  git add <내 파일> && git commit                                  # ❌ 인덱스의 남의 것까지 간다
  ```
- 공유 트리에서 불가피하게 커밋할 때는 **스테이징 후 `git diff --cached --stat`으로 내 파일만
  올라갔는지 반드시 확인**한다. pre-commit이 미스테이징 변경을 임시 stash·복원하므로, 그 과정이
  정상이었는지도 커밋 직후 `git status`로 본다.
  🔴 **다만 확인만으로는 부족하다** — 확인과 커밋 사이에 **다른 세션이 스테이징할 창(window)** 이 남는다.
  실제로 `git status` 확인 후 커밋했는데 그 사이 스테이징된 남의 파일 2개가 실려 나갔다(`a95af44`).
  **확인은 창을 좁히고 pathspec은 창을 없앤다** — 둘 다 한다.

### 도입 절차 — `scripts/worktree-new.sh` (2026-08-19 신설)

`git worktree add`는 한 줄이다. 실제 마찰은 **gitignore된 자산이 새 worktree에 없다**는 것이고,
그 준비를 사람이 매번 기억해야 하면 규칙은 조용히 샌다. 그래서 배선을 스크립트에 박았다.

```bash
./scripts/worktree-new.sh <type>/<kebab-요약> [--venv]
# 예: ./scripts/worktree-new.sh feat/spark-thrift-poc --venv
```

하는 일: 브랜치명 규약(§1) 검사 → `worktree add` → **비커밋 자산 심볼릭 링크** →
(옵션) `uv sync` + `dbt deps`.

#### 🔴 발견 ① — worktree는 피어 감지를 **조용히 끈다** (링크로 해결)

세션 충돌 감지(`session_sync_guard.py`)의 레지스트리는 `$CLAUDE_PROJECT_DIR/.claude/.claims`다.
worktree마다 `CLAUDE_PROJECT_DIR`가 다르므로 **레지스트리도 worktree마다 따로 생기고,
모든 세션이 서로를 "나 혼자"로 본다.** 에러는 나지 않는다 — 그냥 경고가 안 뜬다.

이게 위험한 이유는 **worktree가 격리하는 것과 가드가 지키는 것이 다르기 때문**이다.
worktree는 **파일·인덱스**를 격리하지만 **클러스터·컨테이너·DB는 격리하지 못한다**.
가드에 최근 추가된 `SHARED_INFRA_RE`(kubectl·helm·compose)가 정확히 그 영역을 본다.
즉 **파일 충돌을 없애려고 도입한 격리가, 파일로는 못 막는 충돌의 감지를 끄는** 형국이다.

→ 해법은 가드 수정이 아니라 **레지스트리를 링크로 공유**하는 것이다.
`Path.resolve()`가 링크를 따라가므로 가드의 `/.claude/.claims/` 매칭도 그대로 성립한다.

**실측(2026-08-19, 3셀 대조)** — 동일 페이로드(`git stash list`)로 `CLAUDE_PROJECT_DIR`만 바꿔 실행:

| 셀 | `CLAUDE_PROJECT_DIR` | 결과 |
| --- | --- | --- |
| A 처리군 | 메인 트리 | 피어 **4개** 감지 |
| B 처리군 | worktree(`.claims` 링크) | 피어 **4개** 감지 — A와 동일 |
| C **대조군** | 빈 디렉터리(`.claims` 없음) | **출력 0** |

> C가 이 검증의 핵심이다. A·B만 봤다면 "링크가 먹었다"와 "가드가 원래 항상 경고한다"를
> 갈라내지 못한다. **관측 경로가 살아 있는 것과, 그 관측이 경쟁 가설을 분리하는 것은 다르다.**
>
> 🔴 **단 "4개"라는 절대 수치는 신뢰하지 마라 — 실세션은 3개였다.** 나머지 둘은 **합성 페이로드
> 테스트가 만든 가짜 엔트리**다(아래 참고). 이 검증이 주장하는 것은 A=B와 C=0이라는 **비교**이지
> 개수가 아니다. 수치를 그대로 인용하면 없는 세션을 있다고 적게 된다.

#### 🔴 주의 — 이 가드는 **합성 페이로드로 테스트하면 실제 상태를 바꾼다**

`session_sync_guard.py`의 `main()`은 **어떤 서브커맨드든 먼저 `touch_session()`을 부른다.**
따라서 `session_id`를 지어내 stdin으로 넣으면 그 가짜 세션이 **레지스트리에 실제로 등록**되고,
이후 관측에서 살아 있는 피어로 잡힌다(2026-08-19에 두 세션이 각각 하나씩 오염시켰고,
그 결과가 위 표의 "4개"다). **읽기 전용 검사가 아니다.**
테스트 후에는 `.claude/.claims/sessions/<접두>.json`을 지운다(TTL 90분이라 두면 빠지긴 한다).

#### 🔴 대가 — 레지스트리 공유는 **git 축에 오탐**을 만든다

`live_sessions()`는 `session_ref`로만 거르고 **`cwd`로 거르지 않는다.** 그래서 링크로 레지스트리를
공유하면 축마다 결과가 갈린다.

| 축 | 링크 공유 후 | 판정 |
| --- | --- | --- |
| 공유 인프라(kubectl·helm·compose) | 다른 worktree 세션도 카운트 | ✅ **정확** — 클러스터는 worktree로 격리되지 않는다(이 링크의 존재 이유) |
| 서브에이전트 중복 | 다른 worktree도 카운트 | ✅ 정확 — 같은 일을 두 번 하는 것은 트리와 무관 |
| 동일 파일 동시편집 | `resolve()`가 worktree별 실경로라 교차 감지 안 됨 | ✅ 정확 — 파일은 실제로 격리됐다 |
| **워킹트리 전역 git**(`switch`·`stash`·`reset`) | 다른 worktree 세션까지 카운트 | ❌ **오탐** |

마지막이 문제다. 경고 문구가 문자 그대로 *"이 워킹트리를 쓰는 다른 세션이 N개"* 인데,
worktree A의 `git switch`는 worktree B의 HEAD를 움직이지 않는다 — **worktree 도입으로 해소된
바로 그 위험에 대해 계속 확인을 올린다.** 그리고 이건 소음 이상이다: **안 뜰 때 안심하는 것이
위험한 만큼, 항상 뜨면 무시하는 법을 배운다.** 같은 채널로 나오는 인프라 축 진짜 경고의
신호 대 잡음비가 깎인다.

→ 해법은 `live_sessions()`가 `cwd`를 받아 **git 축만 같은 `cwd`로 필터**하고 인프라 축은
전체를 유지하는 것이다(claim에 `cwd`가 이미 기록돼 있다). 가드 소관 세션이 처리한다.
**그 필터가 들어가기 전까지 worktree 사용 시 git 축 경고는 오탐일 수 있다고 읽는다.**

링크로 공유하는 자산은 셋이다 — `.env`(비밀정보 사본을 늘리지 않는다)·
`.claude/.claims`(위 이유)·`.claude/settings.local.json`(권한이 갈라지면 worktree마다
프롬프트가 달라진다). `.claude/settings.json`·`agents/`·`commands/`는 **커밋 대상**이라 자동으로 따라온다.

#### 🔴 발견 ② — `.venv`는 링크하면 **반쪽 격리**가 된다

venv에는 editable 설치(`_editable_impl_dagster_project.pth`)가 들어 있어 **메인 트리의 소스**를
가리킨다. 링크하면 dbt SQL·문서는 격리되는데 **파이썬 코드는 메인 트리 것이 도는** 상태가 되고,
이건 "격리했다"고 믿는 쪽이 더 위험하다. 그래서 **링크하지 않고 `uv sync`** 한다(실측 **1.2GB**).
비용이 크므로 문서·SQL만 만지는 작업이면 `--venv`를 생략한다(스크립트 기본값이 생략이다).

#### 부수 발견 ③ — `.gitignore`의 **끝 슬래시**가 링크를 놓친다

`.claude/.claims/`처럼 **슬래시로 끝나는 패턴은 디렉터리만** 매칭한다. worktree에서 이 경로는
메인 트리를 가리키는 **심볼릭 링크(=파일 취급)** 라 무시되지 않고 `??`로 잡히고,
그 결과 `git worktree remove`가 *"contains modified or untracked files"* 로 **거부**한다.
→ 루트 `.gitignore`를 **슬래시 없는 `.claude/.claims`** 로 바꿨다(디렉터리·링크 양쪽을 덮는다).
`.env`·`settings.local.json`은 원래 슬래시가 없어 문제가 없었다 — **`.claims`만** 걸렸다.

> 검증도 대조로 했다: 수정된 패턴을 `core.excludesFile`로 주입하면 링크가 무시되고(`check-ignore` 적중),
> 기존 패턴만으로는 무시되지 않아 **원래 증상이 그대로 재현**된다.

정리 시 `--force`가 필요하면 붙여도 된다 — **`--force`는 링크 자체만 끊고 원본을 지우지 않는다**
(제거 후 `.env` 44줄·`claims` 세션 5개·`settings.local.json` 전부 무사함을 실측했다).

#### 한계 — 이미 시작한 세션은 옮길 수 없다

`CLAUDE_PROJECT_DIR`는 세션 시작 시 고정되므로 **실행 중인 세션은 자기 worktree로 이주하지 못한다.**
따라서 이 도입은 **다음 세션부터** 효력이 있고, 지금 main 트리를 공유 중인 세션들에는
**pathspec 의무(위)가 계속 유일한 방어선**이다. 둘은 대체 관계가 아니라 **시간축이 다른 방어**다.

### 사고 사례 — 인덱스 교차 오염 (2026-08-19)

| 항목 | 내용 |
| --- | --- |
| 증상 | 스킬 배선 감사 커밋(`a95af44`)에 **타 세션의 Spark Operator 자원 한도 변경 2파일**이 섞임 |
| 원인 | `git add <내 7개>` 후 `git commit` — 인덱스에 남아 있던 타 세션 스테이징분까지 커밋 |
| 유실 | **없음**(내용은 정확히 들어감). 문제는 **귀속** — 커밋 메시지가 다른 미션이라 작업 주체가 어긋남 |
| 복구 | **하지 않음.** 조율 중 상대가 그 위에 커밋해 `HEAD~1`이 됐고, **살아 있는 세션이 공유하는 `main`에서 2단계 되감기는 위험 대비 이득이 없다**. 양측 합의로 **후속 커밋 본문·저널에 귀속을 정정**하는 쪽을 택했다 |
| 교훈 | 이건 **부주의가 아니라 구조의 결함**이다 — 세 세션이 하나의 인덱스를 공유하는 한 확인은 언제나 늦을 수 있다. 근본 해법은 §7의 **worktree 분리**이고, pathspec 의무화는 그때까지의 완충재다 |

> **"중단"과 "삭제"의 분리처럼, 여기서도 "되돌림"과 "정정"을 분리한다** — 히스토리를 되감는 것만이
> 정정이 아니다. 내용이 정확하고 유실이 없다면 **기록으로 귀속을 바로잡는 편이 위험이 낮다.**

## 8. 세션 표준 흐름

```bash
git switch main && git pull                    # 1) 최신화
git worktree add ../repo-<요약> -b <type>/<요약>   # 2) 격리 worktree+브랜치 (또는 git switch -c)
# 3) 작업 → 논리 단위로 스테이징·커밋
git add <path> && git commit                   # (pre-commit·gitlint 통과)
git push -u origin <branch>                     # 4) push → PR/머지 → main에서 태그·릴리스
git worktree remove ../repo-<요약>              # 5) 정리
```

## 참고

- Conventional Commits: https://www.conventionalcommits.org/
- Pro Git (한국어): https://git-scm.com/book/ko/v2
- pre-commit: https://pre-commit.com/
