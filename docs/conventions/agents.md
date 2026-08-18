# 에이전트 오케스트레이션·기록관 규약 (agents)

AI 세션에서 작업을 **3계층(supervisor → director → subagent)** 으로 나누고, "누가 무엇을
왜 했는가"를 **기록관(archivist) 저널**로 마크다운에 남기는 규약이다. 이 문서가 규약의 **정본**이며,
요약은 [`CLAUDE.md`](../../CLAUDE.md) 운영 섹션에 둔다.

> 원칙: **단순함(YAGNI)** — 계층·기록관은 필요할 때만 늘린다. **추적 용이성** — 결정과 근거(왜)를
> 남겨 나중에 grep/점프 가능하게 한다. **있었던 일만 기록** — 하지 않은 활동은 남기지 않는다.

## 구조도 (한눈에)

> 출처는 서술이 아니라 **실측**이다 — 워커 목록·권한은 `.claude/agents/*.md`의 `tools` 프론트매터에서 세웠다.

```mermaid
flowchart TB
    U([사용자])
    SUP[supervisor · 메인 루프<br/>미션 정의·성공조건<br/>취합·충돌조정·사용자 보고]
    DIR[director · 조율자<br/>하위작업 분해<br/>배정·감독]

    subgraph impl[워커 · 구현 · 쓰기]
        DE[data-engineer]
        OE[devops-engineer]
    end

    subgraph judge[워커 · 판정 · 읽기 전용]
        DV[data-verifier]
        OV[devops-verifier]
        DQ[data-qa]
        OQ[devops-qa]
    end

    GP[general-purpose<br/>그 외 조사·잡무]

    SEC[security · 최종 컨펌 게이트<br/>계층 밖 · 읽기 전용]
    ARC[archivist · 기록 전담<br/>계층 밖 · 판단하지 않음]

    subgraph rec[기록 · 볼트]
        JR[(저널<br/>agents/날짜/NN-미션.md)]
        MOC[(_MOC 대시보드)]
    end

    HOOK{{journal_guard hook<br/>NN 경합 차단}}

    U -->|요청·결정| SUP
    SUP -->|배정| DIR
    SUP -->|배정| SEC
    SUP -->|배정| ARC
    SUP -.->|계층 접기 · YAGNI| impl
    SUP -.->|계층 접기 · YAGNI| judge
    DIR -->|배정·감독| impl
    DIR -->|배정·감독| judge
    DIR -->|배정| GP
    impl -->|산출물 반환| DIR
    judge -->|발견 반환| DIR
    DIR -.->|승인·반려| impl
    DIR -.->|승인·반려| judge
    DIR -->|컨펌 요청| SEC
    SEC -->|승인·반려| DIR
    DIR -->|결과 요약 보고| SUP
    DIR -.->|에스컬레이션 질의| SUP
    SUP -->|승인·반려| DIR
    SUP -->|체크포인트 이벤트 전달| ARC
    ARC -->|기록| JR
    ARC -->|감사·유지| MOC
    SUP -.->|폴백 기록| JR
    HOOK -.->|번호 발급·중복 차단| JR
```

- **하향**(배정·승인)과 **상향**(보고·에스컬레이션)이 서로 다른 경로다. 상향의 판단 주체는 항상 **상위**다.
- 점선 `supervisor ⇢ 워커`는 **계층 접기**다. 미션이 작으면 director 없이 직접 배정한다(YAGNI).
  **2026-08-18 21:0x 실측**(당시 저널 14건) 기준 전부 이 경로였고 director 배정은 **0회**였다.
  같은 날 구조도 검증 미션에서 **최초로 실제 배정**됐다 — 수치는 반드시 시점과 함께 읽어라.
  도입 판단 기준은 §역할 계층 참조.
- 워커는 **서로를 배정하지 못한다**. 워커→워커 화살표가 없는 것이 규약이다.
- **`security`·`archivist`는 director 관할 밖**이다 — 배정 주체는 supervisor다.
  director는 `security`에게 **허가하지 않고 컨펌을 요청**하며, 그 판정에 **구속**된다(§security 최종 컨펌).
- `archivist`는 **모든 결정·액션의 기록 주체**다(§기록 주체). `journal_guard`는 넘버링 경합만 막는다.

### 워커 배치 — 도메인 × 축

축(구현 / 실측 대조 / 체계 감사)은 두 도메인이 **동일**하다. 판단 규칙을 하나로 유지하기 위함이다.

| 축 | 데이터 | 인프라 | 무엇을 묻는가 |
| --- | --- | --- | --- |
| **구현·수정** | `data-engineer` | `devops-engineer` | 만들었는가 |
| **실측 대조** | `data-verifier` | `devops-verifier` | 실제가 선언과 같은가 |
| **체계 감사** | `data-qa` | `devops-qa` | 재발을 막을 상시 장치가 있는가 |
| **노출·규제**(도메인 공통) | `security` | `security` | 새어나가는가 · 규제를 지키는가 |
| **관측·기록**(계층 밖) | `archivist` | `archivist` | 기록이 사실과 맞는가 |

- `security`(노출·규제) ↔ `devops-qa`(운영 신뢰성·재현성)는 **관점이 다르다** — 중첩 금지.
- `archivist`는 **계층 밖 관측자**다. 판단·실행을 하지 않고 저널·MOC 정합만 본다.

### 권한 매트릭스 (실측)

| 에이전트 | `tools` (프론트매터 실측) | 쓰기 | 비가역 작업 |
| --- | --- | --- | --- |
| `director` | **미지정 = All tools** | O | 워커에 **계획만** 받게 하고 승인 후 실행 배정 |
| `data-engineer`·`devops-engineer` | `Read, Write, Edit, Bash, Grep, Glob` | O | **계획만 반환**(커밋·`apply`·`down -v` 금지) |
| `data-verifier`·`devops-verifier`·`data-qa`·`devops-qa`·`security` | `Read, Grep, Glob, Bash` | ✕(규율) | 발견만 반환 — 수정은 `*-engineer`에 재배정 |
| `archivist` | `Read, Write, Edit, Grep, Glob, Bash` | O(저널·MOC **한정**) | 없음 |
| `general-purpose`(내장) | **`*` = All tools** (정의 파일 없음·런타임 제공) | O | 제약을 **정의 파일로 못박을 수 없다** → 배정 프롬프트에 명시할 것 |

> ⚠️ **"읽기 전용"은 도구가 아니라 지시문이 보장한다.** 판정자 5종에도 `Bash`가 있어 도구 수준에서는
> 파일 변경이 막히지 않는다(`Write`·`Edit` 미부여로 **난이도만** 올렸다). 경계 지시문과 저널 기록은
> **규율**이지 강제가 아니다. 기계가 강제하는 층은 **권한 규칙** 하나뿐이다(아래 §권한 게이트).
>
> `general-purpose`는 **정의 파일조차 없어** 경계를 붙일 자리가 없다 — 위 논증이 아예 통하지 않는다.
> 맞는 전문 워커가 있으면 그쪽을 쓰고, 불가피하게 쓸 때는 **배정 프롬프트에 제약을 명시**한다.

### 권한 게이트 (permissions) — 유일한 기계 강제

통제는 3층이고, **아래로 갈수록 강하다.** 위 두 층만 믿으면 안 된다.

| 층 | 수단 | 성격 | 우회 가능성 |
| --- | --- | --- | --- |
| 1 | 프론트매터 `tools` | 도구 **미부여** | `Bash`가 있으면 사실상 무력 |
| 2 | 경계 지시문·승인 게이트 | **규율**(프롬프트) | 모델이 따르지 않으면 끝 |
| 3 | **`permissions` 규칙** | **결정적 강제** | 없음 — 도구 호출 전에 판정. 단 **`bypassPermissions` 모드는 예외**(아래) |

- **평가 순서는 `deny` > `ask` > `allow`** 이며, 이 규칙은 `auto` 모드의 **분류기보다 먼저** 적용된다.
  → auto로 돌아도 `ask` 규칙에 걸리면 **반드시 사용자에게 묻는다**.
- **권한 규칙은 서브에이전트에도 그대로 적용된다.** 경계 지시문은 그 워커의 컨텍스트 안에만 있지만,
  권한 규칙은 세션 전체(메인 루프 + 모든 워커)에 걸린다. `.claude/agents/*.md`의
  "커밋·`apply`·`down -v` 금지"가 **실제로 지켜지는 근거**가 이것이다.
- **`bypassPermissions` 모드에서는 `ask`가 무력화된다.** 워커를 그 모드로 돌리지 않는다.

**배치 (단일 출처 3파일)**

| 파일 | 범위 | 담는 것 | git |
| --- | --- | --- | --- |
| `~/.claude/settings.json` | 전 프로젝트 | 범용 비가역(git·`rm -rf`·`sudo`·인프라 `apply`·외부 발신) + `autoMode` 분류기 튜닝 | — |
| [`.claude/settings.json`](../../.claude/settings.json) | 이 저장소 | **프로젝트 고유** 비가역 + hook 배선(§정합성 가드) | **커밋** |
| `.claude/settings.local.json` | 개인 | 세션 중 승인한 `allow` 누적 | 미추적 |

> ⚠️ **`allow`에 비가역 명령을 넣지 않는다.** 세션 중 "항상 허용"을 누르면 `settings.local.json`에
> 쌓이므로, 커밋·`apply` 계열이 들어갔는지 주기적으로 확인한다(2026-08-18 `Bash(git commit *)`·
> `Bash(git add *)` 유입 발견·제거). 상위 `ask`가 이기지만, 규약과 어긋난 흔적은 지운다.

**`ask` 대상** — 정본 규약의 "계획만 반환" 목록을 **전역+프로젝트 합산**으로 커버한다.
(2026-08-18 실측: 프로젝트 `ask` 27건. 어느 파일에 있는지가 **배치** 열이다 — 한쪽만 보면 누락으로 오인한다.)

| 축 | 명령 | 배치 | 왜 |
| --- | --- | --- | --- |
| 데이터 소실 | `compose down -v` | 프로젝트 | Postgres(Dagster 메타·dbt 상태)·SeaweedFS 전량 소실 |
| 데이터 소실 | `podman volume rm/prune` | 전역 | 프로젝트 무관하게 파괴적 |
| 재적재 유발 | `dbt --full-refresh`·`run-operation`·`build --full-refresh`·`seed`, `dg asset wipe` | 프로젝트 | 대용량 재빌드·머티리얼라이즈 이력 손실 |
| 스키마 파괴 | Trino·psql `DROP`·`TRUNCATE`·`DELETE` | 프로젝트 | 판정자 5종의 **금지 SQL**과 동일 목록 |
| 클러스터 | `scripts/k8s-down.sh` | 프로젝트 | 재기동 비용·상태 소실 |
| 클러스터 | `kind delete`, `kubectl apply/delete` | 전역 | 클러스터 파괴·선언 반영은 프로젝트 무관 |
| 비밀·상태 | `.env`, `terraform/**/*.tfstate` 수정 | 프로젝트 | **커밋 금지** 대상([git.md](git.md#5-커밋-금지--커밋-대상)) |
| 설정 자기수정 | `.claude/settings.json`·`settings.local.json` 수정 | 프로젝트 | 게이트가 **자기 자신을 무르는** 것을 막는다. 커밋 여부는 둘이 다르다 — 아래 참조 |

> ⚠️ **`.claude/settings.json`은 커밋 대상이고 `.claude/settings.local.json`은 커밋 금지다** — 글롭 하나로 묶어 읽지 마라.
> 전자는 팀이 공유하는 게이트·hook 배선이라 저장소에 남아야 하고, 후자는 개인 승인 누적이라 `.gitignore`로 막는다
> ([git.md §5](git.md#5-커밋-금지--커밋-대상)). `ask`가 걸리는 것은 **수정 행위**이고, 커밋 정책은 그와 별개다.

`autoMode.soft_deny`·`hard_deny`(전역)에 같은 축을 **자연어로도** 넣어, 규칙 문자열이 놓친 변형
(파이프·`-chdir=`·래퍼 스크립트)을 분류기가 잡게 한다. 규칙은 결정적이되 문자열 매칭이라 좁고,
분류기는 넓되 확률적이다 — **둘을 겹쳐 쓴다.**

## 역할 계층 (3-tier)

| 계층 | 실체(Claude Code 대응) | 책임 | 경계(하지 않는 것) |
| --- | --- | --- | --- |
| **supervisor** | 메인 루프(대화 주체) | 미션 목표·성공조건 정의 → 도메인 단위 분해 → director 배정 → 결과 취합·충돌조정 → 사용자 보고. 미션 저널(MOC) 개설·유지 | 직접 실행작업(워커에 위임) |
| **director** | `Agent` 툴로 띄운 **단일 조율 서브에이전트**(`director`, 도메인 무관) | **업무 성격에 따라 워커를 배정**하고 그 작업을 **감독**한다(관할: 구현·판정 워커·`general-purpose`) — 하위작업 분해 → 배정·병렬조율 → **품질·승인 게이트** → 결과 요약을 supervisor에 보고. **권한 밖·특이사항은 supervisor에 에스컬레이션**(진행 여부는 supervisor가 결정). 도메인 지식은 컨벤션·스킬로 참조 | 미션 전체 조정(supervisor 몫) · **권한 밖 작업의 자체 판단·진행** |
| **subagent / agent** | `Agent` 툴 **워커 서브에이전트** | 배정받은 **단일 작업** 수행(코드·조사·테스트) → **director 승인 아래** 실행하고 결과를 반환·보고 | 다른 워커 배정, 무승인 실행 |
| **security**<br/>(계층 밖) | `Agent` 툴 워커(읽기 전용) | **director 결정의 최종 컨펌** — 실행·채택 결정을 판정해 `[승인]`/`[반려]`. 노출·규제·거버넌스 점검 | 직접 수정·실행 · director의 지휘를 받는 것 |
| **archivist**<br/>(계층 밖) | `Agent` 툴 워커 | **모든 결정·액션의 기록 주체** — 체크포인트마다 저널 기록, 정합 감사·MOC 유지 | 판단·실행 · 저널 외 파일 수정 |

- **`security`·`archivist`는 director 관할 밖**이다 — **supervisor가 직접 배정**한다.
  director는 이 둘에게 허가를 내리지 않으며, 반대로 `security`의 컨펌에 **구속**된다.
- **director는 우선 1명**(도메인 무관). 도메인 지식(Dagster·dbt·infra·docs)은 해당 [컨벤션 문서](README.md)·스킬로 참조한다.
  부하·전문성 분리가 필요해지면 도메인별 director로 **분화**할 수 있다(YAGNI: 지금은 1명).
- 규모가 작은 미션은 계층을 접는다 — supervisor가 director/subagent 없이 직접 수행해도 된다(YAGNI).
  이때 저널에는 director/subagent를 **"미배정"** 으로 남긴다(가상 활동 금지).

## 승인 게이트 (approval gate)

**subagent는 자율 실행하지 않는다 — 담당 director의 승인 아래 움직인다.** 권한·책임 소재를 명확히 하고, 잘못된 실행을 상위로
넘기기 전에 거른다. Claude Code 서브에이전트는 **실행 중 중단이 불가**하므로 승인은 두 시점으로 실현한다.

- **사전 승인(plan-first)** — 되돌리기 어렵거나 위험한 작업(파일 대량 변경·삭제, 인프라 `apply`, 커밋/푸시, 스키마·데이터 파괴)은
  director가 워커에게 **계획만 반환**하게 하고, 검토 후 `[승인]` 하면 **별도 실행**을 배정한다. 위험하면 `[반려]`.
- **사후 승인(품질 게이트)** — 일반·가역 작업은 워커가 실행·반환한 뒤 director가 결과를 검증해 `[승인]`(supervisor로 보고) 또는
  `[반려]`(사유와 함께 재작업 배정)한다.
- 같은 게이트가 **supervisor↔director** 에도 적용된다 — supervisor가 director 결과를 `[승인]`/`[반려]` 한다.
- 승인·반려는 **상호작용 로그에 실제 이벤트**로 남는다(`[승인]`·`[반려]`). "누가 무엇을 허가/반려했는가"가 추적된다.

> 요지: **실행은 항상 승인을 거친다.** 위험하면 계획을 먼저 승인(사전), 아니면 결과를 승인(사후). 무승인 자율 실행은 없다.

## security 최종 컨펌 (final confirm)

**director의 결정은 `security` 컨펌을 거쳐야 실행된다.** 승인 게이트(director→워커)가 *작업 품질*을 본다면,
이 게이트는 *노출·규제·거버넌스 위험*을 본다 — 관점이 다르므로 서로를 대체하지 않는다.

### 대상 — 실행·채택 결정

| 컨펌 필요 | 컨펌 불요 |
| --- | --- |
| 워커에게 **실행을 배정**하는 결정 | 하위작업 **분해**·조사 배정 등 내부 조율 |
| 워커 결과를 **채택**해 supervisor에 보고하는 결정 | 워커 반환값 검토·`[반려]` 재작업 지시 |
| **비가역 작업 계획**(커밋·`apply`·삭제)의 승인 | 읽기·조회·`plan`·lint 수준 작업 |

> 범위를 "실행·채택"으로 둔 이유: 문자 그대로 "모든 결정"에 걸면 분해 단계마다 `security` 호출이 붙어
> 지연·토큰이 급증하는 반면, 위험은 대부분 **실행 시점**에 실현된다. 게이트 실효는 유지하고 호출은 줄인다.

### 절차

1. director가 결정을 도출한다.
2. director → `security` **`[질의]`**(컨펌 요청) — 결정 내용·근거·영향 범위·되돌림 가능성을 함께 낸다.
3. `security`가 **`[승인]`** 또는 **`[반려]`**(심각도별 발견·근거)로 판정한다.
4. `[반려]`면 director가 결정을 수정해 재요청한다. **동일 결정의 재컨펌은 2회까지** —
   3회째는 director가 supervisor에 **에스컬레이션**한다(무한 왕복 차단).
5. `[승인]` 후에만 실행한다.

- `security`는 **읽기 전용**이다. 컨펌은 판정 반환이며, 직접 수정하거나 실행하지 않는다.
- `security`는 director가 배정하지 않는다(관할 밖) — **supervisor가 배정**하고, director는 컨펌만 요청한다.
- 컨펌·반려는 상호작용 로그에 **실제 이벤트**로 남는다.

## 에스컬레이션 (escalation) — 상향 보고

승인 게이트가 **director → subagent 하향 통제**라면, 에스컬레이션은 **director → supervisor 상향 경로**다.
director는 배정한 워커의 작업을 **감독**하되, 아래에 해당하면 **임의로 진행하지 않고 supervisor에 보고**한다.
**진행 여부는 supervisor가 결정**한다.

### 보고 트리거

**① 권한 밖** — director/워커의 권한으로 실행할 수 없는 것

- **비가역 작업**: 커밋·푸시, `terraform apply`·`kubectl apply`, 볼륨·데이터 삭제, `compose down -v`
- **비용·외부 영향**: 과금이 발생하거나 외부 서비스·공용 자원에 영향을 주는 작업
- **규약·아키텍처 변경**: 정본 문서 수정, 기술 선택 변경 — 사용자 결정이 필요한 선택지
- **범위 밖**: 배정받은 도메인·목표를 벗어나는 작업

**② 특이사항** — 배정 시점의 **전제가 흔들린** 상황

- **선언↔런타임 드리프트**: 실제 상태가 계획·문서와 다름
- **결과 충돌**: 워커 간 근거가 상반되거나, 기존 기록과 실측이 배치됨
- **반복 실패**: 같은 작업이 재시도에도 게이트를 통과하지 못함
- **제3주체의 비승인 변경**: 병렬 세션·외부 요인이 작업 대상을 바꿈
- **범위 확대**: 착수 후 작업량·영향 범위가 배정 시점보다 유의미하게 커짐

### 절차

1. 해당 하위작업을 **중단**한다(다른 독립 작업은 계속해도 된다).
2. supervisor에 `[질의]`로 보고한다 — **상황·실측 근거·선택지·권고안**을 함께 낸다(추정 금지).
3. supervisor가 `[승인]`(진행) 또는 `[반려]`(중단·변경)로 결정한다. 필요하면 supervisor가 사용자에게 다시 `[질의]`한다.
4. 결정을 **수령한 뒤** 재개한다. 응답 없이 임의 진행하지 않는다.

- 에스컬레이션은 **실패가 아니라 정상 경로**다. 올려서 막히는 비용보다, 올리지 않아 잘못 실행되는 비용이 크다.
- 상호작용 로그에 **실제 이벤트**로 남는다(`[질의]` → `[승인]`/`[반려]`).
- 실측 사례:
  - `2026-08-17/12-spark-flink-k8s-setup` `23:35` — 워커가 검증 중 **제3주체의 클러스터 변경**을 감지하고
    "이전 전 상태 소멸"을 이슈로 반환(트리거 ②).
  - `2026-08-18/01-journal-numbering-hook` — `archivist`가 저널 간 **사실 충돌**(Spark CRD `v1` vs `v1beta1`)을
    스스로 판정하지 않고 지적만 반환(트리거 ②).
  - 워커 정의의 "비가역 작업은 **계획만 반환**" 제약이 트리거 ①의 워커 수준 구현이다.

## 기록관(archivist)

- **프로토콜이자 전용 서브에이전트**다. 기본은 프로토콜 — 각 계층이 종료 시 자기 기록을 반환하고
  supervisor가 저널을 단독 기록한다. 여기에 더해 **전용 워커 [`archivist`](../../.claude/agents/archivist.md)가
  실재**하며(2026-08-17 분리), 저널 정합 감사·MOC 유지처럼 **사후 단독 실행**이 안전한 작업에 배정한다.
  (실측: 2026-08-18 `20:0x` MOC 전면 갱신에 배정 — 당시 저널 14건 점검·`_MOC.md` 1건만 쓰기)
- 기록관은 **관측·기록만** 한다 — 판단·작업을 하지 않는다.
- **기록 주체는 archivist다**(§기록 주체). supervisor는 체크포인트마다 이벤트를 전달하고,
  archivist 호출이 실패할 때만 **폴백**으로 직접 쓴다.
- archivist는 **director 관할 밖**이다 — supervisor가 직접 배정한다.

## 저널 저장 위치

- 저널은 **개인 Obsidian 볼트**에 누적한다. **저장소(repo)에는 커밋하지 않는다** — 볼트는 자체 git으로 관리.
- 볼트 경로는 **환경마다 다를 수 있다**. 환경변수 **`$OBSIDIAN_VAULT`(기본값 `~/obsidian`)** 로 참조한다.
  머신·계정이 바뀌면 이 값만 조정하면 된다(하드코딩 금지, *12-Factor Config*).

```
$OBSIDIAN_VAULT/agents/            # 저널 루트 (기본 ~/obsidian/agents/)
  _TEMPLATE.md                     # 재사용 저널 템플릿
  _MOC.md                          # 전체 미션 지도(Map of Content) — 기록관이 유지
  <YYYY-MM-DD>/                    # 작업일자(KST) 폴더
    <NN>-<mission-slug>.md         # 미션당 1파일. NN = 그날의 착수 순번(01부터, 날짜마다 초기화)
    <NN>-<mission-slug>/           # (예외) 병렬 subagent가 많은 미션만 하위폴더로 액터 분리
```

- 파일명 앞 `NN` 은 그날 미션을 **착수한 순서**다(`01`·`02`…). 파일 목록만 봐도 **작업 순서**가 드러나고 정렬이 시간순이 된다.
  날짜 폴더가 바뀌면 `01`부터 다시 시작한다.
- 순번은 **파일명에만** 붙인다. 프론트매터 `mission:`·`tags:`의 슬러그는 **번호 없이** 유지한다(미션 정체성은 순서와 무관).
- 위키링크는 파일명 그대로 쓴다 — `[[01-agent-journal-trigger]]`. 표시를 줄이려면 별칭 `[[01-x|x]]`도 가능.

- **착수 시각의 판정 기준은 본문 `## 🔀 상호작용 로그`의 첫 이벤트**(대개 사용자 요청 수령 시각)다.
  프론트매터 `started`는 실제로 *파일 생성* 시각이라 동시 착수한 세션 간 변별력이 없다.
  (2026-08-17 23:0x 병렬 세션 둘이 같은 `11`을 점유 → 첫 이벤트 `23:00`/`23:05` 기준으로 `11`·`12` 정정)
- 넘버링은 문서 규약만으로 지킬 수 없다 — 병렬 세션은 서로의 컨텍스트를 보지 못한다.
  파일시스템을 단일 출처로 삼는 **hook 가드**가 강제한다(아래 [정합성 가드](#정합성-가드-hook)).

- **작업일자는 KST**(`Asia/Seoul`) 기준으로 폴더를 나눈다([타임존 정책](timezone.md)).
- **미션당 1파일**에 supervisor → director → subagent를 **계층 섹션**으로 누적(append)한다.
  파일 수 최소·시간순 가독이 목적. 병렬 subagent가 많은 미션만 예외로 하위폴더로 분리한다.

## 저널 포맷

원본 템플릿은 `$OBSIDIAN_VAULT/agents/_TEMPLATE.md`. 새 미션은 이를 복사해 채운다.

### 프론트매터(YAML)

```yaml
---
mission: <mission-slug>
date: <YYYY-MM-DD>
status: planned          # planned | in-progress | done | blocked
supervisor: main-loop
agent: <runtime>         # 실행 런타임/도구: claude-code | codex | cursor | ...
model: <model-id>        # supervisor 모델(예: claude-opus-4-8[1m])
directors: []            # 배정된 도메인 director 목록
tags: [agent/mission, mission/<mission-slug>]
started: <YYYY-MM-DDThh:mm+09:00>    # KST
updated: <YYYY-MM-DDThh:mm+09:00>    # KST
---
```

- **`agent`(실행 런타임/도구)** 와 **`model`(모델 ID)** 를 반드시 남긴다 — 어떤 도구·모델이 한 일인지
  추적·재현·비교하기 위함. 프론트매터 값은 **supervisor(세션 주체)** 기준이다.
- director/subagent가 **다른 도구·모델**로 돌면(예: 일부는 `codex`, 일부는 `claude-code`), 각 섹션에
  `agent·model` 을 개별 표기한다(아래 본문 규칙).

### 본문 — PDCA 계층 섹션

- `## 🧭 supervisor — 미션 정의·분해` : 입력(사용자 요청)·성공조건·도메인 분해·**결정 로그(왜)**.
- `## 🔀 상호작용 로그` : **계층 간 주고받음**을 시간순으로(아래 별도 규칙).
- `## 🏷 director: <domain>` : 계획(Plan)·검증(Check 품질게이트), 그 아래 `#### 🔧 subagent: <id>`
  (아래 **서브에이전트 기록 항목** 참조).
  - director를 거치지 않고 supervisor가 워커를 직접 배정했다면 제목을 **역할에 맞게 바꿔 쓴다**
    (예: `## 🏷 기록관: archivist`, `## 🏷 점검 워커`). 없는 director를 만들어 적는 것보다 정확하다(가상 활동 금지).
- `## ✅ supervisor — 취합·보고` : 도메인 결과 종합·사용자 보고 요약·후속(Act).
- 노트 간 연결은 Obsidian `[[위키링크]]` 를 쓴다(부모↔자식 노트·후속 미션).

### 서브에이전트 기록 항목 (`#### 🔧 subagent: <id>`)

**어떤 에이전트가 무슨 권한으로 무엇을 얼마나 써서 했는가**가 남아야 재현·비교·비용판단이 된다.
호출한 서브에이전트마다 아래를 남긴다(**실행 메타**는 표, 나머지는 항목).

| 필드 | 내용 | 출처 |
| --- | --- | --- |
| `type` | 호출한 `subagent_type` (`director`·`security`·`archivist`·`general-purpose` …) | 배정 시점 |
| `agent·model` | 실행 런타임 · 모델 ID (예: `claude-code` · `claude-opus-5[1m]`) | supervisor와 같으면 `동일`로 축약 |
| `tools` | 그 에이전트에 **허용된 도구**(읽기 전용이면 명시) | `.claude/agents/<name>.md` frontmatter |
| `도구 호출` · `토큰` | 실제 도구 호출 수 · 소비 토큰 | 서브에이전트 반환 메타(`tool_uses`·`subagent_tokens`) |
| `소요` | 실행 시간 | 런타임 보고치. **대기 포함일 수 있으므로** 의심되면 `추정`·`미확인` 표기 |
| `결과` | `[승인]` / `[반려]`(사유) / `실패` | 승인 게이트 결과 |

- 이어서 **입력**(배정 지시 요지·부여한 제약)·**실행(Do)**·**결과/검증(Check)**·**산출물**·**조치(Act)** 를 적는다.
- **런타임이 주는 수치는 가공하지 않는다.** 값이 없으면 `미측정`으로 남기고 추정치를 사실처럼 쓰지 않는다.
- **자기보고 ≠ 런타임 계측이면 런타임 값을 채택**하고, 불일치 사실을 함께 남긴다.
  서브에이전트가 응답 본문에 적는 "도구 N회"는 자기 관측이라 어긋날 수 있다(2026-08-17 `security` 실측: 자기보고 15 / 런타임 29).
  기록의 근거는 **호출자가 받은 런타임 메타**다.
- 같은 미션에서 같은 타입을 여러 번 부르면 `#### 🔧 subagent: security-1`처럼 **일련번호**로 구분한다.
- 서브에이전트가 **부여받은 제약을 지켰는지**(저장소 쓰기 금지·커밋 금지 등)를 `결과/검증`에 명시한다 — 경계 준수도 기록 대상이다.

### 상호작용 로그 (`## 🔀 상호작용 로그`)

이 저널의 **핵심 목적**은 "누가 무엇을 했나"에 더해 **agent↔subagent 사이에 어떤 주고받음이 있었나**(배정·보고·질의·반려)를
남기는 것이다. 계층 간 이벤트를 **시간순 한 줄씩** 방향(`→`)과 유형 태그로 적는다.

```markdown
## 🔀 상호작용 로그 (dispatch ↔ report)
- `23:05` **supervisor → director-dbt** `[배정]` bronze source 매핑 정합성 점검
- `23:06` **director-dbt → subagent dbt-1** `[배정]` staging 3개 모델 sqlfluff 수정
- `23:14` **subagent dbt-1 → director-dbt** `[보고]` 3/3 수정·`dbt build` 통과, 산출물 링크
- `23:15` **director-dbt → supervisor** `[보고]` 도메인 완료 요약 / `[반려]`·재작업 있으면 사유
```

- **유형 태그 — 오간 것**: `[배정]`(dispatch) · `[보고]`(report) · `[질의]`(query) · `[반려]`(reject/재작업) · `[승인]`(approve).
- **유형 태그 — 관측된 것**: `[결정]`(사용자·supervisor의 확정) · `[조치]`(직접 실행) · `[확인]`(실측 검증) · `[반증]`(자기 정정) · `[특이사항]`(전제 흔들림) · `[사고]`(손실·훼손) · `[복구]`.
  주체가 하나인 사건도 **시간순 사실**이면 남긴다 — "왜 그때 방향이 바뀌었나"를 추적할 수 있는 유일한 자리다.
- **방향**은 항상 `보낸 주체 → 받는 주체`. 병렬 배정은 각 줄로 나눈다.
- 시각은 **KST**. **실제 오간 것만** 적는다(가상 상호작용 금지). 세부 결과는 해당 계층 섹션에 두고, 여기엔 **오간 사실**만 남긴다.

## 기록 주체 — archivist 전담 (single-writer 유지)

**기록 주체는 `archivist`다 — 모든 결정과 액션을 archivist가 저널에 남긴다.**
동시에 **단일 기록자 원칙은 유지된다**: 한 미션 파일에 같은 시점에 쓰는 주체는 언제나 **1명**이다
(병렬 append는 경합·손상을 낸다 — 이 원칙을 만든 이유).

- **저자는 archivist, 관측 전달자는 supervisor.** 서브에이전트는 **실시간 관측이 불가**하고 반환으로만 소통하므로,
  supervisor가 이벤트를 모아 **체크포인트마다 archivist를 호출**해 기록시킨다(§기록 시점).
- **director·워커는 저널을 직접 쓰지 않는다.** 구조화된 결과를 **반환**하고, 그 반환값이 archivist에게 전달된다.
- **폴백 — supervisor 직접 기록**: archivist 호출이 실패하거나 세션이 급히 끝날 때는 supervisor가 직접 쓴다.
  **기록 유실이 경합보다 나쁘다.** 폴백으로 쓴 구간은 다음 archivist 호출 때 **정합 검토 대상**으로 넘긴다.
- **동시 쓰기 금지**: archivist가 기록하는 동안 supervisor는 같은 파일을 쓰지 않는다. 반대도 같다.
- archivist는 **판단하지 않는다** — 있었던 일을 기록하고, 어긋난 곳을 **지적**할 뿐 고쳐 쓰지 않는다.

> 요지: **기록의 저자는 archivist, 쓰는 순간은 언제나 한 명.** 나머지는 "무엇을 했는지"를 **반환**으로 넘긴다.

## 기록 시점 — 언제 쓰는가 (trigger)

위치·포맷·주체만 정해두면 **저널은 쌓이지 않는다**. 기록이 일어나는 **시점**을 규약으로 못박는다.
아래 **체크포인트**에서 supervisor가 이벤트를 모아 **archivist에 기록을 위임**한다(실패 시 supervisor 폴백).
체크포인트를 두는 이유: 이벤트마다 archivist를 호출하면 서브에이전트 왕복 비용이 폭증하고,
미션 종료에 한 번만 쓰면 세션 중단 시 통째로 유실된다. **배치가 두 실패 사이의 균형점**이다.

| 체크포인트 | 동작 | 기록 |
| --- | --- | --- |
| **미션 개시** | `_TEMPLATE.md` 복사 → `$OBSIDIAN_VAULT/agents/<KST 날짜>/<NN>-<mission-slug>.md` 생성, `status: in-progress`·`started` 기입 (NN은 hook이 발급 — §정합성 가드) | supervisor (개시는 즉시성이 필요) |
| **계층 전환** — director 배정 직전·직후 | `## 🔀 상호작용 로그`에 오간 사실 append | archivist |
| **워커 반환 수령 직후** | 반환값을 계층 섹션(`## 🏷 director:` / `#### 🔧 subagent:`)에 옮겨 적기 + **실행 메타** 표 | archivist |
| **security 컨펌 전후** | 컨펌 요청(`[질의]`)과 판정(`[승인]`/`[반려]`)을 근거와 함께 | archivist |
| **미션 종료 — 사용자 최종 보고 직전** | `## ✅ supervisor — 취합·보고` 작성, `status: done`(막히면 `blocked`), `updated` 갱신 | archivist (실패 시 supervisor) |
| **세션 종료·컨텍스트 요약 직전** | 진행 중이면 현재 상태까지 저장 | supervisor 폴백 (유실 방지 우선) |

**미션 판단 기준** — 다음 중 **하나라도** 해당하면 저널을 연다.

- 저장소 파일을 **생성·수정**하는 작업(코드·문서·설정 모두)
- **director/subagent 위임**이 일어나는 작업
- 사용자와 **결정·합의**가 오간 작업(규약·아키텍처·기술 선택)
- 인프라 **`apply`·배포·마이그레이션** 등 비가역 작업

**열지 않는 것(YAGNI)**: 단순 조회·질의응답, 읽기 전용 탐색, 1회성 명령 실행.

- **`mission-slug`** 는 영문 kebab-case(예: `oci-terraform-setup`). 같은 날 같은 미션이 이어지면 **같은 파일에 append**한다.
- **수동 트리거**: `/journal` 슬래시 커맨드([`.claude/commands/journal.md`](../../.claude/commands/journal.md))로 언제든 현재 세션을
  저널에 기록·갱신한다. 자동 기록이 누락됐을 때의 **보정 수단**이자, 사용자가 명시적으로 기록을 요구하는 통로다.
- **볼트 경로 설정**: `$OBSIDIAN_VAULT`는 **셸 환경변수**로 둔다 — `~/.zshenv`에
  `export OBSIDIAN_VAULT="${OBSIDIAN_VAULT:-$HOME/obsidian}"`. `$HOME` 기준이라 **절대경로 하드코딩이 없고**,
  셸·스크립트·AI 세션이 **한 곳**에서 값을 받는다(*12-Factor Config* / [operations.md](../operations.md#1-환경변수-주입)).
  - **프로젝트 `.env`에 두지 않는다** — `.env`는 compose가 **컨테이너에 주입**하는 런타임 경로이고(AI 세션은 이를 읽지 않는다),
    볼트 경로는 **프로젝트 무관·머신 전역** 값이며 **비밀정보도 아니다**. 성격·전파 경로가 모두 다르다.
  - 미설정 환경에서는 `~/obsidian`으로 폴백한다(`${OBSIDIAN_VAULT:-$HOME/obsidian}`).

## 기록 원칙

1. **있었던 일만** 기록한다(가상 director/subagent 활동 금지).
2. **결정에는 근거(왜)** 를 함께 남긴다 — 나중에 추적·재현 가능하도록.
3. 시각은 **KST**, 저장 시각·`updated` 를 갱신한다.
4. 저널은 **볼트에만**(repo 커밋 금지). 저장소에는 이 **규약(정본)** 만 둔다 — 단일 출처 분리.

## 네이티브 구현 (`.claude/agents/`)

계층은 **Claude Code 서브에이전트**로 구현되어 있다. 각 정의는 종료 시 저널용 결과를 **반환**하도록(supervisor가 기록) 지시문에 못박는다.

| 파일 | 계층 | 역할 |
| --- | --- | --- |
| (없음) | supervisor | 메인 루프(대화 주체) — 파일로 만들 수 없음 |
| `.claude/agents/director.md` | director | **단일 조율자(도메인 무관)** — 분해·배정·품질/승인 게이트·보고. 도메인 지식은 컨벤션·스킬로 참조 |
| (내장 `general-purpose`) | subagent/worker | 단일 작업 워커 — 별도 파일 불필요(YAGNI) |
| `.claude/agents/security.md` | subagent/worker (전문) | **보안 담당** — 비밀누출·데이터 거버넌스·인프라 노출·ISMS-P 준수를 **읽기 전용** 점검, 발견만 반환 |
| `.claude/agents/data-engineer.md` | subagent/worker (전문) | **데이터 엔지니어** — Dagster 에셋·dbt 모델·S3→Iceberg 적재를 **구현·수정**(쓰기 워커) |
| `.claude/agents/data-verifier.md` | subagent/worker (전문) | **데이터 검증자** — 적재된 **실제 데이터 값**을 Trino로 원천과 대조(**읽기 전용**), 불일치만 반환 |
| `.claude/agents/data-qa.md` | subagent/worker (전문) | **데이터 품질보증** — dbt 테스트 커버리지·게이트 등 **검증 체계**를 감사(**읽기 전용**), 보강 계획만 반환 |
| `.claude/agents/devops-engineer.md` | subagent/worker (전문) | **데브옵스 엔지니어** — compose·Dockerfile·k8s manifest·Terraform HCL을 **구현·수정**(쓰기 워커, 로컬 compose 기동 허용) |
| `.claude/agents/devops-verifier.md` | subagent/worker (전문) | **데브옵스 검증자** — 실행 중 인프라의 **런타임 상태**를 선언과 대조(**읽기 전용**), 불일치만 반환 |
| `.claude/agents/devops-qa.md` | subagent/worker (전문) | **데브옵스 품질보증** — 인프라 **선언 파일·게이트 체계**를 감사(**읽기 전용**), 보강 계획만 반환 |
| `.claude/agents/archivist.md` | 기록관 | 저널 정합성·누락 점검, MOC 유지(관측·기록만) |

- director는 `Agent` 툴로 호출한다(`subagent_type: director`). 워커 위임은 기본 `general-purpose`,
  도메인이 맞으면 **전문 워커**(`security` · `data-*` 3종 · `devops-*` 3종)를 쓴다.
- **전문 워커 = 읽기 전용 원칙**: `security`·`data-verifier`·`data-qa`·`devops-verifier`·`devops-qa`처럼
  **판정이 목적**인 워커에는 `Write`/`Edit`를 주지 않는다. 발견을 반환하면 승인 후 **수정은 별도 워커에 배정**한다
  (승인 게이트가 실제로 작동하게 하는 장치).
  **구현이 목적**인 워커(`data-engineer`·`devops-engineer`)는 예외로 쓰기를 갖되, **비가역 작업**(커밋·푸시·
  `terraform apply`·`kubectl apply`·`compose down -v`·파괴적 변경)은 계획만 반환하고 사전 승인을 받는다.

### 전문 워커 3종 세트의 경계 (중첩 금지)

`verifier`/`qa`는 통상 의미가 겹치므로 **축을 명시**해 나눈다 — 겹치면 배정 판단이 흐려지고 규약이 형식화된다.
데이터·인프라 도메인에 **같은 축**을 적용해 판단 규칙을 하나로 유지한다.

| 축 | 보는 대상 | 질문 | 데이터 | 인프라 |
| --- | --- | --- | --- | --- |
| **구현** | 코드·선언 파일 | "어떻게 만드는가" | `data-engineer` | `devops-engineer` |
| **인스턴스** | 지금 존재하는 실체 | "실제가 맞는가" | `data-verifier`(테이블 값) | `devops-verifier`(컨테이너·파드 상태) |
| **체계** | 검증 장치·게이트 | "상시 장치가 있는가" | `data-qa`(dbt 테스트 커버리지) | `devops-qa`(규약 준수·CI 게이트) |

- 흐름(양 도메인 동일): `*-engineer` 구현 → `*-verifier` 실측 대조 → `*-qa`가 그 규칙을 **상시 게이트로 만들 계획** 반환 →
  승인 후 `*-engineer`가 작성. **판정자는 절대 스스로 고치지 않는다.**
- **`security`와의 경계**: `security`는 **비밀 누출·인그레스 노출·RBAC·ISMS-P 준수**의 정본 판정자다.
  `devops-qa`는 같은 파일을 보더라도 **운영 신뢰성·재현성**(태그 고정·자원 한도·healthcheck·CI 게이트)만 본다.
  겹치는 항목은 `devops-qa`가 중복 제기하지 않고 **`security` 확인 요청으로 넘긴다**.
- 정본: 데이터 = [`test.md`](../test.md)·[`dataset_schema.md`](../dataset_schema.md)·[`dagster.md`](dagster.md)·[`dbt.md`](dbt.md) /
  인프라 = [`docker.md`](docker.md)·[`k8s.md`](k8s.md)·[`terraform.md`](terraform.md)·[`resource-sizing.md`](../resource-sizing.md)·[`operations.md`](../operations.md).
  워커 정의는 **정본을 집행**할 뿐 규칙을 새로 만들지 않는다.
- **새 `.claude/agents/*.md`는 추가 직후 같은 세션에서 쓸 수 있다** — 런타임이 레지스트리를 갱신한다(2026-08-17 `security` 추가 시 실측).
  다만 갱신은 런타임 동작이라 보장 대상이 아니다. `subagent_type`을 찾지 못하면 새 세션에서 재시도한다.
- 부하·전문성 분리가 필요해 도메인별 director로 분화하면 이 표와 `.claude/agents/`를 함께 갱신한다.

## 정합성 가드 (hook)

저널 규약 중 **기계가 판정할 수 있는 것**은 문서가 아니라 hook이 강제한다. 근거는 위 경합 사고다 —
규약은 각 세션의 컨텍스트 안에만 있고, 파일시스템은 하나다.

- 구현: [`scripts/journal_guard.py`](../../scripts/journal_guard.py) (의존성 없음·PEP 723·서브커맨드 3종)
- 배선: [`.claude/settings.json`](../../.claude/settings.json) (프로젝트 범위, 커밋 대상)

> `.claude/settings.json` 한 파일이 **hook 배선 + 프로젝트 `permissions`**(§권한 게이트)를 함께 담는다.
> 저널 규율은 hook이, 워커 경계는 `permissions`가 강제한다 — 둘 다 **프로젝트 범위·커밋 대상**이다.

| hook 이벤트 | 서브커맨드 | 하는 일 | 실패 시 |
| --- | --- | --- | --- |
| `SessionStart`(`startup\|resume\|clear\|compact`) | `session-start` | 오늘의 **다음 `NN`**·기존 저널·최근 7일 **열린 미션**(`planned`·`in-progress`·`blocked`)을 stdout으로 **컨텍스트 주입** | 주입 없음(작업 계속) |
| `PreToolUse`(matcher `Write`) | `pre-write` | 볼트 저널 **신규 생성**만 검사 — `NN` 중복·번호 건너뜀·파일명(`<NN>-<slug>.md`)·날짜 폴더(`YYYY-MM-DD`) 위반이면 **차단**하고 올바른 번호를 반환 | 통과(fail-open) |
| `Stop` | `stop` | 오늘 저장소 변경(working tree 또는 당일 커밋)이 있는데 **오늘자 저널 부재** 또는 `updated` 미갱신이면 사용자에게 경고 | 경고 없음 |

- **차단은 `PreToolUse`만** 한다. 공식 스펙상 `Stop`의 exit 2는 "정지를 막고 대화를 계속"이라 경고 용도로
  부적합하므로, `Stop`은 exit 0 + JSON `systemMessage`로 알린다.
- **기존 저널 수정·`_` 접두 파일(`_MOC`·`_TEMPLATE`)·볼트 밖 경로는 검사하지 않는다** — 가드는 넘버링에만 관여한다.
- `$OBSIDIAN_VAULT`가 없거나 볼트가 없는 환경(다른 머신·CI)에서는 **조용히 통과**한다.
  가드가 개인 환경 의존성을 세션의 전제조건으로 만들면 안 된다.
- 가드가 판정할 수 없는 것(내용의 진실성·결정 근거·계층 기록)은 여전히 **supervisor의 책임**이다.
  hook은 규율을 대체하지 않고 **경합만** 없앤다.

## 참고

- 타임존 정책: [`timezone.md`](timezone.md) (KST 기준 일자·시각)
- 문서 동기화: [`../doc-sync.md`](../doc-sync.md)
- 코딩 철학(단순함·추적 용이성): [`../philosophy.md`](../philosophy.md)
- Claude Code Hooks 레퍼런스(이벤트·exit code·JSON 출력): <https://code.claude.com/docs/en/hooks>
