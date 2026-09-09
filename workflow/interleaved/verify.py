#!/usr/bin/env python3
"""Project-owned whole-file and scoped lemma-import verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
from core.easycrypt.lemma_extract import extract_lemma
from core.easycrypt.lemma_decls import lemma_decl_matches
from core.easycrypt.proof_text import strip_comments, tactics_contain_admit
from workflow.interleaved.project import InterleavedProject
from workflow.interleaved.runtime import load_runtime_settings


ROOT = _IMPORT_ROOT
IMPORT_SCOPE = "target_lemma_under_declared_dependencies"


def import_verification_environment() -> dict[str, str]:
    """Keep current project binding; the child owns native toolchain selection."""
    environment = os.environ.copy()
    # A cached native environment must not replace the current project binding.
    # Suppress status injection: collect already holds the registry lock.
    environment.pop("INTERLEAVED_RUN_DIR", None)
    return environment


def candidate_path(root: Path, value: str | Path) -> Path:
    """Resolve a verifier input within the project, never a hidden fallback."""
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("candidate must be an existing project-local file")
    return path


def verify_lemma_import(
    *, root: Path, candidate: Path, lemma: str, target: Path,
    include_dirs: tuple[str, ...], check_dir: Path,
) -> dict[str, Any]:
    """Native check of one proof under its declared dependencies.

    The configured project verifier owns additional source policy. This shared
    check neither writes the target nor establishes whole-project success.
    """
    source = candidate.read_text(encoding="utf-8")
    payload: dict[str, Any] = {
        "kind": "interleaved_lemma_import_verification", "schema_version": 1,
        "lemma": lemma, "scope": IMPORT_SCOPE, "whole_project_verified": False,
        "merged_source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "passed": False,
    }
    try:
        span = find_target_proof_block(source, lemma)
        if span is None:
            raise ValueError("candidate target proof is missing")
        body = source[slice(*span)]
        if tactics_contain_admit([body]) or re.search(r"\babort\s*\.", strip_comments(body)):
            raise ValueError("candidate proof contains admit or abort")
        extracted = extract_lemma(candidate, lemma, verify_proof=True)
        check_dir.mkdir(parents=True, exist_ok=True)
        check_file = check_dir / target.name
        if check_file.resolve() in {target.resolve(), candidate.resolve()}:
            raise ValueError("verification scratch file must not overwrite its input")
        check_file.write_text(extracted, encoding="utf-8")
        command = ["easycrypt", "-no-eco", "-timeout", "30"]
        for include in include_dirs:
            command.extend(["-I", str(root / include)])
        command.extend(["-I", str(target.parent), str(check_file)])
        checked = subprocess.run(
            command, cwd=root, env=get_ec_env(), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, check=False,
        )
        payload.update(
            passed=checked.returncode == 0, easycrypt_exit_code=checked.returncode,
            easycrypt_stdout=checked.stdout[-4000:], easycrypt_stderr=checked.stderr[-4000:],
            checked_source_sha256=hashlib.sha256(extracted.encode("utf-8")).hexdigest(),
        )
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"[:4000]
    return payload


def check_import_with_project_verifier(
    *, root: Path, project: InterleavedProject, candidate: Path,
    lemma: str, output: Path,
) -> dict[str, Any]:
    """Call the configured verifier; unsupported import mode fails closed.

    Consume only this process's JSON response, never a prior output artifact.
    A custom verifier must explicitly implement the scoped import contract.
    """
    try:
        checked = subprocess.run(
            [sys.executable, str(root / (project.verifier or "workflow/interleaved/verify.py")),
             "--check-import", "--candidate", str(candidate.relative_to(root)),
             "--lemma", lemma, "--output", str(output.relative_to(root))],
            cwd=root, env=import_verification_environment(), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=660, check=False,
        )
        try:
            payload = json.loads(checked.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("verifier --check-import did not return JSON: " + checked.stderr[-2000:]) from exc
        if not isinstance(payload, dict):
            raise ValueError("project verifier returned a non-object result")
        if checked.returncode != 0 or payload.get("passed") is not True:
            payload["passed"] = False
            payload.setdefault("error", str(payload.get("errors") or checked.stderr or "project verifier rejected import")[:4000])
        elif (
            payload.get("kind") != "interleaved_lemma_import_verification"
            or payload.get("schema_version") != 1
            or payload.get("lemma") != lemma
            or payload.get("scope") != IMPORT_SCOPE
            or payload.get("whole_project_verified") is not False
            or payload.get("merged_source_sha256") != hashlib.sha256(candidate.read_bytes()).hexdigest()
        ):
            raise ValueError("project verifier returned an unbound lemma-import result")
    except Exception as exc:
        payload = {"passed": False, "error": f"project import verifier: {type(exc).__name__}: {exc}"[:4000]}
    _write(output, payload)
    return payload


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _easycrypt_command(executable: Path, project: InterleavedProject) -> list[str]:
    command = [str(executable), "-no-eco", "-timeout", "60"]
    for include in project.include_dirs:
        command.extend(["-I", include])
    command.append(project.target_file)
    return command


def verify(mode: str, *, candidate: Path | None = None, lemma: str | None = None) -> tuple[int, dict[str, Any]]:
    project = load_runtime_settings().project
    errors: list[str] = []
    target = ROOT / project.target_file
    source_path = candidate if mode == "import" else target
    if mode == "import" and (candidate is None or not lemma):
        raise ValueError("import verification requires candidate and lemma")
    source = source_path.read_text(encoding="utf-8") if source_path and source_path.is_file() else ""
    if not source:
        errors.append(f"target file is missing or empty: {project.target_file}")
    elif not (lemma_decl_matches(source, project.final_lemma) if mode == "import"
              else find_target_proof_block(source, project.final_lemma)):
        errors.append(f"final lemma is missing: {project.final_lemma}")
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
    elif mode == "import":
        if not errors:
            payload = verify_lemma_import(
                root=ROOT, candidate=candidate, lemma=lemma, target=target,
                include_dirs=project.include_dirs, check_dir=candidate.parent / "collect_check",
            )
            payload.update(mode=mode, project_identity_sha256=project.identity_sha256)
            return (0 if payload["passed"] else 1), payload
    elif target.is_file():
        environment = get_ec_env()
        executable_name = shutil.which("easycrypt", path=environment.get("PATH"))
        if executable_name is None:
            errors.append("managed EasyCrypt executable is unavailable")
            executable = Path("easycrypt")
        else:
            executable = Path(executable_name).resolve()
        command = _easycrypt_command(executable, project)
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
        "project_identity_sha256": project.identity_sha256,
        "target_file": project.target_file,
        "final_lemma": project.final_lemma,
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
    modes.add_argument("--check-import", action="store_true")
    parser.add_argument("--candidate")
    parser.add_argument("--lemma")
    parser.add_argument("--output")
    args = parser.parse_args()
    mode = "import" if args.check_import else "final" if args.final else "check" if args.check else "preflight"
    if bool(args.check_import) != bool(args.candidate and args.lemma) or (not args.check_import and (args.candidate or args.lemma)):
        parser.error("--candidate and --lemma are required only with --check-import")
    try:
        candidate = candidate_path(ROOT, args.candidate) if args.check_import else None
        code, payload = verify(mode, candidate=candidate, lemma=args.lemma)
    except ValueError as exc:
        parser.error(str(exc))
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
