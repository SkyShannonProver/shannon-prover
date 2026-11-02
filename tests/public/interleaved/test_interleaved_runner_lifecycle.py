"""Run-level lifecycle of the interleaved runner, with no model or EasyCrypt."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from tests.helpers.interleaved import demo_context, rebind, reference
from workflow.interleaved import runner
from workflow.interleaved.runtime import ProjectContext


PROJECTS = ("reference", "demo")


def _context(project: str, root: Path) -> ProjectContext:
    if project == "demo":
        return demo_context(root)
    return rebind(reference(), root)


def _offline_runner(
    set_attr: Callable[[Any, str, Any], None],
    root: Path,
    *,
    project: str = "reference",
    preflight_returncode: int = 0,
    executable: str | None = "/bin/echo",
    outer_code: str = "pass",
) -> ProjectContext:
    """Replace every external effect of ``runner.main`` below ``root``.

    Each replaced step appends its name to ``root/calls.log``. Returns the
    project context the runner receives.
    """

    context = _context(project, root)
    log = root / "calls.log"

    def record(name: str) -> None:
        with log.open("a", encoding="utf-8") as stream:
            stream.write(name + "\n")

    context.target.parent.mkdir(parents=True, exist_ok=True)
    context.target.write_text(
        f"lemma {context.project.final_lemma} : true.\n", encoding="utf-8",
    )
    if context.project.prompt_file:
        prompt = root / context.project.prompt_file
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text(
            "Run {{RUN_DIR}}.\n{{CONTINUATION_CONTEXT}}\n", encoding="utf-8",
        )

    def verifier(
        _ctx: ProjectContext, mode: str, _output: Path,
    ) -> subprocess.CompletedProcess[str]:
        record(f"verifier:{mode}")
        code = preflight_returncode if mode == "preflight" else 1
        return subprocess.CompletedProcess([mode], code, stdout="", stderr="")

    def identity(*, profile: Any, executable: str, version: str) -> dict[str, str]:
        return {
            "agent_backend": profile.backend,
            "model": profile.model,
            "binary": executable,
            "resolved_path": executable,
            "binary_sha256": "a" * 64,
            "version": "test",
        }

    def source_preflight(_ctx: ProjectContext, *, run_dir: Path) -> dict[str, Any]:
        record("source_preflight")
        return {"passed": True}

    def cancel(_ctx: ProjectContext, **_kwargs: Any) -> dict[str, Any]:
        record("cancel")
        return {"schema_version": 1, "cancelled": [], "forcibly_killed": []}

    set_attr(runner, "require_official_start", lambda _ctx: "0" * 40)
    set_attr(runner, "invoke_verifier", verifier)
    set_attr(runner, "toolchain_fingerprint", lambda: {})
    # Only the provider CLIs exist. Any other program the runner looks up,
    # such as macOS-only caffeinate, is absent on every platform.
    provider_binaries = {
        profile.binary_name for profile in runner.load_agent_profiles()[0].values()
    }
    set_attr(runner.shutil, "which", lambda name, *_args, **_kwargs: (
        executable if name in provider_binaries else None
    ))
    set_attr(runner, "provider_runtime_identity", identity)
    set_attr(runner, "codex_auth_summary", lambda *_args, **_kwargs: {
        "checked": True, "exit_code": 0, "logged_in": True, "auth_method": "chatgpt",
    })
    set_attr(runner, "discover_codex_capabilities", lambda *_args, **_kwargs: SimpleNamespace(
        features=frozenset(),
        require_outer_construction_agent=lambda: None,
        require_managed_proof_node=lambda: None,
        to_dict=lambda: {},
    ))
    set_attr(runner, "provider_cli_identity", lambda backend: {
        "agent_backend": backend,
        "binary": str(executable),
        "resolved_path": str(executable),
        "binary_sha256": "a" * 64,
        "version": "test",
    })
    set_attr(runner, "source_bundle_preflight", source_preflight)
    set_attr(runner, "sha256", lambda _path: "0" * 64)
    set_attr(runner, "build_outer_command", lambda *_args, **_kwargs: (
        [sys.executable, "-c", outer_code], False,
    ))
    set_attr(runner, "cancel_jobs_in_run", cancel)
    set_attr(runner, "checkout_integrity_violations", lambda *_args, **_kwargs: [])
    set_attr(runner, "public_job_summary", lambda *_args: {})
    set_attr(runner, "private_job_records", lambda _run_dir: [])
    return context


def _manifest(context: ProjectContext) -> dict[str, Any]:
    (path,) = (context.root / context.project.artifact_root).glob("*/manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _calls(root: Path) -> list[str]:
    log = root / "calls.log"
    return log.read_text(encoding="utf-8").splitlines() if log.is_file() else []


@pytest.mark.parametrize("project", PROJECTS)
def test_failed_verifier_preflight_still_leaves_a_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    project: str,
) -> None:
    context = _offline_runner(
        monkeypatch.setattr, tmp_path, project=project, preflight_returncode=1,
    )

    with pytest.raises(SystemExit, match="preflight verification failed"):
        runner.main([], context=context)

    manifest = _manifest(context)
    assert manifest["status"] == "preflight_failed"
    assert manifest["runner_error"] == "preflight verification failed"
    assert manifest["model_process_launched"] is False
    assert manifest["finished_at"]


@pytest.mark.parametrize("project", PROJECTS)
def test_missing_provider_fails_before_the_source_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    project: str,
) -> None:
    context = _offline_runner(
        monkeypatch.setattr, tmp_path, project=project, executable=None,
    )

    with pytest.raises(SystemExit, match="not installed"):
        runner.main([], context=context)

    assert "source_preflight" not in _calls(tmp_path)
    manifest = _manifest(context)
    assert manifest["status"] == "preflight_provider_failed"
    assert manifest["provider_runtimes"]["codex"]["version"] == "unavailable"


def test_termination_signal_takes_the_ctrl_c_path_once() -> None:
    termination = runner.TerminationSignals()
    previous = signal.getsignal(signal.SIGTERM)
    termination.install()
    try:
        with pytest.raises(KeyboardInterrupt):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(5)
        # A second signal must not abort the cleanup the first one started.
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(0.1)
        assert termination.received == ["SIGTERM", "SIGTERM"]
    finally:
        termination.restore()
    assert signal.getsignal(signal.SIGTERM) == previous


def test_termination_signals_keep_a_nohup_ignored_sighup() -> None:
    original = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    termination = runner.TerminationSignals()
    try:
        termination.install()
        assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
    finally:
        termination.restore()
        signal.signal(signal.SIGHUP, original)


_SIGNALLED_RUNNER = """
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("lifecycle", sys.argv[1])
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)
context = lifecycle._offline_runner(
    setattr, Path(sys.argv[2]), project=sys.argv[4], outer_code=sys.argv[3],
)
sys.exit(lifecycle.runner.main(["--timeout-seconds", "120"], context=context))
"""


@pytest.mark.parametrize("project", PROJECTS)
def test_sigterm_to_the_runner_still_cancels_jobs_and_records_a_verdict(
    tmp_path: Path,
    project: str,
) -> None:
    # The outer agent signals its parent, the runner, the way `kill`, a
    # timeout wrapper or a CI cancel would.
    outer = (
        "import os, signal, time\n"
        "os.kill(os.getppid(), signal.SIGTERM)\n"
        "time.sleep(60)\n"
    )
    root = Path(__file__).resolve().parents[3]
    child = subprocess.run(
        [
            sys.executable, "-c", _SIGNALLED_RUNNER, __file__, str(tmp_path),
            outer, project,
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )

    output = (
        f"exit {child.returncode}\nstdout:\n{child.stdout[-2000:]}"
        f"\nstderr:\n{child.stderr[-6000:]}"
    )
    # Exit 1 alone is ambiguous: an uncaught exception also exits 1.
    assert "Traceback" not in child.stderr, output
    assert child.returncode == 1, output
    assert _calls(tmp_path) == [
        "verifier:preflight", "source_preflight", "cancel", "verifier:final",
    ], output
    manifest = _manifest(_context(project, tmp_path))
    assert manifest["status"] == "not_proved", output
    assert manifest["interrupted"] is True, output
    assert manifest["termination_signals"] == ["SIGTERM"], output


def test_second_project_runs_under_its_own_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _offline_runner(monkeypatch.setattr, tmp_path, project="demo")

    assert runner.main(["--timeout-seconds", "120"], context=context) == 1

    manifest = _manifest(context)
    assert manifest["project_contract"] == "projects/demo/interleaved_project.json"
    assert manifest["project_identity_sha256"] == context.project.identity_sha256
    assert manifest["run_directory"].startswith("artifacts/demo-interleaved/official_")
    assert manifest["reference_answer_confinement"] is False
    assert manifest["inner_shannon_agent"]["job_scheduler"]["max_parallel"] == 3
    assert manifest["outer_agent"]["model_visible_task_budget_seconds"] == 3600
    # The stub outer agent exits at once with code 0.
    assert manifest["status"] == "premature_agent_stop"
    rendered = (tmp_path / manifest["run_directory"] / "prompt.rendered.md").read_text(
        encoding="utf-8"
    )
    assert "Complete `Main` in `projects/demo/Target.ec`" in rendered
    assert "artifacts/demo-interleaved/official_" in rendered
    assert _calls(tmp_path) == [
        "verifier:preflight", "source_preflight", "cancel", "verifier:final",
    ]
