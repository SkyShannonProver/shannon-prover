"""Prepare a current-project outer-to-inner proof handoff."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.easycrypt.compiler_resource_loader import (
    RuntimeDeclarationRequest,
    load_requested_declarations,
)
from core.easycrypt.ec_daemon import _split_ec_commands
from core.easycrypt.eval_source_prep import find_target_proof_block
from workflow.node.outer_proof_handoff import (
    HANDOFF_KIND,
    HANDOFF_VERSION,
    RESOURCE_ANCHOR_MAX,
    proof_command_sequence_sha256,
)
from workflow.node.proof_node_manager import ProofNodeManager
from workflow.proof_management.tactic_utils import strip_easycrypt_comments
from workflow.interleaved.runtime import load_runtime_settings


_SETTINGS = load_runtime_settings()
TARGET = _SETTINGS.project.target_file
INCLUDE_DIR = _SETTINGS.project.include_dirs[0]
_CLOSER = re.compile(
    r"(?i)^\s*(?:[+*\-]\s*)?(?:qed|admit|abort|exit)\s*\.\s*$"
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _proof_body(content: str, lemma: str) -> tuple[str, tuple[int, int]]:
    block = find_target_proof_block(content, lemma)
    if block is None:
        raise ValueError(f"could not find proof block for {lemma}")
    start, end = block
    text = content[start:end]
    proof = re.search(r"(?i)\bproof\s*\.\s*", text)
    qed = list(re.finditer(r"(?i)\bqed\s*\.", text))
    if proof is None or not qed or qed[-1].start() < proof.end():
        raise ValueError(f"{lemma} does not have a proof./qed. candidate block")
    return text[proof.end():qed[-1].start()], block


def _lemma_prefix_projection(content: str, lemma: str) -> str:
    """Normalize the delegated proof and ignore declarations after it.

    A continuation may replace later, not-yet-proved lemmas with admit shells
    solely to keep the current target loadable.  Those later declarations
    cannot participate in the proof of ``lemma``.  Binding the handoff through
    the end of the selected lemma therefore preserves every relevant source
    byte while allowing a loadable continuation seed to differ in its suffix.
    """
    block = find_target_proof_block(content, lemma)
    if block is None:
        raise ValueError(f"could not project proof block for {lemma}")
    start, _ = block
    return content[:start] + "proof.\n  admit.\nqed."


def _resolve_candidate(
    *,
    root: Path,
    run_dir: Path,
    candidate_source: str | None,
) -> Path:
    if not candidate_source:
        return (root / TARGET).resolve()
    relative = Path(candidate_source)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("handoff candidate must be a safe repository-relative path")
    resolved = (root / relative).resolve()
    allowed = [run_dir.resolve()]
    prior_raw = str(os.environ.get("INTERLEAVED_CONTINUATION_OF", ""))
    if prior_raw:
        prior = Path(prior_raw)
        if not prior.is_absolute() and ".." not in prior.parts:
            allowed.append((root / prior).resolve())
    if not any(resolved.is_relative_to(item) for item in allowed):
        raise ValueError(
            "handoff candidate must be inside the current run or its disclosed continuation"
        )
    if not resolved.is_file():
        raise ValueError(f"handoff candidate does not exist: {resolved}")
    return resolved


def _resolve_strategy_note(*, root: Path, run_dir: Path, raw: str) -> tuple[Path, str]:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("strategy note must be a safe repository-relative path")
    path = (root / relative).resolve()
    if not path.is_relative_to(run_dir.resolve()) or not path.is_file():
        raise ValueError("strategy note must be an existing file in the current run")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("strategy note must not be empty")
    if len(text) > 8000:
        raise ValueError("strategy note exceeds 8000 characters")
    return path, text


def _resolve_resource_anchors(
    *,
    root: Path,
    run_dir: Path,
    raw: str | None,
    context_source: str,
    context_source_ref: str,
    lemma: str,
    source_dir: Path,
) -> tuple[Path | None, list[dict[str, str]]]:
    """Resolve explicit handoff resources through EasyCrypt, never prose mining."""

    if not raw:
        return None, []
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("resource anchors must be a safe repository-relative path")
    path = (root / relative).resolve()
    if not path.is_relative_to(run_dir.resolve()) or not path.is_file():
        raise ValueError("resource anchors must be an existing file in the current run")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"could not read resource anchors: {exc}") from exc
    if not isinstance(value, list) or not 1 <= len(value) <= RESOURCE_ANCHOR_MAX:
        raise ValueError(
            f"resource anchors must be a JSON list of 1..{RESOURCE_ANCHOR_MAX} objects"
        )
    requested: list[dict[str, str]] = []
    symbols: list[str] = []
    allowed_uses = {"apply", "call", "exact", "rewrite", "smt", "reference"}
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"resource anchor {index} must be an object")
        symbol = str(item.get("symbol") or "").strip()
        intended_use = str(item.get("intended_use") or "").strip()
        role = str(item.get("role") or "").strip()
        if (
            not symbol
            or not all(
                part
                and (part[0].isalpha() or part[0] == "_")
                and all(char.isalnum() or char in "_'" for char in part)
                for part in symbol.split(".")
            )
        ):
            raise ValueError(f"resource anchor {index} has an invalid symbol")
        if symbol in symbols:
            raise ValueError(f"duplicate resource anchor {symbol!r}")
        if intended_use not in allowed_uses:
            raise ValueError(
                f"resource anchor {symbol!r} has invalid intended_use {intended_use!r}"
            )
        if not role or len(role) > 500:
            raise ValueError(f"resource anchor {symbol!r} requires a bounded role")
        symbols.append(symbol)
        requested.append({
            "symbol": symbol,
            "intended_use": intended_use,
            "role": role,
        })

    block = find_target_proof_block(context_source, lemma)
    if block is None:
        raise ValueError(f"could not build resource-anchor context for {lemma}")
    start, end = block
    proof = re.search(r"(?i)\bproof\s*\.\s*", context_source[start:end])
    if proof is None:
        raise ValueError(f"resource-anchor context for {lemma} has no proof opener")
    active_context = context_source[: start + proof.end()]
    active_context_sha256 = _sha256_text(active_context)
    descriptor, raw_context = tempfile.mkstemp(
        prefix="shannon_outer_handoff_", suffix=".ec"
    )
    context_file = Path(raw_context)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(active_context)
            if not active_context.endswith("\n"):
                stream.write("\n")
        result = load_requested_declarations(
            (RuntimeDeclarationRequest(
                request_id="outer-handoff-resource-anchors",
                producer_id="outer_proof_handoff.resource_anchors",
                query_kind="symbol_declarations",
                scope="",
                declaration_kinds=("lemma", "axiom"),
                member_name_terms=(),
                max_results=len(symbols),
                symbols=tuple(symbols),
            ),),
            context_file=context_file,
            include_dirs=(
                root / "easycrypt-src" / "theories",
                source_dir,
            ),
        )
    finally:
        try:
            context_file.unlink()
        except OSError:
            pass
    by_symbol = {
        str(item.get("symbol") or ""): item
        for item in result.declarations
        if isinstance(item, dict)
    }
    missing = [symbol for symbol in symbols if symbol not in by_symbol]
    if missing:
        raise ValueError(
            "resource anchors did not resolve exactly in EasyCrypt: "
            + ", ".join(missing)
        )
    anchored: list[dict[str, str]] = []
    for item in requested:
        declaration = by_symbol[item["symbol"]]
        anchored.append({
            **item,
            "source_ref": (
                f"easycrypt-native:print:{context_source_ref}"
                f"@sha256:{active_context_sha256}#{item['symbol']}"
            ),
            "declaration_sha256": str(declaration["declaration_sha256"]),
            "declaration": str(declaration["declaration"]),
        })
    return path, anchored


def _failure_summary(view: dict[str, Any]) -> str:
    result = view.get("last_result")
    if not isinstance(result, dict) or not result:
        return "The candidate tactic did not extend the manager-owned committed prefix."
    return json.dumps(result, ensure_ascii=False, sort_keys=True)[:8000]


def _goal_preview(view: dict[str, Any]) -> str:
    current = view.get("current_goal")
    if not isinstance(current, dict):
        return ""
    lines = current.get("lines")
    if isinstance(lines, list):
        return "\n".join(str(item) for item in lines)[:20000]
    return str(current.get("text") or "")[:20000]


def _candidate_step_kept(
    *,
    accepted: list[str],
    committed: list[str],
) -> bool:
    """Accept any monotonic manager expansion of one candidate command."""

    return len(committed) > len(accepted) and committed[: len(accepted)] == accepted


def _candidate_commands(body: str) -> list[str]:
    """Return complete replay units up to the first proof closer.

    A closer can occur inside a multi-goal development (for example
    ``+ admit.``), so deleting it and retaining later commands splices together
    two states that were never connected by a replayable proof.  The only safe
    non-admitting handoff is the complete-command prefix before that closer.
    """

    commands: list[str] = []
    for item in _split_ec_commands(body):
        command = item.strip()
        if not command:
            continue
        # The source splitter intentionally carries comment-only lines into the
        # next EasyCrypt command.  Detect closers on the semantic command, not
        # the byte-preserving replay text, so the standard eval placeholder
        # ``(* PROVE THIS ... *)\n  admit.`` cannot be replayed as a candidate.
        semantic_command = strip_easycrypt_comments(command).strip()
        if _CLOSER.fullmatch(semantic_command) is not None:
            break
        commands.append(command)
    return commands


def _certify_fresh_replay(
    *,
    root: Path,
    lemma: str,
    replay_commands: list[str],
    expected_committed_spine: list[str],
    expected_goal_hash: str,
    run_dir: Path,
) -> None:
    """Require a fresh manager to reproduce the prepared semantic boundary."""

    session_tag = f"prover_{uuid.uuid4().hex[:12]}_tree_0_0"
    manager = ProofNodeManager(
        file_path=TARGET,
        lemma_name=lemma,
        include_dir=INCLUDE_DIR,
        session_tag=session_tag,
        node_id="Tree-0.0-replay-certification",
        run_dir=run_dir,
        project_root=root,
        surface_profile="proof_state_compiler",
    )
    try:
        bootstrap = manager.bootstrap(replay_prefix=replay_commands)
        _write_json(run_dir / "bootstrap.json", bootstrap)
    finally:
        manager.close_session()

    actual_spine = list(bootstrap.get("replay_prefix") or [])
    if proof_command_sequence_sha256(actual_spine) != proof_command_sequence_sha256(
        expected_committed_spine
    ):
        raise RuntimeError(
            "outer proof handoff fresh replay changed the committed proof spine"
        )
    status = bootstrap.get("workspace_view", {}).get("proof_status", {})
    actual_goal_hash = str(status.get("goal_hash") or "")
    if status.get("goal_identity_required") is not True or not actual_goal_hash:
        raise RuntimeError(
            "outer proof handoff fresh replay did not preserve an open goal"
        )
    if actual_goal_hash != expected_goal_hash:
        raise RuntimeError(
            "outer proof handoff fresh replay changed the goal identity: "
            f"{actual_goal_hash} != {expected_goal_hash}"
        )


def _resolve_handoff_boundary(
    *,
    tactics: list[str],
    failed_index: int | None,
    failure_view: dict[str, Any],
) -> tuple[int, str, str, dict[str, Any]]:
    """Resolve an authoritative open boundary after candidate replay.

    A candidate can exhaust its tactic list while still leaving an open goal.
    That is a valid warm-handoff boundary, not a completed proof. Missing or
    contradictory proof-status data never implies either openness or closure.
    """

    status = failure_view.get("proof_status")
    status = status if isinstance(status, dict) else {}
    identity_required = status.get("goal_identity_required")
    goal_hash = str(status.get("goal_hash") or "")

    if failed_index is None:
        if identity_required is False:
            raise ValueError(
                "the complete candidate tactic body was accepted; verify it "
                "directly instead"
            )
        if identity_required is not True or not goal_hash:
            raise ValueError(
                "candidate exhaustion did not expose an authoritative open or "
                "closed proof boundary"
            )
        return (
            len(tactics),
            "",
            "candidate_exhausted_with_open_goal",
            status,
        )

    if identity_required is not True or not goal_hash:
        raise ValueError(
            "rejected candidate did not leave an authoritative open goal identity"
        )
    return failed_index, tactics[failed_index], "candidate_tactic_rejected", status


def prepare_outer_proof_handoff(
    *,
    root: Path,
    run_rel: Path,
    lemma: str,
    strategy_note: str,
    resource_anchors: str | None = None,
    candidate_source: str | None = None,
    runtime_target_file: str = TARGET,
) -> Path:
    """Natively certify an outer candidate boundary and its briefing.

    A strategy/resource handoff with no candidate tactics is still useful: the
    preparation manager certifies the initial open goal and the inner node
    receives the outer agent's bounded briefing without pretending that a
    proof prefix exists.
    """

    root = root.resolve()
    run_dir = (root / run_rel).resolve()
    if not run_dir.is_dir():
        raise ValueError(f"run directory does not exist: {run_dir}")
    target_path = (root / TARGET).resolve()
    candidate_path = _resolve_candidate(
        root=root,
        run_dir=run_dir,
        candidate_source=candidate_source,
    )
    strategy_path, strategy_text = _resolve_strategy_note(
        root=root, run_dir=run_dir, raw=strategy_note
    )
    target_text = target_path.read_text(encoding="utf-8")
    candidate_text = candidate_path.read_text(encoding="utf-8")
    body, _ = _proof_body(candidate_text, lemma)
    if _sha256_text(_lemma_prefix_projection(target_text, lemma)) != _sha256_text(
        _lemma_prefix_projection(candidate_text, lemma)
    ):
        raise ValueError(
            "candidate and current target differ before or at the delegated lemma"
        )
    resource_anchor_path, resolved_resource_anchors = _resolve_resource_anchors(
        root=root,
        run_dir=run_dir,
        raw=resource_anchors,
        context_source=candidate_text,
        context_source_ref=str(candidate_path.relative_to(root)),
        lemma=lemma,
        source_dir=target_path.parent,
    )

    tactics = _candidate_commands(body)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    handoff_dir = run_dir / "shannon_handoffs" / lemma / stamp
    prepare_dir = handoff_dir / "manager_prepare"
    prepare_dir.mkdir(parents=True, exist_ok=False)
    session_tag = f"prover_{uuid.uuid4().hex[:12]}_tree_0_0"
    manager = ProofNodeManager(
        file_path=TARGET,
        lemma_name=lemma,
        include_dir=INCLUDE_DIR,
        session_tag=session_tag,
        node_id="Tree-0.0",
        run_dir=prepare_dir,
        project_root=root,
        surface_profile="proof_state_compiler",
    )
    try:
        bootstrap = manager.bootstrap(replay_prefix=[])
        _write_json(prepare_dir / "bootstrap.json", bootstrap)

        accepted_commands: list[str] = []
        committed_spine: list[str] = []
        failed_index: int | None = None
        failed_tactic = ""
        failure_view: dict[str, Any] = bootstrap.get("workspace_view", {})
        attempts: list[dict[str, Any]] = []
        for index, tactic in enumerate(tactics):
            turn = manager.handle_agent_message(json.dumps({
                "intent": "commit_tactic",
                "payload": {"tactic": tactic},
            }))
            committed = list(turn.committed_tactics)
            kept = _candidate_step_kept(
                accepted=committed_spine,
                committed=committed,
            )
            attempts.append({
                "index": index,
                "tactic": tactic,
                "kept": kept,
                "committed_count": len(committed),
                "view": turn.workspace_view,
            })
            if not kept:
                failed_index = index
                failed_tactic = tactic
                failure_view = turn.workspace_view
                break
            accepted_commands.append(tactic)
            committed_spine = committed
            failure_view = turn.workspace_view
    finally:
        manager.close_session()

    _write_json(prepare_dir / "attempts.json", {"attempts": attempts})
    failed_index, failed_tactic, boundary_reason, status = _resolve_handoff_boundary(
        tactics=tactics,
        failed_index=failed_index,
        failure_view=failure_view,
    )
    identity_required = status["goal_identity_required"]
    goal_hash = str(status["goal_hash"])

    replay_certify_dir = handoff_dir / "manager_replay_certify"
    replay_certify_dir.mkdir(parents=True, exist_ok=False)
    _certify_fresh_replay(
        root=root,
        lemma=lemma,
        replay_commands=accepted_commands,
        expected_committed_spine=committed_spine,
        expected_goal_hash=goal_hash,
        run_dir=replay_certify_dir,
    )

    suffix = "\n".join(tactics[failed_index:])
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    ).stdout.strip()
    manifest = {
        "kind": HANDOFF_KIND,
        "version": HANDOFF_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Preparation is certified against the canonical lane target above.
        # The managed proof node may run against a proof-stripped projection;
        # replay verifies that the recorded boundary is unchanged there.
        "target": {"file": runtime_target_file, "lemma": lemma},
        "source": {
            "commit": commit,
            "outer_run_dir": run_rel.as_posix(),
            "candidate_source": str(candidate_path.relative_to(root)),
            "candidate_sha256": _sha256_bytes(candidate_path.read_bytes()),
            "projection_scope": "through_delegated_lemma",
            "candidate_projection_sha256": _sha256_text(
                _lemma_prefix_projection(candidate_text, lemma)
            ),
            "current_projection_sha256": _sha256_text(
                _lemma_prefix_projection(target_text, lemma)
            ),
            "strategy_note": str(strategy_path.relative_to(root)),
            "resource_anchors": (
                str(resource_anchor_path.relative_to(root))
                if resource_anchor_path is not None
                else None
            ),
            "manager_prepare_dir": str(prepare_dir.relative_to(root)),
        },
        "replay": {
            # These are the exact complete commands accepted by preparation;
            # the manager's canonical committed spine uses the same command
            # units, including for a command that spans physical lines.
            "commands": accepted_commands,
            "commands_sha256": proof_command_sequence_sha256(accepted_commands),
            "candidate_command_count": len(tactics),
            "accepted_command_count": len(accepted_commands),
            "committed_spine_count": len(committed_spine),
            "committed_spine_sha256": proof_command_sequence_sha256(
                committed_spine
            ),
        },
        "boundary": {
            "reason": boundary_reason,
            "goal_hash": goal_hash,
            "goal_identity_required": identity_required,
            "failed_tactic": failed_tactic,
            "failure_summary": _failure_summary(failure_view),
            "current_goal_preview": _goal_preview(failure_view),
        },
        "briefing": {
            "strategy_note": strategy_text,
            "candidate_suffix": suffix,
            "resource_anchors": resolved_resource_anchors,
        },
    }
    manifest_path = handoff_dir / "outer_handoff.json"
    _write_json(manifest_path, manifest)
    return manifest_path
