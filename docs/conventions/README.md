# 코딩·운영 컨벤션 (conventions)

이 프로젝트의 **규칙 정본**이 모여 있는 디렉터리다. 각 규칙의 정본은 **여기 한 곳**이며,
[`CLAUDE.md`](../../CLAUDE.md)는 요약/인덱스, [`docs/README.md`](../README.md)는 전체 문서 목차다.
규칙을 바꿀 때의 동기화 체인은 [`doc-sync.md`](../doc-sync.md)를 따른다.

## 목차

| 문서 | 다루는 것 | 대표 규칙 |
| --- | --- | --- |
| [`general.md`](general.md) | 공통 코딩·커밋·비밀정보 | Conventional Commits · pre-commit · 비밀정보 취급 |
| [`python.md`](python.md) | Python 스타일 | ruff(4칸·88자) · `scripts/`는 **절차형**(단일 `main`) · PEP 723 |
| [`git.md`](git.md) | git 워크플로 | 브랜치 전략 · **논리적 커밋 단위** · 커밋 대상/금지 · 병렬 세션 worktree |
| [`dagster.md`](dagster.md) | Dagster 정의 | **함수+데코레이터**(클래스 지양) · 에셋 명시 분리 · 머티리얼라이즈 메타데이터 |
| [`dbt.md`](dbt.md) | dbt 모델 | `source()` 매핑 · 메달리온은 kind/tag로 · `fqn:` 셀렉터 |
| [`docker.md`](docker.md) | Compose·Dockerfile | YAML 앵커 · `latest` 금지 · healthcheck + `depends_on` · `profiles` |
| [`k8s.md`](k8s.md) | Kubernetes(이행) | kind on Podman · requests/probe · 로컬 레지스트리 |
| [`terraform.md`](terraform.md) | IaC(도입) | 스택 단위 · 버전 고정 + lock 커밋 · `terraform fmt`(2-space 예외) |
| [`timezone.md`](timezone.md) | 타임존 | **저장 UTC · 표시/스케줄 KST** · tz-aware 강제(ruff `DTZ`) |
| [`agents.md`](agents.md) | 에이전트 오케스트레이션·기록관 | 3계층 · 승인 게이트 · **에스컬레이션** · **security 최종 컨펌** · **archivist 전담 기록** · 권한 게이트 · 정합성 가드 hook |

## 읽는 순서

1. 처음이면 [`general.md`](general.md) → 작업할 영역 문서 1개.
2. **AI 세션으로 작업한다면** [`agents.md`](agents.md)를 먼저 읽는다 — 계층·게이트·기록 의무가 거기 있다.
3. 규칙을 **바꾸려면** [`doc-sync.md`](../doc-sync.md)의 동기화 체인을 먼저 확인한다.

## 원칙

- **정본은 한 곳.** 다른 문서는 요약하고 이 디렉터리를 링크한다.
- **도구로 강제 가능한 규칙의 정본은 도구 설정 파일**이다(`pyproject.toml`의 `[tool.ruff.*]` 등).
  문서는 그 설정의 **의도**를 설명할 뿐 값을 중복 정의하지 않는다.
- **코드·설정과 문서가 어긋나면 코드/설정이 사실**이다. 문서를 코드에 맞춘다(반대 아님).
