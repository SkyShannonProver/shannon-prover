from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

import _pathsetup
from core.easycrypt.proof_state_compiler.backend.presentation import (
    render_action_surface_payload,
)
from io import BytesIO
from tests.helpers.builders import make_manager
from types import SimpleNamespace
from workflow.agents.prover_prompt import (
    MANAGED_HANDOFF_END,
    MANAGED_HANDOFF_START,
    _build_prover_prompt,
    bind_authoritative_managed_handoff,
)
from workflow.node.agent_prompt_render import render_long_lived_agent_prompt
from workflow.node.manager_followup_render import render_manager_followup
from workflow.node.no_progress_guidance import NoProgressGuidance
from workflow.node.node_memory import NodeMemory
from workflow.node.proof_node_runtime import ProofNodeRuntime
from workflow.proof_management import (
    ManagedTurn,
    NodeHealthEvent,
    parse_agent_intent,
)
from workflow.proof_state_compiler.managed_goal_view_manager import (
    ManagedGoalViewManager,
)
from workflow.proof_state_compiler.surface_profiles import (
    project_current_workspace_view,
)
from workflow.proof_tool.proof_node_mcp_server import (
    _read_message,
    _write_message,
)
from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract


ROOT = Path(__file__).resolve().parents[1]


def _current_workspace_view(**overrides: object) -> dict[str, object]:
    view: dict[str, object] = {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "proof_status": {
            "status": "open",
            "remaining_goals_known": True,
            "goal_identity_required": True,
            "goal_hash": "goal",
        },
        "current_goal": {"lines": []},
        "view_hash": "v" * 40,
    }
    proof_status = dict(view["proof_status"])
    proof_status_overrides = overrides.pop("proof_status", {})
    proof_status.update(proof_status_overrides)
    if (
        isinstance(proof_status_overrides, dict)
        and "status" in proof_status_overrides
        and "goal_identity_required" not in proof_status_overrides
    ):
        goal_identity_required = str(proof_status["status"]) not in {
            "candidate_closed",
            "goals_discharged_pending_qed",
            "closed",
            "complete",
            "completed",
            "proved",
            "qed",
            "verified",
        }
        proof_status["goal_identity_required"] = goal_identity_required
        proof_status["goal_hash"] = "goal" if goal_identity_required else ""
    view.update(overrides)
    view["proof_status"] = proof_status
    return view


def test_completed_progress_turn_mints_checkpoint_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import workflow.node.proof_node_runtime as runtime_module

    runtime = ProofNodeRuntime.__new__(ProofNodeRuntime)
    runtime.manager = SimpleNamespace(
        latest_full_view={},
        surface_profile="l1_goal_projection",
    )
    runtime.no_progress_guidance = SimpleNamespace(
        observe=lambda _turn, _handled: ""
    )
    runtime._last_checkpointed_tactics = ()
    runtime.node_id = "Tree-unit"
    checkpoint_calls: list[bool] = []
    events: list[dict[str, object]] = []
    runtime._checkpoint_resume_capsules = lambda: (
        checkpoint_calls.append(True) or ("resume.json",)
    )
    runtime.emit = events.append
    monkeypatch.setattr(
        runtime_module,
        "render_manager_followup",
        lambda *_args, **_kwargs: "rendered",
    )
    turn = ManagedTurn(
        ok=True,
        workspace_view=_current_workspace_view(),
        committed_tactics=("proc.",),
    )

    assert runtime._render_and_checkpoint_manager_turn(
        turn, 1, None, SimpleNamespace()
    ) == "rendered"
    assert runtime._render_and_checkpoint_manager_turn(
        turn, 2, None, SimpleNamespace()
    ) == "rendered"

    assert checkpoint_calls == [True]
    assert runtime._last_checkpointed_tactics == ("proc.",)
    assert events == [{
        "type": "system",
        "kind": "proof_node.progress_checkpointed",
        "node": "Tree-unit",
        "manager_turn": 1,
        "committed_count": 1,
        "checkpoint_count": 1,
    }]


def _profiled_workspace_view(
    profile_name: str,
    **overrides: object,
) -> dict[str, object]:
    manager = ManagedGoalViewManager()
    view = project_current_workspace_view(
        _current_workspace_view(**overrides),
        profile_name,
    )
    view.pop("view_hash", None)
    view["view_hash"] = manager.view_hash(view)
    return manager.order_workspace_view(view)


def _current_bootstrap(**overrides: object) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "node_id": "Tree-unit",
        "session_tag": "unit",
        "session_dir": ".ec_session_unit",
        "session_epoch": 0,
        "state_version": 0,
        "goal_hash": "goal",
        "goal_identity_required": True,
        "workspace_view_artifact": "",
        "execution_refs": {},
    }
    snapshot_overrides = overrides.pop("snapshot", {})
    if isinstance(snapshot_overrides, dict):
        snapshot.update(snapshot_overrides)
    record: dict[str, object] = {
        "schema_version": 3,
        "kind": "proof_node_manager_bootstrap",
        "node_id": "Tree-unit",
        "session_tag": "unit",
        "session_dir": ".ec_session_unit",
        "file": "eval/examples/SchnorrPK.ec",
        "lemma": "dummy",
        "include_dirs": ["eval/examples", "easycrypt-src/theories"],
        "replay_prefix_count": 0,
        "replay_prefix": [],
        "replay_prefix_requested_count": 0,
        "manager_actions": [],
        "snapshot": snapshot,
        "workspace_view": _current_workspace_view(),
    }
    record.update(overrides)
    return record


def test_no_history_intent_added_to_manager_protocol() -> None:
    parsed = parse_agent_intent(
        '{"intent": "retrieve_history", "payload": {"topic": "recent_failures"}}'
    )

    assert parsed.ok is False


def test_long_lived_prompt_explains_runtime_and_memory(tmp_path: Path) -> None:
    prompt = render_long_lived_agent_prompt(
        "ORIGINAL PROMPT",
        proof_tool_manifest=resolve_proof_tool_contract(None),
        node_memory_dir=tmp_path / "node_memory" / "Tree_0_0",
        max_turns=7,
    )

    # §1 header
    assert "You are a long-lived prover agent for one proof node" in prompt
    assert "keep your own working memory" in prompt
    assert "current authoritative proof surface rendered" in prompt
    assert "`SurfaceTurnModel`" in prompt
    assert "Use MCP tools to interact with the manager" in prompt
    assert "structured MCP tool `submit_proof_intent`" in prompt
    assert "`LEGAL_PROOF_SO_FAR`" in prompt        # committed proof is read-on-demand now
    assert "include a `payload` object" in prompt
    assert "no shell escaping or scratch files" in prompt
    # §2 Your MCP tools — one line per granted intent
    assert "## Your MCP tools" in prompt
    for intent in (
        "`commit_tactic`", "`undo_last_step`",
        "`undo_to_checkpoint`", "`fresh_restart`", "`finish`",
    ):
        assert intent in prompt
    # State-dependent context intents are advertised by SurfaceModel actions,
    # not duplicated as a static roster in the long-lived prompt.
    assert "`tactic_forms`" not in prompt
    assert "`goal_info`" not in prompt
    assert "`inspect_context`" not in prompt
    assert "`request_restart`" not in prompt
    # No retired panel-interpretation playbook is embedded in the runtime.
    assert "## How to read the manager surface" not in prompt
    assert "candidate_moves" not in prompt
    assert "route_health" not in prompt
    # Strategy coaching and verifier policy belong to the manager/runtime, not
    # the stable presentation prompt.
    assert "## How to play well" not in prompt
    assert "be brave: COMMIT and UNDO freely" not in prompt
    assert "tracked SCAFFOLD" not in prompt
    assert "scaffold debt" not in prompt
    # §5 runtime details
    assert "## Runtime details" in prompt
    assert "LEGAL_NODE_MEMORY_DIR" in prompt
    assert "latest_followup.md" in prompt
    assert "proof_so_far.md" in prompt
    assert "Amend & replay (`amend_and_replay`)" in prompt
    assert "Required payload fields: `index`, `tactic`." in prompt
    assert "LEGAL_LATEST_WORKSPACE_VIEW" not in prompt
    assert "latest_workspace_view.json" not in prompt
    assert "If Claude context is compacted" in prompt
    assert "using shell directory discovery" in prompt
    assert "TOOL_BOUNDARY_MISSING" in prompt
    assert "mental model" not in prompt
    assert "Do not solve the speculative preview" not in prompt
    for internal_text in (
        "session_cli",
        ".claude",
        "runtime source",
        "bridge client transport",
        "submit script",
        "submit scripts",
        "worktrees",
        "bridge tokens",
        "MCP config files",
        "proof_node_runtime_client",
        "proof_node_runtime_cli",
    ):
        assert internal_text not in prompt
    assert "--port 12345" not in prompt
    assert "--token tok" not in prompt
    assert "long-lived runtime's manager bridge" not in prompt
    assert "ORIGINAL PROMPT" not in prompt


def test_long_lived_prompt_describes_source_navigation_without_new_proof_controls(
    tmp_path: Path,
) -> None:
    prompt = render_long_lived_agent_prompt(
        "ORIGINAL PROMPT",
        proof_tool_manifest=resolve_proof_tool_contract(
            "l1_goal_projection",
            source_navigation_enabled=True,
        ),
        node_memory_dir=tmp_path / "node_memory" / "Tree_0_0",
        max_turns=7,
        surface_profile="l1_goal_projection",
    )

    assert "### Source context" in prompt
    assert "`search_easycrypt_source`" in prompt
    assert "`read_easycrypt_source`" in prompt
    assert "`resolve_easycrypt_declaration`" in prompt
    assert "do not inspect or mutate proof state" in prompt
    assert "copy-ready paths, line numbers" in prompt
    assert "lexical, not a resolved declaration" in prompt
    assert "search → resolve if needed → read nearby source" in prompt
    assert "still submit exactly one proof intent" in prompt
    assert "`inspect_context`" not in prompt


def test_l1_goal_projection_prompt_lists_only_l1_goal_projection_surface(tmp_path: Path) -> None:
    prompt = render_long_lived_agent_prompt(
        "ORIGINAL PROMPT",
        proof_tool_manifest=resolve_proof_tool_contract("l1_goal_projection"),
        node_memory_dir=tmp_path / "node_memory" / "Tree_0_0",
        max_turns=7,
        surface_profile="l1_goal_projection",
    )

    assert "`commit_tactic`" in prompt
    assert "`finish`" in prompt
    # L1 keeps the control surface while omitting derived context channels.
    assert "`undo_to_checkpoint`" in prompt
    # ...but it must NOT advertise the content-retrieval channels (the panel's value).
    assert "`inspect_context`" not in prompt
    assert "`lookup_symbol`" not in prompt
    assert "semantic proof inspection" not in prompt
    assert "rendered `SurfaceTurnModel`" in prompt
    assert "runtime appends `PROOF TACTICS:`" in prompt
    assert "do not read `proof_so_far.md` only to reproduce" in prompt
    for hidden_panel in (
        "`program_frontier`",
        "`application_context`",
        "`facts_and_diagnostics`",
        "`candidate_moves`",
        "`inspect_lookup_handles`",
        "candidate_moves.",
    ):
        assert hidden_panel not in prompt


@pytest.mark.parametrize(
    ("profile", "surface", "expected", "forbidden"),
    [
        (
            "proof_state_compiler",
            """Initial manager handoff completed.

### Current Goal

authoritative L4 goal

### Ready proof action

```json
{"intent":"commit_tactic","payload":{"tactic":"move=> x."}}
```

### Legal Node Memory Anchor

duplicate runtime anchor
""",
            '"tactic":"move=> x."',
            "duplicate runtime anchor",
        ),
        (
            "l1_goal_projection",
            """Initial manager handoff completed.

### Current Goal

authoritative L1 goal
""",
            "authoritative L1 goal",
            "provisional goal",
        ),
    ],
)
def test_worker_binds_manager_authoritative_turn_zero_after_profile_render(
    tmp_path: Path,
    profile: str,
    surface: str,
    expected: str,
    forbidden: str,
) -> None:
    static_prompt = _build_prover_prompt(
        "eval/examples/SchnorrPK.ec",
        "dummy",
        "easycrypt-src/theories",
        managed_session={
            "workspace_view": _profiled_workspace_view(
                profile,
                current_goal={"lines": ["provisional goal"]},
            ),
        },
        surface_profile=profile,
    )
    worker_prompt = render_long_lived_agent_prompt(
        static_prompt,
        proof_tool_manifest=resolve_proof_tool_contract(profile),
        node_memory_dir=tmp_path / "node_memory" / "Tree_0_0",
        max_turns=7,
        surface_profile=profile,
    )

    bound = bind_authoritative_managed_handoff(worker_prompt, surface)

    assert bound.count(MANAGED_HANDOFF_START) == 1
    assert bound.count(MANAGED_HANDOFF_END) == 1
    assert expected in bound
    assert forbidden not in bound
    assert "### Legal Node Memory Anchor" not in bound


def test_node_memory_writes_curated_files(tmp_path: Path) -> None:
    memory = NodeMemory(tmp_path, "Tree-0.0")
    turn = ManagedTurn(
        ok=False,
        workspace_view=_current_workspace_view(
            current_goal={"lines": ["x = y"]},
        ),
        repair_prompt="repair please",
        manager_actions=[{
            "label": "commit_tactic",
            "exit_code": 1,
            "agent_observation": {"error_summary": "bad tactic"},
        }],
    )

    memory.record_turn(
        turn_index=1,
        raw_text='{"intent":"commit_tactic","payload":{"tactic":"bad."}}',
        handled_intent={"intent": "commit_tactic", "payload": {"tactic": "bad."}},
        turn=turn,
    )

    assert (memory.dir / "notes.md").exists()
    assert (memory.dir / "followups").is_dir()
    assert (memory.dir / "manager_results").is_dir()
    assert (memory.dir / "workspace_views").is_dir()
    assert (memory.dir / "timeline.jsonl").read_text(encoding="utf-8")
    assert (memory.dir / "attempts.jsonl").read_text(encoding="utf-8")
    failure = json.loads(
        (memory.dir / "failures.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert failure["intent"]["intent"] == "commit_tactic"
    assert failure["manager_actions"][0]["error_summary"] == "bad tactic"


def test_node_memory_persists_bootstrap_current_view(tmp_path: Path) -> None:
    memory = NodeMemory(tmp_path, "Tree-0.0.0")
    declaration = "lemma CCA_UFCMA.dec_enc : true."
    anchor = {
        "symbol": "CCA_UFCMA.dec_enc",
        "intended_use": "call",
        "role": "encryption correctness",
        "source_ref": "easycrypt-native:print:test#CCA_UFCMA.dec_enc",
        "declaration_sha256": hashlib.sha256(
            declaration.encode("utf-8")
        ).hexdigest(),
        "declaration": declaration,
    }

    memory.record_bootstrap(_current_bootstrap(
        session_tag="unit",
        session_dir=".ec_session_unit",
        replay_prefix_count=3,
        replay_prefix=["proc.", "wp.", "skip."],
        replay_prefix_requested_count=3,
        snapshot={"state_version": 3},
        workspace_view=_current_workspace_view(
            proof_status={"status": "open"},
            current_goal={"lines": ["goal at handoff"]},
        ),
        resource_anchors=[anchor],
    ))

    latest_view = json.loads(memory.latest_view.read_text(encoding="utf-8"))
    latest_result = json.loads(memory.latest_result.read_text(encoding="utf-8"))
    turn_zero_view = json.loads(
        (memory.workspace_views_dir / "turn_000.json").read_text(encoding="utf-8")
    )

    assert latest_view["current_goal"]["lines"] == ["goal at handoff"]
    assert turn_zero_view == latest_view
    assert json.loads(memory.initial_view.read_text(encoding="utf-8")) == latest_view
    assert latest_result["kind"] == "bootstrap"
    assert latest_result["replay_prefix_count"] == 3
    latest_followup = memory.latest_followup.read_text(encoding="utf-8")
    assert memory.initial_followup.read_text(encoding="utf-8") == latest_followup
    assert "LEGAL_LATEST_FOLLOWUP" in latest_followup
    assert "latest_workspace_view.json" not in latest_followup
    assert "LEGAL_LATEST_WORKSPACE_VIEW" not in latest_followup
    assert "Persistent handoff resource anchors" in latest_followup
    assert "CCA_UFCMA.dec_enc" in latest_followup
    proof = memory.latest_proof.read_text(encoding="utf-8")
    assert "Proof so far (3 committed" in proof
    assert "1. proc." in proof
    assert "3. skip." in proof


def test_node_memory_rejects_legacy_bootstrap_envelope(tmp_path: Path) -> None:
    memory = NodeMemory(tmp_path, "Tree-0.0.0")

    with pytest.raises(ValueError, match="proof_node_manager_bootstrap"):
        memory.record_bootstrap({
            "schema_version": 3,
            "kind": "manager_session_bootstrap",
            "workspace_view": _current_workspace_view(),
        })

    assert not memory.timeline.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("node_id", "Tree-other"),
        ("session_tag", "other"),
        ("session_dir", ".ec_session_other"),
        ("file", "eval/examples/Other.ec"),
        ("lemma", "other"),
    ],
)
def test_runtime_rejects_bootstrap_identity_mismatch_before_startup(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    bootstrap = _current_bootstrap()
    bootstrap[field] = value
    if field in {"node_id", "session_tag", "session_dir"}:
        snapshot = dict(bootstrap["snapshot"])
        snapshot[field] = value
        bootstrap["snapshot"] = snapshot

    with pytest.raises(ValueError, match=f"identity mismatch for `{field}`"):
        ProofNodeRuntime(
            prompt="Base prompt",
            bootstrap=bootstrap,
            file_path="eval/examples/SchnorrPK.ec",
            lemma_name="dummy",
            include_dir="easycrypt-src/theories",
            session_tag="unit",
            node_id="Tree-unit",
            run_dir=tmp_path,
            model="claude-test",
            project_root=ROOT,
            emit=lambda _event: None,
        )

    assert not (tmp_path / "node_memory").exists()


def test_adopted_worker_does_not_treat_profiled_bootstrap_as_full_view(
    tmp_path: Path,
) -> None:
    runtime = ProofNodeRuntime(
        prompt="Base prompt",
        bootstrap=_current_bootstrap(
            workspace_view=_profiled_workspace_view(
                "proof_state_compiler",
                current_goal={"lines": ["Current goal", "x = y"]},
            ),
        ),
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="unit",
        node_id="Tree-unit",
        run_dir=tmp_path,
        model="claude-test",
        surface_profile="proof_state_compiler",
        project_root=ROOT,
        emit=lambda _event: None,
    )

    assert runtime.manager.latest_full_view == {}
    turn = runtime.manager.handle_agent_message("not json")
    followup = render_manager_followup(
        turn,
        1,
        None,
        runtime.memory,
        full_view=runtime.manager.latest_full_view,
        surface_profile=runtime.manager.surface_profile,
    )

    assert "Current Goal" in followup
    assert "x = y" in followup
    assert "---\n\n---" not in followup
    stored = json.loads(
        (runtime.memory.workspace_views_dir / "turn_001.json").read_text(
            encoding="utf-8"
        )
    )
    assert stored["ok"] is True
    assert stored["current_goal"]["lines"][-1] == "x = y"

    # Turn 2 reads the curated NodeMemory copy (surface_turn present, durable
    # identity hidden); it must not reinterpret that display as a manager view.
    second = runtime.manager.handle_agent_message("still not json")
    second_followup = render_manager_followup(
        second,
        2,
        None,
        runtime.memory,
        full_view=runtime.manager.latest_full_view,
        surface_profile=runtime.manager.surface_profile,
    )
    assert "x = y" in second_followup


def test_l1_latest_view_and_turn_archive_use_the_same_current_envelope(
    tmp_path: Path,
) -> None:
    """Node memory does not invent a second L1 audit-only carrier."""
    memory = NodeMemory(tmp_path, "Tree-0.0", surface_profile="l1_goal_projection")
    profiled_view = _profiled_workspace_view(
        "l1_goal_projection",
        proof_status={"status": "open"},
        current_goal={"lines": ["goal at handoff"]},
    )
    memory.record_bootstrap(_current_bootstrap(
        session_tag="unit",
        session_dir=".ec_session_unit",
        snapshot={"state_version": 0},
        workspace_view=profiled_view,
    ))

    latest_view = json.loads(memory.latest_view.read_text(encoding="utf-8"))
    archive = json.loads(
        (memory.workspace_views_dir / "turn_000.json").read_text(encoding="utf-8")
    )

    assert "_l1_surface_notice" not in latest_view
    assert latest_view["current_goal"]["lines"] == ["goal at handoff"]
    assert latest_view == archive

    # The L1 followup no longer advertises the full view as a place to read panels.
    followup = memory.latest_followup.read_text(encoding="utf-8")
    assert "every collapsed panel" not in followup


def test_legal_node_memory_anchor_lives_in_system_prompt_not_per_turn(tmp_path: Path) -> None:
    """The LEGAL_* anchor moved to the DURABLE system prompt (Claude preserves the
    system prompt across compaction), so it is NO LONGER re-sent in every per-turn
    followup. The per-turn prompt stays lean; the anchor survives via
    _prover_system_anchor (wired through ClaudeAgentSession.run --append-system-prompt)."""
    from workflow.node.proof_node_runtime import _prover_system_anchor
    memory = NodeMemory(tmp_path, "Tree_0_0")
    declaration = "lemma size_step : true."
    memory.resource_anchors = ({
        "symbol": "size_step",
        "intended_use": "apply",
        "role": "size invariant",
        "source_ref": "easycrypt-native:print:test#size_step",
        "declaration_sha256": hashlib.sha256(
            declaration.encode("utf-8")
        ).hexdigest(),
        "declaration": declaration,
    },)
    turn = ManagedTurn(
        ok=True,
        workspace_view=_current_workspace_view(
            proof_status={"status": "open"},
            current_goal={"lines": ["x = y"]},
        ),
        manager_actions=[],
        committed_tactics=("proc.", "wp."),
    )
    followup = render_manager_followup(
        turn, 1, {"intent": "commit_tactic", "payload": {"tactic": "auto."}}, memory,
    )
    # the per-turn followup no longer carries the heavy LEGAL_* path block
    assert f"LEGAL_NODE_MEMORY_DIR: `{memory.dir}`" not in followup
    assert "Compaction recovery" not in followup
    assert "Persistent handoff resource anchors" in followup
    assert "size_step" in followup

    # but the durable SYSTEM anchor does — paths + the one-intent-per-turn invariant
    sys_anchor = _prover_system_anchor(
        memory,
        resolve_proof_tool_contract(None),
    )
    assert f"LEGAL_NODE_MEMORY_DIR: `{memory.dir}`" in sys_anchor
    assert f"LEGAL_PROOF_SO_FAR: `{memory.latest_proof}`" in sys_anchor
    assert "Compaction recovery" in sys_anchor
    assert "submit_proof_intent" in sys_anchor and "one intent" in sys_anchor.lower()
    assert "Persistent handoff resource anchors" in sys_anchor
    proof = memory.latest_proof.read_text(encoding="utf-8")
    assert "Proof so far (2 committed" in proof
    assert "1. proc." in proof
    assert "2. wp." in proof


def test_durable_system_anchor_includes_copy_ready_source_map(tmp_path: Path) -> None:
    from workflow.node.proof_node_runtime import _prover_system_anchor

    memory = NodeMemory(tmp_path, "Tree-source-map")

    class SourceMapFixture:
        @staticmethod
        def render_source_map() -> str:
            return (
                "### Readable EasyCrypt source map\n\n"
                "- `artifacts/eval_source/task.ec` — active target\n"
                "- `artifacts/eval_source/sibling.eca`"
            )

    anchor = _prover_system_anchor(
        memory,
        resolve_proof_tool_contract(None, source_navigation_enabled=True),
        SourceMapFixture(),  # type: ignore[arg-type]
    )

    assert "### Readable EasyCrypt source map" in anchor
    assert "`search_easycrypt_source`" in anchor
    assert "`read_easycrypt_source`" in anchor
    assert "`resolve_easycrypt_declaration`" in anchor
    assert "`artifacts/eval_source/task.ec` — active target" in anchor
    assert "`artifacts/eval_source/sibling.eca`" in anchor


def test_same_goal_no_progress_nudge_triggers_and_resets_on_progress() -> None:
    guidance = NoProgressGuidance(threshold=3)

    def turn(*, goal: str = "same", committed=()) -> ManagedTurn:
        return ManagedTurn(
            ok=False,
            workspace_view=_current_workspace_view(
                proof_status={"status": "open", "goal_hash": goal},
            ),
            committed_tactics=tuple(committed),
        )

    def intent(tactic: str) -> dict[str, object]:
        return {"intent": "commit_tactic", "payload": {"tactic": tactic}}

    assert guidance.observe(turn(), intent("apply guessed_one.")) == ""
    assert guidance.observe(turn(), intent("apply guessed_two.")) == ""
    nudge = guidance.observe(turn(), intent("apply guessed_three."))
    assert "Manager no-progress nudge" in nudge
    assert "3 commit attempts" in nudge
    assert "Stop cycling through guessed synonymous lemma names" in nudge
    assert "already advertised by the manager" in nudge
    assert "Do not call tools outside" in nudge
    assert "read allowed source" not in nudge
    assert guidance.observe(turn(), intent("apply guessed_four.")) == ""

    assert guidance.observe(
        turn(goal="next", committed=("trivial.",)), intent("trivial.")
    ) == ""
    assert guidance.observe(
        turn(goal="next", committed=("trivial.",)), intent("apply another_guess.")
    ) == ""


@pytest.mark.parametrize(
    ("status", "expected_instruction"),
    (
        (
            "goals_discharged_pending_qed",
            "Next valid action:** commit `qed.` with `commit_tactic`",
        ),
        (
            "session_closed_pending_verification",
            "Next valid action:** submit `finish`",
        ),
    ),
)
def test_terminal_lifecycle_status_is_visible_in_agent_followup(
    status: str,
    expected_instruction: str,
) -> None:
    turn = ManagedTurn(
        ok=True,
        workspace_view=_current_workspace_view(
            proof_status={
                "status": status,
                "remaining_goals": 0,
                "remaining_goals_known": True,
            },
            current_goal={},
        ),
        manager_actions=[],
    )

    followup = render_manager_followup(
        turn,
        1,
        {"intent": "commit_tactic", "payload": {"tactic": "done."}},
    )

    assert f"**Status:** `{status}`" in followup
    assert expected_instruction in followup
    assert "Submit exactly one proof intent for the next turn" in followup


def test_mcp_stdio_framing_is_newline_delimited_json() -> None:
    newline_in = BytesIO(
        b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
    )
    message = _read_message(newline_in)
    assert message is not None
    assert message["method"] == "initialize"

    out = BytesIO()
    _write_message(out, {"jsonrpc": "2.0", "id": 1, "result": {}})
    assert out.getvalue().endswith(b"\n")
    assert out.getvalue().startswith(b'{"jsonrpc"')

    assert _read_message(BytesIO(b"")) is None


def test_commit_followup_is_one_line_last_action_not_manager_result_section(tmp_path) -> None:
    # A commit turn uses the tight L1-style `Last action` one-liner, NOT the
    # `### Manager result (previous turn)` section with its redundant `you submitted`
    # echo (the agent knows what it sent; the new goal proves an accept).
    from types import SimpleNamespace
    mem = NodeMemory(tmp_path, "Tree-0.0")
    accepted = ManagedTurn(
        ok=True,
        workspace_view=_current_workspace_view(
            proof_status={"status": "open"},
            current_goal={"lines": ["Current goal", "AFTER proc"]},
            last_result={"tactic": "proc.",
                            "result": "EasyCrypt accepted the committed tactic.",
                            "outcome_kind": "accepted",
                            "proof_state_effect": "changed",
                            "proof_state_changed": True,
                            "needs_attention": False},
        ),
        snapshot=SimpleNamespace(goal_hash="Hc", state_version=2),
    )
    fa = render_manager_followup(
        accepted, 3, {"intent": "commit_tactic", "payload": {"tactic": "proc."}}, mem)
    assert "**Last action:** `proc.`" in fa and "accepted" in fa
    assert fa.index("**Last action:** `proc.`") < fa.index("## 🎯 Current Goal")
    assert "### Manager result (previous turn)" not in fa   # the section is gone
    assert "you submitted:" not in fa                       # the redundant echo is gone
    assert "Legal Node Memory Anchor" not in fa             # anchor moved to the system prompt

    rejected = ManagedTurn(
        ok=True,
        workspace_view=_current_workspace_view(
            proof_status={"status": "open"},
            current_goal={"lines": ["Current goal", "x = y"]},
            last_result={"tactic": "apply foo.",
                            "result": "EasyCrypt rejected the committed tactic.",
                            "error_summary": "[error] cannot infer all placeholders",
                            "outcome_kind": "rejected",
                            "proof_state_effect": "unchanged",
                            "proof_state_changed": False,
                            "needs_attention": True},
        ),
        snapshot=SimpleNamespace(goal_hash="Hd", state_version=2),
    )
    fr = render_manager_followup(
        rejected, 4, {"intent": "commit_tactic", "payload": {"tactic": "apply foo."}}, mem)
    assert "**Last action:** `apply foo.`" in fr and "rejected" in fr.lower()
    assert "EasyCrypt error:" in fr and "cannot infer all placeholders" in fr   # reject = why, inline
    assert fr.index("**Last action:** `apply foo.`") < fr.index("## 🎯 Current Goal")
    assert fr.index("EasyCrypt error:") < fr.index("## 🎯 Current Goal")
    assert "### Manager result (previous turn)" not in fr
