# 리소스 산정 (resource sizing)

호스트(Docker)에 할당된 CPU·메모리에 맞춰 각 서비스의 옵션을 조정한다.
**서비스 메모리 한도의 합 ≤ 호스트 RAM − OS/버퍼 여유(약 1~2 GB)** 를 유지한다.

> 조정 지점은 이 문서에서 한곳으로 관리하고, `compose.yml`의 `deploy.resources`와
> 각 서비스 설정 파일을 함께 맞춘다. (단순함·명시적 — [philosophy.md](philosophy.md))

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

## Dagster (동시성)

- **run 수** — `dagster.yaml`의 `concurrency.runs.max_concurrent_runs`
  : 동시 실행 run 수. 각 run은 별도 프로세스.
  (현재 프로젝트는 구방식 `run_coordinator: QueuedRunCoordinator`의 `max_concurrent_runs: 10` 사용)
- **op/asset 동시성** — `concurrency.pools.default_limit`(풀별 한도) 또는 job multiprocess executor `max_concurrent`
  : 한 run 안에서 병렬 실행되는 op 수. 보통 CPU 코어 수에 맞춘다.
- **dbt 병렬도** — `profiles.yml`의 `threads`(현재 프로파일 값은 [architecture](architecture.md) 참조): Trino로 보내는 동시 쿼리 수. 호스트별 권장은 아래 프로파일 표.

```yaml
# dagster.yaml — 최신 동시성 블록
concurrency:
  runs:
    max_concurrent_runs: 10
  pools:
    default_limit: 3
```

> 적재 템플릿(`template/`)은 run당 메모리를 `chunk_rows`로 제어한다.
> **run당 메모리 × `max_concurrent_runs` ≤ 호스트 RAM**이 되도록 둘을 함께 낮춘다.

## Postgres

Dagster 메타데이터 + Iceberg JDBC 카탈로그를 함께 담는다. 접속자: Dagster·Trino·dbt·pyiceberg.

- `shared_buffers` ≈ RAM × **0.25**, `work_mem`(정렬/조인 버퍼, 연결당), `max_connections`
- 동시 run·Trino 워커·pyiceberg 연결이 늘면 `max_connections`를 상향한다.

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
