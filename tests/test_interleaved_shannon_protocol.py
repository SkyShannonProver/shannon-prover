"""Contract tests for the fixed outer/inner Shannon experiment arm."""

import hashlib
import json
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from experiments.interleaved_shannon.agent_config import (
    agent_profile_sha256,
    load_agent_profiles,
    provider_identity_sha256,
    resolve_agent_config,
)
from experiments.interleaved_shannon.run_experiment import (
    OUTER_CLAUDE_REQUIRED_OPTIONS,
    build_outer_command,
    claude_capability_error,
    codex_auth_summary,
    experiment_environment,
    fixed_inner_config_mismatches,
    is_premature_agent_stop,
    preserve_partial_candidate,
    provider_runtime_identity,
    resolve_continuation,
    select_agent_providers,
    source_bundle_preflight,
)
from experiments.interleaved_shannon import (
    run_experiment,
    run_shannon,
    shannon_jobs,
    warm_handoff,
    warm_handoff_sentinel,
)
from experiments.interleaved_shannon.run_shannon import (
    INVOCATION_RECEIPT_KIND,
    INVOCATION_RECEIPT_SCHEMA_VERSION,
    WRAPPER_EXIT_CODES,
    _canonical_prover_result,
    _load_invocation_receipt,
    _merge_verified_proof,
    _wrapper_handback,
    build_shannon_command,
    prepare_shannon_eval_source,
)
from experiments.interleaved_shannon.warm_handoff import (
    _candidate_commands,
    _candidate_step_kept,
    _resolve_handoff_boundary,
    _resolve_resource_anchors,
)
from experiments.interleaved_shannon.verify_task import (
    active_shannon_job_errors,
    allowed_tracked_change_sets,
    easycrypt_command,
    easycrypt_replay_outcome,
    editable_region_forbidden_words,
    immutable_projection,
    shannon_terminal_alerts,
    validate_upto_location,
)
from workflow.schemas.prover_result import ProverResult
from workflow.node.outer_proof_handoff import load_outer_proof_handoff
from workflow.tree.supervisor import NodeSupervisor


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "interleaved_shannon"
PRODUCT = ROOT / "workflow" / "interleaved"
TARGET = EXPERIMENT / "task" / "chacha_poly.ec"


def _test_provider_identity(provider: str, model: str) -> dict[str, str]:
    return {
        "agent_backend": provider,
        "model": model,
        "binary": f"/managed/{provider}",
        "resolved_path": f"/managed/{provider}",
        "binary_sha256": "a" * 64,
        "version": f"{provider} test",
    }


def _write_wrapper_evidence(
    iteration: Path,
    *,
    provider: str = "codex",
    model: str = "gpt-6-astra",
) -> dict[str, str]:
    identity = _test_provider_identity(provider, model)
    (iteration / "provider_identity.json").write_text(
        json.dumps({
            "schema_version": 1,
            "kind": "provider_cli_identity",
            **identity,
        }),
        encoding="utf-8",
    )
    (iteration / "source_manifest.json").write_text(
        json.dumps({
            "schema_version": 1,
            "kind": "eval_source_prep",
            "source_contract": "proof_stripped_project",
            "strip_proofs": True,
            "target_lemma": "L",
        }),
        encoding="utf-8",
    )
    return identity


def test_only_scratchpad_and_conclusion_proof_are_editable() -> None:
    source = TARGET.read_text(encoding="utf-8")
    edited = source.replace(
        "(* SCRATCHPAD END *)",
        "local lemma helper : true.\nproof. trivial. qed.\n  (* SCRATCHPAD END *)",
    ).replace(
        "(* PROVE THIS — replace this line with a machine-checkable proof *)\n  admit.",
        "trivial.",
    )
    assert immutable_projection(edited) == immutable_projection(source)

    changed_statement = edited.replace(
        "qdec%r * pr1_poly_out.",
        "qdec%r * pr1_poly_out + 0%r.",
    )
    assert immutable_projection(changed_statement) != immutable_projection(source)


def test_prompt_exposes_shannon_without_inner_selection_and_fixes_eval_mode() -> None:
    prompt = (EXPERIMENT / "prompt.md").read_text(encoding="utf-8")
    normalized_prompt = " ".join(prompt.split())
    rendered = (
        prompt.replace("{{RUN_DIR}}", "artifacts/interleaved_shannon/test")
        .replace("{{CONTINUATION_CONTEXT}}", "")
    )
    assert "{{" not in rendered and "}}" not in rendered
    assert len(prompt.splitlines()) <= 230
    assert len(prompt.split()) <= 1800
    assert "Opus" not in prompt
    assert "your responsibility" in prompt
    assert "shannon_jobs.py submit" in prompt
    assert "uv run python" not in prompt
    assert ".venv/bin/python experiments/interleaved_shannon/" in prompt
    assert "{{INNER_PROVIDER}}" not in prompt
    assert "{{INNER_MODEL}}" not in prompt
    assert "{{INNER_EFFORT}}" not in prompt
    assert "{{ALLOWED_INNER_PROVIDERS}}" not in prompt
    assert "--provider" not in prompt
    assert "no per-job model or provider setting" in normalized_prompt
    assert "--eval-mode" in prompt
    assert "{{SEGMENT_DEADLINE}}" not in prompt
    assert "{{SEGMENT_BUDGET}}" not in prompt
    assert "{{PRIOR_ACTIVE_TIME}}" not in prompt
    assert "fixed 12-hour task budget" in normalized_prompt
    assert "Treat it as a work budget, not merely an upper bound" in normalized_prompt
    assert "do not exit early" in normalized_prompt
    assert "A failed final verification is feedback" in normalized_prompt
    assert "run final verification again" in normalized_prompt
    assert "verify_task.py --check" in prompt
    assert "verify_task.py --upto LINE[:COL]" in prompt
    assert "verify_task.py --final" in prompt
    assert "Shannon Prover only" not in prompt
    assert "Runtime boundary, autonomy, and finish" in prompt
    assert "Do not wait" in prompt
    assert "fall back to a direct EasyCrypt proof" in normalized_prompt
    assert "You are the outer proof engineer" in normalized_prompt
    assert "Do not background scheduler commands manually" in normalized_prompt
    assert "scheduler provides two Shannon lanes" in normalized_prompt
    assert "later jobs queue automatically" in normalized_prompt
    assert "leave none running or queued" in normalized_prompt
    assert "shannon_jobs.py status" in prompt
    assert "shannon_jobs.py wait" in prompt
    assert "shannon_jobs.py cancel" in prompt
    assert "shannon_jobs.py collect" in prompt
    assert "manager-confirmed `live_progress`" in prompt
    assert "accepted_tactic_count" in prompt
    assert "checkpoint_tactic_count" in prompt
    assert "turn growth alone is only activity" in normalized_prompt
    assert "Do not poll continuously" in normalized_prompt
    assert "--resume-job <JOB_ID>" in prompt
    assert "--continuation-note <PATH>" in prompt
    assert "Omit `--continuation-note`" in prompt
    assert "terminal_cursor" in prompt
    assert "checkpoint.continuation_available" in prompt
    assert "attempts.json" in prompt
    assert "backend private" in prompt
    assert "`source_projection.py`" in prompt
    assert "a verifier error alone does not require Shannon" in normalized_prompt
    assert "direct edits repeatedly return to the same semantic boundary" in normalized_prompt
    assert "choose a qualified Shannon handoff or redesign" in normalized_prompt
    assert "native open goals immediately before the rejected command" in normalized_prompt
    assert "stateless" in prompt
    assert "not a persistent Shannon session" in normalized_prompt
    assert "not a persistent Shannon session or a compiler-enriched view" in normalized_prompt
    assert "temporary `admit` shells" in normalized_prompt
    assert "**Scout:**" in prompt
    assert "**Warm completion:**" in prompt
    assert "**Progressing continuation:**" in prompt
    assert "Coarse development verifier" in prompt
    assert "Choose the Shannon handoff class" in prompt
    assert "Scout modes" in prompt
    assert prompt.index("## Your role") < prompt.index(
        "## Operating model"
    ) < prompt.index("## Coarse development verifier") < prompt.index(
        "## Choose the Shannon handoff class"
    ) < prompt.index("## Submit and hand off") < prompt.index(
        "## Runtime boundary, autonomy, and finish"
    )
    assert "Never submit `conclusion` to Shannon" in normalized_prompt
    assert "Do not ask Shannon to invent the overall reduction" in normalized_prompt
    assert "coarse-grained outer development and fine-grained Shannon" in normalized_prompt
    assert "complementary, interleaved lanes" in normalized_prompt
    assert "need not finish decomposition before calling Shannon" in normalized_prompt
    assert "You may use both Shannon lanes" in normalized_prompt
    assert "continue genuinely independent decomposition" in normalized_prompt
    assert "easycrypt_replay_outcome.status" in prompt
    for status in ("reached_upto", "failed_before_upto", "completed_before_upto"):
        assert status in prompt
    assert "does not automatically find the longest accepted prefix" in normalized_prompt
    assert "do not repeat `--upto` mechanically" in normalized_prompt
    assert "machine-checked semantic progress" in normalized_prompt
    assert "only boilerplate such as `proc` or `move=>`" in normalized_prompt
    assert "A zero-prefix handoff remains a scout" in normalized_prompt
    for scout_type in ("Boundary", "Invariant", "Binding", "Prefix"):
        assert f"| {scout_type} |" in prompt
    assert "Recommended initial scout timeout: 8–15 minutes" in normalized_prompt
    assert "Recommended warm-completion timeout: 15–30 minutes" in normalized_prompt
    assert "Recommended continuation timeout: 15–30 minutes by default" in normalized_prompt
    assert "30–60 after substantial progress" in normalized_prompt
    assert "60–120 only with strong accepted evidence" in normalized_prompt
    assert "120-minute harness limit" not in prompt
    assert "30–60" in prompt
    assert "manual `--upto` replay is not mandatory" in normalized_prompt
    assert "A cold scout is allowed only" in normalized_prompt
    assert "`--handoff-current` transports the candidate" in normalized_prompt
    assert "manager preparation certifies its replayed prefix and open boundary" in normalized_prompt
    assert "not its unaccepted remainder" in normalized_prompt
    assert "It does not classify maturity" in normalized_prompt
    assert "always state `Scout` or `Warm completion` explicitly" in normalized_prompt
    assert "These options require `--handoff-current`" in normalized_prompt
    assert "Notes and anchors must be in the current run" in normalized_prompt
    assert "candidate may also come from its disclosed continuation" in normalized_prompt
    assert "Maturity evidence and machine-checked prefix:" in prompt
    assert "First rejected/next tactic and residual goal:" in prompt
    assert "Expected useful result:" in prompt
    assert "accepted_prefix` is the longest manager-derived prefix" in normalized_prompt
    assert "manager-owned `checkpoint`, when present, is resumable" in normalized_prompt
    assert "without one, use `verify_task.py --check`" in normalized_prompt
    assert "may lag it by `uncheckpointed_tail_tactics`" in normalized_prompt
    assert "`agent_guidance.blockers`" in prompt
    assert "`agent_guidance.discoveries`" in prompt
    assert "bounded `source_breadcrumbs`" in normalized_prompt
    assert "blindly repeating a stalled checkpoint" in normalized_prompt
    assert "Run at most one immature scout" in normalized_prompt


def test_runner_profiles_and_launch_contract() -> None:
    runner = (PRODUCT / "runner.py").read_text(encoding="utf-8")
    profiles = json.loads(
        (PRODUCT / "agent_profiles.json").read_text(encoding="utf-8")
    )
    assert profiles["schema_version"] == 2
    assert profiles["defaults"] == {
        "inner_provider": "codex",
        "outer_provider": "codex",
    }
    assert profiles["profiles"]["claude"]["model"] == "claude-opus-5"
    assert profiles["profiles"]["claude"]["outer_max_turns"] == 8000
    assert profiles["profiles"]["claude"]["outer_max_budget_usd"] == 500
    assert profiles["profiles"]["codex"]["model"] == "gpt-6-astra"
    assert "backend" not in profiles["profiles"]["claude"]
    assert "cli_provider" not in profiles["profiles"]["codex"]
    assert "DEFAULT_TIMEOUT_SECONDS = PROJECT.outer_timeout_seconds" in runner
    assert '"ANTHROPIC_API_KEY"' in runner
    assert '"OPENAI_API_KEY"' in runner
    assert '"CODEX_ACCESS_TOKEN"' in runner
    assert 'required_auth_method = "claude.ai"' in runner
    assert 'else "chatgpt"' in runner
    assert 'parser.add_argument("--continuation-of")' in runner
    assert '"outer_events_sha256"' in runner
    assert '"run_kind": kind' in runner
    assert '"partial_candidate": partial_candidate' in runner
    assert "journal only the wrapper-reported reason" in runner
    assert "do not inspect raw" in runner
    assert '"max_parallel": MAX_PARALLEL' in runner
    assert '"--outer-provider"' in runner
    assert '"--inner-provider"' in runner
    assert "select_agent_providers" in runner
    assert '"login", "status"' in runner


def test_one_config_supports_all_four_outer_inner_combinations() -> None:
    profiles, defaults = load_agent_profiles()
    assert defaults == {"outer_provider": "codex", "inner_provider": "codex"}
    claude = profiles["claude"]
    codex = profiles["codex"]
    assert (claude.cli_provider, claude.model, claude.effort) == (
        "claude-code",
        "claude-opus-5",
        "high",
    )
    assert (codex.cli_provider, codex.model, codex.effort) == (
        "codex",
        "gpt-6-astra",
        "high",
    )
    combinations = {
        (
            resolve_agent_config(
                outer_provider=outer,
                inner_provider=inner,
            ).outer.key,
            resolve_agent_config(
                outer_provider=outer,
                inner_provider=inner,
            ).inner.key,
        )
        for outer in profiles
        for inner in profiles
    }
    assert combinations == {
        ("claude", "claude"),
        ("claude", "codex"),
        ("codex", "claude"),
        ("codex", "codex"),
    }
    claude_command, claude_stdin = build_outer_command(
        claude,
        "/bin/claude",
        rendered_prompt="PROMPT",
    )
    assert claude_stdin is False
    assert claude_command[-1] == "PROMPT"
    assert "--max-turns" in claude_command
    for forbidden in ("Agent(*)", "Task(*)", "WebSearch(*)", "WebFetch(*)"):
        assert forbidden in claude_command

    codex_command, codex_stdin = build_outer_command(
        codex,
        "/bin/codex",
        rendered_prompt="PROMPT",
        codex_features=frozenset({"apps", "multi_agent", "shell_tool"}),
    )
    assert codex_stdin is True
    assert codex_command[-1] == "-"
    assert codex_command[:2] == ["/bin/codex", "exec"]
    assert "gpt-6-astra" in codex_command
    assert "danger-full-access" in codex_command
    assert 'model_reasoning_effort="high"' in codex_command
    assert codex_command.count("--disable") == 2
    assert "apps" in codex_command
    assert "multi_agent" in codex_command
    assert "shell_tool" not in codex_command
    assert codex_command.count("gpt-6-astra") == 1


def test_default_pair_launches_astra_for_both_roles() -> None:
    config = resolve_agent_config()
    assert config.required_provider_keys == frozenset({"codex"})
    outer_command, prompt_via_stdin = build_outer_command(
        config.outer,
        "/bin/codex",
        rendered_prompt="PROMPT",
    )
    assert prompt_via_stdin is True
    assert outer_command[:2] == ["/bin/codex", "exec"]
    assert outer_command[outer_command.index("--model") + 1] == "gpt-6-astra"
    assert 'model_reasoning_effort="high"' in outer_command

    inner_command = build_shannon_command(
        config.inner,
        lemma="L",
        timeout_minutes=60,
        output=Path("artifacts/test"),
    )
    assert inner_command[inner_command.index("--agent-backend") + 1] == "codex"
    assert inner_command[inner_command.index("--prover-model") + 1] == "gpt-6-astra"
    assert inner_command[inner_command.index("--prover-effort") + 1] == "high"


def test_final_audit_rejects_job_from_other_provider_in_selected_pair() -> None:
    profiles, _ = load_agent_profiles()
    expected = "e" * 64
    job = {
        "job_id": "wrong-inner",
        "status": "queued",
        "inner_provider": "claude",
        "inner_model": profiles["claude"].model,
        "inner_effort": profiles["claude"].effort,
        "inner_profile_sha256": agent_profile_sha256(profiles["claude"]),
        "expected_provider_identity_sha256": expected,
    }
    assert fixed_inner_config_mismatches(
        [job],
        inner_profile=profiles["codex"],
        expected_inner_profile_sha256=agent_profile_sha256(profiles["codex"]),
        expected_identity_sha256=expected,
    ) == ["wrong-inner"]


def test_agent_profile_config_rejects_adapter_override_and_unknown_fields(
    tmp_path: Path,
) -> None:
    config = json.loads(
        (PRODUCT / "agent_profiles.json").read_text(encoding="utf-8")
    )
    config["profiles"]["claude"]["cli_provider"] = "codex"
    path = tmp_path / "agent_profiles.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown fields: cli_provider"):
        load_agent_profiles(path)


def test_continuation_provider_selection_inherits_and_fails_closed() -> None:
    defaults = {"outer_provider": "claude", "inner_provider": "codex"}
    inherited = {"outer_provider": "codex", "inner_provider": "claude"}
    assert select_agent_providers(
        defaults=defaults,
        requested={"outer_provider": None, "inner_provider": None},
        inherited=inherited,
        allow_change=False,
    ) == inherited
    with pytest.raises(ValueError, match="allow-provider-change"):
        select_agent_providers(
            defaults=defaults,
            requested={"outer_provider": "claude", "inner_provider": None},
            inherited=inherited,
            allow_change=False,
        )
    assert select_agent_providers(
        defaults=defaults,
        requested={"outer_provider": "claude", "inner_provider": "codex"},
        inherited=inherited,
        allow_change=True,
    ) == defaults


def test_continuation_reads_provider_selection_from_prior_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative = Path("artifacts/interleaved_shannon/prior")
    prior = tmp_path / relative
    prior.mkdir(parents=True)
    (prior / "manifest.json").write_text(
        json.dumps({
            "schema_version": 4,
            "agent_selection": {
                "outer_provider": "codex",
                "inner_provider": "claude",
            },
            "cumulative_active_elapsed_seconds": 1234,
        }),
        encoding="utf-8",
    )
    (prior / "outer_agent_events.jsonl").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(run_experiment, "ROOT", tmp_path)
    loaded_rel, metadata, selection = resolve_continuation(relative.as_posix())
    assert loaded_rel == relative
    assert metadata is not None
    assert metadata["inherited_agent_selection"] == selection
    assert metadata["prior_active_elapsed_seconds"] == 1234
    assert selection == {"outer_provider": "codex", "inner_provider": "claude"}

    (prior / "manifest.json").write_text(
        json.dumps({"schema_version": 3}), encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="schema-v4"):
        resolve_continuation(relative.as_posix())


def test_codex_auth_summary_requires_stored_chatgpt_login() -> None:
    completed = subprocess.CompletedProcess(
        ["/bin/codex", "login", "status"],
        0,
        stdout="Logged in using ChatGPT\n",
        stderr="",
    )
    with patch(
        "experiments.interleaved_shannon.run_experiment.subprocess.run",
        return_value=completed,
    ):
        summary = codex_auth_summary("/bin/codex", {})
    assert summary == {
        "checked": True,
        "exit_code": 0,
        "logged_in": True,
        "auth_method": "chatgpt",
    }


def test_claude_outer_capability_probe_fails_before_launch() -> None:
    completed = subprocess.CompletedProcess(
        ["/bin/claude", "--help"],
        0,
        stdout=" ".join(OUTER_CLAUDE_REQUIRED_OPTIONS),
        stderr="",
    )
    with patch(
        "experiments.interleaved_shannon.run_experiment.subprocess.run",
        return_value=completed,
    ):
        assert claude_capability_error(
            "/bin/claude", {}, require_outer=True, require_inner=False
        ) is None

    completed.stdout = "--print --model"
    with patch(
        "experiments.interleaved_shannon.run_experiment.subprocess.run",
        return_value=completed,
    ):
        error = claude_capability_error(
            "/bin/claude", {}, require_outer=True, require_inner=False
        )
    assert error is not None
    assert "--safe-mode" in error


def test_preflight_provider_identity_binds_binary_bytes(tmp_path: Path) -> None:
    binary = tmp_path / "codex"
    binary.write_bytes(b"provider-binary")
    profile = load_agent_profiles()[0]["codex"]
    identity = provider_runtime_identity(
        profile=profile,
        executable=str(binary),
        version="codex-cli test\nignored",
    )
    assert identity["agent_backend"] == "codex"
    assert identity["model"] == "gpt-6-astra"
    assert identity["resolved_path"] == str(binary.resolve())
    assert identity["binary_sha256"] == hashlib.sha256(
        b"provider-binary"
    ).hexdigest()
    assert identity["version"] == "codex-cli test"


def test_preflight_builds_platform_neutral_proof_stripped_bundle(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "artifacts" / "interleaved_shannon" / "preflight"
    manifest_path = run_dir / "source_preflight" / "eval_source" / "source_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    isolated_root = manifest_path.parent / "source" / "ChaChaPoly"
    isolated_root.mkdir(parents=True)
    source_texts = {
        "chacha_poly.ec": (
            "lemma map2_zip : true. proof. admit. qed.\n"
            "lemma conclusion : true. proof. admit. qed.\n"
        ),
        "indistinguishability.eca": "lemma sibling_a : true. proof. admit. qed.\n",
        "ske.ec": "lemma sibling_b : true. proof. admit. qed.\n",
    }
    for name, text in source_texts.items():
        (isolated_root / name).write_text(text, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "kind": "eval_source_prep",
        "source_contract": "proof_stripped_project",
        "strip_proofs": True,
        "target_lemma": "conclusion",
        "isolated_root": str(isolated_root.relative_to(tmp_path)),
        "isolated_file": str(
            (isolated_root / "chacha_poly.ec").relative_to(tmp_path)
        ),
        "proofs_replaced_total": 3,
        "stripped_file_count": 3,
        "stripped_files": [
            {
                "path": name,
                "stripped_sha256": hashlib.sha256(
                    source_texts[name].encode("utf-8")
                ).hexdigest(),
            }
            for name in source_texts
        ],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    isolated = isolated_root / "chacha_poly.ec"
    (tmp_path / "easycrypt-src" / "theories").mkdir(parents=True)
    with patch.object(run_experiment, "ROOT", tmp_path), patch.object(
        run_experiment, "ANSWER_SOURCE", tmp_path / "absent-answer.ec"
    ), patch.object(
        run_experiment,
        "prepare_shannon_eval_source",
        return_value=SimpleNamespace(manifest=manifest, isolated_file=isolated),
    ), patch.object(
        run_experiment,
        "run_warm_handoff_sentinel",
        return_value={"passed": True},
    ), patch(
        "core.easycrypt.compiler_namespace_adapter.load_exact_declarations",
        return_value={
            "map2_zip": {
                "requested": "map2_zip",
                "status": "resolved",
                "resolved": "map2_zip",
                "kind": "lemma",
                "body": "lemma map2_zip : true.",
                "error": "",
            }
        },
    ):
        result = source_bundle_preflight(run_dir=run_dir)

    assert result["passed"] is True
    assert result["source_contract"] == "proof_stripped_project"
    assert result["answer_source_visible"] is False
    assert result["source_navigation"] == {
        "passed": True,
        "tools": [
            "search_easycrypt_source",
            "read_easycrypt_source",
            "resolve_easycrypt_declaration",
        ],
        "native_resolution_symbol": "map2_zip",
        "target_path": str(isolated.relative_to(tmp_path)),
        "target_sha256": hashlib.sha256(
            source_texts["chacha_poly.ec"].encode("utf-8")
        ).hexdigest(),
    }
    assert result["warm_handoff_sentinel"] == {"passed": True}


def test_premature_stop_requires_clean_early_outer_exit_and_failed_final() -> None:
    assert is_premature_agent_stop(
        final_passed=False,
        timed_out=False,
        interrupted=False,
        exit_code=0,
        elapsed_seconds=100,
        timeout_seconds=1000,
    )
    assert not is_premature_agent_stop(
        final_passed=True,
        timed_out=False,
        interrupted=False,
        exit_code=0,
        elapsed_seconds=100,
        timeout_seconds=1000,
    )
    assert not is_premature_agent_stop(
        final_passed=False,
        timed_out=True,
        interrupted=False,
        exit_code=0,
        elapsed_seconds=1000,
        timeout_seconds=1000,
    )


def test_public_infrastructure_failure_never_has_an_empty_reason() -> None:
    public = shannon_jobs._public_record({
        "schema_version": 1,
        "job_id": "deadbeefdeadbeef",
        "lemma": "L",
        "status": "infrastructure_invalid",
        "error": "",
    })
    assert public["failure_class"] == "scheduler_infrastructure_invalid"
    assert public["failure_message"] == "missing_terminal_failure_reason"
    assert public["error"] == "missing_terminal_failure_reason"
    assert shannon_terminal_alerts({"jobs": [public]}) == [{
        "job_id": "deadbeefdeadbeef",
        "lemma": "L",
        "status": "infrastructure_invalid",
        "failure_class": "scheduler_infrastructure_invalid",
        "failure_message": "missing_terminal_failure_reason",
    }]


def test_running_job_projects_only_validated_manager_live_progress(
    tmp_path: Path,
) -> None:
    job_id = "a" * 16
    run_dir = tmp_path / "run"
    lane_run_dir = tmp_path / "lane_run"
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "status": "running",
    }
    shannon_jobs._save_job(run_dir, record)
    live_path = (
        lane_run_dir
        / "shannon"
        / "L"
        / job_id
        / "2026-08-25_1752_L"
        / "iteration_1"
        / "managed_live_progress.json"
    )
    live_path.parent.mkdir(parents=True)
    supervisor = NodeSupervisor(
        lambda *args, **kwargs: ["unused"],
        str(tmp_path),
        target_lemma="L",
        payload_audit_path=live_path.parent / "payload_audit.jsonl",
        live_progress_path=live_path,
    )
    supervisor.logger = SimpleNamespace(warning=lambda *args: None)
    supervisor.nodes = {
        "0.0": SimpleNamespace(
            tracker=SimpleNamespace(
                committed_count=7,
                manager_turns=11,
                finished=False,
                last_accept_time=1_777_000_000.0,
                session_tag="live_progress_test",
            )
        )
    }
    supervisor._publish_live_progress(phase="proof_search")
    live = json.loads(live_path.read_text(encoding="utf-8"))
    first_bytes = live_path.read_bytes()
    supervisor._publish_live_progress(phase="proof_search")
    assert live_path.read_bytes() == first_bytes

    shannon_jobs._refresh_live_job_progress(
        run_dir=run_dir,
        lane_run_dir=lane_run_dir,
        job_id=job_id,
        lemma="L",
    )

    loaded = shannon_jobs._load_job(run_dir, job_id)
    assert loaded["live_progress"] == live
    assert live["accepted_tactic_count"] == 7
    assert live["checkpoint_tactic_count"] == 0
    assert live["inner_turns"] == 11
    assert shannon_jobs._public_record(loaded)["live_progress"] == live
    loaded["status"] = "incomplete"
    assert "live_progress" not in shannon_jobs._public_record(loaded)

    live["goal"] = "private goal text"
    live_path.write_text(json.dumps(live), encoding="utf-8")
    shannon_jobs._refresh_live_job_progress(
        run_dir=run_dir,
        lane_run_dir=lane_run_dir,
        job_id=job_id,
        lemma="L",
    )
    assert shannon_jobs._load_job(run_dir, job_id)["live_progress"] != live


def test_live_progress_ignores_ambiguous_orchestrator_run_directories(
    tmp_path: Path,
) -> None:
    job_id = "a" * 16
    run_dir = tmp_path / "run"
    lane_run_dir = tmp_path / "lane_run"
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "status": "running",
    }
    shannon_jobs._save_job(run_dir, record)
    progress = {
        "schema_version": 1,
        "kind": "managed_prover_live_progress",
        "authority": "tree_supervisor_manager_observer_projection",
        "lemma": "L",
        "phase": "proof_search",
        "accepted_tactic_count": 1,
        "checkpoint_tactic_count": 0,
        "inner_turns": 1,
        "active_nodes": 1,
        "last_progress_at": "2026-08-25T17:52:00+00:00",
        "observed_at": "2026-08-25T17:52:01+00:00",
    }
    job_output = lane_run_dir / "shannon" / "L" / job_id
    for name in ("2026-08-25_1752_L", "2026-08-25_1753_L"):
        path = job_output / name / "iteration_1" / "managed_live_progress.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(progress), encoding="utf-8")

    shannon_jobs._refresh_live_job_progress(
        run_dir=run_dir,
        lane_run_dir=lane_run_dir,
        job_id=job_id,
        lemma="L",
    )

    assert "live_progress" not in shannon_jobs._load_job(run_dir, job_id)


def test_scheduler_keeps_fresh_heartbeat_when_pid_namespace_hides_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    job_id = "a" * 16
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "status": "running",
        "pid": 12345,
    }
    shannon_jobs._save_job(run_dir, record)
    shannon_jobs._write_worker_heartbeat(
        run_dir,
        job_id=job_id,
        pid=12345,
        phase="running",
    )
    monkeypatch.setattr(shannon_jobs, "_pid_alive", lambda _pid: False)

    shannon_jobs._reconcile_locked(run_dir)

    current = shannon_jobs._load_job(run_dir, job_id)
    assert current["status"] == "running"
    assert "terminal_event_sequence" not in current


def test_scheduler_rejects_stale_heartbeat_for_missing_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    job_id = "b" * 16
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "status": "running",
        "pid": 54321,
    }
    shannon_jobs._save_job(run_dir, record)
    shannon_jobs._write_worker_heartbeat(
        run_dir,
        job_id=job_id,
        pid=54321,
        phase="running",
    )
    heartbeat_path = shannon_jobs._worker_heartbeat_path(run_dir, job_id)
    heartbeat = shannon_jobs._read_json(heartbeat_path)
    heartbeat["updated_at_epoch"] -= (
        shannon_jobs.WORKER_HEARTBEAT_STALE_SECONDS + 1
    )
    shannon_jobs._atomic_json(heartbeat_path, heartbeat)
    monkeypatch.setattr(shannon_jobs, "_pid_alive", lambda _pid: False)

    shannon_jobs._reconcile_locked(run_dir)

    current = shannon_jobs._load_job(run_dir, job_id)
    assert current["status"] == "infrastructure_invalid"
    assert current["error"] == (
        "detached Shannon worker exited without a terminal result"
    )


def test_experiment_environment_prefers_stored_oauth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "workspace-claude")
    monkeypatch.setenv("OPENAI_API_KEY", "workspace-openai")
    monkeypatch.setenv("CODEX_ACCESS_TOKEN", "workspace-codex")

    combined_environment, combined_removed = experiment_environment(
        frozenset({"claude", "codex"})
    )
    assert combined_removed == [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "CODEX_ACCESS_TOKEN",
    ]
    assert "ANTHROPIC_API_KEY" not in combined_environment
    assert "OPENAI_API_KEY" not in combined_environment
    assert "CODEX_ACCESS_TOKEN" not in combined_environment


def test_workspace_preparation_is_non_destructive_and_portable() -> None:
    prepare = (EXPERIMENT / "prepare_workspace.sh").read_text(encoding="utf-8")
    assert "worktree remove" not in prepare
    assert "rm -rf" not in prepare
    assert "/Users/" not in prepare
    assert "worktree add --detach" in prepare
    assert "sparse-checkout" in prepare
    assert "source_projection.py" in prepare
    assert "--exclude-answer-sources" in prepare


def test_verifier_never_selects_ambient_easycrypt() -> None:
    verifier = (EXPERIMENT / "verify_task.py").read_text(encoding="utf-8")
    assert "bootstrap_easycrypt.py" in verifier
    assert "receipt.get(\"easycrypt\"" in verifier
    assert "print-env" not in verifier


def test_development_verifier_returns_native_last_goals() -> None:
    executable = Path("/managed/easycrypt")
    check = easycrypt_command(executable, mode="check")
    assert check[:3] == ["/managed/easycrypt", "llm", "-lastgoals"]
    assert "-no-eco" not in check
    assert check[-1] == "experiments/interleaved_shannon/task/chacha_poly.ec"

    upto = easycrypt_command(executable, mode="upto", upto="1477:3")
    assert upto[:5] == [
        "/managed/easycrypt",
        "llm",
        "-lastgoals",
        "-upto",
        "1477:3",
    ]
    assert validate_upto_location("1") == "1"
    assert validate_upto_location("1477:0") == "1477:0"
    with pytest.raises(ValueError, match="LINE or LINE:COL"):
        validate_upto_location("0")
    with pytest.raises(ValueError, match="LINE or LINE:COL"):
        validate_upto_location("10:2:1")


def test_development_verifier_classifies_upto_stop_reason() -> None:
    assert easycrypt_replay_outcome(
        mode="upto",
        returncode=0,
        stdout="Current goal text\n",
    ) == {
        "status": "reached_upto",
        "native_goal_output": "open_goals",
    }
    assert easycrypt_replay_outcome(
        mode="upto",
        returncode=0,
        stdout="No active proof.\n",
    ) == {
        "status": "reached_upto",
        "native_goal_output": "no_active_proof",
    }
    assert easycrypt_replay_outcome(
        mode="upto",
        returncode=0,
        stdout="",
    ) == {
        "status": "completed_before_upto",
        "native_goal_output": "absent",
    }
    assert easycrypt_replay_outcome(
        mode="upto",
        returncode=1,
        stdout="Last open goal\n",
    ) == {
        "status": "failed_before_upto",
        "native_goal_output": "open_goals",
    }


def test_acceptance_verifier_does_not_use_diagnostic_goal_mode() -> None:
    executable = Path("/managed/easycrypt")
    for mode in ("preflight", "final"):
        command = easycrypt_command(executable, mode=mode)
        assert "llm" not in command
        assert "-lastgoals" not in command
        assert "-upto" not in command
        assert "-no-eco" in command


def test_development_check_allows_only_temporary_admit_escape() -> None:
    assert editable_region_forbidden_words(
        "check",
        "lemma helper : true. proof. admit. qed.",
        "admit.",
    ) == []
    assert editable_region_forbidden_words(
        "final",
        "lemma helper : true. proof. admit. qed.",
        "admit.",
    ) == ["admit"]
    assert editable_region_forbidden_words(
        "check",
        "axiom shortcut : true.",
        "",
    ) == ["axiom"]
    assert editable_region_forbidden_words(
        "upto",
        "lemma helper : true. proof. admit. qed.",
        "admit.",
    ) == []


def test_development_check_accepts_clean_or_target_only_change_set() -> None:
    target = "experiments/interleaved_shannon/task/chacha_poly.ec"
    assert allowed_tracked_change_sets("preflight") == [[]]
    assert allowed_tracked_change_sets("check") == [[], [target]]
    assert allowed_tracked_change_sets("upto") == [[], [target]]
    assert allowed_tracked_change_sets("final") == [[target]]


def test_final_verifier_enforces_shannon_join_barrier() -> None:
    summary = {
        "jobs": [
            {"job_id": "one", "status": "running"},
            {"job_id": "two", "status": "verified"},
        ]
    }
    assert active_shannon_job_errors("check", summary) == []
    assert active_shannon_job_errors("final", summary) == [
        "final verification requires a Shannon join barrier; active jobs: one"
    ]

    summary["active_boundary_violations"] = [{
        "message": "active Shannon boundary changed for L (one)",
    }]
    assert active_shannon_job_errors("check", summary) == [
        "active Shannon boundary changed for L (one)"
    ]
    assert active_shannon_job_errors("final", summary) == [
        "active Shannon boundary changed for L (one)",
        "final verification requires a Shannon join barrier; active jobs: one",
    ]


def test_collect_verification_cannot_reenter_job_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "INTERLEAVED_RUN_DIR",
        "artifacts/interleaved_shannon/current",
    )
    monkeypatch.setenv("SHANNON_TEST_MARKER", "preserved")
    from workflow.interleaved.verify import import_verification_environment
    environment = import_verification_environment()
    assert "INTERLEAVED_RUN_DIR" not in environment
    assert environment["SHANNON_TEST_MARKER"] == "preserved"


def test_product_verifier_receives_repository_relative_output() -> None:
    with patch.object(run_experiment, "run") as invoke:
        run_experiment.invoke_verifier(
            "preflight",
            ROOT / "artifacts" / "interleaved" / "preflight.json",
        )
    assert invoke.call_args.args[0][-1] == (
        "artifacts/interleaved/preflight.json"
    )


def test_shannon_wrapper_bakes_in_platform_neutral_source_boundary() -> None:
    wrapper = (PRODUCT / "inner_runner.py").read_text(encoding="utf-8")
    assert '"--inner-provider"' not in wrapper
    assert '"--eval-mode"' in wrapper
    assert "locked_source_visible" not in wrapper
    assert "prepare_eval_source" in wrapper
    assert "confinement_environment" not in wrapper
    assert "_canonical_source_boundary" in wrapper
    assert 'environment["SHANNON_SUITE_WILL_BUNDLE"] = "1"' in wrapper
    assert "SOURCE_RESOURCE_MANIFEST_ENV" in wrapper
    assert "source_manifest.relative_to(ROOT)" in wrapper
    assert "signal.SIGTERM" in wrapper

    profiles, _ = load_agent_profiles()
    for provider, profile in profiles.items():
        command = build_shannon_command(
            profile,
            lemma="L",
            timeout_minutes=60,
            output=Path("artifacts/test"),
        )
        assert command[command.index("--agent-backend") + 1] == provider
        assert command[command.index("--prover-model") + 1] == profile.model
        assert command[command.index("--prover-effort") + 1] == profile.effort
        assert "--eval-mode" in command


def test_shannon_eval_bundle_preserves_task_local_imports(tmp_path: Path) -> None:
    prepared = prepare_shannon_eval_source(
        target_path=TARGET,
        lemma="conclusion",
        output_root=tmp_path,
    )

    assert sorted(path.name for path in prepared.isolated_root.iterdir()) == [
        "chacha_poly.ec",
        "indistinguishability.eca",
        "ske.ec",
    ]
    assert prepared.manifest["copy_root"] == str(TARGET.parent)
    assert prepared.manifest["stripped_file_count"] == 3
    assert prepared.manifest["proofs_replaced_total"] > 3
    stripped = {
        item["path"]: item["proofs_replaced"]
        for item in prepared.manifest["stripped_files"]
    }
    assert set(stripped) == {
        "chacha_poly.ec",
        "indistinguishability.eca",
        "ske.ec",
    }
    assert stripped["chacha_poly.ec"] > 0
    for name, count in stripped.items():
        if count:
            assert "admit." in (
                prepared.isolated_root / name
            ).read_text(encoding="utf-8")


def test_shannon_job_parallelism_is_fixed_at_two() -> None:
    scheduler = (PRODUCT / "jobs.py").read_text(encoding="utf-8")
    assert shannon_jobs.MAX_PARALLEL == 2
    assert "MAX_PARALLEL = _SETTINGS.project.max_parallel" in scheduler


def test_shannon_scheduler_requires_outer_decomposed_helper_lemma() -> None:
    source = f"""lemma Existing : true.
proof. trivial. qed.
{shannon_jobs.SCRATCHPAD_BEGIN}
lemma HybridHop : true.
proof. admit. qed.
{shannon_jobs.SCRATCHPAD_END}
lemma conclusion : 1 = 1.
proof. admit. qed.
"""

    shannon_jobs._require_outer_decomposition_boundary(source, "HybridHop")

    with pytest.raises(
        ValueError,
        match="final target conclusion cannot be delegated",
    ):
        shannon_jobs._require_outer_decomposition_boundary(source, "conclusion")
    with pytest.raises(ValueError, match="outer-defined helper lemma"):
        shannon_jobs._require_outer_decomposition_boundary(source, "Existing")
    with pytest.raises(
        ValueError,
        match="final target conclusion cannot be delegated",
    ):
        shannon_jobs.submit_job(
            lemma="conclusion",
            timeout_minutes=20,
            handoff_current=False,
            strategy_note=None,
        )


def test_shannon_scheduler_rejects_renamed_final_claim() -> None:
    source = fr"""{shannon_jobs.SCRATCHPAD_BEGIN}
lemma WholeGoalRenamed &state : 1 = 1 /\ true.
proof. admit. qed.
{shannon_jobs.SCRATCHPAD_END}
lemma conclusion &m :
  1 = 1 /\ true.
proof. admit. qed.
"""

    assert shannon_jobs._lemma_claim_projection(source, "WholeGoalRenamed") == (
        shannon_jobs._lemma_claim_projection(source, "conclusion")
    )
    with pytest.raises(ValueError, match="helper claim duplicates"):
        shannon_jobs._require_outer_decomposition_boundary(
            source,
            "WholeGoalRenamed",
        )


@pytest.mark.parametrize("head,claim", [
    ("local lemma", "true"), ("local\nlemma", "true"),
    ("local (* nested (* comment *) *)\nlemma", "true"),
    ("equiv", "M.f ~ M.f : ={arg} ==> ={res}"),
    ("hoare", "M.f : true ==> true"),
    ("phoare", "[M.f : true ==> true] = 1%r"),
])
def test_delegation_accepts_shared_declaration_forms(head, claim):
    source = (f"{shannon_jobs.SCRATCHPAD_BEGIN}\n"
              "(* lemma Helper : false. proof. admit. qed. *)\n"
              f"theory Nested.\n{head} Helper : {claim}.\nproof. trivial. qed.\n"
              f"end Nested.\n{shannon_jobs.SCRATCHPAD_END}\n"
              "lemma conclusion : 1 = 1.\nproof. admit. qed.\n")
    shannon_jobs._require_outer_decomposition_boundary(source, "Helper")
    assert shannon_jobs._lemma_claim_projection(source, "Helper").startswith(":")


def test_commented_helper_does_not_authorize_delegation():
    source = ("lemma Helper : true.\nproof. trivial. qed.\n"
              f"{shannon_jobs.SCRATCHPAD_BEGIN}\n"
              "(* local lemma Helper : true. proof. trivial. qed. *)\n"
              f"{shannon_jobs.SCRATCHPAD_END}\n"
              "lemma conclusion : 1 = 1.\nproof. admit. qed.\n")
    with pytest.raises(ValueError, match="outer-defined helper lemma"):
        shannon_jobs._require_outer_decomposition_boundary(source, "Helper")


@pytest.mark.parametrize("head", ["local lemma", "local\nlemma"])
def test_local_helper_still_cannot_duplicate_final_claim(head):
    source = (f"{shannon_jobs.SCRATCHPAD_BEGIN}\n"
              f"{head} Helper : 1 = 1.\nproof. admit. qed.\n"
              f"{shannon_jobs.SCRATCHPAD_END}\n"
              "lemma conclusion : 1 = 1.\nproof. admit. qed.\n")
    with pytest.raises(ValueError, match="helper claim duplicates"):
        shannon_jobs._require_outer_decomposition_boundary(source, "Helper")


def test_shannon_job_uses_only_runner_fixed_inner_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_rel = Path("artifacts/interleaved_shannon/test")
    run_dir = tmp_path / run_rel
    run_dir.mkdir(parents=True)
    target = tmp_path / "target.ec"
    target.write_text(
        f"{shannon_jobs.SCRATCHPAD_BEGIN}\n"
        "lemma L : true.\nproof.\n  admit.\nqed.\n"
        f"{shannon_jobs.SCRATCHPAD_END}\n"
        "lemma conclusion : 1 = 1.\nproof.\n  admit.\nqed.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(shannon_jobs, "ROOT", tmp_path)
    monkeypatch.setattr(shannon_jobs, "TARGET", "target.ec")
    monkeypatch.setattr(
        shannon_jobs,
        "run_directory",
        lambda: (run_rel, run_dir),
    )
    monkeypatch.setattr(shannon_jobs, "_dispatch_locked", lambda **_kwargs: None)
    monkeypatch.setattr(
        shannon_jobs.subprocess,
        "check_output",
        lambda *_args, **_kwargs: "commit-id\n",
    )
    monkeypatch.setenv("INTERLEAVED_INNER_PROVIDER", "codex")
    monkeypatch.setenv(
        "INTERLEAVED_INNER_PROFILE_SHA256",
        agent_profile_sha256(load_agent_profiles()[0]["codex"]),
    )
    monkeypatch.setenv(
        "INTERLEAVED_INNER_PROVIDER_IDENTITY_JSON",
        json.dumps(_test_provider_identity("codex", "gpt-6-astra")),
    )

    record = shannon_jobs.submit_job(
        lemma="L",
        timeout_minutes=60,
        handoff_current=False,
        strategy_note=None,
        candidate_source=None,
    )

    assert record["status"] == "queued"
    assert "inner_provider" not in record
    assert "inner_model" not in record
    assert "inner_effort" not in record
    private = shannon_jobs.private_job_records(run_dir)
    assert len(private) == 1
    assert private[0]["inner_provider"] == "codex"
    assert private[0]["inner_model"] == "gpt-6-astra"
    assert private[0]["inner_effort"] == "high"
    assert private[0]["agent_profiles_sha256"]
    assert private[0]["inner_profile_sha256"] == agent_profile_sha256(
        load_agent_profiles()[0]["codex"]
    )
    assert private[0]["invocation_receipt_sha256"]
    assert private[0]["expected_provider_identity_sha256"]
    scheduler = (EXPERIMENT / "shannon_jobs.py").read_text(encoding="utf-8")
    assert '"--provider"' not in scheduler


def test_provider_identity_fingerprint_ignores_artifact_envelope() -> None:
    expected = _test_provider_identity("codex", "gpt-6-astra")
    observed = {
        "schema_version": 1,
        "kind": "provider_cli_identity",
        **expected,
    }

    assert provider_identity_sha256(expected) == provider_identity_sha256(observed)

    observed["binary"] = "/relocated/bin/codex"
    observed["resolved_path"] = "/different/prefix/codex"
    assert provider_identity_sha256(expected) == provider_identity_sha256(observed)

    observed["model"] = "wrong-model"
    assert provider_identity_sha256(expected) != provider_identity_sha256(observed)


def test_shannon_wrapper_requires_scheduler_owned_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_rel = Path("artifacts/interleaved_shannon/test")
    run_dir = tmp_path / run_rel
    job_id = "1234567890abcdef"
    receipt_dir = run_dir / "job_input" / job_id
    receipt_dir.mkdir(parents=True)
    record = {
        "job_id": job_id,
        "lemma": "L",
        "timeout_minutes": 60,
        "source_commit": "commit-id",
        "source_contract": {"target_sha256": "b" * 64},
        "agent_profiles_sha256": "c" * 64,
        "inner_profile_sha256": agent_profile_sha256(
            load_agent_profiles()[0]["codex"]
        ),
        "inner_agent": {"profile": "codex"},
        "expected_provider_identity": _test_provider_identity(
            "codex", "gpt-6-astra"
        ),
    }
    receipt = shannon_jobs._invocation_receipt(record=record, run_rel=run_rel)
    path = receipt_dir / "invocation_receipt.json"
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(run_shannon, "ROOT", tmp_path)
    monkeypatch.setenv("INTERLEAVED_SHANNON_INVOCATION_ID", job_id)
    monkeypatch.setenv(
        "INTERLEAVED_SHANNON_INVOCATION_RECEIPT",
        str(path.relative_to(tmp_path)),
    )
    monkeypatch.setenv(
        "INTERLEAVED_SHANNON_INVOCATION_RECEIPT_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    loaded, loaded_path, _ = _load_invocation_receipt(
        run_rel=run_rel,
        run_dir=run_dir,
    )
    assert loaded == receipt
    assert loaded["kind"] == INVOCATION_RECEIPT_KIND
    assert loaded["schema_version"] == INVOCATION_RECEIPT_SCHEMA_VERSION
    assert loaded_path == path

    monkeypatch.delenv("INTERLEAVED_SHANNON_INVOCATION_RECEIPT_SHA256")
    with pytest.raises(ValueError, match="receipt is missing"):
        _load_invocation_receipt(run_rel=run_rel, run_dir=run_dir)


def test_confined_proof_merge_preserves_unrelated_proof_bodies(
    tmp_path: Path,
) -> None:
    current = """lemma Prior : true.
proof.
  trivial.
qed.
lemma L : true.
proof.
  admit.
qed.
"""
    isolated = """lemma Prior : true.
proof.
  admit.
qed.
lemma L : true.
proof.
  trivial.
qed.
"""
    target = tmp_path / "target.ec"
    projected = tmp_path / "projected.ec"
    target.write_text(current, encoding="utf-8")
    projected.write_text(isolated, encoding="utf-8")
    result = _merge_verified_proof(
        isolated_file=projected,
        target_file=target,
        lemma="L",
        prepared_source=isolated.replace("  trivial.", "  admit.", 1),
        expected_target_sha256=hashlib.sha256(current.encode()).hexdigest(),
    )
    merged = target.read_text(encoding="utf-8")
    assert "lemma Prior : true.\nproof.\n  trivial." in merged
    assert "lemma L : true.\nproof.\n  trivial." in merged
    assert len(result["proof_body_sha256"]) == 64


def test_confined_proof_merge_accepts_target_body_indentation(
    tmp_path: Path,
) -> None:
    current = """lemma L : true.
proof.
admit.
qed.
"""
    isolated = """lemma L : true.
proof.
  by trivial.
qed.
"""
    target = tmp_path / "target.ec"
    projected = tmp_path / "projected.ec"
    target.write_text(current, encoding="utf-8")
    projected.write_text(isolated, encoding="utf-8")

    _merge_verified_proof(
        isolated_file=projected,
        target_file=target,
        lemma="L",
        prepared_source=current,
        expected_target_sha256=hashlib.sha256(current.encode()).hexdigest(),
    )

    assert target.read_text(encoding="utf-8") == isolated


def test_shannon_job_dispatch_never_starts_third_worker(tmp_path: Path) -> None:
    for index in range(3):
        shannon_jobs._save_job(tmp_path, {
            "schema_version": 1,
            "job_id": f"{index:016x}",
            "created_at": f"2026-08-22T00:00:{index:02d}-07:00",
            "status": "queued",
            "lemma": f"L{index}",
        })

    class _Process:
        def __init__(self, pid: int):
            self.pid = pid

    launched: list[int] = []

    def _popen(*_args, **_kwargs):
        pid = 4000 + len(launched)
        launched.append(pid)
        return _Process(pid)

    with (
        patch.object(
            shannon_jobs,
            "_active_boundary_violations",
            return_value=[],
        ),
        patch.object(shannon_jobs.subprocess, "Popen", side_effect=_popen),
    ):
        with shannon_jobs._registry_lock(tmp_path):
            shannon_jobs._dispatch_locked(
                run_rel=Path("artifacts/interleaved_shannon/test"),
                run_dir=tmp_path,
            )

    jobs = shannon_jobs._all_jobs(tmp_path)
    assert len(launched) == 2
    assert sum(item["status"] == "running" for item in jobs) == 2
    assert sum(item["status"] == "queued" for item in jobs) == 1


def test_shannon_job_dispatch_uses_one_python_launcher(
    tmp_path: Path,
) -> None:
    shannon_jobs._save_job(tmp_path, {
        "schema_version": 1,
        "job_id": "0000000000000001",
        "created_at": "2026-08-22T00:00:00-07:00",
        "status": "queued",
        "lemma": "L",
    })

    with (
        patch.object(
            shannon_jobs,
            "_active_boundary_violations",
            return_value=[],
        ),
        patch.object(shannon_jobs.subprocess, "Popen") as launch,
    ):
        launch.return_value.pid = 4000
        with shannon_jobs._registry_lock(tmp_path):
            shannon_jobs._dispatch_locked(
                run_rel=Path("artifacts/interleaved_shannon/test"),
                run_dir=tmp_path,
            )

    command = launch.call_args.args[0]
    assert command[0] == sys.executable
    assert command[1].endswith("/workflow/interleaved/jobs.py")
    assert command[2:] == ["worker", "--job-id", "0000000000000001"]


def test_shannon_dispatch_holds_queue_on_active_boundary_violation(
    tmp_path: Path,
) -> None:
    job_id = "0000000000000001"
    shannon_jobs._save_job(tmp_path, {
        "schema_version": 1,
        "job_id": job_id,
        "created_at": "2026-08-22T00:00:00-07:00",
        "status": "queued",
        "lemma": "L",
    })
    violation = [{"job_id": job_id, "lemma": "L"}]

    with (
        patch.object(
            shannon_jobs,
            "_active_boundary_violations",
            return_value=violation,
        ),
        patch.object(shannon_jobs.subprocess, "Popen") as launch,
    ):
        with shannon_jobs._registry_lock(tmp_path):
            shannon_jobs._dispatch_locked(
                run_rel=Path("artifacts/interleaved_shannon/test"),
                run_dir=tmp_path,
            )

    launch.assert_not_called()
    assert shannon_jobs._load_job(tmp_path, job_id)["status"] == "queued"


def test_shannon_job_registry_fails_closed_on_invalid_record(tmp_path: Path) -> None:
    record = tmp_path / "shannon_jobs/0000000000000001/job.json"
    record.parent.mkdir(parents=True)
    record.write_text(
        json.dumps({"schema_version": 1, "job_id": "0000000000000002"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid Shannon job record"):
        shannon_jobs._all_jobs(tmp_path)


def test_shannon_worker_launch_failure_is_terminal(
    tmp_path: Path,
) -> None:
    job_id = "0000000000000001"
    shannon_jobs._save_job(tmp_path, {
        "schema_version": 1,
        "job_id": job_id,
        "created_at": "2026-08-22T00:00:00-07:00",
        "status": "queued",
        "lemma": "L",
    })
    with (
        patch.object(
            shannon_jobs,
            "_active_boundary_violations",
            return_value=[],
        ),
        patch.object(
            shannon_jobs.subprocess,
            "Popen",
            side_effect=OSError("launch unavailable"),
        ),
    ):
        with pytest.raises(OSError, match="launch unavailable"):
            with shannon_jobs._registry_lock(tmp_path):
                shannon_jobs._dispatch_locked(
                    run_rel=Path("artifacts/interleaved_shannon/test"),
                    run_dir=tmp_path,
                )
    record = shannon_jobs._load_job(tmp_path, job_id)
    assert record["status"] == "infrastructure_invalid"
    assert "worker launch failed" in record["error"]


def test_worker_binds_wrapper_to_receipt_identity_and_source_boundary(
    tmp_path: Path,
) -> None:
    job_id = "0000000000000001"
    identity = _test_provider_identity("codex", "gpt-6-astra")
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "inner_provider": "codex",
        "inner_model": "gpt-6-astra",
        "inner_effort": "high",
        "invocation_receipt_sha256": "b" * 64,
        "expected_provider_identity": identity,
        "expected_provider_identity_sha256": provider_identity_sha256(identity),
    }
    run_dir = tmp_path / "run"
    lane = tmp_path / "lane"
    lane_run = lane / "run"
    wrapper_path = lane_run / "shannon" / "L" / job_id / "wrapper_result.json"
    wrapper_path.parent.mkdir(parents=True)
    wrapper = {
        "kind": "interleaved_shannon_wrapper_result",
        "invocation_id": job_id,
        "lemma": "L",
        "inner_provider": "codex",
        "inner_model": "gpt-6-astra",
        "inner_effort": "high",
        "invocation_receipt_sha256": "b" * 64,
        "provider_identity": {
            "schema_version": 1,
            "kind": "provider_cli_identity",
            **identity,
        },
        "provider_identity_sha256": provider_identity_sha256(identity),
        "eval_source_boundary": {
            "kind": "interleaved_shannon_source_boundary",
            "source_contract": "proof_stripped_project",
            "source_manifest_sha256": "d" * 64,
            "answer_source_visible_before": False,
            "answer_source_visible_during": False,
            "answer_source_visible_after": False,
        },
        "eval_source_manifest_sha256": "d" * 64,
        "status": "infrastructure_invalid",
        "prover_result_id": "result-id",
        "infrastructure_errors": [
            "safe-stop checkpoint finalization is missing"
        ],
        "progress": {
            "schema_version": 2,
            "kind": "interleaved_shannon_progress_capsule",
            "lemma": "L",
            "turns": 4,
            "elapsed_seconds": 12.0,
            "accepted_prefix": {
                "tactic_count": 1,
                "sha256": hashlib.sha256(b"move=> H.\n").hexdigest(),
                "byte_count": len(b"move=> H.\n"),
                "authority": "manager_committed_history_reporting_artifact",
                "replay_required_before_use": True,
                "text": "move=> H.\n",
            },
            "agent_guidance": {
                "authority": "untrusted_inner_agent_report",
                    "blockers": ["Need a coupling invariant."],
            },
            "next_actions": [
                "replay_prefix_in_outer",
                "warm_handoff",
                "redesign_boundary",
            ],
            "terminal": {
                "status": "infrastructure_invalid",
                "cause": "safe_stop_checkpoint_finalization_failed",
                "message": "safe-stop checkpoint finalization is missing",
            },
        },
    }
    wrapper_path.write_text(json.dumps(wrapper), encoding="utf-8")
    result = shannon_jobs._worker_result(
        record=record,
        run_dir=run_dir,
        lane=lane,
        lane_run_dir=lane_run,
        wrapper_exit_code=20,
    )
    assert result["actual_provider_identity_sha256"] == (
        provider_identity_sha256(identity)
    )
    assert result["eval_source_manifest_sha256"] == "d" * 64
    public = shannon_jobs._public_record(result)
    assert public["progress"]["accepted_prefix"]["text"] == "move=> H.\n"
    assert shannon_terminal_alerts({"jobs": [public]})[0]["progress"] == (
        public["progress"]
    )

    wrapper["progress"]["accepted_prefix"]["sha256"] = "0" * 64
    wrapper_path.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match its hash"):
        shannon_jobs._worker_result(
            record=record,
            run_dir=run_dir,
            lane=lane,
            lane_run_dir=lane_run,
            wrapper_exit_code=20,
        )
    wrapper["progress"]["accepted_prefix"]["sha256"] = hashlib.sha256(
        b"move=> H.\n"
    ).hexdigest()
    wrapper["provider_identity"]["model"] = "wrong-model"
    wrapper_path.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(ValueError, match="actual provider identity"):
        shannon_jobs._worker_result(
            record=record,
            run_dir=run_dir,
            lane=lane,
            lane_run_dir=lane_run,
            wrapper_exit_code=20,
        )


def test_worker_preserves_pre_provider_infrastructure_failure(
    tmp_path: Path,
) -> None:
    job_id = "0000000000000001"
    identity = _test_provider_identity("codex", "gpt-6-astra")
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "inner_provider": "codex",
        "inner_model": "gpt-6-astra",
        "inner_effort": "high",
        "invocation_receipt_sha256": "b" * 64,
        "expected_provider_identity": identity,
        "expected_provider_identity_sha256": provider_identity_sha256(identity),
    }
    run_dir = tmp_path / "run"
    lane = tmp_path / "lane"
    lane_run = lane / "run"
    wrapper_path = lane_run / "shannon" / "L" / job_id / "wrapper_result.json"
    wrapper_path.parent.mkdir(parents=True)
    wrapper_path.write_text(json.dumps({
        "kind": "interleaved_shannon_wrapper_result",
        "invocation_id": job_id,
        "lemma": "L",
        "inner_provider": "codex",
        "inner_model": "gpt-6-astra",
        "inner_effort": "high",
        "invocation_receipt_sha256": "b" * 64,
        "provider_identity": {},
        "provider_identity_sha256": "",
        "eval_source_boundary": {},
        "eval_source_manifest_sha256": "",
        "status": "infrastructure_invalid",
        "prover_result_id": "",
        "infrastructure_errors": [
            "warm handoff preparation failed: no authoritative open goal"
        ],
        "failure_class": "wrapper_infrastructure_invalid",
        "failure_message": "warm handoff preparation failed",
    }), encoding="utf-8")

    result = shannon_jobs._worker_result(
        record=record,
        run_dir=run_dir,
        lane=lane,
        lane_run_dir=lane_run,
        wrapper_exit_code=20,
    )

    assert result["status"] == "infrastructure_invalid"
    assert "warm handoff preparation failed" in result["error"]
    assert result["actual_provider_identity"] == {}
    assert result["actual_provider_identity_sha256"] == ""


def test_inner_process_shutdown_escalates_after_grace_period() -> None:
    class _Process:
        pid = 4321

        def poll(self):
            return None

        def wait(self, timeout):
            if timeout == 8:
                raise shannon_jobs.subprocess.TimeoutExpired("inner", timeout)
            return -signal.SIGKILL

    with patch.object(shannon_jobs.os, "killpg") as kill_group:
        shannon_jobs._stop_inner_process(_Process())
    assert [item.args for item in kill_group.call_args_list] == [
        (4321, signal.SIGTERM),
        (4321, signal.SIGKILL),
    ]


def test_shannon_source_contract_allows_only_independent_suffix_work() -> None:
    source = """op x = 0.
lemma L : true.
proof.
  admit.
qed.
lemma Later : true.
proof. admit. qed.
"""
    contract = shannon_jobs._source_contract(source, "L")

    suffix_edit = source.replace("lemma Later : true.", "lemma Later : 0 = 0.")
    suffix_contract = shannon_jobs._source_contract(suffix_edit, "L")
    assert suffix_contract["lemma_prefix_sha256"] == contract["lemma_prefix_sha256"]
    assert suffix_contract["proof_body_sha256"] == contract["proof_body_sha256"]

    proof_edit = source.replace("  admit.", "  trivial.", 1)
    proof_contract = shannon_jobs._source_contract(proof_edit, "L")
    assert proof_contract["lemma_prefix_sha256"] == contract["lemma_prefix_sha256"]
    assert proof_contract["proof_body_sha256"] != contract["proof_body_sha256"]

    prefix_edit = source.replace("op x = 0.", "op x = 1.")
    prefix_contract = shannon_jobs._source_contract(prefix_edit, "L")
    assert prefix_contract["lemma_prefix_sha256"] != contract["lemma_prefix_sha256"]


def test_collect_merges_only_verified_proof_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """lemma L : true.
proof.
  admit.
qed.
lemma Later : true.
proof. admit. qed.
"""
    proved = source.replace("  admit.", "  trivial.", 1)
    target = tmp_path / "target.ec"
    target.write_text(source, encoding="utf-8")
    run_rel = Path("artifacts/interleaved_shannon/test")
    run_dir = tmp_path / run_rel
    run_dir.mkdir(parents=True)
    job_id = "0000000000000001"

    monkeypatch.setattr(shannon_jobs, "ROOT", tmp_path)
    monkeypatch.setattr(shannon_jobs, "TARGET", "target.ec")
    monkeypatch.setattr(
        shannon_jobs,
        "run_directory",
        lambda: (run_rel, run_dir),
    )
    monkeypatch.setenv("INTERLEAVED_RUN_DIR", run_rel.as_posix())
    shannon_jobs._save_job(run_dir, {
        "schema_version": 1,
        "job_id": job_id,
        "created_at": "2026-08-22T00:00:00-07:00",
        "status": "verified",
        "lemma": "L",
        "source_contract": shannon_jobs._source_contract(source, "L"),
    })
    (shannon_jobs._job_dir(run_dir, job_id) / "proved_candidate.ec").write_text(
        proved,
        encoding="utf-8",
    )

    with patch.object(shannon_jobs, "check_import_with_project_verifier",
                      return_value={"passed": True}) as verify:
        result = shannon_jobs.collect_job(job_id)

    assert result["status"] == "merged"
    assert target.read_text(encoding="utf-8") == proved
    assert verify.call_args.kwargs["lemma"] == "L"
    assert verify.call_args.kwargs["candidate"].read_text() == proved


def test_candidate_snapshot_accepts_only_disclosed_continuation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = tmp_path / "artifacts/interleaved_shannon/current"
    prior = tmp_path / "artifacts/interleaved_shannon/prior"
    unrelated = tmp_path / "artifacts/interleaved_shannon/unrelated"
    for directory in (current, prior, unrelated):
        directory.mkdir(parents=True)
        (directory / "candidate.ec").write_text("lemma L : true.\n", encoding="utf-8")
    monkeypatch.setattr(shannon_jobs, "ROOT", tmp_path)
    monkeypatch.setenv(
        "INTERLEAVED_CONTINUATION_OF",
        "artifacts/interleaved_shannon/prior",
    )

    assert shannon_jobs._resolve_candidate_file(
        current,
        "artifacts/interleaved_shannon/prior/candidate.ec",
    ) == prior / "candidate.ec"
    with pytest.raises(ValueError, match="disclosed continuation"):
        shannon_jobs._resolve_candidate_file(
            current,
            "artifacts/interleaved_shannon/unrelated/candidate.ec",
        )


def test_shannon_wrapper_projects_only_canonical_prover_result(tmp_path: Path) -> None:
    iteration = tmp_path / "one_run" / "iteration_1"
    iteration.mkdir(parents=True)
    result = ProverResult(
        status="verified",
        verification={"status": "pass", "method": "test"},
    )
    result.save(iteration / "prover_run_result.json")
    (iteration.parent / "summary.json").write_text(
        json.dumps({
            "final_proved": True,
            "final_prover_result_id": result.result_id,
            "final_prover_result_status": result.status,
        }),
        encoding="utf-8",
    )

    loaded, path = _canonical_prover_result(tmp_path)
    assert loaded.result_id == result.result_id
    assert path == iteration / "prover_run_result.json"


def test_shannon_wrapper_rejects_process_success_without_result(tmp_path: Path) -> None:
    identity = _test_provider_identity("codex", "gpt-6-astra")
    handback = _wrapper_handback(
        output_root=tmp_path,
        invocation_id="12345678",
        lemma="L",
        process_exit_code=0,
        wrapper_error="",
        inner_provider="codex",
        inner_model="gpt-6-astra",
        inner_effort="high",
        expected_provider_identity=identity,
        invocation_receipt_sha256="b" * 64,
        expected_source_manifest=tmp_path / "source_manifest.json",
    )
    assert handback["status"] == "infrastructure_invalid"
    assert handback["verified"] is False
    assert handback["prover_result_id"] == ""


def test_shannon_wrapper_returns_partial_prefix_without_checkpoint(
    tmp_path: Path,
) -> None:
    iteration = tmp_path / "one_run" / "iteration_1"
    iteration.mkdir(parents=True)
    result = ProverResult(
        status="incomplete",
        turns=17,
        elapsed_seconds=91.5,
        notes="The residual goal needs a stronger loop invariant.",
        report={
            "blockers": ["The current invariant does not retain the counter bound."],
            "discoveries": ["The first two tactics are accepted."],
        },
    )
    result.save(iteration / "prover_run_result.json")
    partial_prefix = "move=> H.\nrewrite H.\n"
    (iteration / "partial_proof_prefix.ec").write_text(
        partial_prefix,
        encoding="utf-8",
    )
    (iteration / "partial_proof_prefix.json").write_text(
            json.dumps({
                "kind": "partial_proof_prefix",
                "schema_version": 2,
                "lemma": "L",
                "closed_by_qed": False,
                "tactic_count": 2,
                "byte_count": len(partial_prefix.encode("utf-8")),
                "sha256": hashlib.sha256(
                    partial_prefix.encode("utf-8")
                ).hexdigest(),
                "source": "manager_session_history_or_resume_capsule",
                "replay_required_before_use": True,
            }),
        encoding="utf-8",
    )
    (iteration.parent / "summary.json").write_text(
        json.dumps({
            "final_proved": False,
            "final_prover_result_id": result.result_id,
            "final_prover_result_status": result.status,
        }),
        encoding="utf-8",
    )
    identity = _write_wrapper_evidence(iteration)

    handback = _wrapper_handback(
        output_root=tmp_path,
        invocation_id="12345678",
        lemma="L",
        process_exit_code=0,
        wrapper_error="",
        inner_provider="codex",
        inner_model="gpt-6-astra",
        inner_effort="high",
        expected_provider_identity=identity,
        invocation_receipt_sha256="b" * 64,
        expected_source_manifest=iteration / "source_manifest.json",
    )
    assert handback["status"] == "incomplete"
    assert handback["verified"] is False
    assert handback["eval_source_boundary"]["source_contract"] == (
        "proof_stripped_project"
    )
    assert handback["provider_identity"]["agent_backend"] == "codex"
    assert handback["progress"]["turns"] == 17
    assert handback["progress"]["accepted_prefix"]["text"] == partial_prefix
    assert handback["progress"]["accepted_prefix"]["tactic_count"] == 2
    assert handback["progress"]["accepted_prefix"][
        "replay_required_before_use"
    ] is True
    assert handback["progress"]["agent_guidance"]["authority"] == (
        "untrusted_inner_agent_report"
    )
    assert "counter bound" in handback["progress"]["agent_guidance"][
        "blockers"
    ][0]
    assert handback["failure_message"] == ""
    assert "checkpoint" not in handback["progress"]
    assert handback["progress"]["terminal"]["status"] == "incomplete"
    assert WRAPPER_EXIT_CODES[handback["status"]] == 10


def test_shannon_wrapper_projects_canonical_infrastructure_reason(
    tmp_path: Path,
) -> None:
    iteration = tmp_path / "one_run" / "iteration_1"
    iteration.mkdir(parents=True)
    result = ProverResult(
        status="infrastructure_invalid",
        error="tree search failed",
        infrastructure_errors=["warm replay diverged"],
        verification={"status": "fail", "method": "full_file_and_extracted_failed",
                      "candidate_id": "bound-candidate", "reason": "native rejection: unmatched goal"},
    )
    result.save(iteration / "prover_run_result.json")
    (iteration.parent / "summary.json").write_text(
        json.dumps({
            "final_proved": False,
            "final_prover_result_id": result.result_id,
            "final_prover_result_status": result.status,
        }),
        encoding="utf-8",
    )
    identity = _write_wrapper_evidence(iteration)

    handback = _wrapper_handback(
        output_root=tmp_path,
        invocation_id="12345678",
        lemma="L",
        process_exit_code=20,
        wrapper_error="",
        inner_provider="codex",
        inner_model="gpt-6-astra",
        inner_effort="high",
        expected_provider_identity=identity,
        invocation_receipt_sha256="b" * 64,
        expected_source_manifest=iteration / "source_manifest.json",
    )
    assert handback["status"] == "infrastructure_invalid"
    assert handback["failure_class"] == "prover_result_infrastructure_invalid"
    assert "tree search failed" in handback["failure_message"]
    assert "warm replay diverged" in handback["failure_message"]
    assert "native rejection: unmatched goal" in handback["failure_message"]
    assert handback["progress"]["verification"] == result.verification
    assert handback["infrastructure_errors"]


def test_warm_handoff_accepts_exhausted_candidate_with_open_goal() -> None:
    index, tactic, reason, status = _resolve_handoff_boundary(
        tactics=["proc.", "auto."],
        failed_index=None,
        failure_view={
            "proof_status": {
                "goal_identity_required": True,
                "goal_hash": "goal-1",
                "remaining_goals": 1,
            }
        },
    )

    assert index == 2
    assert tactic == ""
    assert reason == "candidate_exhausted_with_open_goal"
    assert status["goal_hash"] == "goal-1"


def test_warm_handoff_accepts_monotonic_multi_commit_expansion() -> None:
    assert _candidate_step_kept(
        accepted=["proc."],
        committed=["proc.", "case H.", "- auto.", "+ trivial."],
    )
    assert not _candidate_step_kept(
        accepted=["proc."],
        committed=["proc."],
    )
    assert not _candidate_step_kept(
        accepted=["proc."],
        committed=["skip.", "auto."],
    )


def test_warm_handoff_preserves_multiline_commands_and_stops_at_admit() -> None:
    commands = _candidate_commands("""
have h : Pr[G.main() @ &m : res] <=
  Pr[H.main() @ &m : res].
+ admit.
+ trivial.
""")

    assert commands == [
        "have h : Pr[G.main() @ &m : res] <=\n"
        "  Pr[H.main() @ &m : res]."
    ]


def test_warm_handoff_stops_at_comment_prefixed_admit_placeholder() -> None:
    commands = _candidate_commands("""
(* PROVE THIS — replace this line with a machine-checkable proof *)
  admit.
""")

    assert commands == []


def test_warm_handoff_preparation_always_stops_its_scoped_daemon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stopped: list[tuple[str, str]] = []

    monkeypatch.setattr(
        run_shannon,
        "prepare_outer_proof_handoff",
        lambda **_kwargs: tmp_path / "outer_handoff.json",
    )
    monkeypatch.setattr(
        "core.easycrypt.ec_daemon_client.default_socket_path",
        lambda: "/tmp/ec_daemon_warm_handoff_test.sock",
    )
    monkeypatch.setattr(
        "workflow.agents.ec_services._shutdown_ec_daemon",
        lambda *, reason, socket_path: stopped.append((reason, socket_path)),
    )

    result = run_shannon._prepare_outer_handoff_with_daemon_cleanup(
        root=tmp_path,
        run_rel=Path("artifacts/test"),
        lemma="L",
        strategy_note="note.md",
    )

    assert result == tmp_path / "outer_handoff.json"
    assert stopped == [(
        "outer proof handoff preparation finished",
        "/tmp/ec_daemon_warm_handoff_test.sock",
    )]


def test_warm_handoff_preparation_stops_daemon_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stopped: list[str] = []

    def fail(**_kwargs: object) -> Path:
        raise RuntimeError("preparation failed")

    monkeypatch.setattr(run_shannon, "prepare_outer_proof_handoff", fail)
    monkeypatch.setattr(
        "core.easycrypt.ec_daemon_client.default_socket_path",
        lambda: "/tmp/ec_daemon_warm_handoff_failure.sock",
    )
    monkeypatch.setattr(
        "workflow.agents.ec_services._shutdown_ec_daemon",
        lambda *, reason, socket_path: stopped.append(socket_path),
    )

    with pytest.raises(RuntimeError, match="preparation failed"):
        run_shannon._prepare_outer_handoff_with_daemon_cleanup()

    assert stopped == ["/tmp/ec_daemon_warm_handoff_failure.sock"]


def test_warm_handoff_sentinel_stops_checkout_daemon_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.ec"
    target.write_text("SENTINEL_BODY", encoding="utf-8")
    stopped: list[tuple[str, str]] = []

    def fail(**_kwargs: object) -> Path:
        raise RuntimeError("sentinel failed")

    monkeypatch.setattr(warm_handoff_sentinel, "ROOT", tmp_path)
    monkeypatch.setattr(warm_handoff_sentinel, "TARGET", "target.ec")
    monkeypatch.setattr(
        warm_handoff_sentinel,
        "_proof_body",
        lambda *_args: ("SENTINEL_BODY", None),
    )
    monkeypatch.setattr(
        warm_handoff_sentinel,
        "prepare_outer_proof_handoff",
        fail,
    )
    monkeypatch.setattr(
        "core.easycrypt.ec_daemon_client.default_socket_path",
        lambda: "/tmp/ec_daemon_warm_sentinel_test.sock",
    )
    monkeypatch.setattr(
        "workflow.agents.ec_services._shutdown_ec_daemon",
        lambda *, reason, socket_path: stopped.append((reason, socket_path)),
    )

    with pytest.raises(RuntimeError, match="sentinel failed"):
        warm_handoff_sentinel.run_warm_handoff_sentinel(
            run_dir=tmp_path / "run"
        )

    assert stopped == [(
        "warm-handoff sentinel finished",
        "/tmp/ec_daemon_warm_sentinel_test.sock",
    )]


def test_warm_handoff_sentinel_keeps_multiline_command_as_one_spine_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.ec"
    target.write_text("SENTINEL_BODY", encoding="utf-8")
    command_hash = hashlib.sha256(json.dumps(
        [warm_handoff_sentinel.SENTINEL_COMMAND],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()

    def prepare(**_kwargs: object) -> Path:
        manifest = tmp_path / "outer_handoff.json"
        manifest.write_text(json.dumps({
            "replay": {
                "commands": [warm_handoff_sentinel.SENTINEL_COMMAND],
                "commands_sha256": command_hash,
                "accepted_command_count": 1,
                "committed_spine_count": 1,
                "committed_spine_sha256": command_hash,
            },
            "boundary": {
                "goal_identity_required": True,
                "goal_hash": "a" * 40,
            },
        }), encoding="utf-8")
        return manifest

    monkeypatch.setattr(warm_handoff_sentinel, "ROOT", tmp_path)
    monkeypatch.setattr(warm_handoff_sentinel, "TARGET", "target.ec")
    monkeypatch.setattr(
        warm_handoff_sentinel,
        "_proof_body",
        lambda *_args: ("SENTINEL_BODY", None),
    )
    monkeypatch.setattr(
        warm_handoff_sentinel,
        "prepare_outer_proof_handoff",
        prepare,
    )
    monkeypatch.setattr(
        "core.easycrypt.ec_daemon_client.default_socket_path",
        lambda: "/tmp/ec_daemon_warm_sentinel_test.sock",
    )
    monkeypatch.setattr(
        "workflow.agents.ec_services._shutdown_ec_daemon",
        lambda **_kwargs: None,
    )

    result = warm_handoff_sentinel.run_warm_handoff_sentinel(
        run_dir=tmp_path / "run"
    )

    assert result["passed"] is True
    assert result["accepted_command_count"] == 1
    assert result["committed_spine_count"] == 1


def test_warm_handoff_replays_exact_commands_and_certifies_canonical_spine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / warm_handoff.TARGET
    target.parent.mkdir(parents=True)
    target.write_text(
        """lemma L : true.
proof.
  have h : true =
    true by trivial.
  admit.
  trivial.
qed.
""",
        encoding="utf-8",
    )
    run_rel = Path("artifacts/interleaved_shannon/test")
    run_dir = tmp_path / run_rel
    run_dir.mkdir(parents=True)
    note = run_dir / "handoff_L.md"
    note.write_text("Continue from the accepted have.", encoding="utf-8")

    exact_command = "have h : true =\n    true by trivial."
    canonical_spine = [exact_command]
    goal_status = {
        "goal_identity_required": True,
        "goal_hash": "a" * 40,
        "remaining_goals_known": True,
    }
    submitted: list[str] = []

    class _Manager:
        def __init__(self, **_kwargs):
            pass

        def bootstrap(self, replay_prefix=None):
            replay_prefix = list(replay_prefix or [])
            if replay_prefix:
                assert replay_prefix == [exact_command]
                replayed = canonical_spine
            else:
                replayed = []
            return {
                "replay_prefix": replayed,
                "workspace_view": {"proof_status": goal_status},
            }

        def handle_agent_message(self, raw):
            tactic = json.loads(raw)["payload"]["tactic"]
            submitted.append(tactic)
            return SimpleNamespace(
                committed_tactics=tuple(canonical_spine),
                workspace_view={"proof_status": goal_status},
            )

        def close_session(self):
            return True

    monkeypatch.setattr(warm_handoff, "ProofNodeManager", _Manager)
    monkeypatch.setattr(
        warm_handoff.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout="deadbeef\n", stderr="", returncode=0
        ),
    )

    manifest_path = warm_handoff.prepare_outer_proof_handoff(
        root=tmp_path,
        run_rel=run_rel,
        lemma="L",
        strategy_note=str(note.relative_to(tmp_path)),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    loaded = load_outer_proof_handoff(manifest_path)

    assert submitted == [exact_command]
    assert manifest["replay"]["commands"] == [exact_command]
    assert manifest["replay"]["accepted_command_count"] == 1
    assert manifest["replay"]["committed_spine_count"] == 1
    assert loaded.replay_commands == (exact_command,)
    assert loaded.committed_spine_count == 1


def test_strategy_only_handoff_certifies_initial_open_goal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / warm_handoff.TARGET
    target.parent.mkdir(parents=True)
    target.write_text(
        "lemma L : true.\nproof.\n"
        "  (* PROVE THIS — replace this line with a machine-checkable proof *)\n"
        "  admit.\nqed.\n",
        encoding="utf-8",
    )
    run_rel = Path("artifacts/interleaved_shannon/test")
    run_dir = tmp_path / run_rel
    run_dir.mkdir(parents=True)
    note = run_dir / "handoff_L.md"
    note.write_text("Try a direct trivial proof.", encoding="utf-8")
    goal_status = {
        "goal_identity_required": True,
        "goal_hash": "a" * 40,
        "remaining_goals_known": True,
    }

    class _Manager:
        def __init__(self, **_kwargs):
            pass

        def bootstrap(self, replay_prefix=None):
            assert list(replay_prefix or []) == []
            return {
                "replay_prefix": [],
                "workspace_view": {"proof_status": goal_status},
            }

        def handle_agent_message(self, _raw):
            raise AssertionError("zero-prefix handoff must not submit a tactic")

        def close_session(self):
            return True

    monkeypatch.setattr(warm_handoff, "ProofNodeManager", _Manager)
    monkeypatch.setattr(
        warm_handoff.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout="deadbeef\n", stderr="", returncode=0
        ),
    )

    manifest_path = warm_handoff.prepare_outer_proof_handoff(
        root=tmp_path,
        run_rel=run_rel,
        lemma="L",
        strategy_note=str(note.relative_to(tmp_path)),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    loaded = load_outer_proof_handoff(manifest_path)

    assert manifest["replay"]["commands"] == []
    assert manifest["replay"]["accepted_command_count"] == 0
    assert manifest["boundary"]["reason"] == "candidate_exhausted_with_open_goal"
    assert loaded.replay_commands == ()
    assert loaded.strategy_note == "Try a direct trivial proof."


def test_warm_handoff_resource_anchors_are_native_resolved_and_hash_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "artifacts" / "interleaved_shannon" / "test"
    run_dir.mkdir(parents=True)
    target = tmp_path / warm_handoff.TARGET
    target.parent.mkdir(parents=True)
    target.write_text("lemma L : true.\nproof. trivial. qed.\n", encoding="utf-8")
    anchor_file = run_dir / "resources.json"
    anchor_file.write_text(json.dumps([{
        "symbol": "CCA_UFCMA.dec_enc",
        "intended_use": "call",
        "role": "encryption correctness",
    }]), encoding="utf-8")
    declaration = "lemma CCA_UFCMA.dec_enc : true."
    declaration_sha256 = hashlib.sha256(declaration.encode("utf-8")).hexdigest()
    captured = {}

    def _load(requests, *, context_file, include_dirs):
        captured["requests"] = requests
        captured["context_file"] = context_file
        captured["include_dirs"] = include_dirs
        return SimpleNamespace(declarations=({
            "symbol": "CCA_UFCMA.dec_enc",
            "source_ref": "easycrypt-native:print:test#CCA_UFCMA.dec_enc",
            "declaration_sha256": declaration_sha256,
            "declaration": declaration,
        },))

    monkeypatch.setattr(warm_handoff, "load_requested_declarations", _load)
    path, anchors = _resolve_resource_anchors(
        root=tmp_path,
        run_dir=run_dir,
        raw=str(anchor_file.relative_to(tmp_path)),
        context_source=target.read_text(encoding="utf-8"),
        context_source_ref=str(target.relative_to(tmp_path)),
        lemma="L",
        source_dir=target.parent,
    )

    assert path == anchor_file
    assert captured["requests"][0].symbols == ("CCA_UFCMA.dec_enc",)
    assert anchors == [{
        "symbol": "CCA_UFCMA.dec_enc",
        "intended_use": "call",
        "role": "encryption correctness",
        "source_ref": (
            "easycrypt-native:print:experiments/interleaved_shannon/task/"
            "chacha_poly.ec@sha256:"
            + hashlib.sha256(
                "lemma L : true.\nproof. ".encode("utf-8")
            ).hexdigest()
            + "#CCA_UFCMA.dec_enc"
        ),
        "declaration_sha256": declaration_sha256,
        "declaration": declaration,
    }]


def test_warm_handoff_resource_anchor_miss_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    anchor_file = run_dir / "resources.json"
    anchor_file.write_text(json.dumps([{
        "symbol": "guessed_nonexistent_lemma",
        "intended_use": "apply",
        "role": "guessed helper",
    }]), encoding="utf-8")
    target = tmp_path / "target.ec"
    target.write_text("lemma L : true.\n", encoding="utf-8")
    monkeypatch.setattr(
        warm_handoff,
        "load_requested_declarations",
        lambda *_args, **_kwargs: SimpleNamespace(declarations=()),
    )

    with pytest.raises(ValueError, match="did not resolve exactly"):
        _resolve_resource_anchors(
            root=tmp_path,
            run_dir=run_dir,
            raw=str(anchor_file.relative_to(tmp_path)),
            context_source=(
                "lemma L : true.\nproof.\n  admit.\nqed.\n"
            ),
            context_source_ref="target.ec",
            lemma="L",
            source_dir=target.parent,
        )


def test_warm_handoff_distinguishes_closed_and_unknown_exhaustion() -> None:
    with pytest.raises(ValueError, match="verify it directly"):
        _resolve_handoff_boundary(
            tactics=["trivial."],
            failed_index=None,
            failure_view={
                "proof_status": {
                    "goal_identity_required": False,
                    "remaining_goals": 0,
                }
            },
        )

    with pytest.raises(ValueError, match="authoritative open or closed"):
        _resolve_handoff_boundary(
            tactics=["auto."],
            failed_index=None,
            failure_view={"proof_status": {"remaining_goals": 1}},
        )


def test_answer_bearing_upstream_example_is_excluded_at_rest() -> None:
    projection = (EXPERIMENT / "source_projection.py").read_text(encoding="utf-8")
    assert "!/easycrypt-src/examples/" in projection
    assert "examples\" / \"ChaChaPoly\" / \"chacha_poly.ec" in projection


def test_failed_run_candidate_is_preserved_with_hash(tmp_path: Path) -> None:
    target = tmp_path / "candidate.ec"
    target.write_text("lemma x : true. proof. trivial. qed.\n", encoding="utf-8")
    run_dir = ROOT / "artifacts" / "interleaved_shannon" / tmp_path.name
    run_dir.mkdir(parents=True)
    snapshot = run_dir / "partial_candidate.ec"
    try:
        metadata = preserve_partial_candidate(target=target, run_dir=run_dir)
        assert snapshot.read_bytes() == target.read_bytes()
        assert metadata["path"].endswith("/partial_candidate.ec")
        assert len(metadata["sha256"]) == 64
    finally:
        snapshot.unlink(missing_ok=True)
        run_dir.rmdir()


def test_lane_default_daemon_cleanup_targets_exact_lane_socket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lane = tmp_path / "detached-lane"
    calls: list[dict[str, object]] = []
    from workflow.agents import ec_services

    monkeypatch.setattr(
        ec_services,
        "_shutdown_ec_daemon",
        lambda **kwargs: calls.append(kwargs) or True,
    )

    assert shannon_jobs._shutdown_lane_default_ec_daemon(lane) is True
    expected_key = hashlib.sha1(
        str(lane.resolve()).encode("utf-8")
    ).hexdigest()[:12]
    assert calls == [{
        "reason": "detached Shannon lane finished",
        "socket_path": f"/tmp/ec_daemon_{expected_key}.sock",
    }]


def test_lane_teardown_stops_daemon_before_removing_worktree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lane = tmp_path / "detached-lane"
    actions: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        shannon_jobs,
        "_shutdown_lane_default_ec_daemon",
        lambda path: actions.append(("shutdown", path)) or True,
    )
    monkeypatch.setattr(
        shannon_jobs,
        "_remove_lane",
        lambda path: actions.append(("remove", path)),
    )

    shannon_jobs._teardown_lane(lane)

    assert actions == [("shutdown", lane), ("remove", lane)]
