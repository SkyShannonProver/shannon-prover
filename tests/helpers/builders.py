"""Canonical test-data builders shared across the tests/ tree.

Import-safe from both runners:

- pytest puts the project root on ``sys.path`` via ``tests/conftest.py``;
- standalone scripts (``python3 tests/test_foo.py``) insert the root
  themselves before importing ``tests.helpers.builders``.

Test files keep their local helper names (``_summary``, ``_start_event``,
...) as thin delegates/aliases so call sites stay untouched.
"""
from __future__ import annotations

from pathlib import Path

from core.easycrypt.session_events import append_event

_UNSET = object()


# ─── C1: CommandSummary payload builder ────────────────────────────────────

def command_summary(
    *,
    ok: bool = True,
    proof_status: str = "open",
    primary_action: str = "try_tactic",
    tactic: str = "wp.",
    transition_kind: str | None = None,
    transition_status: str | None = None,
    goal_hash: str = "goal-hash",
    num_remaining=_UNSET,
    final_ready: bool | None = None,
    history_committed: bool | None = None,
    candidate_closed: bool | None = None,
    no_progress: bool = False,
    state_kind: str | None = None,
    current_goal_type: str | None = None,
    runnable: list[dict] | None = None,
    inspections: list[dict] | None = None,
    probe: list[dict] | None = None,
    strategy: list[dict] | None = None,
    actions: list[dict] | None = None,
    recommendations: list[dict] | None = None,
    preview: str = "Current goal\n----\npost = x{1} = x{2}",
    command_status: str = "ok",
    failed_tactic: str = "",
    failure_reason: str = "",
    event_contract_ok: bool = True,
    consistency_ok: bool = True,
    agent_view: str = "/tmp/agent-view.json",
    commit_response: str = "/tmp/commit-response.json",
    active_recommendation_count: int | None = None,
    derived_recommendation_count: int | None = None,
    with_action_fields: bool = True,
) -> dict:
    """Build a ``command_summary`` payload (superset of the per-file copies).

    Defaults reproduce ``tests/test_prover_ux_audit.py``'s ``_summary``; the
    extra keyword arguments cover the episode-timeline and behavior-audit
    variants so their local helpers can delegate without changing payloads.
    ``with_action_fields=False`` omits the ``next.primary_action_id`` /
    ``next.actions`` / ``next.probe_tactics`` keys for the variants that
    never carried them.
    """
    is_open = proof_status == "open"
    if num_remaining is _UNSET:
        nr = 1 if is_open else 0
        nr_determined = True
    else:
        nr = num_remaining
        nr_determined = num_remaining is not None
    hc = ok if history_committed is None else history_committed
    fr = (proof_status == "verified") if final_ready is None else final_ready
    cc = (proof_status == "candidate_closed") if candidate_closed is None else candidate_closed
    t_kind = ("progress" if ok else "error") if transition_kind is None else transition_kind
    t_status = command_status if transition_status is None else transition_status
    sk = proof_status if state_kind is None else state_kind
    cg_type = ("pRHL" if is_open else "complete") if current_goal_type is None else current_goal_type

    runnable = runnable if runnable is not None else [{
        "id": "r0",
        "tactic": "sim.",
        "producer": "goal-parser",
        "confidence": "medium",
        "why": "parser suggestion",
        "source": "deterministic",
        "goal_hash": "goal-hash",
    }]
    inspections = inspections if inspections is not None else []
    probe = probe if probe is not None else []
    strategy = strategy if strategy is not None else []
    actions = actions if actions is not None else [{
        "schema_version": 1,
        "id": "r0.commit",
        "category": "commit",
        "title": "Commit runnable tactic",
        "tool": "next",
        "command": "python3 core/easycrypt/session_cli.py -d /tmp/session -next -c sim.",
        "tactic": "sim.",
        "state_changed": True,
        "cost": "moderate",
        "epistemic_status": "unverified_candidate",
        "confidence": "medium",
        "why": "parser suggestion",
        "goal_hash": "goal-hash",
        "requires_instantiation": False,
        "evidence_refs": [],
        "metadata": {},
    }] if runnable else []
    if recommendations is None:
        recommendations = [{
            "id": "r0",
            "kind": "tactic_candidate",
            "producer": "goal-parser",
            "action": "sim.",
            "why": "parser suggestion",
            "confidence": "medium",
            "source": "deterministic",
            "goal_hash": "goal-hash",
            "category": "runnable_tactic",
        }] if runnable else []

    next_block = {
        "primary_action": primary_action,
        "primary_action_id": actions[0]["id"] if actions else "",
        "actions": actions,
        "safe_next_actions": [],
        "runnable_tactics": runnable,
        "probe_tactics": probe,
        "inspection_actions": inspections,
        "strategy_hints": strategy,
        "warnings": [],
        "recommendations": recommendations,
    }
    if not with_action_fields:
        for key in ("primary_action_id", "actions", "probe_tactics"):
            next_block.pop(key)

    return {
        "schema_version": 1,
        "kind": "command_summary",
        "ok": ok and event_contract_ok and consistency_ok,
        "command": "next",
        "command_status": command_status,
        "mutation": {
            "attempted_count": 1,
            "accepted_count": 1 if hc else 0,
            "rollback_count": 0,
            "history_committed": hc,
            "failed_tactic": failed_tactic,
            "failure_reason": failure_reason,
        },
        "proof": {
            "status": proof_status,
            "candidate_ready": proof_status == "candidate_closed",
            "final_ready": fr,
            "event_contract_ok": event_contract_ok,
            "consistency_ok": consistency_ok,
            "goal_type": "pRHL" if is_open else "complete",
            "num_remaining": nr,
            "num_remaining_determined": nr_determined,
            "goal_hash": goal_hash,
            "history_tactic_count": 1,
            "latest_tactic": tactic,
        },
        "transition": {
            "kind": t_kind,
            "status": t_status,
            "tactic": failed_tactic or tactic,
            "goals_before": 1,
            "goals_after": nr,
            "candidate_closed": cc,
            "no_progress": no_progress,
            "no_progress_reason": "",
            "latest_error": failure_reason,
        },
        "current_goal": {
            "goal_type": cg_type,
            "state_kind": sk,
            "num_remaining": nr,
            "preview": preview,
        },
        "next": next_block,
        "latest_errors": [],
        "warnings": [],
        "errors": [] if ok else [{
            "code": "command.failed",
            "message": failure_reason,
            "tactic": failed_tactic,
        }],
        "artifacts": {
            "agent_view": agent_view,
            "commit_response": commit_response,
        },
        "debug": {
            "active_recommendation_count": (
                0 if active_recommendation_count is None
                else active_recommendation_count
            ),
            "derived_recommendation_count": (
                len(recommendations) if derived_recommendation_count is None
                else derived_recommendation_count
            ),
            "stale_recommendation_count": 0,
            "session_dir": "/tmp/session",
        },
    }


# ─── C2: session-event seeders ─────────────────────────────────────────────

def start_event(d: Path) -> None:
    append_event(d, "session.started", {
        "file": None,
        "lemma": "L",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })


def tool_called(d: Path, name: str, mutates: bool = True) -> None:
    append_event(d, "tool.called", {
        "name": name,
        "mutates_proof_state": mutates,
        "session_dir": str(d.resolve()),
    })


def tool_result(d: Path, name: str, mutates: bool = True, status: str = "ok") -> None:
    append_event(d, "tool.result", {
        "name": name,
        "mutates_proof_state": mutates,
        "session_dir": str(d.resolve()),
        "exit_code": 0 if status == "ok" else 1,
        "status": status,
    })


def write_open_goal(d: Path, body: str = "x = y") -> None:
    (d / "current.out").write_text(
        "[1|check]>\n"
        "Current goal\n"
        "----\n"
        f"{body}\n"
        "[2|check]>\n",
        encoding="utf-8",
    )


# ─── C4: ProofNodeManager construction ─────────────────────────────────────

def make_manager(**overrides):
    """Build the standard unit-test ProofNodeManager (kwargs overridable)."""
    from workflow.proof_node_manager import ProofNodeManager

    kwargs: dict = {
        "file_path": "eval/examples/SchnorrPK.ec",
        "lemma_name": "dummy",
        "include_dir": "easycrypt-src/theories",
        "session_tag": "unit",
        "node_id": "Tree-unit",
    }
    kwargs.update(overrides)
    return ProofNodeManager(**kwargs)


def intent(name: str, tactic: str = ""):
    """Parse a minimal agent intent (optionally carrying a tactic payload)."""
    from workflow.proof_management.protocol_repair import parse_agent_intent

    payload = '{"tactic": "%s"}' % tactic if tactic else "{}"
    return parse_agent_intent(
        '{"intent": "%s", "payload": %s}' % (name, payload)
    ).intent


# ─── C5: patch-loop / LoopMonitor oscillation harness ───────────────────────
# Shared between test_patch_loop_detector.py and test_help_mechanisms_wiring.py.

# Monotonic REPL prompt index — advances every call even when the goal is
# frozen. Views that carry the advancing ``[NNN|check]>`` line exercise Defect 1
# of the patch-loop detector: a fingerprint that did NOT strip this line would
# change every turn and the loop would never be detected.
_LOOP_PROMPT_COUNTER = [500]


def next_loop_prompt() -> int:
    """Advance and return the monotonic REPL prompt index."""
    _LOOP_PROMPT_COUNTER[0] += 3
    return _LOOP_PROMPT_COUNTER[0]


def loop_goal_view(
    label: str,
    remaining,
    *,
    layer: str = "call_site",
    moves: list | None = None,
    with_prompt_line: bool = True,
) -> dict:
    """A synthetic rendered view whose fingerprint is keyed by (label,
    remaining, layer). Distinct labels model genuinely different goals.

    ``with_prompt_line=True`` reproduces test_patch_loop_detector's shape (the
    advancing ``[NNN|check]>`` prompt line + ``view_focus``); ``False``
    reproduces test_help_mechanisms_wiring's prompt-free stub. ``moves``
    optionally attaches ``candidate_moves`` (the up-to-bad call offers).
    """
    if with_prompt_line:
        current_goal = {
            "lines": [
                f"Current goal (remaining: {remaining})",
                "----",
                f"equiv[ G1.O ~ G2.O : {label} ==> ={{res}} ]",
                f"[{next_loop_prompt()}|check]>",
            ],
            "view_focus": layer,
        }
    else:
        current_goal = {
            "lines": [
                "Current goal",
                "----",
                f"equiv[ G1.O ~ G2.O : true ==> ={{res}} ] ({label})",
            ],
        }
    view = {
        "current_goal": current_goal,
        "proof_status": {"remaining_goals": remaining, "current_layer": layer},
    }
    if moves is not None:
        view["candidate_moves"] = {"moves": moves}
    return view


def drive_osc_loop(commit, *, make_loop_view, make_away_view, arrivals: int = 3,
                   loop_tactic: str = "smt().", away_tactic: str = "auto.") -> list:
    """Drive the genuine arrive-leave-arrive loop shape the patch-loop detector
    targets: accepted commits ARRIVE at the loop goal, genuinely LEAVE via an
    accepted commit to a different goal, and arrive back — ``arrivals`` times,
    ending ON an arrival. ``commit(view, tactic)`` submits one accepted commit
    turn and returns that turn's observation; the observations are returned in
    submission order.
    """
    out = []
    for i in range(arrivals):
        if i:
            out.append(commit(make_away_view(), away_tactic))
        out.append(commit(make_loop_view(), loop_tactic))
    return out
