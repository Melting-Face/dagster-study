#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""`analyst` 워커 경로 경계 가드 — 에이전트 스코프 PreToolUse hook.

왜 이 스크립트인가:
    규약상 `analyst`의 쓰기는 **`notebooks/**`·`docs/analyses/**` 한정**이다
    (파이프라인 정의의 단일 소유자는 `data-engineer`). 그런데 이 경계를
    `permissions` 규칙으로는 걸 수 없다 — `permissions`는 **세션 전역**이라
    특정 `subagent_type`에만 범위를 못 주고, `Edit(defs/**)`를 `deny`에 넣으면
    `data-engineer`까지 함께 막힌다.

    반면 **에이전트 정의(`.claude/agents/analyst.md`) 안에 선언한 hook은
    그 subagent에만 걸린다.** 그래서 워커별 경로 강제의 유일한 수단이다
    (2026-08-19 — 그전까지 규약은 이를 "불가능"으로 적고 있었다).

    판정은 두 갈래다:
      - 저장소 **안**의 허용 밖 경로 → `deny`(차단). 규약이 명확하므로 사람에게
        묻지 않고 막는다. 필요하면 `data-engineer`에 재배정하라는 뜻이다.
      - 저장소 **밖** 경로(스크래치패드 등) → `ask`(사용자 확인). 정당한
        임시 파일도 있고, 홈 설정 파일 쓰기도 여기로 들어오므로 사람이 판단한다.

    한계(정직하게): `analyst`에는 `Bash`가 있어 `sed`·리다이렉트 경유 쓰기는
    이 hook에 걸리지 않는다. 그 층은 `protected_paths_guard.py`(보호 경로)와
    경계 지시문이 맡는다. **완전한 봉쇄가 아니라 도구 경로의 확정적 차단**이다.

사용: `.claude/agents/analyst.md` 프론트매터의
    `hooks.PreToolUse[matcher: "Edit|Write|NotebookEdit"]`에서 호출한다.
"""

import json
import os
import sys
from pathlib import Path

# 규약상 `analyst`가 쓸 수 있는 유일한 경로. 정본은 docs/conventions/agents.md.
# 🔴 끝의 `/`는 필수다 — 없으면 `docs/analyses_fake/`가 통과한다(실측으로 잡은 버그).
ALLOWED_PREFIXES = ("notebooks/", "docs/analyses/")

# PreToolUse 입력에서 대상 경로가 담기는 키 — 도구마다 이름이 다르다.
PATH_KEYS = ("file_path", "notebook_path", "path")


def main() -> None:
    """`analyst`의 파일 쓰기가 허용 경로 밖이면 차단하거나 확인으로 올린다."""
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

    # 저장소 밖 — 스크래치패드일 수도, 홈 설정일 수도 있다. 사람이 판단한다.
    # 🔴 값은 `ask`다 — 유효 enum은 allow·deny·ask·defer뿐이고, 벗어나면 출력 전체가
    #    검증 실패해 **결정이 사라진 채 통과**한다(fail-open). 2026-08-19 실측.
    if not target.is_relative_to(project_dir):
        decision = "ask"
        reason = (
            f"`analyst`가 저장소 밖 경로에 쓰려 한다: {target}. "
            "규약상 `analyst`의 쓰기는 `notebooks/**`·`docs/analyses/**` 한정이다. "
            "임시 파일이면 승인하고, 아니면 거부하라."
        )
    else:
        relative = target.relative_to(project_dir).as_posix()
        if relative.startswith(ALLOWED_PREFIXES):
            sys.exit(0)  # 허용 경로 — 통과
        decision = "deny"
        reason = (
            f"`analyst`는 `{relative}`를 쓸 수 없다. "
            "쓰기 범위는 `notebooks/**`·`docs/analyses/**` 뿐이다 — "
            "정의 파일(`defs/`·`models/`)의 소유자는 `data-engineer`이고, "
            "gold 모델은 **제안만** 한다(docs/conventions/agents.md §권한 매트릭스). "
            "필요하면 변경안을 반환해 `data-engineer`에 재배정하라."
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
