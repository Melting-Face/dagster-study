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

## 참고

- PEP 20 — The Zen of Python: https://peps.python.org/pep-0020/
- The Twelve-Factor App — III. Config: https://12factor.net/config
