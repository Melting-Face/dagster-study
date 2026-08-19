#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""세션 간 동기화 가드 — 병렬 세션의 중복 작업을 잡는 PreToolUse·PostToolUse hook.

왜 이 스크립트인가:
    `journal_guard.py`가 저널 넘버링에서 증명한 것과 같은 구조의 문제다 —
    **규약은 각 세션의 컨텍스트 안에만 있고, 파일시스템은 하나다.** 세션 A는
    세션 B가 방금 `data-verifier`를 같은 대상으로 돌렸다는 사실을 알 방법이
    없다. 문서로 "중복 호출하지 말라"고 써도 서로를 못 보므로 소용이 없다.

    그래서 세션이 **무엇을 점유했는지**를 파일시스템에 남기고, 다음 세션이
    같은 것을 집으려 할 때 그 기록을 보여준다. 두 축을 본다:

      ① 서브에이전트 중복 — 같은 `subagent_type`을 같은 대상으로 또 돌리는가
      ② 동일 파일 동시편집 — 다른 세션이 붙잡고 있는 파일을 고치려 하는가

    **차단이 아니라 소통이다.** 판정이 휴리스틱이라 오탐이 나올 수 있고,
    정당한 병렬 작업도 많다. 그래서 실행 중인 충돌은 `escalate`(사용자 확인)로
    올리고, 이미 끝난 작업은 결과 요약을 컨텍스트로 흘려 **재호출 대신 재사용**을
    유도한다. 충돌 상대의 **tmux pane·pid**를 함께 주므로(`ListAgents` 행의
    `tmux 0:@0.%5`와 직접 대응), 모델은 상대를 지목해 `SendMessage`로 물어볼 수 있다.

    한계(정직하게): 대상 지문은 프롬프트 문자열 휴리스틱이라 완전하지 않다.
    표현이 크게 다르면 못 잡고(미탐), 우연히 같은 토큰을 쓰면 잘못 잡는다(오탐).
    목표는 봉쇄가 아니라 **"서로를 모르는 상태"를 없애는 것**이다.

    레지스트리는 `.claude/.claims/`(gitignore)에 둔다 — 볼트는 저널 전용이라
    런타임 상태로 오염시키지 않고, 전역 `~/.claude/`보다 프로젝트 스코프가 맞다.

사용: Claude Code `settings.json`의 hooks에서 호출한다.
    scripts/session_sync_guard.py <agent-pre|agent-post|file-pre|file-post|session-end>
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 저장은 UTC·표시는 KST 정책에 따라 기록 시각은 KST로 남긴다.
KST = timezone(timedelta(hours=9))

# 레지스트리 루트 (프로젝트 스코프, gitignore 대상).
# hook의 cwd는 보장되지 않으므로 `CLAUDE_PROJECT_DIR`를 우선한다 — 상대 경로로
# 두면 세션마다 다른 디렉터리를 봐서 "하나의 파일시스템"이라는 전제가 깨진다.
CLAIM_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".") / ".claude/.claims"

# 실행 중 claim을 살아있다고 보는 시간. 초과분은 죽은 세션의 잔해로 간주해 쓸어낸다.
RUNNING_TTL = timedelta(minutes=30)

# 완료 claim을 재사용 가능하다고 보는 시간. 이후엔 데이터가 변했을 수 있다.
DONE_TTL = timedelta(hours=6)

# 파일 리스가 유효한 시간. 편집할 때마다 갱신되므로 "최근 손댄 흔적"에 가깝다.
LEASE_TTL = timedelta(minutes=20)

# 대상 지문이 이 비율 이상 겹치면 같은 작업으로 본다 (Jaccard).
OVERLAP_THRESHOLD = 0.5

# 프롬프트에서 지문을 뽑을 때 훑는 최대 길이 — 뒤쪽은 대개 형식 지시문이다.
PROMPT_SCAN_LIMIT = 4000

# 지문 하나당 최대 토큰 수 — 너무 많으면 겹침 비율이 희석된다.
MAX_TARGETS = 12

# 결과 요약으로 남길 최대 길이 — 재사용 판단에 필요한 만큼만.
SUMMARY_LIMIT = 600

# 구조적 지문 추출 패턴 (경로·백틱·확장자 파일명 순)
BACKTICK_RE = re.compile(r"`([^`\n]{2,80})`")
PATH_RE = re.compile(r"[A-Za-z0-9_@.-]+/[A-Za-z0-9_./@-]+")
FILENAME_RE = re.compile(
    r"\b[A-Za-z0-9_.-]+\.(?:py|sql|ya?ml|md|json|tf|sh|toml|ini|cfg)\b"
)
WORD_RE = re.compile(r"[a-z][a-z0-9_]{3,}")

# 구조적 지문이 없을 때만 쓰는 내용어 추출의 불용어 — 어느 프롬프트에나 나온다.
STOPWORDS = frozenset(
    (
        "that",
        "this",
        "with",
        "from",
        "into",
        "have",
        "been",
        "will",
        "your",
        "when",
        "what",
        "which",
        "they",
        "them",
        "then",
        "else",
        "must",
        "should",
        "would",
        "could",
        "there",
        "where",
        "than",
        "only",
        "also",
        "same",
        "each",
        "other",
        "more",
        "most",
        "such",
        "very",
        "much",
        "some",
        "many",
        "both",
        "make",
        "made",
        "used",
        "using",
        "use",
        "need",
        "needs",
        "project",
        "file",
        "files",
        "code",
        "check",
        "checks",
        "test",
        "tests",
        "result",
        "results",
        "report",
        "return",
        "returns",
        "please",
        "after",
        "before",
        "again",
        "read",
        "write",
        "edit",
        "find",
        "search",
        "dagster",
        "dbt",
        "asset",
        "assets",
        "model",
        "models",
        "프로젝트",
        "파일",
        "확인",
        "결과",
        "작업",
        "대상",
    )
)


def now() -> datetime:
    """KST 기준 현재 시각."""
    return datetime.now(tz=KST)


def parse_time(raw: str) -> datetime | None:
    """ISO 문자열을 datetime으로. 깨진 값은 None(만료 처리)."""
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def normalize(token: str) -> str:
    """지문 토큰 정규화 — 따옴표·구두점·경로 접두를 떼고 소문자화한다."""
    cleaned = token.strip().strip("`\"'()[]{}<>,.;:").lstrip("./")
    return cleaned.lower()


def extract_targets(prompt: str) -> list[str]:
    """프롬프트에서 '무엇에 대한 작업인가'를 뽑는다.

    구조적 신호(백틱·경로·확장자 파일명)가 있으면 그것만 쓴다 — 정확하기 때문이다.
    하나도 없을 때만 내용어로 물러선다(불용어 제거 후 빈도순).
    """
    text = prompt[:PROMPT_SCAN_LIMIT]

    structured: set[str] = set()
    for pattern in (BACKTICK_RE, PATH_RE, FILENAME_RE):
        for hit in pattern.findall(text):
            token = normalize(hit)
            if len(token) >= 3:
                structured.add(token)
    if structured:
        return sorted(structured)[:MAX_TARGETS]

    counts: dict[str, int] = {}
    for word in WORD_RE.findall(text.lower()):
        if word not in STOPWORDS:
            counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts, key=lambda w: (-counts[w], w))
    return sorted(ranked[:MAX_TARGETS])


def overlap(left: list[str], right: list[str]) -> float:
    """두 지문의 Jaccard 유사도. 한쪽이 비면 0(비교 불가는 겹침 아님)."""
    a, b = set(left), set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def session_ref(session_id: str) -> str:
    """세션 식별자를 6자리로 줄인다 — claim 소유권 비교용 내부 키.

    ⚠️ 이 값은 `ListAgents`가 표시하는 `[7f1735]` ref와 **다르다**(2026-08-19 실측:
    피어 세션 `6ebf1212`의 ListAgents ref는 `7f1735`였다). ref는 session_id에서
    유도되지 않으므로, 사람에게 상대를 지목할 때는 이 값이 아니라 `identity()`가
    담는 **tmux pane·pid**를 쓴다 — 그 둘은 `ListAgents` 행과 직접 대응한다.
    """
    return (session_id or "unknown").replace("-", "")[:6]


def identity(payload: dict) -> dict[str, str]:
    """내 세션의 식별자 묶음.

    `ListAgents` 한 행은 `<name> [<ref>] · … · tmux 0:@0.%5` 형태다. `ref`는 hook이
    알 수 없지만 **tmux pane은 `$TMUX_PANE`으로 그대로 읽힌다**. pid는 피어 메시징
    소켓(`/tmp/cc-socks/<pid>.sock`)의 이름이기도 해서 두 번째 단서가 된다.
    그래서 이 셋을 함께 남기면 사람이 상대 세션을 확실히 지목할 수 있다.
    """
    session_id = payload.get("session_id") or os.environ.get(
        "CLAUDE_CODE_SESSION_ID", ""
    )
    return {
        "session_ref": session_ref(session_id),
        "session_id": session_id,
        "tmux_pane": os.environ.get("TMUX_PANE", ""),
        "pid": os.environ.get("CLAUDE_PID", ""),
        "socket": os.environ.get("CLAUDE_CODE_MESSAGING_SOCKET", ""),
    }


def describe_peer(record: dict) -> str:
    """충돌 상대를 사람이 `ListAgents`에서 찾을 수 있는 형태로 묘사한다.

    pane을 앞에 두는 이유는 `ListAgents`가 `tmux` 컬럼으로 그대로 보여주기 때문이고,
    `session_id`를 함께 붙이는 이유는 **pane 번호가 재사용되기 때문**이다 —
    pane이 죽고 `respawn-pane`으로 되살아나면 다른 세션이 같은 `%N`을 물려받는다.
    그래서 pane은 **찾는 열쇠**, `session_id`는 **맞는지 확인하는 자물쇠**로 쓴다.
    """
    parts = []
    if record.get("tmux_pane"):
        parts.append(f"tmux pane `{record['tmux_pane']}`")
    if record.get("pid"):
        parts.append(f"pid `{record['pid']}`")
    if record.get("session_id"):
        parts.append(f"session `{record['session_id']}`")
    return " · ".join(parts) or "식별자 불명"


# pane 번호 재사용 때문에 붙이는 확인 절차. 두 경고가 공유한다.
PANE_CAVEAT = (
    "찾을 때는 `ListAgents`의 `tmux` 컬럼이 위 pane과 같은 행을 보라. "
    "다만 **pane 번호는 재사용된다**(pane이 죽고 되살아나면 다른 세션이 물려받는다) — "
    "위 session 값과 다르면 **다른 세션**이니, 확신이 서지 않으면 `SendMessage`로 "
    "먼저 session_id를 확인하고 본론을 물어라."
)


def read_claim(path: Path) -> dict | None:
    """저장된 claim JSON 로드. 깨진 파일은 None."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def write_claim(path: Path, record: dict) -> None:
    """원자적 쓰기 — 다른 세션이 반쯤 쓰인 파일을 읽지 않게 replace로 교체한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{os.getpid()}.tmp")
    try:
        temp.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temp.replace(path)
    except OSError:
        temp.unlink(missing_ok=True)


def sweep(directory: Path) -> list[tuple[Path, dict]]:
    """만료 claim을 지우고 살아있는 것만 돌려준다. 호출마다 도는 저비용 GC."""
    alive: list[tuple[Path, dict]] = []
    if not directory.is_dir():
        return alive
    current = now()
    for path in sorted(directory.glob("*.json")):
        record = read_claim(path)
        if record is None:
            path.unlink(missing_ok=True)
            continue
        stamp = parse_time(record.get("updated", ""))
        if stamp is None:
            path.unlink(missing_ok=True)
            continue
        ttl = DONE_TTL if record.get("status") == "done" else RUNNING_TTL
        if record.get("kind") == "file":
            ttl = LEASE_TTL
        if current - stamp > ttl:
            path.unlink(missing_ok=True)
            continue
        alive.append((path, record))
    return alive


def emit(payload: dict) -> None:
    """응답 JSON을 stdout으로 내보내고 종료한다(항상 exit 0 — fail-open)."""
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def escalate(event: str, reason: str) -> None:
    """사용자 확인으로 상신. 차단이 아니라 판단을 사람에게 넘기는 것."""
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": "escalate",
                "permissionDecisionReason": reason,
            }
        }
    )


def inform(event: str, message: str) -> None:
    """결정을 바꾸지 않고 정보만 흘린다 — 완료 claim 재사용 유도용."""
    emit(
        {
            "systemMessage": message,
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": message,
            },
        }
    )


def load_payload() -> dict:
    """표준입력 JSON 페이로드. 파싱 실패는 조용히 통과(fail-open)."""
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)


def elapsed_text(stamp: datetime | None) -> str:
    """경과 시간을 사람이 읽는 문구로. 알 수 없으면 '시각 불명'."""
    if stamp is None:
        return "시각 불명"
    minutes = int((now() - stamp).total_seconds() // 60)
    return "방금" if minutes < 1 else f"{minutes}분 전"


def agent_claim_path(subagent_type: str, targets: list[str]) -> Path:
    """서브에이전트 claim 파일 경로 — 타입 + 대상 지문 해시로 결정한다."""
    digest = hashlib.sha1(  # noqa: S324 — 보안용 아님, 경로 식별자다
        "\n".join(targets).encode("utf-8")
    ).hexdigest()[:8]
    safe_type = re.sub(r"[^a-z0-9_-]", "-", subagent_type.lower()) or "agent"
    return CLAIM_ROOT / "agents" / f"{safe_type}-{digest}.json"


def handle_agent_pre(payload: dict) -> None:
    """서브에이전트 호출 직전 — 같은 작업을 다른 세션이 이미 했는지 본다."""
    tool_input = payload.get("tool_input") or {}
    subagent_type = tool_input.get("subagent_type") or "general-purpose"
    prompt = tool_input.get("prompt") or ""
    if not prompt:
        sys.exit(0)

    mine = identity(payload)
    me = mine["session_ref"]
    targets = extract_targets(prompt)
    if not targets:
        sys.exit(0)  # 지문을 못 뽑으면 판정하지 않는다 — 오탐보다 미탐이 낫다

    conflicts = []
    for _, record in sweep(CLAIM_ROOT / "agents"):
        if record.get("subagent_type") != subagent_type:
            continue
        if record.get("session_ref") == me:
            continue  # 자기 세션의 흔적은 충돌이 아니다
        if overlap(targets, record.get("targets", [])) >= OVERLAP_THRESHOLD:
            conflicts.append(record)

    running = [c for c in conflicts if c.get("status") == "running"]
    done = [c for c in conflicts if c.get("status") == "done"]

    if running:
        peer = running[0]
        shared = ", ".join(sorted(set(targets) & set(peer.get("targets", []))))
        escalate(
            "PreToolUse",
            f"⚠️ 중복 서브에이전트 감지 — 다른 세션({describe_peer(peer)})이 "
            f"같은 대상으로 `{subagent_type}`을(를) 실행 중이다"
            f"(시작 {elapsed_text(parse_time(peer.get('updated', '')))}).\n"
            f"  겹친 대상: {shared}\n"
            f"  상대 작업: {peer.get('description') or '(설명 없음)'}\n"
            f"승인 전에 그 세션에게 진행 상황·결과를 물어보라. {PANE_CAVEAT}\n"
            "받은 결과를 쓸 수 있으면 이 호출은 취소하는 편이 옳다.",
        )

    if done:
        peer = done[0]
        shared = ", ".join(sorted(set(targets) & set(peer.get("targets", []))))
        lines = [
            f"📌 다른 세션({describe_peer(peer)})이 "
            f"{elapsed_text(parse_time(peer.get('updated', '')))} 같은 대상으로 "
            f"`{subagent_type}`을(를) 이미 완료했다.",
            f"  겹친 대상: {shared}",
        ]
        if peer.get("summary"):
            lines.append(f"  결과 요약: {peer['summary']}")
        if peer.get("journal"):
            lines.append(f"  저널: {peer['journal']}")
        lines.append(
            "재호출 대신 이 결과를 쓸 수 있는지 먼저 판단하라. "
            "더 필요하면 `SendMessage`로 그 세션에 추가 질의하는 편이 싸다."
        )
        inform("PreToolUse", "\n".join(lines))

    # 충돌 없음 — 내 claim을 남겨 다음 세션이 나를 볼 수 있게 한다.
    write_claim(
        agent_claim_path(subagent_type, targets),
        {
            "kind": "agent",
            "status": "running",
            "subagent_type": subagent_type,
            "targets": targets,
            "description": tool_input.get("description") or "",
            **mine,
            "cwd": payload.get("cwd") or os.getcwd(),
            "started": now().isoformat(timespec="seconds"),
            "updated": now().isoformat(timespec="seconds"),
        },
    )
    sys.exit(0)


def handle_agent_post(payload: dict) -> None:
    """서브에이전트 종료 직후 — claim을 완료로 바꾸고 결과 요약을 남긴다."""
    tool_input = payload.get("tool_input") or {}
    subagent_type = tool_input.get("subagent_type") or "general-purpose"
    prompt = tool_input.get("prompt") or ""
    targets = extract_targets(prompt)
    if not targets:
        sys.exit(0)

    path = agent_claim_path(subagent_type, targets)
    record = read_claim(path)
    if record is None or record.get("session_ref") != identity(payload)["session_ref"]:
        sys.exit(0)  # 내 claim이 아니면 건드리지 않는다

    response = payload.get("tool_response")
    if isinstance(response, dict):
        response = response.get("content") or response.get("result") or ""
    text = " ".join(str(response or "").split())

    record["status"] = "done"
    record["summary"] = text[:SUMMARY_LIMIT]
    record["finished"] = now().isoformat(timespec="seconds")
    record["updated"] = record["finished"]
    write_claim(path, record)
    sys.exit(0)


def lease_target(payload: dict) -> tuple[Path, str] | None:
    """편집 대상 파일의 (리스 경로, 절대경로). 대상이 아니면 None."""
    raw_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not raw_path:
        return None
    try:
        resolved = str(Path(raw_path).resolve())
    except OSError:
        return None
    # 레지스트리 자신은 대상 밖 — 가드가 자기 발등을 찍지 않게 한다.
    if "/.claude/.claims/" in resolved:
        return None
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:12]  # noqa: S324
    return CLAIM_ROOT / "files" / f"{digest}.json", resolved


def handle_file_pre(payload: dict) -> None:
    """파일 편집 직전 — 다른 세션이 최근 같은 파일을 고쳤는지 보고 확인을 올린다."""
    located = lease_target(payload)
    if located is None:
        sys.exit(0)
    lease_path, resolved = located

    sweep(CLAIM_ROOT / "files")
    existing = read_claim(lease_path) if lease_path.exists() else None
    if existing is None:
        sys.exit(0)
    if existing.get("session_ref") == identity(payload)["session_ref"]:
        sys.exit(0)  # 내가 잡은 리스 — 충돌이 아니다

    stamp = parse_time(existing.get("updated", ""))
    if stamp is None or now() - stamp > LEASE_TTL:
        sys.exit(0)

    escalate(
        "PreToolUse",
        f"⚠️ 동일 파일 동시편집 — `{Path(resolved).name}`을(를) 세션 "
        f"다른 세션({describe_peer(existing)})이 {elapsed_text(stamp)} 편집했다.\n"
        f"  경로: {resolved}\n"
        "승인 전에 그 세션에게 **아직 이 파일을 작업 중인지, 어떤 변경을 했는지** "
        f"물어보라. 겹치면 덮어써서 상대 작업이 날아간다.\n{PANE_CAVEAT}",
    )


def handle_file_post(payload: dict) -> None:
    """파일 편집 직후 — 리스를 내 것으로 갱신한다.

    획득을 `PreToolUse`가 아니라 여기서 하는 이유: `PostToolUse`는 **승인·성공한
    편집에서만** 발동한다. 그래서 리스가 "고치려던 사람"이 아니라 **"실제로 고친
    사람"** 을 가리키고, 확인을 승인하고 넘어간 세션이 소유권을 이어받아 같은
    경고가 반복되지 않는다.
    """
    located = lease_target(payload)
    if located is None:
        sys.exit(0)
    lease_path, resolved = located

    write_claim(
        lease_path,
        {
            "kind": "file",
            "path": resolved,
            "tool": payload.get("tool_name") or "",
            **identity(payload),
            "updated": now().isoformat(timespec="seconds"),
        },
    )
    sys.exit(0)


def handle_session_end(payload: dict) -> None:
    """세션 종료 — 내 리스와 실행 중 claim을 걷어낸다(잔해로 남기지 않는다)."""
    me = identity(payload)["session_ref"]
    for directory in (CLAIM_ROOT / "files", CLAIM_ROOT / "agents"):
        for path, record in sweep(directory):
            if record.get("session_ref") != me:
                continue
            if record.get("kind") == "agent" and record.get("status") == "done":
                continue  # 완료 결과는 다음 세션이 재사용하도록 남긴다
            path.unlink(missing_ok=True)
    sys.exit(0)


HANDLERS = {
    "agent-pre": handle_agent_pre,
    "agent-post": handle_agent_post,
    "file-pre": handle_file_pre,
    "file-post": handle_file_post,
    "session-end": handle_session_end,
}


def main() -> None:
    """서브커맨드를 hook 이벤트로 분기해 실행한다."""
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    handler = HANDLERS.get(command)
    if handler is None:
        print(f"알 수 없는 서브커맨드: {command!r}", file=sys.stderr)
        sys.exit(1)
    handler(load_payload())


if __name__ == "__main__":
    main()
