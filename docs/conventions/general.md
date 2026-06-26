# 공통 코딩 규칙

모든 언어·파일에 공통으로 적용되는 규칙이다.
언어별 세부 규칙은 [Python](python.md) · [Dagster](dagster.md) · [dbt](dbt.md) 문서를 참고한다.

## 언어 (Language)

| 대상                               | 언어                                   |
| ---------------------------------- | -------------------------------------- |
| 코드 주석                          | **한국어**                             |
| 변수명 · 함수명 · 모델명 등 식별자 | **영어**                               |
| 문서(docs)                         | **한국어** (식별자·명령어·경로는 원문) |
| 커밋 메시지                        | **한국어**                             |

## 들여쓰기 (Indentation)

- **스페이스 4칸**으로 통일한다. (Python · YAML · SQL 공통)
- 탭 문자는 사용하지 않는다.

## 포매터 / 린터

| 대상 | 도구 | 설정 위치 |
| --- | --- | --- |
| Python | [`ruff`](https://docs.astral.sh/ruff/) (lint + format) | `pyproject.toml` `[tool.ruff]` |
| SQL | [`sqlfluff`](https://docs.sqlfluff.com/) | `pyproject.toml` `[tool.sqlfluff.*]` |
| 커밋 메시지 | [`gitlint`](https://jorisroovers.github.io/gitlint/) | `.gitlint` (루트) |
| YAML | [`yamllint`](https://yamllint.readthedocs.io/) | `.yamllint.yaml` (루트) |
| Dockerfile | [`hadolint`](https://github.com/hadolint/hadolint) | `.hadolint.yaml` (루트) |
| 시크릿 스캔 | [`gitleaks`](https://github.com/gitleaks/gitleaks) | `.gitleaks.toml` (루트) |
| Python 타입체크 | [`mypy`](https://mypy-lang.org/) | `pyproject.toml` `[tool.mypy]` |

커밋 전 포매터·린터를 통과시킨다. (`mypy`는 어노테이션이 아닌 **타입 정합성**을 검사)

### 실행 (pre-commit)

커밋 시 [`pre-commit`](https://pre-commit.com/)이 린터·포매터·시크릿 스캔을 자동 실행한다(`.pre-commit-config.yaml`).
규칙의 단일 출처는 위 표의 "설정 위치"인 도구 네이티브 파일이며, pre-commit은 **'언제 무엇을 실행할지'만** 정의한다(스테이징된 파일만 검사).

```bash
uv tool install pre-commit
pre-commit install --install-hooks    # pre-commit + commit-msg 훅 설치
pre-commit run --all-files            # 전체 수동 검사
```

- **포함 훅**: `ruff`(check+format) · `yamllint` · `gitleaks` · `gitlint`(commit-msg) · 기본 위생 훅(공백·EOF·toml/yaml 검사).
- **미포함**(마찰·의존성으로 수동/CI): `sqlfluff`(dbt 모델 부재), `mypy`(전체 컨텍스트 필요 → `mypy src`), `hadolint`(바이너리/도커 필요).

직접 실행도 가능하다:

```bash
ruff check . && ruff format .        # Python
yamllint .                           # YAML
gitleaks detect                      # 시크릿 스캔
mypy src                             # Python 타입 정합성 (CI)
```

### 설정 위치 원칙

- `pyproject.toml`을 지원하고 **그 위치에서 실행되는** 도구(`ruff`·`sqlfluff`)는 `pyproject.toml`에 모은다.
- 그 외는 **루트의 도구 네이티브 설정 파일**에 둔다.
  - `yamllint` → `.yamllint.yaml` (pyproject 미지원)
  - `hadolint` → `.hadolint.yaml`
  - `gitleaks` → `.gitleaks.toml`
  - `gitlint` → `.gitlint` (repo 루트에서 실행 → 하위 `pyproject.toml` 자동탐지 불가)
- 세부 예시는 [Python](python.md) · [dbt](dbt.md) 문서 참고.

## 커밋 메시지 (Conventional Commits)

[Conventional Commits](https://www.conventionalcommits.org/) 규약을 따른다.
gitlint `contrib-title-conventional-commits` 룰로 강제한다(루트 `.gitlint`, pre-commit `commit-msg` 훅).

- **형식**: `type(scope): 설명` — `scope`는 선택, **설명은 한국어**.
- 제목은 **72자 이내**(`title-max-length`).
- 파괴적 변경은 `type!: ...` 또는 본문에 `BREAKING CHANGE:` 표기.

### type 종류 (표준 11종)

| type | 용도 | SemVer |
| --- | --- | --- |
| `feat` | 새 기능 | MINOR ↑ |
| `fix` | 버그 수정 | PATCH ↑ |
| `docs` | 문서만 변경 | — |
| `style` | 포맷·세미콜론 등(동작 불변) | — |
| `refactor` | 리팩터링(기능·버그 변화 없음) | — |
| `perf` | 성능 개선 | PATCH |
| `test` | 테스트 추가·수정 | — |
| `build` | 빌드 시스템·의존성 | — |
| `ci` | CI 설정·스크립트 | — |
| `chore` | 잡무(설정·도구 등, src·test 무관) | — |
| `revert` | 커밋 되돌리기 | — |

> 기존 커스텀 type(`mod`·`add`·`del`)은 **폐지**하고 아래로 매핑한다.

| 기존 | → 전환 |
| --- | --- |
| `mod` | 상황별 `feat`(기능) / `fix`(수정) / `refactor` |
| `add` | `feat`(기능) 또는 `chore`·`build`(설정·의존성) |
| `del` | `refactor`(코드 정리) 또는 `chore` |

```text
feat: discord 봇 Ollama Cloud 연동 추가
refactor: DuckDB→Trino 전환, SeaweedFS standalone 및 dlt·bronze 리셋
chore: ruff·gitlint 등 린터 설정 추가
docs: 코딩 규칙 문서 추가
```

## 비밀정보 (Secrets)

- 키·토큰·비밀번호를 코드·설정 파일에 **하드코딩하지 않는다.**
- `.env` + 환경변수로 주입한다. (예: Trino 카탈로그의 `${ENV:AWS_ACCESS_KEY_ID}`)
- `.env`는 절대 커밋하지 않는다.

## 디렉토리 규칙

- 서비스별 컨테이너 빌드 컨텍스트는 `<service>/dockerfile.d/` 하위에 둔다.
- Dagster 프로젝트 소스는 `dagster/dockerfile.d/src/` 하위.
- dbt 프로젝트는 `dagster/dockerfile.d/src/dbt_pipelines/`.

## 작업 원칙

규칙을 정하거나 바꿀 때는 **작업 분해 → PDCA(Plan-Do-Check-Act)** 순으로 진행하고,
다음 관점을 함께 점검한다:

- 관점: 데이터 파이프라인 / 데이터 사이언스 / 데이터 분석 / 데이터베이스 / 데이터 거버넌스 / 데이터 보안
- 항목: 효율성(efficiency) / 비용(cost) / 위험(risk) / 정확성(accuracy)
