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
  - **`.claude/settings.json`** — 프로젝트 공유 권한 게이트·hook 배선
    ([agents.md §권한 게이트](agents.md#권한-게이트-permissions--유일한-기계-강제)). 같은 `.claude/` 아래여도
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
- **AI 보조**: 병렬 에이전트는 각자 worktree에서 격리 작업한다(§6과 함께 적용).
  Claude Code 서브에이전트는 `isolation: worktree`로 임시 worktree를 자동 사용할 수 있다.

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
