"""Developer-only proof verification kept outside compiler presentation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from core.easycrypt.lemma_decls import lemma_declarations
from core.easycrypt.proof_text import (
    discard_sibling_eco,
    file_wide_unchecked_constructs,
    unchecked_proof_constructs,
)


_VERIFY_TIMEOUT_SECONDS = 600


def handle_verify_lemma(session, args) -> int:
    """Verify one extracted lemma with the pinned EasyCrypt runtime."""

    from core.easycrypt.committed_history import committed_history_has_qed
    from core.easycrypt.lemma_extract import extract_lemma
    from core.easycrypt.ec_env import easycrypt_command, get_ec_env

    def emit(status: str, **payload) -> None:
        session.emit_event(
            "verification.completed",
            {
                "lemma": args.verify_lemma,
                "status": status,
                "verifier": "easycrypt",
                **payload,
            },
        )

    file_path = Path(args.file) if args.file else None
    if file_path is None:
        meta_path = session.dir / "session_meta.json"
        if meta_path.exists():
            try:
                value = json.loads(meta_path.read_text()).get("file")
                file_path = Path(value) if value else None
            except Exception:
                file_path = None
    if file_path is None or not file_path.exists():
        emit("error", reason="source_file_not_found")
        sys.stderr.write("No source file found for verification.\n")
        return 1

    history = (
        session.history.read_text(encoding="utf-8", errors="replace")
        if session.history.exists()
        else ""
    )
    # committed_history owns closure syntax: a session may close with a
    # compound step such as `TAC. qed.` on one line.
    use_session_proof = committed_history_has_qed(session.dir)
    try:
        extracted = extract_lemma(
            file_path,
            args.verify_lemma,
            open_proof=use_session_proof,
            verify_proof=not use_session_proof,
        )
    except ValueError as exc:
        emit("error", reason="extract_lemma_failed", error=str(exc))
        sys.stderr.write(f"Could not extract lemma: {exc}\n")
        return 1

    verify_tmp = session.dir / "verify_tmp.ec"
    verify_out = session.dir / "verify.out"
    content = extracted
    if use_session_proof:
        content += ("" if content.endswith("\n") else "\n") + history
    # The extract replaces every other proof with admit, so only the target
    # proof is checked for constructs that skip goals. The target is the
    # last declaration: the extract ends with it.
    declarations = lemma_declarations(content, args.verify_lemma)
    if not declarations:
        emit("fail", reason="target_not_found")
        sys.stdout.write("[verify] FAILED: target declaration not found in the extract\n")
        return 1
    declaration = declarations[-1]
    target_proof = history if use_session_proof else content[declaration.start:]
    skipped = unchecked_proof_constructs(target_proof)
    skipped.extend(file_wide_unchecked_constructs(content))
    if skipped:
        reasons = sorted(set(skipped))
        emit("fail", reason="unchecked_proof", constructs=reasons)
        sys.stdout.write("[verify] FAILED: proof is not checked (" + ", ".join(reasons) + ")\n")
        return 1
    # EasyCrypt accepts a proof left open at the end of a file, so an open
    # proof must not pass as checked.
    if declaration.proof is None or declaration.proof.kind == "open":
        emit("fail", reason="proof_not_closed")
        sys.stdout.write("[verify] FAILED: proof is not closed\n")
        return 1
    verify_tmp.write_text(content, encoding="utf-8")
    discard_sibling_eco(verify_tmp)
    command = easycrypt_command("compile", "-no-eco")
    for include_dir in session._include_dirs:
        command.extend(["-I", include_dir])
    command.append(str(verify_tmp))
    try:
        with verify_out.open("wb") as output:
            completed = subprocess.run(
                command,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
                env=get_ec_env(),
                timeout=_VERIFY_TIMEOUT_SECONDS,
            )
    except FileNotFoundError:
        emit("error", reason="easycrypt_not_found")
        return 1
    except subprocess.TimeoutExpired:
        emit("fail", reason="timeout", timeout_seconds=_VERIFY_TIMEOUT_SECONDS)
        sys.stdout.write(f"[verify] FAILED: timed out after {_VERIFY_TIMEOUT_SECONDS}s\n")
        return 1
    output_text = verify_out.read_text(encoding="utf-8", errors="replace")
    errors = [
        line for line in output_text.splitlines()
        if "[error" in line.lower() or "[critical" in line.lower()
    ]
    if completed.returncode != 0 or errors:
        emit(
            "fail",
            returncode=completed.returncode,
            error_count=len(errors),
            errors=errors[:5],
        )
        sys.stdout.write(
            f"[verify] FAILED (exit {completed.returncode})\n" + "\n".join(errors[:5]) + "\n"
        )
        return 1
    emit("pass", error_count=0)
    sys.stdout.write(f"[verify] PASSED: {args.verify_lemma}\n")
    return 0
