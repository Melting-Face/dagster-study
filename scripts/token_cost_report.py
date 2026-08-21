#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Claude Code 세션 트랜스크립트에서 토큰 사용량·비용을 집계한다.

사용법:
    uv run scripts/token_cost_report.py
    uv run scripts/token_cost_report.py --top 15
    uv run scripts/token_cost_report.py --json
    uv run scripts/token_cost_report.py --no-dedupe   # 중복 제거 로직 검증용
    uv run scripts/token_cost_report.py --project=-Users-jin-other

    🔴 `--project`는 **`=`로 붙여 쓴다**. 슬러그가 `-`로 시작해서
       `--project -Users-...`처럼 띄우면 argparse가 값을 옵션으로 오인한다.

왜 이 스크립트인가:
    "토큰 비용이 많이 나간다"는 체감은 있는데 **어느 축에서 나가는지 볼 수단이
    없었다**. 계측 없이 줄이면 줄였다는 착각만 남는다(철학 원칙 7).

    Claude Code는 세션마다 `~/.claude/projects/<슬러그>/`에 JSONL 트랜스크립트를
    남기고, assistant 메시지의 `message.usage`에 **4개 토큰 축**을 기록한다:
    `input_tokens`(캐시 미적용 입력) / `output_tokens` /
    `cache_creation_input_tokens`(캐시 쓰기) / `cache_read_input_tokens`(캐시 읽기).
    이 넷이 단가가 전부 다르므로, 넷을 합쳐 "토큰 몇 개"로 세면 비용을 못 읽는다.

    2026-08-21 실측에서 **캐시 읽기가 전체 토큰의 약 97%**였다. 즉 이 저장소의
    비용은 사실상 `요청 수 곱하기 컨텍스트 크기`이고, 출력 토큰은 부차적이다.

🔴 서브에이전트 로그는 하위 디렉터리에 따로 있다:
    최상위 `*.jsonl`만 집계하면 `isSidechain: true`가 **0건**으로 나와
    "서브에이전트 비용 없음"으로 오독된다. 실제로는 세션 UUID 디렉터리 안에
    파일이 더 있다(2026-08-21 기준 메인 48 / 서브 109). 그래서 여기서는
    `rglob("*.jsonl")`로 **재귀 수집**하고, 경로 깊이로 메인/서브를 가른다.
    출력의 서브에이전트 요청 수가 0이면 그건 "없다"가 아니라 "못 봤다"이다.

🔴 계측 단위:
    "요청 수"는 **고유 `requestId` 수**다 — 메시지 줄 수가 아니다. 같은 응답이
    트랜스크립트에 여러 줄로 반복 기록되므로, 줄을 세면 값이 부풀려진다.
    `--no-dedupe`로 끄면 수치가 커지는지 확인할 수 있다(안 커지면 죽은 코드).

한계(정직하게):
    - 비용은 **API 정가(list price) 환산 추정**이며 실제 청구액이 아니다.
      구독 플랜은 청구 구조가 다르고, 할인 계약이 있으면 더 낮다.
    - 로컬에 남아 있는 트랜스크립트만 집계된다. 정리·삭제된 세션은 빠진다.
    - 단가는 **하드코딩 스냅샷**이다(아래 PRICING 주석의 관측일 참고).
      모델 출시·단가 인하 때 사람이 갱신해야 하며, 갱신되지 않은 단가는
      조용히 틀린 값을 낸다.
    - 컨텍스트 **내역**(CLAUDE.md 몇 토큰 / 도구 정의 몇 토큰)은 트랜스크립트에
      분해돼 있지 않아 이 스크립트로는 알 수 없다. 내역이 필요하면
      Anthropic `messages.count_tokens` API로 별도 측정해야 한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# 단가: USD / 100만 토큰. 출처는 Anthropic 공식 모델·가격 문서
# (https://platform.claude.com/docs/en/pricing) — 2026-06-24 스냅샷 기준.
# 🔴 sonnet-5의 2.00/10.00은 **인트로 단가이고 2026-08-31에 만료**된다.
#    만료 후에는 3.00/15.00으로 바꿔야 한다(날짜 분기를 코드에 넣지 않는다 —
#    분기가 있으면 갱신 필요성이 보이지 않아 오히려 조용히 낡는다).
PRICING = {
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-opus-4-7": {"input": 5.00, "output": 25.00},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    "claude-opus-4-5": {"input": 5.00, "output": 25.00},
    "claude-fable-5": {"input": 10.00, "output": 50.00},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},  # 인트로 단가 ~2026-08-31
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    # 트랜스크립트에는 날짜 접미사가 붙은 ID가 그대로 들어오기도 한다(실측).
    # 접미사를 잘라내는 정규화 대신 키를 병기한다 — 모르는 ID는 `미측정`으로
    # 드러나는 편이 낫고, 정규화는 미래의 다른 ID를 조용히 잘못 매핑할 수 있다.
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
}

# 캐시 단가는 입력 단가의 배수다. 읽기는 0.1배, 쓰기는 TTL에 따라 갈린다
# (5분 1.25배 / 1시간 2배). 트랜스크립트의 `usage.cache_creation`이 TTL별
# 토큰을 분리해 주므로 추정하지 않고 그대로 쓴다.
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER_5M = 1.25
CACHE_WRITE_MULTIPLIER_1H = 2.0

# 모델 ID가 아닌 합성 항목. 실제 API 호출이 아니므로 집계에서 제외한다.
SYNTHETIC_MODELS = {"<synthetic>"}

MILLION = 1_000_000


def main() -> int:
    """트랜스크립트를 집계해 토큰 사용량·비용 리포트를 출력한다.

    Returns:
        종료코드. 0=정상, 2=판정 불가(트랜스크립트 없음).
    """
    parser = argparse.ArgumentParser(
        description="Claude Code 세션 트랜스크립트의 토큰 사용량·비용을 집계한다.",
    )
    parser.add_argument(
        "--project",
        default=None,
        help=(
            "프로젝트 슬러그. 생략 시 cwd에서 유도. 슬러그가 `-`로 시작하므로"
            " 반드시 `--project=-Users-jin-foo` 형태로 붙여 쓴다"
            " (띄어 쓰면 argparse가 옵션으로 오인한다)."
        ),
    )
    parser.add_argument(
        "--top", type=int, default=10, help="세션 표에 표시할 행 수 (기본 10)"
    )
    parser.add_argument(
        "--json", action="store_true", help="사람용 표 대신 JSON으로 출력한다"
    )
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        help="requestId 중복 제거를 끈다(검증용 — 켰을 때보다 수치가 커져야 정상).",
    )
    args = parser.parse_args()

    # 1. 트랜스크립트 디렉터리를 정한다.
    #    Claude Code는 프로젝트 절대경로의 `/`를 `-`로 바꿔 슬러그로 쓴다.
    slug = args.project or str(Path.cwd()).replace("/", "-")
    root = Path.home() / ".claude" / "projects" / slug
    if not root.is_dir():
        print(f"[오류] 트랜스크립트 디렉터리가 없다: {root}", file=sys.stderr)
        print(
            "       --project 로 슬러그를 직접 지정하거나, 프로젝트 루트에서 실행한다.",
            file=sys.stderr,
        )
        return 2

    # 2. 🔴 재귀 수집. 최상위만 보면 서브에이전트 로그를 통째로 놓친다.
    files = sorted(root.rglob("*.jsonl"))
    if not files:
        print(f"[오류] {root} 아래에 .jsonl이 없다 — 판정 불가.", file=sys.stderr)
        return 2

    # 3. 줄 단위로 usage를 수집한다. 파일 위치로 메인/서브를 가르고,
    #    서브에이전트 로그는 부모 디렉터리 이름(=세션 UUID)으로 귀속시킨다.
    seen_request_ids: set[str] = set()
    records: list[dict] = []
    malformed_lines = 0
    for path in files:
        # 실측 구조: 메인은 `<root>/<세션UUID>.jsonl`,
        #            서브는 `<root>/<세션UUID>/subagents/agent-<id>.jsonl`.
        # 🔴 `path.parent.name`으로 세션을 잡으면 서브가 전부 `subagents` 하나로
        #    뭉친다(값은 맞는데 단위가 어긋난다). 루트 기준 **첫 경로 요소**가
        #    세션이다 — 중간 디렉터리 이름이 바뀌어도 이 규칙은 유지된다.
        rel = path.relative_to(root)
        is_subagent = len(rel.parts) > 1
        session_id = rel.parts[0] if is_subagent else path.stem
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    malformed_lines += 1
                    continue
                message = entry.get("message")
                if not isinstance(message, dict):
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                request_id = entry.get("requestId")
                if not args.no_dedupe:
                    if request_id is None:
                        # requestId가 없으면 중복 판정 자체가 불가능하다.
                        # 조용히 버리면 과소 집계가 되므로 남기되 표시해 둔다.
                        pass
                    elif request_id in seen_request_ids:
                        continue
                    else:
                        seen_request_ids.add(request_id)
                cache_creation = usage.get("cache_creation") or {}
                write_1h = int(cache_creation.get("ephemeral_1h_input_tokens") or 0)
                write_5m = int(cache_creation.get("ephemeral_5m_input_tokens") or 0)
                write_total = int(usage.get("cache_creation_input_tokens") or 0)
                # TTL 분해가 없으면(구 버전 트랜스크립트) 전량을 1h로 본다 —
                # 1h가 더 비싸므로 보수적(과대) 추정 쪽이다.
                if write_1h + write_5m == 0 and write_total > 0:
                    write_1h = write_total
                records.append(
                    {
                        "session": session_id,
                        "subagent": is_subagent,
                        "model": message.get("model") or "unknown",
                        "input": int(usage.get("input_tokens") or 0),
                        "output": int(usage.get("output_tokens") or 0),
                        "cache_write_1h": write_1h,
                        "cache_write_5m": write_5m,
                        "cache_read": int(usage.get("cache_read_input_tokens") or 0),
                    }
                )

    # 4. 모델별·구분별·세션별로 누적하면서 비용을 환산한다.
    #    단가표에 없는 모델은 0원 처리하지 않는다 — 조용한 0은 "비용 없음"으로
    #    오독된다. 비용을 None으로 두고 `미측정`으로 따로 센다.
    axis_keys = ("input", "output", "cache_write_1h", "cache_write_5m", "cache_read")
    by_model: dict[str, dict] = defaultdict(
        lambda: {
            "requests": 0,
            "cost": 0.0,
            "priced": True,
            **dict.fromkeys(axis_keys, 0),
        }
    )
    by_scope: dict[str, dict] = defaultdict(
        lambda: {"requests": 0, "cost": 0.0, **dict.fromkeys(axis_keys, 0)}
    )
    by_session: dict[str, dict] = defaultdict(
        lambda: {"requests": 0, "cost": 0.0, **dict.fromkeys(axis_keys, 0)}
    )
    cost_by_axis: dict[str, float] = defaultdict(float)
    unpriced_models: set[str] = set()
    synthetic_skipped = 0

    for rec in records:
        model = rec["model"]
        if model in SYNTHETIC_MODELS:
            synthetic_skipped += 1
            continue
        price = PRICING.get(model)
        if price is None:
            unpriced_models.add(model)
            cost = None
        else:
            unit_in = price["input"] / MILLION
            cost = (
                rec["input"] * unit_in
                + rec["output"] * price["output"] / MILLION
                + rec["cache_write_1h"] * unit_in * CACHE_WRITE_MULTIPLIER_1H
                + rec["cache_write_5m"] * unit_in * CACHE_WRITE_MULTIPLIER_5M
                + rec["cache_read"] * unit_in * CACHE_READ_MULTIPLIER
            )
            cost_by_axis["input"] += rec["input"] * unit_in
            cost_by_axis["output"] += rec["output"] * price["output"] / MILLION
            cost_by_axis["cache_write"] += (
                rec["cache_write_1h"] * unit_in * CACHE_WRITE_MULTIPLIER_1H
                + rec["cache_write_5m"] * unit_in * CACHE_WRITE_MULTIPLIER_5M
            )
            cost_by_axis["cache_read"] += (
                rec["cache_read"] * unit_in * CACHE_READ_MULTIPLIER
            )

        scope = "서브에이전트" if rec["subagent"] else "메인"
        for bucket, key in (
            (by_model, model),
            (by_scope, scope),
            (by_session, rec["session"]),
        ):
            slot = bucket[key]
            slot["requests"] += 1
            for axis in axis_keys:
                slot[axis] += rec[axis]
            if cost is not None:
                slot["cost"] += cost
        if price is None:
            by_model[model]["priced"] = False

    total_cost = sum(cost_by_axis.values())
    total_tokens = sum(sum(rec[axis] for axis in axis_keys) for rec in records)

    # 5. 출력. --json은 기계 판독용이라 서식 없이 그대로 덤프한다.
    if args.json:
        payload = {
            "observed_root": str(root),
            "files": {
                "total": len(files),
                "main": sum(1 for f in files if f.parent == root),
            },
            "deduped": not args.no_dedupe,
            "unit": (
                "requests = unique requestId count; tokens = raw counts; "
                "cost = USD list-price estimate"
            ),
            "by_model": {k: dict(v) for k, v in by_model.items()},
            "by_scope": {k: dict(v) for k, v in by_scope.items()},
            "by_session": {k: dict(v) for k, v in by_session.items()},
            "cost_by_axis": dict(cost_by_axis),
            "total_cost_usd": total_cost,
            "unpriced_models": sorted(unpriced_models),
            "malformed_lines": malformed_lines,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    main_files = sum(1 for f in files if f.parent == root)
    dedupe_label = "꺼짐(--no-dedupe)" if args.no_dedupe else "켜짐(requestId 기준)"
    print(f"대상: {root}")
    print(
        f"파일: 총 {len(files)}개 "
        f"(메인 {main_files} / 서브에이전트 {len(files) - main_files})"
    )
    print(f"집계: {len(records)}건  |  중복 제거: {dedupe_label}")
    print(
        "단위: '요청'=고유 requestId 수(메시지 줄 수 아님) / "
        "토큰=백만(M) / 비용=USD 정가 추정"
    )
    if malformed_lines:
        print(f"경고: 파싱 실패한 줄 {malformed_lines}개 — 집계에서 빠졌다.")
    if synthetic_skipped:
        print(
            f"참고: 합성 항목(<synthetic>) {synthetic_skipped}건은 "
            "API 호출이 아니라 제외했다."
        )
    print()

    print("[1] 모델별")
    print(
        f"{'모델':<22}{'요청':>8}{'출력M':>10}{'캐시쓰기M':>12}{'캐시읽기M':>12}{'비용USD':>12}"
    )
    for model, v in sorted(by_model.items(), key=lambda kv: -kv[1]["cost"]):
        write_m = (v["cache_write_1h"] + v["cache_write_5m"]) / MILLION
        cost_cell = f"{v['cost']:>12,.2f}" if v["priced"] else f"{'미측정':>12}"
        print(
            f"{model:<22}{v['requests']:>8,}{v['output'] / MILLION:>10.2f}"
            f"{write_m:>12.2f}{v['cache_read'] / MILLION:>12.2f}{cost_cell}"
        )
    if unpriced_models:
        print(
            f"  🔴 단가표에 없는 모델: {', '.join(sorted(unpriced_models))}"
            " — 비용 `미측정`(0원 아님)"
        )
    print()

    print("[2] 메인 vs 서브에이전트")
    print(
        f"{'구분':<16}{'요청':>8}{'출력M':>10}{'캐시쓰기M':>12}{'캐시읽기M':>12}{'비용USD':>12}{'비중':>8}"
    )
    for scope, v in sorted(by_scope.items(), key=lambda kv: -kv[1]["cost"]):
        write_m = (v["cache_write_1h"] + v["cache_write_5m"]) / MILLION
        share = v["cost"] / total_cost * 100 if total_cost else 0.0
        print(
            f"{scope:<16}{v['requests']:>8,}{v['output'] / MILLION:>10.2f}"
            f"{write_m:>12.2f}{v['cache_read'] / MILLION:>12.2f}"
            f"{v['cost']:>12,.2f}{share:>7.1f}%"
        )
    print("  * 서브에이전트 비용은 그 세션을 띄운 부모 세션 ID로 귀속된다.")
    print()

    print(f"[3] 세션 TOP {args.top} (비용순)")
    print(
        f"{'세션':<12}{'요청':>8}{'요청당 컨텍스트':>18}"
        f"{'캐시읽기M':>12}{'출력M':>10}{'비용USD':>12}"
    )
    for session, v in sorted(by_session.items(), key=lambda kv: -kv[1]["cost"])[
        : args.top
    ]:
        ctx = (
            v["cache_read"] + v["cache_write_1h"] + v["cache_write_5m"] + v["input"]
        ) / v["requests"]
        print(
            f"{session[:10]:<12}{v['requests']:>8,}{ctx:>18,.0f}"
            f"{v['cache_read'] / MILLION:>12.2f}{v['output'] / MILLION:>10.2f}"
            f"{v['cost']:>12,.2f}"
        )
    print(
        "  * '요청당 컨텍스트' = (캐시읽기+캐시쓰기+미캐시입력) / 요청 수"
        " — 매 요청이 지고 가는 프롬프트 크기."
    )
    print()

    print("[4] 비용 동인")
    print(f"{'축':<14}{'비용USD':>12}{'비중':>8}")
    axis_labels = {
        "cache_read": "캐시 읽기",
        "cache_write": "캐시 쓰기",
        "output": "출력",
        "input": "미캐시 입력",
    }
    for axis, cost in sorted(cost_by_axis.items(), key=lambda kv: -kv[1]):
        share = cost / total_cost * 100 if total_cost else 0.0
        print(f"{axis_labels.get(axis, axis):<14}{cost:>12,.2f}{share:>7.1f}%")
    print(f"{'합계':<14}{total_cost:>12,.2f}{100.0:>7.1f}%")
    print(f"  총 토큰 {total_tokens / MILLION:,.1f}M")
    print()
    print("🔴 위 비용은 **API 정가 환산 추정**이며 실제 청구액이 아니다.")
    print(
        "   구독 플랜·할인 계약은 청구 구조가 다르다."
        " 단가는 스크립트 상단 PRICING의 스냅샷이다."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
