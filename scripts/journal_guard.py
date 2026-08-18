#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""저널 정합성 가드 — Claude Code hook 진입점(SessionStart·PreToolUse·Stop).

왜 이 스크립트인가:
    저널 파일명 `NN-<mission>.md`의 NN은 "그날 착수 순번"인데, 각 세션이 저마다
    `ls`로 번호를 세어 잡는다. 2026-08-17 23:0x에 병렬 세션 둘이 서로를 모른 채
    같은 `11`을 점유해 넘버링이 깨졌다(→ 11·12번으로 정정). 규약 문서로는 이
    경합을 막을 수 없다 — 문서는 각 세션의 컨텍스트 안에만 있고, 파일시스템은
    하나이기 때문이다. 그래서 번호 발급·중복 차단을 파일시스템 기준으로 옮긴다.

    서브커맨드는 hook 이벤트와 1:1 대응한다:
      session-start : 다음 NN·미완 미션을 stdout으로 컨텍스트 주입(exit 0)
      pre-write     : 볼트 저널 신규 생성 시 NN 중복·파일명 규칙 위반을 차단
      stop          : 저장소 변경이 있는데 오늘자 저널이 없으면 사용자에게 경고

    실패해도 작업을 막지 않는다(fail-open). 볼트가 없는 환경(다른 머신·CI)에서는
    조용히 통과한다 — 가드가 개인 환경 의존성을 세션의 전제조건으로 만들면 안 된다.

사용: Claude Code `settings.json`의 hooks에서 호출한다.
    uv run --script scripts/journal_guard.py <session-start|pre-write|stop>
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NoReturn

# 저장은 UTC·표시는 KST 정책에 따라 저널 날짜·시각은 KST로 판정한다.
KST = timezone(timedelta(hours=9))

# 저널 파일명·하루 폴더명 규약 (docs/conventions/agents.md 정본)
JOURNAL_NAME_RE = re.compile(r"^(\d{2})-([a-z0-9][a-z0-9-]*)\.md$")
DAY_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# `_MOC.md`·`_TEMPLATE.md`처럼 밑줄로 시작하는 볼트 관리 파일은 넘버링 대상이 아니다.
EXEMPT_PREFIX = "_"

# 미션이 아직 열려 있다고 보는 status 값
OPEN_STATUSES = ("planned", "in-progress", "blocked")

# session-start가 훑는 과거 폴더 수 (열린 미션 상기용 — 전체 스캔은 과하다)
RECENT_DAYS = 7


def resolve_journal_root() -> Path | None:
    """볼트의 `agents/` 경로. 볼트 미설정·부재면 None(가드 비활성)."""
    vault = os.environ.get("OBSIDIAN_VAULT") or "~/obsidian"
    root = Path(vault).expanduser() / "agents"
    return root if root.is_dir() else None


def scan_numbers(day_dir: Path) -> list[tuple[int, str]]:
    """하루 폴더의 `(NN, 파일명)` 목록. 규약 위반 파일명은 집계에서 제외한다."""
    found = []
    if not day_dir.is_dir():
        return found
    for path in sorted(day_dir.glob("*.md")):
        matched = JOURNAL_NAME_RE.match(path.name)
        if matched:
            found.append((int(matched.group(1)), path.name))
    return found


def read_frontmatter(path: Path) -> dict[str, str]:
    """저널 frontmatter를 dict로 파싱. 값의 `#` 주석과 따옴표는 떼어낸다."""
    data: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return data
    if not lines or lines[0].strip() != "---":
        return data
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line or line.startswith((" ", "\t", "#")):
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.split("#")[0].strip().strip("\"'")
    return data


def deny(reason: str) -> NoReturn:
    """PreToolUse 차단 응답. 공식 스펙상 강제 정책은 exit 0 + JSON이 권장 형태다."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


def main() -> None:
    """서브커맨드를 hook 이벤트로 분기해 실행한다."""
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    root = resolve_journal_root()
    if root is None:
        sys.exit(0)  # 볼트 없는 환경 — 조용히 통과

    today = datetime.now(tz=KST).strftime("%Y-%m-%d")
    today_dir = root / today

    # ── session-start: 다음 번호와 미완 미션을 컨텍스트로 주입 ──────────────────
    # 세션이 시작하자마자 번호를 알면 `ls`로 세는 경합 자체가 사라진다.
    if command == "session-start":
        numbers = scan_numbers(today_dir)
        next_nn = f"{(max(n for n, _ in numbers) + 1) if numbers else 1:02d}"

        open_missions = []
        day_dirs = sorted(root.glob("????-??-??"), reverse=True)[:RECENT_DAYS]
        for day_dir in day_dirs:
            if not DAY_DIR_RE.match(day_dir.name):
                continue
            for _, name in scan_numbers(day_dir):
                status = read_frontmatter(day_dir / name).get("status", "")
                if status in OPEN_STATUSES:
                    open_missions.append(f"{day_dir.name}/{name[:-3]} ({status})")

        print(f"[저널 가드] 볼트 {root}")
        print(
            f"- 오늘({today}) 다음 미션 번호: **{next_nn}** → "
            f"`{today_dir}/{next_nn}-<mission-slug>.md`"
        )
        if numbers:
            existing_names = ", ".join(name[:-3] for _, name in numbers)
            print(f"- 오늘 기존 저널: {existing_names}")
        else:
            print(
                "- 오늘 저널 없음 — 미션 판단(파일 수정·위임·결정·비가역 작업) 시 "
                "위 경로로 개시할 것"
            )
        if open_missions:
            print(f"- 열린 미션(최근 {RECENT_DAYS}일): {' / '.join(open_missions)}")
        sys.exit(0)

    # ── pre-write: 저널 신규 생성의 넘버링·파일명 규약 강제 ────────────────────
    if command == "pre-write":
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            sys.exit(0)

        raw_path = (payload.get("tool_input") or {}).get("file_path") or ""
        if not raw_path:
            sys.exit(0)
        target = Path(raw_path)

        try:
            relative = target.resolve().relative_to(root.resolve())
        except ValueError:
            sys.exit(0)  # 볼트 저널 밖 — 가드 대상 아님

        if target.exists():
            sys.exit(0)  # 기존 저널 갱신은 넘버링과 무관
        if target.name.startswith(EXEMPT_PREFIX):
            sys.exit(0)  # `_MOC`·`_TEMPLATE` 등 볼트 관리 파일
        if len(relative.parts) != 2:
            deny(
                "저널은 `agents/<YYYY-MM-DD>/<NN>-<mission-slug>.md` 2단 구조여야 "
                f"한다. 받은 경로: {relative}"
            )

        day_name = relative.parts[0]
        if not DAY_DIR_RE.match(day_name):
            deny(f"날짜 폴더명이 `YYYY-MM-DD`가 아니다: `{day_name}`")

        matched = JOURNAL_NAME_RE.match(target.name)
        if not matched:
            deny(
                "파일명이 규약 `<NN>-<mission-slug>.md`(NN=2자리, slug=소문자·숫자"
                f"·하이픈)와 어긋난다: `{target.name}`"
            )

        requested = int(matched.group(1))
        taken = dict(scan_numbers(root / day_name))
        expected = (max(taken) + 1) if taken else 1

        if requested in taken:
            deny(
                f"NN `{matched.group(1)}`은(는) 이미 `{taken[requested]}`가 점유했다. "
                f"병렬 세션 경합일 수 있으니 **{expected:02d}**로 생성하라 "
                "(NN=그날 착수 순번, 판정 기준은 본문 상호작용 로그의 첫 이벤트 시각)."
            )
        if requested != expected:
            occupied = ", ".join(f"{n:02d}" for n in sorted(taken)) or "없음"
            deny(
                f"NN이 연속되지 않는다. 다음 번호는 **{expected:02d}**인데 "
                f"`{matched.group(1)}`을 요청했다. (현 점유: {occupied})"
            )
        sys.exit(0)

    # ── stop: 저장소를 건드렸는데 오늘자 저널이 없으면 경고 ────────────────────
    # exit 2는 "정지를 막고 대화를 계속"이라 경고 용도로 부적합하다 → systemMessage.
    if command == "stop":
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            payload = {}
        cwd = payload.get("cwd") or os.getcwd()

        git_bin = shutil.which("git")
        if git_bin is None:
            sys.exit(0)

        probe = subprocess.run(  # noqa: S603
            [git_bin, "-C", cwd, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if probe.returncode != 0:
            sys.exit(0)  # git 저장소가 아님

        commits = subprocess.run(  # noqa: S603
            [git_bin, "-C", cwd, "log", "--since=midnight", "--oneline"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        touched = bool(probe.stdout.strip()) or bool(commits.stdout.strip())
        if not touched:
            sys.exit(0)

        numbers = scan_numbers(today_dir)
        if not numbers:
            message = (
                f"⚠️ 저널 미개설 — 오늘 저장소 변경이 있는데 `{today_dir}`에 "
                "미션 저널이 없습니다. `/journal`로 보정하세요."
            )
        else:
            stale = [
                name[:-3]
                for _, name in numbers
                if not read_frontmatter(today_dir / name)
                .get("updated", "")
                .startswith(today)
            ]
            if not stale:
                sys.exit(0)
            message = (
                f"⚠️ 저널 `updated` 미갱신 — {', '.join(stale)} "
                "(규약 ④: 사용자 최종 보고 직전 status·updated 갱신)"
            )
        print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        sys.exit(0)

    print(f"알 수 없는 서브커맨드: {command!r}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
