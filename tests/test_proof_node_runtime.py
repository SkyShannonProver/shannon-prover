from __future__ import annotations

import hashlib
import json
import socketserver
import sys
import threading
from io import BytesIO
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from tests.helpers.builders import make_manager  # noqa: E402
from workflow.proof_management import (  # noqa: E402
    ManagedTurn,
    NodeHealthEvent,
)
from workflow.proof_management import parse_agent_intent  # noqa: E402
from workflow.proof_node_mcp_server import (  # noqa: E402
    ProofNodeMcpServer,
    _read_message,
    _write_message,
    intent_text_from_tool_arguments,
    submit_intent_to_bridge,
)
from workflow.proof_node_runtime import (  # noqa: E402
    ManagerBridgeServer,
    NodeMemory,
    ProofNodeRuntime,
    render_manager_followup,
)
from workflow.agent_prompt_render import (  # noqa: E402
    render_long_lived_agent_prompt,
)
from workflow.agents.prover_prompt import (  # noqa: E402
    MANAGED_HANDOFF_END,
    MANAGED_HANDOFF_START,
    _build_prover_prompt,
    bind_authoritative_managed_handoff,
)
from workflow.proof_state_compiler.managed_goal_view_manager import (  # noqa: E402
    ManagedGoalViewManager,
)
from workflow.proof_state_compiler.surface_profiles import (  # noqa: E402
    project_current_workspace_view,
)
from core.easycrypt.proof_state_compiler.backend.presentation import (  # noqa: E402
    render_action_surface_payload,
)


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
        host="127.0.0.1",
        port=12345,
        token="tok",
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


def test_l1_goal_projection_prompt_lists_only_l1_goal_projection_surface(tmp_path: Path) -> None:
    prompt = render_long_lived_agent_prompt(
        "ORIGINAL PROMPT",
        host="127.0.0.1",
        port=12345,
        token="tok",
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
            "l4_proof_state_compiler_v2_operation_binding_repair",
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
        host="127.0.0.1",
        port=12345,
        token="tok",
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


def test_mcp_schema_respects_l1_goal_projection_profile(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SHANNON_SURFACE_PROFILE", "l1_goal_projection")
    server = ProofNodeMcpServer(
        host="127.0.0.1",
        port=12345,
        token="tok",
        node_memory_dir=tmp_path,
    )

    response = server.handle_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
    })
    tool = response["result"]["tools"][0]
    intent_schema = tool["inputSchema"]["properties"]["intent"]
    payload_schema = tool["inputSchema"]["properties"]["payload"]

    # L1 exposes the same state-changing action capabilities as L4 so the comparison
    # isolates derived panel content. A bare rewind request still returns its typed
    # control menu; L1 lacks only the content-retrieval channels.
    assert intent_schema["enum"] == [
        "amend_and_replay",
        "commit_tactic",
        "finish",
        "fresh_restart",
        "undo_last_step",
        "undo_to_checkpoint",
    ]
    assert "inspect_context" not in intent_schema["enum"]
    assert "lookup_symbol" not in intent_schema["enum"]
    assert "semantic proof inspection" not in tool["description"]
    assert "{'topic': 'goal_info'}" not in payload_schema["description"]
    assert "{'symbol': '<symbol>'}" not in payload_schema["description"]



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
                "l4_proof_state_compiler_v2_operation_binding_repair",
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
        surface_profile="l4_proof_state_compiler_v2_operation_binding_repair",
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
    from workflow.proof_node_runtime import _prover_system_anchor
    memory = NodeMemory(tmp_path, "Tree_0_0")
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

    # but the durable SYSTEM anchor does — paths + the one-intent-per-turn invariant
    sys_anchor = _prover_system_anchor(memory)
    assert f"LEGAL_NODE_MEMORY_DIR: `{memory.dir}`" in sys_anchor
    assert f"LEGAL_PROOF_SO_FAR: `{memory.latest_proof}`" in sys_anchor
    assert "Compaction recovery" in sys_anchor
    assert "submit_proof_intent" in sys_anchor and "one intent" in sys_anchor.lower()
    proof = memory.latest_proof.read_text(encoding="utf-8")
    assert "Proof so far (2 committed" in proof
    assert "1. proc." in proof
    assert "2. wp." in proof


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


def test_runtime_uses_one_agent_session_for_multiple_manager_turns(tmp_path: Path) -> None:
    runtime = ProofNodeRuntime(
        prompt="Base prompt",
        bootstrap=_current_bootstrap(
            session_tag="unit",
            session_dir=".ec_session_unit",
            snapshot={"state_version": 0, "session_epoch": 0},
            workspace_view=_current_workspace_view(
                current_goal={"lines": ["initial"]},
            ),
        ),
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

    handled: list[str] = []

    def fake_handle(text: str) -> ManagedTurn:
        parsed = parse_agent_intent(text)
        handled.append(parsed.intent.intent if parsed.intent else "malformed")
        return ManagedTurn(
            ok=True,
            workspace_view=_current_workspace_view(
                last_result={"intent": handled[-1], "result": "ok"},
                current_goal={"lines": [f"turn {len(handled)}"]},
                proof_status={"status": "open"},
            ),
            manager_actions=[{
                "label": handled[-1],
                "exit_code": 0,
                "agent_observation": {
                    **(
                        {"kind": "finish_accepted"}
                        if handled[-1] == "finish" else {}
                    ),
                    "result": "ok",
                },
            }],
        )

    runtime.manager.handle_agent_message = fake_handle  # type: ignore[method-assign]
    runtime.prompt = (
        f"{MANAGED_HANDOFF_START}\nprovisional handoff\n{MANAGED_HANDOFF_END}"
    )
    runtime.memory.initial_followup.write_text(
        """Initial manager handoff.

### Ready proof action
- submit: `{"intent":"commit_tactic","payload":{"tactic":"move=> x."}}`
""",
        encoding="utf-8",
    )

    class FakeAgent:
        def __init__(self) -> None:
            self.run_count = 0
            self.close_count = 0
            self.session_id = "fake-session"
            self.responses: list[str] = []
            self.initial_prompt = ""

        def run(self, prompt: str, *, system_prompt: str = "",
                mcp_config_path: Path | None = None,
                mcp_debug_log: Path | None = None):
            self.run_count += 1
            self.initial_prompt = prompt
            assert "submit_proof_intent" in prompt
            assert "submit_intent.sh" not in prompt
            assert '"tactic":"move=> x."' in prompt
            assert "provisional handoff" not in prompt
            assert mcp_config_path is not None
            config = json.loads(mcp_config_path.read_text(encoding="utf-8"))
            assert "proof_node_manager" in config["mcpServers"]
            assert config["mcpServers"]["proof_node_manager"]["type"] == "stdio"
            env = config["mcpServers"]["proof_node_manager"]["env"]
            assert env["SHANNON_MCP_DEBUG_LOG"].endswith("mcp_debug.jsonl")
            assert env["SHANNON_SURFACE_PROFILE"] == "proof_state_compiler"
            for intent in (
                {"intent": "undo_last_step", "payload": {}},
                {"intent": "finish", "payload": {}},
            ):
                response = submit_intent_to_bridge(
                    host=runtime.bridge.host,
                    port=runtime.bridge.port,
                    token=runtime.bridge.token,
                    intent_text=intent_text_from_tool_arguments(intent),
                )
                assert response["exit_code"] == 0
                self.responses.append(response["text"])
            repeated_finish = submit_intent_to_bridge(
                host=runtime.bridge.host,
                port=runtime.bridge.port,
                token=runtime.bridge.token,
                intent_text=intent_text_from_tool_arguments({
                    "intent": "finish",
                    "payload": {},
                }),
            )
            assert repeated_finish["exit_code"] == 0
            assert "finish was already accepted" in repeated_finish["text"]
            self.responses.append(repeated_finish["text"])
            from workflow.proof_node_runtime import ClaudeRunResult

            return ClaudeRunResult(text="done", session_id=self.session_id, returncode=0)

        def close(self, _reason: str) -> None:
            self.close_count += 1

    fake_agent = FakeAgent()
    runtime.agent = fake_agent  # type: ignore[assignment]
    result = runtime.run()

    assert result.text == "done"
    assert result.turns == 2
    assert fake_agent.run_count == 1
    assert fake_agent.close_count == 1
    assert handled == ["undo_last_step", "finish"]
    assert runtime.memory.initial_agent_prompt.read_text(
        encoding="utf-8",
    ) == fake_agent.initial_prompt
    # Read-only context turns are not proof attempts and must not create the
    # historical tactic-attempt stream.
    assert not (runtime.memory.dir / "attempts.jsonl").exists()
    assert not (runtime.memory.dir / "submit_intent.sh").exists()
    assert runtime._mcp_config_path.exists()
    assert "runtime_private" in str(runtime._mcp_config_path)
    assert (runtime.memory.dir / "latest_workspace_view.json").exists()
    assert (runtime.memory.dir / "latest_manager_result.json").exists()
    assert (runtime.memory.dir / "followups" / "turn_001.md").exists()
    assert (runtime.memory.dir / "followups" / "turn_002.md").exists()
    assert (runtime.memory.dir / "manager_results" / "turn_001.json").exists()
    turn_2_view = json.loads(
        (runtime.memory.dir / "workspace_views" / "turn_002.json").read_text(
            encoding="utf-8",
        ),
    )
    # With no full view projected by this fake manager, NodeMemory stores the
    # authoritative lean turn instead of falling back to the bootstrap view.
    assert turn_2_view["last_result"] == {
        "intent": "finish",
        "result": "ok",
    }
    assert turn_2_view["surface_turn"]["turn_outcome"]["intent"] == "finish"
    assert turn_2_view["surface_turn"]["turn_outcome"]["finish_accepted"] is True
    assert turn_2_view["surface_turn"]["base_surface_updates"] is False
    assert fake_agent.responses
    # The per-turn response is itself the complete compact agent-readable
    # surface; it does not point the agent at the raw workspace audit JSON.
    assert "LEGAL_LATEST_WORKSPACE_VIEW" not in fake_agent.responses[-1]
    assert "finish was already accepted" in fake_agent.responses[-1]
    assert "Stop submitting proof intents" in fake_agent.responses[-1]
    assert "Submit exactly ONE proof intent" not in fake_agent.responses[-1]
    for internal_text in (
        "session_cli",
        ".claude",
        "runtime source",
        "bridge client transport",
        "submit script",
        "submit scripts",
        "worktrees",
    ):
        assert internal_text not in fake_agent.responses[-1]


def test_runtime_passes_surface_profile_to_mcp_config(tmp_path: Path) -> None:
    runtime = ProofNodeRuntime(
        prompt="Base prompt",
        bootstrap=_current_bootstrap(
            session_tag="unit",
            session_dir=".ec_session_unit",
            snapshot={"state_version": 0, "session_epoch": 0},
            workspace_view=_profiled_workspace_view(
                "l1_goal_projection",
                current_goal={"lines": ["initial"]},
            ),
        ),
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="unit",
        node_id="Tree-unit",
        run_dir=tmp_path,
        model="claude-test",
        surface_profile="l1_goal_projection",
        project_root=ROOT,
        emit=lambda _event: None,
    )

    runtime._write_mcp_config(host="127.0.0.1", port=12345, token="tok")
    config = json.loads(runtime._mcp_config_path.read_text(encoding="utf-8"))
    env = config["mcpServers"]["proof_node_manager"]["env"]

    assert env["SHANNON_SURFACE_PROFILE"] == "l1_goal_projection"


def test_runtime_marks_node_unhealthy_without_resume_fallback(tmp_path: Path) -> None:
    runtime = ProofNodeRuntime(
        prompt="Base prompt",
        bootstrap=_current_bootstrap(
            session_tag="unit",
            session_dir=".ec_session_unit",
            snapshot={"state_version": 0, "session_epoch": 0},
            workspace_view=_current_workspace_view(
                current_goal={"lines": ["initial"]},
            ),
        ),
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

    def unhealthy(_text: str) -> ManagedTurn:
        return ManagedTurn(
            ok=False,
            workspace_view=_current_workspace_view(
                current_goal={"lines": ["still open"]},
                proof_status={"status": "open"},
            ),
            health_event=NodeHealthEvent(
                node_id="Tree-unit",
                status="agent_protocol_stuck",
                message="agent produced malformed proof intents repeatedly",
            ),
        )

    runtime.manager.handle_agent_message = unhealthy  # type: ignore[method-assign]

    class FakeAgent:
        session_id = "fake-session"

        def run(self, _prompt: str, *, system_prompt: str = "",
                mcp_config_path: Path | None = None,
                mcp_debug_log: Path | None = None):
            assert mcp_config_path is not None
            response = submit_intent_to_bridge(
                host=runtime.bridge.host,
                port=runtime.bridge.port,
                token=runtime.bridge.token,
                intent_text=intent_text_from_tool_arguments({
                    "intent": "undo_last_step",
                    "payload": {},
                }),
            )
            assert response["exit_code"] == 2
            from workflow.proof_node_runtime import ClaudeRunResult

            return ClaudeRunResult(
                text="agent stopped after terminal health",
                session_id=self.session_id,
                returncode=0,
            )

        def close(self, _reason: str) -> None:
            return None

    runtime.agent = FakeAgent()  # type: ignore[assignment]
    result = runtime.run()

    assert result.returncode == 2
    assert "proof node became unhealthy" in result.text
    assert "agent_protocol_stuck" in result.text


def test_bridge_internal_exception_returns_json_and_marks_unhealthy(tmp_path: Path) -> None:
    manager = make_manager(run_dir=tmp_path)
    memory = NodeMemory(tmp_path, "Tree-unit")
    bridge = ManagerBridgeServer(
        manager=manager,
        memory=memory,
        response_renderer=lambda _turn, _idx, _handled, _memory: "unreachable",
        max_turns=2,
    )

    def explode(_text: str) -> ManagedTurn:
        raise RuntimeError("boom")

    manager.handle_agent_message = explode  # type: ignore[method-assign]
    response = bridge._handle_request(json.dumps({
        "token": bridge.token,
        "text": '{"intent":"tactic_forms","payload":{"name":"wp"}}',
    }).encode("utf-8"))

    assert response["exit_code"] == 2
    assert "MANAGER BRIDGE ERROR" in response["text"]
    assert bridge.terminal_health is not None
    assert bridge.terminal_health.status == "manager_bridge_exception"
    audit = (tmp_path / "proof_node_manager_audit.jsonl").read_text(
        encoding="utf-8",
    )
    assert "manager_bridge.exception" in audit
    assert "boom" in audit


def test_bridge_publishes_its_authoritative_completed_turn_index(
    tmp_path: Path,
) -> None:
    manager = make_manager(run_dir=tmp_path)
    memory = NodeMemory(tmp_path, "Tree-unit")
    emitted: list[dict] = []
    bridge = ManagerBridgeServer(
        manager=manager,
        memory=memory,
        response_renderer=(
            lambda _turn, _idx, _handled, _memory, **_kwargs: "ok"
        ),
        max_turns=2,
        emit=emitted.append,
    )
    manager.handle_agent_message = lambda _text: ManagedTurn(  # type: ignore[method-assign]
        ok=True,
        workspace_view=_current_workspace_view(),
    )

    response = bridge._handle_request(json.dumps({
        "token": bridge.token,
        "text": '{"intent":"commit_tactic","payload":{"tactic":"trivial."}}',
    }).encode("utf-8"))

    assert response["exit_code"] == 0
    assert emitted == [{
        "type": "system",
        "kind": "manager_turn.completed",
        "node": manager.node_id,
        "turn_index": 1,
    }]


def test_bridge_finish_latch_consumes_only_authoritative_observation(
    tmp_path: Path,
) -> None:
    manager = make_manager(run_dir=tmp_path)
    memory = NodeMemory(tmp_path, "Tree-unit")
    bridge = ManagerBridgeServer(
        manager=manager,
        memory=memory,
        response_renderer=(
            lambda _turn, _idx, _handled, _memory, **_kwargs: "ok"
        ),
        max_turns=2,
    )
    turns = iter([
        ManagedTurn(
            ok=True,
            workspace_view=_current_workspace_view(),
            manager_actions=[{
                "label": "finish",
                "exit_code": 0,
                "agent_observation": {"result": "finished"},
            }],
        ),
        ManagedTurn(
            ok=True,
            workspace_view=_current_workspace_view(),
            manager_actions=[{
                "label": "finish",
                "exit_code": 1,
                "needs_attention": True,
                "agent_observation": {
                    "kind": "finish_accepted",
                    "result": "Finish accepted.",
                },
            }],
        ),
    ])
    manager.handle_agent_message = lambda _text: next(turns)  # type: ignore[method-assign]
    request = json.dumps({
        "token": bridge.token,
        "text": '{"intent":"finish","payload":{}}',
    }).encode("utf-8")

    first = bridge._handle_request(request)
    assert first["exit_code"] == 0
    assert bridge.finish_accepted is False

    second = bridge._handle_request(request)
    assert second["exit_code"] == 0
    assert bridge.finish_accepted is True


def test_mcp_tool_arguments_preserve_long_tactic_without_shell_escaping() -> None:
    tactic = (
        "seq 1 1 : (c2{1} = c1{2} /\\ "
        "forall (n0 : nonce), n0 \\in n{1} :: BNR.lenc{1})."
    )

    text = intent_text_from_tool_arguments({
        "intent": "commit_tactic",
        "payload": {"tactic": tactic},
    })
    parsed = parse_agent_intent(text)

    assert parsed.ok
    assert parsed.intent is not None
    assert parsed.intent.intent == "commit_tactic"
    assert parsed.intent.payload["tactic"] == tactic


def test_mcp_tool_arguments_forward_malformed_intent_to_manager_repair() -> None:
    text = intent_text_from_tool_arguments({
        "intent": "",
        "payload": {"tactic": "sp; wp; if."},
    })
    parsed = parse_agent_intent(text)

    assert not parsed.ok
    assert parsed.error == "unknown_or_missing_intent"


def test_compiler_markdown_reaches_mcp_content_byte_for_byte(
    tmp_path: Path,
) -> None:
    admission_presentation = render_action_surface_payload({
        "schema_version": 1,
        "resources": [],
        "bindings": [],
        "actions": [{
            "intent": "commit_tactic",
            "payload": {"tactic": "trivial. (* mcp-byte-probe-μ *)"},
            "presentation_kind": "failure_linked_repair",
            "checked_local_effect": {"closed": True},
        }],
        "diagnostics": [],
    })
    manager = make_manager(run_dir=tmp_path)
    memory = NodeMemory(tmp_path, "Tree-mcp-byte-probe")
    bridge = ManagerBridgeServer(
        manager=manager,
        memory=memory,
        response_renderer=render_manager_followup,
        max_turns=1,
    )

    def fixed_turn(_text: str) -> ManagedTurn:
        return ManagedTurn(
            ok=True,
            workspace_view=_current_workspace_view(
                current_goal={"lines": ["Current goal", "x = x"]},
            ),
            compiler_markdown=admission_presentation.text,
        )

    manager.handle_agent_message = fixed_turn  # type: ignore[method-assign]
    bridge.start()
    try:
        mcp = ProofNodeMcpServer(
            host=bridge.host,
            port=bridge.port,
            token=bridge.token,
            node_memory_dir=memory.dir,
        )
        result = mcp._handle_tool_call({
            "name": "submit_proof_intent",
            "arguments": {
                "intent": "commit_tactic",
                "payload": {"tactic": "trivial."},
            },
        })
    finally:
        bridge.close()

    assert result["isError"] is False
    content_text = result["content"][0]["text"]
    assert content_text.count(admission_presentation.text) == 1
    start = content_text.index(admission_presentation.text)
    compiler_substring = content_text[
        start:start + len(admission_presentation.text)
    ]
    assert compiler_substring.encode("utf-8") == (
        admission_presentation.text.encode("utf-8")
    )
    assert hashlib.sha256(compiler_substring.encode("utf-8")).hexdigest() == (
        admission_presentation.sha256
    )


def test_mcp_server_advertises_structured_submit_tool(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SHANNON_ENABLE_PROBE", raising=False)
    monkeypatch.delenv("SHANNON_DISABLE_PROBE", raising=False)
    server = ProofNodeMcpServer(
        host="127.0.0.1",
        port=1,
        token="hidden",
        node_memory_dir=tmp_path / "node_memory" / "Tree_0_0",
    )

    response = server.handle_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    })

    assert response is not None
    tools = response["result"]["tools"]
    assert tools[0]["name"] == "submit_proof_intent"
    assert "proof-level JSON intent" in tools[0]["description"]
    assert "Bash" not in tools[0]["description"]
    assert "latest_workspace_view.json" not in tools[0]["description"]
    assert "latest_followup.md" in tools[0]["description"]
    assert "proof_so_far.md" in tools[0]["description"]
    assert str(tmp_path / "node_memory" / "Tree_0_0") in tools[0]["description"]
    assert "do not use shell directory discovery" in tools[0]["description"]
    assert "intent" in tools[0]["inputSchema"]["required"]
    intent_enum = tools[0]["inputSchema"]["properties"]["intent"]["enum"]
    assert "request_restart" not in intent_enum
    assert "retired_preview_intent" not in intent_enum


def test_mcp_server_cannot_opt_into_retired_probe_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SHANNON_ENABLE_PROBE", "1")
    monkeypatch.delenv("SHANNON_DISABLE_PROBE", raising=False)
    server = ProofNodeMcpServer(
        host="127.0.0.1",
        port=1,
        token="hidden",
        node_memory_dir=tmp_path / "node_memory" / "Tree_0_0",
    )

    response = server.handle_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    })

    intent_enum = response["result"]["tools"][0]["inputSchema"]["properties"]["intent"]["enum"]
    assert "retired_preview_intent" not in intent_enum


def test_mcp_bridge_empty_response_becomes_tool_error(tmp_path: Path) -> None:
    class EmptyHandler(socketserver.StreamRequestHandler):
        def handle(self) -> None:  # noqa: D401
            self.rfile.readline()

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), EmptyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        mcp = ProofNodeMcpServer(
            host="127.0.0.1",
            port=int(server.server_address[1]),
            token="tok",
            node_memory_dir=tmp_path / "node_memory" / "Tree_0_0",
        )
        result = mcp._handle_tool_call({
            "name": "submit_proof_intent",
            "arguments": {
                "intent": "tactic_forms",
                "payload": {"name": "wp"},
            },
        })
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result["isError"] is True
    assert "MANAGER BRIDGE ERROR" in result["content"][0]["text"]
    assert "without a response" in result["content"][0]["text"]


def test_mcp_stdio_framing_supports_newline_and_legacy_header() -> None:
    newline_in = BytesIO(
        b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
    )
    newline_read = _read_message(newline_in)
    assert newline_read is not None
    newline_message, newline_framing = newline_read
    assert newline_message["method"] == "initialize"
    assert newline_framing == "newline"

    newline_out = BytesIO()
    _write_message(
        newline_out,
        {"jsonrpc": "2.0", "id": 1, "result": {}},
        framing=newline_framing,
    )
    assert newline_out.getvalue().endswith(b"\n")
    assert newline_out.getvalue().startswith(b'{"jsonrpc"')

    body = b'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
    header_in = BytesIO(b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
    header_read = _read_message(header_in)
    assert header_read is not None
    header_message, header_framing = header_read
    assert header_message["method"] == "tools/list"
    assert header_framing == "header"

    header_out = BytesIO()
    _write_message(
        header_out,
        {"jsonrpc": "2.0", "id": 2, "result": {}},
        framing=header_framing,
    )
    assert header_out.getvalue().startswith(b"Content-Length: ")


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
