"""Extract paper-eval metrics from ShannonProver run directories."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from workflow.schemas.prover_result import (
    PROVER_RUN_INFRASTRUCTURE_INVALID,
    ProverResult,
)
from workflow.proof_management.common import node_memory_slug
from workflow.validation.agent_thinking_trace import (
    normalize_codex_usage,
    usage_dedup_key,
)
from typing import Any


DESTRUCTIVE_LOWERING_RE = re.compile(
    r"(?i)(?:^|[;\s])(?:inline\s+\*|wp\.|smt\s*\(|proc\s*;\s*inline\s+\*)"
)
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
THINKING_TOKEN_KEYS = (
    "thinking_tokens",
    "reasoning_tokens",
    "reasoning_output_tokens",
)
OUTPUT_DETAILS_TOKEN_KEYS = (
    "thinking_tokens",
    "reasoning_tokens",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args(argv)

    rows = [collect_run_metrics(path) for path in args.runs]
    payload = {
        "schema_version": 2,
        "kind": "eval_suite_metrics",
        "runs": rows,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(rows), encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def collect_run_metrics(
    path: Path,
) -> dict[str, Any]:
    """Collect stable metrics for one orchestrator run or run container."""
    run_dir = _resolve_run_dir(path)
    summary = _read_json(run_dir / "summary.json")
    config = _read_json(run_dir / "config.json")
    iteration_dirs = sorted(run_dir.glob("iteration_*"))
    timeline_paths = [
        timeline
        for iteration in iteration_dirs
        for timeline in iteration.glob("node_memory/*/timeline.jsonl")
    ]
    audit_paths = [
        audit
        for iteration in iteration_dirs
        for audit in iteration.glob("proof_node_manager_audit.jsonl")
    ]
    audit_records = [
        record
        for audit in audit_paths
        for record in _read_jsonl(audit)
    ]
    payload_records = [
        record
        for iteration in iteration_dirs
        for audit in iteration.glob("payload_audit.jsonl")
        for record in _read_jsonl(audit)
    ]
    target_proof_exposures = [
        dict(record.get("target_proof_exposure") or {})
        for record in payload_records
        if isinstance(record.get("target_proof_exposure"), dict)
        and record["target_proof_exposure"].get("detected") is True
        and record["target_proof_exposure"].get("audit_code")
        == "eval.target_proof_output_exposure"
    ]
    confinement_paths = [
        record
        for iteration in iteration_dirs
        for record in iteration.glob(
            "runtime_private/*/eval_agent_confinement.json"
        )
    ]
    confinement_records = [
        record
        for path in confinement_paths
        for record in [_read_json(path)]
        if record.get("kind") == "eval_agent_filesystem_confinement"
        and (_optional_int_value(record.get("schema_version")) or 0) >= 2
        and record.get("probe_status") == "passed"
        and record.get("original_repository_visible") is False
        and record.get("sibling_worktrees_visible") is False
        and record.get("prior_agent_transcripts_visible") is False
        and record.get("host_tmp_visible") is False
    ]
    expected_confined_nodes = [
        private
        for iteration in iteration_dirs
        for private in iteration.glob("runtime_private/*")
        if private.is_dir()
        and (private / "proof_node_mcp_config.json").is_file()
    ]
    validity_reasons = [
        "agent tool output exposed a line from the target lemma proof body"
        for _item in target_proof_exposures[:1]
    ]
    prover_result: ProverResult | None = None
    result_paths = [
        iteration / "prover_run_result.json"
        for iteration in iteration_dirs
        if (iteration / "prover_run_result.json").is_file()
    ]
    if len(result_paths) != 1:
        validity_reasons.append(
            "exactly one authoritative prover_run_result.json is required"
        )
    else:
        try:
            prover_result = ProverResult.load(result_paths[0])
        except Exception as exc:
            validity_reasons.append(f"prover run result is invalid: {exc}")
    if prover_result is not None:
        if summary.get("final_prover_result_id") != prover_result.result_id:
            validity_reasons.append("summary prover result identity drifted")
        if summary.get("final_prover_result_status") != prover_result.status:
            validity_reasons.append("summary prover result status drifted")
        if bool(summary.get("final_proved")) != prover_result.is_verified:
            validity_reasons.append("summary final_proved contradicts prover result")
        if prover_result.status == PROVER_RUN_INFRASTRUCTURE_INVALID:
            validity_reasons.extend(
                f"prover infrastructure invalid: {reason}"
                for reason in (
                    prover_result.infrastructure_errors
                    or [prover_result.error or "unknown terminal outcome error"]
                )
            )
    failed_run_end_without_timeline = any(
        str(record.get("event") or "") == "run_end"
        and (_optional_int_value(record.get("returncode")) or 0) != 0
        for record in payload_records
    ) and not timeline_paths
    if failed_run_end_without_timeline:
        validity_reasons.append(
            "no proof-node timeline was produced before the run terminated"
        )
    manager_bridge_exceptions = [
        record
        for record in audit_records
        if str(record.get("kind") or "") == "manager_bridge.exception"
        or str((record.get("health") or {}).get("status") or "")
        == "manager_bridge_exception"
    ]
    if manager_bridge_exceptions:
        validity_reasons.append(
            "manager bridge raised an internal exception during the agent run"
        )
    if bool(config.get("eval_mode")) and (
        not expected_confined_nodes
        or len(confinement_records) != len(expected_confined_nodes)
    ):
        validity_reasons.append(
            "eval agent filesystem confinement was not established for every "
            "launched proof node"
        )
    action_counts: Counter[str] = Counter()
    node_commits: Counter[str] = Counter()
    node_failed_turns: Counter[str] = Counter()
    destructive_lowering = 0
    failed_commit_tactics = 0
    failed_tactic_attempts = 0
    accepted_commits = 0
    commit_attempts = 0
    undo_count = 0
    restart_count = 0
    blocked_by_profile = 0
    handled_turns = 0
    blind_retry_spikes: list[int] = []
    blind_run = 0

    for record in audit_records:
        kind = str(record.get("kind") or "")
        if kind == "agent_intent.blocked_by_surface_profile":
            blocked_by_profile += 1
            continue
        if kind != "agent_intent.handled":
            continue
        handled_turns += 1
        node = str(record.get("node") or "")
        intent = _intent_name(record.get("intent"))
        payload = _intent_payload(record.get("intent"))
        actions = [
            action
            for action in record.get("manager_actions") or []
            if isinstance(action, dict)
        ]
        primary = _primary_action(actions)
        if primary:
            label = str(primary.get("label") or intent or "unknown")
            action_counts[label] += 1
        failed_tactic_turn = False
        if intent == "commit_tactic":
            commit_attempts += 1
            tactic = str(payload.get("tactic") or _action_tactic(primary) or "")
            ok = _action_was_accepted(primary)
            if ok:
                accepted_commits += 1
                node_commits[node] += 1
                if DESTRUCTIVE_LOWERING_RE.search(tactic):
                    destructive_lowering += 1
            else:
                failed_commit_tactics += 1
                failed_tactic_attempts += 1
                failed_tactic_turn = True
        elif intent in {"undo_last_step", "undo_to_checkpoint"}:
            undo_count += 1
        elif intent == "fresh_restart":
            restart_count += 1

        if failed_tactic_turn:
            blind_run += 1
            node_failed_turns[node] += 1
        else:
            if blind_run >= 2:
                blind_retry_spikes.append(blind_run)
            blind_run = 0
    if blind_run >= 2:
        blind_retry_spikes.append(blind_run)

    profile = (
        config.get("surface_profile")
        or _first_profile_from_records(audit_records)
        or ""
    )
    best_prefix_depth = max(node_commits.values() or [0])
    final_proof_length = (
        best_prefix_depth
        if prover_result is not None and prover_result.is_verified
        else None
    )
    agent_trace = _collect_agent_trace_metrics(iteration_dirs or [run_dir])
    launched_proof_nodes = len(expected_confined_nodes)
    provider_session_count = int(agent_trace.get("session_count") or 0)
    if launched_proof_nodes and provider_session_count == 0:
        validity_reasons.append(
            "no provider session was captured for any launched proof node"
        )
    if launched_proof_nodes and handled_turns == 0:
        validity_reasons.append(
            "no managed agent turn completed for any launched proof node"
        )
    if (
        provider_session_count > 0
        and not bool(agent_trace.get("token_accounting_complete"))
    ):
        validity_reasons.append(
            "provider token accounting is incomplete for at least one agent "
            "session"
        )
    validity_ok = not validity_reasons
    compiler = _collect_proof_state_compiler_economics(audit_records)
    source_inspection = _collect_source_inspection_economics(
        payload_records,
        manager_turns=handled_turns,
    )
    return {
        "run_dir": str(run_dir),
        "status": "valid" if validity_ok else "invalid",
        "validity": {
            "valid": validity_ok,
            "status": "valid" if validity_ok else "invalid",
            "reasons": validity_reasons,
        },
        "profile": profile,
        "target": summary.get("target") or {
            "file": config.get("file"),
            "lemma": config.get("lemma"),
        },
        "outcome": {
            "proved": bool(prover_result and prover_result.is_verified),
            "regression_ok": bool(summary.get("final_regression_ok")),
            "countable": validity_ok,
            "elapsed_minutes": summary.get("total_elapsed_minutes"),
            "iterations": summary.get("iterations"),
        },
        "main": {
            "manager_turns": handled_turns,
            "commit_attempts": commit_attempts,
            "accepted_commits": accepted_commits,
            "failed_commit_tactics": failed_commit_tactics,
            "failed_tactic_attempts": failed_tactic_attempts,
            "final_proof_length": final_proof_length,
        },
        "navigator": {
            "destructive_lowering_count": destructive_lowering,
            "best_prefix_depth": best_prefix_depth,
        },
        "diagnostics": {
            "blind_retry_spike_count": len(blind_retry_spikes),
            "max_blind_retry_spike_length": max(blind_retry_spikes or [0]),
            "blind_retry_turns": sum(blind_retry_spikes),
            "blocked_by_surface_profile": blocked_by_profile,
            "manager_bridge_exception_count": len(manager_bridge_exceptions),
        },
        "search": {
            "node_count": len({str(record.get("node") or "") for record in audit_records if record.get("node")}),
            "max_node_failed_turns": max(node_failed_turns.values() or [0]),
        },
        "mechanical_work": {
            "undo_count": undo_count,
            "fresh_restart_count": restart_count,
            "route_repair_count": undo_count + restart_count,
            "thinking_tokens_per_accepted_commit": _per(
                agent_trace.get("thinking_tokens"),
                accepted_commits,
            ),
            "thinking_chars_per_accepted_commit": _per(
                agent_trace.get("thinking_chars"),
                accepted_commits,
            ),
            "source_inspection": source_inspection,
        },
        "agent_trace": agent_trace,
        "compiler": compiler,
        "raw_action_counts": dict(sorted(action_counts.items())),
        "integrity": {
            "target_proof_output_exposure_count": len(target_proof_exposures),
            "target_proof_output_exposures": target_proof_exposures[:20],
            "expected_confined_node_count": len(expected_confined_nodes),
            "confined_node_count": len(confinement_records),
            "filesystem_confinement_complete": (
                bool(expected_confined_nodes)
                and len(confinement_records) == len(expected_confined_nodes)
            ),
        },
    }


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Eval Suite Metrics",
        "",
        "| Profile | Target | Proved | Time (min) | Thinking tokens | Turns | Commits | Failed commits | Undo | Restart | Compiler exec/skip | Compiler ms | Native req/batch | Loader ms | Observation cache h/m | Certification cache h/m | Cert work/reuse | Presented | Consumed | Route repairs | Destructive lowering | Blind spikes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        target = row.get("target") or {}
        target_label = target.get("lemma") or row.get("run_dir")
        outcome = row.get("outcome") or {}
        main = row.get("main") or {}
        navigator = row.get("navigator") or {}
        diagnostics = row.get("diagnostics") or {}
        mechanical = row.get("mechanical_work") or {}
        agent_trace = row.get("agent_trace") or {}
        compiler = row.get("compiler") or {}
        lines.append(
            "| {profile} | {target} | {proved} | {time} | {thinking_tokens} | "
            "{turns} | {commits} | {failed_commits} | {undo} | {restart} | "
            "{compiler_execution} | {compiler_ms} | {native_work} | "
            "{loader_ms} | {observation_cache_hits}/"
            "{observation_cache_misses} | {cert_cache_hits}/"
            "{cert_cache_misses} | {cert_work}/{cert_reuse} | {presented} | "
            "{consumed} | "
            "{repairs} | {destructive} | {spikes} |".format(
                profile=row.get("profile") or "",
                target=target_label,
                proved="yes" if outcome.get("proved") else "no",
                time=_fmt(outcome.get("elapsed_minutes")),
                thinking_tokens=_fmt(agent_trace.get("thinking_tokens")),
                turns=_fmt(main.get("manager_turns")),
                commits=_fmt(main.get("accepted_commits")),
                failed_commits=_fmt(main.get("failed_commit_tactics")),
                undo=_fmt(mechanical.get("undo_count")),
                restart=_fmt(mechanical.get("fresh_restart_count")),
                compiler_execution=(
                    f"{_fmt(compiler.get('executed_call_count'))}/"
                    f"{_fmt(compiler.get('skipped_call_count'))}"
                ),
                compiler_ms=_fmt(compiler.get("service_total_ms")),
                native_work=(
                    f"{_fmt(compiler.get('native_planned_request_count'))}/"
                    f"{_fmt(compiler.get('native_batch_count'))}"
                ),
                loader_ms=_fmt(compiler.get("resource_loading_wall_ms")),
                observation_cache_hits=_fmt(
                    compiler.get("exact_observation_cache_hit_count")
                ),
                observation_cache_misses=_fmt(
                    compiler.get("exact_observation_cache_miss_count")
                ),
                cert_cache_hits=_fmt(
                    compiler.get("material_certification_cache_hit_count")
                ),
                cert_cache_misses=_fmt(
                    compiler.get("material_certification_cache_miss_count")
                ),
                cert_work=_fmt(compiler.get("certification_attempt_count")),
                cert_reuse=_fmt(compiler.get("reused_certification_count")),
                presented=_fmt(compiler.get("presented_action_count")),
                consumed=_fmt(compiler.get("consumed_action_count")),
                repairs=_fmt(mechanical.get("route_repair_count")),
                destructive=_fmt(navigator.get("destructive_lowering_count")),
                spikes=_fmt(diagnostics.get("blind_retry_spike_count")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _resolve_run_dir(path: Path) -> Path:
    if (path / "summary.json").exists():
        return path
    summaries = sorted(path.glob("*/summary.json"))
    if len(summaries) == 1:
        return summaries[0].parent
    if not summaries:
        raise FileNotFoundError(f"no summary.json under {path}")
    raise ValueError(
        f"{path} contains multiple run summaries; pass one concrete run dir"
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _intent_identity(value: dict[str, Any]) -> str:
    payload = value.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    return json.dumps(
        {"intent": str(value.get("intent") or ""), "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _collect_proof_state_compiler_economics(
    audit_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate hidden cost and visible action uptake from manager events.

    The compiler completion event is the authoritative generic audit boundary.
    An action is counted as consumed only when the next handled intent for the
    same node is byte-identical to the last action surface offered there.
    """

    completed = 0
    failed = 0
    executed = 0
    skipped = 0
    eligible_feature_occurrences = 0
    execution_skip_reasons: Counter[str] = Counter()
    states_with_planned_loads = 0
    planned_requests = 0
    resource_load_rounds = 0
    completed_requests = 0
    loaded_declarations = 0
    loader_internal_ms = 0
    resource_loading_wall_ms = 0
    input_initial_ms = 0
    manager_state_snapshot_ms = 0
    compiler_input_transport_ms = 0
    native_state_projection_wall_ms = 0
    native_state_lowering_ms = 0
    native_state_elapsed_ms = 0
    native_semantic_execution_ms = 0
    native_planned_requests = 0
    native_observations = 0
    native_batches = 0
    native_batch_elapsed_ms = 0
    service_total_ms = 0
    compile_p1_p4_ms = 0
    certification_ms = 0
    candidate_actions = 0
    certification_attempts = 0
    certification_accepts = 0
    exact_observation_cache_hits = 0
    exact_observation_cache_misses = 0
    material_certification_cache_hits = 0
    material_certification_cache_misses = 0
    resource_cache_hits = 0
    resource_cache_misses = 0
    reused_resource_declarations = 0
    reused_certifications = 0
    presented_items = 0
    presented_actions = 0
    presentation_events = 0
    consumed_actions = 0
    consumed_actions_accepted = 0
    consumed_actions_rejected = 0
    compiler_markdown_bytes = 0
    manifests: set[str] = set()
    presented_by_feature: Counter[str] = Counter()
    consumed_by_feature: Counter[str] = Counter()
    offered_by_node: dict[str, list[dict[str, Any]]] = {}

    for record in audit_records:
        kind = str(record.get("kind") or "")
        node = str(record.get("node") or "")
        if kind == "proof_state_compiler.failed":
            failed += 1
            offered_by_node.pop(node, None)
            continue
        if kind == "proof_state_compiler.completed":
            completed += 1
            execution = (
                record.get("execution")
                if isinstance(record.get("execution"), dict)
                else {}
            )
            execution_status = str(execution.get("status") or "executed")
            if execution_status == "skipped":
                skipped += 1
            else:
                executed += 1
            eligible = execution.get("eligible_feature_ids")
            if isinstance(eligible, list):
                eligible_feature_occurrences += len(eligible)
            decisions = execution.get("decisions")
            if isinstance(decisions, list):
                execution_skip_reasons.update(
                    str(item.get("reason") or "unknown")
                    for item in decisions
                    if isinstance(item, dict) and item.get("eligible") is False
                )
            manifest_id = str(record.get("manifest_id") or "")
            if manifest_id:
                manifests.add(manifest_id)
            loading = (
                record.get("resource_loading")
                if isinstance(record.get("resource_loading"), dict)
                else {}
            )
            timings = (
                record.get("timings_ms")
                if isinstance(record.get("timings_ms"), dict)
                else {}
            )
            native_semantics = (
                record.get("native_semantics")
                if isinstance(record.get("native_semantics"), dict)
                else {}
            )
            native_state = (
                record.get("native_state")
                if isinstance(record.get("native_state"), dict)
                else {}
            )
            certifications = (
                record.get("certifications")
                if isinstance(record.get("certifications"), dict)
                else {}
            )
            exact_observation_cache = (
                record.get("exact_observation_cache")
                if isinstance(record.get("exact_observation_cache"), dict)
                else {}
            )
            certification_cache = (
                record.get("certification_cache")
                if isinstance(record.get("certification_cache"), dict)
                else {}
            )
            resource_cache = (
                record.get("resource_cache")
                if isinstance(record.get("resource_cache"), dict)
                else {}
            )
            admission = (
                record.get("admission")
                if isinstance(record.get("admission"), dict)
                else {}
            )
            candidates = (
                record.get("candidate_counts")
                if isinstance(record.get("candidate_counts"), dict)
                else {}
            )
            planned = _int_value(loading.get("planned_request_count"))
            planned_requests += planned
            states_with_planned_loads += int(planned > 0)
            completed_request_count = _int_value(
                loading.get("request_count")
            )
            completed_requests += completed_request_count
            resource_load_rounds += int(completed_request_count > 0)
            loaded_declarations += _int_value(
                loading.get("loaded_declaration_count")
            )
            loader_internal_ms += _int_value(loading.get("elapsed_ms"))
            resource_loading_wall_ms += _int_value(
                timings.get("resource_loading")
            )
            input_initial_ms += _int_value(timings.get("input_initial"))
            manager_state_snapshot_ms += _int_value(
                timings.get("manager_state_snapshot")
            )
            compiler_input_transport_ms += _int_value(
                timings.get("compiler_input_transport")
            )
            native_state_projection_wall_ms += _int_value(
                timings.get("native_state_projection")
            )
            native_state_lowering_ms += _int_value(
                timings.get("native_state_lowering")
            )
            native_state_elapsed_ms += _int_value(native_state.get("elapsed_ms"))
            native_semantic_execution_ms += _int_value(
                timings.get("native_semantic_execution")
            )
            native_planned_requests += _int_value(
                native_semantics.get("planned_request_count")
            )
            native_observations += _int_value(
                native_semantics.get("observation_count")
            )
            native_batches += _int_value(native_semantics.get("batch_count"))
            native_batch_elapsed_ms += _int_value(
                native_semantics.get("elapsed_ms")
            )
            service_total_ms += _int_value(timings.get("total"))
            compile_p1_p4_ms += _int_value(timings.get("compile_p1_p4"))
            certification_ms += _int_value(timings.get("certification"))
            candidate_actions += _int_value(candidates.get("actions"))
            certification_attempts += _int_value(
                certifications.get("performed")
                if "performed" in certifications
                else certifications.get("total")
            )
            certification_accepts += _int_value(
                certifications.get("performed_accepted")
                if "performed_accepted" in certifications
                else certifications.get("accepted")
            )
            reused_certifications += _int_value(certifications.get("reused"))
            if exact_observation_cache.get("hit") is True:
                exact_observation_cache_hits += 1
            elif exact_observation_cache.get("hit") is False:
                exact_observation_cache_misses += 1
            if certification_cache.get("hit") is True:
                material_certification_cache_hits += 1
            elif certification_cache.get("hit") is False:
                material_certification_cache_misses += 1
            if resource_cache.get("hit") is True:
                resource_cache_hits += 1
            elif resource_cache.get("hit") is False:
                resource_cache_misses += 1
            reused_resource_declarations += _int_value(
                resource_cache.get("reused_declaration_count")
            )
            compiler_markdown_bytes += _int_value(
                admission.get("compiler_markdown_bytes")
            )
            agent_surface = (
                admission.get("agent_surface")
                if isinstance(admission.get("agent_surface"), dict)
                else {}
            )
            surface_items = [
                item
                for key in ("resources", "bindings", "actions", "diagnostics")
                for item in (agent_surface.get(key) or [])
                if isinstance(item, dict)
            ]
            actions = [
                dict(item)
                for item in admission.get("presented_actions") or []
                if isinstance(item, dict)
            ]
            offered_by_node[node] = actions
            if surface_items:
                presentation_events += 1
                presented_items += len(surface_items)
                presented_actions += len(actions)
                admitted_decisions = [
                    item
                    for item in admission.get("decisions") or []
                    if isinstance(item, dict) and item.get("admitted") is True
                ]
                presented_by_feature.update(
                    str(item.get("feature_id") or "unknown")
                    for item in (admitted_decisions or actions)
                )
            continue
        if kind != "agent_intent.handled":
            continue
        offered = offered_by_node.pop(node, [])
        if not offered:
            continue
        submitted = record.get("intent")
        if not isinstance(submitted, dict):
            continue
        identity = _intent_identity(submitted)
        match = next((
            item for item in offered
            if _intent_identity(item) == identity
        ), None)
        if match is not None:
            consumed_actions += 1
            handled_actions = [
                action
                for action in record.get("manager_actions") or []
                if isinstance(action, dict)
            ]
            if _action_was_accepted(_primary_action(handled_actions)):
                consumed_actions_accepted += 1
            else:
                consumed_actions_rejected += 1
            consumed_by_feature[
                str(match.get("feature_id") or "unknown")
            ] += 1

    return {
        "available": bool(completed or failed),
        "service_call_count": completed,
        "failed_call_count": failed,
        "executed_call_count": executed,
        "skipped_call_count": skipped,
        "eligible_feature_occurrence_count": eligible_feature_occurrences,
        "execution_skip_reasons": dict(sorted(execution_skip_reasons.items())),
        "manifest_ids": sorted(manifests),
        "states_with_planned_loads": states_with_planned_loads,
        "planned_request_count": planned_requests,
        "resource_load_round_count": resource_load_rounds,
        "completed_request_count": completed_requests,
        "loaded_declaration_count": loaded_declarations,
        "loader_internal_ms": loader_internal_ms,
        "resource_loading_wall_ms": resource_loading_wall_ms,
        "input_initial_ms": input_initial_ms,
        "manager_state_snapshot_ms": manager_state_snapshot_ms,
        "compiler_input_transport_ms": compiler_input_transport_ms,
        "native_state_projection_wall_ms": native_state_projection_wall_ms,
        "native_state_lowering_ms": native_state_lowering_ms,
        "native_state_elapsed_ms": native_state_elapsed_ms,
        "native_semantic_execution_ms": native_semantic_execution_ms,
        "native_planned_request_count": native_planned_requests,
        "native_observation_count": native_observations,
        "native_batch_count": native_batches,
        "native_batch_elapsed_ms": native_batch_elapsed_ms,
        "compile_p1_p4_ms": compile_p1_p4_ms,
        "certification_ms": certification_ms,
        "service_total_ms": service_total_ms,
        "candidate_action_count": candidate_actions,
        "certification_attempt_count": certification_attempts,
        "certification_accepted_count": certification_accepts,
        "exact_observation_cache_hit_count": exact_observation_cache_hits,
        "exact_observation_cache_miss_count": exact_observation_cache_misses,
        "material_certification_cache_hit_count": (
            material_certification_cache_hits
        ),
        "material_certification_cache_miss_count": (
            material_certification_cache_misses
        ),
        "resource_cache_hit_count": resource_cache_hits,
        "resource_cache_miss_count": resource_cache_misses,
        "reused_resource_declaration_count": reused_resource_declarations,
        "reused_certification_count": reused_certifications,
        "presentation_event_count": presentation_events,
        "presented_item_count": presented_items,
        "presented_action_count": presented_actions,
        "consumed_action_count": consumed_actions,
        "consumed_action_accepted_count": consumed_actions_accepted,
        "consumed_action_rejected_count": consumed_actions_rejected,
        "compiler_markdown_bytes": compiler_markdown_bytes,
        "presented_by_feature": dict(sorted(presented_by_feature.items())),
        "consumed_by_feature": dict(sorted(consumed_by_feature.items())),
    }


def _payload_information_source_kind(
    record: dict[str, Any],
) -> tuple[str, str]:
    """Classify only policy-labelled information-source events."""

    tool_name = str(record.get("tool_name") or "")
    if tool_name not in {"Bash", "Read"}:
        return "", ""
    policy = record.get("policy")
    policy = policy if isinstance(policy, dict) else {}
    source_type = str(policy.get("source_type") or "").lower()
    if "current_node_memory" in source_type:
        return "", ""
    if "source" in source_type:
        return "source_read", "semantic_policy"
    return "", ""


def _collect_source_inspection_economics(
    records: list[dict[str, Any]],
    *,
    manager_turns: int,
) -> dict[str, Any]:
    tool_uses = [
        record
        for record in records
        if str(record.get("event") or "") == "tool_use"
    ]
    submit_count = sum(
        1
        for record in tool_uses
        if str(record.get("tool_name") or "").endswith("submit_proof_intent")
    )
    if not records:
        return {
            "available": False,
            "unavailable_reason": "payload audit unavailable",
            "tool_use_count": None,
            "source_inspection_tool_count": None,
            "source_read_tool_count": None,
            "source_tree_search_tool_count": None,
            "scratch_checker_tool_count": None,
            "source_inspection_result_chars": None,
            "source_inspection_result_lines": None,
            "semantic_policy_count": None,
        }
    if manager_turns > 0 and submit_count == 0:
        return {
            "available": False,
            "unavailable_reason": (
                "payload audit has manager turns but no submit tool-use events"
            ),
            "tool_use_count": len(tool_uses),
            "source_inspection_tool_count": None,
            "source_read_tool_count": None,
            "source_tree_search_tool_count": None,
            "scratch_checker_tool_count": None,
            "source_inspection_result_chars": None,
            "source_inspection_result_lines": None,
            "semantic_policy_count": None,
        }

    category_counts: Counter[str] = Counter()
    basis_counts: Counter[str] = Counter()
    source_tool_ids: set[str] = set()
    for record in tool_uses:
        kind, basis = _payload_information_source_kind(record)
        if not kind:
            continue
        category_counts[kind] += 1
        basis_counts[basis] += 1
        if kind in {"source_read", "source_tree_search"}:
            tool_use_id = str(record.get("tool_use_id") or "")
            if tool_use_id:
                source_tool_ids.add(tool_use_id)

    source_result_chars = 0
    source_result_lines = 0
    for record in records:
        if (
            str(record.get("event") or "") != "tool_result"
            or str(record.get("tool_use_id") or "") not in source_tool_ids
        ):
            continue
        result = record.get("result")
        result = result if isinstance(result, dict) else {}
        source_result_chars += int(result.get("chars") or 0)
        source_result_lines += int(result.get("lines") or 0)

    source_read_count = category_counts["source_read"]
    source_search_count = category_counts["source_tree_search"]
    return {
        "available": True,
        "unavailable_reason": "",
        "tool_use_count": len(tool_uses),
        "source_inspection_tool_count": source_read_count + source_search_count,
        "source_read_tool_count": source_read_count,
        "source_tree_search_tool_count": source_search_count,
        "scratch_checker_tool_count": category_counts["scratch_checker"],
        "source_inspection_result_chars": source_result_chars,
        "source_inspection_result_lines": source_result_lines,
        "semantic_policy_count": basis_counts["semantic_policy"],
        "observation": (
            "agent tool-use events only; reasoning-text mentions are excluded"
        ),
    }


def _collect_agent_trace_metrics(iteration_dirs: list[Path]) -> dict[str, Any]:
    """Whole-run token/thinking accounting from provider event streams.

    Claude transcript lookup is host-specific and can be unavailable after a
    run is moved. Codex JSONL is run-confined and resolves from the canonical
    session registry's iteration/node identity. Related but deliberately
    separate from ``agent_thinking_trace.py``, which attributes reasoning to
    individual manager turns; normalization and Claude usage dedup are shared.
    """
    records = _agent_session_records(iteration_dirs)
    totals = {
        "available": False,
        "session_count": len(records),
        "trace_count": 0,
        "missing_trace_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "effective_input_tokens": 0,
        "total_tokens": 0,
        "thinking_blocks": 0,
        "thinking_chars": 0,
        "thinking_tokens": 0,
        "thinking_tokens_exact": None,
        "thinking_token_estimate": 0,
        "thinking_token_source": "none",
        "summed_trace_duration_seconds": 0.0,
        "max_trace_duration_seconds": 0.0,
        "max_gap_before_thinking_seconds": 0.0,
        "token_accounting_complete": False,
        "incomplete_token_session_count": 0,
        "partial_turn_recovered_count": 0,
        "usage_sources": {},
        "sessions": [],
    }
    exact_thinking_tokens = 0
    saw_exact_thinking_tokens = False
    seen_usage_paths: set[Path] = set()

    codex_trace_sessions: dict[Path, list[str]] = {}
    codex_rollouts: dict[str, Path | None] = {}
    for record in records:
        if str(record.get("agent_backend") or "claude") != "codex":
            continue
        session_id = str(record.get("session_id") or "").strip()
        trace_path = _find_codex_event_trace(record)
        if not session_id or trace_path is None:
            continue
        resolved_trace = trace_path.resolve()
        codex_trace_sessions.setdefault(resolved_trace, []).append(session_id)
        codex_rollouts[session_id] = _find_codex_rollout_trace(
            trace_path,
            session_id,
        )

    for record in records:
        session_id = str(record.get("session_id") or "").strip()
        if not session_id:
            continue
        agent_backend = str(record.get("agent_backend") or "claude")
        trace_path = (
            _find_claude_trace(record)
            if agent_backend == "claude"
            else _find_codex_event_trace(record)
            if agent_backend == "codex"
            else None
        )
        session_status = {
            key: value
            for key, value in record.items()
            if key != "trace_path"
        }
        session_status["trace_found"] = bool(trace_path)
        if trace_path:
            session_status["trace_path"] = str(trace_path)
        totals["sessions"].append(session_status)
        if trace_path is None:
            totals["missing_trace_count"] += 1
            continue
        resolved_trace = trace_path.resolve()
        rollout_path = (
            codex_rollouts.get(session_id)
            if agent_backend == "codex"
            else None
        )
        shared_codex_trace = codex_trace_sessions.get(resolved_trace, [])
        if (
            agent_backend == "codex"
            and rollout_path is None
            and len(shared_codex_trace) > 1
            and any(codex_rollouts.get(sid) is not None for sid in shared_codex_trace)
        ):
            # A shared public CLI stream cannot attribute its aggregate events
            # to the one missing thread without double counting the other
            # threads' exact ledgers.  Fail this session closed instead.
            session_status["usage_source"] = "missing_codex_session_ledger"
            session_status["token_accounting_complete"] = False
            session_status["partial_turn_recovered"] = False
            totals["incomplete_token_session_count"] += 1
            continue
        usage_path = rollout_path or trace_path
        resolved_usage_path = usage_path.resolve()
        if resolved_usage_path in seen_usage_paths:
            session_status["trace_reused"] = True
            continue
        seen_usage_paths.add(resolved_usage_path)
        stats = (
            _parse_codex_trace(
                trace_path,
                session_id=session_id,
                rollout_path=rollout_path,
            )
            if agent_backend == "codex"
            else _parse_agent_trace(trace_path)
        )
        session_status["usage_event_count"] = stats.get("usage_event_count", 0)
        session_status["usage_source"] = str(stats.get("usage_source") or "")
        session_status["token_accounting_complete"] = bool(
            stats.get("token_accounting_complete", True)
        )
        session_status["partial_turn_recovered"] = bool(
            stats.get("partial_turn_recovered", False)
        )
        if not session_status["token_accounting_complete"]:
            totals["incomplete_token_session_count"] += 1
        if session_status["partial_turn_recovered"]:
            totals["partial_turn_recovered_count"] += 1
        usage_source = session_status["usage_source"]
        if usage_source:
            usage_sources = totals["usage_sources"]
            usage_sources[usage_source] = int(usage_sources.get(usage_source) or 0) + 1
        totals["available"] = True
        totals["trace_count"] += 1
        totals["input_tokens"] += stats["input_tokens"]
        totals["output_tokens"] += stats["output_tokens"]
        totals["cache_creation_input_tokens"] += stats[
            "cache_creation_input_tokens"
        ]
        totals["cache_read_input_tokens"] += stats["cache_read_input_tokens"]
        totals["thinking_blocks"] += stats["thinking_blocks"]
        totals["thinking_chars"] += stats["thinking_chars"]
        totals["summed_trace_duration_seconds"] = round(
            totals["summed_trace_duration_seconds"] + stats["duration_seconds"],
            3,
        )
        totals["max_trace_duration_seconds"] = max(
            totals["max_trace_duration_seconds"],
            stats["duration_seconds"],
        )
        totals["max_gap_before_thinking_seconds"] = max(
            totals["max_gap_before_thinking_seconds"],
            stats["max_gap_before_thinking_seconds"],
        )
        if stats["thinking_tokens_exact"] is not None:
            saw_exact_thinking_tokens = True
            exact_thinking_tokens += stats["thinking_tokens_exact"]

    totals["effective_input_tokens"] = (
        totals["input_tokens"]
        + totals["cache_creation_input_tokens"]
        + totals["cache_read_input_tokens"]
    )
    totals["total_tokens"] = (
        totals["effective_input_tokens"]
        + totals["output_tokens"]
    )
    if saw_exact_thinking_tokens:
        totals["thinking_tokens_exact"] = exact_thinking_tokens
        totals["thinking_tokens"] = exact_thinking_tokens
        totals["thinking_token_estimate"] = exact_thinking_tokens
        totals["thinking_token_source"] = "usage_field"
    elif totals["thinking_chars"]:
        totals["thinking_token_estimate"] = int(
            math.ceil(totals["thinking_chars"] / 4.0)
        )
        totals["thinking_tokens"] = totals["thinking_token_estimate"]
        totals["thinking_token_source"] = "char_estimate"
    totals["summed_trace_duration_seconds"] = round(
        totals["summed_trace_duration_seconds"],
        3,
    )
    totals["max_trace_duration_seconds"] = round(
        totals["max_trace_duration_seconds"],
        3,
    )
    totals["max_gap_before_thinking_seconds"] = round(
        totals["max_gap_before_thinking_seconds"],
        3,
    )
    totals["token_accounting_complete"] = bool(records) and (
        totals["missing_trace_count"] == 0
        and totals["incomplete_token_session_count"] == 0
    )
    return totals


def _agent_session_records(iteration_dirs: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for iteration_dir in iteration_dirs:
        # The per-node registry is written at the instant a provider session id
        # appears and is therefore the only durable source for the confined
        # Claude transcript path.  The supervisor manifest enriches these rows
        # with winner/continuation metadata but must not replace them.
        node_records = [
            {
                **record,
                "source": "node_memory/agent_sessions.jsonl",
                "iteration_dir": str(iteration_dir),
            }
            for registry in sorted(
                iteration_dir.glob("node_memory/*/agent_sessions.jsonl")
            )
            for record in _read_jsonl(registry)
            if record.get("session_id")
        ]
        records.extend(node_records)
        manifest = _read_json(iteration_dir / "agent_session_ids.json")
        sessions = manifest.get("sessions") if manifest else None
        if isinstance(sessions, list):
            for item in sessions:
                if isinstance(item, dict) and item.get("session_id"):
                    record = dict(item)
                    record.setdefault("source", "agent_session_ids.json")
                    record.setdefault("iteration_dir", str(iteration_dir))
                    records.append(record)
        session_id_path = iteration_dir / "session_id.txt"
        if session_id_path.exists():
            session_id = session_id_path.read_text(encoding="utf-8").strip()
            if session_id:
                records.append({
                    "session_id": session_id,
                    "winner": True,
                    "source": "session_id.txt",
                    "iteration_dir": str(iteration_dir),
                })
    return _dedupe_session_records(records)


def _dedupe_session_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for record in records:
        session_id = str(record.get("session_id") or "").strip()
        if not session_id:
            continue
        if session_id not in merged:
            merged[session_id] = {"session_id": session_id}
            order.append(session_id)
        merged[session_id].update(record)
    return [merged[session_id] for session_id in order]


def _find_session_trace(session_id: str) -> Path | None:
    if not session_id or not CLAUDE_PROJECTS_DIR.exists():
        return None
    try:
        project_dirs = list(CLAUDE_PROJECTS_DIR.iterdir())
    except OSError:
        return None
    for project_dir in project_dirs:
        try:
            if not project_dir.is_dir():
                continue
            candidate = project_dir / f"{session_id}.jsonl"
            if candidate.exists():
                return candidate
        except OSError:
            continue
    return None


def _find_claude_trace(record: dict[str, Any]) -> Path | None:
    """Resolve one exact Claude trace, preferring the run-confined registry."""

    session_id = str(record.get("session_id") or "").strip()
    if not session_id or not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        return None
    registered = str(record.get("transcript_path") or "").strip()
    if registered:
        candidate = Path(registered)
        if candidate.is_file() and candidate.name == f"{session_id}.jsonl":
            return candidate

    iteration = Path(str(record.get("iteration_dir") or ""))
    node = str(record.get("node") or "").strip()
    if iteration.is_dir() and node:
        projects = (
            iteration
            / "runtime_private"
            / node_memory_slug(node)
            / "agent_state"
            / "claude_home"
            / "projects"
        )
        if projects.is_dir():
            try:
                matches = sorted(
                    path
                    for path in projects.glob(f"*/{session_id}.jsonl")
                    if path.is_file()
                )
            except OSError:
                matches = []
            if len(matches) == 1:
                return matches[0]
    return _find_session_trace(session_id)


def _find_codex_event_trace(record: dict[str, Any]) -> Path | None:
    iteration = Path(str(record.get("iteration_dir") or ""))
    node = str(record.get("node") or "").strip()
    if not iteration.is_dir() or not node:
        return None
    node_slug = node_memory_slug(node)
    candidate = iteration / "runtime_private" / node_slug / "codex_events.jsonl"
    return candidate if candidate.is_file() else None


def _find_codex_rollout_trace(event_trace: Path, session_id: str) -> Path | None:
    """Resolve one exact run-confined Codex rollout by its thread id.

    Eval confinement gives every node a private Codex home.  Unlike a global
    ``~/.codex`` scan, this directory contains only the current node's sessions,
    and the basename is checked against the manager-recorded thread id.  The
    rollout's cumulative token ledger survives a supervisor kill that prevents
    the public CLI stream from emitting ``turn.completed``.
    """

    sid = str(session_id or "").strip()
    if not sid or not re.fullmatch(r"[A-Za-z0-9_-]+", sid):
        return None
    sessions = event_trace.parent / "agent_state" / "codex_home" / "sessions"
    if not sessions.is_dir():
        return None
    suffix = f"-{sid}.jsonl"
    try:
        matches = sorted(
            candidate
            for candidate in sessions.rglob("*.jsonl")
            if candidate.is_file() and candidate.name.endswith(suffix)
        )
    except OSError:
        return None
    return matches[0] if len(matches) == 1 else None


def _parse_codex_rollout_usage(path: Path) -> tuple[dict[str, int] | None, int]:
    """Return the latest cumulative provider usage and checkpoint count."""

    latest: dict[str, int] | None = None
    checkpoint_count = 0
    for event in _read_jsonl(path):
        if str(event.get("type") or "") != "event_msg":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        usage = info.get("total_token_usage") if isinstance(info, dict) else None
        if not isinstance(usage, dict):
            continue
        latest = normalize_codex_usage(usage)
        checkpoint_count += 1
    return latest, checkpoint_count


def _parse_codex_trace(
    path: Path,
    *,
    session_id: str = "",
    rollout_path: Path | None = None,
) -> dict[str, Any]:
    """Read exact Codex usage without losing a supervisor-killed final turn.

    A normal public CLI stream reports one usage aggregate per completed CLI
    turn.  When the supervisor terminates an in-flight turn at the experiment
    deadline, that terminal event is absent.  Prefer Codex's cumulative,
    run-confined session ledger when available; otherwise sum completed turns
    and explicitly mark an unterminated final turn as incomplete.
    """

    stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "thinking_blocks": 0,
        "thinking_chars": 0,
        "thinking_tokens_exact": None,
        "duration_seconds": 0.0,
        "max_gap_before_thinking_seconds": 0.0,
        "usage_event_count": 0,
        "missing_terminal_usage_event_count": 0,
        "provider_checkpoint_count": 0,
        "usage_source": "codex_cli_turn_completed",
        "token_accounting_complete": True,
        "partial_turn_recovered": False,
    }
    reasoning_tokens = 0
    open_turns = 0
    for event in _read_jsonl(path):
        event_type = str(event.get("type") or "")
        if event_type == "turn.started":
            open_turns += 1
            continue
        if event_type in {"turn.completed", "turn.failed"}:
            open_turns = max(0, open_turns - 1)
        if event_type not in {"turn.completed", "turn.failed"}:
            continue
        usage = event.get("usage")
        if not isinstance(usage, dict):
            stats["missing_terminal_usage_event_count"] += 1
            continue
        normalized = normalize_codex_usage(usage)
        stats["usage_event_count"] += 1
        for key in (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        ):
            stats[key] += normalized[key]
        reasoning_tokens += normalized["reasoning_output_tokens"]
    if rollout_path is None:
        rollout_path = _find_codex_rollout_trace(path, session_id)
    rollout_usage: dict[str, int] | None = None
    if rollout_path is not None:
        rollout_usage, checkpoint_count = _parse_codex_rollout_usage(rollout_path)
        stats["provider_checkpoint_count"] = checkpoint_count
    if rollout_usage is not None:
        for key in (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        ):
            stats[key] = rollout_usage[key]
        stats["thinking_tokens_exact"] = rollout_usage[
            "reasoning_output_tokens"
        ]
        stats["usage_source"] = "run_confined_codex_session_ledger"
        stats["partial_turn_recovered"] = bool(
            open_turns > 0 or stats["missing_terminal_usage_event_count"] > 0
        )
    else:
        stats["token_accounting_complete"] = bool(
            open_turns == 0
            and stats["missing_terminal_usage_event_count"] == 0
        )
        if stats["usage_event_count"]:
            stats["thinking_tokens_exact"] = reasoning_tokens
    return stats


def _parse_agent_trace(path: Path) -> dict[str, Any]:
    stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "thinking_blocks": 0,
        "thinking_chars": 0,
        "thinking_tokens_exact": None,
        "duration_seconds": 0.0,
        "max_gap_before_thinking_seconds": 0.0,
    }
    exact_thinking_tokens = 0
    saw_exact_thinking_tokens = False
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    previous_ts: datetime | None = None
    seen_usage_keys: set[str] = set()

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_timestamp(str(event.get("timestamp") or ""))
        if ts is not None:
            start_ts = ts if start_ts is None or ts < start_ts else start_ts
            end_ts = ts if end_ts is None or ts > end_ts else end_ts
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        usage = message.get("usage")
        if not isinstance(usage, dict):
            usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        usage_key = usage_dedup_key(event, message)
        count_usage = bool(usage) and (
            not usage_key or usage_key not in seen_usage_keys
        )
        if usage_key and count_usage:
            seen_usage_keys.add(usage_key)
        if usage and count_usage:
            stats["input_tokens"] += _int_value(usage.get("input_tokens"))
            stats["output_tokens"] += _int_value(usage.get("output_tokens"))
            stats["cache_creation_input_tokens"] += _int_value(
                usage.get("cache_creation_input_tokens")
            )
            stats["cache_read_input_tokens"] += _int_value(
                usage.get("cache_read_input_tokens")
            )
            thinking_tokens = _thinking_tokens_from_usage(usage)
            if thinking_tokens is not None:
                saw_exact_thinking_tokens = True
                exact_thinking_tokens += thinking_tokens

        content = message.get("content") if isinstance(message, dict) else []
        if not isinstance(content, list):
            content = []
        thinking_in_event = False
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "thinking":
                continue
            text = str(block.get("thinking") or "")
            if not text:
                continue
            thinking_in_event = True
            stats["thinking_blocks"] += 1
            stats["thinking_chars"] += len(text)
        if thinking_in_event and ts is not None and previous_ts is not None:
            gap = max(0.0, (ts - previous_ts).total_seconds())
            stats["max_gap_before_thinking_seconds"] = max(
                stats["max_gap_before_thinking_seconds"],
                gap,
            )
        if ts is not None:
            previous_ts = ts

    if start_ts is not None and end_ts is not None:
        stats["duration_seconds"] = max(0.0, (end_ts - start_ts).total_seconds())
    if saw_exact_thinking_tokens:
        stats["thinking_tokens_exact"] = exact_thinking_tokens
    stats["duration_seconds"] = round(stats["duration_seconds"], 3)
    stats["max_gap_before_thinking_seconds"] = round(
        stats["max_gap_before_thinking_seconds"],
        3,
    )
    return stats


def _thinking_tokens_from_usage(usage: dict[str, Any]) -> int | None:
    for key in THINKING_TOKEN_KEYS:
        value = _optional_int_value(usage.get(key))
        if value is not None:
            return value
    details = usage.get("output_tokens_details")
    if isinstance(details, dict):
        for key in OUTPUT_DETAILS_TOKEN_KEYS:
            value = _optional_int_value(details.get(key))
            if value is not None:
                return value
    return None


def _parse_timestamp(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _int_value(value: Any) -> int:
    parsed = _optional_int_value(value)
    return parsed if parsed is not None else 0


def _optional_int_value(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _intent_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("intent") or "")
    return ""


def _intent_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("payload"), dict):
        return dict(value["payload"])
    return {}


def _primary_action(actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    for action in actions:
        if str(action.get("label") or "") != "managed_goal_view":
            return action
    return actions[0] if actions else None


def _action_tactic(action: dict[str, Any] | None) -> str:
    if not action:
        return ""
    observation = action.get("agent_observation")
    if isinstance(observation, dict):
        return str(observation.get("tactic") or "")
    return ""


def _action_was_accepted(action: dict[str, Any] | None) -> bool:
    """Return whether the proof action succeeded at the EasyCrypt layer."""
    if not action:
        return False
    observation = action.get("agent_observation")
    if not isinstance(observation, dict):
        return _optional_int_value(action.get("exit_code")) == 0
    if observation.get("error_summary"):
        return False
    status_text = " ".join(
        str(observation.get(key) or "")
        for key in ("kind", "outcome_kind", "message", "result")
    ).lower()
    if "rejected" in status_text or "could not use" in status_text:
        return False
    if "accepted" in status_text or observation.get("accepted_tactic"):
        return True
    if (
        observation.get("manager_action") == "commit_tactic"
        and "not changed" in str(observation.get("proof_state") or "").lower()
    ):
        return False
    return _optional_int_value(action.get("exit_code")) == 0


def _per(num: Any, den: int) -> float | None:
    if den <= 0:
        return None
    value = _optional_int_value(num)
    if value is None:
        return None
    return round(float(value) / float(den), 2)


def _first_profile_from_records(records: list[dict[str, Any]]) -> str:
    for record in records:
        profile = record.get("surface_profile")
        if profile:
            return str(profile)
    return ""


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _optional_float_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


if __name__ == "__main__":
    raise SystemExit(main())
