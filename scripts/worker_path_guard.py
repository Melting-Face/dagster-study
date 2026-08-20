#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
r"""워커 경로 경계 가드 — 에이전트 스코프 PreToolUse hook.

왜 이 스크립트인가:
    각 워커의 쓰기 범위는 규약으로 정해져 있으나(`docs/conventions/agents.md`
    §권한 매트릭스), 그 경계를 `permissions`로는 걸 수 없다 — `permissions`는
    **세션 전역**이라 특정 `subagent_type`에만 범위를 못 주고, `Edit(terraform/**)`를
    `deny`에 넣으면 `devops-engineer`까지 함께 막힌다.

    반면 **에이전트 정의(`.claude/agents/<worker>.md`) 안에 선언한 hook은
    그 subagent에만 걸린다.** 그래서 워커별 경로 강제의 유일한 수단이다.

    워커마다 스크립트를 복제하지 않고 **대상 워커를 인자로 받는다**(Rule of Three) —
    경계 표가 한 곳에 모여 있어야 규약 문서와 대조하기 쉽다.

배선 (각 워커의 프론트매터):
    hooks:
      PreToolUse:
        - matcher: "Edit|Write|NotebookEdit"
          hooks:
            - type: command
              command: "$CLAUDE_PROJECT_DIR/scripts/worker_path_guard.py <worker>"

    🔴 `command`의 인용 규칙은 `.claude/settings.json`과 **다르다.**
    `"\\"$CLAUDE_PROJECT_DIR\\"/scripts/…"` 처럼 안쪽 따옴표를 이스케이프하면
    프론트매터(YAML)에서는 벗겨지지 않아 경로가 깨지고, **에러 없이 그냥 통과**한다
    (2026-08-19 실측 — "막았다고 믿는데 안 막힌" 상태가 된다).
    배선을 바꾸면 반드시 §실발동 확인을 다시 돌린다.

한계(정직하게):
    워커들에게는 `Bash`가 있어 `sed`·리다이렉트 경유 쓰기는 이 matcher 밖이다.
    그 층은 `protected_paths_guard.py`(보호 경로)와 경계 지시문이 맡는다.
    **완전한 봉쇄가 아니라 도구 경로의 확정적 차단**이다.
"""

import json
import os
import sys
from pathlib import Path

# 워커별 저장소 **안** 경계. 정본은 docs/conventions/agents.md §권한 매트릭스.
#   allow — 여기 나열된 접두어만 쓸 수 있다(그 외 전부 거부). 좁은 범위의 워커용.
#   deny  — 여기 나열된 접두어만 막는다(그 외 허용). 넓은 범위의 구현 워커용.
# 🔴 접두어 끝의 `/`는 필수다 — 없으면 `docs/analyses_fake/`가 통과한다(실측 버그).
BOUNDARIES = {
    # 분석가 — 노트북·리포트만. 정의 파일 소유자는 data-engineer다.
    "analyst": {"allow": ("notebooks/", "docs/analyses/")},
    # 데이터 엔지니어 — 인프라 선언은 devops-engineer 소관.
    "data-engineer": {
        "deny": ("terraform/", "k8s/", "compose.yml", ".env", ".claude/"),
    },
    # 데브옵스 엔지니어 — 파이프라인 정의·분석 산출물은 남의 소관.
    "devops-engineer": {
        "deny": (
            "dagster_project/",
            "dbt/",
            "notebooks/",
            "docs/analyses/",
            ".env",
            ".claude/",
        ),
    },
    # 기록관 — 저널은 저장소 **밖** 볼트에 쓴다. 저장소 안에는 쓸 것이 없다.
    "archivist": {"allow": ()},
    # 리서처 — 읽기 전용. `disallowedTools`가 1차 방어이고 이건 2차(심층 방어)다.
    # 둘 다 두는 이유: `disallowedTools`의 실효는 워커마다 실측해야 확정되는데
    # (§권한 매트릭스 — 선언한 tools가 전부 실재하지는 않는다), 이 워커는 유일하게
    # **외부 네트워크에 접촉**하므로 가져온 내용이 파일로 착지하는 경로를 남기지 않는다.
    "researcher": {"allow": ()},
    # 테크라이터 — 외부 공개 산출물만. 내부 결론(`docs/analyses/`)은 analyst 소관이고
    # 파이프라인 정의는 data-engineer 소관이다. 공개물은 정정 비용이 크므로 좁게 연다.
    "tech-writer": {"allow": ("docs/posts/",)},
}

# 저장소 **밖**에서 예외로 허용할 절대경로 접두어. 미지정 워커는 사용자 확인(`ask`).
OUTSIDE_ALLOW = {
    "archivist": (os.environ.get("OBSIDIAN_VAULT") or str(Path.home() / "obsidian"),),
}

# PreToolUse 입력에서 대상 경로가 담기는 키 — 도구마다 이름이 다르다.
PATH_KEYS = ("file_path", "notebook_path", "path")


def main() -> None:
    """워커의 파일 쓰기가 경계 밖이면 차단하거나 사용자 확인으로 올린다."""
    worker = sys.argv[1] if len(sys.argv) > 1 else ""
    boundary = BOUNDARIES.get(worker)
    if boundary is None:
        sys.exit(0)  # 경계가 정의되지 않은 워커 — 이 가드의 소관이 아니다

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # 입력을 못 읽으면 통과 — 가드가 작업을 멈추게 하지 않는다

    tool_input = payload.get("tool_input") or {}
    raw_path = next((tool_input[k] for k in PATH_KEYS if tool_input.get(k)), "")
    if not raw_path:
        sys.exit(0)

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        target = project_dir / target
    target = target.resolve()

    if not target.is_relative_to(project_dir):
        # 저장소 밖 — 워커별 예외 목록에 있으면 통과, 아니면 사람이 판단한다.
        allowed = OUTSIDE_ALLOW.get(worker, ())
        roots = (Path(prefix).expanduser().resolve() for prefix in allowed)
        if any(target.is_relative_to(root) for root in roots):
            sys.exit(0)
        # 🔴 값은 `ask`다 — 유효 enum은 allow·deny·ask·defer뿐이고, 벗어나면 출력
        #    전체가 검증 실패해 **결정이 사라진 채 통과**한다(fail-open).
        #    2026-08-19 실측.
        decision = "ask"
        reason = (
            f"`{worker}`가 저장소 밖 경로에 쓰려 한다: {target}. "
            "임시 파일이면 승인하고, 아니면 거부하라."
        )
    else:
        relative = target.relative_to(project_dir).as_posix()
        if "allow" in boundary:
            scope = boundary["allow"]
            permitted = relative.startswith(scope)
            # 라벨을 붙인다 — 없으면 "…쓸 수 없다. docs/posts/."처럼 읽혀
            # 그 경로가 금지인지 허용인지 뒤집혀 읽힌다(2026-08-20 실발동 로그 관측).
            scope_text = (
                f"쓸 수 있는 곳: {' · '.join(scope)}"
                if scope
                else "이 워커는 저장소 안에 쓸 수 있는 경로가 없다"
            )
        else:
            scope = boundary["deny"]
            permitted = not relative.startswith(scope)
            scope_text = f"금지: {' · '.join(scope)}"
        if permitted:
            sys.exit(0)
        decision = "deny"
        reason = (
            f"`{worker}`는 `{relative}`를 쓸 수 없다. {scope_text}. "
            "정본은 docs/conventions/agents.md §권한 매트릭스다 — "
            "필요하면 변경안을 반환해 소관 워커에 재배정하라."
        )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                },
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
