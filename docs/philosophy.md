# 코딩 철학

이 프로젝트의 코드·설계 결정을 관통하는 핵심 가치. 구체적 규칙(어떻게)은 `conventions/`에,
이 문서는 그 근거(왜)를 담는다.

> 출처: **PEP 20 — The Zen of Python** (Tim Peters) · **The Twelve-Factor App** (Adam Wiggins).
> Zen of Python 원문은 `python -c "import this"` 로 확인.

## 원칙

| #   | 원칙                 | 격언 (출처)                                  | 적용                                                                                            |
| --- | -------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1   | **단순함**           | *Simple is better than complex.* (PEP 20)    | 함수+데코레이터·상속 지양 · 최소 인프라(YAGNI: 메타스토어 회피, Flink 보류) · 데이터 특성에 맞는 도구 |
| 2   | **명시적**           | *Explicit is better than implicit.* (PEP 20) | 선언적 설정(dbt `meta.dagster.group`·데코레이터 인자) · 규칙은 문서로 명문화 · 의존성·env·경로 명시 |
| 3   | **가독성**           | *Readability counts.* (PEP 20)               | 관심사 분리(기능별 모듈 constants·utils·helper·assets) · 영어 식별자/한국어 주석 · ruff·sqlfluff·4칸 |
| 4   | **비밀정보는 참조로** | III. Config (12-Factor App)                  | `${ENV:VAR}`·`{{ env_var() }}`·`os.environ` · `.env` gitignore·값 노출 금지 · 비밀 설정 `:ro` 마운트 |
| 5   | **재사용은 3회부터 추출** | Rule of Three — *Refactoring* (M. Fowler) / DRY — *Pragmatic Programmer* | 동일 로직/값이 **3회 이상 반복되면 함수·상수로 추출** · 2회까지는 허용(과도한 추상화 경계) |
| 6   | **추적 용이성**      | Locality of Behaviour (C. Gross) / *Readability counts.* (PEP 20) | **코드를 파악할 때 최대한 적은 파일로 파악할 수 있게** — wiring은 한 곳에 모아 중간 레이어를 줄이고(읽을 때 점프 최소화) · 값은 **named constant**로 선언해 grep/IDE 점프 가능 · 자산은 팩토리 대신 **명시 정의**로 이름 검색 · 로직 없는 단순 리턴 리소스·설정은 빌더 없이 인라인 · 실행형 스크립트(`scripts/`)는 절차형(클래스·보조 함수 최소화)으로 **실행 순서 = 읽는 순서** 유지 |
| 7   | **성공 신호를 의심한다** | *Errors should never pass silently.* (PEP 20) / *Program testing can be used to show the presence of bugs, but never to show their absence.* (E. W. Dijkstra) | **성공 신호가 무엇을 증명하는지 적는다** — "통과"가 *검사했다*인지 *실행됐다*뿐인지 구분 · 부정 결과(없음·통과·정상)는 **관측 경로가 살아 있었음을 함께 확인**해야 유효 · 게이트를 새로 걸면 **일부러 위반시켜 실제로 막히는지** 본다 |

> **#5(DRY)와 #6(적은 파일로 파악)의 균형**: 값·로직의 반복은 3회부터 추출(#5)하되, 그 추출이
> **다른 파일로의 점프를 만들어 파악을 흩뜨린다면** wiring/설정에 한해 #6을 우선한다. 예)
> `IcebergCatalogConfig` 카탈로그 설정은 공용 빌더(`common/resources.py`)로 빼는 대신
> `defs/resources.py`의 각 리소스에 인라인해 **한 파일에서 전체 리소스 설정을 읽도록** 한다.
> 판단 기준: 추출 대상이 **로직(계산·분기)** 이면 #5, **선언적 설정·wiring** 이면 #6 쪽으로 기운다.

### #7의 근거 — 실패가 실패로 보이지 않는다 (2026-08-19 실측 6건)

이 원칙은 추상론이 아니라 **하루에 여섯 번 같은 구조로 밟은 결과**다. 공통점은 하나다 —
🔴 **확인 행위는 성공했는데 확인 대상은 확인되지 않았다.**

| 사례 | 겉보기 | 실제 | 무엇이 안 보였나 |
| --- | --- | --- | --- |
| 에이전트 hook `command` 인용 오류 | 도구 호출 **통과** | 훅 **미발동** | 명령이 깨지면 에러가 아니라 통과다 |
| CNPG `bootstrap.initdb` 비밀번호 회전 | Secret **갱신됨** | DB 롤은 **그대로** | `initdb`는 부트스트랩 1회성 |
| `SparkApplication` `DriverReady` 고착 | 잡 **실행 중** | 이미 **성공 종료** | 오퍼레이터 watch가 죽어 상태가 안 바뀜 |
| `skills-lock.json` 3/24 고정 | **고정됨** | lock에 없으면 **최신을 씀** | 미등재는 경고 없이 통과 |
| compose SeaweedFS 조회 실패 | 데이터 **없음** | 321MB **실재** | 컨테이너가 죽어 있었을 뿐 |
| `dbt compile` 22모델 통과 *(기존 교훈)* | 이행 **완료** | 값 일치는 **미검증** | 컴파일은 값을 보지 않는다 |

- 🔴 **부정 결과는 관측 경로의 생존을 함께 증명해야 유효하다.** "없다"·"통과"·"정상"은
  *대상이 그렇다*는 뜻일 수도, *보지 못했다*는 뜻일 수도 있다. 후자를 배제하지 않으면 결론이 아니다.
- 🔴 **게이트는 걸었다고 서지 않는다.** 새로 건 규칙·훅·테스트는 **일부러 위반시켜** 실제로 막히는지 본다
  (§실발동 확인). 통과만 보고 "막힌다"고 문서에 쓰지 않는다 — 그 문장이 다음 사람을 속인다.
- 🔴 **한 번의 성공을 결론으로 읽지 않는다.** 위 hook 사례는 발동 2회를 확인한 뒤
  **같은 조합이 6회 연속 미발동**했다. 재현되지 않으면 아직 결론이 아니다.
- **마지막 행이 이 원칙을 만든 이유다** — 같은 교훈을 사례가 나올 때마다 *그 사례 옆에* 따로 적어왔다.
  이름을 붙여 한곳에 모은다.

## 참고

- PEP 20 — The Zen of Python: https://peps.python.org/pep-0020/
- The Twelve-Factor App — III. Config: https://12factor.net/config
- Locality of Behaviour (Carson Gross): https://htmx.org/essays/locality-of-behaviour/
- E. W. Dijkstra, *Notes on Structured Programming* (EWD249, 1970) — "Program testing can be used
  to show the presence of bugs, but never to show their absence."
  https://www.cs.utexas.edu/~EWD/ewd02xx/EWD249.PDF
