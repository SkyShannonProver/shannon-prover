"""Tactic extraction, proof write-back, and EasyCrypt verification.

Extracted verbatim from workflow/agents/prover.py: everything that turns a
finished (or interrupted) prover session into a verified proof in the target
.ec file — session-history extraction, lemma-scoped verification, admit
scanning, failing-tactic pruning, and the final write-and-verify pass.
prover.py re-exports every name so external callers and tests are unchanged.
"""
from __future__ import annotations

import logging
import time
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional
from core.easycrypt.committed_history import (
    closed_history_tactics,
    read_committed_tactics,
    split_trailing_qed,
)
from workflow.agents.ec_services import (
    _claude_scratch_path,
    _ensure_why3server,
    _get_opam_env,
    _is_why3server_responsive,
)

logger = logging.getLogger("workflow.agents.prover")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_EC_SPINNER_RE = re.compile(r'^\[[-\\|/]\]\s+\[\d+\]\s+\d+\.\d+%')
_ADMIT_TOKEN_RE = re.compile(r"(?<!\w)admit\.", re.IGNORECASE)


def _extract_tactics_from_session(
    lemma_name: str,
    parallelism: int,
    output_text: str,
    preferred_session_dir: str | Path | None = None,
    *,
    scan_project_sessions: bool = True,
) -> list[str]:
    """Extract the accepted tactic list from the prover session.

    Prefers manager-owned session history files (exact per-tactic lines from
    the EC session — ground truth). Falls back to parsing the "PROOF TACTICS:"
    marker in the prover's output text (which may compress multiple tactics
    onto one line, causing poor formatting when written to the .ec file).

    ``scan_project_sessions`` gates the fallback that globs sibling
    ``.ec_session_prover_*`` dirs under ``_PROJECT_ROOT``; tests disable it so
    they stay hermetic against leftover session dirs in the working tree (see
    the matching flag on ``_extract_partial_tactics_from_session``).
    """
    # Primary: session history files (one tactic per line, ground truth)
    if preferred_session_dir:
        session_dir = Path(preferred_session_dir)
        tactics = closed_history_tactics(session_dir)
        if tactics:
            return tactics

    # Check both racing-mode names (prover_LEMMA_N) and tree-mode names (prover_tree_N_M)
    if scan_project_sessions:
        safe_name = lemma_name.replace("'", "_prime")
        session_patterns = [
            f".ec_session_prover_{safe_name}_{i}" for i in range(max(1, parallelism))
        ]
        # Also glob for tree-mode sessions
        for p in sorted(_PROJECT_ROOT.glob(".ec_session_prover_tree_*")):
            if p.name not in session_patterns:
                session_patterns.append(p.name)

        for dirname in session_patterns:
            session_dir = _PROJECT_ROOT / dirname if "/" not in dirname else Path(dirname)
            tactics = closed_history_tactics(session_dir)
            if tactics:
                return tactics

    # Fallback: parse output text for "PROOF TACTICS:" marker
    # The prover may output tactics in markdown format; parsing is best-effort.
    if output_text:
        m = re.search(
            r"\*{0,2}PROOF TACTICS:?\*{0,2}\s*(.+?)(?:\n\n|$)",
            output_text,
            re.DOTALL,
        )
        if m:
            raw = m.group(1).strip()
            # Strip markdown bold markers and backticks wrapping the whole block
            raw = re.sub(r"^\*{1,2}\s*", "", raw)
            raw = raw.strip("`").strip()
            tactics = []
            for line in raw.splitlines():
                line = re.sub(r"^\d+\.\s*", "", line.strip())  # remove "1. " prefix
                line = line.strip("`").strip()
                # Strip residual markdown bold
                line = re.sub(r"^\*{1,2}\s*", "", line)
                line = re.sub(r"\s*\*{1,2}$", "", line)
                # Keep indented tactic lines (+ prefix for subgoal bullets)
                if line.startswith("+"):
                    line = line[1:].strip()
                if line and line.endswith("."):
                    tactics.append(line)
            # Split off trailing "qed." embedded in the last tactic
            # e.g. "proc; islossless. qed." → ["proc; islossless.", "qed."]
            if tactics:
                return split_trailing_qed(tactics)

    return []


def _extract_partial_tactics_from_session(
    lemma_name: str,
    parallelism: int,
    *,
    preferred_session_dir: str | Path | None = None,
    resume_capsules: list[str] | None = None,
    scan_project_sessions: bool = True,
) -> list[str]:
    """Return the best replayable prefix even when no ``qed.`` exists.

    This is reporting-only: callers must not mark the proof as proved from this
    result.  It lets eval reports show how far an interrupted or failed run got.
    """
    candidates: list[list[str]] = []
    if preferred_session_dir:
        candidates.append(read_committed_tactics(Path(preferred_session_dir)))

    if scan_project_sessions:
        safe_name = lemma_name.replace("'", "_prime")
        session_patterns = [
            f".ec_session_prover_{safe_name}_{i}" for i in range(max(1, parallelism))
        ]
        for p in sorted(_PROJECT_ROOT.glob(".ec_session_prover_tree_*")):
            if p.name not in session_patterns:
                session_patterns.append(p.name)
        for dirname in session_patterns:
            session_dir = _PROJECT_ROOT / dirname if "/" not in dirname else Path(dirname)
            candidates.append(read_committed_tactics(session_dir))

    for capsule in resume_capsules or []:
        path = Path(capsule)
        root = path if path.is_dir() else path.parent
        candidates.append(read_committed_tactics(root))

    candidates = [item for item in candidates if item]
    if not candidates:
        return []
    return max(candidates, key=len)


def _has_why3_error(stderr: str) -> bool:
    """Check if stderr contains a why3server connection error."""
    return "cannot start & connect to why3server" in stderr


def _distill_ec_stderr(stderr: str, max_lines: int = 20) -> str:
    """Keep significant lines from `easycrypt` stderr; drop progress spinners.

    EC writes a spinner frame per compile-unit to stderr (e.g.
    `[-] [0002] 1.6% (-1.0B / [frag -1.0B])`). Real diagnostics
    (`[critical] ... at line N: ...`, `[error-X-Y] ...`, `[warning] ...`)
    arrive AFTER the spinners, so a fixed-length prefix of stderr (what the
    caller used to log) shows only the spinner and hides the error.

    Prefer lines matching `[critical|error|warning` or `at line`; fall back
    to the non-spinner tail. Capped at `max_lines`.
    """
    kept: list[str] = []
    for line in stderr.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _EC_SPINNER_RE.match(stripped):
            continue
        kept.append(line.rstrip())
    important = [
        l for l in kept
        if re.search(r'\[(critical|error|warning)', l) or 'at line' in l
    ]
    chosen = important if important else kept
    return "\n".join(chosen[-max_lines:])


def _verify_ec_file(
    ec_path: Path,
    include_dir: str = "",
    extra_include_dirs: Optional[list] = None,
) -> tuple[bool, str]:
    """Run `easycrypt <file>` to verify the file compiles.

    Args:
        ec_path: file to verify.
        include_dir: user-supplied -I path (typically `easycrypt-src/theories`).
        extra_include_dirs: additional -I paths. Use this when verifying a
            temp file extracted from a source file that lives elsewhere — pass
            the source file's parent dir so its sibling .ec/.eca theories
            (e.g. ChaChaPoly's `ske.ec`, `indistinguishability.eca`) resolve.
            See `_verify_extracted_file` for the canonical call pattern.

    Returns (success, stderr) so the caller can inspect failure reasons.
    `stderr` is the raw stderr so call sites that look for specific markers
    (e.g. `_has_why3_error` scanning for 'cannot start & connect to why3server')
    still work. Only the log message is distilled.

    Recovery: a why3server connection error means the persistent socket
    has gone unresponsive mid-run (server died, was OOM-killed, etc.).
    The first failure triggers a forced ``_ensure_why3server(force_restart=
    True)`` and one retry. Without this, a single transient why3 hiccup
    fails the whole verification and the orchestrator rejects an
    otherwise-correct proof — observed on br93 eq_Game1_Game2 run
    (2026-05-03), where session_runtime had healthy smt() but the
    verify subprocess hit a stale socket inherited from prior sessions.
    """
    logger.info("Verifying %s with easycrypt...", ec_path)

    def _run(why3_socket: Optional[str]) -> tuple[bool, str]:
        env = _get_opam_env()
        cmd = ["easycrypt", "-timeout", "30"]
        if why3_socket and os.path.exists(why3_socket) \
                and _is_why3server_responsive(why3_socket):
            cmd.extend(["-server", why3_socket])
        if include_dir:
            cmd.extend(["-I", include_dir])
        for d in (extra_include_dirs or []):
            if d:
                cmd.extend(["-I", str(d)])
        cmd.append(str(ec_path))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
        if result.returncode == 0:
            return True, result.stderr
        return False, result.stderr

    try:
        ok, stderr = _run(os.environ.get("WHY3EC_SOCKET", "/tmp/why3ec.sock"))
        if ok:
            logger.info("Verification PASSED")
            return True, stderr
        if _has_why3_error(stderr):
            logger.warning(
                "why3server connection failed during verify; "
                "force-restarting and retrying once",
            )
            new_socket = _ensure_why3server(force_restart=True)
            if new_socket is not None:
                ok, stderr = _run(new_socket)
                if ok:
                    logger.info("Verification PASSED on retry")
                    return True, stderr
        logger.error(
            "Verification FAILED:\n%s", _distill_ec_stderr(stderr),
        )
        return False, stderr
    except Exception as e:
        logger.error("Verification error: %s", e)
        return False, str(e)


def _verify_extracted_file(
    temp_path: Path,
    source_ec_path: Path,
    include_dir: str = "",
) -> tuple[bool, str]:
    """Verify a temp file extracted from `source_ec_path`.

    Inherits include context from the source file's parent directory so
    sibling .ec/.eca theories (e.g. ChaChaPoly's `ske.ec`,
    `indistinguishability.eca`) resolve. EC's theory lookup walks the
    input file's own directory + `-I` paths; an extracted file living outside
    that tree has no sibling-theory access by default, and `require Ske` fails
    with "cannot locate theory `Ske`". Observed in step1 Run 8 prune-verify
    (2026-04-27) — the prune scratch file failed line 4 even though the proof
    body was correct, falling through to full-file verify.

    Use this whenever you write an extracted .ec file outside its source dir
    and need to verify it.
    """
    return _verify_ec_file(
        temp_path,
        include_dir=include_dir,
        extra_include_dirs=[source_ec_path.resolve().parent],
    )


def _verify_lemma_extracted(
    ec_path: Path, lemma_name: str, include_dir: str = "",
    decl_line: int | None = None,
) -> bool:
    """Verify a single lemma by extracting it into a standalone file.

    Uses lemma_extract with verify_proof=True: keeps the target lemma's
    proof intact, replaces all other proofs with admit., and cuts the file
    after the target's qed. This avoids SMT dependency issues from
    unrelated lemmas while verifying our proof.

    `decl_line` (0-based) pins extraction to a specific declaration when
    the lemma name is duplicated in the file.
    """
    logger.info("Falling back to extracted-lemma verification for %s", lemma_name)
    try:
        from core.easycrypt.lemma_extract import extract_lemma

        extracted = extract_lemma(ec_path, lemma_name, verify_proof=True,
                                  decl_line=decl_line)

        tmp_path = _claude_scratch_path(f"verify_{lemma_name}_extracted.ec")
        tmp_path.write_text(extracted, encoding="utf-8")

        ok, _ = _verify_extracted_file(tmp_path, ec_path, include_dir=include_dir)
        return ok
    except Exception as e:
        logger.error("Extracted-lemma verification error: %s", e)
        return False


def _candidate_gate_for_session(ec_session_dir: str | Path | None):
    """Validate that the EC session produced a real closed candidate."""
    try:
        from workflow.proof_acceptance import validate_candidate_event_contract
        return validate_candidate_event_contract(ec_session_dir)
    except Exception as e:
        logger.error("Candidate event-contract check crashed: %s", e)
        return None


def _acceptance_gate_for_session(ec_session_dir: str | Path | None):
    """Validate final event contract after offline verification emits status."""
    try:
        from workflow.proof_acceptance import validate_acceptance_event_contract
        return validate_acceptance_event_contract(ec_session_dir)
    except Exception as e:
        logger.error("Acceptance event-contract check crashed: %s", e)
        return None


def _emit_verification_status(
    ec_session_dir: str | Path | None,
    *,
    lemma_name: str,
    status: str,
    ec_path: Path,
    reason: str,
    **extra: object,
) -> bool:
    try:
        from workflow.proof_acceptance import emit_workflow_verification_event
        return emit_workflow_verification_event(
            ec_session_dir,
            lemma=lemma_name,
            status=status,
            verifier="easycrypt",
            file=str(ec_path.resolve()),
            reason=reason,
            **extra,
        )
    except Exception as e:
        logger.error("Could not emit verification event: %s", e)
        return False


def _resolve_lemma_decl_start(content: str, lemma_name: str) -> int | None:
    """Resolve the target declaration of `lemma_name` to a byte offset.

    When multiple lemmas share the same name (e.g., one inside a section
    and one outside), prefer the one that needs proving (has admit or
    empty proof body) over an already-proved one.

    The offset is a STABLE declaration identity: resolve it ONCE per
    write-back cycle and pass it to `_find_proof_block`,
    `_prune_failing_tactics`, and `_proof_body_has_admit` so they all
    target the same declaration. Without this, the prefer-needs-proving
    heuristic re-runs after the write-back fills one declaration and
    resolves to the OTHER still-admitted duplicate, whose `admit` then
    reverts a genuinely proved lemma (xorK1 in ChaChaPoly/chacha_poly.ec,
    2026-06-11). Offsets stay valid across the write-back because the
    replacement happens strictly after the declaration start.
    """
    from core.easycrypt.lemma_decls import lemma_decl_matches

    all_matches = lemma_decl_matches(content, lemma_name)
    if not all_matches:
        return None

    def _needs_proving(match):
        """Check if this lemma occurrence has admit or empty proof."""
        after = content[match.end():match.end() + 500]
        return bool(re.search(r'\badmit\b', after[:300])) or \
               bool(re.search(r'proof\.\s*(?:\(\*.*?\*\)\s*)?qed\.', after[:300], re.DOTALL))

    # Prefer the match that needs proving; fall back to first match
    lemma_match = next((m for m in all_matches if _needs_proving(m)), all_matches[0])
    return lemma_match.start()


def _find_proof_block(
    content: str, lemma_name: str, decl_start: int | None = None,
) -> tuple[int, int] | None:
    """Find the byte range of a lemma's proof block (proof. ... qed. or admit.).

    Returns (start, end) positions in content, or None if not found.
    Uses line-by-line scanning to avoid regex issues with dots in expressions
    like P(F).main().

    `decl_start` pins the lookup to the declaration at that byte offset (as
    returned by `_resolve_lemma_decl_start`); if no declaration of
    `lemma_name` starts there, returns None rather than silently targeting
    a different same-name declaration. When omitted, the
    prefer-needs-proving heuristic picks the declaration.
    """
    from core.easycrypt.lemma_decls import lemma_decl_matches

    if decl_start is None:
        decl_start = _resolve_lemma_decl_start(content, lemma_name)
        if decl_start is None:
            return None
    else:
        all_matches = lemma_decl_matches(content, lemma_name)
        if not any(m.start() == decl_start for m in all_matches):
            return None

    rest = content[decl_start:]

    # Bound search: stop at next top-level declaration to avoid matching
    # a different lemma's proof block.
    # Match only top-level declarations (at most 2 spaces indent).
    # Deeper indentation (e.g., "    equiv [D4.sample ...]" inside a type) is NOT a new decl.
    next_decl = re.search(
        r'^[ ]{0,2}(?:local\s+)?(?:lemma|theorem|axiom|op\s|type\s|module\s|clone\s|section\b|end\s+section)',
        rest[1:],  # skip current lemma
        re.MULTILINE,
    )
    if next_decl:
        rest = rest[:1 + next_decl.start()]

    # Find 'proof.' on its own line (possibly indented, possibly with trailing comment)
    proof_match = re.search(r'^([ \t]*)proof\..*$', rest, re.MULTILINE)
    if proof_match:
        # Find matching qed.
        after_proof = rest[proof_match.end():]
        qed_match = re.search(r'^[ \t]*qed\.', after_proof, re.MULTILINE)
        if qed_match:
            abs_start = decl_start + proof_match.start()
            abs_end = decl_start + proof_match.end() + qed_match.end()
            return abs_start, abs_end

    # No proof./qed. — look for standalone admit.
    admit_match = re.search(r'^[ \t]*admit\.[ \t]*$', rest, re.MULTILINE)
    if admit_match:
        abs_start = decl_start + admit_match.start()
        abs_end = decl_start + admit_match.end()
        return abs_start, abs_end

    return None


def _extract_prover_notes(output_text: str) -> str:
    """Extract the PROVER NOTES section from the prover's output (legacy).

    Returns the notes text, or empty string if not found.
    """
    if not output_text:
        return ""
    m = re.search(
        r"\*{0,2}PROVER NOTES:?\*{0,2}\s*(.+?)(?:\n\n(?:##|\*\*)|$)",
        output_text,
        re.DOTALL,
    )
    if m:
        notes = m.group(1).strip()
        notes = re.sub(r"^\*{1,2}\s*", "", notes)
        notes = re.sub(r"\s*\*{1,2}$", "", notes)
        return notes[:3000]
    return ""


def _extract_prover_report(output_text: str) -> dict:
    """Extract the structured PROVER REPORT JSON from the prover's output.

    Returns the parsed dict, or empty dict if not found or invalid.
    Expected keys: suggestions, open_questions, discoveries.
    """
    if not output_text:
        return {}

    # Look for PROVER REPORT: followed by a JSON block (possibly in markdown fences)
    m = re.search(
        r"\*{0,2}PROVER REPORT:?\*{0,2}\s*(?:```json\s*)?\{",
        output_text,
        re.DOTALL,
    )
    if not m:
        return {}

    # Find the start of the JSON object
    json_start = output_text.index("{", m.start())

    # Find matching closing brace (handle nested braces)
    depth = 0
    for i in range(json_start, len(output_text)):
        if output_text[i] == "{":
            depth += 1
        elif output_text[i] == "}":
            depth -= 1
            if depth == 0:
                json_text = output_text[json_start:i + 1]
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    logger.warning("PROVER REPORT JSON parse failed")
                    return {}
    return {}


def _strip_comments_for_admit_check(text: str) -> str:
    """Remove `(* ... *)` comments (nested) so admit checks can't be fooled.

    We do not care about string literals — EasyCrypt doesn't allow `admit.`
    inside strings in practice, and keyword-checks are case-sensitive.
    """
    out: list[str] = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        if i + 1 < n and text[i] == "(" and text[i + 1] == "*":
            depth += 1
            i += 2
            continue
        if depth > 0 and i + 1 < n and text[i] == "*" and text[i + 1] == ")":
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(text[i])
        i += 1
    return "".join(out)


def _tactics_contain_admit(tactics: list[str]) -> bool:
    """Return True if any tactic in `tactics` is (or contains) a bare admit.

    Also catches `admit` without a trailing period (some provers write it
    that way when followed by another tactic).
    """
    for tac in tactics:
        scrubbed = _strip_comments_for_admit_check(tac)
        stripped = scrubbed.strip().lower().rstrip(".").strip()
        if stripped == "admit":
            return True
        if _ADMIT_TOKEN_RE.search(scrubbed):
            return True
    return False


def _proof_body_has_admit(
    content: str, lemma_name: str, decl_start: int | None = None,
) -> bool:
    """Return True if the `lemma_name`'s proof block contains `admit.`.

    Scans the proof. ... qed. block after the lemma declaration, strips
    comments, and looks for a bare `admit` at word boundary. Used as a
    post-verify safety net — EC accepts admit as a closer, but we don't.

    Pass the `decl_start` the write-back targeted so this checks the SAME
    declaration that was just filled — without it, a same-name duplicate
    that is still admitted wins the prefer-needs-proving heuristic and
    this check reverts a genuinely proved lemma.
    """
    block = _find_proof_block(content, lemma_name, decl_start=decl_start)
    if block is None:
        return False
    start, end = block
    body = content[start:end]
    scrubbed = _strip_comments_for_admit_check(body)
    return bool(_ADMIT_TOKEN_RE.search(scrubbed))


def _prune_failing_tactics(
    ec_path: Path,
    lemma_name: str,
    tactics: list[str],
    include_dir: str = "",
    max_prunes: int = 5,
    decl_start: int | None = None,
) -> list[str]:
    """Defense-in-depth: before writing the final proof, replay the extracted
    tactic list through EC in an isolated scratch file. If it fails, parse the
    error line, drop the offending tactic, and retry up to `max_prunes` times.

    Rationale: the session tracks which tactics EC accepted, but it can still
    emit tactics that fail under strict end-to-end replay (e.g. a `rewrite`
    whose precondition isn't matched produces "[critical] nothing to rewrite"
    on replay even though the session treated it as a NO_PROGRESS no-op).
    Auto-rollback in session_cli catches most of these up-front, but this
    pruning pass is the safety net if anything slips through.

    Returns the pruned tactic list (possibly unchanged). Does NOT modify
    `ec_path` — writing happens in `_write_and_verify_proof`.
    """
    if not tactics:
        return tactics

    original_content = ec_path.read_text(encoding="utf-8")
    block = _find_proof_block(original_content, lemma_name, decl_start=decl_start)
    if block is None:
        return tactics
    # Pin extraction to the same declaration (its line is stable: the
    # candidate proof text is spliced in strictly after the declaration).
    decl_line = (
        original_content.count("\n", 0, decl_start)
        if decl_start is not None else None
    )

    current_tactics = list(tactics)
    pruned_count = 0

    for attempt in range(max_prunes):
        # Write scratch file with current tactic list
        proof_text = _build_proof_text(original_content[block[0]:block[1]], current_tactics)
        scratch_content = original_content[:block[0]] + proof_text + original_content[block[1]:]
        scratch_path = _claude_scratch_path(f"prune_{lemma_name}.ec")
        scratch_path.write_text(scratch_content, encoding="utf-8")

        # Extract just the target lemma to isolate from other lemmas' timeouts
        try:
            from core.easycrypt.lemma_extract import extract_lemma
            extracted = extract_lemma(scratch_path, lemma_name, verify_proof=True,
                                      decl_line=decl_line)
            verify_path = _claude_scratch_path(f"prune_verify_{lemma_name}.ec")
            verify_path.write_text(extracted, encoding="utf-8")
        except Exception as e:
            logger.warning("prune: lemma_extract failed (%s); skipping pruning", e)
            return tactics

        ok, stderr = _verify_extracted_file(verify_path, ec_path, include_dir=include_dir)
        if ok:
            if pruned_count > 0:
                logger.info("prune: pruned %d ghost tactic(s); scratch verifies clean", pruned_count)
            return current_tactics

        # Parse first error line number from stderr
        fail_line = _parse_ec_error_line(stderr, str(verify_path))
        if fail_line is None:
            logger.info("prune: could not parse error line; stopping pruning")
            return current_tactics

        # Map file line → tactic index (proof block's tactics are "  tac" per line)
        tactic_idx = _scratch_line_to_tactic_idx(verify_path.read_text(), fail_line, current_tactics)
        if tactic_idx is None or tactic_idx >= len(current_tactics):
            logger.info("prune: failing line %d doesn't map to a tactic; stopping", fail_line)
            return current_tactics

        dropped = current_tactics.pop(tactic_idx)
        pruned_count += 1
        logger.info("prune: dropped tactic[%d] %r (line %d: %s)",
                    tactic_idx, dropped[:60], fail_line, _first_err_msg(stderr))

    logger.info("prune: hit max_prunes=%d; returning current list", max_prunes)
    return current_tactics


def _build_proof_text(old_block: str, tactics: list[str]) -> str:
    """Format a proof block with the given tactics, preserving the COMPLETE THIS comment."""
    proof_tactics = [t for t in tactics if t.strip().lower().rstrip(".").strip() != "qed"]
    comment_match = re.search(r'(\(\*.*?COMPLETE\s+THIS.*?\*\))', old_block, re.DOTALL)
    comment_line = (comment_match.group(1) + "\n") if comment_match else ""
    return "proof.\n" + comment_line + "\n".join(f"  {t}" for t in proof_tactics) + "\nqed."


def _parse_ec_error_line(stderr: str, file_path: str) -> int | None:
    """Parse EC error output for the failing line number.

    Matches patterns like:
      [critical] [/path/to/file.ec: line 74 (9-26)] nothing to rewrite
      [error-3-0] [/path/to/file.ec: line 12 (5-18)] ...
    """
    path_escaped = re.escape(file_path)
    m = re.search(rf"\[(?:error|critical|fatal)[^\]]*\]\s*\[{path_escaped}:\s*line\s+(\d+)", stderr)
    if m:
        return int(m.group(1))
    # Fallback: any [severity] [*: line N] — takes the first match
    m = re.search(r"\[(?:error|critical|fatal)[^\]]*\]\s*\[[^:]+:\s*line\s+(\d+)", stderr)
    if m:
        return int(m.group(1))
    return None


def _first_err_msg(stderr: str) -> str:
    """Extract a short snippet of the first error message for logging."""
    m = re.search(r"\[(?:error|critical|fatal)[^\]]*\][^\n]{0,100}", stderr)
    return (m.group(0).strip() if m else stderr.strip())[:120]


def _scratch_line_to_tactic_idx(
    scratch_content: str, fail_line: int, tactics: list[str]
) -> int | None:
    """Map a scratch-file line number back to a tactic index.

    Proof block is formatted as:
        proof.
        (* COMPLETE THIS ... *)   ← optional
          tactic_0
          tactic_1
          ...
        qed.
    """
    lines = scratch_content.splitlines()
    if fail_line < 1 or fail_line > len(lines):
        return None
    # Walk up: find the nearest preceding "proof." and count tactic lines until fail_line
    proof_idx = None
    for i in range(fail_line - 1, -1, -1):
        if lines[i].strip() == "proof.":
            proof_idx = i
            break
    if proof_idx is None:
        return None
    tac_idx = 0
    for i in range(proof_idx + 1, fail_line):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("(*"):
            continue
        tac_idx += 1
    return tac_idx


def _write_and_verify_proof(
    ec_path: Path,
    lemma_name: str,
    tactics: list[str],
    include_dir: str = "",
    session_proved: bool = False,
    ec_session_dir: str | Path | None = None,
) -> bool:
    """Write proof tactics into the .ec file (replacing admit) and verify.

    Args:
        session_proved: True if the EC session reported that the proof
            candidate closed. This is useful progress signal, but final
            acceptance still requires offline verification.

    Returns True if easycrypt verification passes. Reverts on failure.
    """
    content = ec_path.read_text(encoding="utf-8")

    # Normalize a compound closer ("TAC. qed." committed as one step) into
    # a separate standalone "qed." entry. The proof-block builder below
    # filters standalone qed lines and appends its own "qed."; an embedded
    # qed would survive that filter and yield a double qed that EasyCrypt
    # rejects ("cannot process [save] outside a proof script").
    tactics = split_trailing_qed(tactics)

    # Resolve the target declaration ONCE. Every later lookup in this cycle
    # (prune, block write, post-verify admit check, extracted verification)
    # is pinned to this offset — re-running the name-based heuristic after
    # the write-back would resolve to a still-admitted same-name duplicate
    # and revert a genuinely proved lemma (xorK1, 2026-06-11). The offset
    # stays valid in the written file because the proof block is replaced
    # strictly after the declaration start.
    decl_start = _resolve_lemma_decl_start(content, lemma_name)
    decl_line = (
        content.count("\n", 0, decl_start) if decl_start is not None else None
    )

    # Defense-in-depth: prune any ghost tactics that would fail standalone replay
    tactics = _prune_failing_tactics(ec_path, lemma_name, tactics,
                                     include_dir=include_dir,
                                     decl_start=decl_start)

    # Hard rule: proofs containing `admit.` are NOT proofs. EasyCrypt accepts
    # admit as an axiom-introduction closer, so the file verifies — but the
    # subgoal is morally unproved. Reject any tactic list with `admit.` at
    # depth 0 (i.e. not inside a comment). Seen in ChaChaPoly step3 Run 2.
    if _tactics_contain_admit(tactics):
        logger.error(
            "Proof for %s contains `admit.` — rejecting. "
            "admit closes subgoals by introducing an axiom, which makes the "
            "file compile but leaves the obligation unproved. The prover "
            "must supply real tactics for every subgoal.",
            lemma_name,
        )
        return False

    candidate_gate = _candidate_gate_for_session(ec_session_dir)
    if candidate_gate is None or not candidate_gate.ok:
        detail = (
            candidate_gate.error_summary() if candidate_gate is not None
            else "event-contract checker unavailable"
        )
        logger.error(
            "Rejecting proof for %s before file write: EC session did not "
            "produce a valid closed-candidate event contract (%s).",
            lemma_name, detail,
        )
        return False

    # Build the proof block (exclude qed from tactics, we add it ourselves)
    proof_tactics = [t for t in tactics if t.strip().lower().rstrip(".").strip() != "qed"]

    block = _find_proof_block(content, lemma_name, decl_start=decl_start)
    if block is None:
        logger.error("Cannot find proof block for %s in %s", lemma_name, ec_path)
        return False

    start, end = block

    # Preserve any (* COMPLETE THIS ... *) comment from the old proof block
    old_block = content[start:end]
    comment_match = re.search(r'(\(\*.*?COMPLETE\s+THIS.*?\*\))', old_block, re.DOTALL)
    comment_line = ""
    if comment_match:
        comment_line = comment_match.group(1) + "\n"

    proof_text = "proof.\n" + comment_line + "\n".join(f"  {t}" for t in proof_tactics) + "\nqed."

    new_content = content[:start] + proof_text + content[end:]

    ec_path.write_text(new_content, encoding="utf-8")
    logger.info("Wrote proof to %s", ec_path)

    # Verify: try full-file first, then extracted. A session close is only
    # a candidate signal; offline verification remains the acceptance gate.
    ok, stderr = _verify_ec_file(ec_path, include_dir=include_dir)
    verified_reason = "full_file"
    if ok:
        # Safety net: even if EC accepts the file, reject proofs whose body
        # contains `admit.` — EasyCrypt's admit adds an axiom, so the file
        # verifies but the subgoal is unproved. See ChaChaPoly step3 Run 2.
        if _proof_body_has_admit(new_content, lemma_name, decl_start=decl_start):
            logger.error(
                "Post-verify admit check failed for %s — proof body contains "
                "admit. Reverting.", lemma_name,
            )
            ec_path.write_text(content, encoding="utf-8")
            return False
    else:
        # Full-file failed (common: other lemmas' smt timeouts).
        # Try extracted verification — isolates our lemma.
        logger.info("Full-file verification failed; trying extracted lemma verification")
        full_file_error_excerpt = _distill_ec_stderr(stderr, max_lines=8)
        if _verify_lemma_extracted(ec_path, lemma_name, include_dir=include_dir,
                                   decl_line=decl_line):
            ok = True
            verified_reason = "extracted_lemma"

    if ok:
        _emit_verification_status(
            ec_session_dir,
            lemma_name=lemma_name,
            status="pass",
            ec_path=ec_path,
            reason=verified_reason,
            **(
                {
                    "full_file_status": "fail",
                    "full_file_error_excerpt": full_file_error_excerpt,
                    "extracted_status": "pass",
                }
                if verified_reason == "extracted_lemma" else {}
            ),
        )
        acceptance_gate = _acceptance_gate_for_session(ec_session_dir)
        if acceptance_gate is None or not acceptance_gate.ok:
            detail = (
                acceptance_gate.error_summary() if acceptance_gate is not None
                else "event-contract checker unavailable"
            )
            logger.error(
                "Offline verifier passed for %s, but final event contract "
                "failed (%s). Reverting.",
                lemma_name, detail,
            )
            ec_path.write_text(content, encoding="utf-8")
            return False
        return True

    _emit_verification_status(
        ec_session_dir,
        lemma_name=lemma_name,
        status="fail",
        ec_path=ec_path,
        reason="full_file_and_extracted_failed",
    )

    if session_proved:
        logger.error(
            "Session reported a closed proof candidate for %s, but both "
            "full-file and extracted verification failed. Rejecting the "
            "candidate; session closure is not final proof truth.",
            lemma_name,
        )

    # Nothing confirms the proof — revert.
    ec_path.write_text(content, encoding="utf-8")
    logger.info("Reverted %s to original", ec_path)
    return False
