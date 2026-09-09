#!/usr/bin/env python3
"""Fail-closed source and EasyCrypt verifier for the interleaved experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from experiments.interleaved_shannon.source_projection import (
    ANSWER_SOURCE,
)


ROOT = Path(__file__).resolve().parents[2]
TARGET_REL = Path("experiments/interleaved_shannon/task/chacha_poly.ec")
SIBLING_RELS = (
    Path("experiments/interleaved_shannon/task/ske.ec"),
    Path("experiments/interleaved_shannon/task/indistinguishability.eca"),
)
SCRATCH_BEGIN = "(* SCRATCHPAD BEGIN — your own declarations may go below this line *)"
SCRATCH_END = "(* SCRATCHPAD END *)"
ALWAYS_FORBIDDEN = re.compile(
    r"\b(?:axiom|pragma|exit|abort|require)\b",
    re.IGNORECASE,
)
ADMIT = re.compile(r"\badmit\b", re.IGNORECASE)
UPTO_LOCATION = re.compile(r"[1-9][0-9]*(?::[0-9]+)?\Z")


class VerificationError(RuntimeError):
    pass


def run(
    command: list[str], *, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=environment,
    )


def git_bytes(path: Path) -> bytes:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.as_posix()}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise VerificationError(
            f"cannot read pinned HEAD copy of {path}: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
    return result.stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def editable_regions(source: str) -> tuple[str, str]:
    if source.count(SCRATCH_BEGIN) != 1 or source.count(SCRATCH_END) != 1:
        raise VerificationError("scratchpad markers must each occur exactly once")

    begin = source.index(SCRATCH_BEGIN) + len(SCRATCH_BEGIN)
    end = source.index(SCRATCH_END, begin)

    lemma_matches = list(re.finditer(r"(?m)^lemma\s+conclusion\b", source[end:]))
    if len(lemma_matches) != 1:
        raise VerificationError("lemma conclusion must occur exactly once after the scratchpad")
    lemma_start = end + lemma_matches[0].start()
    proof_match = re.search(r"(?m)^proof\.\s*$", source[lemma_start:])
    if proof_match is None:
        raise VerificationError("conclusion proof opener was not found")
    proof_body_start = lemma_start + proof_match.end()
    qed_match = re.search(r"(?m)^qed\.\s*$", source[proof_body_start:])
    if qed_match is None:
        raise VerificationError("conclusion qed was not found")
    proof_body_end = proof_body_start + qed_match.start()
    return source[begin:end], source[proof_body_start:proof_body_end]


def immutable_projection(source: str) -> str:
    editable_regions(source)
    scratch_start = source.index(SCRATCH_BEGIN) + len(SCRATCH_BEGIN)
    scratch_end = source.index(SCRATCH_END, scratch_start)
    lemma_start = source.index("lemma conclusion", scratch_end)
    proof_match = re.search(r"(?m)^proof\.\s*$", source[lemma_start:])
    assert proof_match is not None
    proof_body_start = lemma_start + proof_match.end()
    qed_match = re.search(r"(?m)^qed\.\s*$", source[proof_body_start:])
    assert qed_match is not None
    proof_body_end = proof_body_start + qed_match.start()
    return (
        source[:scratch_start]
        + "\n<EDITABLE_SCRATCHPAD>\n"
        + source[scratch_end:proof_body_start]
        + "\n<EDITABLE_CONCLUSION_PROOF>\n"
        + source[proof_body_end:]
    )


def _source_policy_mode(mode: str) -> str:
    """Map a diagnostic replay mode to its source-confinement policy."""

    if mode in {"upto", "import"}:
        return "check"
    if mode in {"preflight", "check", "final"}:
        return mode
    raise ValueError(f"unsupported verification mode: {mode}")


def editable_region_forbidden_words(mode: str, scratch: str, proof: str) -> list[str]:
    """Return constructs forbidden in editable regions for one verifier mode.

    Development checks deliberately allow temporary ``admit`` shells so Opus
    can coarse-check a loadable file while constructing later declarations.
    Every other escape construct remains forbidden, and final acceptance adds
    ``admit`` back to the forbidden set.
    """

    policy_mode = _source_policy_mode(mode)
    text = scratch + proof
    forbidden = {
        match.group(0).lower()
        for match in ALWAYS_FORBIDDEN.finditer(text)
    }
    if policy_mode == "final" and ADMIT.search(text):
        forbidden.add("admit")
    return sorted(forbidden)


def allowed_tracked_change_sets(mode: str) -> list[list[str]]:
    """Return the exact tracked change sets admitted by one verifier mode."""

    target = TARGET_REL.as_posix()
    if mode == "preflight":
        return [[]]
    if mode in {"check", "upto", "import"}:
        return [[], [target]]
    if mode == "final":
        return [[target]]
    raise ValueError(f"unsupported verification mode: {mode}")


def active_shannon_job_errors(mode: str, summary: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    violations = summary.get("active_boundary_violations")
    if isinstance(violations, list):
        errors.extend(
            str(item.get("message") or "active Shannon boundary changed")
            for item in violations
            if isinstance(item, dict)
        )
    if mode != "final":
        return errors
    jobs = summary.get("jobs")
    if not isinstance(jobs, list):
        return errors
    active = [
        str(item.get("job_id") or "unknown")
        for item in jobs
        if isinstance(item, dict)
        and item.get("status") in {"queued", "starting", "running"}
    ]
    if not active:
        return errors
    errors.append(
        "final verification requires a Shannon join barrier; active jobs: "
        + ", ".join(active)
    )
    return errors


def shannon_terminal_alerts(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Prominently project terminal jobs at the next verifier boundary."""

    jobs = summary.get("jobs")
    if not isinstance(jobs, list):
        return []
    alerts: list[dict[str, Any]] = []
    for item in jobs:
        if not isinstance(item, dict) or item.get("status") not in {
            "verified",
            "incomplete",
            "infrastructure_invalid",
            "cancelled",
            "stale_merge",
        }:
            continue
        alert: dict[str, Any] = {
            key: str(item.get(key) or "")
            for key in (
                "job_id",
                "lemma",
                "status",
                "failure_class",
                "failure_message",
                "resume_from_job_id",
                "resume_checkpoint_id",
                "terminal_event_sequence",
            )
            if item.get(key)
        }
        if isinstance(item.get("progress"), dict):
            alert["progress"] = item["progress"]
        alerts.append(alert)
    return alerts


def validate_upto_location(value: str) -> str:
    """Validate the bounded EasyCrypt ``-upto`` location grammar."""

    if not UPTO_LOCATION.fullmatch(value):
        raise ValueError("--upto must be LINE or LINE:COL with a positive line")
    return value


def easycrypt_command(
    executable: Path,
    *,
    mode: str,
    upto: str | None = None,
) -> list[str]:
    """Build the locked EasyCrypt command for one verifier mode.

    Development checking uses EasyCrypt's stateless LLM batch frontend so a
    failed replay returns the native goals immediately before the rejected
    command.  Final and preflight verification retain the ordinary full-file
    acceptance path.
    """

    loader = [
        "-timeout",
        "60",
        "-I",
        "easycrypt-src/theories",
        TARGET_REL.as_posix(),
    ]
    if mode == "check":
        if upto is not None:
            raise ValueError("--upto is not valid with --check")
        return [str(executable), "llm", "-lastgoals", *loader]
    if mode == "upto":
        if upto is None:
            raise ValueError("upto mode requires a source location")
        return [
            str(executable),
            "llm",
            "-lastgoals",
            "-upto",
            validate_upto_location(upto),
            *loader,
        ]
    if mode in {"preflight", "final"}:
        if upto is not None:
            raise ValueError(f"--upto is not valid with --{mode}")
        return [str(executable), "-no-eco", *loader]
    raise ValueError(f"unsupported verification mode: {mode}")


def easycrypt_goal_output_kind(stdout: str) -> str:
    """Classify the native goal channel without reinterpreting its contents."""

    output = stdout.strip()
    if not output:
        return "absent"
    if output == "No active proof.":
        return "no_active_proof"
    return "open_goals"


def easycrypt_replay_outcome(
    *,
    mode: str,
    returncode: int,
    stdout: str,
) -> dict[str, Any]:
    """Describe why one EasyCrypt replay stopped.

    In ``upto`` mode, a successful process with native goal output reached the
    requested pre-command boundary.  A successful process with no goal output
    completed the file before such a boundary was encountered.  Combining
    ``-upto`` with ``-lastgoals`` lets a failing replay retain the exact native
    goal immediately before the earlier rejected command.
    """

    goal_output = easycrypt_goal_output_kind(stdout)
    if mode == "upto":
        if returncode != 0:
            status = "failed_before_upto"
        elif goal_output == "absent":
            status = "completed_before_upto"
        else:
            status = "reached_upto"
    elif mode == "check":
        status = "completed" if returncode == 0 else "failed"
    elif mode in {"preflight", "final"}:
        status = "accepted" if returncode == 0 else "rejected"
    else:
        raise ValueError(f"unsupported verification mode: {mode}")
    return {
        "status": status,
        "native_goal_output": goal_output,
    }


def repository_change_errors(mode: str) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    diff = run(["git", "diff", "--name-only", "HEAD"])
    staged = run(["git", "diff", "--cached", "--name-only", "HEAD"])
    untracked = run(["git", "ls-files", "--others", "--exclude-standard"])
    changed = sorted(line for line in diff.stdout.splitlines() if line)
    staged_paths = sorted(line for line in staged.stdout.splitlines() if line)
    untracked_paths = sorted(line for line in untracked.stdout.splitlines() if line)

    if any(result.returncode != 0 for result in (diff, staged, untracked)):
        errors.append("could not determine the complete Git change set")
    if staged_paths:
        errors.append(f"staged changes are forbidden: {staged_paths}")
    if untracked_paths:
        errors.append(f"untracked non-ignored files are forbidden: {untracked_paths}")

    allowed = allowed_tracked_change_sets(mode)
    if changed not in allowed:
        errors.append(
            f"tracked changes must be one of {allowed}, got {changed}"
        )

    return errors, {
        "tracked_changes": changed,
        "allowed_tracked_change_sets": allowed,
        "staged_changes": staged_paths,
        "untracked_nonignored": untracked_paths,
    }


def locked_easycrypt() -> tuple[Path, dict[str, Any], dict[str, str]]:
    python = ROOT / ".venv" / "bin" / "python"
    if not python.is_file():
        raise VerificationError(f"managed Python is missing: {python}")
    result = run([str(python), "tools/bootstrap_easycrypt.py", "--verify-only"])
    try:
        from core.easycrypt.ec_env import get_ec_env

        environment = get_ec_env()
    except RuntimeError as exc:
        raise VerificationError(f"managed EasyCrypt environment failed: {exc}") from exc
    if result.returncode != 0:
        raise VerificationError(
            "managed EasyCrypt verification failed: " + (result.stderr or result.stdout).strip()
        )
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError("bootstrap_easycrypt returned non-JSON output") from exc
    executable = Path(str(receipt.get("easycrypt", "")))
    if not executable.is_absolute() or not executable.is_file():
        raise VerificationError(f"invalid EasyCrypt path in receipt: {executable}")
    if Path(environment.get("OPAMROOT", "")) != Path(str(receipt.get("opam_root", ""))):
        raise VerificationError("managed EasyCrypt environment selected a different opam root")
    if environment.get("OPAMSWITCH") != receipt.get("switch"):
        raise VerificationError("managed EasyCrypt environment selected a different switch")
    return executable, receipt, environment


def verify(
    mode: str,
    output: Path | None,
    *,
    upto: str | None = None,
    candidate: Path | None = None,
    lemma: str | None = None,
) -> tuple[dict[str, Any], bool]:
    if mode == "import":
        if candidate is None or not lemma:
            raise ValueError("import verification requires candidate and lemma")
        from workflow.interleaved.verify import candidate_path
        candidate = candidate_path(ROOT, candidate)
    elif candidate is not None or lemma is not None:
        raise ValueError("candidate and lemma are only valid for import verification")
    policy_mode = _source_policy_mode(mode)
    if mode == "upto":
        if upto is None:
            raise ValueError("upto mode requires a source location")
        upto = validate_upto_location(upto)
    elif upto is not None:
        raise ValueError(f"--upto is not valid with --{mode}")
    errors: list[str] = []
    report: dict[str, Any] = {"mode": mode, "target": TARGET_REL.as_posix()}
    if upto is not None:
        report["upto"] = upto
        report["prefix_only"] = True

    run_raw = os.environ.get("INTERLEAVED_RUN_DIR", "").strip()
    if run_raw:
        relative = Path(run_raw)
        candidate_run = (ROOT / relative).resolve()
        allowed_runs = (ROOT / "artifacts" / "interleaved_shannon").resolve()
        if (
            not relative.is_absolute()
            and ".." not in relative.parts
            and candidate_run.is_relative_to(allowed_runs)
            and candidate_run.is_dir()
        ):
            try:
                from experiments.interleaved_shannon.shannon_jobs import (
                    public_job_summary,
                )

                report["shannon_jobs"] = public_job_summary(candidate_run)
                report["shannon_terminal_alerts"] = shannon_terminal_alerts(
                    report["shannon_jobs"]
                )
                errors.extend(active_shannon_job_errors(mode, report["shannon_jobs"]))
            except Exception as exc:
                report["shannon_jobs"] = {
                    "status": "unavailable",
                    "error": f"{type(exc).__name__}: {exc}",
                }

    commit = run(["git", "rev-parse", "HEAD"])
    report["commit"] = commit.stdout.strip()
    if commit.returncode != 0:
        errors.append("could not resolve HEAD")

    target = ROOT / TARGET_REL
    if not target.is_file() or target.is_symlink():
        errors.append("target must be a regular non-symlink file")
        current_bytes = b""
    else:
        current_bytes = (candidate if mode == "import" else target).read_bytes()

    try:
        pinned_bytes = git_bytes(TARGET_REL)
        current_text = current_bytes.decode("utf-8")
        pinned_text = pinned_bytes.decode("utf-8")
        scratch, proof = editable_regions(current_text)
        if policy_mode == "preflight":
            if current_bytes != pinned_bytes:
                errors.append("preflight target differs from the pinned commit")
        elif immutable_projection(current_text) != immutable_projection(pinned_text):
            errors.append("content outside the two editable regions changed")

        forbidden = editable_region_forbidden_words(mode, scratch, proof)
        if forbidden:
            errors.append(f"editable regions contain forbidden words: {forbidden}")
        if policy_mode == "final" and ADMIT.search(current_text):
            errors.append("final target contains admit")
        report["target_sha256"] = sha256(current_bytes)
        report["pinned_target_sha256"] = sha256(pinned_bytes)
    except (UnicodeDecodeError, VerificationError) as exc:
        errors.append(str(exc))

    sibling_hashes: dict[str, Any] = {}
    for relative in SIBLING_RELS:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            errors.append(f"sibling must be a regular non-symlink file: {relative}")
            continue
        actual = path.read_bytes()
        try:
            pinned = git_bytes(relative)
        except VerificationError as exc:
            errors.append(str(exc))
            continue
        sibling_hashes[relative.as_posix()] = {
            "actual": sha256(actual),
            "pinned": sha256(pinned),
        }
        if actual != pinned:
            errors.append(f"sibling changed: {relative}")
    report["siblings"] = sibling_hashes

    change_errors, change_report = repository_change_errors(mode)
    errors.extend(change_errors)
    report["git"] = change_report

    ec_stdout = ""
    ec_stderr = ""
    if not errors:
        try:
            executable, receipt, environment = locked_easycrypt()
            report["easycrypt_receipt"] = receipt
            report["why3_config"] = environment.get("SHANNON_WHY3_CONFIG")
            if mode == "import":
                from workflow.interleaved.verify import verify_lemma_import
                checked_import = verify_lemma_import(
                    root=ROOT, candidate=candidate, lemma=lemma, target=target,
                    include_dirs=("easycrypt-src/theories",),
                    check_dir=candidate.parent / "collect_check",
                )
                report.update(checked_import)
                ec_stdout = str(checked_import.get("easycrypt_stdout") or "")
                ec_stderr = str(checked_import.get("easycrypt_stderr") or "")
                if not checked_import["passed"]:
                    errors.append(str(checked_import.get("error") or ec_stderr or "lemma import rejected"))
            else:
                ec_stdout, ec_stderr = _replay_check(
                    report, errors, executable, environment, mode, upto,
                )
        except VerificationError as exc:
            errors.append(str(exc))

    report["errors"] = errors
    report["answer_source_visible_after_verification"] = ANSWER_SOURCE.exists()
    if ANSWER_SOURCE.exists() and run(
        ["git", "config", "--bool", "core.sparseCheckout"]
    ).stdout.strip() == "true":
        errors.append("answer-bearing EasyCrypt source remains visible")
    report["passed"] = not errors

    if output is not None:
        output = output if output.is_absolute() else ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output.with_suffix(".easycrypt.stdout.log").write_text(ec_stdout, encoding="utf-8")
        output.with_suffix(".easycrypt.stderr.log").write_text(ec_stderr, encoding="utf-8")

    return report, not errors


def _replay_check(
    report: dict[str, Any], errors: list[str], executable: Path,
    environment: dict[str, str], mode: str, upto: str | None,
) -> tuple[str, str]:
    command = easycrypt_command(executable, mode=mode, upto=upto)
    report["easycrypt_interaction"] = (
        "stateless_last_goals" if mode == "check"
        else "stateless_goal_at_location" if mode == "upto"
        else "full_file_acceptance"
    )
    check = run(command, environment=environment)
    ec_stdout, ec_stderr = check.stdout, check.stderr
    report["easycrypt_exit_code"] = check.returncode
    report["easycrypt_replay_outcome"] = easycrypt_replay_outcome(
        mode=mode, returncode=check.returncode, stdout=ec_stdout,
    )
    if mode in {"check", "upto"}:
        report["easycrypt_goal_output"] = ec_stdout
        report["easycrypt_error_output"] = ec_stderr
    report["easycrypt_stdout_tail"] = ec_stdout[-4000:]
    report["easycrypt_stderr_tail"] = ec_stderr[-4000:]
    if check.returncode != 0:
        errors.append(f"EasyCrypt replay failed with exit code {check.returncode}")
    return ec_stdout, ec_stderr


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument(
        "--check",
        action="store_true",
        help=(
            "development-time stateless whole-file EasyCrypt check; on "
            "failure return the native goals immediately before the rejected "
            "command; temporary admit shells are allowed only inside editable "
            "regions"
        ),
    )
    modes.add_argument(
        "--upto",
        metavar="LINE[:COL]",
        help=(
            "development-time stateless prefix replay; compile up to the "
            "pre-command source boundary, return the native current goals, "
            "and retain last goals if replay fails before that boundary"
        ),
    )
    modes.add_argument("--final", action="store_true")
    modes.add_argument("--check-import", action="store_true")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--lemma")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    mode = (
        "import"
        if args.check_import
        else "preflight"
        if args.preflight
        else "check"
        if args.check
        else "upto"
        if args.upto is not None
        else "final"
    )
    try:
        report, passed = verify(mode, args.output, upto=args.upto,
                                candidate=args.candidate, lemma=args.lemma)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
