"""Provider launch contracts for the managed proof tool."""
from __future__ import annotations

from pathlib import Path

import pytest

from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract
from workflow.proof_tool.proof_tool_launch import (
    CodexCapabilities,
    ProofMcpLaunchSpec,
    ProofToolTimingBudget,
    ProviderCapabilityError,
    codex_feature_disable_args,
    discover_codex_capabilities,
    outer_codex_feature_disable_args,
    render_claude_mcp_config,
    render_codex_mcp_overrides,
)


def _spec(tmp_path: Path) -> ProofMcpLaunchSpec:
    return ProofMcpLaunchSpec(
        manifest=resolve_proof_tool_contract(None),
        endpoint_host="127.0.0.1",
        endpoint_port=43210,
        endpoint_token="private-token",
        private_dir=tmp_path / "private",
        timing=ProofToolTimingBudget.from_manager_budget(600),
        python_executable="/managed/python",
    )


def test_provider_renderers_consume_the_same_neutral_spec(tmp_path: Path) -> None:
    spec = _spec(tmp_path)

    claude = render_claude_mcp_config(spec, launch_id="launch-1")
    codex = render_codex_mcp_overrides(spec, launch_id="launch-1")

    server = claude["mcpServers"][spec.manifest.identity.server]
    assert server["alwaysLoad"] is True
    assert server["command"] == "/managed/python"
    assert "--launch-id" in server["args"]
    assert "launch-1" in server["args"]
    assert any(
        value.startswith("mcp_servers.proof_node_manager.command=")
        for value in codex
    )
    assert any(
        'enabled_tools=["submit_proof_intent"]' in value
        for value in codex
    )
    assert any("launch-1" in value for value in codex)


def test_codex_enables_manager_source_tool_from_the_same_manifest(
    tmp_path: Path,
) -> None:
    base = _spec(tmp_path)
    spec = ProofMcpLaunchSpec(
        manifest=resolve_proof_tool_contract(None, source_navigation_enabled=True),
        endpoint_host=base.endpoint_host,
        endpoint_port=base.endpoint_port,
        endpoint_token=base.endpoint_token,
        private_dir=base.private_dir,
        timing=base.timing,
        python_executable=base.python_executable,
    )

    codex = render_codex_mcp_overrides(spec, launch_id="launch-source")

    assert any(
        'enabled_tools=["submit_proof_intent", "read_easycrypt_source", '
        '"search_easycrypt_source", "resolve_easycrypt_declaration"]'
        in value
        for value in codex
    )


def test_leading_dash_token_is_one_unambiguous_argument(tmp_path: Path) -> None:
    base = _spec(tmp_path)
    spec = ProofMcpLaunchSpec(
        manifest=base.manifest,
        endpoint_host=base.endpoint_host,
        endpoint_port=base.endpoint_port,
        endpoint_token="-leading-dash-token",
        private_dir=base.private_dir,
        timing=base.timing,
        python_executable=base.python_executable,
    )

    _command, arguments, _env = spec.child_command("launch-1")

    assert "--token=-leading-dash-token" in arguments
    assert "--token" not in arguments


def test_node_deadline_is_forwarded_to_the_stdio_adapter(tmp_path: Path) -> None:
    base = _spec(tmp_path)
    spec = ProofMcpLaunchSpec(
        manifest=base.manifest,
        endpoint_host=base.endpoint_host,
        endpoint_port=base.endpoint_port,
        endpoint_token=base.endpoint_token,
        private_dir=base.private_dir,
        timing=base.timing,
        node_deadline_epoch=12345.5,
        python_executable=base.python_executable,
    )

    _command, arguments, _env = spec.child_command("launch-1")

    option = arguments.index("--node-deadline-epoch")
    assert arguments[option + 1] == "12345.5"


def test_timing_budget_has_one_ordered_owner() -> None:
    budget = ProofToolTimingBudget.from_manager_budget(
        100,
        startup_seconds=20,
        transport_margin_seconds=7,
    )
    assert budget.manager_operation_seconds == 100
    assert budget.endpoint_read_seconds == 107
    assert budget.provider_tool_seconds == 114

    with pytest.raises(ValueError, match="manager < endpoint < provider"):
        ProofToolTimingBudget(
            startup_seconds=20,
            manager_operation_seconds=100,
            endpoint_read_seconds=90,
            provider_tool_seconds=120,
        )


def _capabilities(*, features: set[str], missing_json: bool = False) -> CodexCapabilities:
    exec_options = {
        "--config",
        "--disable",
        "--ignore-user-config",
        "--json",
        "--sandbox",
        "--strict-config",
    }
    if missing_json:
        exec_options.remove("--json")
    return CodexCapabilities(
        binary="codex",
        version="codex-cli test",
        features=frozenset(features),
        exec_options=frozenset(exec_options),
        resume_options=frozenset({
            "--config",
            "--disable",
            "--ignore-user-config",
            "--json",
            "--strict-config",
        }),
    )


def test_codex_optional_features_are_negotiated_not_version_pinned() -> None:
    capabilities = _capabilities(features={"shell_tool", "apps"})

    assert codex_feature_disable_args(capabilities) == [
        "--disable",
        "apps",
        "--disable",
        "shell_tool",
    ]

    assert outer_codex_feature_disable_args(capabilities) == [
        "--disable",
        "apps",
    ]


def test_missing_required_codex_capability_fails_before_launch() -> None:
    capabilities = _capabilities(features=set(), missing_json=True)

    with pytest.raises(ProviderCapabilityError, match="--json"):
        capabilities.require_managed_proof_node()


def test_outer_codex_capabilities_are_role_specific() -> None:
    base = _capabilities(features=set())
    outer = CodexCapabilities(
        binary=base.binary,
        version=base.version,
        features=base.features,
        exec_options=base.exec_options
        | frozenset({"--cd", "--color", "--ephemeral", "--ignore-rules"}),
        resume_options=frozenset(),
    )
    outer.require_outer_construction_agent()
    with pytest.raises(ProviderCapabilityError, match="--ephemeral"):
        base.require_outer_construction_agent()


def test_outer_only_codex_discovery_does_not_probe_resume(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_probe(_binary, arguments, _timeout):
        calls.append(arguments)
        if arguments == ("--version",):
            return "codex-cli test"
        if arguments == ("exec", "--help"):
            return " ".join({
                "--cd",
                "--color",
                "--config",
                "--disable",
                "--ephemeral",
                "--ignore-rules",
                "--ignore-user-config",
                "--json",
                "--sandbox",
                "--strict-config",
            })
        if arguments == ("features", "list"):
            return "apps false"
        raise AssertionError(f"unexpected probe: {arguments}")

    monkeypatch.setattr(
        "workflow.proof_tool.proof_tool_launch._probe",
        fake_probe,
    )
    capabilities = discover_codex_capabilities("codex", probe_resume=False)
    capabilities.require_outer_construction_agent()
    assert ("exec", "resume", "--help") not in calls
