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
| 커밋 메시지 | [`gitlint`](https://jorisroovers.github.io/gitlint/) | `pyproject.toml` `[tool.gitlint]` |
| YAML | [`yamllint`](https://yamllint.readthedocs.io/) | `.yamllint.yaml` (루트) |
| Dockerfile | [`hadolint`](https://github.com/hadolint/hadolint) | `.hadolint.yaml` (루트) |
| 시크릿 스캔 | [`gitleaks`](https://github.com/gitleaks/gitleaks) | `.gitleaks.toml` (루트) |

커밋 전 포매터·린터를 통과시킨다.

### 실행

별도 오케스트레이터 없이 각 린터를 **직접 실행**한다.
(규칙의 단일 출처는 위 표의 "설정 위치"인 도구 네이티브 파일이다.)

```bash
ruff check . && ruff format .        # Python
sqlfluff lint . && sqlfluff fix .    # SQL
yamllint .                           # YAML
hadolint **/Dockerfile               # Dockerfile
gitleaks detect                      # 시크릿 스캔
gitlint                              # 직전 커밋 메시지 검사
```

> 일괄 실행이 필요하면 `pre-commit` 등으로 묶을 수 있다(현재 repo엔 미설정).

### 설정 위치 원칙

- `pyproject.toml`을 지원하는 도구(`ruff`·`sqlfluff`·`gitlint`)는 **`pyproject.toml`에 모은다.**
- 지원하지 않는 도구는 **루트의 도구 네이티브 설정 파일**에 둔다.
  - `yamllint` → `.yamllint.yaml` (pyproject 미지원)
  - `hadolint` → `.hadolint.yaml`
  - `gitleaks` → `.gitleaks.toml`
- 세부 예시는 [Python](python.md) · [dbt](dbt.md) 문서 참고.

## 커밋 메시지 (Git Commit)

- 한국어로 작성한다.
- 형식: **`type: 설명`**

### type 종류

| type       | 용도                 |
| ---------- | -------------------- |
| `feat`     | 새 기능 추가         |
| `fix`      | 버그 수정            |
| `mod`      | 기능 수정(동작 변경) |
| `add`      | 파일·리소스 추가     |
| `del`      | 파일·리소스 삭제     |
| `docs`     | 문서 변경            |
| `refactor` | 리팩터링(동작 불변)  |
| `test`     | 테스트 추가·수정     |

```text
feat: discord 봇 Ollama Cloud 연동 추가
refactor: DuckDB→Trino 전환, SeaweedFS standalone 및 dlt·bronze 리셋
docs: docs 디렉토리에 코딩 규칙 문서 추가
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
