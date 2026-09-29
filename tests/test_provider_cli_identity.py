"""The agent CLI's version is recorded per run, mirroring the pinned
EasyCrypt identity: harness-version drift is a measurement confound and has
produced live failures (Claude system-subtype events, Codex alpha shapes)."""

from __future__ import annotations

import subprocess

import _pathsetup  # noqa: F401  (repo root on sys.path)

from workflow.provider import provider_sessions as runtime_module
from workflow.provider.provider_sessions import provider_cli_identity


def _clear_cache():
    runtime_module._PROVIDER_CLI_IDENTITY_CACHE.clear()


def test_identity_captures_first_version_line(monkeypatch):
    _clear_cache()

    def fake_run(argv, **kwargs):
        assert argv[-1] == "--version"
        return subprocess.CompletedProcess(
            argv, 0, stdout="codex-cli 0.148.0-alpha.15\nextra\n", stderr=""
        )

    monkeypatch.setattr(runtime_module.subprocess, "run", fake_run)
    identity = provider_cli_identity("codex")
    assert identity["version"] == "codex-cli 0.148.0-alpha.15"
    assert identity["agent_backend"] == "codex"
    assert identity["binary"]
    _clear_cache()


def test_identity_probe_failure_never_raises(monkeypatch):
    _clear_cache()

    def fake_run(argv, **kwargs):
        raise FileNotFoundError("no such binary")

    monkeypatch.setattr(runtime_module.subprocess, "run", fake_run)
    identity = provider_cli_identity("claude")
    assert identity["version"].startswith("unknown (FileNotFoundError")
    _clear_cache()


def test_identity_is_cached_per_backend(monkeypatch):
    _clear_cache()
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="v1\n", stderr="")

    monkeypatch.setattr(runtime_module.subprocess, "run", fake_run)
    provider_cli_identity("codex")
    provider_cli_identity("codex")
    assert len(calls) == 1
    _clear_cache()
