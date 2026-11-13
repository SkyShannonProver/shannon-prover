from __future__ import annotations

from pathlib import Path

from workflow.node.proof_node_manager import ProofNodeManager
from workflow.proof_management.repl_session import ReplSessionManager
from workflow.proof_state_compiler.configuration import (
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.managed_goal_view_manager import (
    ManagedGoalViewManager,
)
from workflow.proof_state_compiler.profile_registry import PRODUCTION_PROFILE_REGISTRATIONS


ROOT = Path(__file__).resolve().parents[3]

def test_l1_manager_does_not_assemble_any_legacy_view_component(
    tmp_path: Path,
) -> None:
    manager = ProofNodeManager(
        file_path="target.ec",
        lemma_name="target",
        include_dir=".",
        session_tag="neutral",
        node_id="Tree-neutral",
        project_root=tmp_path,
        surface_profile="l1_goal_projection",
    )

    assert isinstance(manager.workspace, ManagedGoalViewManager)
    for removed in ("surfaces", "node_state", "analyzers", "renderer"):
        assert not hasattr(manager, removed)

def test_current_repl_start_explicitly_skips_historical_debug_view(
    tmp_path: Path,
) -> None:
    repl = ReplSessionManager(
        file_path="target.ec",
        lemma_name="target",
        include_dir=".",
        session_tag="neutral-start",
        node_id="Tree-neutral-start",
        project_root=tmp_path,
    )
    calls: list[tuple[str, list[str]]] = []

    def fake_backend(request, *, actions, timeout):  # noqa: ANN001
        label, args = request.label, list(request.args)
        calls.append((label, list(args)))
        actions.append({"label": label, "exit_code": 0})
        return '{"ok": true}'

    sentinel = object()
    repl._run_backend = fake_backend  # type: ignore[method-assign]
    repl._snapshot_from_managed_goal_view = (  # type: ignore[method-assign]
        lambda *, actions: sentinel
    )

    snapshot, _actions = repl.start()

    assert snapshot is sentinel
    assert calls[0][1] == [
        "-start", "-f", "target.ec", "-I", ".", "-lemma", "target",
    ]

def test_runtime_profiles_have_one_structural_composition_root() -> None:
    for profile_id, registration in PRODUCTION_PROFILE_REGISTRATIONS.items():
        assembly = compiler_assembly_for_profile(profile_id)
        if registration.compiler_profile.activations:
            assert assembly is not None
            assert assembly.manifest.manifest_id == profile_id
        else:
            assert assembly is None

    for relative in (
        "workflow/proof_state_compiler/configuration.py",
        "workflow/proof_state_compiler/profile_ids.py",
        "workflow/proof_state_compiler/surface_profiles.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "CompilerProfile(" not in source, relative
        assert "SurfaceProfile(" not in source, relative

    identity_source = (
        ROOT / "workflow/proof_state_compiler/profile_ids.py"
    ).read_text(encoding="utf-8")
    assert "profile_registry" not in identity_source

def test_codex_and_claude_prove_launchers_share_one_canonical_workflow() -> None:
    skill = (ROOT / ".agents/skills/prove/SKILL.md").read_text(encoding="utf-8")
    metadata = (
        ROOT / ".agents/skills/prove/agents/openai.yaml"
    ).read_text(encoding="utf-8")
    claude = (ROOT / ".claude/commands/prove.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert skill.startswith("---\nname: prove\n")
    assert "proof_state_compiler" in skill
    assert "uv run python -m workflow.orchestrator" in skill
    assert "--agent-backend codex" in skill
    assert "\n     --eval-mode" not in skill
    assert "Do not add `--eval-mode`" in skill
    assert "uv run python -m eval_suite.run" not in skill
    assert "ordinary in-place proof" in skill
    assert 'allow_implicit_invocation: false' in metadata
    assert 'default_prompt: "Use $prove ' in metadata
    assert "Reject extra positional tokens" in skill
    assert "Never offer a cross-backend override" in skill
    assert '<LEMMA>" projects' in skill
    assert '<LEMMA>" eval/examples' in skill
    assert "Search the designated user workspace first" in skill

    assert ".agents/skills/prove/SKILL.md" in claude
    assert "$ARGUMENTS" in claude
    assert "bind the proof-node backend to `claude`" in claude
    assert "[agent_backend]" not in claude
    assert "bootstrap_easycrypt.py" not in claude
    assert "eval_suite.run" not in claude
    assert "do not add `--eval-mode`" in claude

    assert "$prove my_lemma" in readme
    assert "/prove my_lemma" in readme
    assert "eval_suite/suites/demo_pir.json" in readme
    assert "$prove PIR_correct claude" not in readme
    assert "/prove PIR_correct claude" not in readme
    assert "type `/` and choose **Prove**" in readme
    assert "Research evaluation is a different workflow" in readme
    assert "You do **not** need `eval_suite`" in readme
    assert "Strict live evaluation currently requires Linux" in readme
    assert "projects/my-proof/Target.ec" in readme
    assert "It searches `projects/` first" in readme
