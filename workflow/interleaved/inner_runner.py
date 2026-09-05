#!/usr/bin/env python3
"""Managed Shannon inner-node entry point for an interleaved project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from core.easycrypt.eval_source_prep import (
    find_target_proof_block,
    prepare_eval_source,
)
from core.easycrypt.ec_lifecycle import split_ec_commands
from workflow.interleaved.agent_config import (
    agent_profile_sha256,
    AgentProfile,
    profile_for,
    provider_identity_projection,
    provider_identity_sha256,
)
from workflow.interleaved.resume_contract import (
    CONTINUATION_NOTE_MAX_CHARS,
    directory_content_sha256,
    rebind_resume_capsule,
    select_resume_checkpoint,
)
from workflow.proof_tool.easycrypt_source_resource import (
    SOURCE_RESOURCE_MANIFEST_ENV,
)
from workflow.interleaved.warm_handoff import (
    prepare_outer_proof_handoff,
)
from workflow.interleaved.runtime import load_runtime_settings
from workflow.schemas.prover_result import (
    PROVER_RUN_INCOMPLETE,
    PROVER_RUN_INFRASTRUCTURE_INVALID,
    PROVER_RUN_VERIFIED,
    ProverResult,
)


_SETTINGS = load_runtime_settings()
ROOT = _SETTINGS.root
TARGET = _SETTINGS.project.target_file
INCLUDE_DIR = _SETTINGS.project.include_dirs[0]
ARTIFACT_ROOT = _SETTINGS.project.artifact_root
ANSWER_SOURCE = _SETTINGS.answer_source or ROOT / ".interleaved-no-answer-source"
LEMMA = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")
INVOCATION_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
INVOCATION_RECEIPT_KIND = "interleaved_shannon_invocation_receipt"
INVOCATION_RECEIPT_SCHEMA_VERSION = 3
RECEIPT_ENV = "INTERLEAVED_SHANNON_INVOCATION_RECEIPT"
RECEIPT_SHA256_ENV = "INTERLEAVED_SHANNON_INVOCATION_RECEIPT_SHA256"
WRAPPER_EXIT_CODES = {
    PROVER_RUN_VERIFIED: 0,
    PROVER_RUN_INCOMPLETE: 10,
    PROVER_RUN_INFRASTRUCTURE_INVALID: 20,
}
PARTIAL_PREFIX_MAX_BYTES = 64 * 1024
GUIDANCE_TEXT_MAX_CHARS = 2000
GUIDANCE_ITEMS_MAX = 5


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def prepare_shannon_eval_source(
    *,
    target_path: Path,
    lemma: str,
    output_root: Path,
):
    """Build the proof-stripped task bundle consumed by a Shannon run.

    ChaChaPoly's target imports task-local declarations, so the source boundary
    copies the complete task directory rather than the target file alone. The
    canonical source-preparation helper strips every proof in that bundle
    before either provider is launched.
    """

    return prepare_eval_source(
        source_file=target_path,
        target_lemma=lemma,
        output_dir=output_root / "eval_source",
        copy_root=target_path.parent,
        strip_proofs=True,
    )


def run_directory() -> tuple[Path, Path]:
    raw = os.environ.get("INTERLEAVED_RUN_DIR", "")
    relative = Path(raw)
    if not raw or relative.is_absolute() or ".." in relative.parts:
        raise SystemExit("INTERLEAVED_RUN_DIR must be a safe repository-relative path")
    resolved = (ROOT / relative).resolve()
    allowed = (ROOT / ARTIFACT_ROOT).resolve()
    if not resolved.is_relative_to(allowed):
        raise SystemExit("INTERLEAVED_RUN_DIR is outside the project artifact root")
    if not resolved.is_dir():
        raise SystemExit(f"run directory does not exist: {resolved}")
    return relative, resolved


def append_audit(path: Path, payload: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True) + "\n")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_sha256(value: dict[str, object]) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _load_invocation_receipt(
    *,
    run_rel: Path,
    run_dir: Path,
) -> tuple[dict[str, object], Path, str]:
    invocation_id = os.environ.get("INTERLEAVED_SHANNON_INVOCATION_ID", "").strip()
    if not INVOCATION_ID.fullmatch(invocation_id):
        raise ValueError("scheduler-owned invocation id is missing or invalid")
    raw_path = os.environ.get(RECEIPT_ENV, "").strip()
    claimed_sha256 = os.environ.get(RECEIPT_SHA256_ENV, "").strip()
    if not raw_path or not re.fullmatch(r"[0-9a-f]{64}", claimed_sha256):
        raise ValueError("scheduler-owned invocation receipt is missing")
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("invocation receipt path must be repository-relative")
    path = (ROOT / relative).resolve()
    allowed = (run_dir / "job_input" / invocation_id).resolve()
    if not path.is_relative_to(allowed) or not path.is_file():
        raise ValueError("invocation receipt is outside its scheduler-owned job input")
    raw = path.read_bytes()
    if _sha256_bytes(raw) != claimed_sha256:
        raise ValueError("invocation receipt byte hash mismatch")
    receipt = json.loads(raw)
    if not isinstance(receipt, dict):
        raise ValueError("invocation receipt must be a JSON object")
    if (
        receipt.get("schema_version") != INVOCATION_RECEIPT_SCHEMA_VERSION
        or receipt.get("kind") != INVOCATION_RECEIPT_KIND
        or receipt.get("job_id") != invocation_id
        or receipt.get("run_directory") != run_rel.as_posix()
    ):
        raise ValueError("invocation receipt identity mismatch")
    # The content hash is calculated with that field omitted so receipts are
    # stable and self-authenticating without recursive serialization.
    without_hash = dict(receipt)
    without_hash.pop("content_sha256", None)
    if _canonical_json_sha256(without_hash) != str(
        receipt.get("content_sha256") or ""
    ):
        raise ValueError("invocation receipt content hash mismatch")
    return receipt, path, claimed_sha256


def _canonical_prover_result(output_root: Path) -> tuple[ProverResult, Path]:
    """Load the only canonical result produced by this invocation root."""

    candidates = sorted(
        output_root.glob("*/iteration_1/prover_run_result.json")
    )
    if len(candidates) != 1:
        raise ValueError(
            "Shannon invocation must produce exactly one canonical "
            f"ProverResult, found {len(candidates)}"
        )
    result_path = candidates[0]
    result = ProverResult.load(result_path)
    summary_path = result_path.parent.parent / "summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"canonical Shannon summary is unreadable: {exc}") from exc
    if not isinstance(summary, dict):
        raise ValueError("canonical Shannon summary must be a JSON object")
    if summary.get("final_prover_result_id") != result.result_id:
        raise ValueError("canonical Shannon summary result identity mismatch")
    if summary.get("final_prover_result_status") != result.status:
        raise ValueError("canonical Shannon summary status mismatch")
    if summary.get("final_proved") is not result.is_verified:
        raise ValueError("canonical Shannon summary verified flag mismatch")
    return result, result_path


def _canonical_provider_identity(result_path: Path) -> tuple[dict[str, object], Path]:
    path = result_path.parent / "provider_identity.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"canonical provider identity is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("canonical provider identity must be a JSON object")
    if value.get("schema_version") != 1 or value.get("kind") != "provider_cli_identity":
        raise ValueError("canonical provider identity contract mismatch")
    required = (
        "agent_backend",
        "model",
        "binary",
        "resolved_path",
        "binary_sha256",
        "version",
    )
    if any(not isinstance(value.get(key), str) or not value.get(key) for key in required):
        raise ValueError("canonical provider identity has an empty required field")
    return value, path


def _canonical_source_boundary(
    *,
    expected_lemma: str,
    expected_source_manifest: Path,
    answer_source_visible_before: bool,
    answer_source_visible_during: bool,
    answer_source_visible_after: bool,
) -> tuple[dict[str, object], str]:
    """Bind the handback to the proof-stripped input used by this invocation."""

    try:
        manifest = json.loads(expected_source_manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"eval source manifest is unreadable: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("eval source manifest must be a JSON object")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("kind") != "eval_source_prep"
        or manifest.get("source_contract") != "proof_stripped_project"
        or manifest.get("strip_proofs") is not True
        or manifest.get("target_lemma") != expected_lemma
    ):
        raise ValueError("eval source manifest contract mismatch")
    if any(
        (
            answer_source_visible_before,
            answer_source_visible_during,
            answer_source_visible_after,
        )
    ):
        raise ValueError("answer-bearing source became visible during Shannon")
    record: dict[str, object] = {
        "schema_version": 1,
        "kind": "interleaved_shannon_source_boundary",
        "source_contract": "proof_stripped_project",
        "target_lemma": expected_lemma,
        "source_manifest": str(expected_source_manifest.resolve()),
        "source_manifest_sha256": _sha256_bytes(expected_source_manifest.read_bytes()),
        "answer_source_visible_before": False,
        "answer_source_visible_during": False,
        "answer_source_visible_after": False,
    }
    return record, str(record["source_manifest_sha256"])


def _identity_mismatches(
    expected: dict[str, object],
    actual: dict[str, object],
) -> list[str]:
    fields = tuple(provider_identity_projection(expected))
    return [
        key
        for key in fields
        if str(expected.get(key) or "") != str(actual.get(key) or "")
    ]


def _proof_body_span(content: str, lemma: str) -> tuple[str, tuple[int, int]]:
    block = find_target_proof_block(content, lemma)
    if block is None:
        raise ValueError(f"could not find proof block for {lemma}")
    start, end = block
    block_text = content[start:end]
    # The delegated proof body is every byte between the proof opener and
    # ``qed.``.  In particular, leading whitespace belongs to the body: proof
    # agents commonly indent their first tactic even when the admit shell was
    # unindented.  Excluding that whitespace manufactured an outside-body
    # drift during the final confined merge.
    proof = re.search(r"(?i)\bproof\s*\.", block_text)
    qed = list(re.finditer(r"(?i)\bqed\s*\.", block_text))
    if proof is None or not qed or qed[-1].start() < proof.end():
        raise ValueError(f"{lemma} has no proof./qed. block")
    body_start = start + proof.end()
    body_end = start + qed[-1].start()
    return content[body_start:body_end], (body_start, body_end)


def _merge_verified_proof(
    *,
    isolated_file: Path,
    target_file: Path,
    lemma: str,
    prepared_source: str,
    expected_target_sha256: str,
) -> dict[str, str]:
    isolated = isolated_file.read_text(encoding="utf-8")
    current = target_file.read_text(encoding="utf-8")
    if _sha256_bytes(current.encode("utf-8")) != expected_target_sha256:
        raise ValueError("canonical lane target drifted while Shannon was running")
    proof_body, (isolated_start, isolated_end) = _proof_body_span(isolated, lemma)
    _, (prepared_start, prepared_end) = _proof_body_span(prepared_source, lemma)
    isolated_projection = (
        isolated[:isolated_start] + "<TARGET-PROOF>" + isolated[isolated_end:]
    )
    prepared_projection = (
        prepared_source[:prepared_start]
        + "<TARGET-PROOF>"
        + prepared_source[prepared_end:]
    )
    if isolated_projection != prepared_projection:
        raise ValueError("confined source drifted outside the delegated proof body")
    if re.search(r"\badmit\b", proof_body, re.IGNORECASE):
        raise ValueError("confined verified proof still contains admit")
    _, (body_start, body_end) = _proof_body_span(current, lemma)
    merged = current[:body_start] + proof_body + current[body_end:]
    temporary = target_file.with_suffix(target_file.suffix + ".shannon.tmp")
    temporary.write_text(merged, encoding="utf-8")
    temporary.replace(target_file)
    return {
        "isolated_source_sha256": _sha256_bytes(isolated.encode("utf-8")),
        "merged_target_sha256": _sha256_bytes(merged.encode("utf-8")),
        "proof_body_sha256": _sha256_bytes(proof_body.encode("utf-8")),
    }


def _bounded_guidance_item(value: object) -> str:
    """Render one explicitly untrusted prover-report item within a hard bound."""

    if isinstance(value, str):
        rendered = value.strip()
    else:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return rendered[:GUIDANCE_TEXT_MAX_CHARS]


def _terminal_progress(
    *,
    result: ProverResult,
    result_path: Path,
    output_root: Path,
    lemma: str,
) -> tuple[dict[str, object], str]:
    """Build a bounded public progress capsule for any non-verified run.

    The accepted prefix is a reporting artifact produced from manager-owned
    committed history.  It is useful continuation evidence, but it is neither
    merged nor a terminal proof result and must be replayed before reuse.  The
    notes/report remain explicitly untrusted agent guidance.
    """

    progress: dict[str, object] = {
        "schema_version": 2,
        "kind": "interleaved_shannon_progress_capsule",
        "lemma": lemma,
        "turns": max(0, int(result.turns)),
        "elapsed_seconds": max(0.0, float(result.elapsed_seconds)),
    }
    checkpoint_artifact = ""

    prefix_metadata_path = result_path.parent / "partial_proof_prefix.json"
    prefix_path = result_path.parent / "partial_proof_prefix.ec"
    accepted_commands: tuple[str, ...] | None = None
    if prefix_metadata_path.is_file() and prefix_path.is_file():
        try:
            metadata = json.loads(prefix_metadata_path.read_text(encoding="utf-8"))
            if (
                not isinstance(metadata, dict)
                or metadata.get("kind") != "partial_proof_prefix"
                or metadata.get("schema_version") != 2
                or metadata.get("lemma") != lemma
                or metadata.get("closed_by_qed") is not False
                or not isinstance(metadata.get("tactic_count"), int)
                or metadata["tactic_count"] <= 0
                or not isinstance(metadata.get("byte_count"), int)
                or metadata["byte_count"] <= 0
                or not re.fullmatch(
                    r"[0-9a-f]{64}", str(metadata.get("sha256") or "")
                )
                or metadata.get("source")
                != "manager_session_history_or_resume_capsule"
                or metadata.get("replay_required_before_use") is not True
            ):
                raise ValueError("invalid manager partial-prefix metadata")
            prefix_bytes = prefix_path.read_bytes()
            prefix_text = prefix_bytes.decode("utf-8")
            if (
                len(prefix_bytes) != metadata["byte_count"]
                or _sha256_bytes(prefix_bytes) != metadata["sha256"]
            ):
                raise ValueError("manager partial-prefix bytes do not match metadata")
            accepted_commands = tuple(
                command.strip()
                for command in split_ec_commands(prefix_text)
                if command.strip()
            )
            if len(accepted_commands) != metadata["tactic_count"]:
                raise ValueError(
                    "manager partial-prefix command count does not match metadata"
                )
            if re.search(r"(?i)\b(?:admit|qed)\s*\.", prefix_text):
                raise ValueError("manager partial prefix contains a terminal escape")
            accepted_prefix: dict[str, object] = {
                "tactic_count": metadata["tactic_count"],
                "sha256": _sha256_bytes(prefix_bytes),
                "byte_count": len(prefix_bytes),
                "authority": "manager_committed_history_reporting_artifact",
                "replay_required_before_use": True,
            }
            if len(prefix_bytes) <= PARTIAL_PREFIX_MAX_BYTES:
                accepted_prefix["text"] = prefix_text
            else:
                accepted_prefix["text_omitted_reason"] = (
                    "accepted prefix exceeds the public handback byte limit"
                )
            progress["accepted_prefix"] = accepted_prefix
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            progress["accepted_prefix_unavailable"] = (
                f"{type(exc).__name__}: {exc}"
            )[:GUIDANCE_TEXT_MAX_CHARS]

    selected = select_resume_checkpoint(
        result.resume_capsules,
        allowed_root=result_path.parent / "resume_capsules",
        lemma=lemma,
        accepted_prefix=accepted_commands,
    )
    if selected is not None:
        if "accepted_prefix" not in progress:
            prefix_bytes = selected.prefix_text.encode("utf-8")
            accepted_prefix = {
                "tactic_count": selected.capsule.tactic_count,
                "sha256": _sha256_bytes(prefix_bytes),
                "byte_count": len(prefix_bytes),
                "authority": "manager_committed_history_reporting_artifact",
                "replay_required_before_use": True,
            }
            if len(prefix_bytes) <= PARTIAL_PREFIX_MAX_BYTES:
                accepted_prefix["text"] = selected.prefix_text
            else:
                accepted_prefix["text_omitted_reason"] = (
                    "accepted prefix exceeds the public handback byte limit"
                )
            progress["accepted_prefix"] = accepted_prefix
        progress["checkpoint"] = selected.public
        accepted_count = int(
            dict(progress.get("accepted_prefix") or {}).get("tactic_count") or 0
        )
        checkpoint_count = selected.capsule.tactic_count
        if checkpoint_count < accepted_count:
            progress["uncheckpointed_tail_tactics"] = (
                accepted_count - checkpoint_count
            )
        checkpoint_artifact = selected.manifest_path.relative_to(
            output_root.resolve()
        ).as_posix()

    guidance: dict[str, object] = {
        "authority": "untrusted_inner_agent_report",
    }
    prior_guidance: dict[str, object] = {}
    if selected is not None and isinstance(selected.capsule.resume_context, dict):
        prior_brief = selected.capsule.resume_context.get("continuation_brief")
        if isinstance(prior_brief, dict):
            prior_guidance = prior_brief
    report_matches_checkpoint = selected is None or (
        bool(result.ec_session_dir)
        and selected.capsule.session_name == Path(result.ec_session_dir).name
    )
    report = (
        result.report
        if report_matches_checkpoint and isinstance(result.report, dict)
        else {}
    )
    for key in ("blockers", "discoveries"):
        raw_items = (
            report[key]
            if key in report
            else prior_guidance.get(key)
        )
        if not isinstance(raw_items, list):
            continue
        items: list[str] = []
        for item in raw_items[:GUIDANCE_ITEMS_MAX]:
            rendered = _bounded_guidance_item(item)
            if rendered:
                items.append(rendered)
        if items:
            guidance[key] = items
    if len(guidance) > 1:
        progress["agent_guidance"] = guidance
    raw_breadcrumbs = prior_guidance.get("source_breadcrumbs")
    if isinstance(raw_breadcrumbs, list) and raw_breadcrumbs:
        progress["source_breadcrumbs"] = {
            "authority": "manager_observed_source_navigation",
            "items": raw_breadcrumbs[:12],
        }

    if isinstance(progress.get("checkpoint"), dict):
        progress["next_actions"] = [
            "resume_checkpoint",
            "replay_prefix_in_outer",
            "fresh_restart",
            "redesign_boundary",
        ]
    elif "accepted_prefix" in progress:
        progress["next_actions"] = [
            "replay_prefix_in_outer",
            "warm_handoff",
            "redesign_boundary",
        ]
    else:
        progress["next_actions"] = [
            "fresh_restart",
            "redesign_boundary",
        ]

    if "accepted_prefix" not in progress and "agent_guidance" not in progress:
        progress["summary"] = (
            "No reusable accepted prefix or structured blocker was produced; "
            "redesign the boundary before retrying."
        )
    return progress, checkpoint_artifact


def _wrapper_handback(
    *,
    output_root: Path,
    invocation_id: str,
    lemma: str,
    process_exit_code: int | None,
    wrapper_error: str,
    inner_provider: str,
    inner_model: str,
    inner_effort: str,
    expected_provider_identity: dict[str, object],
    invocation_receipt_sha256: str,
    expected_source_manifest: Path,
    answer_source_visible_before: bool = False,
    answer_source_visible_during: bool = False,
    answer_source_visible_after: bool = False,
) -> dict[str, object]:
    """Project one bounded public result from the canonical ProverResult."""

    errors: list[str] = []
    result: ProverResult | None = None
    result_path: Path | None = None
    provider_identity: dict[str, object] = {}
    provider_identity_path: Path | None = None
    source_boundary: dict[str, object] = {}
    source_manifest_sha256 = ""
    progress: dict[str, object] = {}
    resume_checkpoint_artifact = ""
    try:
        result, result_path = _canonical_prover_result(output_root)
        if result.status == PROVER_RUN_INFRASTRUCTURE_INVALID:
            for item in [result.error, *result.infrastructure_errors]:
                message = str(item or "").strip()
                if message and message not in errors:
                    errors.append(message[:2000])
        provider_identity, provider_identity_path = _canonical_provider_identity(
            result_path
        )
        mismatches = _identity_mismatches(
            expected_provider_identity,
            provider_identity,
        )
        if mismatches:
            errors.append(
                "actual provider identity mismatch: " + ", ".join(mismatches)
            )
        source_boundary, source_manifest_sha256 = _canonical_source_boundary(
            expected_lemma=lemma,
            expected_source_manifest=expected_source_manifest,
            answer_source_visible_before=answer_source_visible_before,
            answer_source_visible_during=answer_source_visible_during,
            answer_source_visible_after=answer_source_visible_after,
        )
        if result.status != PROVER_RUN_VERIFIED:
            progress, resume_checkpoint_artifact = _terminal_progress(
                result=result,
                result_path=result_path,
                output_root=output_root,
                lemma=lemma,
            )
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    if wrapper_error:
        errors.append(wrapper_error)
    if process_exit_code not in {0, None}:
        errors.append(f"orchestrator exited with code {process_exit_code}")

    if errors or result is None:
        status = PROVER_RUN_INFRASTRUCTURE_INVALID
    else:
        status = result.status
    if status == PROVER_RUN_INFRASTRUCTURE_INVALID and not errors:
        errors.append("missing_terminal_failure_reason")
    failure_class = (
        "prover_result_infrastructure_invalid"
        if result is not None
        and result.status == PROVER_RUN_INFRASTRUCTURE_INVALID
        else "wrapper_infrastructure_invalid"
        if status == PROVER_RUN_INFRASTRUCTURE_INVALID
        else ""
    )
    if progress:
        progress["terminal"] = {
            "status": status,
            "cause": failure_class or "proof_search_incomplete",
            "message": "; ".join(errors)[:2000],
        }
    return {
        "schema_version": 1,
        "kind": "interleaved_shannon_wrapper_result",
        "invocation_id": invocation_id,
        "lemma": lemma,
        "inner_provider": inner_provider,
        "inner_model": inner_model,
        "inner_effort": inner_effort,
        "invocation_receipt_sha256": invocation_receipt_sha256,
        "provider_identity": provider_identity,
        "provider_identity_sha256": (
            provider_identity_sha256(provider_identity)
            if provider_identity_path is not None
            else ""
        ),
        "eval_source_boundary": source_boundary,
        "eval_source_manifest_sha256": source_manifest_sha256,
        "status": status,
        "verified": status == PROVER_RUN_VERIFIED,
        "process_exit_code": process_exit_code,
        "prover_result_id": result.result_id if result is not None else "",
        "prover_result_status": result.status if result is not None else "",
        "prover_result_artifact": (
            str(result_path.relative_to(output_root))
            if result_path is not None
            else ""
        ),
        "infrastructure_errors": errors,
        "failure_class": failure_class,
        "failure_message": "; ".join(errors)[:4000],
        "progress": progress,
        "resume_checkpoint_artifact": resume_checkpoint_artifact,
    }


def build_shannon_command(
    profile: AgentProfile,
    *,
    target: str = TARGET,
    lemma: str,
    timeout_minutes: int,
    output: Path,
) -> list[str]:
    """Build one managed proof-node command from the selected inner profile."""

    return [
        sys.executable,
        "-m",
        "workflow.orchestrator",
        "--file",
        target,
        "--lemma",
        lemma,
        "--include-dir",
        INCLUDE_DIR,
        "--surface-profile",
        "proof_state_compiler",
        "--agent-backend",
        profile.backend,
        "--prover-model",
        profile.model,
        "--prover-effort",
        profile.effort,
        "--eval-mode",
        "--max-iterations",
        "1",
        "--prover-timeout-minutes",
        str(timeout_minutes),
        "--tree-initial-provers",
        "1",
        "--tree-max-concurrent",
        "1",
        "--output-dir",
        output.as_posix(),
    ]


def _run_orchestrator_process(
    command: list[str],
    *,
    environment: dict[str, str],
    interruption_requested: Callable[[], bool],
    grace_seconds: float = 60.0,
) -> tuple[int, str]:
    """Run one isolated orchestrator and preserve its checkpoint on SIGTERM."""

    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        start_new_session=True,
    )
    interrupt_sent = False
    interrupt_deadline: float | None = None
    while True:
        try:
            return process.wait(timeout=0.25), ""
        except subprocess.TimeoutExpired:
            if not interruption_requested():
                continue
            if not interrupt_sent:
                # SIGINT enters the orchestrator's normal KeyboardInterrupt
                # boundary, which archives the best manager-owned session.
                try:
                    os.killpg(process.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
                interrupt_sent = True
                interrupt_deadline = time.monotonic() + grace_seconds
                continue
            if (
                interrupt_deadline is None
                or time.monotonic() < interrupt_deadline
            ):
                continue
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                exit_code = process.wait(timeout=4.0)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                exit_code = process.wait()
            return exit_code, (
                "managed safe-stop handback exceeded its cooperative "
                "shutdown grace"
            )


def _prepare_outer_handoff_with_daemon_cleanup(**kwargs: object) -> Path:
    """Prepare one warm handoff without leaking its bootstrap EC daemon.

    Handoff certification runs before the inner orchestrator configures and
    owns its per-run daemon. Its short-lived proof managers close their own
    sessions, but the detached default daemon is process-scoped and otherwise
    survives cancellation as an orphan. This wrapper owns that exact socket
    for the preparation call and tears it down on success or failure.
    """

    from core.easycrypt.ec_daemon_client import default_socket_path
    from workflow.agents.ec_services import _shutdown_ec_daemon

    socket_path = default_socket_path()
    try:
        return prepare_outer_proof_handoff(**kwargs)
    finally:
        _shutdown_ec_daemon(
            reason="outer proof handoff preparation finished",
            socket_path=socket_path,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lemma", required=True)
    parser.add_argument("--timeout-minutes", type=int, required=True)
    parser.add_argument(
        "--handoff-current",
        action="store_true",
        help=(
            "certify the longest accepted prefix of the outer candidate and "
            "warm-start the managed proof node at its first rejected tactic"
        ),
    )
    parser.add_argument(
        "--strategy-note",
        help="repository-relative same-run note passed to the inner proof node",
    )
    parser.add_argument(
        "--resource-anchors",
        help=(
            "repository-relative same-run JSON list of exact EasyCrypt symbols, "
            "intended uses, and roles to resolve and persist in the warm handoff"
        ),
    )
    parser.add_argument(
        "--candidate-source",
        help=(
            "repository-relative candidate snapshot in this run or the "
            "disclosed immediately preceding continuation"
        ),
    )
    parser.add_argument(
        "--resume-capsule",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--continuation-note",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if not LEMMA.fullmatch(args.lemma):
        parser.error("--lemma is not a valid EasyCrypt identifier")
    if not 1 <= args.timeout_minutes <= _SETTINGS.project.max_inner_minutes:
        parser.error(
            "--timeout-minutes must be between 1 and "
            f"{_SETTINGS.project.max_inner_minutes}"
        )
    if args.handoff_current and not args.strategy_note:
        parser.error("--handoff-current requires --strategy-note")
    if args.handoff_current and args.resume_capsule:
        parser.error("warm handoff and managed checkpoint resume are exclusive")
    if args.continuation_note and not args.resume_capsule:
        parser.error("--continuation-note requires a managed checkpoint resume")
    if not args.handoff_current and (
        args.strategy_note or args.resource_anchors or args.candidate_source
    ):
        parser.error(
            "--strategy-note/--resource-anchors/--candidate-source require "
            "--handoff-current"
        )
    run_rel, run_dir = run_directory()
    try:
        receipt, receipt_path, receipt_sha256 = _load_invocation_receipt(
            run_rel=run_rel,
            run_dir=run_dir,
        )
    except Exception as exc:
        parser.error(str(exc))
    invocation_id = str(receipt["job_id"])
    if receipt.get("lemma") != args.lemma:
        parser.error("invocation receipt lemma mismatch")
    if receipt.get("timeout_minutes") != args.timeout_minutes:
        parser.error("invocation receipt timeout mismatch")
    if bool(args.resource_anchors) != bool(receipt.get("has_resource_anchors")):
        parser.error("invocation receipt resource-anchor presence mismatch")
    if bool(args.resume_capsule) != bool(receipt.get("has_resume_checkpoint")):
        parser.error("invocation receipt resume-checkpoint presence mismatch")
    if bool(args.continuation_note) != bool(
        receipt.get("has_continuation_note")
    ):
        parser.error("invocation receipt continuation-note presence mismatch")
    if args.resource_anchors:
        anchor_relative = Path(args.resource_anchors)
        if anchor_relative.is_absolute() or ".." in anchor_relative.parts:
            parser.error("resource anchors path is not repository-relative")
        anchor_path = (ROOT / anchor_relative).resolve()
        if (
            not anchor_path.is_file()
            or _sha256_bytes(anchor_path.read_bytes())
            != receipt.get("resource_anchors_sha256")
        ):
            parser.error("invocation receipt resource-anchor hash mismatch")
    resume_manifest: Path | None = None
    continuation_note = ""
    if args.resume_capsule:
        resume_relative = Path(args.resume_capsule)
        if resume_relative.is_absolute() or ".." in resume_relative.parts:
            parser.error("resume capsule path is not repository-relative")
        resume_manifest = (ROOT / resume_relative).resolve()
        allowed_resume = (
            run_dir / "job_input" / invocation_id / "resume_capsule"
        ).resolve()
        if (
            not resume_manifest.is_file()
            or not resume_manifest.is_relative_to(allowed_resume)
            or resume_manifest.name != "resume.json"
        ):
            parser.error("resume capsule is outside scheduler-owned job input")
        if directory_content_sha256(resume_manifest.parent) != receipt.get(
            "resume_checkpoint_directory_sha256"
        ):
            parser.error("invocation receipt resume-checkpoint hash mismatch")
    if args.continuation_note:
        note_relative = Path(args.continuation_note)
        if note_relative.is_absolute() or ".." in note_relative.parts:
            parser.error("continuation note path is not repository-relative")
        note_path = (ROOT / note_relative).resolve()
        allowed_note = (
            run_dir / "job_input" / invocation_id / "continuation_note.md"
        ).resolve()
        if note_path != allowed_note or not note_path.is_file():
            parser.error("continuation note is outside scheduler-owned job input")
        note_bytes = note_path.read_bytes()
        if _sha256_bytes(note_bytes) != receipt.get("continuation_note_sha256"):
            parser.error("invocation receipt continuation-note hash mismatch")
        try:
            continuation_note = note_bytes.decode("utf-8")
        except UnicodeDecodeError:
            parser.error("continuation note must be UTF-8")
        if (
            not continuation_note.strip()
            or len(continuation_note) > CONTINUATION_NOTE_MAX_CHARS
        ):
            parser.error("continuation note must contain 1 to 8000 characters")
    inner_agent = receipt.get("inner_agent")
    if not isinstance(inner_agent, dict):
        parser.error("invocation receipt is missing inner agent identity")
    inner_profile = profile_for(str(inner_agent.get("profile") or ""))
    if inner_agent != inner_profile.base_dict():
        parser.error("invocation receipt inner profile does not match committed config")
    expected_inner_profile_hash = os.environ.get(
        "INTERLEAVED_INNER_PROFILE_SHA256", ""
    ).strip()
    actual_inner_profile_hash = agent_profile_sha256(inner_profile)
    if (
        not expected_inner_profile_hash
        or expected_inner_profile_hash != actual_inner_profile_hash
        or receipt.get("inner_profile_sha256") != actual_inner_profile_hash
    ):
        parser.error("selected inner profile does not match the active run")
    expected_provider_identity = receipt.get("expected_provider_identity")
    if not isinstance(expected_provider_identity, dict):
        parser.error("invocation receipt is missing expected provider identity")
    if (
        expected_provider_identity.get("agent_backend") != inner_profile.backend
        or expected_provider_identity.get("model") != inner_profile.model
    ):
        parser.error("invocation receipt provider identity does not match inner profile")
    target_path = ROOT / TARGET
    if _sha256_bytes(target_path.read_bytes()) != receipt.get("target_sha256"):
        parser.error("lane target does not match the scheduler submission")
    current_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if (
        current_commit.returncode != 0
        or current_commit.stdout.strip() != receipt.get("source_commit")
    ):
        parser.error("lane commit does not match the scheduler submission")
    if ANSWER_SOURCE.exists():
        parser.error("answer-bearing source is visible before Shannon launch")
    output = run_rel / "shannon" / args.lemma / invocation_id
    output_root = ROOT / output
    output_root.mkdir(parents=True, exist_ok=False)
    prepared = prepare_shannon_eval_source(
        target_path=target_path,
        lemma=args.lemma,
        output_root=output_root,
    )
    prepared_source = prepared.isolated_file.read_text(encoding="utf-8")
    managed_target = prepared.isolated_file.relative_to(ROOT).as_posix()
    source_manifest = output_root / "eval_source" / "source_manifest.json"
    command = build_shannon_command(
        inner_profile,
        target=managed_target,
        lemma=args.lemma,
        timeout_minutes=args.timeout_minutes,
        output=output,
    )
    if resume_manifest is not None:
        try:
            rebind_resume_capsule(
                resume_manifest,
                target_file=managed_target,
                parent_job_id=str(receipt.get("resume_from_job_id") or ""),
                checkpoint_id=str(receipt.get("resume_checkpoint_id") or ""),
                continuation_note=continuation_note,
            )
        except Exception as exc:
            parser.error(f"managed checkpoint rebind failed: {exc}")
        command.extend([
            "--resume-capsule",
            str(resume_manifest.relative_to(ROOT)),
        ])
    audit = run_dir / "shannon_invocations.jsonl"
    answer_source_visible_before = ANSWER_SOURCE.exists()
    answer_source_visible_during = False
    exit_code: int | None = None
    error = ""
    interruption_requested = False
    handoff_path: Path | None = None

    def request_interruption(_signum: int, _frame: object) -> None:
        nonlocal interruption_requested
        interruption_requested = True

    try:
        if args.handoff_current:
            append_audit(
                audit,
                {
                    "event": "handoff_preparing",
                    "at": timestamp(),
                    "invocation_id": invocation_id,
                    "lemma": args.lemma,
                    "strategy_note": args.strategy_note,
                    "resource_anchors": args.resource_anchors,
                    "candidate_source": args.candidate_source,
                },
            )
        previous_sigterm = signal.signal(signal.SIGTERM, request_interruption)
        try:
            if args.handoff_current:
                handoff_path = _prepare_outer_handoff_with_daemon_cleanup(
                    root=ROOT,
                    run_rel=run_rel,
                    lemma=args.lemma,
                    strategy_note=str(args.strategy_note),
                    resource_anchors=args.resource_anchors,
                    candidate_source=args.candidate_source,
                    runtime_target_file=managed_target,
                )
                command.extend(
                    ["--outer-proof-handoff", str(handoff_path.relative_to(ROOT))]
                )
            append_audit(
                audit,
                {
                    "event": "started",
                    "at": timestamp(),
                    "invocation_id": invocation_id,
                    "lemma": args.lemma,
                    "timeout_minutes": args.timeout_minutes,
                    "inner_agent": inner_profile.base_dict(),
                    "expected_provider_identity": expected_provider_identity,
                    "invocation_receipt": str(receipt_path.relative_to(ROOT)),
                    "invocation_receipt_sha256": receipt_sha256,
                    "source_manifest": str(source_manifest.relative_to(ROOT)),
                    "managed_target": managed_target,
                    "command": command,
                    "outer_proof_handoff": (
                        str(handoff_path.relative_to(ROOT)) if handoff_path else None
                    ),
                    "resume_from_job_id": receipt.get("resume_from_job_id"),
                    "resume_from_run_directory": receipt.get(
                        "resume_from_run_directory"
                    ),
                    "resume_checkpoint_id": receipt.get("resume_checkpoint_id"),
                    "has_continuation_note": bool(continuation_note),
                    "answer_source_visible_before": answer_source_visible_before,
                    "answer_source_visible_during_trusted_call": ANSWER_SOURCE.exists(),
                },
            )
            answer_source_visible_during = ANSWER_SOURCE.exists()
            environment = os.environ.copy()
            # The explicit output directory above is the experiment-owned
            # complete audit artifact. Suppress the orchestrator's additional
            # legacy agent_view_runs bundle so a trusted Shannon invocation
            # cannot dirty the confined outer-agent worktree.
            environment["SHANNON_SUITE_WILL_BUNDLE"] = "1"
            environment[SOURCE_RESOURCE_MANIFEST_ENV] = str(
                source_manifest.relative_to(ROOT)
            )
            exit_code, process_error = _run_orchestrator_process(
                command,
                environment=environment,
                interruption_requested=lambda: interruption_requested,
            )
            if process_error:
                error = process_error
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        append_audit(
            audit,
            {
                "event": "finished",
                "at": timestamp(),
                "invocation_id": invocation_id,
                "lemma": args.lemma,
                "exit_code": exit_code,
                "error": error,
                "interruption_requested": interruption_requested,
                "outer_proof_handoff": (
                    str(handoff_path.relative_to(ROOT)) if handoff_path else None
                ),
                "answer_source_visible_after": ANSWER_SOURCE.exists(),
            },
        )
    handback = _wrapper_handback(
        output_root=output_root,
        invocation_id=invocation_id,
        lemma=args.lemma,
        process_exit_code=exit_code,
        wrapper_error=error,
        inner_provider=inner_profile.key,
        inner_model=inner_profile.model,
        inner_effort=inner_profile.effort,
        expected_provider_identity=expected_provider_identity,
        invocation_receipt_sha256=receipt_sha256,
        expected_source_manifest=source_manifest,
        answer_source_visible_before=answer_source_visible_before,
        answer_source_visible_during=answer_source_visible_during,
        answer_source_visible_after=ANSWER_SOURCE.exists(),
    )
    if handback["verified"]:
        try:
            handback["proof_merge"] = _merge_verified_proof(
                isolated_file=prepared.isolated_file,
                target_file=target_path,
                lemma=args.lemma,
                prepared_source=prepared_source,
                expected_target_sha256=str(receipt["target_sha256"]),
            )
        except Exception as exc:
            handback["status"] = PROVER_RUN_INFRASTRUCTURE_INVALID
            handback["verified"] = False
            handback["infrastructure_errors"].append(
                f"isolated proof merge failed: {type(exc).__name__}: {exc}"
            )
    handback_path = output_root / "wrapper_result.json"
    handback_path.write_text(
        json.dumps(handback, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    append_audit(
        audit,
        {
            "event": "canonical_result_projected",
            "at": timestamp(),
            "invocation_id": invocation_id,
            "lemma": args.lemma,
            "status": handback["status"],
            "verified": handback["verified"],
            "prover_result_id": handback["prover_result_id"],
            "wrapper_result": str(handback_path.relative_to(ROOT)),
        },
    )
    print(json.dumps(handback, indent=2, sort_keys=True))
    return WRAPPER_EXIT_CODES[str(handback["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
