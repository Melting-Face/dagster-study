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
| **2.5 인증 및 권한관리** | (study 단일 사용자) 서비스 계정은 `.env` 크리덴셜로 분리 | 🟡 | Trino·Dagster·SeaweedFS **RBAC/최소권한** 미문서화. 확장 시 계정·권한 매트릭스 필요 |
| **2.6 접근통제** | 내부 네트워크(compose)로 서비스 격리, 비밀 설정 `:ro` 마운트([philosophy #4](philosophy.md)) | 🟡 | 관리 UI(SeaweedFS·Dagster) **포트 노출** 범위 점검·인증 필요 |
| **2.7 암호화 적용** | 비밀정보 **하드코딩 금지·참조 주입**(`dg.EnvVar`/`${ENV:...}`), `.env` gitignore ([general.md](conventions/general.md#비밀정보-secrets)) | 🟡 | **저장 암호화(at-rest)** 미설정(SeaweedFS·Postgres·Iceberg). **전송 암호화(TLS)** — S3 endpoint `http://`(내부 평문). 실서비스는 HTTPS/TLS 필요 |
| **2.8 정보시스템 도입 및 개발 보안** | pre-commit **gitleaks** 시크릿 스캔·`ruff`·`hadolint`, 이미지 `latest` 금지([docker.md](conventions/docker.md)) | ✅ | 의존성 취약점 스캔(SCA) 미도입 |
| **2.9 시스템 및 서비스 운영관리** | Docker 로그 보존(`max-size 10m × 20`), healthcheck+`depends_on`, `deploy.resources` 명시 | ✅ | — |
| **2.10 시스템 및 서비스 보안관리** | UTC 저장/KST 표시로 **로그 타임스탬프 일관성**([timezone.md](conventions/timezone.md)) | 🟡 | 중앙 **감사 로그(접속기록)** 수집·보관 미설정 |
| **2.11 사고 예방 및 대응** | — | ⬜ | 침해 대응 절차·알림(모니터링) 미정의 |
| **2.12 재해복구 및 업무연속성** | — | ⬜ | Postgres(카탈로그)·SeaweedFS **백업·복구** 정책 미설정 |

### 2-2. 영역 3 — 개인정보 처리 단계별 (연구 데이터 대응)

| 인증기준 | 현 프로젝트 통제 | 상태 | 미비점·TODO |
| --- | --- | --- | --- |
| **3.1 수집 시 보호조치** | 비식별 데이터만 수집(원천이 이미 Safe Harbor 비식별) | ✅ | 원천 데이터 **저장소 커밋 금지** 규칙 준수(§0 철칙) |
| **3.2 보유 및 이용 시 보호조치** | 데이터는 SeaweedFS에만 상주, 코드/문서와 분리 | 🟡 | 접근기록(누가 조회) 로깅 미설정 |
| **3.4 파기 시 보호조치** | — | ⬜ | Iceberg **snapshot 만료·orphan 정리** 미설정 → 무제한 누적([operations.md §2](operations.md)). 보존기간·파기 자동화 필요 |

> **재식별 금지(제28조의5·DUA)**: 어떤 파이프라인·분석도 특정 개인 재식별을 시도하지 않는다.
> 외부 데이터와의 결합은 DUA·가이드라인 심의 없이는 수행하지 않는다.

## 3. 우선순위 TODO (거버넌스·보안 관점)

> 각 항목의 **실행 절차**는 [§4](#4-todo-실행-절차)에 도구별로 상세화한다.

리스크·규제 영향 순으로 정렬(★ = 우선순위). 정본 통제는 각 문서에, 현황 요약은 여기서 관리.

| ★ | 항목 | 근거 인증기준 | 연계 문서 |
| --- | --- | --- | --- |
| ★★★★★ | 원천 데이터·`.env`·크리덴셜 **저장소 커밋 금지** 준수·점검 | DUA · 2.7 · 3.1 | [general.md](conventions/general.md#비밀정보-secrets) |
| ★★★★☆ | Iceberg snapshot **보존·파기** 자동화(`expire_snapshots`·`remove_orphan_files`) | 3.4 · 2.9 | [operations.md §2](operations.md) |
| ★★★★☆ | **저장/전송 암호화**(at-rest·TLS) — 실서비스 확장 전제 | 2.7 | [docker.md](conventions/docker.md) |
| ★★★☆☆ | 서비스 **RBAC·최소권한** 매트릭스 문서화 | 2.5 · 2.6 | [operations.md](operations.md) |
| ★★★☆☆ | Postgres·SeaweedFS **백업·복구** 정책 | 2.12 | [operations.md](operations.md) |
| ★★☆☆☆ | 중앙 **감사 로그·접속기록** 수집·보관 | 2.10 · 3.2 | — |

## 4. TODO 실행 절차

각 절차는 **제안(TODO)** 이며 현재 미구현이다. 구현 시 이 문서와 해당 정본 문서
([operations.md](operations.md)·[docker.md](conventions/docker.md))를 함께 갱신한다.
설정 파일·환경변수는 §0 철칙(비밀은 참조·커밋 금지)을 따른다.

### 4-1. Iceberg snapshot 보존·파기 자동화 (3.4 · 2.9)

`expire_snapshots()`를 호출하지 않으면 스냅샷·데이터 파일이 무제한 누적된다([operations.md §2](operations.md)).
**안전 순서: expire snapshots → remove orphan files → rewrite manifests.** `expire_snapshots`는
orphan 파일을 지우지 않으므로 둘을 함께 돌린다.

Dagster 잡·스케줄로 자동화한다(에셋은 함수형·명시적, 스케줄은 KST — [timezone.md](conventions/timezone.md)).

```python
# defs/maintenance.py (제안) — pyiceberg 유지보수 잡
from datetime import datetime, timedelta, timezone

import dagster as dg
from pyiceberg.catalog import load_catalog

# 파기 대상 테이블(네임스페이스.테이블)과 스냅샷 보존기간
RETENTION_DAYS = 7
MAINTAINED_TABLES = ["mimiciv.chartevents", "mimiciv.labevents", "eicu.nurse_charting"]


@dg.op
def expire_iceberg_snapshots(context: dg.OpExecutionContext) -> None:
    """보존기간 지난 스냅샷 만료 후 orphan 파일 제거(안전 순서)."""
    catalog = load_catalog("iceberg")  # properties는 defs/resources.py와 동일 출처로 주입
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=RETENTION_DAYS)
    for identifier in MAINTAINED_TABLES:
        table = catalog.load_table(identifier)
        table.expire_snapshots().expire_older_than(int(cutoff.timestamp() * 1000)).commit()
        # remove_orphan_files는 pyiceberg 버전에 따라 미지원일 수 있음 → 미지원 시 Trino/Spark 프로시저로 대체
        context.log.info("expired snapshots < %s for %s", cutoff.isoformat(), identifier)


@dg.job
def iceberg_maintenance_job() -> None:
    expire_iceberg_snapshots()


# 매주 일요일 03:00 KST
iceberg_maintenance_schedule = dg.ScheduleDefinition(
    job=iceberg_maintenance_job, cron_schedule="0 3 * * 0", execution_timezone="Asia/Seoul"
)
```

> `remove_orphan_files`가 설치된 pyiceberg에 없으면 Trino의 `ALTER TABLE ... EXECUTE remove_orphan_files`
> 또는 Spark 프로시저로 대체한다. 구현 후 보존기간을 [operations.md §2](operations.md) 표에 확정한다.

### 4-2. 저장/전송 암호화 (2.7)

**저장 시 암호화(at-rest)**

| 대상 | 방법 |
| --- | --- |
| SeaweedFS(오브젝트) | **SSE-S3**(AES-256, 서버 관리 키·envelope 암호화). S3 API로 업로드 시 서버 측 암호화 적용 |
| Postgres(Iceberg 카탈로그·Dagster DB) | 커뮤니티 Postgres는 네이티브 TDE 미지원 → **볼륨/디스크 암호화**(LUKS·클라우드 EBS 암호화)로 대체 |
| Iceberg 데이터 파일 | SeaweedFS SSE-S3에 위임(데이터는 warehouse 버킷에 저장) |

**전송 시 암호화(in-transit)**

| 구간 | 방법 |
| --- | --- |
| S3(SeaweedFS) | `security.toml`로 TLS 구성(gRPC·HTTPS 분리). 현재 endpoint `http://seaweedfs:8333`는 **격리된 compose 내부망**이라 평문 허용 — **외부 노출 시 HTTPS 필수**([constants.py](../dagster/dockerfile.d/src/src/dagster_project/common/constants.py) `S3_ENDPOINT`) |
| Trino | `http-server.https.enabled=true` + 키스토어. 비밀번호 인증은 **TLS 필수** |
| Postgres | `ssl=on` + `server.crt`/`server.key`, 클라이언트 `sslmode=require` |

> 내부 격리망(단일 호스트 compose)에서는 평문이 허용되나, **관리 UI·서비스를 호스트 밖으로 노출하면
> 전 구간 TLS를 적용**한다([docker.md](conventions/docker.md)).

### 4-3. 서비스 RBAC·최소권한 (2.5 · 2.6)

서비스별 계정을 **분리**하고 필요한 권한만 부여한다(현재 단일 크리덴셜 공유 → 분리 필요).

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
| Postgres(`iceberg_catalog`·Dagster DB) | 논리 백업 `pg_dump`(정기 cron) 또는 물리 백업 `pg_basebackup` + **WAL 아카이브**(PITR) | `pg_restore`(논리) / base backup + WAL 재생(물리) |
| SeaweedFS `s3://warehouse` | 버킷 객체 복제(다른 호스트/버킷) 또는 볼륨 백업 | 복제본에서 복원 후 카탈로그 정합 확인 |

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
