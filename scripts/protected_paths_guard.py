#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""보호 경로 쓰기 가드 — `Bash` 우회를 막는 PreToolUse hook.

왜 이 스크립트인가:
    `permissions`의 `ask` 규칙은 **도구별**이다. `Edit(.claude/settings.json)`·
    `Write(.env)`를 걸어도 `Bash(python3 - <<'EOF' … write_text …)`나 `sed -i`,
    `>` 리다이렉트로 같은 파일을 쓰면 규칙에 걸리지 않는다(2026-08-18 실측 —
    권한 게이트를 보강하는 작업 자체가 그 경로로 이뤄졌다).

    그래서 `Bash` 명령 문자열을 보고, **보호 경로 + 쓰기 동작**이 함께 나타나면
    사용자에게 확인을 올린다(`escalate`). 차단이 아니라 확인이다 — 정당한 편집도
    많고, 판단은 사람이 해야 한다.

    보호 경로는 **`.claude/settings.json`의 `ask` 규칙에서 자동 추출**한다.
    목록을 두 곳에 두면 반드시 어긋나므로 단일 출처를 유지한다.

    한계(정직하게): 문자열 휴리스틱이라 **완전하지 않다**. 변수 치환·인코딩·별칭으로
    얼마든 우회된다. 목표는 봉쇄가 아니라 **실수와 무심코를 잡는 것**이다.

사용: `PreToolUse`(matcher `Bash`) hook에서 호출한다.
    scripts/protected_paths_guard.py
"""

import json
import re
import sys
from pathlib import Path

# `ask` 규칙에서 경로를 뽑을 도구들 — 파일을 직접 쓰는 도구만 대상으로 한다.
FILE_TOOL_RE = re.compile(r"^(?:Edit|Write|NotebookEdit)\((.+)\)$")

# 쓰기로 간주하는 신호. 읽기 전용 명령(cat·grep·json.load)은 걸리지 않는다.
WRITE_SIGNALS = (
    ">",
    ">>",
    "tee",
    "sed -i",
    "perl -i",
    "cp ",
    "mv ",
    "rm ",
    "truncate",
    "dd ",
    "write_text",
    "writelines",
    "json.dump",
    "yaml.dump",
    "open(",
    "shutil.copy",
    "shutil.move",
    "unlink",
    "Path.write",
)

# 글롭 조각을 정규식으로 옮길 때 쓰는 치환 (`**/*.tfstate*` 같은 규칙 대응)
GLOB_TO_RE = ((".", r"\."), ("**", "\x00"), ("*", "[^/]*"), ("\x00", ".*"), ("?", "."))


def load_protected_patterns() -> list[tuple[str, re.Pattern[str]]]:
    """`.claude/settings.json`의 `ask` 규칙에서 보호 경로 패턴을 뽑는다."""
    settings = Path(".claude/settings.json")
    if not settings.is_file():
        return []
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    patterns = []
    for rule in data.get("permissions", {}).get("ask", []):
        matched = FILE_TOOL_RE.match(rule)
        if not matched:
            continue
        raw = matched.group(1).strip()
        converted = raw
        for src, dst in GLOB_TO_RE:
            converted = converted.replace(src, dst)
        patterns.append((raw, re.compile(converted)))
    return patterns


def main() -> None:
    """Bash 명령이 보호 경로를 쓰려 하면 사용자 확인으로 올린다."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        sys.exit(0)

    if not any(signal in command for signal in WRITE_SIGNALS):
        sys.exit(0)  # 읽기 전용으로 보이는 명령 — 통과

    patterns = load_protected_patterns()
    hits = []
    for raw, compiled in patterns:
        # 명령 문자열 안에 등장하는 경로 후보를 패턴과 대조한다.
        for token in re.findall(r"[\w./*@~-]{3,}", command):
            if compiled.fullmatch(token.lstrip("./")) or compiled.fullmatch(token):
                hits.append(raw)
                break
    if not hits:
        sys.exit(0)

    targets = ", ".join(sorted(set(hits)))
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "escalate",
                    "permissionDecisionReason": (
                        f"보호 경로에 쓰기 신호가 감지됐다: {targets}. "
                        "`permissions`의 `ask`는 도구별이라 `Bash` 경로로는 "
                        "걸리지 않는다 — 이 확인이 그 빈틈을 메운다. "
                        "의도한 변경이면 승인하라."
                    ),
                },
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
