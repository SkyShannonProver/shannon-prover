"""Display ordering helpers for EasyCrypt session CLI output."""
from __future__ import annotations

import re
from typing import Optional

from core.easycrypt.session_common import (
    classify_and_format as _classify_and_format,
    trim_after_last_prompt as _trim_after_last_prompt,
)
from core.easycrypt.session_diagnostics import (
    explain_no_progress as _explain_no_progress,
)
from core.easycrypt.session_no_progress import detect_no_progress


DISPLAY_LAYER_MAP: list[tuple[str, int]] = [
    ("[DAEMON_REJECTED]", 0),
    ("[POST-CALL-INV-HINT]", 0),
    ("[STATE-DIFF]", 0),
    ("[GOAL_CLOSED]", 0),
    ("[ALL_GOALS_CLOSED]", 0),
    ("[TACTIC_NO_EFFECT_AUTO_REVERTED]", 0),
    ("[GOAL-TOO-LARGE]", 0),
    ("[AUTO-NOPROG-HINT]", 0),
    ("[AUTO-SIG]", 0),
    ("[CLASS:", 0),
    ("[STRICT_WARNING]", 0),
    ("State:", 1),
    ("Delta:", 1),
    ("[goal:", 1),
    ("[AUTO-PIVOT-CALL-READY]", 2),
    ("[AUTO-PIVOT-VERIFIED]", 2),
    ("[AUTO-BRIDGE-SUGGEST", 2),
    ("[AUTO-REWRITE-PROBE]", 2),
    ("[AUTO-DIFF]", 3),
    ("[AUTO-PIVOT]", 3),
    ("[AUTO-CALL-SUGGEST]", 3),
    ("[AUTO-LEMMA-HINTS]", 4),
    ("[AUTO-SELF-HINTS]", 4),
    ("[AUTO-RESOLVED-NAMES]", 5),
    ("[WHERE-HIT]", 5),
]


DISPLAY_LAYER_HEADERS = {
    0: "\n==[ L0 - action result ]==\n",
    1: "\n==[ L1 - current goal state ]==\n",
    2: "\n==[ L2 - ready-to-act (daemon-verified) ]==\n",
    3: "\n==[ L3 - file helpers (status-aware) ]==\n",
    4: "\n==[ L4 - strategy hints ]==\n",
    5: "\n==[ L5 - lookups ]==\n",
}


def classify_emit_chunk(chunk: str) -> int:
    """First-marker layer assignment. Unmatched chunks land in layer 6."""
    for marker, layer in DISPLAY_LAYER_MAP:
        if marker in chunk:
            return layer
    return 6


def reorder_display(display: list[str]) -> list[str]:
    """Group emit chunks by layer and prepend one header per non-empty layer."""
    layers: list[list[str]] = [[] for _ in range(7)]
    for chunk in display:
        layers[classify_emit_chunk(chunk)].append(chunk)
    out: list[str] = []
    for i in range(6):
        if layers[i]:
            out.append(DISPLAY_LAYER_HEADERS[i])
            out.extend(layers[i])
    if layers[6]:
        out.extend(layers[6])
    return out


def _last_try_chain_goal_after(steps: list) -> dict:
    """Return the last successful try-chain goal snapshot, if any."""
    for step in reversed(steps or []):
        if not isinstance(step, dict) or not step.get("accepted"):
            continue
        goal = step.get("goal_after") or {}
        if isinstance(goal, dict):
            return goal
    return {}


# ── Speculative-probe result rendering + current-state compression ─────────
# Pure text renderers moved out of Session (session_runtime) — they read only
# their arguments. Session keeps thin @staticmethod delegates so existing
# callers and tests are unaffected.

def format_try_single(
    tactic: str, r: dict, file_path: Optional[str] = None,
    prev_raw: str = "",
) -> str:
    accepted = bool(r.get("accepted"))
    out_lines = [
        f"[TRY] tactic: {tactic}",
        f"[TRY] accepted: {accepted}",
    ]
    if accepted:
        goal = r.get("goal_after") or {}
        if isinstance(goal, dict):
            if goal.get("is_closed"):
                out_lines.append("[TRY] goal_after: all goals closed.")
            else:
                remaining = goal.get("remaining", "?")
                out_lines.append(
                    f"[TRY] goal_after: {remaining} subgoal(s) remaining"
                )
                raw = goal.get("raw", "") or ""
                # Tier B cross-reference: when the speculative tactic
                # is `call (_: ...)` and ≥3 subgoals will spawn, point
                # the agent at `-call-subgoals` for the structured
                # preview (oracle proc names, ordering hints). Without
                # this, agent commits and reverse-engineers post-hoc.
                # step4_1 audit 2026-04-30: Tree-0.1 spent ~5 min after
                # call commit figuring out which of 4 subgoals was
                # which.
                _is_call_underscore = bool(
                    re.match(r"^\s*call\s*\(\s*_\s*:", tactic or "")
                )
                try:
                    _remaining_int = int(remaining)
                except (TypeError, ValueError):
                    _remaining_int = 0
                if _is_call_underscore and _remaining_int >= 3:
                    # Extract the invariant body for the suggested
                    # `-call-subgoals -c` invocation. Match the
                    # outermost `(_: ... )` group.
                    _inv_match = re.search(
                        r"call\s*\(\s*_\s*:\s*(?P<inv>.*)\)\s*\.\s*$",
                        (tactic or "").strip(),
                    )
                    _inv_text = (
                        _inv_match.group("inv").strip()
                        if _inv_match else "<invariant>"
                    )
                    out_lines.append(
                        f"[TRY] hint: this `call (_: I)` will spawn "
                        f"{remaining} subgoals. For a structured "
                        f"preview (oracle proc names + ordering "
                        f"recommendations) BEFORE you commit, run:"
                    )
                    out_lines.append(
                        f"  python3 core/easycrypt/session_cli.py "
                        f"-d <sess> -call-subgoals -c "
                        f"'{_inv_text[:120]}{'...' if len(_inv_text) > 120 else ''}'"
                    )
                # No-progress prediction: run the SAME detection that
                # commit-time auto-revert uses, so -try's verdict aligns
                # with what -next would actually do. Without this, agent
                # sees "accepted" → commits → -next auto-reverts →
                # confused → may restart session blaming "accumulated
                # state" (step3 Run 9 Tree-0.0 incident, ~5 min wasted).
                if prev_raw and raw:
                    is_noop, reason = detect_no_progress(
                        prev_raw, raw, has_new_error=False,
                    )
                    if is_noop:
                        out_lines.append(
                            f"[TRY] WARNING: tactic accepted but PRODUCES "
                            f"NO PROGRESS ({reason}). Committing via "
                            f"`-next`/`-chain` would auto-revert with "
                            f"`[TACTIC_NO_EFFECT_AUTO_REVERTED]`."
                        )
                        # Context-driven hint: extract concrete suggestions
                        # from the actual goal text (compiler-style
                        # diagnostic — names come from the proof, not
                        # hardcoded examples).
                        specific_hint = _explain_no_progress(tactic, prev_raw)
                        if specific_hint:
                            out_lines.append(f"[TRY] hint: {specific_hint}")
                if raw:
                    try:
                        from core.easycrypt.session_state import (  # type: ignore
                            extract_active_goal_block,
                        )
                        body, _remaining = extract_active_goal_block(raw)
                    except Exception:
                        body = ""
                    if not body:
                        snippet = _trim_after_last_prompt(raw)
                        body = "\n".join(snippet.splitlines()[-20:])
                    out_lines.append("[TRY] goal_after_raw:")
                    out_lines.append(body)
    else:
        err = r.get("error") or {}
        kind = err.get("kind", "unknown") if isinstance(err, dict) else "unknown"
        raw = (err.get("raw", "") if isinstance(err, dict) else "") or ""
        out_lines.append(f"[TRY] error_kind: {kind}")
        if raw:
            excerpt = [l for l in raw.strip().splitlines() if l.strip()][:6]
            out_lines.append("[TRY] error_excerpt:")
            for l in excerpt:
                out_lines.append(f"  {l}")
        # Error classification: label SYNTAX vs STRUCTURE so the
        # prover attributes correctly (see ec_error_classifier.py).
        cls_block = _classify_and_format(
            raw, tactic_text=tactic, file_path=file_path,
        )
        if cls_block:
            out_lines.append(cls_block.rstrip())
    out_lines.append(
        "[TRY] NOTE: session state unchanged. If accepted, commit "
        "with `-next -c '<tactic>'` to make it stick."
    )
    return "\n".join(out_lines) + "\n"


def format_try_chain(
    tactics: list, chain: dict, file_path: Optional[str] = None,
    prev_raw: str = "",
) -> str:
    accepted = bool(chain.get("accepted"))
    final_closed = bool(chain.get("final_closed"))
    out_lines = [
        f"[TRY-CHAIN] tactics: {len(tactics)} step(s)",
    ]
    for i, t in enumerate(tactics):
        out_lines.append(f"  [{i + 1}] {t}")
    out_lines.append("")
    out_lines.append(f"[TRY-CHAIN] all_accepted: {accepted}")
    out_lines.append(f"[TRY-CHAIN] final_closed: {final_closed}")

    steps = chain.get("steps") or []
    failed_at = chain.get("failed_at")
    # Step-by-step no-progress prediction: thread prev_raw through
    # the chain. After step N succeeds with goal_after.raw, that
    # becomes prev_raw for step N+1's no-progress check. Detects
    # mid-chain no-op tactics (e.g. `inline X. proc.` where the
    # `inline X` is a no-op but `proc.` isn't).
    running_prev = prev_raw
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        ok = s.get("accepted")
        noop_tag = ""
        if ok:
            ga = s.get("goal_after") or {}
            if isinstance(ga, dict) and ga.get("is_closed"):
                state = "→ all goals closed"
                running_prev = ""  # no further prev to compare
            elif isinstance(ga, dict):
                state = f"→ {ga.get('remaining', '?')} subgoal(s) remaining"
                new_raw = ga.get("raw", "") or ""
                if running_prev and new_raw:
                    is_noop, reason = detect_no_progress(
                        running_prev, new_raw, has_new_error=False,
                    )
                    if is_noop:
                        noop_tag = f"  [NO-PROGRESS: {reason} — would auto-revert if committed]"
                if new_raw:
                    running_prev = new_raw
            else:
                state = "→ ok"
        else:
            err = s.get("error") or {}
            kind = err.get("kind", "unknown") if isinstance(err, dict) else "unknown"
            state = f"✗ {kind}"
        out_lines.append(f"  step {i + 1} ({tactics[i] if i < len(tactics) else '?'}): {state}{noop_tag}")

    if accepted:
        if final_closed:
            out_lines.append("[TRY-CHAIN] goal_after: all goals closed.")
        else:
            final_goal = _last_try_chain_goal_after(steps)
            if final_goal:
                remaining = final_goal.get("remaining", "?")
                out_lines.append(
                    f"[TRY-CHAIN] goal_after: {remaining} subgoal(s) remaining"
                )
                raw = final_goal.get("raw", "") or ""
                if raw:
                    try:
                        from core.easycrypt.session_state import (  # type: ignore
                            extract_active_goal_block,
                        )
                        body, _remaining = extract_active_goal_block(raw)
                    except Exception:
                        body = ""
                    if not body:
                        snippet = _trim_after_last_prompt(raw)
                        body = "\n".join(snippet.splitlines()[-20:])
                    out_lines.append("[TRY-CHAIN] goal_after_raw:")
                    out_lines.append(body)

    if failed_at is not None and failed_at < len(tactics):
        err = chain.get("error") or {}
        kind = err.get("kind", "unknown") if isinstance(err, dict) else "unknown"
        raw = (err.get("raw", "") if isinstance(err, dict) else "") or ""
        out_lines.append("")
        out_lines.append(
            f"[TRY-CHAIN] stopped at step {failed_at + 1}: {kind}"
        )
        if raw:
            excerpt = [l for l in raw.strip().splitlines() if l.strip()][:6]
            out_lines.append("[TRY-CHAIN] error_excerpt:")
            for l in excerpt:
                out_lines.append(f"  {l}")
        # Error classification: label SYNTAX vs STRUCTURE for the
        # failing step so the prover attributes correctly.
        failing_tactic = tactics[failed_at] if failed_at is not None and failed_at < len(tactics) else ""
        cls_block = _classify_and_format(
            raw, tactic_text=failing_tactic, file_path=file_path,
        )
        if cls_block:
            out_lines.append(cls_block.rstrip())

    out_lines.append(
        "[TRY-CHAIN] NOTE: session state unchanged. Commit the "
        "full chain by calling `-next -c '<tactic1>. <tactic2>...'` "
        "or step by step with `-next`."
    )
    return "\n".join(out_lines) + "\n"


def compress_current_state(text: str) -> str:
    """Reduce raw EC transcript output to only the current goal state.

    Raw EC output contains the full replay transcript: context processing,
    cloned-theory chatter, per-tactic commit / undo prompts. When
    `-start -lemma <name>` extracts a standalone context, subsequent
    lemmas whose types are not yet cloned produce benign `[error-*]`
    lines on their way to the target lemma's prompt. These errors are
    NOT state problems — EC reaches the target and happily accepts
    tactics — but they sit in `current.out` and look alarming to an
    agent that Reads the file.

    v7.2 step1 (2026-04-22) lost a ~45-min run: the agent Read
    `current.out`, saw `[error-26-28]unknown type name: RO` and
    `[error-0-17]cannot process [proof script] outside a proof script`
    inside the context transcript, escalated to "the session is
    corrupted", rm'd `history.ec`/`steps.log`/`current.out`/`delta.out`,
    and blew away 30 min of proof state.

    Fix: `current.out` should contain the CURRENT GOAL STATE, not the
    replay transcript. This helper finds the relevant state section and
    returns it; trailing noise past the last prompt is also stripped.

    Rules:
      - Locate the last state marker (`Current goal`, `Current goal
        (remaining: N)`, or `No more goals`). Keep from there onwards.
      - If no state marker but a prompt exists, keep the content from
        the 2nd-to-last prompt (so the last state + last prompt are
        both present, which lets the no-progress diff compare useful
        state rather than prompts).
      - If neither exists, return the text unchanged (EC presumably
        didn't produce anything recognizable; don't destroy info).
      - Always apply ``_trim_after_last_prompt`` to strip trailing
        post-prompt noise.
    """
    if not text:
        return text
    lines = text.splitlines(keepends=True)
    # Look for state markers
    state_marker_idx = -1
    state_re = re.compile(
        r"^(?:Current goal(?:\s*\(remaining:\s*\d+\))?|No more goals)\s*$"
    )
    prompt_re = re.compile(r"^\[[0-9]+\|[^\]]+\]>\s*$")
    prompt_indices: list = []
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if state_re.match(stripped):
            state_marker_idx = i
        if prompt_re.match(stripped):
            prompt_indices.append(i)
    if state_marker_idx != -1:
        # Back up to the preceding prompt (if any) so the state section
        # starts at a clean boundary. Keep from there to the end — EC
        # often emits the final state BODY after the last prompt (EOF
        # without a trailing prompt), so do NOT strip trailing content.
        start = state_marker_idx
        for p in reversed(prompt_indices):
            if p < state_marker_idx:
                start = p
                break
        return "".join(lines[start:])
    if prompt_indices:
        # No state marker — keep content from the 2nd-to-last prompt
        # onward so we preserve both the last prompt and what came
        # before (which often names the failing construct). For a
        # single prompt, just keep from it.
        start = prompt_indices[-2] if len(prompt_indices) >= 2 else prompt_indices[-1]
        return "".join(lines[start:])
    return text

# ── Generic text/statement display helpers (moved from the workspace-view
# module; the frontier-scope module and the view builder both consume them). ─

def preview(text: str, *, limit: int = 420) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def leading_statement(side_text: str) -> str:
    """The FIRST (syntactic-head) statement of a side. An `_alignment_rows` 'setup'
    row summarises the leading statements as 'N setup statement(s): a; b' — the head
    is `a`. A plain row already carries a single statement."""
    s = (side_text or "").strip()
    m = re.match(r'^\d+\s+setup statement\(s\):\s*(.*)$', s)
    if m:
        s = m.group(1).strip()
    low = s.lower()
    if low.startswith("while") or low.startswith("if ") or low.startswith("if("):
        return s  # a structural head spans a block — keep it whole
    return s.split(';', 1)[0].strip()


def statement_head(statement: str) -> str:
    text = statement.strip()
    lowered = text.lower()
    if (
        not text
        or (lowered.startswith("no ") and "frontier" in lowered)  # "no … at this frontier" placeholders
        or lowered.startswith("easycrypt marks the programs as synchronized")
        or "residual program column" in lowered  # a synchronized-column note, not a stmt
    ):
        return ""
    if lowered.startswith("if ") or lowered.startswith("if("):
        return "if"
    if lowered.startswith("while ") or lowered.startswith("while("):
        return "while"
    if "<@" in text:
        return "call"
    if "<$" in text:
        return "sample"
    if "<-" in text:
        return "assignment"
    if lowered.startswith("return"):
        return "return"
    return "statement"
