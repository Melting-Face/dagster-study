# Python 코딩 규칙

대상 버전: **Python 3.10 ~ 3.14** (`pyproject.toml`의 `requires-python = ">=3.10,<3.15"`)

## 포매팅 / 린팅

- [`ruff`](https://docs.astral.sh/ruff/)로 lint와 format을 모두 처리한다.
- 들여쓰기 스페이스 4칸.
- 커밋 전 실행:

```bash
ruff format .
ruff check --fix .
```

### 설정은 `pyproject.toml`에서 관리한다

ruff 룰·옵션 명세는 별도 `.ruff.toml`을 만들지 않고 **`pyproject.toml`의 `[tool.ruff]`** 에 둔다.

```toml
# pyproject.toml
[tool.ruff]
line-length = 88
indent-width = 4
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]   # pycodestyle, pyflakes, isort, pyupgrade, bugbear

[tool.ruff.format]
indent-style = "space"
```

## 주석 / 네이밍

- 주석은 **한국어**로 작성한다.
- 식별자(변수·함수·클래스)는 **영어**, `snake_case`(함수·변수) / `PascalCase`(클래스).

## 타입 힌트

- 새 코드에는 타입 힌트를 단다.
- 모던 문법 사용 (3.10+):
  - `list[str]`, `dict[str, int]` (대문자 `List`/`Dict` 지양)
  - `X | None` (`Optional[X]` 지양), `X | Y` (`Union` 지양)

```python
from pathlib import Path


def load_config(path: Path, retries: int = 3) -> dict[str, str] | None:
    # 설정 파일을 읽어 dict로 반환한다. 없으면 None.
    ...
```

## 예외 처리 (LBYL 우선)

- 가능하면 **사전 점검(Look Before You Leap)** 으로 흐름을 명확히 한다.
- 광범위한 `except Exception` 남발을 피하고, 구체적 예외를 잡는다.

```python
# 권장: 사전 점검
if not path.exists():
    raise FileNotFoundError(path)
data = path.read_text(encoding="utf-8")
```

## 파일 경로

- 문자열 경로 조작 대신 [`pathlib.Path`](https://docs.python.org/3/library/pathlib.html)를 사용한다.
  (현 코드도 `definitions.py`에서 `Path(__file__).parent` 사용)

## 의존성 관리

- 패키지 관리는 [`uv`](https://docs.astral.sh/uv/) 사용 (`uv sync`).
- 의존성은 `pyproject.toml`의 `[project].dependencies`에 선언한다.
- **버전 고정(pin)** 을 기본으로 한다. Dagster 관련 패키지는 **버전을 일치**시킨다.

```toml
# 예: dagster 코어/플러그인 버전 일치
dagster        == 1.12.12
dagster-dbt    == 0.28.12
dagster-postgres == 0.28.12
```

- 개발용 의존성은 `[dependency-groups].dev`에 둔다 (`pytest` 등).

## 테스트

- 테스트는 [`pytest`](https://docs.pytest.org/)로 작성하고 `tests/` 하위에 둔다.

## 참고

- ruff: https://docs.astral.sh/ruff/
- uv: https://docs.astral.sh/uv/
- PEP 604 (`X | Y` 타입): https://peps.python.org/pep-0604/
