# 환경변수·운영 정책 (operations)

> **목적**: 환경변수 주입 방식과 데이터 보존 등 운영 정책을 한곳에서 관리한다.
> **언제 읽나**: 새 환경변수 추가, 서비스 추가, 보존기간·만료 정책 결정 시.
> **연관**: [conventions/docker.md](conventions/docker.md), [conventions/general.md](conventions/general.md)(비밀정보), [resource-sizing.md](resource-sizing.md).

`data-pipeline` 레포에서 이식·적응.

## 1. 환경변수 주입

- 민감한 값(DB 비밀번호, S3 키, 토큰)은 반드시 `.env`에 정의하고 **코드·설정에 하드코딩하지 않는다.**
- Python 코드에서는 `dg.EnvVar("KEY")`(리소스 config) 또는 `os.environ["KEY"]`(즉시 필요)를 쓴다.
- `os.environ.get("KEY", "default")`는 **선택적** 환경변수에만 쓴다.
- `.env`는 절대 커밋하지 않는다(`.gitignore`에 포함). Trino 카탈로그 등 설정 파일은 `${ENV:KEY}`로 치환.

```python
# Good — 참조로 주입
S3Resource(aws_access_key_id=dg.EnvVar("AWS_ACCESS_KEY_ID"))

# Bad — 하드코딩
S3Resource(aws_access_key_id="AKIAIOSFODNN7EXAMPLE")
```

### 1-1. 환경변수 추가 시 전파 확인 (의존성 관리)

새 환경변수는 **코드에서 참조하는 것으로 끝내지 않고, 그 값을 실제로 사용하는 컨테이너까지
주입되는지** 확인한다. `.env`에만 있고 서비스에 전달되지 않으면 컨테이너 안에서
`KeyError`·인증 실패가 난다. 아래 체인을 위→아래로 모두 채운다.

```
.env.example  (형식·예시 문서화, 값은 비움 — 팀 공유용, 커밋)
    │
.env          (실제 값, 커밋 금지)
    │
compose.yml   (${KEY} 보간 → 컨테이너 environment)
    │
dg.EnvVar("KEY") / os.environ["KEY"]  (코드에서 참조)
```

**절차**:

1. **`.env.example`에 키와 형식 예시를 추가**한다(값은 비움 — 커밋 대상).
2. `compose.yml`에서 그 값을 **사용하는 서비스**에 `- KEY=${KEY}`가 있는지 확인하고 없으면 추가한다.
   - 공용 앵커 **`x-dagster-common`**(`&dagster-common`)을 상속하는 서비스(webserver·daemon)는
     **앵커에 한 번만** 추가하면 둘 다 전파된다.
   - 앵커를 상속하지 않는 서비스(`trino`·`seaweedfs` 등)는 해당 서비스의 `environment:`에 직접 추가한다.
3. **에셋 실행 컨테이너**에 전파되는지 확인한다. 이 레포는 `DefaultRunLauncher`라 run이
   **daemon in-process 서브프로세스**로 돌아 daemon 서비스 env로 커버된다. 향후
   `DockerRunLauncher` 등 별도 컨테이너로 바꾸면 그 컨테이너 env에도 추가해야 한다.
4. 코드에서 `dg.EnvVar("KEY")`(필수) 또는 `os.environ.get("KEY", ...)`(선택)로 참조한다.

> 예) `AWS_*`·`ENDPOINT_URL`은 `x-dagster-common` 앵커에 있어 webserver·daemon에 전파되고,
> `trino` 서비스는 앵커를 안 쓰므로 `environment:`에 `AWS_*`를 **별도로** 나열한다(현재 구현).

### 1-2. 호스트 실행과 컨테이너 실행의 값이 다른 키

재설계 토폴로지에서 Dagster는 **호스트**(`uv run dg dev`)에서 돌고 메타 Postgres는 **compose**에 있다
([conventions/k8s.md](conventions/k8s.md) §8). 같은 키라도 **누가 읽느냐에 따라 값이 달라진다**.

| 키 | 컨테이너(compose) | 호스트(`dg dev`) |
| --- | --- | --- |
| `POSTGRES_HOST` | `postgres`(서비스명) — `compose.yml`이 **리터럴로 고정** | `localhost` — `.env` 값 사용 |

- `dagster.yaml`의 `hostname`은 **하드코딩하지 않고** `env: POSTGRES_HOST`로 참조한다.
  하드코딩하면 호스트 실행 시 이름 해석이 안 돼 `too many retries for DB connection`으로 죽는다(2026-08-18 실측).
- compose `postgres`는 호스트가 붙을 수 있도록 **`127.0.0.1:${POSTGRES_PORT}:5432`** 로 퍼블리시한다
  (루프백 바인딩 — 외부 노출 금지, [security.md](security.md)).
- 호스트 실행 시 **`DAGSTER_HOME`을 `dagster.yaml`이 있는 디렉터리**(`dagster/dockerfile.d/src`)로 지정한다.
  지정하지 않으면 임시 sqlite 인스턴스가 쓰여 **UI에 런이 안 남는다**.
- **dbt-spark 타깃 키**(`ICEBERG_*`·`SPARK_REMOTE`)도 같은 성격이다. 호스트에서 dbt를 돌리면
  in-cluster 서비스(카탈로그 Postgres·SeaweedFS·Spark Connect)에 **port-forward가 필요**하므로
  `.env` 기본값은 `localhost:<로컬포트>`를 가리킨다. 클러스터 안에서 도는 워크로드는
  매니페스트가 서비스명(`catalog-postgres`·`seaweedfs`)을 직접 주입한다.

## 2. 운영 정책 (보존·만료)

> 아래 항목은 **미설정** 상태다. 팀(개인) 논의 후 결정하고 이 표를 갱신한다.

| 항목 | 현재 동작 | 상태 | 비고 |
| --- | --- | --- | --- |
| Iceberg 유지보수(컴팩션·만료·orphan) | `iceberg_maintenance_job`이 **매주 일요일 03:00 KST**에 대용량 3테이블을 **컴팩션(Trino optimize) → 스냅샷 만료(`SNAPSHOT_RETENTION_DAYS` 기본 7일) → orphan 정리(Trino)** 순서로 처리(순서 강제)([`defs/maintenance.py`](../dagster/dockerfile.d/src/src/dagster_project/defs/maintenance.py)) | **부분 구현** | 보존기간(기본 7일)·컴팩션 임계값(기본 100MB)·대상 테이블 범위는 **확정 필요**([security.md §4-1](security.md)) |
| SeaweedFS(`s3://warehouse`) 용량 | 수명주기 정책 없음 | **논의 필요** | compute-log·중간 산출물 정리 정책 미설정 |
| Docker 컨테이너 로그 유지 | `max-size: 10m` × `max-file: 20` → 컨테이너당 **최대 200MB** | 설정됨 | [conventions/docker.md](conventions/docker.md) §1-1. 시간 기반 순환은 미설정 |

> Iceberg 유지보수는 `iceberg_maintenance_job`(주간 스케줄, **컴팩션→만료→orphan** 순서)으로
> 자동화했다(컴팩션·orphan은 Trino 프로시저). 남은 결정은 **보존기간(기본 7일)·컴팩션 임계값
> (기본 100MB)·대상 테이블 범위** 확정이며, 확정 시 이 표·[security.md §4-1](security.md)·[resource-sizing.md](resource-sizing.md)를 함께 갱신한다.

## 참고

- Dagster — Environment variables & secrets: https://docs.dagster.io/guides/deploy/using-environment-variables-and-secrets
- Docker Compose — 환경변수 보간: https://docs.docker.com/reference/compose-file/interpolation/
- Iceberg — Maintenance(expire snapshots): https://iceberg.apache.org/docs/latest/maintenance/
