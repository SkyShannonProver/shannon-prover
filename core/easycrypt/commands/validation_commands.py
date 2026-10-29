"""Developer-only proof verification kept outside compiler presentation."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from core.easycrypt.proof_text import (
    discard_sibling_eco,
    easycrypt_code,
    file_wide_unchecked_constructs,
    unchecked_proof_constructs,
)


_VERIFY_TIMEOUT_SECONDS = 600
_TOKEN_EDGE = r"(?<![A-Za-z0-9_'])"
_QED_RE = re.compile(rf"{_TOKEN_EDGE}qed\s*\.")
_BY_RE = re.compile(rf"{_TOKEN_EDGE}by(?![A-Za-z0-9_'])")
# EasyCrypt ends a sentence at a dot followed by a blank, newline or the end.
_SENTENCE_END_RE = re.compile(r"\.(?=[ \t\r\n]|$)")


def _target_region(content: str, lemma: str) -> str | None:
    """Return the text from the last declaration of ``lemma`` to the end."""

    pattern = re.compile(
        r"(?m)^\s*(?:local\s+)?(?:lemma|theorem|equiv|hoare|phoare|ehoare)\s+"
        + re.escape(lemma) + r"(?=[\s:(\[]|$)"
    )
    matches = list(pattern.finditer(easycrypt_code(content)))
    return content[matches[-1].start():] if matches else None


def _proof_closed(region: str) -> bool:
    """Whether the proof in ``region`` ends, by `qed` or a one-line `by`.

    EasyCrypt accepts a proof left open at the end of a file, so an open
    proof must not pass as checked.
    """

    code = easycrypt_code(region)
    if _QED_RE.search(code):
        return True
    end = _SENTENCE_END_RE.search(code)
    return bool(_BY_RE.search(code[:end.start()] if end else code))


def handle_verify_lemma(session, args) -> int:
    """Verify one extracted lemma with the pinned EasyCrypt runtime."""

    from core.easycrypt.lemma_extract import extract_lemma
    from core.easycrypt.session.session_common import get_ec_env
    from core.easycrypt.ec_env import easycrypt_command

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
    use_session_proof = any(
        line.strip().lower().rstrip(".").strip() == "qed"
        for line in history.splitlines()
    )
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
    # proof is checked for constructs that skip goals.
    target_proof = history if use_session_proof else _target_region(
        content, args.verify_lemma,
    )
    if target_proof is None:
        emit("fail", reason="target_not_found")
        sys.stdout.write("[verify] FAILED: target declaration not found in the extract\n")
        return 1
    skipped = unchecked_proof_constructs(target_proof)
    skipped.extend(file_wide_unchecked_constructs(content))
    if skipped:
        reasons = sorted(set(skipped))
        emit("fail", reason="unchecked_proof", constructs=reasons)
        sys.stdout.write("[verify] FAILED: proof is not checked (" + ", ".join(reasons) + ")\n")
        return 1
    if not _proof_closed(target_proof):
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
