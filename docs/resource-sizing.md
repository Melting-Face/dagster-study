# 리소스 산정 (resource sizing)

호스트(Docker)에 할당된 CPU·메모리에 맞춰 각 서비스의 옵션을 조정한다.
**서비스 메모리 한도의 합 ≤ 호스트 RAM − OS/버퍼 여유(약 1~2 GB)** 를 유지한다.

> 조정 지점은 이 문서에서 한곳으로 관리하고, `compose.yml`의 `deploy.resources`와
> 각 서비스 설정 파일을 함께 맞춘다. (단순함·명시적 — [philosophy.md](philosophy.md))

> **문서 구성**: 아래 "Kubernetes 재설계 시나리오"는 **목표(이행) 배분**([redesign.md](redesign.md)),
> 그 이후 섹션(Trino·Dagster·Postgres…)은 **현행 compose 배분**이다. Trino는 재설계에서 제거되므로
> Trino 섹션은 이행 완료 시 레거시 참조가 된다.

## Kubernetes 재설계 시나리오 (kind + Podman · 6 CPU / 16 GB) 🚧

> 대상: [redesign.md](redesign.md)의 목표 토폴로지. **Dagster는 호스트**(이 예산 밖), 컴퓨트·데이터
> 서비스만 로컬 K8s(kind on Podman)에 둔다. 컴퓨트는 **Spark(배치) / Flink(스트리밍)** 2엔진이며 **시분할** 한다.

### (A) podman machine(VM) 예산 = 6 CPU / 16 GB / disk 120 GB

```bash
# macOS(Apple Silicon): 자원은 머신 생성 시 확정(사후 변경은 재생성 필요), kind는 rootful 요구
podman machine init dagster-k8s --rootful --cpus 6 --memory 16384 --disk-size 120
podman machine start dagster-k8s
export KIND_EXPERIMENTAL_PROVIDER=podman
kind create cluster --name lakehouse --config kind-cluster.yaml
```

- **호스트 headroom(중요)**: 16 GB는 VM에 통째 할당된다. Dagster(webserver+daemon+메타 Postgres)가
  **호스트**에서 도므로 **호스트 총 RAM ≥ 24 GB(권장 32 GB)**. 미달 시 VM 메모리를 낮춘다.
- **disk 120 GB**: SeaweedFS(원천 csv.gz + Iceberg parquet) + Redpanda 로그 + 이미지 레이어 대비.

### (B) 컴포넌트 배분 (requests / limits) — 2엔진 시분할

원칙: **Σrequests ≤ 할당가능(≈5.5 CPU / ~14 GiB)**. **BATCH(Spark)와 STREAM(Flink)은 동시 실행 금지**
(동시 피크 ≈ 6.85 CPU로 초과). 한 번에 한 엔진만 띄운다.

| 구분 | 워크로드 | req CPU | req Mem | lim CPU | lim Mem |
| --- | --- | --- | --- | --- | --- |
| **상주(baseline)** | kube-system(kind CP·CNI·coredns·local-path) | 0.5 | 1.5Gi | — | — |
| | Spark Operator(Apache, **JVM**) | 250m | 512Mi | 500m | 1Gi |
| | Flink Operator | 200m | 512Mi | 500m | 1Gi |
| | SeaweedFS(master+volume+filer+s3) | 300m | 768Mi | 1 | 1.5Gi |
| | **CloudNativePG 오퍼레이터**(컨트롤러) | 100m | 200Mi | 250m | 384Mi |
| | Catalog Postgres(Iceberg JDBC, CNPG `Cluster` 1인스턴스) | 250m | 512Mi | 500m | 768Mi |
| | **Spark Connect 서버**(Phase 1, dbt 접속용) | 500m | 1.5Gi | 1 | 2Gi |
| | **ingress-nginx 컨트롤러**(UI 고정 URL) | 100m | 90Mi | — | — |
| | **상주 소계** | **~2.2** | **~5.5Gi** | | |
| **BATCH(일시)** | Spark driver | 1 | 1Gi | 1 | 1.5Gi |
| | Spark executor × 2 | 2 | 4Gi | 1/ea | 2.5Gi/ea |
| | **BATCH 피크(상주+Spark)** | **~4.7** | **~9.1Gi** | | ✅ 6/16 내 |
| **STREAM(일시)** | Redpanda(dev, 1 broker) | 500m | 1.5Gi | 1 | 2Gi |
| | Flink JobManager | 1 | 1.5Gi | 1 | 2Gi |
| | Flink TaskManager × 1(2 slot) | 1 | 2Gi | 1 | 2.5Gi |
| | **STREAM 피크(상주+Flink)** | **~4.2** | **~9.1Gi** | | ✅ 6/16 내 |

> ingress-nginx는 **`limits`가 없는 유일한 워크로드**다(외부 매니페스트 그대로, [conventions/k8s.md](conventions/k8s.md) §2 예외).
> 상주 부하가 작아 예산에는 영향이 미미하지만, 상한이 없다는 점은 인지하고 쓴다.

> 🔴 **Spark Operator 행 정정 (2026-08-19)** — 종전 `100m/256Mi req · 250m/512Mi lim`은
> **Kubeflow(Go) 오퍼레이터 시절 수치**였다. 프로젝트는 Apache 오퍼레이터(**JVM**)로 이전했는데
> 이 표를 재검토하지 않아, 아래 두 가지가 동시에 성립하고 있었다.
>
> 1. **표가 거짓을 말했다** — `scripts/k8s-operators.sh`에 근거 주석만 있고 `--set`이 빠져
>    실제로는 차트 기본값 **`1000m/2048Mi`** 가 적용됐다. helm은 값을 지정하지 않아도 에러를
>    내지 않으므로 **선언과 실제가 4~8배 벌어진 채 조용히 유지**됐다(실사용은 196Mi — 10.7배 과예약).
> 2. **표대로 집행했으면 오퍼레이터가 죽었다** — 차트 jvmArgs가 `-XX:MaxRAMPercentage=80`이라
>    힙 상한이 컨테이너 한도에 직접 연동된다. 한도 `256Mi` → 힙 205Mi인데 실측 `RssAnon`이
>    이미 193MB라 기동 즉시 OOMKill이다.
>
> 새 값(`250m/512Mi req · 500m/1Gi lim`)은 **실측 196Mi 기준 한도 1Gi(힙 819Mi)로 약 4배 여유**이며,
> `InitialRAMPercentage=80`+`AlwaysPreTouch` 선점이 유효해지더라도 한도 안에 들어온다
> (= **선점 유효/무효 어느 가설에서도 안전**). 측정은 `crictl stats`와 컨테이너 내부
> `/proc/1/status`·`cgroup memory.current`를 병행했다(kind에 metrics-server가 없다).
>
> **교훈**: 이 표는 오래 "검증된 값"으로 인용됐지만 **아무도 실측과 대조하지 않았다.**
> 오퍼레이터를 교체하면 언어 런타임이 바뀌고, 그러면 사이징 근거가 통째로 무효가 된다.
> 엔진·오퍼레이터 교체 시 **이 표의 해당 행을 함께 재측정**한다([philosophy](philosophy.md) 원칙 7).

### (C) 운영 다이얼 (초과 시 조절 순서)

0. **★★★★★ Spark Connect 서버 스케일 0** — dbt를 돌리지 않을 때 `kubectl scale deploy/spark-connect --replicas=0`.
   유일하게 **상주하는 컴퓨트**라 시분할 원칙의 예외다. 켜둔 채 잊으면 예산을 계속 갉아먹는다.
1. **★★★★★ 엔진 시분할** — BATCH(Spark)·STREAM(Flink)을 **번갈아** 실행. 대기 엔진 파드는 0으로.
2. **★★★★☆ Spark executor 수/크기** — 기본 `2 × (1core/2Gi)`. 대용량 인제스트 시 조절.
3. **★★★★☆ Flink TaskManager slot/개수** — 스트리밍 병렬도. 기본 TM 1개(2 slot).
4. **★★★☆☆ Redpanda dev 모드 메모리** — `--memory`/`--smp`로 축소, 데모 후 스케일 0.

### (C-2) 실측 (2026-08-18, kind `lakehouse` 단일 노드)

| 구성 | Requests CPU | Requests Mem |
| --- | --- | --- |
| 상주만(오퍼레이터 2종 + SeaweedFS + 카탈로그 PG + cert-manager) | 3500m (43%) | 5538Mi (24%) |
| + Flink 세션 클러스터(JM 1 + TM 1) | 4500m (56%) | 7586Mi (34%) |

> ⚠️ 위 실측은 **2026-08-18** 값으로, 이후 구성이 바뀌었다(Flink 스택 제거 / CNPG 도입).
>
> **2026-08-19 재실측** (`kubectl describe node`, CNPG 적용 직후):
>
> | 구성 | Requests CPU | Requests Mem |
> | --- | --- | --- |
> | 상주(Spark Operator + **CNPG 오퍼레이터·`Cluster` 1인스턴스** + SeaweedFS + Spark Connect + ingress) | 3200m (40%) | 5444Mi (24%) |
>
> Flink Operator가 빠지고 CNPG 2종이 들어와 **CPU는 -300m**, 메모리는 거의 같다.
>
> 🔴 **위 재실측 값의 정정 (같은 날 후속 측정)** — `3200m/5444Mi`는 **합계는 맞지만 내역이 틀렸다.**
> 이 숫자는 `describe node`의 결과를 그대로 옮긴 것이라, 그 안에 **Spark Operator 드리프트
> (선언 없이 차트 기본값 `1000m/2048Mi`)가 통째로 포함**돼 있었다. 즉 재실측이 드리프트를
> 교정한 게 아니라 **정상값으로 박제**했고, 그 결과 같은 문서의 (B) 표(당시 `100m/256Mi`)와
> (C-2) 실측이 서로 모순인데도 실측 쪽만 갱신돼 **모순이 증거가 아니라 잡음처럼 보이게** 됐다.
> 드리프트 교정 후 상주 예상치는 **약 2450m / 3908Mi**다(적용 후 재측정 필요).
>
> 🔴 **cert-manager는 빠지지 않았다** — 종전 서술은 사실과 다르다. cert-manager 3파드는 계속
> 가동 중이며(현재는 Flink가 아니라 **CNPG barman-cloud 플러그인의 TLS** 발급자다),
> `describe node` 합계에 안 잡힌 이유는 제거돼서가 아니라 **requests/limits 선언이 아예 없어서**다
> (barman-cloud도 동일). 예산표에 안 보이는 워크로드가 실제로는 약 82MiB를 쓰고 있다 —
> **"합계에 없다 = 없다"가 아니다.**
>
> podman machine 실제 할당은 **8 CPU / 22GiB**로, 문서 목표치(6/16)보다 여유가 있다.
> 목표 예산으로 좁힐 경우 위 수치가 상한에 근접하므로 시분할이 다시 필수가 된다.

### (D) 참고 수치 근거

- Flink Operator FlinkDeployment 예시: JobManager/TaskManager 각 `memory 2048m / cpu 1`(권장 예시값)
  [Apache Flink Kubernetes Operator — custom-resource/overview].
- podman machine 기본 1 CPU / 2048 MiB → 반드시 상향 지정 [podman-machine-init — Podman docs].

## 조정 지점 요약

| 서비스      | 핵심 조정 항목                                            | 위치                                              |
| ----------- | -------------------------------------------------------- | ------------------------------------------------- |
| `trino`     | JVM heap(`-Xmx`), `query.max-memory(-per-node)`, headroom | `trino/etc/jvm.config`, `trino/etc/config.properties` |
| `dagster`   | `max_concurrent_runs`, op 동시성, dbt `threads`           | `dagster.yaml`, `dbt_pipelines/profiles.yml`      |
| `postgres`  | `shared_buffers`, `work_mem`, `max_connections`           | postgres command / `postgresql.conf`             |
| `seaweedfs` | volume 수·인덱스 메모리                                   | `compose.yml`의 `seaweedfs` command               |
| 공통        | CPU·메모리 한도                                           | `compose.yml` `deploy.resources.limits/reservations` |

## Docker 서비스 자원 한도 (compose)

```yaml
services:
  trino:
    deploy:
      resources:
        limits: { cpus: "2.0", memory: 2G }
        reservations: { memory: 1G }
```

- compose v2는 비-swarm 환경에서도 `deploy.resources.limits`(cpus·memory)를 적용한다.
- 모든 서비스 `limits.memory` 합이 호스트 RAM을 넘지 않도록 한다.

## Trino

> 현재 `compose.yml`은 `trino/etc/catalog/`만 마운트한다. heap·메모리를 조정하려면
> `trino/etc/jvm.config`·`trino/etc/config.properties`를 추가하고 `trino/etc/`를 마운트한다.

메모리는 JVM heap에서 출발한다.

- `jvm.config`: `-Xmx<heap>` — 컨테이너 메모리의 약 **70~80%**
- `config.properties`:
  - `query.max-memory-per-node` — 기본 **heap × 0.3**. `per-node + heap-headroom < heap` 제약 내에서 상향 가능
  - `query.max-memory` — 클러스터 전체 한도(기본 **20GB**; 단일 노드면 per-node 수준)
  - `memory.heap-headroom-per-node` — Trino 미추적 할당용 버퍼, 기본 **heap × 0.3**

예) 컨테이너 4G → `-Xmx3G` → 기본 per-node 0.9G. 상향 시 `per-node + headroom(0.9G) < 3G` 유지(예: `query.max-memory-per-node=2GB`)

> 큰 조인/집계가 heap을 넘으면 `EXCEEDED_LOCAL_MEMORY_LIMIT`가 난다.
> 메모리를 늘리거나 쿼리를 분할/스필 설정을 검토한다.

### 메모리 설정 3중 결합 (함께 검증)

세 파일의 값이 **한 방향 제약**으로 묶여 있어, 하나만 바꾸면 기동 실패나 OOM이 난다.
아래 부등식을 위→아래로 만족시킨다.

```
compose.yml  memory limit
  └── jvm.config  -Xmx            (≤ limit − JVM 비힙 오버헤드)
        └── config.properties
              ├── memory.heap-headroom-per-node   (Trino 미추적 할당 버퍼)
              └── query.max-memory-per-node       (≤ Xmx − headroom)
```

| 파일 | 항목 | 현재값(6G 컨테이너 예) | 제약 |
| --- | --- | --- | --- |
| `compose.yml` | `deploy.resources.limits.memory` | 6G | ≥ Xmx + 비힙 오버헤드 |
| `trino/etc/jvm.config` | `-Xmx` | 예: 4~5G | < 컨테이너 limit |
| `config.properties` | `memory.heap-headroom-per-node` | 기본 Xmx×0.3 | JVM 비쿼리 오버헤드 |
| `config.properties` | `query.max-memory-per-node` | ≤ Xmx − headroom | 초과 시 쿼리 OOM |

**JVM 비힙 오버헤드**(컨테이너 limit이 `-Xmx`보다 커야 하는 이유):

```
컨테이너 limit  >  -Xmx  +  ReservedCodeCache(~256M)  +  Metaspace(~400M) + 기타
     6g         >   5G   +          256M               +      ~400M        ≈ 5.7G  (✓ 여유)
```

> `-Xmx`를 컨테이너 limit에 바짝 붙이면(예: 6G 컨테이너에 `-Xmx6G`) 비힙 영역이 밀려 컨테이너
> OOM Kill이 난다. **`-Xmx`는 컨테이너 memory의 70~80%**를 넘기지 않는다.
> 변경 시 `compose.yml`·`jvm.config`·`config.properties` 세 파일을 **함께** 검증한다.

## Dagster (동시성)

- **run 수** — `dagster.yaml`의 `concurrency.runs.max_concurrent_runs`
  : 동시 실행 run 수. 각 run은 별도 프로세스.
  (현재 프로젝트는 구방식 `run_coordinator: QueuedRunCoordinator`의 `max_concurrent_runs: 10` 사용)
- **op/asset 동시성** — `concurrency.pools.default_limit`(풀별 한도) 또는 job multiprocess executor `max_concurrent`
  : 한 run 안에서 병렬 실행되는 op 수. 보통 CPU 코어 수에 맞춘다.
- **dbt 병렬도** — `profiles.yml`의 `threads`(현재 프로파일 값은 [architecture](architectures/overview.md) 참조): Trino로 보내는 동시 쿼리 수. 호스트별 권장은 아래 프로파일 표.

```yaml
# dagster.yaml — 최신 동시성 블록
concurrency:
  runs:
    max_concurrent_runs: 10
  pools:
    default_limit: 3
```

> 적재 헬퍼(`load_heavy_csv_gz_to_iceberg`)는 run당 메모리를 `chunk_rows`로 제어한다.
> **run당 메모리 × `max_concurrent_runs` ≤ 호스트 RAM**이 되도록 둘을 함께 낮춘다.

### daemon 메모리 계산 (multiprocess OOM 방지)

`DefaultRunLauncher` + multiprocess executor는 run마다 daemon 컨테이너 안에서 **자식 프로세스를
fork**한다. fork 순간 부모 메모리가 복사(Copy-on-Write)되므로 **피크 = 부모 + 자식 합산**이
컨테이너 `memory` 한도를 넘으면 OOM Kill(SIGKILL)이 난다. 따라서 daemon `memory`는 다음으로 잡는다.

```
daemon 필요 메모리
  = 데몬 기본(~300MB)
  + max_concurrent_runs × run당 피크 메모리 × 1.5(여유율)

예) bronze 적재(청크 스트리밍, 피크 ~500MB), concurrent=2:
    300MB + 2 × 500MB × 1.5 = 1.8g → limit 2g
예) 수백만 행 DataFrame 변환(피크 ~4GB), concurrent=2:
    300MB + 2 × 4GB × 1.5 = 12.3g → limit 16g
```

**결정 절차**: ① 가장 메모리를 많이 쓰는 에셋을 특정 → ② `docker stats dagster-daemon` 또는 UI run
로그로 피크 추정 → ③ 위 공식 적용 → ④ `dagster.yaml`·`compose.yml`·`cpus`를 **함께** 수정 → ⑤ 실측 검증.

**의존성 연동 규칙** — `max_concurrent_runs`(`dagster.yaml`)와 daemon `memory`(`compose.yml`)는 강결합.
한쪽만 바꾸면 OOM 또는 낭비된 한도가 발생한다.

| 변경 | 연동 필수 | 방향 |
| --- | --- | --- |
| `max_concurrent_runs` 증가 | daemon `memory` 재계산·상향, `cpus` 상향 | `dagster.yaml` → `compose.yml` |
| `max_concurrent_runs` 감소 | daemon `memory`·`cpus` 하향 가능(절약) | `dagster.yaml` → `compose.yml` |
| 데이터 집약 에셋 추가 | 피크 메모리 재추정 → daemon `memory` 재계산 | `assets.py` → `compose.yml` |
| daemon `memory` 변경 | 호스트 가용 RAM·전체 서비스 합계 검증 | `compose.yml` 내부 |

> 새 데이터 집약 에셋(수백만 행 변환·윈도잉 등)을 추가하면 위 계산을 재실행하고 리소스 설정을 갱신한다.
> 단일 daemon이 모든 자식 프로세스의 메모리를 공유하므로, 규모가 커지면 `dagster-celery`(Worker 분리)·
> `dagster-k8s`(run당 Pod)로의 전환을 검토한다.

## Postgres

**두 벌**이고 성격이 다르다 — 자원도 따로 잡는다.

| 대상 | 담는 것 | 위치 | 튜닝 지점 |
| --- | --- | --- | --- |
| 메타 Postgres | Dagster run·이벤트·스케줄 상태 | compose(호스트) | `compose.yml` / `postgresql.conf` |
| 카탈로그 Postgres | Iceberg 테이블 메타(JDBC 카탈로그) | K8s(CNPG `Cluster`) | `k8s/catalog-postgres.yaml`의 `spec.postgresql.parameters` |

- `shared_buffers` ≈ RAM × **0.25**, `work_mem`(정렬/조인 버퍼, 연결당), `max_connections`
- 동시 run·pyiceberg 연결이 늘면 `max_connections`를 상향한다.
- 카탈로그 쪽은 **테이블 메타만** 담아 데이터가 작다 → `shared_buffers 128MB`로 충분하다.
  접속자는 Dagster(pyiceberg)·Spark·Flink·dbt 4종이라 연결 수가 먼저 병목이 된다.
- 🔴 **메타 PG를 클러스터로 옮기지 않는다** — Dagster는 호스트에 남으므로, 메타 스토리지를 kind에 두면
  클러스터가 없을 때 Dagster 자체가 기동하지 못하는 **순환 의존**이 된다.

## SeaweedFS

대체로 I/O 바운드이며, 볼륨 인덱스가 메모리를 사용한다.

- `-volume.max`(볼륨 수), 인덱스 방식(`-volume.index=leveldb`로 메모리 절감)

## 호스트 크기별 권장 프로파일 (출발점)

| 항목                                | 8 GB      | 16 GB     | 32 GB     |
| ----------------------------------- | --------- | --------- | --------- |
| trino 컨테이너 / `-Xmx`             | 2G / 1.5G | 4G / 3G   | 8G / 6G   |
| trino `query.max-memory-per-node`   | 1GB       | 2GB       | 4GB       |
| dagster `max_concurrent_runs`       | 2         | 4         | 8         |
| dbt `threads` (dev)                 | 2         | 4         | 8         |
| postgres `shared_buffers`           | 256MB     | 512MB     | 1GB       |

> 표는 출발점이며 실제 데이터량·쿼리 특성에 맞춰 조정한다.
> 변경 시 `compose.yml`·Trino 설정·`dagster.yaml`·`profiles.yml`을 함께 갱신한다.

## 참고

- Trino — Resource management properties: https://trino.io/docs/current/admin/properties-resource-management.html
- Trino — Deploying Trino(JVM config): https://trino.io/docs/current/installation/deployment.html
- Dagster — Managing concurrency: https://docs.dagster.io/guides/operate/managing-concurrency
- PostgreSQL — Resource Consumption: https://www.postgresql.org/docs/current/runtime-config-resource.html
- Docker Compose — deploy.resources: https://docs.docker.com/reference/compose-file/deploy/#resources
- SeaweedFS — wiki: https://github.com/seaweedfs/seaweedfs/wiki
- Apache Flink Kubernetes Operator — 리소스 설정: https://nightlies.apache.org/flink/flink-kubernetes-operator-docs-main/docs/custom-resource/overview/
- podman machine init(자원 지정): https://docs.podman.io/en/latest/markdown/podman-machine-init.1.html
- kind — Podman provider: https://kind.sigs.k8s.io/docs/user/rootless/
