# notebooks — 호스트 탐색용 노트북

Dagster 파이프라인 **밖**에서 레이크하우스를 ad-hoc 조회·탐색(EDA)하는 자리다.
파이프라인 정의(에셋·dbt 모델)는 여기 두지 않는다 — 정의는 `dagster_project/defs/`가 단일 출처다.

> **작성 규칙의 정본은 [`docs/conventions/analysis.md`](../docs/conventions/analysis.md)** 다
> (파일명 `NN-<slug>.ipynb` · 위→아래 1회 실행 재현 · 결론 수치는 gold/dbt 모델 경유 ·
> 반복되는 조회는 gold 모델로 승격). 이 문서는 **실행 환경**(포트·venv·접속·정리)을 다룬다.

## 실행

```shell
kubectl port-forward svc/spark-connect 15002:15002   # 필수, 별도 터미널

cd dagster/dockerfile.d/src
uv run --group notebook jupyter lab --port 8889 --notebook-dir ../../../notebooks
```

| 항목 | 값 | 이유 |
|---|---|---|
| 포트 | **8889** | 기본 8888은 compose SeaweedFS filer UI가 게시 |
| venv | **Dagster와 공유** (`dagster/dockerfile.d/src/.venv`) | `pyspark[connect]`·`pyiceberg`·`pandas`·`pyarrow`가 이미 있고, `dagster_project.common.*`를 그대로 import해 **에셋과 같은 코드로** 검증할 수 있다 |
| 의존성 | `[dependency-groups] notebook` | 런타임(`[project].dependencies`)과 분리 — 이미지·daemon에는 들어가지 않는다 |

## SQL 엔진은 Spark Connect다 (Trino 아님)

재설계에서 Trino는 **제거 대상**이고 ad-hoc 조회는 **Spark SQL**로 간다
([`docs/architectures/trino.md`](../docs/architectures/trino.md) · [`docs/redesign.md`](../docs/redesign.md) §5).
compose의 `trino`는 `--profile legacy-sql` 로만 뜬다(방언 값 대조용).

카탈로그 설정(JDBC URI·warehouse·S3·자격증명)은 **Spark Connect 서버 측**
(`k8s/spark/spark-connect-server.yaml`)에 있다. → 클라이언트는 `sc://localhost:15002`만 알면 되고
**비밀정보를 노트북에 두지 않는다**. pyiceberg로 직접 붙는 경로는 `.env`가 추가로 필요하다
(스타터 노트북 §6 참고).

## ⚠️ 셀 출력은 커밋되지 않는다

원천은 비식별 연구 데이터셋이지만 **DUA 대상**이다([`docs/security.md`](../docs/security.md)).
`.ipynb`의 셀 출력에는 조회 결과가 **그대로 박제**되고, `gitleaks`는 크리덴셜 패턴을 잡지
헬스 데이터를 잡지 못한다. 그래서 두 겹으로 막는다.

- `nbstripout` pre-commit 훅 — 커밋 시 셀 출력·실행횟수 제거 (`.pre-commit-config.yaml`)
- `.gitignore` — `**/.ipynb_checkpoints/` (Jupyter 자동 스냅샷은 출력을 그대로 담는다)

훅을 `--no-verify`로 우회해 커밋하지 않는다.

## 파일

| 파일 | 내용 |
|---|---|
| `00-lakehouse-connect.ipynb` | 접속 스타터 — port-forward 점검 → Spark Connect → 카탈로그 탐색 → pandas → Iceberg 메타데이터 → (선택) pyiceberg 직접 접속 |

## 컴퓨트 정리

Spark Connect는 클러스터의 **유일한 상주 컴퓨트**다. 오래 안 쓸 거면 내린다
([`docs/conventions/k8s.md`](../docs/conventions/k8s.md)).

```shell
kubectl scale deploy/spark-connect --replicas=0
```
