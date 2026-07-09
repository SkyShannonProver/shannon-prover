from __future__ import annotations

import json
import socketserver
import sys
import threading
from io import BytesIO
from pathlib import Path


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
    _render_manager_followup,
)
from workflow.agent_prompt_render import (  # noqa: E402
    _turn_interpretation,
    _workspace_view_preview,
    render_long_lived_agent_prompt,
)


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
    assert "current authoritative `ProverWorkspaceView`" in prompt
    assert "Use MCP tools to interact with the manager" in prompt
    assert "structured MCP tool `submit_proof_intent`" in prompt
    assert "`LEGAL_PROOF_SO_FAR`" in prompt        # committed proof is read-on-demand now
    assert "include a `payload` object" in prompt
    assert "no shell escaping or scratch files" in prompt
    # §2 Your MCP tools — one line per granted intent
    assert "## Your MCP tools" in prompt
    assert "The current `intent` must be one of:" in prompt
    for intent in (
        "`commit_tactic`", "`tactic_forms`", "`lookup_symbol`",
        "`undo_last_step`", "`undo_to_checkpoint`", "`fresh_restart`",
        "`finish`",
    ):
        assert intent in prompt
    assert "`goal_info`" not in prompt
    assert "`inspect_context`" not in prompt
    assert "`probe_tactic`" not in prompt
    assert "`request_restart`" not in prompt
    # §3 how to read what the manager returns
    assert "## How to read what the manager returns" in prompt
    assert "STATIC-ANALYSIS FACT" in prompt
    assert "FORK, not a wall" in prompt
    assert "candidate_moves" in prompt  # signal-weighing block (full surface)
    # §4 how to play well + final-admit gate
    assert "## How to play well" in prompt
    assert "be brave: COMMIT and UNDO freely" in prompt
    assert "A final proof must contain no committed `admit.` tactics" in prompt
    assert "blocks `qed.` / `finish`" in prompt
    assert "tracked SCAFFOLD" not in prompt
    assert "scaffold debt" not in prompt
    # §5 runtime details
    assert "## Runtime details" in prompt
    assert "LEGAL_NODE_MEMORY_DIR" in prompt
    assert "latest_followup.md" in prompt
    assert "proof_so_far.md" in prompt
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
    assert "ORIGINAL PROMPT" in prompt


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
    # L1 now has the full ACTION capability set (so the L1<->L4 comparison isolates the
    # panel CONTENT, not capabilities) — including the index-addressed rewinds.
    assert "`amend_and_replay`" in prompt
    assert "`undo_to_checkpoint`" in prompt
    # ...but it must NOT advertise the content-retrieval channels (the panel's value).
    assert "`probe_tactic`" not in prompt
    assert "`inspect_context`" not in prompt
    assert "`lookup_symbol`" not in prompt
    assert "semantic proof inspection" not in prompt
    assert (
        "`current_goal`, `proof_status`, `last_result`, and "
        "`latest_observation`"
    ) in prompt
    for hidden_panel in (
        "`program_frontier`",
        "`application_context`",
        "`facts_and_diagnostics`",
        "`candidate_moves`",
        "`inspect_lookup_handles`",
        "candidate_moves.",
    ):
        assert hidden_panel not in prompt


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

    # L1 now exposes the SAME action capabilities as L4 (amend_and_replay +
    # undo_to_checkpoint both reference a step by index off the proof_so_far panel L1
    # renders, so L1 needs no checkpoint menu) — so the L1<->L4 comparison isolates
    # the DERIVED panel content. L1 still lacks the content-retrieval channels.
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
    assert "{'symbol': 'LEMMA'}" not in payload_schema["description"]


def test_workspace_view_preview_compacts_navigation() -> None:
    preview = _workspace_view_preview({
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["goal"]},
        "candidate_moves": {
            "structural_transitions": [{
                "id": "post_wp_surgery",
                "kind": "structural_transition",
                "status": "candidate_reversible_probe",
                "tactic": "wp.",
                "phase": "post-wp surgery",
                "valid_for": "current_view_only",
                "why_here": "large pRHL postcondition",
                "decision": (
                    "Probe this tactic if you want to test entry into the "
                    "post-wp surgery phase."
                ),
                "recommended_next": {
                    "label": "Probe this transition",
                    "submit": {
                        "intent": "probe_tactic",
                        "payload": {"tactic": "wp."},
                    },
                },
                "after_commit": (
                    "The next authoritative view will expose the real "
                    "post-wp surgery workbench."
                ),
            }],
            "navigation": [{
                "id": "probability_phoare_loop",
                "episode": "top_level_probability",
                "route": "case_split_then_byphoare_loop",
                "confidence": "high",
                "confidence_reason": "x" * 500,
                "valid_for": "current_view_only",
                "why_now": "y" * 500,
                "fast_track_probe": {
                    "tactic": "byphoare (_: <pre> ==> <post>) => //; " + "z" * 500,
                    "preconditions": ["probe first"],
                    "expected_next_shape": "loop obligations",
                },
                "anti_routes": [{"route": "byequiv_first", "reason": "wrong shape"}],
                "repair_if_fails": [{"failure": "syntax", "next": "inspect tactic_forms"}],
                "lemma_pack": [],
            }],
            "probe_alternatives": [{
                "tactic": "wp.",
                "probe_result": "accepted",
                "status": "verified_on_current_state",
                "how_to_use": "commit this exact tactic",
                "structural_transition": {
                    "id": "post_wp_surgery",
                    "kind": "structural_transition",
                    "status": "accepted_checkpoint",
                    "tactic": "wp.",
                    "phase": "post-wp surgery",
                    "recommended_next": {
                        "label": "Enter this transition",
                        "submit": {
                            "intent": "commit_tactic",
                            "payload": {"tactic": "wp."},
                        },
                    },
                    "after_commit": (
                        "The next authoritative view will expose the real "
                        "post-wp surgery workbench."
                    ),
                },
                "goal_after_probe_summary": {
                    "remaining_goals": 2,
                    "first_lines": ["Current goal", "x = y"],
                },
            }],
            "moves": [{"title": "probe", "category": "probe", "tactic": "wp."}],
            "limitations": [{"kind": "template"}],
        },
    })

    nav = preview["candidate_moves"]["navigation"][0]

    assert nav["id"] == "probability_phoare_loop"
    assert nav["valid_for"] == "current_view_only"
    assert "truncated" in nav["confidence_reason"]
    assert "truncated" in nav["fast_track_probe"]["tactic"]
    assert (
        preview["candidate_moves"]["structural_transitions"][0]["id"]
        == "post_wp_surgery"
    )
    transition = preview["candidate_moves"]["probe_alternatives"][0]["structural_transition"]
    assert transition["id"] == "post_wp_surgery"
    assert transition["phase"] == "post-wp surgery"
    assert "real post-wp surgery workbench" in transition["after_commit"]
    assert transition["recommended_next"]["submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "wp."},
    }
    assert preview["candidate_moves"]["moves"][0]["tactic"] == "wp."


def test_workspace_view_preview_shows_real_goals_whole() -> None:
    # the goal is THE thing the agent acts on — a normal (even large) proof goal is
    # shown WHOLE inline now (cap is 30k). A 5k-char goal must NOT truncate.
    preview = _workspace_view_preview({
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["Current goal", "x" * 5000, "tail"],
                         "text_fully_shown": True, "truncated": False},
    })
    goal = preview["current_goal"]
    assert not goal.get("truncated")
    assert "x" * 5000 in goal["lines_preview"]


def test_workspace_view_preview_oversize_goal_nudges_undo_not_a_file() -> None:
    # only a pathological goal (>30k, almost always a destructive `inline *`
    # explosion) truncates — and it must NOT point the agent at a file (that read
    # tripped the bridge-escape watchdog); it nudges undo instead.
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown
    preview = _workspace_view_preview({
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["x" * 100 for _ in range(400)],  # ~40k chars
                         "text_fully_shown": True, "truncated": False},
    })
    goal = preview["current_goal"]
    assert "lines" not in goal
    assert goal["truncated"] is True
    assert goal["truncation_scope"] == "inline_preview"
    assert goal["oversize_consider_undo"] is True
    assert "read_full_current_goal_lines_from" not in goal   # no file pointer
    md = render_surface_turn_markdown(
        compose_surface_turn(
            preview,
            "l1_goal_projection",
            goal_only=True,
        ),
        goal_only=True,
    )
    assert "undo_last_step" in md and "latest_workspace_view.json" not in md


def test_surface_turn_markdown_tiers_and_orders_by_goal_size() -> None:
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown
    base = {
        "proof_status": {"remaining_goals": 1, "view_focus": "seq_cut",
                         "current_layer": "procedure_body"},
        "seq_cut_surface": {
            "seq_scope": "left 0..2 / right 0..2",
            "obligation_shape": "aligned branch residual",
        },
        # the reference is an ACTIONABLE retrieval menu, not a dump of panel JSON
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "tactic_forms", "payload": {"name": "rewrite"},
             "use_when": "need the valid form for rewrite"}]},
    }
    # small goal -> the goal leads (the normal contract), focus follows
    small = {**base, "current_goal": {"lines_preview": "x = y", "line_count": 3}}
    md = render_surface_turn_markdown(
        compose_surface_turn(small, "l4_checked_action_surface")
    )
    assert "## 🎯 Current Goal" in md and "## Surgery" in md
    assert md.index("Current Goal") < md.index("Surgery")
    assert "**Seq scope:**" in md and "aligned branch residual" in md
    # reference gives the EXACT intent to submit, not a truncated panel dump
    assert "submit `{" in md and '"intent": "tactic_forms"' in md
    # large goal -> the goal still leads; the panel is explanatory, not the proof-state anchor.
    large = {**base, "current_goal": {"lines_preview": "x = y", "truncated": True}}
    md2 = render_surface_turn_markdown(
        compose_surface_turn(large, "l4_checked_action_surface")
    )
    assert md2.index("Current Goal") < md2.index("Surgery")
    # recover focus is error-handling: the outcome leads, then the goal, then panel.
    recover = {
        "proof_status": {"remaining_goals": 1, "view_focus": "procedure_body",
                         "current_layer": "recovery"},
        "current_goal": {"lines_preview": "x = y", "line_count": 3},
        "last_result": {
            "tactic": "rewrite.",
            "result": "EasyCrypt rejected the committed tactic.",
            "error_summary": "[error] no rewrite rule applies",
        },
    }
    md3 = render_surface_turn_markdown(
        compose_surface_turn(
            recover,
            "l4_checked_action_surface",
            handled_intent={"intent": "commit_tactic", "payload": {"tactic": "rewrite."}},
            ok=False,
        )
    )
    assert md3.index("EasyCrypt rejected") < md3.index("Current Goal")
    assert md3.index("Current Goal") < md3.index("Recover")


def test_l1_surface_turn_surfaces_raw_ec_error_on_rejection() -> None:
    # L1 has no diagnostics panel and cannot inspect:diagnose — its one-line
    # last-action feedback must carry the raw EC error so a rejection says *why*
    # (the `result` text already tells the agent to "use the error summary").
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown
    rejected = {
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "last_result": {
            "intent": "commit_tactic",
            "tactic": "call (equ_cc _ _ _).",
            "result": ("EasyCrypt rejected the committed tactic. Use the error "
                       "summary and current goal to revise the proof step."),
            "error_summary": "[error] cannot infer all placeholders",
            "proof_state": "The committed EasyCrypt proof state was not changed.",
        },
    }
    md = render_surface_turn_markdown(
        compose_surface_turn(
            rejected,
            "l1_goal_projection",
            handled_intent={
                "intent": "commit_tactic",
                "payload": {"tactic": "call (equ_cc _ _ _)."},
            },
            ok=False,
            goal_only=True,
        ),
        goal_only=True,
    )
    assert "cannot infer all placeholders" in md   # the raw EC reason is shown
    assert "EasyCrypt error" in md
    assert md.index("EasyCrypt error") < md.index("Current Goal")
    # an accepted action carries no spurious error line
    accepted = {
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "last_result": {
            "intent": "commit_tactic",
            "tactic": "proc.",
            "result": "EasyCrypt accepted the committed tactic.",
        },
    }
    md_ok = render_surface_turn_markdown(
        compose_surface_turn(
            accepted,
            "l1_goal_projection",
            handled_intent={"intent": "commit_tactic", "payload": {"tactic": "proc."}},
            goal_only=True,
        ),
        goal_only=True,
    )
    assert "EasyCrypt error" not in md_ok


def test_probe_outcome_accept_leads_with_goal_after_not_unchanged_goal() -> None:
    # A probe is a dry run: on ACCEPT the headline must be the goal-AFTER (what
    # committing produces), NOT the unchanged committed goal — the agent probed
    # precisely to see the change. (MEE-CBC L4: the old followup re-showed the
    # unchanged goal and only POINTED at goal_after_probe in the JSON.)
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown
    view = {
        "last_result": {
            "intent": "probe_tactic",
            "tactic": "proc.",
            "result": "EasyCrypt accepted this read-only probe.",
            "probe_preview": {
                "goal_after_remaining": 1,
                "goal_after_probe": {"lines": ["Current goal", "p <- None", "s <- head witness c"]},
            },
        },
        "current_goal": {"lines": ["the OLD lemma statement"]},
    }
    md = render_surface_turn_markdown(
        compose_surface_turn(
            view,
            "l4_checked_action_surface",
            handled_intent={"intent": "probe_tactic", "payload": {"tactic": "proc."}},
        )
    )
    assert "Probe preview" in md and "accepted" in md
    assert "p <- None" in md and "s <- head witness c" in md     # the goal-AFTER is shown
    assert "the OLD lemma statement" not in md                   # not the unchanged goal
    assert "EasyCrypt error" not in md                           # accept != error


def test_probe_outcome_reject_leads_with_ec_error_keeps_goal_as_context() -> None:
    # On REJECT the headline is the EC error (the `why`); the committed goal stays
    # as collapsed context. Mutually exclusive with the accept preview.
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown
    view = {
        "last_result": {
            "intent": "probe_tactic",
            "tactic": "inline PRPc.PseudoRP.fi.",
            "result": "EasyCrypt rejected this probe or could not use it.",
            "error_summary": "[error] cannot inline PRPc.PseudoRP.fi: abstract procedure",
        },
        "current_goal": {"lines": ["Current goal"] + [f"line {i}" for i in range(20)]},
    }
    md = render_surface_turn_markdown(
        compose_surface_turn(
            view,
            "l4_checked_action_surface",
            handled_intent={
                "intent": "probe_tactic",
                "payload": {"tactic": "inline PRPc.PseudoRP.fi."},
            },
        )
    )
    assert "Probe rejected" in md
    assert "EasyCrypt error:" in md and "abstract procedure" in md
    assert "committing this would produce" not in md             # reject != preview
    assert "committed state unchanged" in md.lower()


def test_probe_preview_surface_replaces_goal_block() -> None:
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown
    # when a probe preview exists, SurfaceTurnModel leads with it (not the goal)
    view = {
        "last_result": {
            "intent": "probe_tactic",
            "tactic": "proc.",
            "result": "EasyCrypt accepted this read-only probe.",
            "probe_preview": {"goal_after_probe": {"lines": ["Current goal", "after"]}},
        },
        "current_goal": {"lines_preview": "x = y", "line_count": 1},
    }
    md = render_surface_turn_markdown(
        compose_surface_turn(
            view,
            "l4_checked_action_surface",
            handled_intent={"intent": "probe_tactic", "payload": {"tactic": "proc."}},
        )
    )
    assert md.startswith("## Probe preview -- `proc.`")
    assert "## 🎯 Current Goal" not in md                        # goal block replaced


def test_surface_panel_markdown_blank_line_between_bullets_and_next_label() -> None:
    # regression (live audit, turn_009): a `**Label:**` immediately under a `- bullet`
    # with no blank line is swallowed as a markdown lazy-continuation of the bullet,
    # rendering "…bullet **Label:**" jammed. Every label must be its own block.
    from workflow.surface_turn_model import render_surface_turn_markdown
    md = render_surface_turn_markdown({
        "presentation_kind": "proof_state",
        "proof_surface": {
            "goal": {"text": "Current goal"},
            "primary_panel": {
                "title": "Call Frontier",
                "facts": [
                    {"label": "Situation", "value": "named call not callable yet"},
                    {"label": "Candidate", "value": ["`UFCMA_genCC`"]},
                    {
                        "label": "Frontier",
                        "value": ["setup before the frontier", "frontier: both sides at `b <@ ...`"],
                    },
                    {"label": "Options", "value": ["`call (_: <Inv>)`", "`inline*` / `proc`"]},
                    {"label": "Yours", "value": "the invariant predicate"},
                ],
            },
        },
    })
    lines = md.splitlines()
    # no `**Label:**` line may directly follow a `- bullet` (must have a blank line)
    for i in range(1, len(lines)):
        if lines[i].startswith("**") and lines[i].rstrip().endswith(":**") or (
            lines[i].startswith("**") and ":**" in lines[i]):
            assert not lines[i - 1].startswith("- "), (
                f"label {lines[i]!r} jammed onto bullet {lines[i-1]!r}")
    # specifically: Frontier / Options / Yours each separated from the prior bullets
    assert "\n\n**Frontier:**" in md and "\n\n**Options:**" in md and "\n\n**Yours:**" in md


def test_surface_turn_status_does_not_cram_truncated_last_tactic() -> None:
    # regression: the status line used to append `last \`tac…\` — result…` (double
    # truncation), redundant with the focus + manager-result section. Now: just
    # remaining + phase.
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown
    md = render_surface_turn_markdown(compose_surface_turn({
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "proof_status": {"remaining_goals": 7, "view_focus": "failure_diagnostic",
                         "current_layer": "procedure_body"},
        "last_result": {"tactic": "while (={p2, c2, i, n, a, p1, n0, p, p0, nap, c, UFCMA...}).",
                        "result": "EasyCrypt rejected the committed tactic. Use the error..."},
    }, "l4_checked_action_surface"))
    status = md.split("## Status", 1)[1].split("**Last action:**", 1)[0]
    assert "remaining **7**" in status and "failure_recovery" in status
    assert "failure_diagnostic" not in status
    assert "last `" not in status and "while" not in status


def test_workspace_view_preview_preserves_accepted_probe_decision() -> None:
    preview = _workspace_view_preview({
        "kind": "prover_workspace_view",
        "last_result": {
            "kind": "accepted_structural_transition",
            "message": "This structural transition probe was accepted.",
            "question": "Do you want to enter the post-wp surgery workbench?",
            "accepted_tactic": "wp.",
            "structural_transition": {
                "id": "post_wp_surgery",
                "phase": "post-wp surgery",
                "recommended_next": {
                    "label": "Enter this transition",
                    "submit": {
                        "intent": "commit_tactic",
                        "payload": {"tactic": "wp."},
                    },
                },
            },
            "recommended_next": {
                "label": "Enter this transition",
                "submit": {
                    "intent": "commit_tactic",
                    "payload": {"tactic": "wp."},
                },
            },
            "guidance": (
                "If yes, commit this exact tactic and read the real "
                "post-commit workbench. If no, choose another probe or inspect "
                "the current state. Do not solve the speculative preview in "
                "your mental model."
            ),
        },
        "current_goal": {"lines": ["goal"]},
    })

    assert preview["last_result"]["kind"] == "accepted_structural_transition"
    assert preview["last_result"]["question"].startswith("Do you want to enter")
    assert preview["last_result"]["structural_transition"]["id"] == "post_wp_surgery"
    assert "mental model" in preview["last_result"]["guidance"]


def test_turn_interpretation_spotlights_structural_probe_decision() -> None:
    note = _turn_interpretation(
        {"intent": "probe_tactic", "payload": {"tactic": "wp."}},
        [{
            "agent_observation": {
                "kind": "accepted_structural_transition",
                "structural_transition": {
                    "id": "post_wp_surgery",
                    "recommended_next": {
                        "submit": {
                            "intent": "commit_tactic",
                            "payload": {"tactic": "wp."},
                        },
                    },
                },
            },
        }],
    )

    assert "Accepted structural transition probe" in note
    assert "last_result.structural_transition" in note
    assert "mental model" in note


def test_workspace_view_preview_preserves_menu_submit_payloads() -> None:
    preview = _workspace_view_preview({
        "kind": "prover_workspace_view",
        "last_result": {
            "kind": "fresh_restart_confirmation",
            "message": "Fresh restart will erase all your committed tactics in this node.",
            "options": [{
                "label": "Undo last committed tactic",
                "effect_if_selected": "This will undo the last committed tactic in this node.",
                "submit": {"intent": "undo_last_step", "payload": {}},
            }],
        },
        "current_goal": {"lines": ["goal"]},
    })

    assert preview["last_result"]["options"][0]["submit"] == {
        "intent": "undo_last_step",
        "payload": {},
    }


def test_node_memory_writes_curated_files(tmp_path: Path) -> None:
    memory = NodeMemory(tmp_path, "Tree-0.0")
    turn = ManagedTurn(
        ok=False,
        workspace_view={"current_goal": {"lines": ["x = y"]}},
        repair_prompt="repair please",
        manager_actions=[{
            "label": "probe_tactic",
            "exit_code": 1,
            "agent_observation": {"error_summary": "bad tactic"},
        }],
    )

    memory.record_turn(
        turn_index=1,
        raw_text='{"intent":"probe_tactic","payload":{"tactic":"bad."}}',
        handled_intent={"intent": "probe_tactic", "payload": {"tactic": "bad."}},
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
    assert failure["intent"]["intent"] == "probe_tactic"
    assert failure["manager_actions"][0]["error_summary"] == "bad tactic"


def test_node_memory_persists_bootstrap_current_view(tmp_path: Path) -> None:
    memory = NodeMemory(tmp_path, "Tree-0.0.0")

    memory.record_bootstrap({
        "session_tag": "unit",
        "session_dir": ".ec_session_unit",
        "replay_prefix_count": 3,
        "snapshot": {"state_version": 3},
        "workspace_view": {
            "kind": "prover_workspace_view",
            "proof_status": {"status": "open"},
            "current_goal": {"lines": ["goal at handoff"]},
        },
    })

    latest_view = json.loads(memory.latest_view.read_text(encoding="utf-8"))
    latest_result = json.loads(memory.latest_result.read_text(encoding="utf-8"))
    turn_zero_view = json.loads(
        (memory.workspace_views_dir / "turn_000.json").read_text(encoding="utf-8")
    )

    assert latest_view["current_goal"]["lines"] == ["goal at handoff"]
    assert turn_zero_view == latest_view
    assert latest_result["kind"] == "bootstrap"
    assert latest_result["replay_prefix_count"] == 3
    latest_followup = memory.latest_followup.read_text(encoding="utf-8")
    assert "LEGAL_LATEST_FOLLOWUP" in latest_followup
    assert "latest_workspace_view.json" not in latest_followup
    assert "LEGAL_LATEST_WORKSPACE_VIEW" not in latest_followup


def test_l1_audit_latest_view_leads_with_off_surface_notice(
    tmp_path: Path,
) -> None:
    """The L1 latest workspace audit JSON leads with a gentle off-surface
    reminder, while the per-turn audit archive stays full and un-annotated.
    """
    memory = NodeMemory(tmp_path, "Tree-0.0", surface_profile="l1_goal_projection")
    full_view = {
        "kind": "prover_workspace_view",
        "proof_status": {"status": "open"},
        "current_goal": {"lines": ["goal at handoff"]},
        "candidate_moves": [{"tactic": "auto."}, {"tactic": "smt."}],
        "inspect_lookup_handles": [{"topic": "tactic_forms", "name": "wp"}],
        "program_frontier": {"position": "head"},
    }
    memory.record_bootstrap({
        "session_tag": "unit",
        "session_dir": ".ec_session_unit",
        "snapshot": {"state_version": 0},
        "workspace_view": full_view,
    })

    latest_view = json.loads(memory.latest_view.read_text(encoding="utf-8"))
    archive = json.loads(
        (memory.workspace_views_dir / "turn_000.json").read_text(encoding="utf-8")
    )

    # The durable latest-view audit file leads with the reminder, but content is
    # NOT redacted (resume/replay read this same file) — it is a gentle nudge,
    # not a projection.
    assert "_l1_surface_notice" in latest_view
    assert list(latest_view)[0] == "_l1_surface_notice"
    assert "NOT part of your surface" in latest_view["_l1_surface_notice"]
    assert latest_view["current_goal"]["lines"] == ["goal at handoff"]

    # The audit archive stays full and un-annotated.
    assert "_l1_surface_notice" not in archive
    assert archive["candidate_moves"]

    # The L1 followup no longer advertises the full view as a place to read panels.
    followup = memory.latest_followup.read_text(encoding="utf-8")
    assert "every collapsed panel" not in followup


def test_non_l1_agent_facing_latest_view_is_unannotated(tmp_path: Path) -> None:
    """For non-L1 profiles the agent-facing file is the full view, no notice added."""
    memory = NodeMemory(tmp_path, "Tree-0.0", surface_profile="l4_preview_diagnostic")
    memory.record_bootstrap({
        "session_tag": "unit",
        "session_dir": ".ec_session_unit",
        "snapshot": {"state_version": 0},
        "workspace_view": {
            "kind": "prover_workspace_view",
            "current_goal": {"lines": ["g"]},
            "candidate_moves": [{"tactic": "auto."}],
        },
    })
    latest_view = json.loads(memory.latest_view.read_text(encoding="utf-8"))
    assert "_l1_surface_notice" not in latest_view
    assert latest_view["candidate_moves"]


def test_legal_node_memory_anchor_lives_in_system_prompt_not_per_turn(tmp_path: Path) -> None:
    """The LEGAL_* anchor moved to the DURABLE system prompt (Claude preserves the
    system prompt across compaction), so it is NO LONGER re-sent in every per-turn
    followup. The per-turn prompt stays lean; the anchor survives via
    _prover_system_anchor (wired through ClaudeAgentSession.run --append-system-prompt)."""
    from workflow.proof_node_runtime import _prover_system_anchor
    memory = NodeMemory(tmp_path, "Tree_0_0")
    turn = ManagedTurn(
        ok=True,
        workspace_view={
            "kind": "prover_workspace_view",
            "proof_status": {"status": "open"},
            "current_goal": {"lines": ["x = y"]},
        },
        manager_actions=[],
    )
    followup = _render_manager_followup(
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


def test_playground_memory_none_retrieval_followup_renders_surface_model_answer() -> None:
    turn = ManagedTurn(
        ok=True,
        workspace_view={
            "kind": "prover_workspace_view",
            "proof_status": {"status": "open", "current_layer": "procedure_body"},
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "last_result": {
                "intent": "tactic_forms",
                "payload": {"name": "rewrite"},
                "result": "Read-only context returned.",
                "proof_state": "unchanged",
                "content": {
                    "title": "Tactic Form Reference",
                    "preview": (
                        "=== `rewrite` tactic -- argument forms ===\n"
                        "Form 1: rewrite LEMMA."
                    ),
                },
            },
        },
        manager_actions=[],
    )
    followup = _render_manager_followup(
        turn,
        2,
        {"intent": "tactic_forms", "payload": {"name": "rewrite"}},
        memory=None,
        surface_profile="l4_checked_action_surface",
    )

    assert "Requested: `tactic_forms`" in followup
    assert "rewrite LEMMA" in followup
    assert followup.index("Current Goal") < followup.index("Requested: `tactic_forms`")
    assert "Manager result (previous turn)" not in followup


def test_runtime_uses_one_agent_session_for_multiple_manager_turns(tmp_path: Path) -> None:
    runtime = ProofNodeRuntime(
        prompt="Base prompt",
        bootstrap={
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "snapshot": {"state_version": 0, "session_epoch": 0},
            "workspace_view": {"current_goal": {"lines": ["initial"]}},
        },
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
            workspace_view={
                "kind": "prover_workspace_view",
                "last_result": {"intent": handled[-1], "result": "ok"},
                "current_goal": {"lines": [f"turn {len(handled)}"]},
                "proof_status": {"status": "open"},
            },
            manager_actions=[{
                "label": handled[-1],
                "exit_code": 0,
                "agent_observation": {"result": "ok"},
            }],
        )

    runtime.manager.handle_agent_message = fake_handle  # type: ignore[method-assign]

    class FakeAgent:
        def __init__(self) -> None:
            self.run_count = 0
            self.close_count = 0
            self.session_id = "fake-session"
            self.responses: list[str] = []

        def run(self, prompt: str, *, system_prompt: str = "",
                mcp_config_path: Path | None = None,
                mcp_debug_log: Path | None = None):
            self.run_count += 1
            assert "submit_proof_intent" in prompt
            assert "submit_intent.sh" not in prompt
            assert mcp_config_path is not None
            config = json.loads(mcp_config_path.read_text(encoding="utf-8"))
            assert "proof_node_manager" in config["mcpServers"]
            assert config["mcpServers"]["proof_node_manager"]["type"] == "stdio"
            env = config["mcpServers"]["proof_node_manager"]["env"]
            assert env["SHANNON_MCP_DEBUG_LOG"].endswith("mcp_debug.jsonl")
            assert env["SHANNON_SURFACE_PROFILE"] == ""
            for intent in (
                {"intent": "tactic_forms", "payload": {"name": "wp"}},
                {"intent": "probe_tactic", "payload": {"tactic": "smt()."}},
            ):
                response = submit_intent_to_bridge(
                    host=runtime.bridge.host,
                    port=runtime.bridge.port,
                    token=runtime.bridge.token,
                    intent_text=intent_text_from_tool_arguments(intent),
                )
                assert response["exit_code"] == 0
                self.responses.append(response["text"])
            from workflow.proof_node_runtime import ClaudeRunResult

            return ClaudeRunResult(text="done", session_id=self.session_id, returncode=0)

        def close(self, _reason: str) -> None:
            self.close_count += 1

    fake_agent = FakeAgent()
    runtime.agent = fake_agent  # type: ignore[assignment]
    result = runtime.run()

    assert result.text == "done"
    assert fake_agent.run_count == 1
    assert fake_agent.close_count == 1
    assert handled == ["tactic_forms", "probe_tactic"]
    assert (runtime.memory.dir / "attempts.jsonl").exists()
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
    assert turn_2_view["last_result"] == {"intent": "probe_tactic", "result": "ok"}
    assert fake_agent.responses
    # Per-turn followup points back to the compact agent-readable surface, not
    # the raw workspace audit JSON.
    assert "LEGAL_LATEST_FOLLOWUP" in fake_agent.responses[-1]
    assert "LEGAL_LATEST_WORKSPACE_VIEW" not in fake_agent.responses[-1]
    assert "submit_proof_intent" in fake_agent.responses[-1]
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
        bootstrap={
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "snapshot": {"state_version": 0, "session_epoch": 0},
            "workspace_view": {"current_goal": {"lines": ["initial"]}},
        },
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


def test_manager_followup_marks_inspect_results_as_readonly_speculative(tmp_path: Path) -> None:
    memory = NodeMemory(tmp_path, "Tree-0.0")
    turn = ManagedTurn(
        ok=True,
        workspace_view={
            "kind": "prover_workspace_view",
            "proof_status": {"status": "open"},
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "last_result": {
                "intent": "call_subgoals",
                "payload": {},
                "result": "Read-only context returned.",
                "proof_state": "unchanged",
                "content": {
                    "title": "Call Obligation Preview",
                    "result": (
                        "The previewed call did not typecheck against the "
                        "daemon; no tactic was committed."
                    ),
                    "preview": "=== Call subgoal preview === ...",
                },
            },
        },
        manager_actions=[{
            "label": "inspect_call_subgoals",
            "exit_code": 0,
            "duration_ms": 12,
            "mutates_proof_state": False,
            "agent_observation": {
                "content": {
                    "title": "Call Obligation Preview",
                    "result": (
                        "The previewed call did not typecheck against the "
                        "daemon; no tactic was committed."
                    ),
                    "preview": "=== Call subgoal preview === ...",
                },
            },
        }],
    )

    followup = _render_manager_followup(
        turn,
        3,
        {"intent": "call_subgoals", "payload": {}},
        memory,
    )
    result = json.loads(memory.latest_result.read_text(encoding="utf-8"))

    assert "Read-only context" in result["manager_note"]
    assert "route-selection information" in result["manager_note"]
    assert result["manager_actions"][0]["action"] == "call-obligation preview"
    assert result["manager_actions"][0]["outcome"].startswith("The previewed call")
    assert result["manager_actions"][0]["content"] == {
        "title": "Call Obligation Preview",
        "preview": "=== Call subgoal preview === ...",
    }
    assert "mutates_proof_state" not in result["manager_actions"][0]
    assert "proof_state_changed" not in result["manager_actions"][0]
    assert "proof_state" not in result["manager_actions"][0]
    assert "observation" not in result["manager_actions"][0]
    assert "preview_scope" not in followup
    assert "preview_status" not in followup
    # (composition fix 2026-06-05) the requested inspect answer LEADS, surfaced as
    # readable SurfaceModel markdown — NOT buried in a raw result_payload JSON dump.
    assert "## Requested" in followup
    assert "Call subgoal preview" in followup            # the content.preview itself
    # (ergonomics fix) the 4-line "Manager result" section is replaced by a
    # SurfaceModel context-result panel, and the per-turn Legal Node Memory
    # Anchor is dropped from retrieval turns (recovery is owned by the system prompt).
    assert "Legal Node Memory Anchor" not in followup    # dropped on retrieval turns
    assert "```json" not in followup                     # no raw result_payload dump
    # the requested answer sits after the unchanged proof surface/actions.
    assert followup.index("Current Goal") < followup.index("Call subgoal preview")
    assert (memory.dir / "followups" / "turn_003.md").read_text(
        encoding="utf-8",
    ) == followup
    assert json.loads(
        (memory.dir / "manager_results" / "turn_003.json").read_text(
            encoding="utf-8",
        ),
    ) == result
    turn_view = json.loads(
        (memory.dir / "workspace_views" / "turn_003.json").read_text(
            encoding="utf-8",
        ),
    )
    assert turn_view["current_goal"]["lines"] == ["Current goal", "x = y"]


def test_runtime_marks_node_unhealthy_without_resume_fallback(tmp_path: Path) -> None:
    runtime = ProofNodeRuntime(
        prompt="Base prompt",
        bootstrap={
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "snapshot": {"state_version": 0, "session_epoch": 0},
            "workspace_view": {"current_goal": {"lines": ["initial"]}},
        },
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
            workspace_view={
                "kind": "prover_workspace_view",
                "current_goal": {"lines": ["still open"]},
                "proof_status": {"status": "open"},
            },
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
                    "intent": "tactic_forms",
                    "payload": {"name": "wp"},
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


def test_mcp_tool_arguments_preserve_long_tactic_without_shell_escaping() -> None:
    tactic = (
        "seq 1 1 : (c2{1} = c1{2} /\\ "
        "forall (n0 : nonce), n0 \\in n{1} :: BNR.lenc{1})."
    )

    text = intent_text_from_tool_arguments({
        "intent": "probe_tactic",
        "payload": {"tactic": tactic},
    })
    parsed = parse_agent_intent(text)

    assert parsed.ok
    assert parsed.intent is not None
    assert parsed.intent.intent == "probe_tactic"
    assert parsed.intent.payload["tactic"] == tactic


def test_mcp_tool_arguments_forward_malformed_intent_to_manager_repair() -> None:
    text = intent_text_from_tool_arguments({
        "intent": "",
        "payload": {"tactic": "sp; wp; if."},
    })
    parsed = parse_agent_intent(text)

    assert not parsed.ok
    assert parsed.error == "unknown_or_missing_intent"


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
    assert (
        "proof mutation or profile-visible semantic proof context"
        in tools[0]["description"]
    )
    assert "Bash" not in tools[0]["description"]
    assert "latest_workspace_view.json" not in tools[0]["description"]
    assert "latest_followup.md" in tools[0]["description"]
    assert "proof_so_far.md" in tools[0]["description"]
    assert str(tmp_path / "node_memory" / "Tree_0_0") in tools[0]["description"]
    assert "do not use shell directory discovery" in tools[0]["description"]
    assert "intent" in tools[0]["inputSchema"]["required"]
    intent_enum = tools[0]["inputSchema"]["properties"]["intent"]["enum"]
    assert "request_restart" not in intent_enum
    assert "probe_tactic" not in intent_enum
    assert "probe_replay_suffix_chunk" not in intent_enum


def test_mcp_server_can_opt_into_probe_schema(monkeypatch, tmp_path: Path) -> None:
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
    assert "probe_tactic" in intent_enum
    assert "probe_replay_suffix_chunk" in intent_enum


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


def test_probe_followup_is_scratchpad_minimal_no_anchor_no_panels(tmp_path) -> None:
    # A probe is a scratchpad dry run: the followup is ONLY the outcome + the format
    # reminder. No focus panel / status / manager-result / node-memory anchor — those
    # are about the unchanged committed goal (re-stapling them every probe is what
    # slows the L4 probe loop). Compaction recovery is owned by the system prompt.
    from types import SimpleNamespace
    mem = NodeMemory(tmp_path, "Tree-0.0")
    accepted = ManagedTurn(
        ok=True,
        workspace_view={
            "kind": "prover_workspace_view",
            "proof_status": {"status": "open", "view_focus": "seq_cut",
                             "current_layer": "procedure_body"},
            "current_goal": {"lines": ["Current goal", "the OLD committed goal"]},
            "deep_focus": {"toolbox": ["`case: (<g>)`"]},  # a focus panel that must NOT render
            "last_result": {"tactic": "proc.", "probe_preview": {
                "goal_after_remaining": 1,
                "goal_after_probe": {"lines": ["Current goal", "AFTER proc: the while loop"]}}},
        },
        snapshot=SimpleNamespace(goal_hash="Hp", state_version=2),
    )
    fu = _render_manager_followup(
        accepted, 8, {"intent": "probe_tactic", "payload": {"tactic": "proc."}}, mem)
    assert "Probe preview" in fu and "AFTER proc: the while loop" in fu  # dry-run result leads
    assert "the OLD committed goal" not in fu                            # not the unchanged goal
    assert "Legal Node Memory Anchor" not in fu                          # anchor dropped on a probe
    assert "Manager result (previous turn)" not in fu                    # no manager-result section
    assert "Surgery" not in fu and "case:" not in fu                     # no focus panel
    assert "submit_proof_intent" in fu                                   # format reminder kept

    rejected = ManagedTurn(
        ok=True,
        workspace_view={
            "kind": "prover_workspace_view",
            "proof_status": {"status": "open"},
            "current_goal": {"lines": ["Current goal"] + [f"l{i}" for i in range(20)]},
            "last_result": {"tactic": "inline X.",
                            "error_summary": "[error] cannot inline X: abstract procedure"},
        },
        snapshot=SimpleNamespace(goal_hash="Hr", state_version=2),
    )
    fr = _render_manager_followup(
        rejected, 9, {"intent": "probe_tactic", "payload": {"tactic": "inline X."}}, mem)
    assert "Probe rejected" in fr and "cannot inline X: abstract procedure" in fr
    assert "Legal Node Memory Anchor" not in fr and "Manager result (previous turn)" not in fr
    assert "submit_proof_intent" in fr


def test_commit_followup_is_one_line_last_action_not_manager_result_section(tmp_path) -> None:
    # A commit turn uses the tight L1-style `Last action` one-liner, NOT the
    # `### Manager result (previous turn)` section with its redundant `you submitted`
    # echo (the agent knows what it sent; the new goal proves an accept).
    from types import SimpleNamespace
    mem = NodeMemory(tmp_path, "Tree-0.0")
    accepted = ManagedTurn(
        ok=True,
        workspace_view={
            "kind": "prover_workspace_view",
            "proof_status": {"status": "open"},
            "current_goal": {"lines": ["Current goal", "AFTER proc"]},
            "last_result": {"tactic": "proc.",
                            "result": "EasyCrypt accepted the committed tactic.",
                            "proof_state": "The committed EasyCrypt proof state changed."},
        },
        snapshot=SimpleNamespace(goal_hash="Hc", state_version=2),
    )
    fa = _render_manager_followup(
        accepted, 3, {"intent": "commit_tactic", "payload": {"tactic": "proc."}}, mem)
    assert "**Last action:** `proc.`" in fa and "accepted" in fa
    assert fa.index("## 🎯 Current Goal") < fa.index("**Last action:** `proc.`")
    assert "### Manager result (previous turn)" not in fa   # the section is gone
    assert "you submitted:" not in fa                       # the redundant echo is gone
    assert "Legal Node Memory Anchor" not in fa             # anchor moved to the system prompt

    rejected = ManagedTurn(
        ok=True,
        workspace_view={
            "kind": "prover_workspace_view",
            "proof_status": {"status": "open"},
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "last_result": {"tactic": "apply foo.",
                            "result": "EasyCrypt rejected the committed tactic.",
                            "error_summary": "[error] cannot infer all placeholders"},
        },
        snapshot=SimpleNamespace(goal_hash="Hd", state_version=2),
    )
    fr = _render_manager_followup(
        rejected, 4, {"intent": "commit_tactic", "payload": {"tactic": "apply foo."}}, mem)
    assert "**Last action:** `apply foo.`" in fr and "rejected" in fr.lower()
    assert "EasyCrypt error:" in fr and "cannot infer all placeholders" in fr   # reject = why, inline
    assert fr.index("**Last action:** `apply foo.`") < fr.index("## 🎯 Current Goal")
    assert fr.index("EasyCrypt error:") < fr.index("## 🎯 Current Goal")
    assert "### Manager result (previous turn)" not in fr
