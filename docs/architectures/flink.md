# Apache Flink (아키텍처 · 프로젝트 관점)

## 개요

Flink는 **상태 기반 스트림 처리 엔진**이다. 무한 스트림을 이벤트 시간(event-time) 기준으로 낮은
지연에 처리하고, 체크포인트로 **정확히 한 번(exactly-once)** 상태를 보장한다. JobManager가 조율하고
TaskManager가 병렬 처리하며, 배치는 스트림의 특수 경우로 취급한다(통합 API).

- 최신 안정: **Flink 2.3.0**(2026-06). (2.0은 2025-03의 메이저 마일스톤)

## 이 프로젝트에서의 위치 — 🚧 채택·이행중 · ✅ **Iceberg 배치 왕복 실증(2026-08-22)** · ⏸ 스트리밍 미착수

> **지금 Flink는 배치 전용이다.** 2026-08-22에 오퍼레이터 **1.15.0** + `FlinkDeployment` 세션
> 클러스터를 다시 세워 **Spark ↔ Flink Iceberg 왕복**을 닫았다(아래 §왕복 실증). 즉 "Flink가
> 이 레이크하우스에서 읽고 쓸 수 있는가"는 더 이상 미확인이 아니다.
> **다만 스트리밍(Redpanda·체크포인트·RocksDB)은 여전히 미착수**이며, 이 문서의 §운영 메모(목표)는
> 현행이 아니라 [redesign.md](../redesign.md) **Phase 3**의 설계안이다.
>
> **검증 후 세션 클러스터는 그 자리에서 내렸다.** 🔴 **사유는 시분할이 아니라 회수 규율이다** —
> 2026-08-22 실측(3워크로드 동시 상주 피크 CPU 84% / Mem 52%)으로 규약이 **시분할 금지 → 동시
> 기동 허용**으로 바뀌었고, 경계 ①은 오히려 **Flink JM 상주를 전제로** 동시 기동을 허용한다
> ([conventions/k8s.md](../conventions/k8s.md) §9-3). 그럼에도 내리는 이유는 **잡 없는 세션
> 클러스터가 JM 1 CPU / 2Gi를 놀리기 때문**이고, **예산 여유는 회수를 면제하지 않는다**
> (2026-08-19에 **13시간 샌 전력**이 있고, 발견 경로가 성능 이상이 아니라 "안 쓰는 것 정리"였다는
> 점이 이 규율의 근거다 — [conventions/k8s.md](../conventions/k8s.md) §회수 규율).
> **"중단"과 "삭제"의 분리**(trino 선례) — 자원은 즉시 회수하되 결정·검증 결과·매니페스트·러너
> 이미지는 남긴다. 오퍼레이터 복구는 `./scripts/k8s-operators.sh` 한 줄이다 — **`INSTALL_FLINK`
> 기본값이 `true`라 지정 없이 설치된다**(제외하려면 `INSTALL_FLINK=false`, 스크립트가 정본).
> 🔴 다만 이것으로 돌아오는 것은 **오퍼레이터까지**이고, 잡을 돌리려면 세션 클러스터
> (`FlinkDeployment`)를 따로 세운다(롤백 비용 ≈ 0).

- **채택 방향**: [재설계](../redesign.md)에서 컴퓨트를 **Spark(배치)+Flink(스트림)** 으로 나누며 Flink를 도입한다.
  Trino는 제거한다. 전체 로드맵은 [redesign.md](../redesign.md) Phase 3.
- **역할(Flink의 존재이유)**: MIMIC/eICU는 본래 배치 데이터지만, **`vitalsign` 등을 Redpanda로 리플레이**해
  스트림을 만들고 **이벤트타임 윈도우로 실시간 SOFA/Sepsis-3 조기경보**를 계산한다. 배치(Spark/dbt-spark)와
  **역할이 겹치지 않는** 스트리밍 유스케이스를 부여해 "엔진을 위한 엔진"을 피한다([redesign.md](../redesign.md) 급소①).
- **실행 방식**: **Flink Kubernetes Operator**(Helm)로 **`FlinkDeployment`(CRD)** 를 배포한다.
  JobManager/TaskManager를 선언적으로 관리하고, Dagster(호스트)가 잡 수명주기를 트리거·관측한다.
- **버전(실측 고정)**: 오퍼레이터 **1.15.0** / Flink **2.1.3** / Iceberg **1.11.0**.
  Flink 2.2가 나와 있어도 `iceberg-flink-runtime-2.2`가 **없어서** 2.1로 맞춘다 — 짝이 맞는 조합이 우선이다.
- **Web UI(Spark 대비 장점)**: JobManager가 상주하므로 **UI가 계속 살아 있다**(8081, `<name>-rest` Service).
  Spark는 driver JVM이 끝나면 UI도 사라져 History Server가 필요하지만, Flink 세션 클러스터는 그렇지 않다.
  접근은 `kubectl port-forward svc/<name>-rest 8081:8081`.
- **읽기 검증(2026-08-18)**: 세션 클러스터에서 **Spark가 적재한 Iceberg 테이블을 Flink SQL로 조회**
  (`iceberg.poc.sample` 3행). 두 엔진이 **같은 JDBC 카탈로그 + SeaweedFS**를 공유함을 실증했다(급소② 전제).
  🔴 **이때 검증된 것은 읽기 한 방향뿐이다** — 쓰기는 2026-08-22에 닫혔다(아래).
- **Spark 스트리밍 대비**: Flink=네이티브 스트림(레코드 단위·낮은 지연·풍부한 상태) /
  Spark Structured Streaming=마이크로배치. 저지연·상태 중심이라 Flink를 택한다.

## ✅ Iceberg 배치 왕복 실증 (2026-08-22)

**Spark 적재 → Flink 읽기 → Flink 쓰기 → Spark 읽기**를 한 바퀴 돌려 두 엔진이 같은 카탈로그·
같은 스토리지 위에서 **양방향으로** 상호운용됨을 확인했다.

| 단계 | 수행 주체 | 내용 |
| --- | --- | --- |
| ① 적재 | Spark | `iceberg.poc.sample` (3행) |
| ② 읽기 | Flink SQL | 같은 테이블을 조회 — `spark_rows = 3` |
| ③ 쓰기 | Flink SQL | `INSERT INTO iceberg.poc.sample_flink SELECT …, 'flink-batch' AS src` |
| ④ 되읽기 | Spark Connect | Flink 산출물 3행 확인, `src = 'flink-batch'` |

🔴 **삼중 증거로 닫았다.** "행이 보인다"는 단독으로는 약한 신호라, 서로 위조 관계가 없는 층 셋을 겹쳤다.

| 층 | 증거 |
| --- | --- |
| ⓐ **데이터** | 산출 행의 `src` 컬럼 값이 `flink-batch` |
| ⓑ **테이블 메타데이터** | 스냅샷 summary에 `engine-name: flink` · `iceberg-version: Apache Iceberg 1.11.0` |
| ⓒ **잡 신원** | 스냅샷의 `flink.job-id`가 **Flink 잡 overview의 `jid`와 일치** |

🔴 **같은 카탈로그에 두 엔진 서명이 공존한다** — `poc.sample`은 `1.6.1` / `spark`,
`poc.sample_flink`는 `1.11.0` / `flink`로 기록된다. 즉 커밋 주체가 메타데이터에 남으므로,
다중 writer 환경에서 **"누가 이 스냅샷을 만들었나"를 사후에 물을 수 있다**(급소② 논의의 실측 근거).

### 배치 모드라서 성립한 것 (범위를 좁혀 읽어라)

`SET 'execution.runtime-mode' = 'batch'`로 돌렸다. 🔴 **배치에서 Iceberg 싱크는 잡 완료 시점에
커밋**하므로 **체크포인트가 필요 없었고**, 그래서 `flink-s3-fs-hadoop` 플러그인을 이번에 넣지 않고도
성립했다. 스트리밍은 **체크포인트 단위로 커밋**한다.

📌 **"체크포인트가 필요 없다"가 아니라 "이 잡에는 필요 없다"** 로 읽어야 한다.
스트리밍으로 넘어가는 순간 **체크포인트 설정 + `flink-s3-fs-hadoop` 플러그인 + 러너 이미지
재빌드가 동시에** 필요해진다. 이번 성공을 "S3 플러그인 없이 된다"로 일반화하면 Phase 3 착수
시점에 같은 조사를 반복하게 된다.

### 자원 프로파일 — TaskManager는 온디맨드다

| 구성요소 | 수명 | 비용 |
| --- | --- | --- |
| JobManager | 세션 클러스터와 함께 상주 | **1000m / 2048Mi** — 유휴 비용의 전부 |
| TaskManager | 잡 제출 **+7초**에 기동, **46~52초** 생존, 잡 종료 시 자동 회수 | 잡이 없으면 0 |

⇒ 세션 클러스터를 띄워 둘 때 실제로 새는 것은 **JM 하나**다. 그래서 회수 판단이 단순하다
(잡을 안 돌릴 거면 내린다).

### 구현 방식 — `sql-client.sh -f` + ConfigMap

잡은 **ConfigMap에 담은 SQL을 `sql-client.sh -f`로 실행**하는 형태로 만들었다
(`k8s/flink/iceberg-batch-job.yaml`). **`FlinkSessionJob` CR은 쓰지 않았다** — `jarURI`가 필수라
SQL 한 장을 돌리자고 jar 빌드·배포 파이프라인을 세워야 해서 과대했다.

- **`allowed-schemes`를 `local;https` → `local`로 좁혔다.** 런타임에 외부에서 jar를 받아오는
  경로를 끊는 편이 공급망상 안전하고, 필요한 의존성은 **이미지에 굽는다**.

## 운영 메모 — 🎯 **목표(Phase 3)이지 현행이 아니다**

> 🔴 **아래는 스트리밍 계층의 설계안이다.** 2026-08-22 기준 Flink는 **배치 전용**으로만
> 검증됐고, Redpanda·체크포인트·RocksDB는 **하나도 배포되지 않았다**. 이 절을 현행 구성으로
> 읽지 않는다([philosophy.md](../philosophy.md) 원칙 7 — 설계안과 실측을 같은 문단에 두면 섞인다).

- **소스**: Redpanda(Kafka API, 경량). **싱크**: Iceberg(Spark와 동일 JDBC 카탈로그 공유, 낙관적 동시성).
- **체크포인트**: S3 호환 **SeaweedFS 재사용**(path-style 강제), 상태 백엔드 RocksDB.
  → 도입 시 `flink-s3-fs-hadoop` 플러그인·이미지 재빌드가 **함께** 필요하다(위 §배치 모드 참고).
- **자원·동시 기동**: JM+TM는 **배치(Spark)와 동시 실행이 허용**된다(2026-08-22 실측 피크
  CPU 84% / Mem 52%, 분모는 노드 Allocatable `8000m`/`22843508Ki`). 단 경계가 셋이다 —
  **Flink 상주는 JM만**(TM은 잡 제출 시 온디맨드·수명 46~52초) · **`spark.executor.instances` ≤ 1** ·
  **Redpanda 미도입**(도입 시 경계 재계산). 정본 [conventions/k8s.md](../conventions/k8s.md) §9-3,
  배분은 [resource-sizing.md](../resource-sizing.md) "Kubernetes 재설계 시나리오".
- **카탈로그 정합**: Spark·Flink 동시 writer 구조라 장기적으로 REST 카탈로그 이행 유인이 크다([redesign.md](../redesign.md) 급소②).

## ⚠️ 드리프트 교정 — cert-manager는 제거되지 않았다

2026-08-19 문서는 Flink 스택을 내리면서 **"cert-manager도 함께 제거했다"** 고 적었다.
**이 서술은 거짓이다** — cert-manager는 **줄곧 `Running`이었다**.

- **왜 그렇게 적혔나**: cert-manager를 Flink Operator의 webhook 의존으로만 인식했고,
  Flink를 내리는 커맨드 묶음에 넣었으니 지워졌으리라고 **확인 없이 기록**했다.
- **실제**: **CNPG(CloudNativePG)의 barman 플러그인이 cert-manager를 무조건 요구**한다.
  즉 카탈로그 Postgres가 살아 있는 한 cert-manager는 내려갈 수 없다.
- **교훈**: "함께 제거했다"는 **실행한 명령의 기록**이지 **관측된 상태**가 아니었다.
  제거를 적을 때는 `kubectl get`으로 **부재를 확인**한 뒤 적는다(부정 결과는 관측 경로가
  살아 있었음을 함께 확인해야 유효하다 — [philosophy.md](../philosophy.md) 원칙 7).

## 참고

- Flink 문서(stable): https://flink.apache.org/documentation/flink-stable/
- 다운로드/릴리스: https://flink.apache.org/downloads/
- Flink Kubernetes Operator: https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-main/
- Flink + Iceberg connector: https://iceberg.apache.org/docs/latest/flink/
- Redpanda: https://docs.redpanda.com/
