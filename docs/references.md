# 참고 문서 (외부 표준·출처)

이 프로젝트의 규칙·설계가 근거로 삼는 외부 표준과 문서를 모은다. 각 문서의 `참고` 섹션은
여기의 항목을 링크한다(단일 출처 — [`doc-sync.md`](doc-sync.md)).

## 코딩 철학·규칙

| 표준 | 용도 | 참조 문서 |
| --- | --- | --- |
| [PEP 20 — The Zen of Python](https://peps.python.org/pep-0020/) | 단순함·명시적·가독성 | [philosophy.md](philosophy.md) |
| [12-Factor App](https://12factor.net/config) | 설정/비밀정보는 환경변수 참조 | [philosophy.md](philosophy.md) · [operations.md](operations.md) |
| [Rule of Three / DRY](https://en.wikipedia.org/wiki/Rule_of_three_(computer_programming)) | 3회 반복부터 추출 | [philosophy.md](philosophy.md) |
| [PEP 8](https://peps.python.org/pep-0008/) · [PEP 257](https://peps.python.org/pep-0257/) | 스타일·docstring | [conventions/python.md](conventions/python.md) |
| [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) | docstring(Google 스타일) | [conventions/python.md](conventions/python.md) |
| [Conventional Commits](https://www.conventionalcommits.org/) | 커밋 메시지 규약 | [conventions/general.md](conventions/general.md) |

## 도구

| 도구 | 용도 | 참조 문서 |
| --- | --- | --- |
| [ruff](https://docs.astral.sh/ruff/) | Python lint·format | [conventions/python.md](conventions/python.md) |
| [sqlfluff](https://docs.sqlfluff.com/) | SQL lint·format (trino dialect) | [conventions/dbt.md](conventions/dbt.md) |
| [uv](https://docs.astral.sh/uv/) | 의존성·가상환경 | [conventions/python.md](conventions/python.md) |

## 플랫폼·프레임워크

| 문서 | 용도 | 참조 문서 |
| --- | --- | --- |
| [Dagster](https://docs.dagster.io/) | 오케스트레이션·에셋·리소스 | [conventions/dagster.md](conventions/dagster.md) · [architectures/overview.md](architectures/overview.md) |
| [dagster-dbt](https://docs.dagster.io/integrations/dbt) | dbt 통합(`@dbt_assets`) | [conventions/dbt.md](conventions/dbt.md) |
| [dbt-trino](https://github.com/starburstdata/dbt-trino) | dbt Trino 어댑터 | [conventions/dbt.md](conventions/dbt.md) |
| [Apache Iceberg](https://iceberg.apache.org/) | 테이블 포맷(JDBC 카탈로그) | [architectures/overview.md](architectures/overview.md) |
| [Trino](https://trino.io/docs/current/) | 쿼리 엔진 | [architectures/overview.md](architectures/overview.md) · [resource-sizing.md](resource-sizing.md) |
| [SeaweedFS](https://github.com/seaweedfs/seaweedfs) | S3 호환 오브젝트 스토리지 | [architectures/overview.md](architectures/overview.md) |

## 처리·배포 기술 (architectures)

| 기술 | 상태 | 참조 문서 |
| --- | --- | --- |
| [Docker Compose](https://docs.docker.com/reference/compose-file/) | ✅ 채택(배포) | [architectures/docker.md](architectures/docker.md) · [conventions/docker.md](conventions/docker.md) |
| [Apache Spark](https://spark.apache.org/docs/latest/) | 🔎 미채택 | [architectures/spark.md](architectures/spark.md) |
| [Apache Flink](https://flink.apache.org/documentation/flink-stable/) | 🔎 미채택 | [architectures/flink.md](architectures/flink.md) |
| [Kubernetes](https://kubernetes.io/docs/home/) | 🔎 향후 배포 | [architectures/k8s.md](architectures/k8s.md) · [conventions/k8s.md](conventions/k8s.md) |
| [Helm](https://helm.sh/docs/) | 🔎 K8s 패키징 | [conventions/k8s.md](conventions/k8s.md) |

## 보안·규제 (의료데이터)

| 표준·법령 | 용도 | 참조 문서 |
| --- | --- | --- |
| [ISMS-P 인증기준(2023.11)](https://www.privacy.go.kr/front/bbs/bbsView.do?bbsNo=BBSMSTR_000000000049&bbscttNo=20677) | 정보보호·개인정보보호 관리체계 101 인증기준 | [security.md](security.md) |
| [개인정보 보호법](https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=213857) | 가명정보 처리 특례(제28조의2·4·5) | [security.md](security.md) |
| [보건의료데이터 활용 가이드라인](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=D010030000) | 보건의료 가명정보 처리 절차·심의(DRB) | [security.md](security.md) |
| [HIPAA De-identification (Safe Harbor)](https://www.hhs.gov/hipaa/for-professionals/privacy/special-topics/de-identification/index.html) | 데이터셋 비식별 근거(18식별자) | [security.md](security.md) |
| [PhysioNet Credentialed License·DUA](https://physionet.org/content/mimiciv/) | 데이터 접근·재식별 금지 협약 | [security.md](security.md) |

## 데이터셋·도메인

| 출처 | 용도 | 참조 문서 |
| --- | --- | --- |
| [MIMIC-IV](https://physionet.org/content/mimiciv/) | 원천 데이터셋(icu·hosp 모듈) | [dataset_schema.md](dataset_schema.md) |
| [eICU-CRD](https://physionet.org/content/eicu-crd/) | 원천 데이터셋 | [dataset_schema.md](dataset_schema.md) |
| [mimic-code concepts](https://github.com/MIT-LCP/mimic-code) | 실버 모델(SOFA·Sepsis-3) 원 로직 | [dataset_schema.md](dataset_schema.md) |
| [Sepsis-3 (JAMA 2016)](https://jamanetwork.com/journals/jama/fullarticle/2492881) | Sepsis-3 정의(SOFA≥2 + 감염 의심) | [dataset_schema.md](dataset_schema.md) |
