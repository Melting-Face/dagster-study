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

1. **`.env.example`에 키와 형식 예시를 추가**한다(값은 비움).
   > 현재 이 레포에는 `.env.example`이 없다. 신규 참여자 온보딩·전파 누락 방지를 위해
   > `.env`의 **키만** 담은 `.env.example`을 두는 것을 권장한다.
2. `compose.yml`에서 그 값을 **사용하는 서비스**에 `- KEY=${KEY}`가 있는지 확인하고 없으면 추가한다.
   - 공용 앵커 **`x-dagster-common`**(`&dagster-common`)을 상속하는 서비스(webserver·daemon)는
     **앵커에 한 번만** 추가하면 둘 다 전파된다.
   - 앵커를 상속하지 않는 서비스(`trino`·`discord-bot` 등)는 해당 서비스의 `environment:`에 직접 추가한다.
3. **에셋 실행 컨테이너**에 전파되는지 확인한다. 이 레포는 `DefaultRunLauncher`라 run이
   **daemon in-process 서브프로세스**로 돌아 daemon 서비스 env로 커버된다. 향후
   `DockerRunLauncher` 등 별도 컨테이너로 바꾸면 그 컨테이너 env에도 추가해야 한다.
4. 코드에서 `dg.EnvVar("KEY")`(필수) 또는 `os.environ.get("KEY", ...)`(선택)로 참조한다.

> 예) `AWS_*`·`ENDPOINT_URL`은 `x-dagster-common` 앵커에 있어 webserver·daemon에 전파되고,
> `trino` 서비스는 앵커를 안 쓰므로 `environment:`에 `AWS_*`를 **별도로** 나열한다(현재 구현).

## 2. 운영 정책 (보존·만료)

> 아래 항목은 **미설정** 상태다. 팀(개인) 논의 후 결정하고 이 표를 갱신한다.

| 항목 | 현재 동작 | 상태 | 비고 |
| --- | --- | --- | --- |
| Iceberg snapshot 유지기간 | `expire_snapshots()` 호출 시에만 만료 → 미실행 시 **무제한 누적** | **논의 필요** | 주기적 만료 스케줄(에셋/잡) 미설정. 스냅샷·orphan 파일이 SeaweedFS 용량 잠식 |
| SeaweedFS(`s3://warehouse`) 용량 | 수명주기 정책 없음 | **논의 필요** | compute-log·중간 산출물 정리 정책 미설정 |
| Docker 컨테이너 로그 유지 | `max-size: 10m` × `max-file: 20` → 컨테이너당 **최대 200MB** | 설정됨 | [conventions/docker.md](conventions/docker.md) §1-1. 시간 기반 순환은 미설정 |

> Iceberg 스냅샷 만료는 데이터 거버넌스·비용(스토리지) 관점에서 우선 검토 대상이다.
> 만료 주기를 정하면 Dagster 잡/스케줄로 `expire_snapshots`·`remove_orphan_files`를 자동화하고
> 이 표와 [resource-sizing.md](resource-sizing.md)를 함께 갱신한다.

## 참고

- Dagster — Environment variables & secrets: https://docs.dagster.io/guides/deploy/using-environment-variables-and-secrets
- Docker Compose — 환경변수 보간: https://docs.docker.com/reference/compose-file/interpolation/
- Iceberg — Maintenance(expire snapshots): https://iceberg.apache.org/docs/latest/maintenance/
