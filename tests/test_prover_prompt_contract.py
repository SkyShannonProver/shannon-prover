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
from workflow.schemas.config import RunConfig  # noqa: E402


def _stub_prover_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(prover, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(prover, "_precheck_lemma", lambda *a, **k: "has_admit")
    monkeypatch.setattr(prover, "_ensure_why3server", lambda: "")
    monkeypatch.setattr(prover, "_extract_tactics_from_session", lambda *a, **k: [])
    monkeypatch.setattr(prover, "_find_latest_session_id", lambda *a, **k: "")

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
            strategy_index=0,
        )
        fake_tree.last_destructive_abort = False
        fake_tree.last_destructive_reason = ""
        fake_tree.last_session_id = ""
        fake_tree.last_ec_session_dir = ""
        fake_tree.last_information_source_audit = []
        fake_tree.last_payload_audit_path = (
            str(payload_audit_path) if payload_audit_path else ""
        )
        return ("", 0, "0.0", False)

    fake_tree.last_destructive_abort = False
    fake_tree.last_destructive_reason = ""
    fake_tree.last_session_id = ""
    fake_tree.last_ec_session_dir = ""
    fake_tree.last_information_source_audit = []
    fake_tree.last_payload_audit_path = ""
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
        model="test-model",
        timeout_minutes=1,
        parallelism=1,
        warmup_seconds=0,
        run_dir=tmp_path,
    )

    assert not result.proved
    prompt = (tmp_path / "prover_prompt.md").read_text(encoding="utf-8")
    assert "Strategy" + " Seed" not in prompt
    assert "**Opener**" not in prompt
    assert "starting hypothesis for child" not in prompt
    assert "Target file: `eval/examples/Test.ec`" in prompt
    assert "planner" not in prompt.lower()


def test_proof_bank_policy_skips_eval_and_live_smoke(monkeypatch, tmp_path):
    monkeypatch.delenv("EVAL_TARGET_LEMMA", raising=False)
    monkeypatch.delenv("SHANNON_RECORD_PROOF_BANK", raising=False)

    assert prover._should_record_proof_bank(
        "eval/examples/Pedersen.ec", "target", tmp_path, False, None,
    )
    assert not prover._should_record_proof_bank(
        "eval/examples/Pedersen.ec", "target", tmp_path, True, None,
    )
    assert not prover._should_record_proof_bank(
        "artifacts/live_smoke/Pedersen_smoke.ec", "target",
        tmp_path, False, None,
    )
    assert prover._should_record_proof_bank(
        "artifacts/live_smoke/Pedersen_smoke.ec", "target",
        tmp_path, False, True,
    )

    monkeypatch.setenv("EVAL_TARGET_LEMMA", "target")
    assert not prover._should_record_proof_bank(
        "eval/examples/Pedersen.ec", "target", tmp_path, False, None,
    )


def test_archive_ec_sessions_preserves_events_and_views(monkeypatch, tmp_path):
    monkeypatch.setattr(prover, "_PROJECT_ROOT", tmp_path)
    session = tmp_path / ".ec_session_prover_target_0"
    (session / "proof_context_views").mkdir(parents=True)
    (session / "command_summaries").mkdir()
    (session / "events.jsonl").write_text(
        '{"event_type":"session.started"}\n',
        encoding="utf-8",
    )
    (session / "proof_context_views" / "proof_context_view.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (session / "command_summaries" / "summary.json").write_text(
        "{}",
        encoding="utf-8",
    )

    run_dir = tmp_path / "run"
    archived = prover._archive_ec_session_dirs(run_dir)

    archived_session = run_dir / "ec_sessions" / session.name
    assert str(archived_session.resolve()) in archived
    assert (archived_session / "events.jsonl").exists()
    assert (archived_session / "proof_context_views/proof_context_view.json").exists()
    assert (archived_session / "command_summaries/summary.json").exists()
    assert (run_dir / "ec_sessions/manifest.json").exists()


if __name__ == "__main__":
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"])
    )
