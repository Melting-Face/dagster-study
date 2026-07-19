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
