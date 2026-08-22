# 모니터링 · 관측 (아키텍처 · 프로젝트 관점)

## 개요

**Prometheus**는 **pull(스크레이프) 모델**의 시계열 수집기다. 서버가 설정된 타깃의
`/metrics` 엔드포인트를 주기적으로 긁어 라벨 붙은 시계열로 저장하고, PromQL로 질의한다.
서비스가 직접 메트릭을 내지 못하면 **exporter**(노드·DB·큐 등 전용 어댑터)를 앞에 두어
`/metrics`를 대신 노출시킨다. 임계 조건은 **rule_files**의 알림 규칙으로 평가하고,
발화된 알림의 묶음·중복 제거·라우팅은 별도 컴포넌트인 **Alertmanager**가 맡는다.

즉 관측이 성립하려면 **① 타깃(무엇을 볼지) ② 수집기(긁는 주체) ③ 규칙·라우팅(무엇을 알릴지)**
셋이 이어져야 하고, 하나만 있어도 나머지가 없으면 데이터는 생기지 않는다.

## 이 프로젝트에서의 위치 — 🔎 미채택 (선언 잔존 · 수집 대상이 정본과 갈림)

🔴 **상태 마커 근거**: `compose.yml`에 Prometheus **정의가 있다**. 그래서 ✅(채택)로 읽히기 쉽다.
그리고 ⚠️ **`--profile monitoring`으로 띄우면 실제로 타깃 2개가 다 산다** — `seaweedfs`에
`monitoring` profile이 함께 걸려 있어(`compose.yml:162-165`, 바로 위 `:159-161` 주석이 그 이유를
"prometheus가 `seaweedfs:9324` 메트릭을 수집"으로 적어 뒀다) 그 컨테이너가 같이 뜨고
`-metricsPort=9324`(`:173`)로 응답한다. **수집기가 죽어 있는 상태가 아니다.**

🔴 **단절은 수집기가 아니라 대상에 있다.** 오브젝트 스토리지 **정본은 2026-08-19에 K8s로 이전**됐고
compose 쪽은 `legacy-storage` profile로 **상시 기동만 끊긴 레거시**다. 그런데 정본인
`k8s/seaweedfs.yaml`에는 메트릭 포트가 없다. 즉 수집기는 **살아 있는 채로 정본이 아닌 대상을 보고 있다.**
🔴 이것이 더 나쁜 종류의 고장이다 — **켜면 초록불이 뜨기 때문에 검산을 통과하며 남는다.**
"수집이 되고 있다"는 관측은 참이지만 그 문장이 세고 있는 대상이 이미 정본이 아니다
([../conventions/monitoring.md](../conventions/monitoring.md) §3 — 경로 생존과 판별력은 다른 축이다).

정의가 있으니 🔎(미도입)이라고만 하기도 어렵고, 이행 작업이 진행 중이지 않으니 🚧도 아니다.
그래서 **🔎 미채택 + "선언은 남아 있고 수집 대상이 정본과 갈렸다"** 로 표기한다.
이것은 [../conventions/monitoring.md](../conventions/monitoring.md) §2가 막으려는 것 —
**수집기가 만들어내는 거짓 신호** — 의 실제 사례이되, 형태가 한 단계 고약하다.
§2의 전형은 *타깃이 없는* 수집기이고 여기는 **타깃이 있는데 그 타깃이 정본이 아닌** 경우다.
전자는 켜 보면 비어 있어 들키지만, 후자는 **켜면 채워진다.**

### 현행 사실

> **관측 시각** 2026-08-22 10:59 KST(`date` 실측) · **모집단** 저장소 전체(`compose.yml` 서비스 6개,
> `k8s/**` 매니페스트, `dagster/dockerfile.d/src/` 설정, `dagster_project/` 코드) ·
> **계측 도구** `grep -rn` / `cat` / `sed -n`(파일 정적 판독. 러닝 클러스터 질의 아님).
> ⚠️ 아래 "0건"은 검색 경로가 살아 있음을 대조군으로 확인한 뒤 적었다 —
> 같은 조건의 `readinessProbe` 검색이 **2건 hit**했다([../conventions/monitoring.md](../conventions/monitoring.md) §3).

| 축 | 선언 | 실제 |
| --- | --- | --- |
| **Prometheus** | `compose.yml:186-206` · profile `monitoring` · `prom/prometheus:v2.21.0` · 포트 `9000:9090` · `deploy.resources` 1 CPU / 1G | **healthcheck 없음**, `depends_on`이 조건 없는 구식 리스트([../conventions/docker.md](../conventions/docker.md) §1-4 미준수) |
| **스크레이프 타깃** | `prometheus/prometheus.yml`(11줄, 이 디렉터리의 **유일한 파일**) | `prometheus:9090`(self) + `seaweedfs:9324` **2개뿐** · `scrape_interval: 30s` · `rule_files` · `alerting`(Alertmanager) · `remote_write` **전무** |
| **SeaweedFS 메트릭** | compose는 `-metricsPort=9324`(`compose.yml:173`), 호스트 미게시(내부 스크레이프 전용). `monitoring` profile이 함께 걸려 있어(`:162-165`) 수집기와 같이 뜬다 | **compose 쪽은 응답한다** — 다만 그 대상이 `legacy-storage`, 즉 **정본이 아니다**(스토리지 정본은 2026-08-19 K8s로 이전). 🔴 그리고 **정본인 `k8s/seaweedfs.yaml`의 `args`에는 `-metricsPort`가 없고 포트도 s3·filer·master 3개뿐** — 이 두 사실이 겹쳐 **응답하는 대상과 정본이 갈렸다** |
| **compose healthcheck** | 서비스 6개 | **2개만** — `postgres`(`pg_isready`) · `trino`(`curl /v1/info`). `dagster-webserver`·`dagster-daemon`·`seaweedfs`·`prometheus` 없음 |
| **K8s probe** | — | readiness **2개뿐** — `k8s/spark/spark-connect-server.yaml`(tcpSocket 15002) · `k8s/spark/spark-thrift-server.yaml`(exec/beeline `SELECT 1`). liveness·startup 0건 |
| **Prometheus Operator** | — | **미설치**(`scripts/k8s-operators.sh`는 Spark·Flink·CNPG만 설치). `k8s/` 전체에 `ServiceMonitor`·`PodMonitor`·`PrometheusRule` **0건** |
| **Dagster 설정** | `dagster/dockerfile.d/src/dagster.yaml` 최상위 키 7개(scheduler · run_coordinator · run_launcher · run_storage · schedule_storage · event_log_storage · telemetry) | **`run_monitoring` 없음**, **`compute_logs` 미설정**(기본 `LocalComputeLogManager`), `telemetry.enabled: true` |
| **Dagster 알림** | — | `dagster_project` 전체에 sensor · `@asset_check` · Slack/이메일 알림 **0건** |
| **Dagster 스케줄** | `defs/automation.py`의 `dbt_all_schedule`, cron `0 * * * *`, `execution_timezone="Asia/Seoul"` | `default_status=STOPPED` — 근거 주석이 신호 포화(배경 소음)를 든다 |
| **Flink 오퍼레이터 메트릭** | `k8s/flink/operator-values.yaml`의 `kubernetes.operator.metrics.reporter.slf4j.*` | **slf4j 리포터**, `interval: 5 MINUTE` → **로그로만** 나간다. Prometheus 리포터 미설정 |
| **Spark 메트릭** | driver UI 4040 Ingress만 | `k8s/spark/` 전체에 `prometheus`·`jmx` **0건** — `spark.ui.prometheus.enabled`·JMX exporter 미설정 |
| **Grafana · Alertmanager · exporter** | — | 저장소 전체 **0건** |
| **실질 관측 수단** | — | ⓐ Docker json-file 로그 ⓑ Dagster `context.log` + 머티리얼라이즈 메타데이터 ⓒ Spark·Flink Web UI(Ingress) ⓓ readinessProbe 2개 |

### 대안 비교 — 왜 지금 쓰지 않는가

⚠️ 아래는 **현재 미채택인 이유**를 적은 것이지 도입 계획이 아니다. 상시 컴포넌트를 하나 올리는 것은
컴퓨트 예산을 직접 깎는 선택이고, 예산의 단위·배분은 [../resource-sizing.md](../resource-sizing.md)가
정본이다(수치는 여기 옮기지 않는다).

| 후보 | 무엇을 주나 | 현재 안 쓰는 이유 |
| --- | --- | --- |
| **Grafana** | 대시보드·시각화 | 🔴 **볼 만한 데이터가 없다** — 대시보드가 비어서가 아니라 **채워지는 것이 이 스택의 실제 상태가 아니어서**다. 수집 대상은 레거시 스토리지 1종뿐이고, **정본 워크로드(K8s의 Spark·Flink·CNPG·SeaweedFS)는 하나도 스크레이프되지 않는다**. 이 상태로 대시보드를 붙이면 초록 화면이 관측을 대신한다. 상주 파드가 하나 더 늘어 예산도 소비한다 |
| **kube-prometheus-stack** | Operator + Prometheus + Alertmanager + Grafana + 기본 룰 일괄 | 한 번에 상주 컴포넌트 여럿이 붙어 **가장 비싼 선택**이다. 현재 클러스터의 상주 컴퓨트는 필요할 때만 올리고 쓰지 않으면 내리는 규율로 관리한다([../conventions/k8s.md](../conventions/k8s.md) §9-3) — 그 규율과 정면으로 충돌한다 |
| **metrics-server** | `kubectl top` 수준의 리소스 사용량 | 🔴 **kind 클러스터에 없다** — 그래서 자원 실측은 `/proc/1/status`·cgroup `memory.current` 병행으로 대신하고 있다([../resource-sizing.md](../resource-sizing.md)). 즉 **없는 상태가 실측 절차에 이미 반영돼 있다** |
| **Alertmanager** | 알림 묶음·중복 제거·라우팅 | **알릴 규칙이 없다**(`rule_files` 0건). 발화원 없이 라우터만 두면 §2의 거짓 신호가 하나 더 늘어난다. 단일 사용자 학습 환경이라 수신 채널·당직 개념도 없다 |
| **exporter 계열**(node·postgres 등) | 서비스별 `/metrics` | 수집기는 살아 있으나 **정본 워크로드를 스크레이프하도록 배선돼 있지 않다**. 그 상태에서 exporter부터 붙이면 **내보내는 쪽만 늘고 읽는 쪽이 없다**(순서가 거꾸로다) |

## 운영 메모

- 🔴 **수집 대상과 정본이 갈린 것이 이 문서의 핵심 사실이다.** SeaweedFS 메트릭
  (`-metricsPort=9324`)은 compose 정의에 **그대로 살아 있다** — 사라진 것은 메트릭이 아니라
  **정본의 자리**다. 오브젝트 스토리지 정본이 K8s로 이전됐는데(2026-08-19)
  `k8s/seaweedfs.yaml`에는 해당 인자도 포트도 **만들어지지 않았다**. 그래서 수집기는 계속 응답을
  받지만 그 응답은 레거시 쪽에서 온다. **compose와 K8s의 관측 수준이 갈린 지점**이다.
  🔴 **이 상태는 가설이 아니라 이 저장소에서 한 번 실현된 실패 양식이고, 방향만 거울상이다.**
  2026-08-18에 "원천 데이터가 어디에도 없다"고 판정한 적이 있고 **다음 날 오진으로 정정**됐다
  ([../redesign.md](../redesign.md) Phase 2 정정 · [../philosophy.md](../philosophy.md)
  §*#7의 근거 — 실패가 실패로 보이지 않는다*의 사례표).
  그때는 **사람이 K8s만 조회하고 compose를 놓쳤다** — compose 컨테이너가 `Exited`라 S3 API가 죽어
  있었고 그 조회 실패가 "버킷 0개"로 읽혔다 → **있는 것을 없다고** 판정.
  지금은 **수집기가 compose를 보고 K8s를 놓친다** → **안 보는 것을 본다고** 판정.
  🔴 **원인은 같다 — SeaweedFS가 compose와 K8s에 이중으로 존재한다.** 방향만 뒤집혔다.
  ⚠️ 그리고 갈리는 것이 하나 더 있다. **발견 경로**다. 2026-08-18은 사람이 그 자리에서 한 번
  데었기 때문에 드러났지만, 지금 그 자리에서 답하는 것은 **초록불을 띄우는 수집기**다.
  ⚠️ 이것을 *결정*으로 적어 둔 문장은 찾지 못했다 — 모집단 `docs/**/*.md`,
  키워드 `metricsPort`·`9324` 검색에서 hit는 [../conventions/docker.md](../conventions/docker.md)의
  compose profile 설명 1건뿐이었다(2026-08-22 10:59 KST). **"기록이 없다"이지 "결정이 없었다"가 아니다.**
- Prometheus 이미지가 **`prom/prometheus:v2.21.0`** 이고, 이는 **2020-09-11 릴리스**다.
  현재 최신 안정은 **`v3.14.0`(2026-08-17)** 으로 **메이저 한 계열이 통째로 뒤에 있다**
  (관측 시각 2026-08-22 · 출처 GitHub 릴리스 이력, 아래 §참고). 버전 고정 자체는 규칙에 맞다
  ([../conventions/docker.md](../conventions/docker.md) §1-3) — **문제는 고정이 아니라
  갱신된 적이 없다는 것**이고, 이 격차를 "관리되는 고정"이 아니라 **방치의 신호**로 읽는다.
- **Prometheus 자신에 healthcheck가 없다.** 수집기가 죽어도 compose는 정상으로 보고한다 —
  "메트릭이 0"과 "수집기가 죽었다"를 구분할 수단이 그 서비스 자체에 없다
  ([../conventions/monitoring.md](../conventions/monitoring.md) §3).
- **kind에는 metrics-server가 없다.** 클러스터 자원 관측은 `kubectl top`이 아니라
  파드 내부 `/proc`·cgroup 판독으로 하고 있으며, 실측 절차와 수치는
  [../resource-sizing.md](../resource-sizing.md)가 정본이다.
- **Flink 오퍼레이터 메트릭은 로그로만 나간다**(slf4j 리포터, 5분 간격). 값은 남지만
  시계열로 질의할 수 없고, 로그 보존 정책([../operations.md](../operations.md) §2)의 수명을 따른다.
- **Dagster 쪽 관측은 실행 기록에 의존한다** — `run_monitoring` 미설정이라 워커가 죽은 런의
  자동 판정이 없고, `compute_logs`가 기본값이라 스텝 로그는 컨테이너 로컬에 남는다.
  자산 단위 관측은 머티리얼라이즈 메타데이터가 담당한다([../conventions/dagster.md](../conventions/dagster.md)).
- 관측 수단을 더하거나 뺄 때의 **규칙**(등록 의무·수집기 정리·생존 확인·수치 기재)은
  [../conventions/monitoring.md](../conventions/monitoring.md)가 정본이다.
- ⚠️ **이 문서의 무게는 실행 환경에 걸려 있다.** 위 공백들이 지금 수용 가능한 것은 현행 검증 환경이
  **로컬 단독**이기 때문이다 — kind는 `listenAddress: "127.0.0.1"`(`k8s/kind-cluster.yaml`)이라
  LAN에서 도달할 수 없고, [oci.md](oci.md)의 OCI 스택은 **⏸ 보류**로 컴퓨트가 서 있지 않다.
  🔴 **OCI를 재개해 인터넷에 면한 노드가 생기면 이 판단이 그대로 살아나지 않는다** — 같은 공백이
  **탐지 공백**으로 성격이 바뀌고, 위 표는 그 노드에서 무엇을 못 보는지의 목록이 된다.
  [../security.md](../security.md) 2.6·2.11과 함께 다시 읽어야 하는 지점이다.

## 참고

- Prometheus — Overview: https://prometheus.io/docs/introduction/overview/
- Prometheus — Configuration(`scrape_configs`·`rule_files`): https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- Prometheus — 릴리스 이력(버전·릴리스일 1차 출처): https://github.com/prometheus/prometheus/releases
- Prometheus Operator(ServiceMonitor·PodMonitor 제공 주체): https://prometheus-operator.dev/
- Kubernetes SIGs — metrics-server: https://github.com/kubernetes-sigs/metrics-server
- Apache Flink Kubernetes Operator(메트릭 리포터 설정): https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-main/
- Dagster 문서(`run_monitoring`·`compute_logs` 설정): https://docs.dagster.io/
- 관측 **규칙** 정본: [../conventions/monitoring.md](../conventions/monitoring.md)
