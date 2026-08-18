# 프로젝트 CLAUDE.md (dagster-study)

## 문서화 원칙

- 이 프로젝트에서 정한 **규칙·결정·작업 패턴은 최대한 문서로 남긴다**.
- 규칙을 새로 정하거나 바꾸면 `CLAUDE.md`·`docs/`·`README.md`를 **함께 갱신**해 단일 출처(single source of truth)를 유지한다.
- `CLAUDE.md`는 핵심 컨벤션의 **요약/인덱스**, 상세 배경·흐름은 `docs/`에 둔다.
- 문서는 한국어로 작성하고, 코드 식별자·명령어·경로는 원문 그대로 표기한다.

## 커밋 컨벤션

- **Conventional Commits**를 따른다. (전역 `CLAUDE.md`와 동일 규약)
- 형식 `type(scope): 설명` — 설명은 한국어, 제목 72자 이내.
- type: `feat`·`fix`·`docs`·`style`·`refactor`·`perf`·`test`·`build`·`ci`·`chore`·`revert`.
- gitlint `contrib-title-conventional-commits`로 강제. 상세·매핑은 [`docs/conventions/general.md`](docs/conventions/general.md).
- **git 워크플로**(브랜치 전략·논리적 커밋 단위·병렬 세션 **git worktree**·AI 세션 git 규칙)는
  [`docs/conventions/git.md`](docs/conventions/git.md). 커밋·푸시는 **사용자 요청 시에만**, 락 파일(`.terraform.lock.hcl`·`skills-lock.json`)은 커밋.

## 코딩 철학

핵심 가치 (상세 [`docs/philosophy.md`](docs/philosophy.md)):

1. **단순함** — 함수+데코레이터, 최소 인프라(YAGNI) *(PEP 20)*
2. **명시적** — 선언적 설정, 규칙은 문서로 *(PEP 20)*
3. **가독성** — 관심사 분리, 일관 네이밍, 포매터 고정 *(PEP 20)*
4. **비밀정보는 참조로** — 환경변수/시크릿 비노출 *(12-Factor Config)*
5. **재사용은 3회부터 추출** — 3회 이상 반복 시 함수화/상수화 *(Rule of Three / DRY)*
6. **추적 용이성** — wiring 집중·named constant·명시 정의로 grep/점프 용이, 단순 리턴은 인라인 *(Locality of Behaviour)*

## Python 코딩 컨벤션

상세 [`docs/conventions/python.md`](docs/conventions/python.md).

### `scripts/` 스크립트는 절차형으로 쓴다

- 실행형 유틸리티(`scripts/`)는 **호이스팅은 적용**(선언은 상단·진입은 하단), **캡슐화·함수화는 최소화**한다
  → 클래스 없이, 보조 함수로 쪼개지 않고 **하나의 `main()`** 에서 위→아래로 실행한다.
- 이유: **가독성 / Locality of Behaviour** — 스크립트는 재사용 단위가 아니라 **실행 순서 = 읽는 순서**가 명확할 때 최선.
  단, **Rule of Three(3회 이상 반복)** 는 유효하며, 라이브러리·에셋 코드(`common/`·`defs/`)에는 적용하지 않는다(관심사 분리·명시적 함수 유지).
- 외부 의존성은 **PEP 723 인라인 메타데이터**로 선언하고 `uv run <script>.py`로 실행한다. `scripts/**`는 ruff **C901 면제**.

## Dagster 코딩 컨벤션

### 에셋 생성은 클래스화를 지양한다

- Dagster 에셋은 **함수 + 데코레이터**(`@asset`, `@multi_asset`, `@dbt_assets`)로 정의한다.
  클래스 기반 정의나 커스터마이징을 위한 **불필요한 서브클래싱은 지양**한다.
- 커스터마이징이 필요하면 **선언적 설정**(데코레이터 인자, 메타데이터, dbt config 등)을 우선한다.
  - 예: dbt 에셋의 group은 `DagsterDbtTranslator` 서브클래스 대신
    dbt 모델/프로젝트의 config(`meta.dagster.group` 또는 `+group`)로 선언한다.
- 이유: 가독성·테스트 용이성·낮은 결합도. 함수형 정의가 Dagster의 권장 패턴이며 보일러플레이트가 적다.

### 각 에셋은 명시적으로 분리 정의한다

- 에셋은 **팩토리로 동적 생성하지 않고** 각각 `@asset` 함수로 **명시적으로 정의**한다.
  → 에셋 이름으로 바로 검색/점프(탐색성), per-asset 커스터마이징(deps·partition·description·automation)이 자연스럽다.
- 공통 처리 로직은 일반 함수(`common.helper`)로 분리해 재사용하되(DRY), **에셋 정의 자체는 분리·명시**한다.
- 에셋은 **데이터셋별 서브프로젝트 단위로 분리 관리**한다(`defs/<dataset>/assets.py`).
- **`@dg.definitions`는 `@asset`이 있는 모듈에 두지 않는다** — 같이 두면 그 반환값이 모듈 정의를 대체해
  **모듈 스코프 `@asset`이 조용히 누락**된다. 리소스 등록은 `resources.py`처럼 자산 없는 모듈에 두고,
  정의 추가 후 `dg check defs`로 자산 수를 확인한다. 상세 [`docs/conventions/dagster.md`](docs/conventions/dagster.md).

## 프로젝트 구조 컨벤션

### 공통 라이브러리(`common/`) + 자동발견 정의(`defs/`)

- **공통 재사용 로직**은 `dagster_project/common/`에 둔다(데이터셋 무관 공통 라이브러리, `defs/` 밖).
  - `constants.py` — 공통 상수/기본값(S3 파라미터 포함)
  - `helper.py` — 적재 헬퍼(`read_csv_gz_table` 일반 / `load_heavy_csv_gz_to_iceberg` 대용량)
  - `dbt.py` — 공유 dbt 설정(`DbtProject`·`build_dbt_resource`); 단일 dbt 프로젝트를 데이터셋 subproject가 공유
  - `trino.py` — Trino 접속 리소스(`TrinoResource`); Iceberg 유지보수 프로시저(`remove_orphan_files`) 실행용
- **정의는 모두 `dagster_project/defs/` 하위**에 두고 `load_defs`가 재귀 자동발견한다.
  - **데이터셋별 서브프로젝트** `defs/<dataset>/`에 **정의만** 둔다.
    - `constants.py` — 데이터셋 전용 `NAMESPACE`·`GROUP_NAME`·`SOURCE_BASE`
    - `assets.py` — 테이블별 **명시적 `@asset`**(bronze 적재; 모듈 스코프라 자동 수집)
    - `dbt_assets.py` — 데이터셋 dbt 모델 소유(`@dbt_assets(select="fqn:<dataset>", project=dbt_project)`)
  - `defs/resources.py` — 공유 리소스(S3·dbt·IO 매니저·테이블 바인딩)를 `@dg.definitions`로 제공. Iceberg 카탈로그 설정(`IcebergCatalogConfig`)은 별도 빌더 없이 **각 리소스에 인라인**해 한 파일에서 전체를 파악한다(적은 파일로 파악).
  - `defs/automation.py` — 잡·스케줄(모듈 스코프 객체라 자동 수집)
- **wiring은 최상위 `definitions.py` 한 곳**에서 `defs = load_defs(dagster_project.defs)`로
  자동발견 결과를 **단일 `Definitions`**로 합친다(중간 definitions 레이어 없음, 모듈 스코프 `Definitions` 1개).

### S3 → Iceberg 적재 (리소스 기반, 2경로)

- S3/Iceberg 연결은 **Dagster 리소스로 관리**한다: `dagster-aws` `S3Resource` + `dagster-iceberg`(IO 매니저·`IcebergTableResource`). 연결을 자산이 아닌 리소스에 둔다.
- **일반(부하 없는) 파일**: 자산이 `pa.Table` 반환 → **dagster-iceberg IO 매니저**가 자동 create+적재.
- **대용량 파일(예: 3.3GB)**: boto3 스트리밍 + **청크 append**(`load_heavy_csv_gz_to_iceberg`, IO 매니저 미사용 — 전량 메모리 적재 금지). 대상 테이블용 `IcebergTableResource`는 `defs/resources.py`에 추가한다.
- **메타스토어를 두지 않는다**: Trino와 동일한 Iceberg JDBC 카탈로그를 재사용한다.
- **dbt 미생성 테이블(=Dagster 적재분)은 dbt `source()`로 참조**한다. source는 데이터셋별
  `models/<dataset>/source.yml`에 두고 `meta.dagster.asset_key`로 Dagster 자산키와 매핑해 lineage를
  연결한다. 메달리온 레이어는 스키마 접두어가 아닌 **kind(Dagster)/tag(dbt)** 로 표기한다.
  상세 [`docs/conventions/dbt.md`](docs/conventions/dbt.md).
- **`@dbt_assets` 셀렉터는 `select="fqn:<dataset>"`** 를 쓴다(`project=dbt_project` 동반).
  `path:models/<dataset>`는 cwd 글롭이라 정의 로드 시 모델이 수집되지 않는다(잠복 버그).
- **어댑터 방언은 매크로로 흡수**한다(`dbt-trino`↔`dbt-spark` 이행 대비) — 엔진 리터럴을 직접 쓰지 않는다.
  **의미론이 같으면 dbt 내장**(`{{ dbt.dateadd(...) }}`), **갈리거나 내장이 없으면 프로젝트 dispatch 매크로**
  (`macros/cross_engine.sql`의 `elapsed`·`unnest_array`, `default__`에 `raise_compiler_error`).
  🔴 **`dbt.datediff`는 쓰지 않는다** — Spark는 경과시간 `ceil`, Trino는 경계 교차라 임계값 비교에서 값이 갈린다.
  기준은 "도는 것"이 아니라 **"같은 값"**. `dbt compile`은 이를 못 잡으므로 **컴파일 통과를 이행 완료로 읽지 않는다**.
- **데이터셋 원천 스키마·피처(SOFA→Sepsis-3)** 는 [`docs/dataset_schema.md`](docs/dataset_schema.md) 참고.
- 자세한 흐름·사용법은 [`docs/architectures/overview.md`](docs/architectures/overview.md) 참고.

### 머티리얼라이즈 메타데이터를 남긴다

- 적재/변환 에셋은 관측 메타데이터(행 수·미리보기 등)를 남긴다.
  일반 경로(`pa.Table` 반환)는 `context.add_output_metadata(...)`, 대용량 경로는
  `MaterializeResult(metadata=...)`. 상세 [`docs/conventions/dagster.md`](docs/conventions/dagster.md).

## 테스트 컨벤션

- 테스트는 **계층별 우선순위**로 채운다: dbt 스키마 테스트 → 통합·스모크(`dg check`·`dbt build`)
  → dbt 단위 테스트 → Dagster 에셋 pytest → dbt singular. **비용 대비 회귀 방어가 큰 순서**.
- dbt 테스트는 모델 옆 `schema.yml`(`data_tests:`/`unit_tests:`), Dagster 테스트는 `src/tests/`(`pytest`).
  **단위 테스트는 실인프라(SeaweedFS·Trino) 미접속**(격리·재현). 상세·예시는 [`docs/test.md`](docs/test.md).

## 타임존 정책

- **저장은 UTC**(Iceberg·Postgres), **표시·스케줄은 KST**(`Asia/Seoul`).
- `datetime`은 tz-aware(`tz=timezone.utc`)로 생성(ruff `DTZ`), 스케줄은 `execution_timezone="Asia/Seoul"` 명시,
  컨테이너는 `TZ=Asia/Seoul`. 상세 [`docs/conventions/timezone.md`](docs/conventions/timezone.md).

## 운영 (operations)

- **환경변수는 참조로 주입**(`dg.EnvVar`/`os.environ`), 하드코딩 금지. 추가 시
  `.env`→`compose.yml`(공용 앵커 `x-dagster-common`)→코드 **전파 체인**을 확인한다.
  Iceberg snapshot·로그 보존 정책 포함 [`docs/operations.md`](docs/operations.md).
- **Docker/Compose 규칙**: 로깅·env YAML 앵커, 이미지 `latest` 금지, healthcheck + `depends_on`,
  전 서비스 `deploy.resources` 명시. **옵션 기능(모니터링)은 `profiles`로 분리**(뼈대는 profile
  없이 항상 실행, `--profile <name>`으로 opt-in). 상세 [`docs/conventions/docker.md`](docs/conventions/docker.md).
- **로컬 K8s(현행 검증 환경)**: **kind on Podman**(rootful 머신 필수) 클러스터 `lakehouse` +
  로컬 레지스트리 `localhost:5001`. 기동은 `scripts/k8s-up.sh` → `k8s-operators.sh` → `k8s-poc-storage.sh`
  (설정 단일 출처 `scripts/k8s-env.sh`). Dagster는 **호스트 유지**, 컴퓨트·스토리지만 클러스터에 둔다.
  규칙 [`docs/conventions/k8s.md`](docs/conventions/k8s.md), 예산·배분 [`docs/resource-sizing.md`](docs/resource-sizing.md).
  클러스터에는 **Spark Operator**(배치)·**Flink Operator**(스트림)·**Spark Connect**(dbt-spark 접속용 상주)가 있고,
  Spark·Flink가 **같은 Iceberg JDBC 카탈로그**를 공유한다. 버전은 **엔진 최신이 아니라 Iceberg가 지원하는 짝**으로
  고정한다(예: `iceberg-flink-runtime`이 2.1까지라 Flink는 2.1). Spark Connect는 유일한 상주 컴퓨트라
  미사용 시 `--replicas=0`으로 내린다.
  **Iceberg 카탈로그 이름은 전 엔진 `iceberg`로 통일**한다 — JDBC 카탈로그는 `catalog_name`으로 레지스트리를
  분할해, 이름이 다르면 같은 DB를 봐도 서로의 테이블이 안 보인다. 또 **SeaweedFS는 AWS SDK의 aws-chunked
  체크섬을 못 풀어** 객체가 조용히 손상되므로 `AWS_REQUEST_CHECKSUM_CALCULATION=when_required`를 유지한다.
  **노출은 HTTP UI만 Ingress**(ingress-nginx, `*.localtest.me:8080`)로 내고 gRPC·JDBC·S3는 `port-forward`를 쓴다 —
  kind는 **공개 포트를 클러스터 생성 시점에만** 정할 수 있어 `extraPortMappings`를 빠뜨리면 재생성이 유일한 해법이다.
  컴퓨트 **러너 이미지는 로컬 레지스트리에 직접 push**하고(`kind load` 불필요) **태그와 매니페스트를 함께 올린다**.
- **Terraform/IaC 규칙**: 스택 단위 `terraform/<stack>/`, 버전 고정 + `.terraform.lock.hcl` 커밋, 포매터는
  **`terraform fmt`(2-space, 4칸 규칙의 예외)**, `*.tfstate`·`terraform.tfvars`·개인키 **커밋 금지**,
  부트스트랩은 **cloud-init 선언형**. 첫 스택 [`terraform/oci-k3s/`](terraform/oci-k3s/README.md)(OCI A1+k3s)는
  **⏸ 보류**(A1 용량 부족 — 네트워크 5종만 생성됨·과금 0, **state 유지**).
  상세 [`docs/conventions/terraform.md`](docs/conventions/terraform.md), 현황·재개 [`docs/architectures/oci.md`](docs/architectures/oci.md).
- **처리·배포 기술 비교**: 각 기술(trino·docker·spark·flink·k8s·oci)을 **프로젝트 결정 관점**(채택 이유·
  대안 비교)으로 [`docs/architectures/`](docs/architectures/README.md)에 정리(채택 ✅ / 미채택 🔎).
- **Claude Code 스킬**: 프로젝트가 쓰는 Agent Skills와 사용 규칙(**프로젝트 컨벤션 우선**)은
  [`docs/skills.md`](docs/skills.md), 단일 출처는 [`skills-lock.json`](skills-lock.json).
- **에이전트 오케스트레이션·기록관**: AI 세션을 **3계층(supervisor→director→subagent)** 으로 나눈다(**director는 우선 1명**,
  도메인 무관). **director는 업무 성격에 따라 워커를 배정·감독**하고, **권한 밖(비가역·비용·규약변경·범위 밖)이나 특이사항(드리프트·결과충돌·반복실패·비승인변경)은 supervisor에 에스컬레이션**해 **진행 여부를 supervisor가 결정**한다. subagent 실행은 director **승인 게이트**를 거친다. **`security`·`archivist`는 director 관할 밖**(supervisor가 직접 배정)이며, **director의 실행·채택 결정은 `security` 최종 컨펌 후 진행**한다(동일 결정 재컨펌 2회 초과 시 에스컬레이션). 미션 저널의 **기록 주체는 `archivist`** — supervisor가 **체크포인트마다** 이벤트를 전달해 기록시키고(경합 방지 single-writer 유지), 호출 실패·세션 급종료 시에만 supervisor가 **폴백**으로 직접 쓴다. "누가 무엇을 왜
  했는가"와 **계층 간 상호작용(배정·보고·질의·반려·승인)**·실행 `agent`/`model`을 **기록관 저널**로 남긴다. 저널은 개인 Obsidian 볼트
  **`$OBSIDIAN_VAULT`(기본 `~/obsidian`, 환경마다 다를 수 있음)** 의 `agents/<YYYY-MM-DD>/<NN>-<mission>.md`(NN=그날 착수 순번)
  (작업일자별·미션당 1파일, 계층 섹션 누적)에 쌓으며 **저장소 커밋 대상 아님**.
  **기록 시점(필수)**: ① 미션 개시 시 파일 생성 ② 계층 간 이벤트 직후 상호작용 로그 append ③ 서브에이전트 결과 수령 직후
  계층 섹션 기록 ④ **사용자 최종 보고 직전** 취합·`status`/`updated` 갱신 ⑤ 세션 종료·컨텍스트 요약 직전 현재 상태 저장.
  **미션 판단**: 파일 생성·수정 / 위임 발생 / 결정·합의 / 비가역 작업 중 하나면 저널을 연다(단순 조회·질의응답은 제외).
  누락 보정·수동 기록은 **`/journal`** 슬래시 커맨드. 전문 워커는 **`security`**(보안 점검) + 데이터·인프라 **각 3종 세트**로,
  **같은 축**(구현 / 실측 대조 / 체계 감사)을 공유한다 — 데이터는 **`data-engineer`·`data-verifier`·`data-qa`**,
  인프라는 **`devops-engineer`·`devops-verifier`·`devops-qa`**. **판정자(`*-verifier`·`*-qa`·`security`)는 읽기 전용**으로
  발견만 반환하고, 구현 워커(`*-engineer`)만 쓰기를 갖되 비가역 작업(커밋·`terraform/kubectl apply`·`compose down -v`·
  파괴적 변경)은 계획만 반환한다. `security`(노출·규제) ↔ `devops-qa`(운영 신뢰성·재현성) 관점 분리.
  서브에이전트를 호출하면 **실행 메타**(`subagent_type`·`agent`/`model`·허용 도구·도구 호출 수·토큰·소요·승인 결과)와
  **경계 준수 여부**를 저널에 남긴다(수치 없으면 `미측정` — 추정치 금지).
  저널 **`NN` 넘버링은 hook이 강제**한다(`scripts/journal_guard.py` + `.claude/settings.json`) — `SessionStart`가 다음 번호·열린 미션을 주입하고, `PreToolUse(Write)`가 중복·규약 위반 생성을 차단하며, `Stop`이 저널 누락을 경고한다. 착수 순번의 판정 기준은 **본문 상호작용 로그의 첫 이벤트**.
  **워커 경계의 실효 강제는 `permissions` 규칙**이다(프론트매터 `tools`·경계 지시문은 난이도·규율일 뿐).
  `deny` > `ask` > `allow` 순으로 **auto 모드 분류기보다 먼저** 평가되고 **서브에이전트에도 동일 적용**된다 —
  비가역 작업(git 커밋·푸시, `terraform/kubectl apply`, `compose down -v`, `dbt --full-refresh`, `DROP`/`TRUNCATE`,
  `.env`·`tfstate` 수정, 외부 발신)은 `ask`로 못 박는다. `allow`에 비가역 명령을 넣지 않는다.
  상세 [`docs/conventions/agents.md`](docs/conventions/agents.md).
- **리소스 산정**: `max_concurrent_runs`↔daemon `memory` 결합(CoW OOM), Trino 3파일 메모리 제약.
  상세 [`docs/resource-sizing.md`](docs/resource-sizing.md).
- **보안·데이터 거버넌스**: 원천 진료 데이터·`.env`·크리덴셜은 **저장소 커밋 금지**(비식별 연구
  데이터셋 + DUA). ISMS-P 인증기준(101)·의료데이터 보안 규제와 현행 통제 매핑·미비점(TODO)은
  [`docs/security.md`](docs/security.md).
