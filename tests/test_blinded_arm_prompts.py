"""Arms that never expose compiler bytes must not name a compiler or the arm.

The research audit arms are checked in test_blinded_audit_arm_prompts.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from eval_suite import run as suite_run
from workflow.node.agent_prompt_render import render_long_lived_agent_prompt
from workflow.node.node_memory import NodeMemory
from workflow.node.proof_node_runtime import _prover_system_anchor
from workflow.proof_state_compiler.profile_registry import (
    profile_exposes_compiler_output,
)
from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract

L1 = "l1_goal_projection"
PRODUCTION = "proof_state_compiler"

_ORIGINAL = (
    "[EVAL MODE ACTIVE]\n\n"
    "You are proving EasyCrypt lemma `foo` in `artifacts/x/source/T.ec`.\n\n"
    "## What you can reason about vs what you need EC for\n\nbody\n"
)


def _prompt(profile: str, tmp_path: Path) -> str:
    return render_long_lived_agent_prompt(
        _ORIGINAL,
        proof_tool_manifest=resolve_proof_tool_contract(
            profile, source_navigation_enabled=True
        ),
        node_memory_dir=tmp_path / "node_memory" / "Tree_0_0",
        max_turns=7,
        surface_profile=profile,
    )


def test_l1_prompt_never_names_a_compiler(tmp_path: Path) -> None:
    profile = L1
    assert profile_exposes_compiler_output(profile) is False
    prompt = _prompt(profile, tmp_path)
    anchor = _prover_system_anchor(
        NodeMemory(tmp_path, "Tree_0_0"),
        resolve_proof_tool_contract(profile, source_navigation_enabled=True),
        compiler_output_visible=profile_exposes_compiler_output(profile),
    )
    assert "compiler" not in prompt.lower()
    assert "compiler" not in anchor.lower()
    assert "This proof surface is part of the experiment contract" in prompt
    assert "The current goal arrives in each manager turn" in anchor


@pytest.mark.parametrize(("profile", "names_compiler"), [(L1, False), (PRODUCTION, True)])
def test_runtime_system_anchor_follows_the_arm(
    profile: str, names_compiler: bool, tmp_path: Path
) -> None:
    from workflow.node.proof_node_runtime import ProofNodeRuntime

    runtime = ProofNodeRuntime.__new__(ProofNodeRuntime)
    runtime.memory = NodeMemory(tmp_path, "Tree_0_0")
    runtime.proof_tool_manifest = resolve_proof_tool_contract(
        profile, source_navigation_enabled=True
    )
    runtime.surface_profile = profile
    anchor = runtime._system_anchor(None)
    assert ("compiler" in anchor.lower()) is names_compiler


def test_production_prompt_keeps_its_compiler_wording(tmp_path: Path) -> None:
    assert profile_exposes_compiler_output(PRODUCTION) is True
    prompt = _prompt(PRODUCTION, tmp_path)
    anchor = _prover_system_anchor(
        NodeMemory(tmp_path, "Tree_0_0"),
        resolve_proof_tool_contract(PRODUCTION, source_navigation_enabled=True),
    )
    assert "and the current compiler profile." in prompt
    assert "This compiler profile is part of the experiment contract" in prompt
    assert "The current goal and any bounded compiler output arrive" in anchor


def test_arm_directory_labels_replace_the_profile_path_component() -> None:
    defaults = {
        "output_dir": "out",
        "arm_directory_labels": {L1: "arm-a", PRODUCTION: "arm-b"},
    }
    suite_run._validate_arm_directory_labels(defaults, [L1, PRODUCTION])
    path = suite_run._run_output_dir(
        target={"id": "t1"},
        profile=PRODUCTION,
        repeat=1,
        defaults=defaults,
        suite_name="ab",
    )
    assert path == Path("out/ab/arm-b/t1/r01")
    assert "compiler" not in str(path)


@pytest.mark.parametrize(
    "labels",
    [
        {L1: "arm-a"},
        {L1: "arm-a", PRODUCTION: "arm-a"},
        {L1: "arm-a", PRODUCTION: "x_proof_state_compiler"},
        {L1: "arm-a", PRODUCTION: "a/b"},
        {L1: "arm-a", PRODUCTION: "compiler"},
        {L1: "l1", PRODUCTION: "arm-b"},
        {L1: "arm-a", PRODUCTION: "with-audit"},
    ],
)
def test_arm_directory_labels_must_be_complete_distinct_and_neutral(
    labels: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        suite_run._validate_arm_directory_labels(
            {"arm_directory_labels": labels}, [L1, PRODUCTION]
        )


@pytest.mark.parametrize(
    ("suite_name", "output_dir"),
    [("compiler_v2_ab", "out"), ("ab", "artifacts/l1_vs_prod")],
)
def test_blinded_suite_name_and_output_dir_must_not_name_an_arm(
    suite_name: str, output_dir: str,
) -> None:
    # Both appear in the source path the agent is shown.
    with pytest.raises(ValueError, match="names an arm"):
        suite_run._validate_arm_directory_labels(
            {
                "output_dir": output_dir,
                "arm_directory_labels": {L1: "arm-a", PRODUCTION: "arm-b"},
            },
            [L1, PRODUCTION],
            suite_name=suite_name,
        )


def test_unlabelled_suites_keep_the_profile_path_component() -> None:
    path = suite_run._run_output_dir(
        target={"id": "t1"},
        profile=L1,
        repeat=2,
        defaults={"output_dir": "out"},
        suite_name="s",
    )
    assert path == Path("out/s/l1_goal_projection/t1/r02")


def _prepared_project(tmp_path: Path) -> Path:
    from core.easycrypt.eval_source_prep import prepare_eval_source

    project = tmp_path / "repo"
    task = project / "task"
    task.mkdir(parents=True)
    target = task / "Target.ec"
    target.write_text(
        "lemma helper : true.\nproof.\n  trivial.\nqed.\n\n"
        "lemma target : true.\nproof.\n  trivial.\nqed.\n",
        encoding="utf-8",
    )
    (project / "easycrypt-src" / "theories").mkdir(parents=True)
    prepare_eval_source(
        source_file=target,
        target_lemma="target",
        output_dir=project / "out",
        copy_root=task,
        strip_proofs=True,
    )
    return project


def test_source_navigation_binds_the_arm_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from workflow.proof_tool.easycrypt_source_resource import (
        SOURCE_RESOURCE_MANIFEST_ENV,
    )

    project = _prepared_project(tmp_path)
    monkeypatch.chdir(project)
    cmd = [
        "python", "--file", "out/source/task/Target.ec", "--lemma", "target",
        "--include-dir", "easycrypt-src/theories",
    ]
    env: dict[str, str] = {}
    ok, reason = suite_run._enable_source_navigation(
        cmd, env, source_manifest=Path("out/source_manifest.json")
    )
    assert ok, reason
    assert env[SOURCE_RESOURCE_MANIFEST_ENV] == "out/source_manifest.json"

    wrong_lemma = [*cmd[:4], "helper", *cmd[5:]]
    env = {}
    ok, _reason = suite_run._enable_source_navigation(
        wrong_lemma, env, source_manifest=Path("out/source_manifest.json")
    )
    assert not ok
    assert SOURCE_RESOURCE_MANIFEST_ENV not in env

    ok, _reason = suite_run._enable_source_navigation(
        cmd, {}, source_manifest=Path("out/missing.json")
    )
    assert not ok


def test_inherited_source_manifest_never_reaches_an_arm(tmp_path: Path) -> None:
    from workflow.proof_tool.easycrypt_source_resource import (
        SOURCE_RESOURCE_MANIFEST_ENV,
    )

    inherited = {SOURCE_RESOURCE_MANIFEST_ENV: "/elsewhere/source_manifest.json"}
    env = dict(inherited)
    assert suite_run._bind_source_navigation(
        [], env, enabled=False, source_manifest=tmp_path / "m.json"
    ) is None
    assert SOURCE_RESOURCE_MANIFEST_ENV not in env

    env = dict(inherited)
    ok, reason = suite_run._bind_source_navigation(
        [], env, enabled=True, source_manifest=tmp_path / "missing.json"
    )
    assert not ok and "missing" in reason
    assert SOURCE_RESOURCE_MANIFEST_ENV not in env
