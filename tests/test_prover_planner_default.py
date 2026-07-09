"""Pytest-style tests for ``workflow.agents.prover``.

Uses ``monkeypatch`` and ``tmp_path`` fixtures, so this file MUST be
run via pytest. The ``__main__`` block at the bottom delegates to
pytest automatically so ``python3 tests/test_prover_planner_default.py``
also works (matching the convention used by the standalone test
files in this directory).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Self-contained path setup so the file is importable both via pytest
# (with tests/conftest.py) and via direct ``python3 -m pytest <file>``.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.agents import prover  # noqa: E402
from workflow.agents import prover_prompt  # noqa: E402
from workflow.schemas.proof_plan import ContextBrief, ProofPlan  # noqa: E402


def _plan_with_statement(statement: str) -> ProofPlan:
    return ProofPlan(
        target_file="eval/examples/Test.ec",
        target_lemma="target",
        difficulty="easy",
        context_brief=ContextBrief(
            file_content=statement + "\nproof. admit. qed.\n",
            target_statement=statement,
        ),
    )


def _stub_prover_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(prover, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(prover, "_precheck_lemma", lambda *a, **k: "has_admit")
    monkeypatch.setattr(prover, "_ensure_why3server", lambda: "")
    monkeypatch.setattr(prover, "_extract_tactics_from_session", lambda *a, **k: [])
    monkeypatch.setattr(prover, "_find_latest_session_id", lambda *a, **k: "")

    def fake_tree(
        *,
        build_cmd_fn,
        cwd,
        timeout,
        max_concurrent,
        initial_provers,
        stuck_errors,
        stuck_idle_seconds,
        grace_seconds,
        max_depth,
        min_alive_seconds,
        progress_gap_ratio,
        progress_gap_idle,
        source_file,
        initial_branches=None,
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


def test_forced_opener_helpers_are_removed():
    assert not hasattr(prover_prompt, "_STRATEGY_OPENERS")
    assert not hasattr(prover_prompt, "_classify_goal_shape")
    assert not hasattr(prover_prompt, "_strategy_opener_for")


def test_no_strategy_seed_opener_injected(monkeypatch, tmp_path):
    # The old forced opener block was removed; the prompt must carry no such
    # instruction.
    _stub_prover_runtime(monkeypatch, tmp_path)

    def fake_planner(config, run_dir, previous_reports=None, previous_plans=None):
        return _plan_with_statement(
            "lemma target &m : "
            "Pr[G0.main() @ &m : res] = Pr[G1.main() @ &m : res]."
        )

    monkeypatch.setattr("workflow.agents.proof_planner.run", fake_planner)

    prover.run(
        file_path="eval/examples/Test.ec",
        lemma_name="target",
        include_dir="easycrypt-src/theories",
        model="test-model",
        timeout_minutes=1,
        parallelism=1,
        warmup_seconds=0,
        run_dir=tmp_path,
    )

    prompt = (tmp_path / "prover_prompt.md").read_text(encoding="utf-8")
    assert "Strategy" + " Seed" not in prompt
    assert "**Opener**" not in prompt
    assert "starting hypothesis for child" not in prompt


def test_prover_run_auto_plans_when_plan_missing(monkeypatch, tmp_path):
    _stub_prover_runtime(monkeypatch, tmp_path)
    calls = []

    def fake_planner(config, run_dir, previous_reports=None, previous_plans=None):
        calls.append((config, Path(run_dir)))
        return ProofPlan(
            target_file=config.file,
            target_lemma=config.lemma,
            difficulty="easy",
            context_brief=ContextBrief(
                file_content="lemma target : true.\nproof. admit. qed.",
                target_statement="lemma target : true.",
                available_lemmas=[
                    {"name": "target", "statement": "lemma target : true.", "status": "admit"}
                ],
            ),
        )

    monkeypatch.setattr("workflow.agents.proof_planner.run", fake_planner)

    result = prover.run(
        file_path="eval/examples/Pedersen.ec",
        lemma_name="target",
        include_dir="easycrypt-src/theories",
        model="test-model",
        timeout_minutes=1,
        parallelism=1,
        warmup_seconds=0,
        run_dir=tmp_path,
    )

    assert not result.proved
    assert calls
    assert calls[0][0].file == "eval/examples/Pedersen.ec"
    prompt = (tmp_path / "prover_prompt.md").read_text(encoding="utf-8")
    # The prompt points at the target instead of inlining it (a97b0ce9f):
    # no embedded file content and no planner lemma list — the agent reads
    # source on demand and gets proof state from the manager view.
    assert (
        "You are proving EasyCrypt lemma `target` in "
        "`eval/examples/Pedersen.ec`." in prompt
    )
    assert "Target file: `eval/examples/Pedersen.ec`" in prompt
    assert "lemma target : true." not in prompt  # planner file content
    assert "- `target` [admit]" not in prompt  # planner lemma list


def test_prover_run_no_planner_is_explicit_ablation(monkeypatch, tmp_path, capsys):
    _stub_prover_runtime(monkeypatch, tmp_path)

    def fail_planner(*args, **kwargs):
        raise AssertionError("planner should not run in explicit ablation mode")

    monkeypatch.setattr("workflow.agents.proof_planner.run", fail_planner)

    result = prover.run(
        file_path="eval/examples/Pedersen.ec",
        lemma_name="target",
        include_dir="easycrypt-src/theories",
        model="test-model",
        timeout_minutes=1,
        parallelism=1,
        warmup_seconds=0,
        run_dir=tmp_path,
        use_planner=False,
    )

    assert not result.proved
    # use_planner=False must be an EXPLICIT, announced ablation, never a
    # silent degrade: the planner is not invoked (fail_planner above would
    # raise) and the run states the ablation mode. The prompt itself no
    # longer carries a planner banner (a97b0ce9f) — it is the same lean
    # target-pointer surface as the planner-backed run.
    assert "ablation" in capsys.readouterr().out
    prompt = (tmp_path / "prover_prompt.md").read_text(encoding="utf-8")
    assert (
        "You are proving EasyCrypt lemma `target` in "
        "`eval/examples/Pedersen.ec`." in prompt
    )


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
    assert (archived_session / "proof_context_views" / "proof_context_view.json").exists()
    assert (archived_session / "command_summaries" / "summary.json").exists()
    assert (run_dir / "ec_sessions" / "manifest.json").exists()



if __name__ == "__main__":
    # Standalone invocation: delegate to pytest so monkeypatch /
    # tmp_path fixtures resolve. Matches the standalone-runner
    # convention used by the rest of tests/ — ``python3 <file>``
    # works for every test file in this directory.
    import subprocess

    raise SystemExit(subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-q"],
    ))
