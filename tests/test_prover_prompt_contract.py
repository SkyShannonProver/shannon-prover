"""Contracts for the managed prover prompt and runtime boundary."""

from __future__ import annotations

import inspect
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow import orchestrator  # noqa: E402
from workflow.agents import prover, prover_prompt  # noqa: E402
from workflow.schemas.config import ProverConfig, RunConfig  # noqa: E402
from workflow.schemas.prover_result import (  # noqa: E402
    PROVER_RUN_INCOMPLETE,
    PROVER_RUN_INFRASTRUCTURE_INVALID,
)
from workflow.proof_tool.easycrypt_source_resource import (  # noqa: E402
    SOURCE_RESOURCE_MANIFEST_ENV,
)
from workflow.tree.result import (  # noqa: E402
    TREE_RUN_TERMINATION_WALL_CLOCK_TIMEOUT,
    TreeRunResult,
)


def _stub_prover_runtime(
    monkeypatch,
    tmp_path,
    *,
    worker_returncode=0,
    worker_termination_reason="",
):
    monkeypatch.setattr(prover, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(prover, "_precheck_lemma", lambda *a, **k: "has_admit")
    # Keep the test hermetic: never shell out to the real provider CLI.
    from workflow.provider import provider_sessions as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "provider_cli_identity",
        lambda backend: {
            "agent_backend": backend,
            "binary": "stub",
            "resolved_path": "stub",
            "version": "stub 0.0",
        },
    )
    monkeypatch.setattr(prover, "_ensure_why3server", lambda: "")
    monkeypatch.setattr(prover, "_extract_tactics_from_candidate", lambda *a, **k: [])
    # Prompt-shape tests do not exercise the managed EasyCrypt bootstrap.  Stub
    # that boundary explicitly instead of relying on the retired behavior that
    # manufactured a hollow bootstrap when `_PROJECT_ROOT` had no backend.
    monkeypatch.setattr(prover, "_prepare_managed_session", lambda **_kwargs: {})

    def fake_tree(
        *,
        build_cmd_fn,
        payload_audit_path=None,
        **kwargs,
    ):
        del kwargs
        build_cmd_fn(
            "prover_tree_0_0",
            "0.0",
            [],
            [],
        )
        return TreeRunResult(
            returncode=worker_returncode,
            termination_reason=worker_termination_reason,
            selected_node_id="0.0",
            turns=7,
            payload_audit_path=(
                str(payload_audit_path) if payload_audit_path else ""
            ),
        )
    # prover.run imports run_tree_prover from the supervisor at call time.
    monkeypatch.setattr("workflow.tree.supervisor.run_tree_prover", fake_tree)


def test_retired_workflow_planner_contract_is_physically_absent():
    assert not (_ROOT / "workflow/agents/proof_planner.py").exists()
    assert not (_ROOT / "workflow/schemas/proof_plan.py").exists()
    assert "plan" not in inspect.signature(prover.run).parameters
    assert "use_planner" not in inspect.signature(prover.run).parameters
    assert "plan" not in inspect.signature(orchestrator.run_prover).parameters
    assert "plan" not in inspect.signature(prover_prompt._build_prover_prompt).parameters
    assert "plan" not in inspect.signature(
        prover_prompt._build_child_prover_prompt
    ).parameters
    assert "use_planner" not in {item.name for item in fields(RunConfig)}


def test_forced_opener_helpers_are_removed():
    assert not hasattr(prover_prompt, "_STRATEGY_OPENERS")
    assert not hasattr(prover_prompt, "_classify_goal_shape")
    assert not hasattr(prover_prompt, "_strategy_opener_for")


def test_root_prompt_is_target_pointer_without_strategy_seed(monkeypatch, tmp_path):
    _stub_prover_runtime(monkeypatch, tmp_path)

    result = prover.run(
        file_path="eval/examples/Test.ec",
        lemma_name="target",
        include_dir="easycrypt-src/theories",
        prover=ProverConfig(
            model="test-model",
            timeout_minutes=1,
        ),
        run_dir=tmp_path,
    )

    assert result.status == PROVER_RUN_INCOMPLETE
    assert not result.is_verified
    assert result.turns == 7
    prompt = (tmp_path / "prover_prompt.md").read_text(encoding="utf-8")
    assert "Strategy" + " Seed" not in prompt
    assert "**Opener**" not in prompt
    assert "starting hypothesis for child" not in prompt
    assert "Target file: `eval/examples/Test.ec`" in prompt
    assert "planner" not in prompt.lower()


def test_eval_prompt_matches_manager_only_tool_policy(monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_TARGET_LEMMA", "target")

    prompt = prover_prompt._build_prover_prompt(
        "eval/examples/Test.ec",
        "target",
        "easycrypt-src/theories",
    )

    assert "not an agent-facing filesystem resource" in prompt
    assert "Do not call shell, filesystem, MCP resource" in prompt
    assert "Read the target file on demand" not in prompt


def test_eval_prompt_exposes_only_manager_owned_source_read(monkeypatch):
    monkeypatch.setenv("EVAL_TARGET_LEMMA", "target")
    monkeypatch.setenv(SOURCE_RESOURCE_MANIFEST_ENV, "artifacts/source_manifest.json")

    prompt = prover_prompt._build_prover_prompt(
        "artifacts/eval_source/Test.ec",
        "target",
        "easycrypt-src/theories",
    )

    assert "manager-owned source-navigation tools" in prompt
    assert "runtime contract" in prompt
    assert "provider-native filesystem, shell" in prompt
    assert "Proof-state interaction remains exclusively" in prompt
    assert "not an agent-facing filesystem resource" not in prompt


def test_nonzero_worker_exit_is_canonical_infrastructure_failure(
    monkeypatch,
    tmp_path,
):
    _stub_prover_runtime(monkeypatch, tmp_path, worker_returncode=2)

    result = prover.run(
        file_path="eval/examples/Test.ec",
        lemma_name="target",
        include_dir="easycrypt-src/theories",
        prover=ProverConfig(model="test-model", timeout_minutes=1),
        run_dir=tmp_path,
    )

    assert result.status == PROVER_RUN_INFRASTRUCTURE_INVALID
    assert result.infrastructure_errors == [
        "selected proof worker exited nonzero (code 2)"
    ]


def test_timeout_terminated_worker_is_canonical_incomplete(
    monkeypatch,
    tmp_path,
):
    _stub_prover_runtime(
        monkeypatch,
        tmp_path,
        worker_returncode=-15,
        worker_termination_reason=TREE_RUN_TERMINATION_WALL_CLOCK_TIMEOUT,
    )

    result = prover.run(
        file_path="eval/examples/Test.ec",
        lemma_name="target",
        include_dir="easycrypt-src/theories",
        prover=ProverConfig(model="test-model", timeout_minutes=1),
        run_dir=tmp_path,
    )

    assert result.status == PROVER_RUN_INCOMPLETE
    assert result.infrastructure_errors == []


def test_tree_supervisor_marks_its_wall_clock_termination(tmp_path):
    from workflow.tree.supervisor import run_tree_prover

    result = run_tree_prover(
        lambda *_args, **_kwargs: [
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
        ],
        cwd=str(tmp_path),
        timeout=0,
        max_concurrent=1,
        initial_provers=1,
        source_file=None,
        target_lemma="target",
    )

    assert result.returncode != 0
    assert (
        result.termination_reason
        == TREE_RUN_TERMINATION_WALL_CLOCK_TIMEOUT
    )
    assert result.infrastructure_errors == ()


def test_archive_ec_sessions_preserves_events_and_current_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(prover, "_PROJECT_ROOT", tmp_path)
    session = tmp_path / ".ec_session_prover_target_0"
    (session / "prover_workspace_views").mkdir(parents=True)
    (session / "tactic_execution_results").mkdir()
    (session / "events.jsonl").write_text(
        '{"event_type":"session.started"}\n',
        encoding="utf-8",
    )
    (session / "prover_workspace_views" / "workspace.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (session / "tactic_execution_results" / "result.json").write_text(
        "{}",
        encoding="utf-8",
    )

    run_dir = tmp_path / "run"
    unrelated = tmp_path / ".ec_session_unrelated"
    unrelated.mkdir()
    (unrelated / "history.ec").write_text("admit.\n", encoding="utf-8")
    archived = prover._archive_ec_session_dirs(
        run_dir,
        session_dirs=[str(session)],
    )

    archived_session = run_dir / "ec_sessions" / session.name
    assert str(archived_session.resolve()) in archived
    assert (archived_session / "events.jsonl").exists()
    assert (archived_session / "prover_workspace_views/workspace.json").exists()
    assert (archived_session / "tactic_execution_results/result.json").exists()
    assert (run_dir / "ec_sessions/manifest.json").exists()
    assert not (run_dir / "ec_sessions" / unrelated.name).exists()


if __name__ == "__main__":
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"])
    )
