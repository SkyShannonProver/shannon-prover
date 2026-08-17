"""Extract each prover turn's reasoning (thinking) text into node memory.

The run's own artifacts deliberately never store the agent's thinking — see
``workflow/progress.py:_assistant_context_before_tool`` (only size/hash/markers).
Claude reasoning lives in its session transcript under ``~/.claude/projects``;
Codex emits a run-confined ``runtime_private/<node>/codex_events.jsonl`` stream.
This module joins the applicable provider stream back to the per-turn timeline
and writes, for each
``submit_proof_intent`` turn, the thinking block(s) that immediately preceded it
to ``node_memory/<tree>/thinking/turn_NNN.md`` — so the agent-view timeline can
link a per-step, clickable thinking view next to each row, the same way it links
the per-turn ``ProverWorkspaceView``.

Transcript discovery (per node):

1. Preferred — ``node_memory/<tree>/agent_sessions.jsonl`` written at run time
   (``NodeMemory.record_agent_session``): the recorded ``session_id`` resolves
   directly to ``~/.claude/projects/*/<session_id>.jsonl``.
2. A bounded transcript scan for current runs missing a registry record, joined
   by the ordered current ``submit_proof_intent`` sequence.

Offline and deterministic. Reading a transcript here is a backend audit action
on sessions this run produced; it is not the agent-facing protocol.

Usage:
    python3 -m workflow.validation.agent_thinking_trace <run_iteration_dir>
    python3 -m workflow.validation.agent_thinking_trace --node <node_memory/Tree_x> \
        [--transcript PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import json
from dataclasses import dataclass, field
from pathlib import Path
from workflow.validation.replay_artifacts import node_id_from_dir as _node_id_from_dir
from typing import Any


@dataclass
class TurnThinking:
    ts: str
    intent: str
    key: str
    thinking: str
    text: str
    session_id: str
    # Provider usage (deduped). Claude is attributable between manager submits;
    # Codex usage is an exact CLI-turn aggregate attached to that CLI turn's last
    # manager submit. ``token_usage_scope`` distinguishes those semantics.
    tokens: dict[str, int] = field(default_factory=dict)
    token_usage_scope: str = ""


@dataclass
class NodeResult:
    node_dir: Path
    node_id: str
    transcripts: list[Path] = field(default_factory=list)
    discovery: str = ""
    turns_written: int = 0
    turns_total: int = 0
    files: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# transcript parsing
# ---------------------------------------------------------------------------

def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def intent_payload_key(intent_name: str, payload: dict[str, Any]) -> str:
    """Normalized fingerprint of an intent payload, stable across the transcript
    and the timeline so the two can be matched position-by-position."""
    if intent_name == "commit_tactic":
        return " ".join(str(payload.get("tactic") or "").split())
    return json.dumps(payload, sort_keys=True) if payload else ""


def usage_dedup_key(event: dict, message: dict) -> str:
    """Dedup key for streamed usage chunks: one request/message counts once.

    THE canonical formula — eval_suite.metrics imports it. The two trace
    readers stay separate on purpose (this module attributes thinking to
    turns for bundles; metrics does whole-run token accounting over all
    events), but they must never disagree on what "one request" means.
    """
    message_id = str(message.get("id") or "")
    request_id = str(event.get("requestId") or "")
    if message_id or request_id:
        return f"{request_id}:{message_id}"
    return ""


def normalize_codex_usage(usage: dict[str, Any]) -> dict[str, int]:
    """Normalize OpenAI counters into the four disjoint report categories.

    Codex reports total input plus cached/cache-write subsets, while the
    existing report schema stores mutually exclusive uncached input, cache
    creation, cache reads, and output.  Clamp malformed overlaps so the three
    input categories always sum to the provider's total input counter.
    Reasoning output is retained as an exact diagnostic subset of output.
    """

    def token_int(value: Any) -> int:
        if isinstance(value, bool) or value is None:
            return 0
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    total_input = token_int(usage.get("input_tokens"))
    cache_read = min(total_input, token_int(usage.get("cached_input_tokens")))
    remaining = total_input - cache_read
    cache_creation = min(
        remaining,
        token_int(
            usage.get("cache_write_input_tokens")
            if usage.get("cache_write_input_tokens") is not None
            else usage.get("cache_creation_input_tokens")
        ),
    )
    return {
        "input_tokens": remaining - cache_creation,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "output_tokens": token_int(usage.get("output_tokens")),
        "reasoning_output_tokens": token_int(
            usage.get("reasoning_output_tokens")
        ),
    }


def _codex_item_text(item: dict[str, Any]) -> str:
    for key in ("text", "summary", "aggregated_output", "output", "result"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            text = "\n".join(str(part) for part in value if str(part).strip())
            if text.strip():
                return text
    return ""


def _extract_codex_turns(
    events: list[dict[str, Any]],
    transcript: Path,
) -> list[TurnThinking]:
    """Extract manager submits from Codex JSONL.

    Codex reports usage once at the end of a CLI turn, and one CLI turn may
    contain several manager calls.  Preserve exact whole-run accounting by
    attaching that aggregate to the last manager call in the CLI turn and
    label its scope explicitly; do not invent a per-manager-call split.
    """

    turns: list[TurnThinking] = []
    pending_think: list[str] = []
    pending_text: list[str] = []
    current_session = transcript.stem
    current_cli_turn: list[int] = []
    seen_tool_calls: set[str] = set()

    for event in events:
        event_type = str(event.get("type") or "")
        if event_type == "thread.started":
            current_session = str(event.get("thread_id") or current_session)
            continue
        if event_type == "turn.started":
            current_cli_turn = []
            # Codex item ids are scoped to one ``exec``/resume turn and may be
            # reused (for example every turn can start again at ``item_1``).
            seen_tool_calls = set()
            continue
        item = event.get("item")
        item = item if isinstance(item, dict) else {}
        item_type = str(item.get("type") or "")
        if item_type == "reasoning" and event_type == "item.completed":
            text = _codex_item_text(item)
            if text:
                pending_think.append(text)
            continue
        if item_type == "agent_message" and event_type == "item.completed":
            text = _codex_item_text(item)
            if text:
                pending_text.append(text)
            continue
        if item_type == "mcp_tool_call" and event_type in {
            "item.started",
            "item.completed",
        }:
            tool = str(item.get("tool") or item.get("name") or "")
            if tool != "submit_proof_intent":
                continue
            item_id = str(item.get("id") or "")
            if item_id and item_id in seen_tool_calls:
                continue
            if item_id:
                seen_tool_calls.add(item_id)
            arguments = item.get("arguments") or item.get("input") or {}
            arguments = arguments if isinstance(arguments, dict) else {}
            payload = arguments.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            turns.append(TurnThinking(
                ts=str(event.get("timestamp") or ""),
                intent=str(arguments.get("intent") or ""),
                key=intent_payload_key(str(arguments.get("intent") or ""), payload),
                thinking="\n\n".join(pending_think).strip(),
                text="\n\n".join(pending_text).strip(),
                session_id=current_session,
            ))
            current_cli_turn.append(len(turns) - 1)
            pending_think = []
            pending_text = []
            continue
        if event_type == "turn.completed":
            usage = event.get("usage")
            if current_cli_turn and isinstance(usage, dict):
                target = turns[current_cli_turn[-1]]
                target.tokens = normalize_codex_usage(usage)
                target.token_usage_scope = "codex_cli_turn_aggregate"
            current_cli_turn = []

    return turns


def extract_turns(transcript: Path) -> list[TurnThinking]:
    """Ordered submit_proof_intent turns in one transcript, each carrying the
    thinking/text blocks that immediately preceded it.

    Thinking and the tool_use can land in the same assistant event or in separate
    streamed events, so we accumulate blocks in document order and flush them onto
    the next ``submit_proof_intent``.
    """
    events = _iter_jsonl(transcript)
    if any(
        str(event.get("type") or "") in {
            "thread.started",
            "turn.started",
            "turn.completed",
            "item.started",
            "item.completed",
        }
        for event in events
    ):
        return _extract_codex_turns(events, transcript)

    session_id = transcript.stem
    turns: list[TurnThinking] = []
    pending_think: list[str] = []
    pending_text: list[str] = []
    pending_usage: dict[str, int] = {}
    seen_usage: set[str] = set()
    _UF = ("output_tokens", "input_tokens",
           "cache_read_input_tokens", "cache_creation_input_tokens")
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        sid = str(ev.get("sessionId") or ev.get("session_id") or session_id)
        ts = str(ev.get("timestamp") or "")
        msg = ev.get("message") or {}
        # accumulate deduped usage onto the current (not-yet-flushed) turn. Dedup
        # by requestId:message_id so streamed chunks of one request count once
        # (identical to eval_suite.metrics — verified exact).
        usage = msg.get("usage")
        if isinstance(usage, dict):
            ukey = usage_dedup_key(ev, msg)
            if ukey not in seen_usage:
                seen_usage.add(ukey)
                for _f in _UF:
                    pending_usage[_f] = pending_usage.get(_f, 0) + int(usage.get(_f) or 0)
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict):
                continue
            btype = blk.get("type")
            if btype == "thinking":
                txt = str(blk.get("thinking") or "")
                if txt.strip():
                    pending_think.append(txt)
            elif btype == "text":
                txt = str(blk.get("text") or "")
                if txt.strip():
                    pending_text.append(txt)
            elif btype == "tool_use" and str(blk.get("name") or "").endswith(
                "submit_proof_intent"
            ):
                inp = blk.get("input") or {}
                name = str(inp.get("intent") or "")
                payload = inp.get("payload") or {}
                turns.append(TurnThinking(
                    ts=ts,
                    intent=name,
                    key=intent_payload_key(
                        name, payload if isinstance(payload, dict) else {},
                    ),
                    thinking="\n\n".join(pending_think).strip(),
                    text="\n\n".join(pending_text).strip(),
                    session_id=sid,
                    tokens=dict(pending_usage),
                ))
                pending_think = []
                pending_text = []
                pending_usage = {}
    return turns


# ---------------------------------------------------------------------------
# node timeline (the ground-truth intent sequence to match against)
# ---------------------------------------------------------------------------

def _node_intents(node_dir: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for entry in _iter_jsonl(node_dir / "timeline.jsonl"):
        if entry.get("kind") != "manager_turn":
            continue
        intent = entry.get("intent") or {}
        name = str(intent.get("intent") or "")
        payload = intent.get("payload") or {}
        out.append((
            name,
            intent_payload_key(name, payload if isinstance(payload, dict) else {}),
        ))
    return out


def _node_time_window(node_dir: Path) -> tuple[str, str]:
    times = [
        str(e.get("time") or "")
        for e in _iter_jsonl(node_dir / "timeline.jsonl")
        if e.get("time")
    ]
    times = [t for t in times if t]
    if not times:
        return "", ""
    return min(times), max(times)


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def _claude_projects_root() -> Path:
    return Path.home() / ".claude" / "projects"


def _resolve_recorded_transcripts(node_dir: Path) -> list[Path]:
    """Provider event streams named by the run-time session registry."""
    paths: list[Path] = []
    seen: set[str] = set()
    seen_paths: set[Path] = set()
    for rec in _iter_jsonl(node_dir / "agent_sessions.jsonl"):
        backend = str(rec.get("agent_backend") or "claude")
        sid = str(rec.get("session_id") or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        if backend == "codex":
            iteration_dir = node_dir.parent.parent
            candidate = (
                iteration_dir
                / "runtime_private"
                / node_dir.name
                / "codex_events.jsonl"
            )
            resolved = candidate.resolve()
            if candidate.is_file() and resolved not in seen_paths:
                seen_paths.add(resolved)
                paths.append(candidate)
            continue
        if backend != "claude":
            continue
        candidate = Path(str(rec.get("transcript_path") or ""))
        if candidate.is_file():
            resolved = candidate.resolve()
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                paths.append(candidate)
            continue
        # Authoritative key is the filename; recover by glob if the stored path is
        # stale (e.g. bundle moved to another machine).
        hits = glob.glob(str(_claude_projects_root() / "*" / f"{sid}.jsonl"))
        if hits:
            resolved = Path(hits[0]).resolve()
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                paths.append(Path(hits[0]))
    return paths


def _ts_to_epoch(ts: str) -> float:
    if not ts:
        return 0.0
    try:
        from datetime import datetime
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _match_at(
    node_intents: list[tuple[str, str]], offset: int, turns: list[TurnThinking],
) -> int:
    """Length of the run of transcript submits matching the node's intent
    sequence starting at ``offset`` — a near-unique fingerprint for the session
    (or session-chain link) that drove this stretch of the node."""
    score = 0
    for (n_name, n_key), turn in zip(node_intents[offset:], turns):
        if n_name == turn.intent and n_key == turn.key:
            score += 1
        else:
            break
    return score


def _candidate_pool(node_dir: Path, *, window_pad_s: float = 1800.0) -> list[Path]:
    """Recorded transcripts PLUS every transcript whose mtime overlaps the node's
    timeline window. The recorded pointers are not trusted to be complete: a
    context swap mid-run starts a new Claude session, and historically only the
    final session of the chain was registered."""
    pool = list(_resolve_recorded_transcripts(node_dir))
    registered = list(_iter_jsonl(node_dir / "agent_sessions.jsonl"))
    if registered and not any(
        str(record.get("agent_backend") or "claude") == "claude"
        for record in registered
    ):
        # A Codex thread id is not a Claude transcript key. Do not let the
        # historical mtime-window fallback attach an unrelated Claude run.
        return pool
    seen = {p.resolve() for p in pool}
    start, end = _node_time_window(node_dir)
    lo = _ts_to_epoch(start) - window_pad_s
    hi = _ts_to_epoch(end) + window_pad_s
    if lo and hi:
        for path in _claude_projects_root().glob("*/*.jsonl"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if not (lo <= mtime <= hi):
                continue
            if path.resolve() not in seen:
                seen.add(path.resolve())
                pool.append(path)
    return pool


# A ctx-respawn can terminate a generation with a submit in flight; the fresh
# session then re-submits it, so the continuation transcript may START with a
# few submits that duplicate the previous link's tail without a matching
# timeline row. Chain assembly may skip up to this many leading submits of a
# NON-FIRST link to realign.
_RESPAWN_BOUNDARY_SKIP = 2


def _assemble_chain(
    candidates: list[Path],
    node_intents: list[tuple[str, str]],
    cache: dict[Path, list[TurnThinking]],
) -> list[tuple[Path, list[TurnThinking]]]:
    """Greedy chain assembly over ``candidates`` against the intent timeline."""
    chain: list[tuple[Path, list[TurnThinking]]] = []
    used: set[Path] = set()
    offset = 0
    while offset < len(node_intents):
        best: tuple[int, int, Path] | None = None  # (score, skip, path)
        for path in candidates:
            if path in used:
                continue
            if path not in cache:
                cache[path] = extract_turns(path)
            turns = cache[path]
            if not turns:
                continue
            max_skip = _RESPAWN_BOUNDARY_SKIP if chain else 0
            for skip in range(0, min(max_skip, len(turns) - 1) + 1):
                score = _match_at(node_intents, offset, turns[skip:])
                # Require a real run of matching intents, not a chance single
                # hit (a short tail may legitimately be shorter than 3).
                if score >= min(3, len(node_intents) - offset):
                    if best is None or score > best[0]:
                        best = (score, skip, path)
        if best is None:
            break
        score, skip, path = best
        # Slice to the matched run so stray leading resubmits and trailing
        # submits (e.g. a session that outlived the node) cannot shift the
        # global numbering.
        chain.append((path, cache[path][skip:skip + score]))
        used.add(path)
        offset += score
    return chain


def assemble_session_chain(
    node_dir: Path,
) -> tuple[list[tuple[Path, list[TurnThinking]]], str]:
    """Greedily assemble the node's full session chain against its timeline.

    Starting at intent 0, repeatedly pick the candidate transcript whose submit
    sequence matches the longest run of the node's remaining intents; take that
    matched slice, advance, and continue with the next transcript. This stitches
    context-swap chains (session N covers turns 1..k, session N+1 covers
    k+1..m, ...) so the merged turn numbering is global and aligns with the
    timeline rows.

    Discovery order: the canonical per-node registry
    (``agent_sessions.jsonl``) first — a run whose runtime registered every
    session resolves entirely from it. The mtime-window sweep over
    ``~/.claude/projects`` is only a fallback for historical bundles whose
    registry predates registration-at-creation and is incomplete.
    """
    node_intents = _node_intents(node_dir)
    recorded = _resolve_recorded_transcripts(node_dir)
    if not node_intents:
        # No timeline to align against — old behavior: recorded sessions as-is.
        return (
            [(p, extract_turns(p)) for p in recorded],
            "recorded_session_id" if recorded else "not_found",
        )
    cache: dict[Path, list[TurnThinking]] = {}
    # Primary: the canonical registry alone.
    chain = _assemble_chain(recorded, node_intents, cache)
    covered = sum(len(t) for _, t in chain)
    if covered < len(node_intents):
        # Historical fallback: registry + transcripts whose mtime overlaps the
        # node's window (older runs registered only the first session).
        pool = _assemble_chain(_candidate_pool(node_dir), node_intents, cache)
        if sum(len(t) for _, t in pool) > covered:
            chain = pool
            covered = sum(len(t) for _, t in chain)
    if chain:
        if len(chain) > 1:
            label = f"session_chain[{len(chain)}]"
        elif chain[0][0] in recorded:
            label = "recorded_session_id"
        else:
            label = "content_match"
        if covered < len(node_intents):
            label += f" (partial {covered}/{len(node_intents)})"
        return chain, label
    if recorded:
        # Alignment failed entirely — fall back to the recorded pointers.
        return [(p, extract_turns(p)) for p in recorded], "recorded_session_id"
    return [], "not_found"


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def _node_display(node_id: str) -> str:
    return node_id


def _render_turn_md(*, node_id: str, turn: int, t: TurnThinking) -> str:
    tac = t.key or "(none)"
    body = t.thinking.strip()
    if not body:
        body = t.text.strip()
    header = (
        f"# {node_id} · turn {turn} · {t.intent or 'unknown'}\n\n"
        f"<!-- session {t.session_id} · {t.ts} -->\n\n"
        f"**Intent:** `{t.intent}`  \n"
        f"**Payload:** `{tac}`\n\n"
        "---\n\n"
    )
    return header + (body if body else "_(no reasoning text captured before this submit)_") + "\n"


def write_node_thinking(node_dir: Path, *, dry_run: bool = False) -> NodeResult:
    node_id = _node_id_from_dir(node_dir)
    result = NodeResult(node_dir=node_dir, node_id=node_id)
    chain, discovery = assemble_session_chain(node_dir)
    result.transcripts = [p for p, _ in chain]
    result.discovery = discovery
    if not chain:
        return result

    # Concatenate the timeline-aligned slices in chain order: global turn i is
    # exactly timeline row i. (Chain links are already time-ordered by
    # construction; re-sorting by ts could scramble identical timestamps.)
    merged: list[TurnThinking] = []
    for _, turns in chain:
        merged.extend(turns)
    result.turns_total = len(merged)

    thinking_dir = node_dir / "thinking"
    index: list[dict[str, Any]] = []
    for i, t in enumerate(merged, start=1):
        has_reasoning = bool(t.thinking.strip() or t.text.strip())
        index.append({
            "turn": i,
            "intent": t.intent,
            "payload_key": t.key,
            "thinking_chars": len(t.thinking),
            "text_chars": len(t.text),
            "tokens": t.tokens,
            "token_usage_scope": t.token_usage_scope,
            "session_id": t.session_id,
            "timestamp": t.ts,
            "file": f"thinking/turn_{i:03d}.md" if has_reasoning else "",
        })
        if not has_reasoning or dry_run:
            continue
        thinking_dir.mkdir(parents=True, exist_ok=True)
        out_path = thinking_dir / f"turn_{i:03d}.md"
        out_path.write_text(
            _render_turn_md(node_id=node_id, turn=i, t=t), encoding="utf-8"
        )
        result.files.append(str(out_path))
        result.turns_written += 1
    if not dry_run and index:
        thinking_dir.mkdir(parents=True, exist_ok=True)
        (thinking_dir / "index.json").write_text(
            json.dumps({
                "node": node_id,
                "discovery": discovery,
                "transcripts": [str(p) for p in result.transcripts],
                "turns": index,
            }, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
    return result


def write_run_thinking(run_iter_dir: Path, *, dry_run: bool = False) -> list[NodeResult]:
    root = run_iter_dir / "node_memory"
    if not root.is_dir():
        return []
    results: list[NodeResult] = []
    for node_dir in sorted(root.iterdir()):
        if not node_dir.is_dir() or not (node_dir / "timeline.jsonl").exists():
            continue
        results.append(write_node_thinking(node_dir, dry_run=dry_run))
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_iteration_dir",
        nargs="?",
        help="Run iteration dir (writes thinking/ under every node_memory tree).",
    )
    parser.add_argument(
        "--node",
        type=Path,
        help="A single node_memory/<tree> dir instead of a whole run.",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        help="Override transcript discovery for --node (debugging).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.node is not None:
        node_dir = args.node
        if args.transcript is not None:
            # Stage an explicit pointer so discovery uses it.
            res = NodeResult(node_dir=node_dir, node_id=_node_id_from_dir(node_dir))
            merged = extract_turns(args.transcript)
            print(
                f"{res.node_id}: transcript={args.transcript.name} "
                f"submits={len(merged)} "
                f"with_thinking={sum(1 for t in merged if t.thinking.strip())}"
            )
            if not args.dry_run:
                # reuse the standard writer by faking recorded discovery
                _write_from_turns(node_dir, res.node_id, merged, [args.transcript])
            return 0
        results = [write_node_thinking(node_dir, dry_run=args.dry_run)]
    elif args.run_iteration_dir:
        results = write_run_thinking(Path(args.run_iteration_dir), dry_run=args.dry_run)
    else:
        parser.error("provide a run iteration dir or --node")
        return 2

    for r in results:
        print(
            f"{r.node_id}: discovery={r.discovery} "
            f"transcripts={[p.name for p in r.transcripts]} "
            f"turns={r.turns_written}/{r.turns_total} written"
        )
    return 0


def _write_from_turns(
    node_dir: Path, node_id: str, merged: list[TurnThinking], transcripts: list[Path],
) -> None:
    merged = sorted(merged, key=lambda t: (_ts_to_epoch(t.ts), t.ts))
    thinking_dir = node_dir / "thinking"
    index: list[dict[str, Any]] = []
    for i, t in enumerate(merged, start=1):
        has_reasoning = bool(t.thinking.strip() or t.text.strip())
        index.append({
            "turn": i, "intent": t.intent, "payload_key": t.key,
            "thinking_chars": len(t.thinking), "text_chars": len(t.text),
            "session_id": t.session_id, "timestamp": t.ts,
            "tokens": t.tokens, "token_usage_scope": t.token_usage_scope,
            "file": f"thinking/turn_{i:03d}.md" if has_reasoning else "",
        })
        if not has_reasoning:
            continue
        thinking_dir.mkdir(parents=True, exist_ok=True)
        (thinking_dir / f"turn_{i:03d}.md").write_text(
            _render_turn_md(node_id=node_id, turn=i, t=t), encoding="utf-8"
        )
    if index:
        thinking_dir.mkdir(parents=True, exist_ok=True)
        (thinking_dir / "index.json").write_text(
            json.dumps({
                "node": node_id, "discovery": "explicit_transcript",
                "transcripts": [str(p) for p in transcripts], "turns": index,
            }, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(main())
