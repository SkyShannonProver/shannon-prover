from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from core.env_loader import KNOWN_ENV_FLAGS
from workflow.eval_agent_confinement import (
    EVAL_CONFINEMENT_MANIFEST_ENV,
    EVAL_CONFINEMENT_REQUIRED_ENV,
    EvalAgentConfinement,
    EvalAgentConfinementError,
)


def test_confinement_environment_knobs_are_registered() -> None:
    assert EVAL_CONFINEMENT_MANIFEST_ENV in KNOWN_ENV_FLAGS
    assert EVAL_CONFINEMENT_REQUIRED_ENV in KNOWN_ENV_FLAGS


@pytest.fixture(autouse=True)
def _bubblewrap_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The argv contract is unit-testable on hosts without Bubblewrap."""

    fake = tmp_path / "bwrap"
    fake.write_text("fixture\n", encoding="utf-8")
    real_which = shutil.which
    monkeypatch.setattr(
        "workflow.eval_agent_confinement.shutil.which",
        lambda name: str(fake) if name == "bwrap" else real_which(name),
    )


def _fixture(tmp_path: Path, *, target_lemma: str = "target") -> tuple[
    Path, Path, Path, Path, dict[str, str]
]:
    project = tmp_path / "repo"
    for name in ("core", "workflow", "easycrypt-src", "knowledge"):
        (project / name).mkdir(parents=True, exist_ok=True)
    legacy_run = project / "workflow" / "runs" / "old"
    legacy_run.mkdir(parents=True)
    (legacy_run / "proof_so_far.md").write_text(
        "old proof must be hidden\n", encoding="utf-8"
    )
    (project / "AGENTS.md").write_text("fixture\n", encoding="utf-8")
    (project / "eval" / "examples").mkdir(parents=True)
    (project / "eval" / "examples" / "Target.ec").write_text(
        "lemma target : true. proof. trivial. qed.\n", encoding="utf-8"
    )
    output = project / "artifacts" / "suite" / "l4" / "target" / "r01"
    isolated_root = output / "source"
    isolated_root.mkdir(parents=True)
    isolated_file = isolated_root / "Target.ec"
    isolated_file.write_text(
        "lemma target : true. proof. admit. qed.\n", encoding="utf-8"
    )
    manifest = output / "source_manifest.json"
    manifest.write_text(
        json.dumps({
            "schema_version": 1,
            "kind": "eval_source_prep",
            "source_contract": "proof_stripped_project",
            "original_file": "eval/examples/Target.ec",
            "copy_root": "eval/examples/Target.ec",
            "isolated_file": str(isolated_file),
            "isolated_root": str(isolated_root),
            "target_lemma": target_lemma,
            "strip_proofs": True,
        }),
        encoding="utf-8",
    )
    node_memory = output / "run" / "iteration_1" / "node_memory" / "Tree_0_0"
    node_memory.mkdir(parents=True)
    private = output / "run" / "iteration_1" / "runtime_private" / "Tree_0_0"
    env = {
        EVAL_CONFINEMENT_MANIFEST_ENV: str(manifest),
        EVAL_CONFINEMENT_REQUIRED_ENV: "1",
    }
    return project, isolated_file, node_memory, private, env


def test_confinement_requires_proof_stripped_matching_source(tmp_path: Path) -> None:
    project, isolated, memory, private, env = _fixture(tmp_path)
    spec = EvalAgentConfinement.from_environment(
        project_root=project,
        source_file=isolated,
        target_lemma="target",
        node_memory_dir=memory,
        private_dir=private,
        environ=env,
    )
    assert spec is not None
    assert spec.isolated_file == isolated.resolve()

    with pytest.raises(EvalAgentConfinementError, match="target lemma"):
        EvalAgentConfinement.from_environment(
            project_root=project,
            source_file=isolated,
            target_lemma="different",
            node_memory_dir=memory,
            private_dir=private,
            environ=env,
        )


def test_required_confinement_without_manifest_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(EvalAgentConfinementError, match="no source manifest"):
        EvalAgentConfinement.from_environment(
            project_root=tmp_path,
            source_file="Target.ec",
            target_lemma="target",
            node_memory_dir=tmp_path / "memory",
            private_dir=tmp_path / "private",
            environ={EVAL_CONFINEMENT_REQUIRED_ENV: "1"},
        )


def test_confinement_rejects_unstripped_project_include(tmp_path: Path) -> None:
    project, isolated, memory, private, env = _fixture(tmp_path)

    with pytest.raises(EvalAgentConfinementError, match="include directory"):
        EvalAgentConfinement.from_environment(
            project_root=project,
            source_file=isolated,
            target_lemma="target",
            node_memory_dir=memory,
            private_dir=private,
            include_dir=project / "eval" / "examples",
            environ=env,
        )


def test_bubblewrap_view_selects_only_current_source_and_node_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, isolated, memory, private, env = _fixture(tmp_path)
    runtime_prefix = project / ".venv"
    runtime_prefix.mkdir()
    (runtime_prefix / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    monkeypatch.setattr("workflow.eval_agent_confinement.sys.prefix", str(runtime_prefix))
    spec = EvalAgentConfinement.from_environment(
        project_root=project,
        source_file=isolated,
        target_lemma="target",
        node_memory_dir=memory,
        private_dir=private,
        environ=env,
    )
    assert spec is not None
    command = spec.wrap_command(["/usr/bin/true"], agent_backend="codex")

    assert command[0].endswith("bwrap")
    assert ["--ro-bind", "/", "/"] not in [
        command[index:index + 3] for index in range(len(command) - 2)
    ]
    assert str(isolated.parent.resolve()) in command
    assert str(memory.resolve()) in command
    assert str(private.resolve()) in command
    assert str(runtime_prefix.resolve()) in command
    assert ["--tmpfs", str((project / "workflow" / "runs").resolve())] in [
        command[index:index + 2] for index in range(len(command) - 1)
    ]
    assert str((project / "eval" / "examples").resolve()) not in command
    mounted_sources = {
        command[index + 1]
        for index, item in enumerate(command[:-2])
        if item in {"--bind", "--ro-bind"}
    }
    assert str((project / "artifacts").resolve()) not in mounted_sources
    assert command[-2:] == ["--", str(Path("/usr/bin/true").resolve())]

    audit = spec.audit_record({
        "probe_status": "passed",
        "original_repository_visible": False,
        "sibling_worktrees_visible": False,
        "prior_agent_transcripts_visible": False,
        "host_tmp_visible": False,
    })
    assert audit["schema_version"] == 2
    assert audit["original_repository_visible"] is False
    assert audit["sibling_worktrees_visible"] is False
    assert audit["prior_agent_transcripts_visible"] is False


def test_target_below_easycrypt_src_does_not_reexpose_original_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, isolated, memory, private, env = _fixture(tmp_path)
    original = project / "easycrypt-src" / "tests" / "Target.ec"
    original.parent.mkdir(parents=True)
    original.write_text(
        "lemma target : true. proof. trivial. qed.\n",
        encoding="utf-8",
    )
    theories = project / "easycrypt-src" / "theories"
    theories.mkdir()
    manifest_path = Path(env[EVAL_CONFINEMENT_MANIFEST_ENV])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["original_file"] = "easycrypt-src/tests/Target.ec"
    manifest["copy_root"] = "easycrypt-src/tests/Target.ec"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    runtime_prefix = project / ".venv"
    runtime_prefix.mkdir()
    (runtime_prefix / "pyvenv.cfg").write_text(
        "home = /usr/bin\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "workflow.eval_agent_confinement.sys.prefix",
        str(runtime_prefix),
    )
    spec = EvalAgentConfinement.from_environment(
        project_root=project,
        source_file=isolated,
        target_lemma="target",
        node_memory_dir=memory,
        private_dir=private,
        include_dir=theories,
        environ=env,
    )
    assert spec is not None
    command = spec.wrap_command(["/usr/bin/true"], agent_backend="codex")
    mounted_sources = {
        command[index + 1]
        for index, item in enumerate(command[:-2])
        if item in {"--bind", "--ro-bind"}
    }

    assert str((project / "easycrypt-src").resolve()) not in mounted_sources
    assert str(theories.resolve()) in mounted_sources
    assert str(original.resolve()) not in mounted_sources


def test_confinement_refuses_runtime_prefix_containing_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, isolated, memory, private, env = _fixture(tmp_path)
    (project / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    monkeypatch.setattr("workflow.eval_agent_confinement.sys.prefix", str(project))
    spec = EvalAgentConfinement.from_environment(
        project_root=project,
        source_file=isolated,
        target_lemma="target",
        node_memory_dir=memory,
        private_dir=private,
        environ=env,
    )
    assert spec is not None

    with pytest.raises(EvalAgentConfinementError, match="contains the evaluation project"):
        spec.wrap_command(["/usr/bin/true"], agent_backend="codex")


def test_codex_non_secret_client_state_is_private_and_writable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, isolated, memory, private, env = _fixture(tmp_path)
    host_home = tmp_path / "host-home"
    host_codex = host_home / ".codex"
    host_codex.mkdir(parents=True)
    (host_codex / "auth.json").write_text("secret\n", encoding="utf-8")
    (host_codex / "installation_id").write_text("install-id\n", encoding="utf-8")
    (host_codex / "models_cache.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr("workflow.eval_agent_confinement.Path.home", lambda: host_home)

    spec = EvalAgentConfinement.from_environment(
        project_root=project,
        source_file=isolated,
        target_lemma="target",
        node_memory_dir=memory,
        private_dir=private,
        environ=env,
    )
    assert spec is not None
    command = spec.wrap_command(["/usr/bin/true"], agent_backend="codex")
    private_codex = private / "agent_state" / "codex_home"

    assert (private_codex / "installation_id").read_text(encoding="utf-8") == (
        "install-id\n"
    )
    assert (private_codex / "models_cache.json").read_text(encoding="utf-8") == "{}\n"
    assert (private_codex / "auth.json").read_text(encoding="utf-8") == ""

    read_only_targets = {
        command[index + 2]
        for index, item in enumerate(command[:-2])
        if item == "--ro-bind"
    }
    assert str(host_codex / "auth.json") in read_only_targets
    assert str(host_codex / "installation_id") not in read_only_targets
    assert str(host_codex / "models_cache.json") not in read_only_targets


def test_confinement_probe_is_fail_closed(monkeypatch, tmp_path: Path) -> None:
    project, isolated, memory, private, env = _fixture(tmp_path)
    spec = EvalAgentConfinement.from_environment(
        project_root=project,
        source_file=isolated,
        target_lemma="target",
        node_memory_dir=memory,
        private_dir=private,
        environ=env,
    )
    assert spec is not None

    class _Completed:
        returncode = 1
        stdout = ""
        stderr = "namespace denied"

    monkeypatch.setattr(
        "workflow.eval_agent_confinement.subprocess.run",
        lambda *args, **kwargs: _Completed(),
    )
    with pytest.raises(EvalAgentConfinementError, match="namespace denied"):
        spec.probe(agent_backend="codex")


def test_confinement_audit_is_derived_from_probe_result(
    monkeypatch, tmp_path: Path,
) -> None:
    project, isolated, memory, private, env = _fixture(tmp_path)
    spec = EvalAgentConfinement.from_environment(
        project_root=project,
        source_file=isolated,
        target_lemma="target",
        node_memory_dir=memory,
        private_dir=private,
        environ=env,
    )
    assert spec is not None

    class _Completed:
        returncode = 0
        stderr = ""
        stdout = json.dumps({
            "probe_status": "passed",
            "allowed_paths_readable": True,
            "original_repository_visible": False,
            "sibling_worktrees_visible": False,
            "prior_agent_transcripts_visible": False,
            "host_tmp_visible": False,
        })

    monkeypatch.setattr(
        "workflow.eval_agent_confinement.subprocess.run",
        lambda *args, **kwargs: _Completed(),
    )
    result = spec.probe(agent_backend="codex")
    audit = spec.audit_record(result)

    assert audit["probe_status"] == "passed"
    assert audit["original_repository_visible"] is False
    assert audit["probe_path_counts"]["original_repository_visible"] >= 1
    assert "probe_paths" not in audit


def test_confinement_audit_requires_observed_negative_probe(tmp_path: Path) -> None:
    project, isolated, memory, private, env = _fixture(tmp_path)
    spec = EvalAgentConfinement.from_environment(
        project_root=project,
        source_file=isolated,
        target_lemma="target",
        node_memory_dir=memory,
        private_dir=private,
        environ=env,
    )
    assert spec is not None

    with pytest.raises(EvalAgentConfinementError, match="negative visibility"):
        spec.audit_record({
            "probe_status": "passed",
            "original_repository_visible": True,
            "sibling_worktrees_visible": False,
            "prior_agent_transcripts_visible": False,
            "host_tmp_visible": False,
        })
