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

> **#5(DRY)와 #6(적은 파일로 파악)의 균형**: 값·로직의 반복은 3회부터 추출(#5)하되, 그 추출이
> **다른 파일로의 점프를 만들어 파악을 흩뜨린다면** wiring/설정에 한해 #6을 우선한다. 예)
> `IcebergCatalogConfig` 카탈로그 설정은 공용 빌더(`common/resources.py`)로 빼는 대신
> `defs/resources.py`의 각 리소스에 인라인해 **한 파일에서 전체 리소스 설정을 읽도록** 한다.
> 판단 기준: 추출 대상이 **로직(계산·분기)** 이면 #5, **선언적 설정·wiring** 이면 #6 쪽으로 기운다.

## 참고

- PEP 20 — The Zen of Python: https://peps.python.org/pep-0020/
- The Twelve-Factor App — III. Config: https://12factor.net/config
- Locality of Behaviour (Carson Gross): https://htmx.org/essays/locality-of-behaviour/
