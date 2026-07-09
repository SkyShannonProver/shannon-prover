"""Structured reader for EasyCrypt session state.

This module is the Phase-2 boundary between EC's human-facing text stream and
the rest of the toolchain. Code outside this module should not re-implement
prompt scanning or closed-proof detection when it only needs the active goal.
"""
from __future__ import annotations

import json as _json
import re
from dataclasses import dataclass
from pathlib import Path


REMAINING_UNKNOWN = -1
_CHECK_PROMPT_RE = re.compile(r"\[(\d+)\|check\]>")
_ANY_PROMPT_RE = re.compile(r"\[\d+\|[^\]]+\]>")
_CURRENT_GOAL_MARKER_RE = re.compile(
    r"^\s*Current goal(?:\s*\(remaining:\s*(\d+)\))?\s*$",
)
_NO_MORE_GOALS_MARKER_RE = re.compile(r"^\s*No more goals\s*$")


@dataclass(frozen=True)
class SessionState:
    session_dir: Path
    current_path: Path
    previous_path: Path
    has_current: bool
    raw_current: str
    active_output: str
    active_goal_block: str
    num_remaining: int
    proof_candidate_closed: bool

    @property
    def raw_for_goal_tools(self) -> str:
        return self.active_goal_block if self.active_goal_block else self.active_output


def read_session_state(
    session_dir: Path,
    current_path: Path | None = None,
    previous_path: Path | None = None,
    target_lemma: str | None = None,
) -> SessionState:
    """Read the current structured state for a session directory.

    ``target_lemma`` overrides the closed-detection heuristic with EC's
    authoritative ``+ added lemma: `<NAME>'`` close signal. When the
    session is started with ``-lemma <NAME>``, the extracted file
    contains helper lemmas that close (each emitting their own
    ``No more goals`` and ``+ added lemma`` lines) BEFORE the target
    lemma's open proof. The legacy heuristic — scan backwards from the
    last prompt for ``No more goals`` vs ``Current goal`` — picks up a
    helper's close and falsely reports the target as closed. Discovered
    on ChaChaPoly step1 (2026-05-03) where Tree-0.1 saw
    ``candidate_closed`` despite having an open ``proof.`` for step1
    and burned 7 min in a debug rabbit hole.

    When ``target_lemma`` is None, this reads the lemma name from
    ``session_meta.json`` automatically (best-effort). Pass ``""``
    explicitly to opt out of lemma-aware detection.
    """
    session_dir = Path(session_dir)
    current_path = Path(current_path) if current_path else session_dir / "current.out"
    previous_path = Path(previous_path) if previous_path else session_dir / "prev.out"
    if not current_path.exists():
        return SessionState(
            session_dir=session_dir,
            current_path=current_path,
            previous_path=previous_path,
            has_current=False,
            raw_current="",
            active_output="",
            active_goal_block="",
            num_remaining=REMAINING_UNKNOWN,
            proof_candidate_closed=False,
        )

    raw_current = current_path.read_text(encoding="utf-8", errors="replace")
    active_output = extract_active_goal_output(raw_current, previous_path)
    active_goal_block, num_remaining = extract_active_goal_block(raw_current)

    if target_lemma is None:
        target_lemma = read_target_lemma_from_meta(session_dir)

    target_signal = (
        target_lemma_added(raw_current, target_lemma) if target_lemma else None
    )
    if target_signal is True:
        proof_candidate_closed = True
        if num_remaining == REMAINING_UNKNOWN:
            num_remaining = 0
    elif target_signal is False:
        # Target lemma is known and EC has NOT emitted its close signal.
        # Disregard any "No more goals" the legacy heuristic picked up
        # (those came from helper lemmas whose admit. qed. was processed
        # earlier in the same run). num_remaining was likely also misled
        # to 0; reset to UNKNOWN — we can't tell the real subgoal count
        # without trusting EC's last "Current goal" block, which is
        # absent here.
        proof_candidate_closed = False
        if num_remaining == 0:
            num_remaining = REMAINING_UNKNOWN
    else:
        # No target lemma context — fall back to legacy "No more goals"
        # heuristic. This path is correct for full-file proving (no
        # `-lemma` extraction) where the agent sequentially closes
        # whatever lemma is currently open.
        proof_candidate_closed = (
            num_remaining == 0
            or (
                num_remaining == REMAINING_UNKNOWN
                and latest_state_is_closed(raw_current)
            )
        )
        if proof_candidate_closed and num_remaining == REMAINING_UNKNOWN:
            num_remaining = 0
    return SessionState(
        session_dir=session_dir,
        current_path=current_path,
        previous_path=previous_path,
        has_current=True,
        raw_current=raw_current,
        active_output=active_output,
        active_goal_block=active_goal_block,
        num_remaining=num_remaining,
        proof_candidate_closed=proof_candidate_closed,
    )


def target_lemma_added(raw_text: str, target_name: str) -> bool:
    """True iff EC's ``+ added lemma: `<target_name>'`` line appears in
    ``raw_text``.

    EC prints this line after a ``qed.`` (or ``by``-shorthand) successfully
    closes a top-level lemma, with the name quoted in backtick-apostrophe
    style. It is the authoritative "this specific lemma is closed"
    signal — unlike ``No more goals`` (which can be the close of a
    SUBGOAL or a HELPER lemma earlier in the file), this only fires
    when EC fully accepted the named lemma's proof.
    """
    if not target_name:
        return False
    pattern = re.compile(
        r"\+\s+added\s+lemma:\s+`" + re.escape(target_name) + r"'",
    )
    return bool(pattern.search(raw_text))


def read_target_lemma_from_meta(session_dir: Path) -> str:
    """Read the target lemma name from ``session_meta.json`` so callers
    do not need to thread it through every read_session_state call.

    Returns the empty string when the file is missing, unparseable, or
    has no lemma field. The full-file (no ``-lemma``) path produces an
    empty string here, which correctly disables lemma-aware detection
    and reverts to the legacy heuristic.
    """
    meta_path = Path(session_dir) / "session_meta.json"
    if not meta_path.exists():
        return ""
    try:
        data = _json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(data.get("lemma") or "")


def extract_active_goal_output(raw_current: str, previous_path: Path | None) -> str:
    """Return the suffix of current output produced by the latest tactic."""
    if previous_path and previous_path.exists() and previous_path.stat().st_size > 0:
        prev_len = len(
            previous_path.read_text(
                encoding="utf-8", errors="replace",
            ).splitlines()
        )
        curr_lines = raw_current.splitlines()
        if prev_len < len(curr_lines):
            return "\n".join(curr_lines[prev_len:])
    return raw_current


def extract_active_goal_block(raw_text: str) -> tuple[str, int]:
    """Extract the active goal block and remaining count from EC output.

    EC's `-emacs` mode prints state above the prompt. A closed proof may look
    like `No more goals`, then one prompt, then `+ added lemma`, then another
    prompt. This function treats that as a closed active state instead of an
    indeterminate empty tail.
    """
    lines = raw_text.splitlines()
    check_lines: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        m = _CHECK_PROMPT_RE.search(line)
        if m:
            check_lines.append((int(m.group(1)), i))

    if not check_lines:
        if latest_state_is_closed(raw_text):
            return "No more goals", 0
        return "", REMAINING_UNKNOWN

    _, highest_idx = max(check_lines, key=lambda x: x[0])

    goal_start = highest_idx
    for i in range(highest_idx, -1, -1):
        if _is_current_goal_marker(lines[i]):
            goal_start = i
            break

    if goal_start == highest_idx and not _is_current_goal_marker(lines[goal_start]):
        for i in range(highest_idx + 1, len(lines)):
            if _is_current_goal_marker(lines[i]):
                goal_start = i
                break

    if goal_start > highest_idx:
        block = "\n".join(lines[goal_start:])
    else:
        block = "\n".join(lines[goal_start:highest_idx + 1])

    if goal_start == highest_idx:
        for i in range(highest_idx - 1, -1, -1):
            if "No more goals" in lines[i]:
                block = "No more goals\n" + block
                break

    n_remaining = REMAINING_UNKNOWN
    scan_end = -1
    for j in range(highest_idx - 1, -1, -1):
        if _CHECK_PROMPT_RE.search(lines[j]):
            scan_end = j
            break
    for i in range(highest_idx - 1, scan_end, -1):
        marker_remaining = _state_marker_remaining(lines[i])
        if marker_remaining is not None:
            n_remaining = marker_remaining
            break

    if (
        n_remaining == REMAINING_UNKNOWN
        and goal_start > highest_idx
    ):
        # Some EC start states print the prompt before the first goal block:
        #   [13|check]>
        #   Current goal
        #   ...
        # There is no later prompt to scan backwards from, but the visible
        # block is still authoritative. Preserve the parenthesized count when
        # EC printed one instead of collapsing every prompt-before-goal block
        # to a single remaining goal.
        for line in lines[goal_start:]:
            marker_remaining = _state_marker_remaining(line)
            if marker_remaining is not None:
                n_remaining = marker_remaining
                break

    if n_remaining == REMAINING_UNKNOWN and goal_start == highest_idx:
        for i in range(highest_idx - 1, -1, -1):
            if _NO_MORE_GOALS_MARKER_RE.match(lines[i]):
                n_remaining = 0
                break

    return block, n_remaining


def _state_marker_remaining(line: str) -> int | None:
    """Return the EC goal count encoded by a state-marker line.

    Keep this intentionally stricter than a generic ``remaining: N`` search:
    session output can include diagnostics or JSON snippets mentioning
    ``remaining`` after the goal header. Only EasyCrypt's own state markers are
    authoritative for the current proof state's goal count.
    """
    if _NO_MORE_GOALS_MARKER_RE.match(line):
        return 0
    m = _CURRENT_GOAL_MARKER_RE.match(line)
    if not m:
        return None
    return int(m.group(1)) if m.group(1) is not None else 1


def _is_current_goal_marker(line: str) -> bool:
    return _CURRENT_GOAL_MARKER_RE.match(line) is not None


def latest_state_section(raw_text: str) -> str:
    """Return the prompt-delimited section containing the latest state."""
    prompts = list(_ANY_PROMPT_RE.finditer(raw_text))
    if not prompts:
        return raw_text[-500:]
    last = prompts[-1]
    if len(prompts) >= 2:
        return raw_text[prompts[-2].end():last.start()]
    return raw_text[:last.start()]


def infer_goal_count(raw_text: str) -> tuple[int, bool]:
    """Return `(remaining_goals, has_no_more_goals)` for a raw EC state."""
    _, remaining = extract_active_goal_block(raw_text)
    if remaining != REMAINING_UNKNOWN:
        return remaining, remaining == 0

    section = latest_state_section(raw_text)
    if "No more goals" in section:
        return 0, True
    m = re.search(r"Current goal(?: \(remaining: (\d+)\))?", section)
    if m:
        return int(m.group(1)) if m.group(1) else 1, False
    if latest_state_is_closed(raw_text):
        return 0, True
    return REMAINING_UNKNOWN, False


def latest_state_is_closed(raw_text: str) -> bool:
    """Return True when the latest visible EC state says no goals remain."""
    lines = raw_text.splitlines()
    prompt_lines: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        m = _ANY_PROMPT_RE.search(line)
        if m:
            num_match = re.search(r"\[(\d+)\|", m.group(0))
            prompt_lines.append((int(num_match.group(1)) if num_match else i, i))

    if prompt_lines:
        _, highest_idx = max(prompt_lines, key=lambda x: x[0])
        scan = range(highest_idx - 1, -1, -1)
    else:
        scan = range(len(lines) - 1, -1, -1)

    for i in scan:
        line = lines[i]
        if "No more goals" in line:
            return True
        if "Current goal" in line:
            return False
    return False


def extract_goal_body(raw_text: str) -> str:
    """Extract the active goal body and strip EC prompt markers.

    A "Current goal" header at line index 0 is the NORMAL shape for a
    compressed display (current.out/prev.out start with it), so it must count
    as found: gating on ``start > 0`` silently degraded those inputs to the
    last-80-lines fallback, and ``detect_no_progress`` then compared only the
    tails of the two displays — blind to any change in the hypotheses or the
    upper goal body. That false "text-equal" auto-reverted a real
    hypothesis rewrite (`rewrite /inv /inv_cpa in H.`) during bootstrap
    prefix replay (step4_1 r2 respawn, 2026-06-09), silently dropping a
    parent-committed step from the child session's history.
    """
    lines = raw_text.splitlines()
    start = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "Current goal" or stripped.startswith("Current goal (remaining:"):
            start = i
    if start >= 0:
        goal_text = "\n".join(lines[start:])
    else:
        goal_text = "\n".join(lines[-80:])
    return _ANY_PROMPT_RE.sub("", goal_text)
