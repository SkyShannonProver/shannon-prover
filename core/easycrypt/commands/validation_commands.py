"""Developer-only proof verification kept outside compiler presentation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def handle_verify_lemma(session, args) -> int:
    """Verify one extracted lemma with the pinned EasyCrypt runtime."""

    from core.easycrypt.lemma_extract import extract_lemma
    from core.easycrypt.session_common import get_ec_env

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
    verify_tmp.write_text(content, encoding="utf-8")
    command = ["easycrypt", "-emacs"]
    for include_dir in session._include_dirs:
        command.extend(["-I", include_dir])
    try:
        with verify_tmp.open("rb") as source, verify_out.open("wb") as output:
            subprocess.run(
                command,
                stdin=source,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
                env=get_ec_env(),
            )
    except FileNotFoundError:
        emit("error", reason="easycrypt_not_found")
        return 1
    output_text = verify_out.read_text(encoding="utf-8", errors="replace")
    errors = [line for line in output_text.splitlines() if "[error" in line.lower()]
    if errors:
        emit("fail", error_count=len(errors), errors=errors[:5])
        sys.stdout.write("[verify] FAILED\n" + "\n".join(errors[:5]) + "\n")
        return 1
    emit("pass", error_count=0)
    sys.stdout.write(f"[verify] PASSED: {args.verify_lemma}\n")
    return 0
