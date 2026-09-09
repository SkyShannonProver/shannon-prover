"""Tactic extraction, proof write-back, and EasyCrypt verification.

Extracted verbatim from workflow/agents/prover.py: everything that turns a
finished (or interrupted) prover session into a verified proof in the target
.ec file — exact candidate extraction, lemma-scoped verification, admit
scanning, and the final write-and-verify pass. Finalization never repairs proofs.
prover.py re-exports every name so external callers and tests are unchanged.
"""
from __future__ import annotations

import logging
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from core.easycrypt.committed_history import (
    closed_history_tactics,
    read_committed_commands,
    read_committed_transactions,
    split_trailing_qed,
)
from core.easycrypt.proof_text import (
    ADMIT_TOKEN_RE as _ADMIT_TOKEN_RE,
    strip_comments as _strip_comments_for_admit_check,
    tactics_contain_admit as _tactics_contain_admit,
)
from workflow.agents.ec_services import (
    _claude_scratch_path,
    _ensure_why3server,
    _get_opam_env,
    _is_why3server_responsive,
)

logger = logging.getLogger("workflow.agents.prover")

if TYPE_CHECKING:
    from workflow.proof_acceptance import EventContractGate
    from workflow.tree.result import SessionClosureCandidate

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_EC_SPINNER_RE = re.compile(r'^\[[-\\|/]\]\s+\[\d+\]\s+\d+\.\d+%')


@dataclass(frozen=True)
class ProofVerificationEvidence:
    """Mechanical finalization evidence consumed by the run-level owner."""

    status: str
    method: str = ""
    event_contract: "EventContractGate | None" = None
    error: str = ""

    def __post_init__(self) -> None:
        if self.status not in {"pass", "fail"}:
            raise ValueError("unsupported proof verification status")

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def _extract_tactics_from_candidate(
    candidate: "SessionClosureCandidate | None",
) -> list[str]:
    """Return only the exact tree candidate's validated committed history.

    The immutable candidate is the only semantic handoff from tree search.
    Missing, drifted, or non-qed history fails closed. Sibling sessions, mutable
    function attributes, and agent prose are intentionally not recovery sources.
    """
    if candidate is None:
        return []
    try:
        from workflow.proof_acceptance import (
            validate_completion_candidate_contract,
        )

        candidate_gate = validate_completion_candidate_contract(candidate)
    except Exception:
        return []
    if not candidate_gate.ok or not candidate_gate.completion_candidate_bound:
        return []
    return closed_history_tactics(Path(candidate.session_dir))


def _extract_partial_tactics_from_sessions(
    *,
    session_dirs: list[str] | tuple[str, ...],
    resume_capsules: list[str] | None = None,
) -> list[str]:
    """Return the best replayable prefix even when no ``qed.`` exists.

    This is reporting-only: callers must not mark the proof as proved from this
    result.  It lets eval reports show how far an interrupted or failed run got.
    """
    candidates = [
        read_committed_commands(Path(session_dir))
        for session_dir in session_dirs
        if str(session_dir).strip()
    ]

    for capsule in resume_capsules or []:
        path = Path(capsule)
        root = path if path.is_dir() else path.parent
        candidates.append(read_committed_commands(root))

    candidates = [item for item in candidates if item]
    if not candidates:
        return []
    return max(candidates, key=len)


def _extract_partial_transactions_from_sessions(
    *,
    session_dirs: list[str] | tuple[str, ...],
    committed_prefix: list[str] | tuple[str, ...],
    resume_capsules: list[str] | None = None,
) -> list[str]:
    """Return transaction boundaries for the selected partial prefix.

    The public/reporting prefix is command-oriented, but replay must retain
    the manager commit boundaries recorded by ``steps.log`` so EasyCrypt
    bullet blocks remain atomic.
    """

    expected = list(committed_prefix)
    for session_dir in session_dirs:
        path = Path(session_dir)
        if read_committed_commands(path) == expected:
            transactions = read_committed_transactions(path)
            if transactions:
                return transactions
    for raw_capsule in resume_capsules or []:
        try:
            from workflow.node.proof_node_resume import load_resume_capsule

            capsule = load_resume_capsule(raw_capsule)
        except Exception:
            continue
        if capsule.replay_prefix == expected:
            return list(capsule.replay_transactions)
    return []


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
        from core.easycrypt.ec_proc import why3_socket_from_env

        ok, stderr = _run(why3_socket_from_env())
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
) -> tuple[bool, str]:
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

        return _verify_extracted_file(tmp_path, ec_path, include_dir=include_dir)
    except Exception as e:
        logger.error("Extracted-lemma verification error: %s", e)
        return False, str(e)


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
    extraction, and `_proof_body_has_admit` so they all
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

    Returns only the current bounded handback fields, or an empty dict if the
    report is absent or invalid. Shannon reports concrete blockers and
    evidence-grounded discoveries; deciding what to do next remains the
    caller's job.
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

    try:
        parsed, _end = json.JSONDecoder().raw_decode(output_text[json_start:])
    except json.JSONDecodeError:
        logger.warning("PROVER REPORT JSON parse failed")
        return {}
    if not isinstance(parsed, dict):
        return {}
    report: dict[str, list[str]] = {}
    for key in ("blockers", "discoveries"):
        raw_items = parsed.get(key)
        if raw_items is None:
            continue
        if not isinstance(raw_items, list):
            logger.warning("PROVER REPORT field %s must be a list", key)
            continue
        items = [
            str(item).strip()[:3000]
            for item in raw_items[:12]
            if isinstance(item, str) and str(item).strip()
        ]
        report[key] = items
    unknown = sorted(set(parsed) - {"blockers", "discoveries"})
    if unknown:
        logger.warning(
            "Ignoring unsupported PROVER REPORT field(s): %s",
            ", ".join(unknown),
        )
    return report


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




def _build_proof_text(old_block: str, tactics: list[str]) -> str:
    """Format a proof block with the given tactics, preserving the COMPLETE THIS comment."""
    proof_tactics = [t for t in tactics if t.strip().lower().rstrip(".").strip() != "qed"]
    comment_match = re.search(r'(\(\*.*?COMPLETE\s+THIS.*?\*\))', old_block, re.DOTALL)
    comment_line = (comment_match.group(1) + "\n") if comment_match else ""
    return "proof.\n" + comment_line + "\n".join(f"  {t}" for t in proof_tactics) + "\nqed."




def _write_and_verify_proof(
    ec_path: Path,
    lemma_name: str,
    tactics: list[str],
    completion_candidate: "SessionClosureCandidate",
    include_dir: str = "",
) -> ProofVerificationEvidence:
    """Write proof tactics into the .ec file (replacing admit) and verify.

    Args:
        completion_candidate: exact content-bound tree/session handoff.

    Returns typed verification evidence. Reverts on failure.
    """
    if ec_path.resolve() != Path(completion_candidate.target_file).resolve():
        logger.error("Completion candidate target file identity does not match writeback")
        return ProofVerificationEvidence(
            status="fail", error="candidate target file mismatch",
        )
    if lemma_name != completion_candidate.target_lemma:
        logger.error("Completion candidate target lemma identity does not match writeback")
        return ProofVerificationEvidence(
            status="fail", error="candidate target lemma mismatch",
        )
    content = ec_path.read_text(encoding="utf-8")

    # Normalize a compound closer ("TAC. qed." committed as one step) into
    # a separate standalone "qed." entry. The proof-block builder below
    # filters standalone qed lines and appends its own "qed."; an embedded
    # qed would survive that filter and yield a double qed that EasyCrypt
    # rejects ("cannot process [save] outside a proof script").
    tactics = split_trailing_qed(tactics)

    # Resolve the target declaration ONCE. Every later lookup in this cycle
    # (block write, post-verify admit check, extracted verification)
    # is pinned to this offset — re-running the name-based heuristic after
    # the write-back would resolve to a still-admitted same-name duplicate
    # and revert a genuinely proved lemma (xorK1, 2026-06-11). The offset
    # stays valid in the written file because the proof block is replaced
    # strictly after the declaration start.
    decl_start = _resolve_lemma_decl_start(content, lemma_name)
    decl_line = (
        content.count("\n", 0, decl_start) if decl_start is not None else None
    )

    # Verify the selected history unchanged. Removing rejected commands here
    # would change both the proof strategy and the content-bound candidate.

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
        return ProofVerificationEvidence(
            status="fail", error="proof contains admit",
        )

    from workflow.proof_acceptance import validate_completion_candidate_contract

    candidate_gate = validate_completion_candidate_contract(completion_candidate)
    if not candidate_gate.ok:
        detail = (
            candidate_gate.error_summary() if candidate_gate is not None
            else "event-contract checker unavailable"
        )
        logger.error(
            "Rejecting proof for %s before file write: EC session did not "
            "produce a valid closed-candidate event contract (%s).",
            lemma_name, detail,
        )
        return ProofVerificationEvidence(
            status="fail", event_contract=candidate_gate,
            error="completion candidate contract failed",
        )

    block = _find_proof_block(content, lemma_name, decl_start=decl_start)
    if block is None:
        logger.error("Cannot find proof block for %s in %s", lemma_name, ec_path)
        return ProofVerificationEvidence(
            status="fail", event_contract=candidate_gate,
            error="target proof block not found",
        )

    start, end = block

    proof_text = _build_proof_text(content[start:end], tactics)

    new_content = content[:start] + proof_text + content[end:]

    ec_path.write_text(new_content, encoding="utf-8")
    logger.info("Wrote proof to %s", ec_path)

    # Verify: try full-file first, then extracted. A session close is only
    # a candidate signal; offline verification remains the acceptance gate.
    ok, stderr = _verify_ec_file(ec_path, include_dir=include_dir)
    full_file_error_excerpt = _distill_ec_stderr(stderr, max_lines=8)[:3000] if not ok else ""
    extracted_error_excerpt = ""
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
            return ProofVerificationEvidence(
                status="fail", event_contract=candidate_gate,
                error="verified proof body contains admit",
            )
    else:
        # Full-file failed (common: other lemmas' smt timeouts).
        # Try extracted verification — isolates our lemma.
        logger.info("Full-file verification failed; trying extracted lemma verification")
        extracted_ok, extracted_stderr = _verify_lemma_extracted(
            ec_path, lemma_name, include_dir=include_dir, decl_line=decl_line)
        extracted_error_excerpt = _distill_ec_stderr(extracted_stderr, max_lines=8)[:3000] if not extracted_ok else ""
        if extracted_ok:
            ok = True
            verified_reason = "extracted_lemma"

    if ok:
        _emit_verification_status(
            completion_candidate.session_dir,
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
        acceptance_gate = _acceptance_gate_for_session(
            completion_candidate.session_dir
        )
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
            return ProofVerificationEvidence(
                status="fail", event_contract=acceptance_gate,
                error="final verification event contract failed",
            )
        return ProofVerificationEvidence(
            status="pass",
            method=verified_reason,
            event_contract=acceptance_gate,
        )

    _emit_verification_status(
        completion_candidate.session_dir,
        lemma_name=lemma_name,
        status="fail",
        ec_path=ec_path,
        reason="full_file_and_extracted_failed",
        candidate_id=completion_candidate.candidate_id,
        full_file_error_excerpt=full_file_error_excerpt,
        extracted_error_excerpt=extracted_error_excerpt,
    )

    logger.error(
        "Session completion candidate %s for %s failed offline verification; "
        "session closure is not final proof truth.",
        completion_candidate.candidate_id,
        lemma_name,
    )

    # Nothing confirms the proof — revert.
    ec_path.write_text(content, encoding="utf-8")
    logger.info("Reverted %s to original", ec_path)
    return ProofVerificationEvidence(
        status="fail",
        method="full_file_and_extracted_failed",
        error=("offline EasyCrypt verification failed; "
               f"full_file: {full_file_error_excerpt or 'no diagnostic'}; "
               f"extracted_lemma: {extracted_error_excerpt or 'no diagnostic'}"),
    )
