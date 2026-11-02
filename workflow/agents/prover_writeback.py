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
import secrets
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from core.easycrypt.ec_env import easycrypt_command
from core.easycrypt.committed_history import (
    closed_history_tactics,
    read_committed_commands,
    split_trailing_qed,
)
from core.easycrypt.lemma_decls import lemma_declarations, target_declaration
from core.easycrypt.proof_text import (
    discard_sibling_eco as _discard_sibling_eco,
    easycrypt_code,
    file_wide_unchecked_constructs as _file_wide_unchecked_constructs,
    tactics_contain_admit as _tactics_contain_admit,
    unchecked_proof_constructs as _unchecked_proof_constructs,
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
_EC_DIAGNOSTIC_RE = re.compile(r"\[(?:critical|error)\b")


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


def _has_why3_error(stderr: str) -> bool:
    """Check if stderr contains a why3server connection error."""
    return "cannot start & connect to why3server" in stderr


def _reports_checking_failure(stderr: str) -> bool:
    """True when EasyCrypt ran and itself rejected the checked file.

    A failed check prints a ``[critical]`` (or ``[error-…]``) diagnostic. A
    why3server connection failure, a process that could not start or timed
    out, or an extraction error carries no verdict on the proof.
    """
    return bool(_EC_DIAGNOSTIC_RE.search(stderr)) and not _has_why3_error(stderr)


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
        cmd = easycrypt_command("-timeout", "30")
        if why3_socket and os.path.exists(why3_socket) \
                and _is_why3server_responsive(why3_socket):
            cmd.extend(["-server", why3_socket])
        if include_dir:
            cmd.extend(["-I", include_dir])
        for d in (extra_include_dirs or []):
            if d:
                cmd.extend(["-I", str(d)])
        cmd.append(str(ec_path))
        _discard_sibling_eco(ec_path)
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

        # Runs sharing a checkout can verify a same-named lemma at the same
        # time; a shared path would let one run check the other's proof.
        tmp_path = _claude_scratch_path(
            f"verify_{lemma_name}_{secrets.token_hex(6)}_extracted.ec"
        )
        try:
            tmp_path.write_text(extracted, encoding="utf-8")
            return _verify_extracted_file(tmp_path, ec_path, include_dir=include_dir)
        finally:
            tmp_path.unlink(missing_ok=True)
            tmp_path.with_suffix(".eco").unlink(missing_ok=True)
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

    With several declarations of the name, the first that still needs a
    proof is the target (`lemma_decls.target_declaration`).

    The offset is a stable declaration identity: resolve it once per
    write-back cycle and pass it to `_find_proof_block`, extraction and
    `_proof_body_has_admit`, so they all target the same declaration.
    Resolving again after the write-back fills one declaration would pick a
    still-admitted duplicate and revert a proved lemma. Offsets stay valid
    across the write-back because the replacement happens strictly after
    the declaration start.
    """
    declaration = target_declaration(content, lemma_name)
    return declaration.start if declaration is not None else None


def _find_proof_block(
    content: str, lemma_name: str, decl_start: int | None = None,
) -> tuple[int, int] | None:
    """Find the span of a lemma's own proof block to replace.

    The block is the declaration's `proof. ... qed.` sentences, or the
    sentences no `qed.` closes (such as a bare `admit.`), as
    `lemma_decls` resolves them; a one-line `by` proof has no block. A
    block whose first sentence and `qed.` each start a line is replaced
    from the start of its first line, so the rewritten block starts there.

    `decl_start` pins the lookup to the declaration at that offset (as
    returned by `_resolve_lemma_decl_start`); if no declaration of
    `lemma_name` starts there, returns None rather than silently targeting
    a different same-name declaration. When omitted, the declaration
    `_resolve_lemma_decl_start` picks is used.
    """
    if decl_start is None:
        declaration = target_declaration(content, lemma_name)
    else:
        declaration = next(
            (d for d in lemma_declarations(content, lemma_name)
             if d.start == decl_start),
            None,
        )
    if declaration is None or declaration.proof is None:
        return None
    proof = declaration.proof
    if proof.kind == "by":
        return None
    line_start = content.rfind("\n", 0, proof.start) + 1
    if content[line_start:proof.start].strip():
        return proof.start, proof.end
    if proof.kind == "qed":
        qed = proof.start + easycrypt_code(content[proof.start:proof.end]).rfind("qed")
        qed_line_start = content.rfind("\n", 0, qed) + 1
        if qed_line_start <= proof.start or content[qed_line_start:qed].strip():
            return proof.start, proof.end
    return line_start, proof.end


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
    """Return True if the `lemma_name`'s proof block skips a goal.

    Scans the proof. ... qed. block after the lemma declaration, strips
    comments, and looks for `admit`, `admitted` or a weakening `Proofs`
    pragma as whole tokens. Used as a post-verify safety net — EC accepts
    these, but we don't.

    Pass the `decl_start` the write-back targeted so this checks the SAME
    declaration that was just filled — without it, a same-name duplicate
    that is still admitted wins the prefer-needs-proving heuristic and
    this check reverts a genuinely proved lemma.
    """
    block = _find_proof_block(content, lemma_name, decl_start=decl_start)
    if block is None:
        return False
    start, end = block
    return bool(_unchecked_proof_constructs(content[start:end]))




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
    """Verify proof tactics in place of the target's proof, then write them.

    Args:
        completion_candidate: exact content-bound tree/session handoff.

    Returns typed verification evidence. ``ec_path`` changes only when the
    new content passed every check; on any failure it keeps its old text.
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

    # `exit` or a weakening pragma anywhere in the file skips checks for the
    # proofs after it, so EasyCrypt accepting the file would not show the
    # lemma proved.
    weakening = _file_wide_unchecked_constructs(content)
    if weakening:
        logger.error(
            "Rejecting proof for %s: %s disables strict proof checking (%s).",
            lemma_name, ec_path, ", ".join(sorted(set(weakening))),
        )
        return ProofVerificationEvidence(
            status="fail", error="source disables strict proof checking",
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

    # Verify a copy and move it over the target only after it passes, so the
    # source never holds an unverified proof, even if the run is interrupted
    # mid-check. The copy sits beside the target so EasyCrypt resolves its
    # `require`s exactly as it would for the target.
    target_path = ec_path.resolve()
    copy_path = target_path.with_name(
        f".{target_path.stem}.shannon-verify-{secrets.token_hex(6)}"
        f"{target_path.suffix}"
    )

    def _excerpt(stderr: str) -> str:
        # Diagnostics name the copy; report them against the user's file.
        stderr = stderr.replace(str(copy_path), str(ec_path))
        stderr = stderr.replace(copy_path.name, ec_path.name)
        return _distill_ec_stderr(stderr, max_lines=8)[:3000]

    try:
        copy_path.write_text(new_content, encoding="utf-8")

        # Verify: try full-file first, then extracted. A session close is only
        # a candidate signal; offline verification remains the acceptance gate.
        ok, stderr = _verify_ec_file(copy_path, include_dir=include_dir)
        full_file_error_excerpt = _excerpt(stderr) if not ok else ""
        extracted_error_excerpt = ""
        verified_reason = "full_file"
        if ok:
            # Safety net: even if EC accepts the file, reject proofs whose body
            # contains `admit.` — EasyCrypt's admit adds an axiom, so the file
            # verifies but the subgoal is unproved. See ChaChaPoly step3 Run 2.
            if _proof_body_has_admit(new_content, lemma_name, decl_start=decl_start):
                logger.error(
                    "Post-verify admit check failed for %s — proof body "
                    "contains admit. Leaving %s unchanged.", lemma_name, ec_path,
                )
                return ProofVerificationEvidence(
                    status="fail", event_contract=candidate_gate,
                    error="verified proof body contains admit",
                )
        else:
            # Full-file failed (common: other lemmas' smt timeouts).
            # Try extracted verification — isolates our lemma.
            logger.info("Full-file verification failed; trying extracted lemma verification")
            extracted_ok, extracted_stderr = _verify_lemma_extracted(
                copy_path, lemma_name, include_dir=include_dir, decl_line=decl_line)
            extracted_error_excerpt = (
                _excerpt(extracted_stderr) if not extracted_ok else ""
            )
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
                    "failed (%s). Leaving %s unchanged.",
                    lemma_name, detail, ec_path,
                )
                return ProofVerificationEvidence(
                    status="fail", event_contract=acceptance_gate,
                    error="final verification event contract failed",
                )
            install_error = _install_verified_copy(copy_path, ec_path, content)
            if install_error:
                logger.error(
                    "Verified proof for %s was not written: %s",
                    lemma_name, install_error,
                )
                return ProofVerificationEvidence(
                    status="fail", event_contract=acceptance_gate,
                    error=install_error,
                )
            logger.info("Wrote verified proof to %s", ec_path)
            return ProofVerificationEvidence(
                status="pass",
                method=verified_reason,
                event_contract=acceptance_gate,
            )
    finally:
        copy_path.unlink(missing_ok=True)
        copy_path.with_suffix(".eco").unlink(missing_ok=True)

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
        "session closure is not final proof truth. %s is unchanged.",
        completion_candidate.candidate_id,
        lemma_name,
        ec_path,
    )
    return ProofVerificationEvidence(
        status="fail",
        method="full_file_and_extracted_failed",
        error=("offline EasyCrypt verification failed; "
               f"full_file: {full_file_error_excerpt or 'no diagnostic'}; "
               f"extracted_lemma: {extracted_error_excerpt or 'no diagnostic'}"),
    )


def _install_verified_copy(copy_path: Path, ec_path: Path, content: str) -> str:
    """Atomically replace ``ec_path`` with ``copy_path``; return an error or "".

    A target that changed since write-back read it is left alone: replacing
    it would discard those edits, and the verified copy was built from the
    old text.
    """
    target_path = ec_path.resolve()
    try:
        if target_path.read_text(encoding="utf-8") != content:
            return "target source changed during verification; proof not written"
        os.chmod(copy_path, stat.S_IMODE(target_path.stat().st_mode))
        os.replace(copy_path, target_path)
    except OSError as exc:
        return f"could not write the verified proof: {exc}"
    return ""
