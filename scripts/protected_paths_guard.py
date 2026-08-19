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
    사용자에게 확인을 올린다(`ask`). 차단이 아니라 확인이다 — 정당한 편집도
    많고, 판단은 사람이 해야 한다.

    🔴 `permissionDecision`의 유효 값은 **`allow`·`deny`·`ask`·`defer`뿐**이다
    (CLI 2.1.226 실측: zod `Nr(["allow","deny","ask","defer"])`). 예전에 쓰던
    `escalate`는 스키마에 없어 **훅 출력 전체가 검증 실패**하고, 그 훅의 결정이
    폐기된 채 도구가 그냥 진행한다 — 에러 배너만 한 번 뜨고 **게이트는 fail-open**
    이었다(2026-08-19 실측: `cat .env > /dev/null`이 프롬프트 없이 통과).
    `defer`는 print-mode 전용이라 대화형에서는 무시된다.

    보호 경로는 **`.claude/settings.json`의 `ask` 규칙에서 자동 추출**한다.
    목록을 두 곳에 두면 반드시 어긋나므로 단일 출처를 유지한다.

    한계(정직하게): 문자열 휴리스틱이라 **완전하지 않다**. 변수 치환·인코딩·별칭으로
    얼마든 우회된다. 목표는 봉쇄가 아니라 **실수와 무심코를 잡는 것**이다.

사용: `PreToolUse`(matcher `Bash`) hook에서 호출한다.
    scripts/protected_paths_guard.py
"""

import json
import os
import re
import sys
from pathlib import Path

# `ask` 규칙에서 경로를 뽑을 도구들 — 파일을 직접 쓰는 도구만 대상으로 한다.
FILE_TOOL_RE = re.compile(r"^(?:Edit|Write|NotebookEdit)\((.+)\)$")

# 쓰기로 간주하는 신호. 읽기 전용 명령(cat·grep·json.load)은 걸리지 않는다.
# 🔴 여기 없는 신호는 경로 대조에 **도달조차 못 한다**(아래 조기 통과) — 파일을 만드는
#    모든 경로를 열거해야 한다. 2026-08-19 security 재컨펌에서 `install`·`tar`·`rsync`·
#    `ln`·`git checkout`류가 누락돼 절대경로인데도 통과하는 것이 실측됐다.
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
    # 아카이브 전개·복사·링크 — 파일을 만들지만 리다이렉트가 없다
    "install ",
    "tar ",
    "unzip ",
    "rsync",
    "ln ",
    "touch ",
    "patch ",
    "chmod ",
    # 네트워크에서 직접 파일로 받는 형태 (`curl * -o *` 규칙의 도구층 밖 보완)
    "--output",
    "-O ",
    "wget ",
    # 워킹트리를 덮어쓰는 git 명령
    "git checkout",
    "git restore",
    "git apply",
    "git stash pop",
    "git clean",
)

# 글롭 조각을 정규식으로 옮길 때 쓰는 치환 (`**/*.tfstate*` 같은 규칙 대응)
# 🔴 선두 `**/`는 **선택적 접두어**여야 한다 — 단순히 `**`→`.*`로 두면 뒤따르는 `/`가
#    리터럴로 남아 `.*`가 빈 문자열일 때도 `/`를 요구한다. 그러면 절대경로·`~` 형태는
#    잡히는데 **프로젝트 상대경로(`.claude/skills/x`)는 원리상 안 잡힌다**(실측).
#    같은 이유로 `terraform/**/*.tfstate*`가 `terraform/foo.tfstate`를 놓치고 있었다.
# 치환은 **순서가 의미를 가진다** — `?`→`.`를 먼저 끝내야 아래에서 넣는 `(?:.*/)?`의
#    `?`가 다시 치환되지 않는다.
GLOB_TO_RE = (
    (".", r"\."),
    ("?", "."),
    ("**/", "\x01"),  # 선택적 디렉터리 접두어
    ("**", "\x00"),  # 경로 구분자를 넘는 와일드카드
    ("*", "[^/]*"),  # 한 세그먼트 안의 와일드카드
    ("\x01", "(?:.*/)?"),
    ("\x00", ".*"),
)


def load_protected_patterns() -> list[tuple[str, re.Pattern[str]]] | None:
    """`.claude/settings.json`의 `ask` 규칙에서 보호 경로 패턴을 뽑는다.

    읽지 못하면 `None`을 돌려준다 — 호출부는 이를 **통제 소멸**로 보고
    fail-closed 처리한다. 빈 리스트(`[]`, 규칙이 정말 0개)와 구분해야 한다.
    """
    # 🔴 상대경로로 읽으면 cwd가 프로젝트 루트가 아닐 때 패턴이 0개가 되고
    #    **에러도 없이 전부 통과**한다. 이 저장소는 `git worktree` 병렬 세션을
    #    표준으로 쓰고 서브디렉터리에서 세션을 열 수도 있어 실제 위험이다.
    #    hook 배선은 `$CLAUDE_PROJECT_DIR`로 절대경로를 쓰는데 스크립트 내부만
    #    cwd에 의존하면 기준이 어긋난다(2026-08-19 security 실측).
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    settings = root / ".claude/settings.json"
    if not settings.is_file():
        return None
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

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
    tokens = re.findall(r"[\w./*@~-]{3,}", command)
    # 토큰 하나를 여러 형태로 펼친다. 형태를 빠뜨리면 **그 형태만 조용히 통과**하므로
    # 넓게 잡고, 과차단은 대조군 테스트로 관리한다(§5형태 매트릭스).
    candidates: set[str] = set()
    heads: set[str] = set()
    for token in tokens:
        for base in (token, token.lstrip("./")):
            # 🔴 접미어 전개 — 토큰 정규식이 `$`를 제외해 `$VAR/경로`가 `VAR/경로`로
            #    남는다. 접두어가 붙은 채로는 `.claude/agents/**` 같은 **앵커된 패턴**에
            #    걸리지 않는다(`$CLAUDE_PROJECT_DIR/.claude/agents/x`가 통과했다).
            #    `/` 뒤 조각을 전부 후보로 넣어 접두어 종류에 무관하게 만든다.
            parts = base.split("/")
            for i in range(len(parts)):
                suffix = "/".join(parts[i:])
                if not suffix:
                    continue
                candidates.add(suffix)
                # 🔴 디렉터리형 — `tar -C <디렉터리>`처럼 **대상이 디렉터리 자체**면
                #    `.../skills/**` 패턴의 뒷부분이 비어 매칭에 실패한다. `/`를 붙이면
                #    `.*`가 빈 문자열로 매칭된다.
                candidates.add(suffix + "/")
                heads.add(suffix)

    for raw, compiled in patterns or ():
        if any(compiled.fullmatch(c) for c in candidates):
            hits.append(raw)
            continue
        # 🔴 상위 디렉터리 — 보호 경로의 **부모**에 아카이브를 풀거나 동기화하면
        #    보호 대상이 생성·덮어쓰기된다(`tar -C .claude`). 패턴의 글롭 앞
        #    리터럴 머리와 대조한다.
        literal_head = raw.split("*")[0].rstrip("/")
        if literal_head and any(literal_head.startswith(h + "/") for h in heads):
            hits.append(raw)
    if patterns is None:
        # 🔴 fail-closed — 통제가 죽은 채 조용히 통과하는 것보다 낫다.
        reason = (
            "보호 경로 설정을 읽지 못했다(`.claude/settings.json`) — 이 가드의 통제가 "
            "**소멸한 상태**다. cwd나 `CLAUDE_PROJECT_DIR`를 확인하라. "
            "통제 없이 진행할 의도면 승인하라."
        )
    elif hits:
        targets = ", ".join(sorted(set(hits)))
        reason = (
            f"보호 경로에 쓰기 신호가 감지됐다: {targets}. "
            "`permissions`의 `ask`는 도구별이라 `Bash` 경로로는 "
            "걸리지 않는다 — 이 확인이 그 빈틈을 메운다. "
            "의도한 변경이면 승인하라."
        )
    else:
        sys.exit(0)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                },
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
