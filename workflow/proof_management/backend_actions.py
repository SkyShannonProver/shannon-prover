"""Normalize backend command results into manager actions."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from core.easycrypt.value_shapes import first_text as _first_text

from workflow.proof_management.analyzers.pure_tail import (
    _goal_text_contains_call_site,
)
from workflow.proof_management.common import (
    _dict,
    _drop_empty,
    _list,
    _preview,
)
from workflow.proof_management.transitions import (
    is_broad_inline_tactic as _is_broad_inline_tactic,
    structural_transition_surface as _render_structural_transition,
)
from workflow.proof_management.turn_view import intent_effect as _intent_effect

def _iter_json_objects(text: str):
    """Yield every top-level decodable JSON object in ``text``, in order.

    Backend command stdout is multi-section: human/hook display lines, legacy
    goal text (which contains brace-delimited fragments), candidate-option JSON
    previews, daemon-verify emissions, and finally the authoritative result
    block. Callers that need a *specific* object must select by marker or shape
    rather than taking the first ``{`` (see _select_json_object); this generator
    is the shared scan that makes that possible.
    """
    raw = text or ""
    decoder = json.JSONDecoder()
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] != "{":
            i += 1
            continue
        try:
            obj, end = decoder.raw_decode(raw[i:])
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict):
            yield obj
        i += max(end, 1)


def _extract_json_object(text: str) -> dict[str, Any]:
    """First decodable JSON object. Heuristic — prefer marker/shape selection.

    Retained as a last-resort fallback for command stdout that emits a single
    unambiguous JSON envelope (read-only inspects, agent-view). For anything
    whose stdout interleaves other JSON (tactic exec, workspace views) use
    _tactic_execution_result_payload / _select_json_object instead, so the
    parse never latches onto a stray earlier object.
    """
    for obj in _iter_json_objects(text):
        return obj
    return {}


def _select_json_object(text: str, predicate, *, last: bool = True) -> dict[str, Any]:
    """Return a decodable JSON object in ``text`` satisfying ``predicate``.

    ``last=True`` returns the freshest match (the authoritative result is
    emitted after any preliminary/daemon-verify blocks); ``last=False`` returns
    the first match. Returns ``{}`` if none match.
    """
    chosen: dict[str, Any] = {}
    for obj in _iter_json_objects(text):
        if predicate(obj):
            chosen = obj
            if not last:
                break
    return chosen


# The backend prints the canonical, agent-facing tactic-exec result under this
# marker (session_tactic_execution_result.format_tactic_execution_result).
_TACTIC_EXECUTION_RESULT_MARKER = "[TACTIC-EXECUTION-RESULT]"


def _tactic_execution_result_payload(text: str) -> dict[str, Any]:
    """Return the JSON object emitted under ``[TACTIC-EXECUTION-RESULT]``.

    This is the authoritative result of a probe/commit/undo. Parsing it
    explicitly avoids ``_extract_json_object``'s "first decodable ``{``"
    heuristic, which can latch onto an earlier daemon-verify/AUTO-PIVOT phase
    emission (carrying its own ``ok: false``) and mislabel a successful
    multi-goal commit as "EasyCrypt rejected the committed tactic". Uses the
    last marker occurrence so chained commits / re-verified steps report their
    final state.
    """
    raw = text or ""
    idx = raw.rfind(_TACTIC_EXECUTION_RESULT_MARKER)
    if idx < 0:
        return {}
    for obj in _iter_json_objects(raw[idx + len(_TACTIC_EXECUTION_RESULT_MARKER):]):
        return obj
    return {}


def _workspace_payload_from_stdout(text: str) -> dict[str, Any]:
    """Authoritative ProverWorkspaceView object from an ``-agent-view`` stdout.

    Selects by shape (``_looks_like_workspace_payload`` / the view's structural
    keys) rather than first-``{``, so a stray JSON fragment emitted before the
    view can never become the agent's whole visible state. Falls back to the
    first object only if nothing matches.
    """
    def _is_view(obj: dict[str, Any]) -> bool:
        return _looks_like_workspace_payload(obj) or any(
            key in obj
            for key in (
                "current_goal",
                "candidate_moves",
                "proof_status",
                "decision_context",
                "proof_position",
            )
        )

    return _select_json_object(text, _is_view, last=True) or _extract_json_object(text)


def _workspace_view_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    workspace = payload.get("workspace")
    if isinstance(workspace, dict) and isinstance(workspace.get("view"), dict):
        return workspace["view"]
    if isinstance(payload.get("current_goal"), dict) and (
        payload.get("kind") == "prover_workspace_view"
        or "candidate_moves" in payload
        or "proof_status" in payload
        or "decision_context" in payload
        or "proof_position" in payload
    ):
        return payload
    return payload if isinstance(payload, dict) else {}


def _command_summary(
    label: str,
    cmd: list[str],
    result: subprocess.CompletedProcess[str],
    duration_ms: int = 0,
    *,
    session_dir: Any = None,
) -> dict[str, Any]:
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return {
        "label": label,
        "argv": cmd,
        "exit_code": result.returncode,
        "duration_ms": int(duration_ms),
        "mutates_proof_state": _backend_args_mutate_proof_state(cmd),
        "agent_observation": _agent_observation_from_command(
            label,
            cmd,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            session_dir=session_dir,
        ),
        "stdout_chars": len(stdout),
        "stdout_lines": len(stdout.splitlines()),
        "stderr_chars": len(stderr),
        "stderr_preview": stderr[-1200:],
        "stdout_has_workspace_view": (
            "current_goal" in stdout
            and (
                "candidate_moves" in stdout
                or "decision_context" in stdout
                or "suggested_next_steps" in stdout
            )
        ),
    }


def _timeout_command_summary(
    label: str,
    cmd: list[str],
    exc: subprocess.TimeoutExpired,
    timeout: int,
    duration_ms: int = 0,
) -> dict[str, Any]:
    stdout = _timeout_stream_text(exc.output)
    stderr = _timeout_stream_text(exc.stderr)
    return {
        "label": label,
        "argv": cmd,
        "exit_code": None,
        "timed_out": True,
        "timeout_seconds": timeout,
        "duration_ms": int(duration_ms),
        "mutates_proof_state": _backend_args_mutate_proof_state(cmd),
        "agent_observation": _timeout_observation(label, cmd, timeout),
        "stdout_chars": len(stdout),
        "stdout_lines": len(stdout.splitlines()),
        "stderr_chars": len(stderr),
        "stderr_preview": stderr[-1200:],
        "stdout_has_workspace_view": (
            "current_goal" in stdout
            and (
                "candidate_moves" in stdout
                or "decision_context" in stdout
                or "suggested_next_steps" in stdout
            )
        ),
    }


def _latest_tool_view_artifact(session_dir: Any, cmd: list[str]) -> dict[str, Any] | None:
    """Read the freshest persisted ToolView for this inspect's backend tool.

    Inspect tools write a structured ToolView to
    ``session_dir/tool_views/<tool>_*.json`` even when stdout carries only the
    proof-state envelope. ``<tool>`` is the backend flag (e.g. ``-bridge-lemmas``
    -> ``bridge-lemmas``)."""
    try:
        tool = next(
            (a[1:] for a in cmd if isinstance(a, str) and a.startswith("-") and a != "-d"),
            "",
        )
        if not tool:
            return None
        matches = sorted(
            (Path(session_dir) / "tool_views").glob(f"{tool}_*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        if not matches:
            return None
        data = json.loads(matches[-1].read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _agent_observation_from_command(
    label: str,
    cmd: list[str],
    *,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    session_dir: Any = None,
) -> dict[str, Any]:
    # Parse the authoritative result, never "the first decodable JSON". Tactic
    # exec (probe / commit / undo) emits a [TACTIC-EXECUTION-RESULT] block; read
    # it by marker so the verdict reflects the recorded result, not an earlier
    # daemon-verify/AUTO-PIVOT emission that happens to decode first (which
    # mislabeled successful multi-goal commits as "rejected"). Read-only
    # inspects / agent-view emit a single envelope, so the first-object fallback
    # is unambiguous there.
    payload = _tactic_execution_result_payload(stdout) or _extract_json_object(stdout)
    # Inspect tools (e.g. -bridge-lemmas) persist their structured ToolView to
    # session_dir/tool_views/ but emit only a proof-state envelope to stdout. Pull
    # that ToolView in so its recommendations/notes reach the content builder
    # instead of falling back to a truncated raw preview. EXCEPT topics with a
    # richer dedicated content path (lemma_index roster / tactic_forms whole-text),
    # which the generic ToolView (often just a placeholder note) must not shadow.
    _tv_dedicated = {"inspect_lemma_index", "inspect_tactic_forms"}
    if (
        session_dir
        and label.startswith("inspect_")
        and label not in _tv_dedicated
        and not isinstance(payload.get("tool_view"), dict)
    ):
        _tv = _latest_tool_view_artifact(session_dir, cmd)
        if _tv and (
            (_tv.get("guidance") or {}).get("recommendations")
            or _tv.get("notes")
        ):
            payload = {**payload, "tool_view": _tv}
    result = _dict(payload.get("result"))
    execution = _dict(payload.get("execution"))
    status = _first_text(
        result.get("status"),
        payload.get("command_status"),
        payload.get("status"),
        default="ok" if exit_code == 0 else "failed",
    )
    ok_value = payload.get("ok")
    result_ok = result.get("ok")
    if isinstance(ok_value, bool):
        ok = ok_value
    elif isinstance(result_ok, bool):
        ok = result_ok
    else:
        ok = exit_code == 0
    read_only_context = _is_read_only_context_action(label)
    if read_only_context and ok:
        observation: dict[str, Any] = {
            "effect": _action_effect(label, execution),
            "result": _read_only_result_text(status),
        }
    else:
        observation = {
            "manager_action": label,
            "result": _manager_result_text(label, status, ok),
            "effect": _action_effect(label, execution),
            "proof_state": _proof_state_observation(label, execution, status),
        }
    probe_preview = _probe_preview_from_payload(label, payload)
    if probe_preview:
        observation["result"] = (
            "EasyCrypt accepted this read-only probe. The committed proof "
            "state was not changed; `goal_after_probe` shows the goal that "
            "would be visible if this tactic were committed."
        )
        observation["probe_preview"] = probe_preview
        preview_tactic = _first_text(
            probe_preview.get("tactic"),
            _first_list_text(execution.get("submitted_tactics")),
            _command_arg_after(cmd, "-c"),
            default="",
        )
        decision = _accepted_probe_decision_surface(
            preview_tactic,
            probe_preview,
        )
        if decision:
            observation.update(decision)
    content = _content_observation_from_payload(label, payload, stdout)
    if content:
        observation["content"] = content
    tactic = _first_text(
        _first_list_text(execution.get("submitted_tactics")),
        _command_arg_after(cmd, "-c"),
        default="",
    )
    if tactic:
        observation["tactic"] = tactic
    error_summary = _error_summary(payload, stderr, ok=ok)
    # A read-only `probe_tactic` whose TACTIC was rejected still reports ok=True (the
    # probe TOOL ran fine; only EC rejected the tactic), so `not ok` alone MISSES it.
    # That is the exact gap that left a rejected `inline` probe with no `why`, so the
    # agent guessed for minutes why it failed (MEE-CBC L4, 2026-06-06). Recover the EC
    # error whenever the step was rejected — a failed commit (`not ok`) OR a rejected
    # probe (`status == "probe_rejected"`).
    tactic_rejected = (not ok) or str(status).strip() == "probe_rejected"
    if not error_summary and tactic_rejected:
        # The authoritative [TACTIC-EXECUTION-RESULT] block omits structured
        # `errors` on some rejections (e.g. "cannot infer all placeholders"); the
        # daemon's agent-view envelope (also in stdout) still carries the raw EC
        # error. Recover it so last_result says *why* the tactic was rejected —
        # critical for L1 (commit) and for every L4 probe, whose result text already
        # tells the agent to "use the error summary". Read-only: never alters a verdict.
        error_summary = _stdout_error_summary(stdout)
    if error_summary:
        observation["error_summary"] = error_summary
    if label == "probe_tactic" and (
        str(status).strip() == "probe_error"
        or (not ok and str(status).strip() != "probe_rejected")
    ):
        observation["kind"] = "probe_tool_error"
    return _drop_empty(observation)


# tactic_forms is a STATIC, BOUNDED argument-forms reference; the largest entry
# (`call`) is ~5.4KB / 12 forms. The agent pulls it precisely to disambiguate a
# form, so it must be shown WHOLE — the generic 1200-char preview lands mid-list
# around Form 4, disproportionately the form the agent needs (e.g. `call`'s
# upto-bad 3-arg form, `eager` Form 4). Generous fixed cap (fits all 21 covered
# tactics + headroom) so the view stays bounded without clipping a real form.
_TACTIC_FORMS_PREVIEW_LIMIT = 8000

# lemma_index is an UNBOUNDED whole-file roster the agent pulls to see what is
# available to apply/rewrite/bridge with; the generic 1200-char flatten-and-cut
# dropped the load-bearing lemmas (chacha: 51 entries cut to ~9) and sliced the
# last entry mid-signature. Generous budget that fits typical files whole; large
# files degrade by cutting at a lemma boundary with an explicit count + escape.
_LEMMA_INDEX_PREVIEW_LIMIT = 14000


def _lemma_index_preview(text: str, *, limit: int) -> str:
    """Keep WHOLE lemma entries (line structure preserved) up to `limit`; when a
    large file overflows, cut at a lemma boundary and note how many were dropped so
    the agent reaches for `lookup_symbol` instead of seeing a silently short list."""
    text = (text or "").rstrip()
    if len(text) <= limit:
        return text
    lines = text.split("\n")

    def _entry(ln: str) -> bool:  # a lemma entry starts e.g. "L42 [lemma, top_level] addrA:"
        return ln[:1] == "L" and ln[1:2].isdigit() and " [" in ln[:48]

    starts = [i for i, ln in enumerate(lines) if _entry(ln)]
    if not starts:
        return text[: max(0, limit - 1)].rstrip() + "…"
    bounds = starts + [len(lines)]
    kept = ["\n".join(lines[: starts[0]])]
    used = len(kept[0])
    shown = 0
    for k in range(len(starts)):
        entry = "\n".join(lines[bounds[k] : bounds[k + 1]])
        if used + len(entry) + 1 > limit:
            break
        kept.append(entry)
        used += len(entry) + 1
        shown += 1
    note = (
        f"\n… ({len(starts) - shown} more lemma(s) not shown — the file index is "
        "large; `lookup_symbol <name>` for any specific lemma)"
    )
    return "\n".join(kept).rstrip() + note


def _content_observation_from_payload(
    label: str,
    payload: dict[str, Any],
    stdout: str,
) -> dict[str, Any]:
    content: dict[str, Any] = {}
    topic = str(payload.get("topic") or "").strip()
    if topic:
        title = _context_topic_title(topic)
        if title:
            content["title"] = title
    goal_info_surface = _goal_info_content_surface(label, payload)
    if goal_info_surface:
        content.update(goal_info_surface)
    for key in ("runtime_note",):
        if payload.get(key) not in (None, "", [], {}):
            content[key] = payload.get(key)
    items: list[dict[str, Any]] = []
    observations = payload.get("observations")
    if isinstance(observations, list) and observations:
        items.extend(
            _context_item_surface(obs)
            for obs in observations
            if isinstance(obs, dict)
        )
    tool_view = payload.get("tool_view")
    if isinstance(tool_view, dict):
        guidance = _dict(tool_view.get("guidance"))
        recs = _list(guidance.get("recommendations"))
        if recs:
            # Prefer tool-view recommendations because they preserve the
            # candidate/action string. They represent the same content as the
            # legacy observations, so avoid showing both.
            items = [
                _context_item_surface(rec)
                for rec in recs
                if isinstance(rec, dict)
            ]
        notes = _list(tool_view.get("notes"))
        if notes:
            content["notes"] = [
                _message_surface(note)
                for note in notes
                if isinstance(note, dict)
            ][:3]
    if items:
        content["items"] = _dedupe_context_items(items)[:6]
    else:
        result_text = _context_content_result_text(payload)
        if result_text:
            content["result"] = result_text
    if label == "inspect_call_subgoals":
        preview = _text_preview(stdout, limit=1200)
        if preview and not _looks_like_workspace_payload(payload):
            call_surface = _call_subgoal_preview_surface(preview)
            if content:
                return _drop_empty({**content, **call_surface})
            return call_surface
    if label == "inspect_operator_lemmas":
        # Live EC `search OP.` output — a lemma roster (like lemma_index), shown WHOLE so
        # the project-local hits are not truncated mid-list. Merge with content so the
        # generic "recorded as raw evidence" note does not short-circuit the preview.
        preview = _lemma_index_preview(stdout, limit=_LEMMA_INDEX_PREVIEW_LIMIT)
        if preview and not _looks_like_workspace_payload(payload):
            return _drop_empty({**content, "preview": preview})
    if content:
        return _drop_empty(content)
    if label.startswith("inspect_") or label == "lookup_symbol":
        # Reference rosters the agent pulls to see in full get a generous preview
        # (tactic_forms whole; lemma_index boundary-aware); every other inspect/
        # lookup preview stays capped at 1200.
        if label == "inspect_lemma_index":
            preview = _lemma_index_preview(stdout, limit=_LEMMA_INDEX_PREVIEW_LIMIT)
        else:
            limit = (
                _TACTIC_FORMS_PREVIEW_LIMIT
                if label == "inspect_tactic_forms" else 1200
            )
            preview = _text_preview(stdout, limit=limit)
        if preview and not _looks_like_workspace_payload(payload):
            return {"preview": preview}
    return {}


def _goal_info_content_surface(label: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool = str(payload.get("tool") or "").strip().replace("_", "-")
    if label != "inspect_goal_info" and tool != "goal-info":
        return {}

    guidance = _dict(payload.get("guidance"))
    goal_info = _dict(guidance.get("goal_info"))
    proof_state = _dict(payload.get("proof_state"))
    goal_state = _dict(proof_state.get("goal"))
    history = _dict(proof_state.get("history"))
    latest_transition = _dict(proof_state.get("latest_transition"))

    content: dict[str, Any] = {"title": _context_topic_title("goal_info")}
    if goal_info:
        content["goal_info"] = goal_info
    if goal_state:
        content["goal_state"] = _drop_empty({
            "state_kind": goal_state.get("state_kind"),
            "goal_type": goal_state.get("goal_type"),
            "num_remaining": goal_state.get("num_remaining"),
            "num_remaining_determined": goal_state.get("num_remaining_determined"),
            "proof_candidate_closed": goal_state.get("proof_candidate_closed"),
            "active_goal_hash": goal_state.get("active_goal_hash"),
            "authority": goal_state.get("authority"),
            "ec_ground_truth": goal_state.get("ec_ground_truth"),
        })
    if history:
        content["history"] = _drop_empty({
            "tactic_count": history.get("tactic_count"),
            "has_qed": history.get("has_qed"),
            "latest_tactic": _preview(str(history.get("latest_tactic") or ""), limit=320),
        })
    if latest_transition:
        content["latest_transition"] = _drop_empty({
            "kind": latest_transition.get("kind"),
            "status": latest_transition.get("status"),
            "goals_before": latest_transition.get("goals_before"),
            "goals_after": latest_transition.get("goals_after"),
            "candidate_closed": latest_transition.get("candidate_closed"),
            "no_progress": latest_transition.get("no_progress"),
            "no_progress_reason": latest_transition.get("no_progress_reason"),
            "latest_error": latest_transition.get("latest_error"),
            "tactic": _preview(str(latest_transition.get("tactic") or ""), limit=320),
        })

    recommendations = _list(guidance.get("recommendations"))
    if recommendations:
        content["items"] = [
            _context_item_surface(item)
            for item in recommendations
            if isinstance(item, dict)
        ][:6]
    notes = _list(payload.get("notes"))
    if notes:
        content["notes"] = [
            _message_surface(note)
            for note in notes
            if isinstance(note, dict)
        ][:3]
    errors = _list(payload.get("errors"))
    if errors:
        content["errors"] = [
            _message_surface(error)
            for error in errors
            if isinstance(error, dict)
        ][:3]

    return _drop_empty(content)


def _context_item_surface(rec: dict[str, Any]) -> dict[str, Any]:
    metadata = _dict(rec.get("metadata"))
    confidence = str(rec.get("confidence") or "").strip()
    verification = ""
    if confidence == "verified":
        verification = "daemon-verified against the current goal"
    elif confidence:
        verification = "not daemon-verified against the current goal"
    return _drop_empty({
        "candidate": rec.get("action") or rec.get("candidate"),
        "why": rec.get("why"),
        "effect": _context_effect_text(metadata.get("effect") or rec.get("effect")),
        "verification": verification,
        "runtime_note": metadata.get("runtime_note"),
        "submit": metadata.get("submit"),
    })


def _context_effect_text(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if normalized in {
        "context only; proof state unchanged",
        "read-only; proof state unchanged",
    }:
        return (
            "This is route-selection context only; it does not run a tactic "
            "or change the EasyCrypt proof state."
        )
    return normalized


def _probe_preview_from_payload(
    label: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if label != "probe_tactic":
        return {}
    candidate = _dict(payload.get("candidate_after"))
    if str(candidate.get("status") or "") != "probe_accepted":
        return {}
    goal = _dict(candidate.get("current_goal"))
    lines = [
        str(item)
        for item in _list(goal.get("lines"))
        if isinstance(item, str)
    ]
    goal_after_probe = _drop_empty({
        "lines": lines,
        "line_count": goal.get("line_count") or len(lines),
        "char_count": goal.get("char_count"),
        "shown_lines": goal.get("shown_lines"),
        "text_fully_shown": goal.get("text_fully_shown"),
        "truncated": goal.get("truncated"),
        "source": goal.get("source"),
    })
    if not goal_after_probe:
        return {}
    return _drop_empty({
        "tactic": candidate.get("tactic"),
        "outcome": "EasyCrypt accepted this read-only probe.",
        "goal_after_remaining": candidate.get("goal_after_remaining"),
        "effect": (
            "This preview is speculative only; the committed EasyCrypt proof "
            "state was not changed."
        ),
        "goal_after_probe": goal_after_probe,
    })


def _accepted_probe_decision_surface(
    tactic: str,
    preview: dict[str, Any],
) -> dict[str, Any]:
    transition = _render_structural_transition(
        tactic,
        status="accepted_checkpoint",
        submit_intent="commit_tactic",
    )
    goal_after = _dict(preview.get("goal_after_probe"))
    preview_summary = _drop_empty({
        "remaining_goals": preview.get("goal_after_remaining"),
        "line_count": goal_after.get("line_count"),
        "char_count": goal_after.get("char_count"),
        "truncated": goal_after.get("truncated"),
    })
    preview_effects = _accepted_probe_preview_effects(tactic, preview)
    if transition.get("kind") == "closing_or_checking":
        return _drop_empty({
            "kind": "accepted_closing_probe",
            "message": "This closing/checking probe was accepted.",
            "accepted_tactic": tactic,
            "closing_decision": transition,
            "preview_summary": preview_summary,
        })
    if preview_effects:
        transition = dict(transition)
        commit_action = transition.pop("recommended_next", None)
        if commit_action:
            transition["available_commit"] = commit_action
        transition["observed_risk"] = preview_effects.get("observed_risk")
        return _drop_empty({
            "kind": "accepted_structural_probe_preview",
            "message": "This structural probe was accepted.",
            "accepted_tactic": tactic,
            "structural_transition": transition,
            "effect": (
                "Committing this accepted tactic would change the EasyCrypt "
                "proof state and return a post-commit workspace view."
            ),
            "preview_effects": preview_effects,
            "if_route_wrong": transition.get("if_wrong_after_commit"),
            "preview_summary": preview_summary,
        })
    return _drop_empty({
        "kind": "accepted_structural_transition",
        "message": "This structural transition probe was accepted.",
        "accepted_tactic": tactic,
        "structural_transition": transition,
        "question": f"Do you want to enter the {transition.get('phase')} workbench?",
        "recommended_next": transition.get("recommended_next"),
        "guidance": (
            "If yes, commit this exact tactic and read the real post-commit "
            "workbench. If no, choose another probe or inspect the current "
            "state. Do not solve the speculative preview in your mental model."
        ),
        "if_route_wrong": transition.get("if_wrong_after_commit"),
        "preview_summary": preview_summary,
    })


def _accepted_probe_preview_effects(
    tactic: str,
    preview: dict[str, Any],
) -> dict[str, Any]:
    if not _is_broad_inline_tactic(str(tactic or "").lower()):
        return {}
    goal_after = _dict(preview.get("goal_after_probe"))
    lines = "\n".join(
        str(line)
        for line in _list(goal_after.get("lines"))
        if isinstance(line, str)
    )
    return _drop_empty({
        "kind": "broad_inline_preview",
        "after": {
            "remaining_goals": preview.get("goal_after_remaining"),
            "line_count": goal_after.get("line_count"),
            "char_count": goal_after.get("char_count"),
            "truncated": goal_after.get("truncated"),
            "goal_contains_call_site": (
                _goal_text_contains_call_site(lines) if lines else None
            ),
        },
        "observed_risk": "broad_inline_can_reduce_call_site_handles",
        "reversible_to": "last_call_site_boundary",
    })


def _call_subgoal_preview_surface(preview: str) -> dict[str, Any]:
    normalized = preview.lower()
    if "accepted by daemon" in normalized:
        result = (
            "The previewed call typechecked against the daemon; no tactic was "
            "committed."
        )
    elif "rejected by daemon" in normalized or "was rejected" in normalized:
        result = (
            "The previewed call did not typecheck against the daemon; no tactic "
            "was committed."
        )
    else:
        result = (
            "The manager returned a call-obligation preview; no tactic was "
            "committed."
        )
    return _drop_empty({
        "title": "Call Obligation Preview",
        "result": result,
        "preview": preview,
    })


def _is_read_only_context_action(label: str) -> bool:
    return label.startswith("inspect_") or label == "lookup_symbol"


def _read_only_result_text(status: str) -> str:
    normalized = str(status or "").strip()
    if normalized in {"", "ok", "available"}:
        return "The manager returned read-only context for the current goal."
    if normalized == "no_matching_context":
        return "Manager found no matching context for the current goal."
    return "The manager returned read-only context for the current goal."


def _manager_result_text(label: str, status: str, ok: bool) -> str:
    normalized = str(status or "").strip()
    # NO-PROGRESS: EasyCrypt ACCEPTED the tactic, but it changed nothing (structural
    # no-op), so a commit auto-reverts (`no_progress_reverted`) and a probe reports
    # `probe_no_progress`. This is NOT a syntax/type error — there is no error to
    # surface (errors=None). Routing it through the generic "rejected — use the error
    # summary" text misleads the agent into hunting a non-existent error: observed
    # live (MEE-CBC L1, 2026-06-06), the agent burned turns re-trying `inline` variants
    # that EC accepted-but-no-op'd, each time told to "use the error summary" with none
    # present. Say the truth instead: accepted, no effect, pick a different tactic.
    if normalized in {"no_progress_reverted", "probe_no_progress"}:
        verb = "probe" if label == "probe_tactic" else "commit"
        return (
            f"NO PROGRESS — EasyCrypt ACCEPTED this {verb} but it did not change the "
            "goal, so nothing was committed (it auto-reverts). This is NOT a syntax or "
            "type error — there is no error to fix. The tactic is a no-op at this goal "
            "(e.g. the call is already effectively inlined, or it needs a different / "
            "positional form). Re-trying this exact tactic will no-op again — pick a "
            "different tactic."
        )
    if label == "probe_tactic":
        if ok and normalized == "probe_accepted":
            return (
                "EasyCrypt accepted this read-only probe. The committed proof "
                "state was not changed."
            )
        if normalized in {"probe_error", "tool_error"}:
            return (
                "The read-only probe tool failed before EasyCrypt could "
                "validate this tactic. The committed proof state was not "
                "changed; use the error summary as a backend health signal, "
                "not as proof that the tactic is invalid."
            )
        # EC validated and REJECTED the tactic. The daemon reports ok=False for a
        # rejection, but this is a genuine EasyCrypt rejection — NOT a tool/transport
        # failure. The old `or not ok` above mislabeled it as "tool failed before
        # EasyCrypt could validate", contradicting the surfaced EC error (MEE-CBC L4
        # 2026-06-06, probe `inline PseudoRP.fi.` → `unknown procedure`). The EC error
        # is in error_summary.
        return (
            "EasyCrypt rejected this probe. The committed proof state was not "
            "changed; the EasyCrypt error tells you why."
        )
    if label == "commit_tactic":
        if ok and normalized in {"ok", "accepted", "success"}:
            return "EasyCrypt accepted the committed tactic."
        if ok:
            return "The manager finished the commit attempt and refreshed the workspace view."
        return (
            "EasyCrypt rejected the committed tactic. Use the error summary "
            "and current goal to revise the proof step."
        )
    if label == "probe_replay_suffix_chunk":
        return (
            "The manager checked an old route chunk in a scratch verifier "
            "session; the committed proof state was not changed."
        )
    if label == "commit_replay_suffix_chunk":
        if ok:
            return "The manager committed a verifier-checked old route chunk."
        return "The manager did not commit the old route chunk."
    if label == "fresh_restart":
        if ok:
            return (
                "EasyCrypt restarted this node from the target lemma; prior "
                "committed tactics in this node were discarded."
            )
        return "The manager could not restart this node."
    if label == "undo_to_checkpoint":
        if ok:
            return "The manager rewound this branch to the selected checkpoint."
        return "The manager could not rewind to the selected checkpoint."
    if ok:
        return "The manager completed this proof-level request."
    return "The manager could not complete this proof-level request."


def _context_topic_title(topic: str) -> str:
    return {
        "goal_info": "Parsed Goal Information",
        "diagnose": "Latest Failure Diagnosis",
        "episode_view": "Proof Timeline",
        "proof_frontier": "Proof Frontier Context",
        "pivot_context": "Pr Route Context",
        "verified_pivot_options": "Verified Pr Route Options",
        "call_site_options": "Call-Site Context",
        "call_invariant_skeleton": "Call-Invariant Glob Skeleton",
        "call_subgoals": "Call Obligation Preview",
        "lemma_hints": "Lemma Hint Context",
        "lemma_index": "Whole-File Lemma Index",
        "operator_lemmas": "Operator → Loaded Lemmas (live EC search)",
        "pr_bridge_routes": "Verified Pr Bridge Routes",
        "equiv_bridge_lemmas": "Equiv Bridge Lemma Context",
        "bridge_lemmas": "Equiv Bridge Lemma Context",   # back-compat alias
        "bridge_options": "Verified Pr Bridge Routes",   # back-compat alias
        "rewrite_candidates": "Rewrite Candidate Context",
        "suggest_close": "Closing Context",
        "tactic_forms": "Tactic Form Reference",
        "align": "Left/Right Alignment Context",
    }.get(topic, "")


def _context_content_result_text(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "").strip()
    if status == "no_matching_context":
        return "No matching context was found for the current goal."
    count = 0
    observations = payload.get("observations")
    if isinstance(observations, list):
        count = len(observations)
    tool_view = payload.get("tool_view")
    if isinstance(tool_view, dict):
        guidance = _dict(tool_view.get("guidance"))
        recs = _list(guidance.get("recommendations"))
        count = max(count, len(recs))
    if count:
        return f"{count} context item(s) returned."
    if status in {"ok", "available"}:
        return "Context returned."
    return ""


def _dedupe_context_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        clean = _drop_empty(item)
        key = json.dumps(clean, sort_keys=True)
        if not clean or key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def _message_surface(message: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty({
        "message": message.get("message"),
        "severity": message.get("severity"),
    })


def _looks_like_workspace_payload(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("kind") == "prover_workspace_view"
        or (
            isinstance(payload.get("workspace"), dict)
            and isinstance(_dict(payload.get("workspace")).get("view"), dict)
        )
    )


def _timeout_observation(label: str, cmd: list[str], timeout: int) -> dict[str, Any]:
    return _drop_empty({
        "manager_action": label,
        "result": "The manager action timed out before producing a new completed view.",
        "effect": (
            "The attempted action may have touched the backend; the manager "
            "returned the last completed workspace view."
            if _backend_args_mutate_proof_state(cmd)
            else (
                "This was a read-only manager request; it did not change the "
                "EasyCrypt proof state."
            )
        ),
        "proof_state": (
            "The manager could not confirm a new proof state before the timeout."
            if _backend_args_mutate_proof_state(cmd)
            else "The committed EasyCrypt proof state was not changed."
        ),
        "tactic": _command_arg_after(cmd, "-c"),
        "timeout_seconds": timeout,
    })


def _action_effect(label: str, execution: dict[str, Any]) -> str:
    mode = _first_text(execution.get("mode"), default="")
    if label.startswith("inspect_") or label == "lookup_symbol":
        return (
            "This asks the manager for information only; it does not change "
            "the EasyCrypt proof state."
        )
    if label == "probe_tactic" or mode == "probe":
        return (
            "This is a read-only probe; it asks EasyCrypt what would happen "
            "without changing the committed proof state."
        )
    if bool(execution.get("state_changed") or execution.get("history_committed")):
        return (
            "EasyCrypt accepted a proof-state change; the refreshed view is "
            "based on the new committed state."
        )
    if label == "fresh_restart":
        return (
            "This explicitly restarts the current node's EasyCrypt session "
            "from the target lemma and discards this node's committed branch."
        )
    if label == "undo_to_checkpoint":
        return (
            "This rewinds the current node's committed branch to the selected "
            "checkpoint and returns the refreshed view."
        )
    if label == "commit_tactic":
        return (
            "The manager attempted to commit a tactic; use the result and "
            "latest goal to decide what changed."
        )
    return _intent_effect(label)


def _proof_state_observation(
    label: str,
    execution: dict[str, Any],
    status: str,
) -> str:
    normalized = str(status or "").strip()
    if label == "probe_replay_suffix_chunk":
        return "The committed EasyCrypt proof state was not changed."
    if label == "commit_replay_suffix_chunk":
        return "The committed EasyCrypt proof state changed if the replay chunk was accepted."
    if label == "probe_tactic" or _first_text(execution.get("mode"), default="") == "probe":
        return "The committed EasyCrypt proof state was not changed."
    if normalized in {"no_progress", "no_progress_reverted", "probe_no_progress"}:
        return "The committed EasyCrypt proof state was not changed."
    if bool(execution.get("state_changed") or execution.get("history_committed")):
        return "The committed EasyCrypt proof state changed."
    if normalized in {"probe_rejected", "failed", "error", "rejected"}:
        return "The committed EasyCrypt proof state was not changed."
    if label.startswith("inspect_") or label == "lookup_symbol":
        return "The committed EasyCrypt proof state was not changed."
    if label == "fresh_restart":
        return "The EasyCrypt proof state was reset to the target lemma start."
    if label == "undo_to_checkpoint":
        return "The EasyCrypt proof state was rewound to the selected checkpoint."
    return ""


def _extract_daemon_rejected(raw_excerpt: str) -> str:
    """The EC daemon prints `[DAEMON_REJECTED] <reason>` (e.g. `[DAEMON_REJECTED]
    unknown procedure: PseudoRP.fi`) when it rejects a tactic. That reason carries no
    `error_excerpt:`/`errors` structure, so the other extractors miss it — recover it
    so a daemon rejection is not surfaced as an empty error summary."""
    for line in (raw_excerpt or "").splitlines():
        s = line.strip()
        if s.startswith("[DAEMON_REJECTED]"):
            reason = s[len("[DAEMON_REJECTED]"):].strip()
            if reason:
                return _preview(reason, limit=280)
    return ""


def _error_summary(payload: dict[str, Any], stderr: str, *, ok: bool = False) -> str:
    result = _dict(payload.get("result"))
    # Structured EC error fields FIRST: a daemon/tactic rejection carries the clean
    # reason directly in result.error / result.failure_reason (e.g. "[error] unknown
    # procedure: PseudoRP.fi"). These were never read, so a `[DAEMON_REJECTED]`
    # commit/probe landed error_summary=None and the agent was told to "use the error
    # summary" with none present (root-caused by EC replay, MEE-CBC L1/L4 2026-06-06).
    structured = _first_text(result.get("error"), result.get("failure_reason"), default="")
    if structured.strip():
        return _preview(structured.strip(), limit=280)
    raw_excerpt = _first_text(result.get("raw_excerpt"), default="")
    extracted = _extract_error_excerpt(raw_excerpt)
    if extracted:
        return extracted
    extracted = _extract_try_error_summary(raw_excerpt)
    if extracted:
        return extracted
    extracted = _extract_daemon_rejected(raw_excerpt)
    if extracted:
        return extracted
    for item in _list(payload.get("errors")):
        if isinstance(item, dict):
            text = _first_text(
                item.get("message"),
                item.get("diagnostic"),
                item.get("error"),
                default="",
            )
            if text:
                return _preview(text, limit=280)
        elif str(item).strip():
            return _preview(str(item), limit=280)
    # Raw-stderr fallback — ONLY when the action FAILED. Structured proof errors
    # (raw_excerpt / errors above) are read regardless of status, so a probe
    # rejection still surfaces its detail. But session_cli also writes purely
    # INFORMATIONAL notices to stderr on SUCCESS (exit 0) — notably the
    # "[session_cli] Restart #N: discarding K committed tactic(s) … Proceeding
    # with fresh session" line emitted when a checkpoint rewind restarts+replays.
    # Promoting that to error_summary surfaced a SUCCESSFUL undo_to_checkpoint to
    # the agent as a manager_error claiming its committed work was discarded — a
    # misleading signal. Only fall back to stderr when the command did not succeed.
    if not ok and stderr.strip():
        return _preview(stderr.strip(), limit=280)
    return ""


def _stdout_error_summary(stdout: str) -> str:
    """Recover the raw EasyCrypt error from any JSON object in a failed command's
    stdout — used when the [TACTIC-EXECUTION-RESULT] block carried no structured
    ``errors`` but the daemon agent-view envelope (also in stdout) did. Raw EC
    text only; no heuristic classification (that stays in ec_error_classifier)."""
    for obj in _iter_json_objects(stdout or ""):
        for item in _list(obj.get("errors")):
            if isinstance(item, dict):
                text = _first_text(
                    item.get("message"),
                    item.get("diagnostic"),
                    item.get("error"),
                    default="",
                )
                if text:
                    return _preview(text, limit=280)
            elif str(item).strip():
                return _preview(str(item), limit=280)
    return ""


def _extract_try_error_summary(raw_excerpt: str) -> str:
    if not raw_excerpt:
        return ""
    lines = [line.strip() for line in raw_excerpt.splitlines() if line.strip()]
    selected: list[str] = []
    for line in lines:
        if line.startswith("[TRY] error:"):
            selected.append(line.removeprefix("[TRY] error:").strip())
            continue
        if line.startswith("[TRY] sync_detail:"):
            selected.append(
                "sync_detail: "
                + line.removeprefix("[TRY] sync_detail:").strip()
            )
    if not selected:
        return ""
    return _preview(" ".join(selected), limit=280)


def _extract_error_excerpt(raw_excerpt: str) -> str:
    if not raw_excerpt:
        return ""
    lines = [line.strip() for line in raw_excerpt.splitlines()]
    for idx, line in enumerate(lines):
        if "error_excerpt:" not in line:
            continue
        tail: list[str] = []
        for item in lines[idx + 1:]:
            if not item:
                continue
            if item.startswith("[") and tail:
                break
            if item.startswith("["):
                continue
            tail.append(item)
        if tail:
            return _preview(" ".join(tail), limit=280)
    return ""


def _command_arg_after(cmd: list[str], flag: str) -> str:
    try:
        idx = cmd.index(flag)
    except ValueError:
        return ""
    try:
        return str(cmd[idx + 1]).strip()
    except IndexError:
        return ""


def _first_list_text(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    for item in value:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return ""



def _text_preview(text: str, *, limit: int) -> str:
    """Preview structured stdout without destroying its layout.

    `tactic_forms`, call-subgoal previews, signatures, and many EasyCrypt inspect
    outputs are already human-readable line-oriented text.  The generic `_preview`
    intentionally flattens whitespace for one-line summaries, but using it for
    returned context content turns forms/lemmas into an unreadable paragraph.
    """
    shown = str(text or "").rstrip()
    if len(shown) <= limit:
        return shown
    return shown[: max(0, limit - 3)].rstrip() + "..."


def _timeout_stream_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _backend_args_mutate_proof_state(cmd: list[str]) -> bool:
    flags = set(str(part) for part in cmd)
    if "-tactic-exec" in flags:
        try:
            idx = cmd.index("-tactic-exec")
            mode = str(cmd[idx + 1])
        except (ValueError, IndexError):
            mode = ""
        return mode != "probe"
    return bool(flags & {"-start", "-next", "-prev", "-chain", "-replay"})




extract_json_object = _extract_json_object
workspace_payload_from_stdout = _workspace_payload_from_stdout
workspace_view_from_payload = _workspace_view_from_payload
command_summary = _command_summary
timeout_command_summary = _timeout_command_summary
agent_observation_from_command = _agent_observation_from_command
content_observation_from_payload = _content_observation_from_payload
backend_args_mutate_proof_state = _backend_args_mutate_proof_state
accepted_probe_preview_effects = _accepted_probe_preview_effects
