from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import textwrap

from workflow.proof_node_manager import ProofNodeManager
from workflow.proof_management.repl_session import ReplSessionManager
from workflow.proof_state_compiler.configuration import (
    COMPILER_PROFILES,
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.managed_goal_view_manager import (
    ManagedGoalViewManager,
)
from workflow.proof_state_compiler.surface_profiles import (
    CURRENT_SURFACE_PROFILES,
)
from workflow.proof_state_compiler.profile_registry import (
    CURRENT_PROFILE_REGISTRATIONS,
)


ROOT = Path(__file__).resolve().parents[1]


def test_fresh_current_manager_process_does_not_load_legacy_compiler_modules() -> None:
    script = textwrap.dedent(
        """
        import json
        import sys
        import tempfile
        from workflow.proof_node_manager import ProofNodeManager

        with tempfile.TemporaryDirectory() as project_root:
            ProofNodeManager(
                file_path="target.ec",
                lemma_name="target",
                include_dir=".",
                session_tag="neutral-import-audit",
                node_id="Tree-neutral-import-audit",
                project_root=project_root,
                surface_profile="l1_goal_projection",
            )

        forbidden_prefixes = (
            "core.easycrypt.analysis",
            "workflow.proof_management.analyzers",
        )
        forbidden_exact = {
            "core.easycrypt.session_agent_view",
            "core.easycrypt.session_prover_workspace_view",
            "core.easycrypt.session_workspace_view_manager",
        }
        loaded = sorted(
            name
            for name in sys.modules
            if name in forbidden_exact
            or any(name.startswith(prefix) for prefix in forbidden_prefixes)
        )
        print(json.dumps(loaded))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == []


def test_fresh_current_worker_and_mcp_imports_do_not_load_legacy_presentation() -> None:
    script = textwrap.dedent(
        """
        import json
        import sys
        import workflow.proof_node_runtime
        import workflow.proof_node_mcp_server

        forbidden_exact = {
            "core.easycrypt.session_workspace_view_manager",
            "workflow.surface_profiles",
            "workflow.surface_turn_model",
            "workflow.surface_composer",
            "workflow.surface_model",
        }
        loaded = sorted(name for name in sys.modules if name in forbidden_exact)
        print(json.dumps(loaded))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == []


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

    def fake_backend(label, args, *, actions, timeout):  # noqa: ANN001
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


def test_current_suite_namespace_contains_only_current_profile_ids() -> None:
    current = set(CURRENT_SURFACE_PROFILES)
    assert current == set(COMPILER_PROFILES)
    for path in sorted((ROOT / "eval_suite/suites").glob("*.json")):
        suite = json.loads(path.read_text(encoding="utf-8"))
        assert set(suite.get("profiles") or ()) <= current, path.name


def test_runtime_profiles_have_one_structural_composition_root() -> None:
    assert set(CURRENT_PROFILE_REGISTRATIONS) == set(COMPILER_PROFILES)
    assert set(CURRENT_PROFILE_REGISTRATIONS) == set(CURRENT_SURFACE_PROFILES)
    for profile_id, registration in CURRENT_PROFILE_REGISTRATIONS.items():
        assert COMPILER_PROFILES[profile_id] is registration.compiler_profile
        assert CURRENT_SURFACE_PROFILES[profile_id] is registration.turn_profile
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


def test_retired_protocols_and_evaluator_are_outside_current_namespaces() -> None:
    assert not any((ROOT / "eval_suite/suites").glob("*m07*"))
    assert not any((ROOT / "eval_suite/suites").glob("*m15*"))
    assert not (
        ROOT
        / "workflow/validation/proof_state_compiler_mechanical_batch_results.py"
    ).exists()
    archived = ROOT / "docs/reports/proof_state_compiler_v2/archived_protocols"
    if archived.exists():
        assert any(archived.glob("*m07*.json"))
        assert any(archived.glob("*m15*.json"))


def test_retired_compiler_source_trees_are_physically_absent() -> None:
    removed = (
        "core/easycrypt/analysis",
        "core/easycrypt/audit",
        "core/easycrypt/search",
        "workflow/proof_management/analyzers",
        "tools/audit_harness",
        "tools/panel_audit",
        "playground",
    )
    assert [path for path in removed if (ROOT / path).exists()] == []


def test_current_action_consumers_use_one_projection_label() -> None:
    consumers = (
        "workflow/agent_prompt_render.py",
        "workflow/managed_turn_outcome.py",
        "workflow/proof_state_compiler/current_turn_composer.py",
        "workflow/proof_state_compiler/turn_evidence.py",
        "workflow/validation/proof_state_compiler_manager_turn_sentinel.py",
    )
    for relative in consumers:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert '"agent_view"' not in source, relative
        assert '"managed_goal_view"' in source, relative


def test_current_operational_docs_use_only_managed_easycrypt_and_v2_profiles() -> None:
    operational_docs = (
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "TESTING.md",
        "RELEASING.md",
        "core/easycrypt/TOOLS.md",
        "eval/README.md",
        "eval_suite/README.md",
        "tools/README.md",
    )
    forbidden = (
        'opam env --switch=easycrypt',
        "l4_checked_action_surface",
        "tools/panel_audit/",
        "tools/audit_harness/",
    )
    violations = []
    for relative in operational_docs:
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "bootstrap_easycrypt.py" not in text:
            violations.append(f"{relative}: missing managed bootstrap")
        for retired in forbidden:
            if retired in text:
                violations.append(f"{relative}: advertises {retired}")
    assert violations == []


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

    assert "$prove PIR_correct" in readme
    assert "/prove PIR_correct" in readme
    assert "$prove PIR_correct claude" not in readme
    assert "/prove PIR_correct claude" not in readme
    assert "type `/` and choose **Prove**" in readme
    assert "Research evaluation is a different workflow" in readme
    assert "You do **not** need `eval_suite`" in readme
    assert "Strict live evaluation currently requires Linux" in readme
    assert "projects/my-proof/Target.ec" in readme
    assert "It searches `projects/` first" in readme


def test_named_architecture_and_evidence_docs_declare_lifecycle_status() -> None:
    governed_tokens = (
        "CHECKPOINT",
        "AUDIT",
        "PREREGISTRATION",
        "RESULTS",
        "ANALYSIS",
    )
    missing = []
    governed_roots = (
        ROOT / "docs/architecture",
        ROOT / "docs/design",
        ROOT / "docs/reports/l1l4_20260801",
        ROOT / "docs/reports/proof_state_compiler_v2",
    )
    for governed_root in governed_roots:
        for path in sorted(governed_root.rglob("*.md")):
            if not any(token in path.name.upper() for token in governed_tokens):
                continue
            head = "\n".join(
                path.read_text(encoding="utf-8").splitlines()[:15]
            )
            if "status:" not in head.lower():
                missing.append(str(path.relative_to(ROOT)))
    assert missing == []
