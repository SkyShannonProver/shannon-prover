#!/usr/bin/env python3
"""Product-level whole-file verification for interleaved projects."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from core.easycrypt.ec_env import get_ec_env
from core.easycrypt.eval_source_prep import find_target_proof_block
from workflow.interleaved.runtime import load_runtime_settings


_SETTINGS = load_runtime_settings()
ROOT = _SETTINGS.root
PROJECT = _SETTINGS.project


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _easycrypt_command(executable: Path) -> list[str]:
    command = [str(executable), "-no-eco", "-timeout", "60"]
    for include in PROJECT.include_dirs:
        command.extend(["-I", include])
    command.append(PROJECT.target_file)
    return command


def verify(mode: str) -> tuple[int, dict[str, Any]]:
    errors: list[str] = []
    target = ROOT / PROJECT.target_file
    source = target.read_text(encoding="utf-8") if target.is_file() else ""
    if not source:
        errors.append(f"target file is missing or empty: {PROJECT.target_file}")
    elif find_target_proof_block(source, PROJECT.final_lemma) is None:
        errors.append(f"final lemma is missing: {PROJECT.final_lemma}")
    if mode == "final" and re.search(r"(?i)\badmit\s*\.", source):
        errors.append("final target still contains admit.")

    bootstrap = subprocess.run(
        [sys.executable, "tools/bootstrap_easycrypt.py", "--verify-only"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    command: list[str] = []
    replay: subprocess.CompletedProcess[str] | None = None
    if bootstrap.returncode != 0:
        errors.append("locked EasyCrypt bootstrap verification failed")
    elif target.is_file():
        environment = get_ec_env()
        executable_name = shutil.which("easycrypt", path=environment.get("PATH"))
        if executable_name is None:
            errors.append("managed EasyCrypt executable is unavailable")
            executable = Path("easycrypt")
        else:
            executable = Path(executable_name).resolve()
        command = _easycrypt_command(executable)
        if executable_name is not None:
            replay = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if replay.returncode != 0:
                errors.append("whole-file EasyCrypt verification failed")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "interleaved_project_verification",
        "checked_at": _now(),
        "mode": mode,
        "project_identity_sha256": PROJECT.identity_sha256,
        "target_file": PROJECT.target_file,
        "final_lemma": PROJECT.final_lemma,
        "passed": not errors,
        "errors": errors,
        "bootstrap_exit_code": bootstrap.returncode,
        "easycrypt_command": command,
        "easycrypt_exit_code": replay.returncode if replay is not None else None,
        "easycrypt_stdout": (replay.stdout[-8000:] if replay is not None else ""),
        "easycrypt_stderr": (replay.stderr[-8000:] if replay is not None else ""),
    }
    return (0 if not errors else 1), payload


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--final", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    mode = "final" if args.final else "check" if args.check else "preflight"
    code, payload = verify(mode)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        if output.is_absolute() or ".." in output.parts:
            parser.error("--output must be repository-relative")
        _write(ROOT / output, payload)
    print(rendered)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
