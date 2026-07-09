#!/usr/bin/env python3
"""Bounded swap search: systematically find valid swap sequences.

Instead of the prover guessing swap{1}/swap{2} numbers by trial and error,
this tool uses the goal parser to compute candidates and tries each one
against the actual EasyCrypt session, rolling back failures automatically.

Usage (via session_cli):
    python3 core/easycrypt/session_cli.py -d .ec_session -swap-search

Usage (standalone, for testing):
    python3 core/easycrypt/swap_search.py .ec_session_dir
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SwapSearchResult:
    success: bool
    accepted_swaps: list[str] = field(default_factory=list)
    remaining_misaligned: int = 0
    attempts: int = 0
    error: str = ""
    # Structured hint for special cases (e.g., eager goals)
    hint: str = ""
    hint_tactics: list[str] = field(default_factory=list)


def _all_deterministic_misaligned(
    misaligned: list[dict],
    left_stmts: list[dict],
    right_stmts: list[dict],
) -> bool:
    """Return True if every remaining misaligned match involves ASSIGN on both sides.

    Deterministic assignments ('<-') don't need positional alignment because
    'wp' consumes trailing assigns from both sides regardless of relative order.
    Only SAMPLE ('<$') and CALL ('<@') statements require explicit swap alignment.
    An empty list returns False (vacuously not applicable — already aligned).
    """
    if not misaligned:
        return False
    left_type_map = {s["pos"]: s["type"] for s in left_stmts}
    right_type_map = {s["pos"]: s["type"] for s in right_stmts}
    for m in misaligned:
        left_type = left_type_map.get(m["left_pos"], "")
        right_type = right_type_map.get(m["right_pos"], "")
        if left_type in ("SAMPLE", "CALL") or right_type in ("SAMPLE", "CALL"):
            return False
    return True


def search_swaps(
    session_dir: str,
    max_attempts: int = 20,
) -> SwapSearchResult:
    """Search for a valid swap alignment sequence.

    Reads the current goal from the session, generates swap candidates
    using the goal parser, and tries each one. Rolls back failures.

    Args:
        session_dir: path to session_cli session directory
        max_attempts: maximum individual swap attempts before giving up

    Returns:
        SwapSearchResult with accepted swaps and status
    """
    from core.easycrypt.analysis.ec_goal_parser import parse_goal, classify_goal
    from core.easycrypt.session_api import open_session
    from core.easycrypt.session_projection import read_proof_state_projection
    from core.easycrypt.session_state import extract_goal_body

    session = open_session(Path(session_dir))
    result = SwapSearchResult(success=False)

    # Read current goal
    if not session.curr.exists():
        result.error = "No current goal state. Run -start and -next first."
        return result

    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="swap-search",
    )
    if projection.status in ("candidate_closed", "verified"):
        result.success = True
        result.remaining_misaligned = 0
        result.hint = "Proof is already complete; no swap alignment needed."
        return result
    if projection.consistency.errors:
        result.error = (
            "Inconsistent proof state; refusing swap search: "
            + "; ".join(projection.consistency.errors[:3])
        )
        return result

    state = session.read_state()
    raw = state.raw_for_goal_tools
    goal_type = classify_goal(raw)

    if goal_type == "eager":
        # Eager goals have distinct syntax: eager[ R(); P ~ Q, R() ]
        # swap-search cannot parse them as two-column programs.
        # Detect this case and suggest 'eager proc' first, then re-run.
        info = parse_goal(raw)
        left_stmt = info.eager_left_stmt or "?"
        left_proc = info.eager_left_proc or "?"
        right_proc = info.eager_right_proc or "?"
        right_stmt = info.eager_right_stmt or "?"

        hint_lines = [
            "EAGER GOAL DETECTED — swap-search cannot align eager obligations directly.",
            f"  Eager judgment: {left_stmt} , {left_proc} ~ {right_proc} , {right_stmt}",
            "  Step 1: Apply 'eager proc.' to convert the obligation to a pRHL goal.",
            "  Step 2: Re-run -swap-search on the resulting pRHL goal for swap alignment.",
            "  Note: If 'eager proc' fails, try 'eager proc; wp.' or inspect the",
            "        obligation manually — the programs may need an rcondf/rnd coupling",
            "        argument rather than pure swap alignment.",
        ]
        hint = "\n".join(hint_lines)
        result.error = hint
        result.hint = hint
        result.hint_tactics = [
            "eager proc.",
            "eager proc; wp.",
            "eager proc; inline *; wp.",
            "eager proc; sim.",
        ]
        return result

    if goal_type != "pRHL":
        result.error = (
            f"Current goal is '{goal_type}', not pRHL. "
            f"Swap search only works on pRHL (two-column) goals. "
            f"Use 'proc; inline *' first to get a pRHL listing."
        )
        return result

    # Parse the goal to get matches and dependency info
    info = parse_goal(raw)
    if not info.matches:
        result.error = "No statement matches found. Nothing to align."
        return result

    # Check which matches are already aligned
    misaligned = [
        m for m in info.matches
        if m["left_pos"] != m["right_pos"]
    ]

    if not misaligned:
        result.success = True
        result.remaining_misaligned = 0
        return result

    # If all misaligned pairs are deterministic assignments, wp handles them.
    if _all_deterministic_misaligned(misaligned, info.left_stmts, info.right_stmts):
        result.success = True
        result.remaining_misaligned = len(misaligned)
        result.hint = (
            f"{len(misaligned)} misaligned pair(s) are deterministic assignments "
            f"(ASSIGN type) — wp handles these without swap alignment."
        )
        result.hint_tactics = ["wp.", "auto => />."]
        return result

    result.remaining_misaligned = len(misaligned)

    # Generate candidate swaps from the parser's suggestions
    candidates = info.safe_swaps[:]  # Start with parser-computed swaps

    # Also generate additional candidates from misaligned matches
    # (parser may have skipped some due to dependency analysis)
    for m in misaligned:
        left_pos = m["left_pos"]
        right_pos = m["right_pos"]
        offset = right_pos - left_pos
        if offset != 0:
            # Try both sides
            candidates.append(f"swap{{1}} {left_pos} {offset}.")
            candidates.append(f"swap{{2}} {right_pos} {-offset}.")

    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        # Normalize: strip comments and extra spaces
        normalized = re.sub(r"\s*\(\*.*?\*\)", "", c).strip()
        if normalized not in seen:
            seen.add(normalized)
            unique_candidates.append(normalized)

    # Try each candidate
    for candidate in unique_candidates:
        if result.attempts >= max_attempts:
            break

        result.attempts += 1
        success, error_msg = _try_swap(session, candidate)

        if success:
            result.accepted_swaps.append(candidate)

            # Re-parse to check if fully aligned now
            state = session.read_state()
            raw = state.raw_for_goal_tools
            new_type = classify_goal(raw)

            if new_type != "pRHL":
                # Goal type changed (e.g., swap closed a subgoal or moved to wp territory)
                result.success = True
                result.remaining_misaligned = 0
                return result

            new_info = parse_goal(raw)
            new_misaligned = [
                m for m in new_info.matches
                if m["left_pos"] != m["right_pos"]
            ]
            result.remaining_misaligned = len(new_misaligned)

            if not new_misaligned:
                result.success = True
                return result

            # If only deterministic assignments remain, wp handles them.
            if _all_deterministic_misaligned(
                new_misaligned, new_info.left_stmts, new_info.right_stmts
            ):
                result.success = True
                result.hint = (
                    f"{len(new_misaligned)} remaining misaligned pair(s) are deterministic "
                    f"assignments (ASSIGN type) — wp handles these without swap alignment."
                )
                result.hint_tactics = ["wp.", "auto => />."]
                return result

            # Generate new candidates from updated state
            for m in new_misaligned:
                lp, rp = m["left_pos"], m["right_pos"]
                off = rp - lp
                if off != 0:
                    for new_c in [f"swap{{1}} {lp} {off}.", f"swap{{2}} {rp} {-off}."]:
                        norm = re.sub(r"\s*\(\*.*?\*\)", "", new_c).strip()
                        if norm not in seen:
                            seen.add(norm)
                            unique_candidates.append(norm)
        else:
            # Try to adjust based on EC error feedback
            adjusted = _adjust_from_error(candidate, error_msg)
            if adjusted and adjusted not in seen:
                seen.add(adjusted)
                unique_candidates.append(adjusted)

    # Final check: maybe only deterministic assignments remain after partial progress.
    if not result.success and result.accepted_swaps:
        state = session.read_state()
        raw = state.raw_for_goal_tools
        if classify_goal(raw) == "pRHL":
            final_info = parse_goal(raw)
            final_misaligned = [
                m for m in final_info.matches
                if m["left_pos"] != m["right_pos"]
            ]
            if _all_deterministic_misaligned(
                final_misaligned, final_info.left_stmts, final_info.right_stmts
            ):
                result.success = True
                result.remaining_misaligned = len(final_misaligned)
                result.hint = (
                    f"{len(final_misaligned)} remaining misaligned pair(s) are deterministic "
                    f"assignments (ASSIGN type) — wp handles these without swap alignment."
                )
                result.hint_tactics = ["wp.", "auto => />."]

    return result


def _try_swap(session, tactic: str) -> tuple[bool, str]:
    """Try a swap tactic. Returns (success, error_message).

    On failure, auto-rolls back the tactic.
    """
    # Capture state before
    prev_text = ""
    if session.curr.exists():
        prev_state = session.read_state()
        prev_text = prev_state.raw_current
        prev_goal_text = prev_state.raw_for_goal_tools
    else:
        prev_goal_text = ""

    error_re = re.compile(r"^\s*\[(error|critical|fatal)")
    prev_errors = set(
        l for l in prev_text.split("\n") if error_re.match(l)
    )

    # Apply the tactic
    session.append_block(tactic, deltas_only=False)

    # Check for errors
    curr_state = session.read_state()
    curr_text = curr_state.raw_current
    curr_errors = set(
        l for l in curr_text.split("\n") if error_re.match(l)
    )
    new_errors = curr_errors - prev_errors

    # Also check for stale (no change = tactic had no effect). Use the
    # shared session_state goal-body extractor so prompt scanning and
    # closed-proof detection stay consistent with the rest of session_cli.
    prev_goal = extract_goal_body(prev_goal_text) if prev_goal_text else ""
    curr_goal = extract_goal_body(curr_state.raw_for_goal_tools)
    no_more = curr_state.proof_candidate_closed
    stale = (curr_goal == prev_goal) and not no_more and not new_errors

    if new_errors or stale:
        # Rollback
        session.step_up()
        error_msg = ""
        if new_errors:
            error_msg = list(new_errors)[0]
        elif stale:
            error_msg = "tactic had no effect"
        return False, error_msg

    return True, ""


def _adjust_from_error(tactic: str, error_msg: str) -> Optional[str]:
    """Try to adjust a swap tactic based on EC's error message.

    EC sometimes says "too large by N" or gives offset hints.
    """
    if not error_msg:
        return None

    # Parse the original tactic
    m = re.match(r"swap\{(\d)\}\s+(\d+)\s+(-?\d+)\.", tactic)
    if not m:
        return None

    side = m.group(1)
    pos = int(m.group(2))
    offset = int(m.group(3))

    # Check for "too large" / "too small" hints
    too_large = re.search(r"too large by (\d+)", error_msg)
    too_small = re.search(r"too small by (\d+)", error_msg)

    if too_large:
        correction = int(too_large.group(1))
        new_offset = offset - correction if offset > 0 else offset + correction
        if new_offset != 0:
            return f"swap{{{side}}} {pos} {new_offset}."

    if too_small:
        correction = int(too_small.group(1))
        new_offset = offset + correction if offset > 0 else offset - correction
        if new_offset != 0:
            return f"swap{{{side}}} {pos} {new_offset}."

    # Try smaller offset (binary search style)
    if abs(offset) > 1:
        half = offset // 2
        if half != 0:
            return f"swap{{{side}}} {pos} {half}."

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 swap_search.py <session_dir> [--max N]")
        return 1

    session_dir = sys.argv[1]
    max_attempts = 20
    if "--max" in sys.argv:
        idx = sys.argv.index("--max")
        if idx + 1 < len(sys.argv):
            max_attempts = int(sys.argv[idx + 1])

    result = search_swaps(session_dir, max_attempts=max_attempts)

    if result.success:
        print(f"[swap-search] Aligned in {result.attempts} attempts:")
        for s in result.accepted_swaps:
            print(f"  {s}")
        if result.hint:
            print(f"  NOTE: {result.hint}")
            for t in result.hint_tactics:
                print(f"  Next tactic: {t}")
    else:
        print(f"[swap-search] Could not fully align after {result.attempts} attempts.")
        if result.accepted_swaps:
            print(f"  Partial progress ({len(result.accepted_swaps)} swaps accepted):")
            for s in result.accepted_swaps:
                print(f"    {s}")
        print(f"  {result.remaining_misaligned} pairs still misaligned.")
        if result.error:
            print(f"  {result.error}")

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
