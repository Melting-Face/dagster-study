# 보안·데이터 거버넌스 (security)

> **목적**: 이 프로젝트의 보안 통제를 **ISMS-P 인증기준**과 **의료데이터 보안 규제**에 매핑해
> 한 곳에서 파악한다. 현행 통제·미비점(TODO)을 함께 남겨 단일 출처를 유지한다.
> **언제 읽나**: 보안 통제 추가·점검, 데이터 취급 정책 결정, 실서비스 확장 검토 시.
> **연관**: [conventions/general.md](conventions/general.md)(비밀정보), [operations.md](operations.md)(환경변수·보존정책), [conventions/docker.md](conventions/docker.md), [dataset_schema.md](dataset_schema.md).

## 0. 전제 — 이 프로젝트의 데이터 성격 (중요)

이 저장소는 **비식별(de-identified) 연구용 공개 데이터셋**([MIMIC-IV](https://physionet.org/content/mimiciv/) ·
[eICU-CRD](https://physionet.org/content/eicu-crd/))를 학습 목적으로 다룬다. 두 데이터셋은 미국
**HIPAA Safe Harbor** 기준(18개 식별자 제거·진료일자 이동)으로 비식별되었고, **PhysioNet
Credentialed Health Data License + DUA**(데이터 이용 협약, 재식별 시도 금지·인증 교육 이수)로 배포된다.

따라서 이 프로젝트는 국내 **개인정보/의료데이터 처리 의무 주체가 아니며**, 원천 데이터에는
직접 식별정보가 없다. 다만 아래 두 가지 이유로 ISMS-P·의료데이터 보안 통제를 **매핑·문서화**한다.

1. **DUA 준수 의무** — 재식별 금지·크리덴셜 관리·원천 데이터 비공개는 협약상 실제 의무다.
2. **학습·확장 대비** — 향후 실제 (가명)의료데이터를 다루는 파이프라인으로 확장할 때 통제 공백을
   미리 식별한다. 국내법상 MIMIC/eICU 같은 연구용 데이터는 **개인정보보호법 제28조의2(가명정보의
   처리 특례 — 과학적 연구)** 범주에 대응한다.

> **철칙(governance)**: 원천 진료 데이터(csv.gz)·`.env`·크리덴셜은 **공개 git 저장소에 커밋하지 않는다.**
> 데이터는 SeaweedFS(오브젝트 스토리지)에만 두고, 저장소에는 코드·스키마·문서만 둔다.

## 1. 규제·표준 개요

### 1-1. ISMS-P (정보보호 및 개인정보보호 관리체계 인증)

개인정보보호위원회·과학기술정보통신부가 운영하고 KISA가 심사하는 국내 통합 인증제도.
**2023.11 개정 인증기준** 기준 3개 영역 **101개 인증기준**으로 구성된다.

| 영역 | 인증기준 수 | 세부항목 | 내용 |
| --- | --- | --- | --- |
| 1. 관리체계 수립 및 운영 | 16 | 42 | 관리체계 기반·위험관리·운영·점검개선(라이프사이클) |
| 2. 보호대책 요구사항 | 64 | 195 | 12개 분야: 정책·조직·인적·물리·인증권한·접근통제·암호화·개발보안·운영·사고대응·재해복구 |
| 3. 개인정보 처리 단계별 요구사항 | 21 | 91 | 수집·보유이용·제공·파기·정보주체 권리 등 생명주기별 보호조치 |

> ISMS(정보보호)와 ISMS-P(정보보호+개인정보)로 나뉘며, 개인정보를 다루면 영역 3까지 포함하는 ISMS-P가 대상.

### 1-2. 의료데이터 보안 관련 법·가이드라인

| 근거 | 핵심 요지 | 이 프로젝트 관련성 |
| --- | --- | --- |
| **개인정보보호법 제28조의2** (가명정보 처리 특례) | 통계작성·**과학적 연구**·공익적 기록보존 목적은 정보주체 동의 없이 가명정보 처리 가능 | 연구용 MIMIC/eICU 활용의 국내 대응 근거 |
| **개인정보보호법 제28조의4** (안전조치의무) | 추가정보(복원키)를 **분리 보관·관리**, 기술적·관리적·물리적 안전조치 | 크리덴셜/재식별키 분리, 접근통제 원칙 |
| **개인정보보호법 제28조의5** (금지의무) | 특정 개인을 알아보기 위한 가명정보 처리 **금지**(재식별 금지) | DUA의 재식별 금지 조항과 정합 |
| **보건의료데이터 활용 가이드라인** (개인정보위·보건복지부) | 보건의료 가명정보 처리 절차·심의(DRB)·안전조치. 2020.9 최초 → 2022.1·2024.1 개정 → **2025.12.31 시행**(공용 DRB 도입·비정형 의료데이터 가명처리 구체화) | 의료데이터 가명처리 절차의 국내 표준 |
| **HIPAA Safe Harbor** (미국) | 18개 식별자 제거 시 비식별로 간주 | MIMIC/eICU 비식별의 실제 근거 |
| **PhysioNet Credentialed License · DUA** | 인증 교육 이수·재식별 금지·데이터 재배포 제한 | 데이터 접근·취급의 실제 계약상 의무 |

## 2. ISMS-P 인증기준 ↔ 현 프로젝트 통제 매핑

현행 구현을 대표 인증기준에 매핑한다. **상태**는 ✅ 구현 / 🟡 부분 / ⬜ 미구현(TODO).
경로·식별자는 원문 표기.

### 2-1. 영역 2 — 보호대책 요구사항

| 인증기준(분야) | 현 프로젝트 통제 | 상태 | 미비점·TODO |
| --- | --- | --- | --- |
| **2.5 인증 및 권한관리** | (study 단일 사용자) 서비스 계정은 `.env` 크리덴셜로 분리. **OCI API 키는 로컬 생성·공개키만 업로드**, SSH 키는 **용도별 분리**, k3s kubeconfig `600` | 🟡 | Trino·Dagster·SeaweedFS **RBAC/최소권한** 미문서화. **k3s 클러스터 RBAC**(기본 cluster-admin 단일 kubeconfig) 미분리 |
| **2.6 접근통제** | 내부 네트워크(compose)로 서비스 격리, 비밀 설정 `:ro` 마운트([philosophy #4](philosophy.md)). **OCI 공개 노드**는 Security List `/32` 화이트리스트(SSH 22·API 6443, `0.0.0.0/0`은 `validation`으로 차단) + 호스트 iptables([terraform.md](conventions/terraform.md)) | 🟡 | 카탈로그 PG 3종 서비스(`-rw`/`-ro`/`-r`)는 **전부 ClusterIP·Ingress 없음** 확인(2026-08-19), 단 **`NetworkPolicy` 부재**로 클러스터 내 임의 파드가 5432에 도달 가능. 관리 UI(SeaweedFS·Dagster·**Flink**) **포트 노출** 범위 점검·인증 필요 — 🔴 **Flink Web UI가 Ingress로 무인증 노출**되고 **jar 제출까지 열려 있다**(2026-08-22, 아래 §2-1 보강). 호스트 iptables의 **kubelet 10250이 소스 무제한**(SL이 앞단 방어) — 방어 심화 필요 |
| **2.7 암호화 적용** | 비밀정보 **하드코딩 금지·참조 주입**(`dg.EnvVar`/`${ENV:...}`), `.env` gitignore ([general.md](conventions/general.md#비밀정보-secrets)). 개인키·`*.tfstate`·`*.tfvars`·회수 kubeconfig는 **gitignore + 권한 600**. **카탈로그 PG 전송구간은 CNPG가 자체 CA·서버 인증서를 생성해 TLS 1.3 가능**(2026-08-19 실측 `ssl_min/max_protocol_version=TLSv1.3`). 🔴 **크리덴셜의 SQL DDL 기재 금지에 조건부 예외 1건**(Iceberg **JDBC 카탈로그** `CREATE CATALOG` — 환경변수 자격증명 체인이 없어 회피 불가). **5개 조건을 전부 충족할 때만** 허용하며 정본은 [k8s.md §9-2](conventions/k8s.md)다 — 여기 중복 서술하지 않는다 | 🟡 | **저장 암호화(at-rest)** 미설정(SeaweedFS·Postgres·Iceberg). 🔴 카탈로그 PG가 `emptyDir`(휘발)에서 **영속 PVC**(호스트 디스크·비암호화)로 바뀌어 at-rest 미설정이 **실질 리스크로 승격**(2026-08-19). 클라이언트 `sslmode` 강제는 미확인. S3 endpoint `http://`(내부 평문). `tfstate` **원격 백엔드+암호화** 미도입 |
| **2.8 정보시스템 도입 및 개발 보안** | pre-commit **gitleaks** 시크릿 스캔 + **`detect-private-key`**(gitleaks가 못 잡는 키 파일 2차 방어)·`ruff`(bandit `S` 룰 포함)·`sqlfluff`·`shellcheck`·**`hadolint` 실배선**(2026-08-21 — 이전엔 설정만 있고 훅이 없었다), 이미지 `latest` 금지([docker.md](conventions/docker.md)). **에이전트 스킬은 출처 등급별 통제 + 보호 경로 `ask`**([skills.md](skills.md) §출처 등급별 통제) | 🟡 | 의존성 취약점 스캔(SCA) 미도입. 🔴 **모든 게이트가 로컬 pre-commit뿐이라 `--no-verify`·훅 미설치 클론으로 전량 우회**된다(서버측 CI 게이트 0개). 🔴 **`.gitleaks.toml`의 allowlist `'''x{4,}'''` 가 과대** — 4자 이상 `x` 연속을 포함하면 **실제 시크릿도 면제**될 수 있다(미해소). 🔴 **에이전트 스킬 공급망**: 스킬은 **에이전트 실행 컨텍스트에 주입되는 외부 코드**이고 **실행 파일을 포함할 수 있다**(과거 설치본에 실재했다 — 현 설치분 기준 **0건**, 2026-08-22 실측 `find -L .claude/skills -type f -perm -u+x`. 🔴 이 값은 설치할 때마다 바뀌므로 **등재 시마다 다시 잰다**). 그런데 `gitleaks`·`ruff`·`hadolint` **어느 것도 스킬 설치 경로를 스캔하지 않는다** — 🔴 **경로는 둘 다 봐야 한다**: `.claude/skills/`와 `.agents/skills/`. 전자의 엔트리 일부가 후자를 가리키는 **스킬 단위 심볼릭 링크**라(디렉터리 단위가 아니다) **한쪽만 스캔하거나 링크를 따라가지 않으면 대상이 조용히 빠진다.** 🔴 **세 축을 섞지 않는다** — 🔒(무결성 고정) ↔ **출처 등급**(A~D) ↔ **로컬 검증 가능성**은 서로 독립이다(`find-skills`는 🔒·B등급이면서 `computedHash`가 blob 경로라 **로컬 재현 불가**). ⇒ **🔒를 "안전함"으로도 "검증됨"으로도 읽지 않는다.** 🔴 **종수·등급 분포·고정 비율의 수치는 여기 적지 않는다** — 정본은 [skills.md](skills.md)이며 **수치를 옮기지 말고** 그 문서 §재측정 방법의 명령으로 **그 자리에서 다시 잰다**(과거 이 자리의 `3/24 = 12.5%`는 분자가 lock 파일·분모가 디스크 설치라 **단위가 어긋난 수치**였고, 분모의 모집단인 전역 경로는 이후 소멸했다). 현 시점 **미고정 0건**이나 **C등급 잔여**가 있어 위험이 0인 것은 아니다 — 등급 분포도 정본에서 읽는다. 🔴 **이미지 태그 갱신 방치**(Prometheus): `compose.yml`의 `prom/prometheus:v2.21.0`은 **태그 고정 요건([docker.md](conventions/docker.md) §1-3)은 충족**하나 **갱신된 적이 없고 예외를 정당화한 문장도 없다** — `seaweedfs`는 태그 예외 근거가 명문화됐지만(`8e1c088`) 이쪽은 없다. 보안 축의 실질은 **알려진 취약점 미패치 가능성**이며, 버전 격차 수치는 여기 적지 않고 [architectures/monitoring.md](architectures/monitoring.md)에서 관측 시각과 함께 읽는다 |
| **2.9 시스템 및 서비스 운영관리** | Docker 로그 보존(`max-size 10m × 20`), healthcheck+`depends_on`(**일부 서비스만**), `deploy.resources` 명시(전 서비스) | 🟡 | 🔴 **적용 범위가 통제 선언에 못 미친다**(2026-08-22 실측): compose `healthcheck:`는 **6개 서비스 중 2개**뿐(`:90` postgres · `:136` trino — 나머지 `dagster-webserver`·`dagster-daemon`·`seaweedfs`·`prometheus` 없음), `prometheus`의 `depends_on`(`:196-197`)은 **조건(`condition:`) 없는 구식 리스트**라 기동 순서만 걸고 준비 상태를 보지 않는다. 관측 수단 부재가 *결정*인지 *누락*인지 선언된 바 없다 — 실태는 [architectures/monitoring.md](architectures/monitoring.md), 등록 의무 규칙은 [conventions/monitoring.md](conventions/monitoring.md) §1. 🔴 **이 문장을 "compose의 `depends_on`에 조건이 없다"로 일반화 인용하지 마라** — 조건 없는 구식 리스트는 **`prometheus` 1건뿐**이고, `dagster-webserver`·`dagster-daemon`(공용 앵커 `x-dagster-common` 경유)·`trino` **3개는 이미 `condition:` map**이다(2026-08-22 실측). 실제로 그렇게 일반화 인용된 적이 있다. `healthcheck` "6개 중 2개"의 **모집단은 전체 6개**(opt-in profile 3종 포함)이며 **core 3개(`dagster-webserver`·`dagster-daemon`·`postgres`)로 좁히면 1/3**이다 — 모집단을 밝히지 않으면 두 값이 서로를 반박하는 것처럼 보인다 |
| **2.10 시스템 및 서비스 보안관리** | UTC 저장/KST 표시로 **로그 타임스탬프 일관성**([timezone.md](conventions/timezone.md)) | 🟡 | 중앙 **감사 로그(접속기록)** 수집·보관 미설정 |
| **2.11 사고 예방 및 대응** | — | ⬜ | 침해 대응 절차·알림(모니터링) 미정의. 🔴 **알림 경로 0건이 실측으로 확인**됐다(2026-08-22 — Alertmanager·`rule_files`·Dagster sensor·`@asset_check` 전부 0건). 관측 실태 인벤토리는 [architectures/monitoring.md](architectures/monitoring.md), 관측 수단 등록·생존 확인 **규칙**은 [conventions/monitoring.md](conventions/monitoring.md) — ⚠️ 문서가 생긴 것이 통제가 생긴 것은 아니므로 상태는 ⬜ 유지 |
| **2.12 재해복구 및 업무연속성** | 카탈로그 Postgres가 **CloudNativePG 관리**로 바뀌며 백업 **경로는 확보**(Barman Cloud 플러그인) | ⬜ | **여전히 미활성**(`INSTALL_CNPG_BACKUP=false` 기본 + cert-manager 부재). 🔴 계획된 백업 대상(클러스터 내부 SeaweedFS)은 **같은 장애 도메인**이라 DR이 아니다 — 논리 오류 복구용. SeaweedFS 백업 정책은 여전히 미설정 |

#### 🔴 2-1 보강 — Flink Web UI 무인증 노출과 **조건의 철회** (2.6, 2026-08-22)

`k8s/flink/flinkdeployment-session.yaml`이 오퍼레이터 네이티브 `spec.ingress`로 Web UI를
**`flink.localtest.me`** 에 낸다. **인증이 없다.** 그리고 🔴 **`web.submit.enable`이 기본값 `true`로
유지**되므로 **jar 업로드 = 클러스터 내 임의 코드 실행**이다.

🔴 **이 상태는 `security` 조건이 반영된 결과가 아니라 「사용자 결정에 의한 철회」다.**
원안은 `web.submit.enable=false`(조건 C7)였고 근거가 위 실행 경로였는데,
사용자 지시(*"flink 동작도 확인할 수 있게 켜놔줘"*)로 **제출까지 켜두기로 결정**됐다.

> ⚠️ **결정 전에 전달된 사실**: `web.submit.enable=false`여도 **UI 조회는 전부 된다** —
> 잡 목록·상태·메트릭·로그·체크포인트·백프레셔. 꺼지는 것은 **jar 업로드 제출**과 **취소 버튼**뿐이다.
> **그럼에도 켜두는 것으로 결정**됐다.
>
> 🔴 이 문단을 *"C7이 반영됐다"* 로 읽지 않는다. **조건은 걸려 있지 않다** — 안 적으면
> 다음 사람이 걸려 있다고 믿는다.

| 축 | 내용 |
| --- | --- |
| 완화 요인 | `kind-cluster.yaml`의 `listenAddress: "127.0.0.1"` ⇒ **LAN에서 도달 불가** |
| ⚠️ 그러나 없는 위험이 아님 | `localtest.me`는 **공개 DNS가 127.0.0.1로 응답**한다 ⇒ 웹 페이지가 로컬로 POST를 던지는 **CSRF 계열 시나리오는 성립**한다 |
| 수용 근거 | **로컬 단독 개발 환경**이라 수용한 것이다(실서비스·공유 환경으로 나가면 즉시 재검토) |
| ✅ 회수 | 검증 후 **세션 클러스터를 내렸다**(2026-08-22) — UI는 **상시 노출이 아니다** |

⇒ 위 표 **2.6**의 TODO *"관리 UI 포트 노출 범위 점검·인증 필요"* 에 **Flink가 추가**된다.
재기동해 상주시키기로 하면 이 항목이 **미결 상태 그대로** 살아난다.

### 2-2. 영역 3 — 개인정보 처리 단계별 (연구 데이터 대응)

| 인증기준 | 현 프로젝트 통제 | 상태 | 미비점·TODO |
| --- | --- | --- | --- |
| **3.1 수집 시 보호조치** | 비식별 데이터만 수집(원천이 이미 Safe Harbor 비식별) | ✅ | 원천 데이터 **저장소 커밋 금지** 규칙 준수(§0 철칙) |
| **3.2 보유 및 이용 시 보호조치** | 데이터는 SeaweedFS에만 상주, 코드/문서와 분리 | 🟡 | 접근기록(누가 조회) 로깅 미설정 |
| **3.4 파기 시 보호조치** | Iceberg **스냅샷 만료 + orphan 정리 잡**(주간 스케줄, [defs/maintenance.py](../dagster/dockerfile.d/src/src/dagster_project/defs/maintenance.py)) | 🟡 | 보존기간(기본 7일)·대상 테이블 범위 확정 필요([§4-1](#4-todo-실행-절차)) |

> **재식별 금지(제28조의5·DUA)**: 어떤 파이프라인·분석도 특정 개인 재식별을 시도하지 않는다.
> 외부 데이터와의 결합은 DUA·가이드라인 심의 없이는 수행하지 않는다.

### 2-3. 분석·공개 산출물 통제 (노트북·리포트·공개물)

파이프라인은 데이터를 **저장소 밖**(SeaweedFS)에 두지만, **분석 산출물은 저장소 안으로 들어온다.**
`.ipynb` 셀 출력과 리포트의 표·그림은 **조회 결과를 그대로 박제**한다.
~~여기가 원천 데이터가 새는 **유일한 실질 경로**다.~~

🔴 **2026-08-20부로 이 문장은 사실이 아니다.** 경로가 둘 늘었고, 방향이 **반대**다 —
앞의 것이 "저장소 **안으로** 들어오는" 경로라면 새로 생긴 둘은 **저장소 밖으로 나가는** 경로다.

1. **공개물** — `docs/posts/**`(블로그·공유 자료). 작성 워커 `tech-writer`.
2. **외부 질의** — `researcher`의 `WebSearch`·`WebFetch`. **질의문 자체가 외부 발신**이다.
3. 🔴 **데이터 반출** — `data-extractor`의 추출물. 착지는 **저장소 밖** `$DATA_EXTRACT_DIR`
   (기본 `~/extracts`)이며, **앞의 둘과 달리 원천 진료 데이터 그 자체**가 나간다(2026-08-22 신설).
   경로 강제는 `scripts/worker_path_guard.py` — 저장소 안은 `deny`, 반출 경로 밖도 **`deny`**
   (`OUTSIDE_STRICT` — 다른 워커의 `ask`는 auto 모드 분류기가 흡수해 막히지 않는다).
   실행 **전** `security` 사전 컨펌이 필수 게이트다(Δ 트리거 ⓒ).

> 🔴 **이 표는 「점검 대상 목록」이지 설명이 아니다** — 여기 없는 경로는 다음 `security` 점검이
> **보지 않는다**. 반출 경로가 생기면 문서 미화가 아니라 **통제 목록의 정확성** 문제로 여기 먼저 적는다.

작업 규칙 정본은 [conventions/analysis.md](conventions/analysis.md)(분석)와
[conventions/publishing.md](conventions/publishing.md)(공개)이고, 이 절은 그 거버넌스 근거다.

| 통제 | 수단 | 상태 | 근거 |
| --- | --- | --- | --- |
| 셀 출력 커밋 차단 | `nbstripout` pre-commit 훅(출력·실행횟수 제거) | ✅ 구현 | `.pre-commit-config.yaml` |
| 자동 스냅샷 차단 | `.gitignore`의 `**/.ipynb_checkpoints/` | ✅ 구현 | Jupyter가 출력째로 스냅샷을 남긴다 |
| 실행 산출물 잔류 차단 | `nbconvert --execute` 사본을 **검증 직후 삭제** | 🟡 규칙 | [test.md §6](test.md) |
| 개별 행 노출 차단 | 리포트에 개별 환자 행 금지, **소규모 셀(관례상 5 미만) 마스킹** | 🟡 규칙 | 3.3 · DUA |
| 재식별 금지 | 외부 데이터 결합은 심의 없이 하지 않는다 | 🟡 규칙 | 제28조의5 · DUA |
| **공개물 반출 차단** | `tech-writer` 쓰기 **`docs/**` · `README.md`**(2026-08-20 확대, `worker_path_guard.py` hook 강제 — 실발동 확인), 단 **`except`: `docs/security.md`·`docs/skills.md` 제외**(2026-08-22) + **`security` 컨펌 게이트** + **사람이 발행**(워커 발행 금지) + 컨펌 전 커밋 금지 | 🟡 규칙 | [publishing.md §5](conventions/publishing.md) · DUA 재배포 제한 |
| ↳ ✅ **확대의 잔여 위험 — 정본 개찬 (해소)** | 2026-08-20 확대로 **이 문서(`docs/security.md`)와 [skills.md](skills.md)가 `tech-writer` 쓰기 범위 안**에 들어와 **통제·규제 매핑과 공급망 정책을 그 워커가 고칠 수 있었다.** 가드가 디렉터리 단위라 못 갈라 **규율로만** 막혀 있었으나, 2026-08-22 `worker_path_guard.py`에 **`except` 축**(`allow`/`deny`보다 먼저 평가, `deny`와 같은 방향이라 대소문자 무시)을 신설해 **기계 강제로 승격**했다. 🔴 승격 계기는 같은 날의 **정본 설계 게이트 축소**다(`CANON_PATTERNS`에서 `docs/conventions/**`·`docs/architectures/**` 제거) — **규율 의존이 늘어난 만큼 가장 위험한 2종은 기계로 내렸다.** 🔴 `docs/conventions/**`는 `except`에 넣지 **않았다**(doc-sync 정합 교정이 그 워커의 정당한 업무라 막으면 매 교정이 supervisor 왕복이 된다) — 그쪽은 **규율로 남고, 이제 `ask` 프롬프트조차 없다** | 🟢 기계 강제 — **단 `Edit`/`Write`/`NotebookEdit` 도구 축 한정**(matcher·`PATH_KEYS` 기준 **범위**이고, **라이브 실증은 `Edit` 하나뿐**이다 — 나머지 둘은 로직층만. 🔴 **3도구로 일반화하지 마라**)<br/>🔴 **`Bash` 경유(`sed`·리다이렉트·`tee`)는 matcher 밖이라 규율뿐**이다(2026-08-22 `security` 실측: `sed -i '' docs/security.md`·`docs/skills.md` **둘 다 통과** — 같은 축에서 `CLAUDE.md`·`.claude/settings.json`·`.env`는 `ask`가 떠 **관측 경로는 살아 있다**). `tech-writer`의 `tools`에 `Bash`가 있으므로 이 구멍은 실재한다 — **라벨을 「전면 차단」으로 읽지 마라** | [agents.md §권한 매트릭스](conventions/agents.md) · 2026-08-20 `security` 사후 컨펌 ④ · 2026-08-22 해소 |
| **외부 질의 유출 차단** | `researcher` 질의 규율(내부 데이터 금지) | 🔴 **규율뿐** — `permissions.ask`의 맨이름 `WebFetch`·`WebSearch`는 **죽은 규칙**(실측: 9회 호출·프롬프트 0회). 기계 검사도 **사람 관측점도 없다** | [researcher.md](../.claude/agents/researcher.md) · [publishing.md §7](conventions/publishing.md) |
| **외부 발신(egress) 차단** | `permissions.deny`의 `curl`/`wget` 발신 동사 · `ask`의 `gh api`·`git push`·`scp`/`rsync` | 🟡 부분 — `python`/`node` 경유·GET+쿼리스트링은 **못 막는다**(실측) | [publishing.md §7](conventions/publishing.md) |

- 🔴 **`gitleaks`는 크리덴셜 패턴을 잡지 헬스 데이터를 잡지 못한다.** 자동 검사 통과를 안전으로 읽지
  않는다 — 분석 산출물의 위험은 **비밀값이 아니라 데이터 그 자체**다.
- 🔴 **훅을 `--no-verify`로 우회해 커밋하지 않는다.** 우회하면 위 ✅ 두 줄이 동시에 무력화된다.
- **저장소는 공개(public)이고 푸시는 사실상 비가역이다** — force-push해도 캐시·포크·이벤트가 남는다.
  따라서 통제 지점은 푸시가 아니라 **커밋 이전**이며, 분석 산출물은 **공유 직전 수동 관문**
  ([test.md §6](test.md))을 거친다.
- **ISMS-P 대응**: 산출물 공유·반출은 **3.3(제공 시 보호조치)**, 조회 결과의 저장소 유입은
  **3.2(보유·이용 시 보호조치)** 에 대응한다.

#### 🔴 2-3 보강 — 방어 도구가 **셋인데 셋 다 다른 것을 본다** (2026-08-22 실측)

위 표의 ✅ 두 줄과 `gitleaks`를 합치면 데이터 유입이 막힌 것처럼 보인다. **아니었다.**
셋의 관측 범위가 서로 겹치지 않아 **틈**이 있었다.

| 도구 | 무엇을 보는가 | 무엇을 못 보는가 |
| --- | --- | --- |
| `nbstripout` | `.ipynb` **셀 출력만** | 노트북 밖 파일 전부 |
| `gitleaks` | **크리덴셜 패턴만** | 헬스 데이터 — **패턴이 아니다** |
| `.gitignore` | 당시 **`data/` 한 줄뿐** | 그 밖의 모든 경로 |

⇒ `notebooks/*.csv`·`notebooks/*.parquet`·`docs/analyses/*.csv`는 **셋 다의 사각지대**였고
**그대로 커밋 대상**이었다. 판정 명령은 `git check-ignore -v <경로>` → **exit 1 · 무출력**(미무시).
관측 **2026-08-22 01:5x KST**, 커밋 `65345fc` **이전** 상태.

- 🔴 **위험한 것은 각 도구가 자기 범위에서는 정상 작동했다는 점이다.** 셋 다 초록불이라
  **합집합이 전부를 덮는다고 읽혔다.** 어느 도구도 거짓말을 하지 않았고, 아무도 **합집합을
  실제로 계산하지 않았다.**
- **해소**: 2층(`.gitignore` + pre-commit 훅)을 걸고 **일부러 위반시켜** 둘 다 발동하는 것과
  **대조군 2셀이 안 걸리는 것**을 확인했다(커밋 `65345fc`).
- 🔴 **이것은 [conventions/agents.md](conventions/agents.md)의 *"가드가 여럿이라고 「하나가 막으니
  다 막힌다」고 읽지 않는다"*(`file_path`/`notebook_path` 함정)의 다음 층이다.** 그 조항은
  **한 가드가 도구마다 다른 키를 읽는** 경우였고, 여기는 **도구마다 보는 대상이 다른** 경우다.
- 🔴 **처방(이 사례가 추가되는 이유)**: **도구가 여럿이면 각자 무엇을 보는지 표로 적어야 틈이 보인다.**
  "몇 겹인가"는 안전의 척도가 아니다 — **겹의 합집합이 대상을 덮는가**만이 척도다.

> **아래 §2-4의 사례와 축이 다르다.** 그쪽은
> **한 도구의 범위 지정이 빗나간** 것이고(처방: 점검 범위에 숨김 파일·셸 히스토리·홈 디렉터리 포함),
> 이쪽은 **여러 도구의 범위가 안 겹쳐 틈이 생긴** 것이다(처방: 위 표).
> 결론은 둘 다 *"관측 경로의 생존"과 "관측 범위의 충분성"은 다른 축* 이지만 **처방이 갈린다.**

### 2-4. 실측 기록 — 크리덴셜 평문 유출 1건 (2026-08-22)

**처분 완료** 건이며, 재발 조건과 교훈을 남기기 위해 기록한다.

| 항목 | 내용 |
| --- | --- |
| 대상 | `/opt/flink/.flink-sql-history`(JobManager 컨테이너 내부) |
| 내용 | `PG_PASSWORD` **평문 5라인**(파일 총 30행). 🔴 **값은 여기 옮겨 적지 않는다** |
| 원인 | `sql-client`가 **실행한 모든 문장을 히스토리에 append**한다. `-i`로 넘긴 렌더된 `CREATE CATALOG … 'jdbc.password' = '<값>'` 이 그대로 적힌다 |
| 증가 양상 | **호출마다 1건씩** 늘었다(세션 5회 = 5건) |
| 반경 | perm `600` `flink:flink` · **overlay FS**(파드 교체 시 소멸, PVC 아님) · **REST 미노출** · 도달 수단은 사실상 `kubectl exec` |
| 처분 | 즉시 삭제 + **재발 차단**(`sql-client`의 `--history`를 버릴 경로로 지정) · ✅ **파드 소멸로 최종 정리 확인** |

**✅ 같은 점검에서 무유출로 확인된 3점**

| 관측점 | 결과 | 생존 확인 |
| --- | --- | --- |
| 컨테이너 로그 | **0건** | 무해 패턴 **811건** 매칭 |
| 파드 파일시스템 `/opt/flink/log`·`/tmp` | **0건** | 무해 패턴 **6건** |
| **JobManager REST 로그 API** | **0건** | 무해 패턴 **814건** — 무인증·200이나 **서빙 로그에 비밀이 없다**. 히스토리 파일은 **404**(로그 디렉터리에 스코프가 잠겨 있다) |

- ✅ **S3 키는 0건이다** — env 자격증명 체인(S3FileIO)이라 애초에 DDL에 들어가지 않는다.
- 🔴 **핵심 교훈 — 점검 「범위」다.** 지정된 점검 범위는 `/opt/flink/log`·`/tmp`였고
  **평문은 그 밖에 있었다.** 워커가 스코프를 넘어 찾아냈기에 잡혔고,
  **규정대로만 훑었으면 "0건 통과"** 였다.
- 🔴 **생존 확인은 멀쩡했다**(811·6·814건). ⇒ **"관측 경로의 생존"과 "관측 범위의 충분성"은
  다른 축이다.** 이것이 [philosophy.md](philosophy.md) 원칙 7의 **다음 층**이다 —
  살아 있는 관측 경로로도 **범위 밖은 못 본다.**
- 🔴 **명문화**: 크리덴셜 유출 점검 범위에는 **숨김 파일(`.*`)·셸 히스토리·홈 디렉터리**를
  **반드시 포함**한다. 로그 디렉터리만 훑는 점검은 **범위 밖을 조용히 부정 결과로 계상**한다.
- **재발 조건**: 이 건의 위험이 낮았던 이유는 위 통제가 아니라 **비밀번호가 아직 회전되지 않은
  공개 상수**였기 때문이다([k8s.md §9-2](conventions/k8s.md) 조건 5). **회전하는 순간 등급이 오른다.**

### 2-5. 손상 잔재 — orphan 객체 (2026-08-22, 미해소)

카탈로그에서 **네임스페이스 `smoke`가 삭제**된 뒤 그 아래 데이터의 **오브젝트 53개가 orphan으로
남아 있다.** 🔴 **경로·버킷은 여기 적지 않는다**(존재와 개수만).

- 🔴 **주간 유지보수 잡으로는 영영 정리되지 않는다.** `remove_orphan_files`는
  **인자로 받은 테이블의 location 하위만** 스캔하는데, **해당 네임스페이스에 테이블이 0개**라
  스캔 진입점 자체가 없다([§4-1](#4-todo-실행-절차)).
- **성격**: 유출이 아니라 **파기(3.4) 미완**이다 — 카탈로그상 지워진 데이터의 실체가 남아 있다.
- **처리 방향**(미실행): 삭제 전에 **대상 식별 근거를 남기고** 수동 정리하거나,
  네임스페이스 삭제 절차에 **선(先) orphan 정리**를 넣는다. 어느 쪽도 **비가역**이라
  사람 승인 게이트를 거친다.
- 🔴 **교훈**: **"카탈로그에서 지웠다"는 "지워졌다"가 아니다.** 메타데이터와 데이터가 분리 저장되는
  구조에서 파기는 **두 곳 모두**에서 일어나야 하고, 자동화의 **스캔 진입점이 메타데이터 쪽에 있으면
  메타데이터를 먼저 지운 순간 자동화의 사정거리 밖으로 나간다.**

## 3. 우선순위 TODO (거버넌스·보안 관점)

> 각 항목의 **실행 절차**는 [§4](#4-todo-실행-절차)에 도구별로 상세화한다.

리스크·규제 영향 순으로 정렬(★ = 우선순위). 정본 통제는 각 문서에, 현황 요약은 여기서 관리.

| ★ | 항목 | 근거 인증기준 | 연계 문서 |
| --- | --- | --- | --- |
| ★★★★★ | 원천 데이터·`.env`·크리덴셜 **저장소 커밋 금지** 준수·점검 | DUA · 2.7 · 3.1 | [general.md](conventions/general.md#비밀정보-secrets) |
| ★★★★☆ | Iceberg **보존·파기** 자동화 — 🟡 잡 구현(만료+orphan 정리, [defs/maintenance.py](../dagster/dockerfile.d/src/src/dagster_project/defs/maintenance.py)), 보존기간·대상 범위 확정 잔여 | 3.4 · 2.9 | [operations.md §2](operations.md) |
| ★★★★☆ | **분석·공개 산출물 반출 통제** — ✅ 셀 출력 훅·스냅샷 무시 구현, 🟡 소규모 셀 마스킹·실행 산출물 삭제는 **규칙 단계**(기계 강제 없음), 🟡 **공개물(`docs/posts/**`)·외부 질의 축 추가**(2026-08-20) — 게이트는 **전부 사람**. ✅ **원천 데이터 파일(`*.csv`·`*.parquet`) 커밋 차단 2층**(`.gitignore` + pre-commit 훅, 커밋 `65345fc`) — 그 전까지 **세 도구 모두의 사각지대**였다([§2-3 보강](#2-3-분석공개-산출물-통제-노트북리포트공개물)) | 3.2 · 3.3 · DUA | [§2-3](#2-3-분석공개-산출물-통제-노트북리포트공개물) · [analysis.md](conventions/analysis.md) · [publishing.md](conventions/publishing.md) |
| ★★★★★ | **외부 발신(egress) 통제** — 🟡 `permissions.deny`(발신 동사)·`ask`(`gh`·`git push`) 구현. 🔴 미비: `WebFetch`/`WebSearch` `ask`가 **죽은 규칙**(실측 9회 프롬프트 0회) · `python`/`node` 경유·GET+쿼리스트링·변수 조립 **미커버**(실측) · `researcher` 인젝션 사정거리(`.env`·`tfvars`·`gh` 토큰 **읽기 무통제**) | 2.6 · 2.7 · 3.3 | [publishing.md §7](conventions/publishing.md) · [researcher.md](../.claude/agents/researcher.md) |
| ★★★★☆ | **저장/전송 암호화**(at-rest·TLS) — 실서비스 확장 전제 | 2.7 | [docker.md](conventions/docker.md) |
| ★★★☆☆ | 서비스 **RBAC·최소권한** 매트릭스 문서화 | 2.5 · 2.6 | [operations.md](operations.md) |
| ★★★☆☆ | Postgres·SeaweedFS **백업·복구** 정책 | 2.12 | [operations.md](operations.md) |
| ★★☆☆☆ | 중앙 **감사 로그·접속기록** 수집·보관 | 2.10 · 3.2 | [architectures/monitoring.md](architectures/monitoring.md)(현행 관측 실태 — 수집기는 살아 있으나 수집 대상이 정본과 갈림) · [conventions/monitoring.md](conventions/monitoring.md)(관측 수단 등록·생존 확인 규칙) |

### 3-1. 점검 수단 — `security` 서브에이전트

위 항목의 **준수 여부 점검**은 AI 세션의 보안 담당 워커 [`.claude/agents/security.md`](../.claude/agents/security.md)에 배정한다
(3계층 규약 [conventions/agents.md](conventions/agents.md)).

- **읽기 전용**이다 — 발견을 심각도(높음·중간·낮음)로 **반환만** 하고, 수정·커밋은 승인 후 별도 워커가 한다(승인 게이트).
- 점검 범위는 이 문서(ISMS-P 매핑·§0 철칙)와 [general.md](conventions/general.md)·[operations.md](operations.md)·
  [publishing.md](conventions/publishing.md)(외부 공개)·인프라 컨벤션(terraform·k8s·docker)이며,
  **규칙을 새로 만들지 않고 정본을 집행**한다.
- 보고 시 **비밀값 원문은 마스킹**한다. 내장 `/security-review`(변경분 취약점 중심)와 병행 — 이 워커는 **거버넌스·컨벤션 준수**를 본다.
- 권장 시점: 커밋 전, 인프라 변경(terraform·k8s·docker) 리뷰 시, §2 매핑표 갱신 시.

## 4. TODO 실행 절차

각 절차는 **제안(TODO)** 이며 현재 미구현이다. 구현 시 이 문서와 해당 정본 문서
([operations.md](operations.md)·[docker.md](conventions/docker.md))를 함께 갱신한다.
설정 파일·환경변수는 §0 철칙(비밀은 참조·커밋 금지)을 따른다.

### 4-1. Iceberg snapshot 보존·파기 자동화 (3.4 · 2.9)

유지보수를 안 돌리면 작은 파일·스냅샷이 무제한 누적된다([operations.md §2](operations.md)).
**안전 순서: compact → expire snapshots → remove orphan files.** 컴팩션이 새 파일·스냅샷을 만든 뒤
만료가 옛 작은 파일 참조를 풀고, orphan 정리가 잔여를 제거한다.

**구현**: [`defs/maintenance.py`](../dagster/dockerfile.d/src/src/dagster_project/defs/maintenance.py) —
Dagster 잡·스케줄(매주 일요일 03:00 KST). 카탈로그 설정 중복 없이 이미 등록된
대용량 테이블 `IcebergTableResource` 바인딩을 단일 출처로 재사용한다. 위 **안전 순서**를
op 의존성(`dg.In(dg.Nothing)`)으로 강제한다.

| 단계 | 실행 | 근거 |
| --- | --- | --- |
| 1. 컴팩션 | **Trino** `ALTER TABLE iceberg.<ns>.<table> EXECUTE optimize(file_size_threshold => '100MB')` | 청크 append로 쌓인 small-files 병합. Spark 대비는 [architectures/spark.md](architectures/spark.md) |
| 2. 스냅샷 만료 | pyiceberg 0.11.x `table.maintenance.expire_snapshots().older_than(dt).commit()` (`older_than`는 tz-aware datetime) | 보존기간 `SNAPSHOT_RETENTION_DAYS`(기본 7일) 경과분 |
| 3. orphan 정리 | **Trino** `ALTER TABLE iceberg.<ns>.<table> EXECUTE remove_orphan_files` | pyiceberg 0.11.x 미지원 → Trino 프로시저. retention 생략 시 기본 7일(min-retention) |

Trino 접속은 컨벤션대로 리소스로 관리한다(`common/trino.py`의 `TrinoResource`,
`defs/resources.py`에 `"trino"`로 등록). 내부망 평문(`http`) — 외부 노출 시 TLS 필요([§4-2](#4-2-저장전송-암호화-27)).

> **컴팩션(단계 1)**: 대용량 append 테이블의 small-files를 Trino `optimize`로 병합한다.
> Spark `rewrite_data_files`와의 비교·프로젝트 결정은 [architectures/spark.md](architectures/spark.md) 심화 참고.

> retention을 7일보다 짧게 지정하면 Trino가 거부한다(`iceberg.remove-orphan-files.min-retention` 기본 7d).
> 보존기간(`SNAPSHOT_RETENTION_DAYS`) 확정 값은 [operations.md §2](operations.md) 표에 반영한다.

### 4-2. 저장/전송 암호화 (2.7)

**저장 시 암호화(at-rest)**

| 대상 | 방법 |
| --- | --- |
| SeaweedFS(오브젝트) | **SSE-S3**(AES-256, 서버 관리 키·envelope 암호화). S3 API로 업로드 시 서버 측 암호화 적용 |
| Postgres(Iceberg 카탈로그·Dagster DB) | 커뮤니티 Postgres는 네이티브 TDE 미지원 → **볼륨/디스크 암호화**(LUKS·클라우드 EBS 암호화)로 대체. 🔴 카탈로그 PG는 2026-08-19부터 **영속 PVC**(kind `rancher.io/local-path` = 호스트 디스크, 비암호화)라 이 항목이 실질 리스크다 |
| Iceberg 데이터 파일 | SeaweedFS SSE-S3에 위임(데이터는 warehouse 버킷에 저장) |

**전송 시 암호화(in-transit)**

| 구간 | 방법 |
| --- | --- |
| S3(SeaweedFS) | `security.toml`로 TLS 구성(gRPC·HTTPS 분리). 현재 endpoint `http://seaweedfs:8333`는 **격리된 compose 내부망**이라 평문 허용 — **외부 노출 시 HTTPS 필수**([constants.py](../dagster/dockerfile.d/src/src/dagster_project/common/constants.py) `S3_ENDPOINT`) |
| Trino | `http-server.https.enabled=true` + 키스토어. 비밀번호 인증은 **TLS 필수** |
| Postgres | `ssl=on` + `server.crt`/`server.key`, 클라이언트 `sslmode=require`. **카탈로그 PG는 CNPG가 자체 CA(`catalog-postgres-ca`)와 서버 인증서를 자동 발급**해 서버 측 TLS 1.3이 이미 켜져 있다(2026-08-19 실측) — 남은 것은 **클라이언트 `sslmode` 강제**다. ⚠️ CA 개인키가 `default` 네임스페이스 Secret에 있어, 같은 ns의 secret read 권한 = CA 키 접근이다 |

> 내부 격리망(단일 호스트 compose)에서는 평문이 허용되나, **관리 UI·서비스를 호스트 밖으로 노출하면
> 전 구간 TLS를 적용**한다([docker.md](conventions/docker.md)).

### 4-3. 서비스 RBAC·최소권한 (2.5 · 2.6)

서비스별 계정을 **분리**하고 필요한 권한만 부여한다(현재 단일 크리덴셜 공유 → 분리 필요).

**CloudNativePG(카탈로그 PG)** — RBAC이 **2계층**이다(2026-08-19 실측).
컨트롤러 `ClusterRole/cloudnative-pg`는 **전 네임스페이스의 `secrets`·`configmaps`·`services`에 RW**를 갖는다
(cluster-wide 설치 · CNPG 아키텍처상 불가피). 반면 인스턴스용 `Role/catalog-postgres`는 `resourceNames`로
**자기 시크릿·configmap·Cluster에만** 한정돼 최소권한을 지킨다.
→ 방어 심화 과제: 차트의 감시 네임스페이스 제한 검토, `NetworkPolicy`로 5432 접근 제한
(현재 없음 — 클러스터 내 임의 파드가 카탈로그 PG에 도달 가능).

**SeaweedFS S3** — `-s3.config=s3.json`의 `identities`로 서비스별 accessKey·최소 action 지정
(`Admin`/`Read`/`Write`/`List`/`Tagging`). *주의: `-s3.iam.config`는 identities 미지원 → `-s3.config` 사용.*

```json
{
  "identities": [
    { "name": "dagster-writer",
      "credentials": [{ "accessKey": "${DAGSTER_S3_KEY}", "secretKey": "${DAGSTER_S3_SECRET}" }],
      "actions": ["Read:warehouse", "Write:warehouse", "List:warehouse", "Tagging:warehouse"] },
    { "name": "trino-reader",
      "credentials": [{ "accessKey": "${TRINO_S3_KEY}", "secretKey": "${TRINO_S3_SECRET}" }],
      "actions": ["Read:warehouse", "List:warehouse"] }
  ]
}
```

**Trino** — file-based access control로 카탈로그·스키마·테이블·컬럼 권한을 rules.json에 선언
(위→아래 첫 매칭 규칙 적용, 약 30초 자동 리로드).

```properties
# etc/access-control.properties
access-control.name=file
security.config-file=/etc/trino/rules.json
```

필요 시 `etc/password-authenticator.properties`(`password-authenticator.name=file`)로 사용자 인증을
추가한다(단, **HTTPS·공유 시크릿 필수**).

**Postgres** — 서비스별 role을 만들고 최소 GRANT(예: 카탈로그 DB는 스키마 사용 권한만).

```sql
CREATE ROLE trino_ro LOGIN PASSWORD :'pw';
GRANT CONNECT ON DATABASE iceberg_catalog TO trino_ro;
GRANT USAGE ON SCHEMA public TO trino_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO trino_ro;
```

> 계정 분리 시 §4-2 전송 암호화와 함께 적용하고, 계정·권한 매트릭스를 [operations.md](operations.md)에 표로 남긴다.

### 4-4. 백업·복구 (2.12)

| 대상 | 백업 | 복구 |
| --- | --- | --- |
| 카탈로그 Postgres(K8s, CNPG) | **Barman Cloud 플러그인**(CNPG-I)으로 base backup + WAL 아카이브 → SeaweedFS S3. `INSTALL_CNPG_BACKUP=true`로 opt-in(**현재 off**) | CNPG `Cluster`의 `bootstrap.recovery`로 복원(PITR 지원) |
| 메타 Postgres(compose, Dagster DB) | 논리 백업 `pg_dump`(정기 cron) 또는 물리 백업 `pg_basebackup` + **WAL 아카이브**(PITR) | `pg_restore`(논리) / base backup + WAL 재생(물리) |
| SeaweedFS `s3://warehouse` | 버킷 객체 복제(다른 호스트/버킷) 또는 볼륨 백업 | 복제본에서 복원 후 카탈로그 정합 확인 |

> 🔴 **백업 대상이 같은 장애 도메인이면 DR이 아니다** — CNPG 백업을 클러스터 내부 SeaweedFS로 보내면
> 원본 PVC와 백업본이 **같은 kind 노드·같은 호스트 디스크**에 놓여 노드 유실 시 함께 사라진다.
> 목적을 **논리 오류·실수 복구**로 한정하고, 진짜 DR이 필요해지면 목적지를 호스트 밖으로 뺀다.
> 카탈로그 DB가 담는 것은 테이블 식별자·메타 포인터라 **PHI 유출 경로는 아니다**(평문 전송이어도 등급이 다르다).
>
> **정합 주의**: Iceberg는 메타데이터(Postgres 카탈로그)와 데이터(SeaweedFS)가 분리 저장되므로
> **둘의 백업 시점을 맞춘다**. 카탈로그만 복구하면 없는 데이터 파일을 가리켜 읽기 실패가 난다.
> 백업 주기·보존기간은 [operations.md §2](operations.md) 표에 확정한다.

### 4-5. 감사 로그·접속기록 (2.10 · 3.2)

- Trino **쿼리 이벤트 리스너**(누가·언제·무엇을 조회)와 SeaweedFS 접근 로그를 중앙 수집한다.
- UTC 저장/KST 표시 정책으로 로그 타임스탬프를 정합화한다([timezone.md](conventions/timezone.md)).
- (확장 시) 개인정보 접속기록 보관은 개인정보보호법 시행령상 **최소 보관기간**을 확인해 반영한다.

## 참고

- ISMS-P 인증기준 안내서(2023.11) — 개인정보보호위원회: https://www.privacy.go.kr/front/bbs/bbsView.do?bbsNo=BBSMSTR_000000000049&bbscttNo=20677
- ISMS-P 인증 소개 — KISA: https://isms.kisa.or.kr/
- 개인정보 보호법 제28조의2 (가명정보의 처리 등) — 국가법령정보센터: https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=213857
- 보건의료데이터 활용 가이드라인 — 개인정보보호위원회: https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=D010030000
- HIPAA De-identification (Safe Harbor) — HHS: https://www.hhs.gov/hipaa/for-professionals/privacy/special-topics/de-identification/index.html
- MIMIC-IV (PhysioNet, Credentialed License·DUA): https://physionet.org/content/mimiciv/
- eICU-CRD (PhysioNet): https://physionet.org/content/eicu-crd/

### 실행 절차(§4) 도구 문서

- Apache Iceberg — Maintenance(expire snapshots·remove orphan files): https://iceberg.apache.org/docs/latest/maintenance/
- SeaweedFS — S3 Configuration(identities·SSE-S3): https://github.com/seaweedfs/seaweedfs/wiki/S3-Configuration
- SeaweedFS — Security Configuration(TLS `security.toml`): https://github.com/seaweedfs/seaweedfs/wiki/Security-Configuration
- Trino — File-based access control: https://trino.io/docs/current/security/file-system-access-control.html
- Trino — TLS/HTTPS & Password authentication: https://trino.io/docs/current/security/tls.html
- PostgreSQL — Backup & Restore / SSL: https://www.postgresql.org/docs/current/backup.html
