"""코드 로케이션 진입점 — `defs/` 패키지를 자동발견해 단일 Definitions로 합친다.

에셋·리소스·잡·스케줄 정의는 모두 `dagster_project/defs/` 하위에 둔다.
- 데이터셋별 서브프로젝트(`defs/<dataset>/`): bronze `@asset`·`@dbt_assets`
- 공유 리소스(`defs/resources.py`): `@dg.definitions`로 리소스 Definitions 제공
- 잡·스케줄(`defs/automation.py`): 모듈 스코프 객체
`load_defs`가 위를 재귀 수집·merge한다. 공통 라이브러리(`common/`)는 defs 밖에 둔다.
모듈 스코프 Definitions는 `defs` 1개(autodiscovery 제약).
"""

import dagster_project.defs
from dagster import load_defs

defs = load_defs(dagster_project.defs)
