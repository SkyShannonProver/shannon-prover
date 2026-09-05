"""Provider-neutral proof-tool launch specification and capability adapters.

The runtime resolves one :class:`ProofMcpLaunchSpec` from the manager endpoint.
Provider adapters render that object directly; Codex never parses a Claude
configuration file and no provider owns the proof-tool identity.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflow.proof_tool.proof_tool_contract import ProofToolContractManifest
from workflow.proof_management.repl_session import replay_aggregate_budget_seconds


class ProviderCapabilityError(RuntimeError):
    """Raised before model launch when a required provider capability is absent."""


@dataclass(frozen=True)
class ProofToolTimingBudget:
    """One ordered timeout contract for a complete proof-tool request."""

    startup_seconds: float
    manager_operation_seconds: float
    endpoint_read_seconds: float
    provider_tool_seconds: float

    def __post_init__(self) -> None:
        values = (
            self.startup_seconds,
            self.manager_operation_seconds,
            self.endpoint_read_seconds,
            self.provider_tool_seconds,
        )
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError("proof-tool timing values must be finite and positive")
        if not (
            self.manager_operation_seconds < self.endpoint_read_seconds
            < self.provider_tool_seconds
        ):
            raise ValueError(
                "proof-tool timing must satisfy manager < endpoint < provider"
            )

    @classmethod
    def from_manager_budget(
        cls,
        manager_operation_seconds: float,
        *,
        startup_seconds: float | None = None,
        transport_margin_seconds: float = 30.0,
    ) -> "ProofToolTimingBudget":
        manager = float(manager_operation_seconds)
        margin = max(1.0, float(transport_margin_seconds))
        startup = float(
            startup_seconds
            if startup_seconds is not None
            else os.environ.get("SHANNON_MCP_READY_TIMEOUT_S", "75")
        )
        return cls(
            startup_seconds=startup,
            manager_operation_seconds=manager,
            endpoint_read_seconds=manager + margin,
            provider_tool_seconds=manager + 2 * margin,
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "startup_seconds": self.startup_seconds,
            "manager_operation_seconds": self.manager_operation_seconds,
            "endpoint_read_seconds": self.endpoint_read_seconds,
            "provider_tool_seconds": self.provider_tool_seconds,
        }


def proof_tool_timing_for_prefix(prefix_length: int) -> ProofToolTimingBudget:
    """Resolve the one request budget from the session replay ceiling.

    The extra phase allowance covers authoritative refresh, turn-spine binding,
    compiler work, memory persistence, and rendering after the slowest replay.
    A single explicit override replaces the complete manager-operation budget;
    transport/provider ceilings are still derived and cannot drift below it.
    """

    replay_seconds = replay_aggregate_budget_seconds(prefix_length)
    raw = os.environ.get("SHANNON_MANAGER_OPERATION_TIMEOUT_S", "").strip()
    if raw:
        try:
            manager_seconds = float(raw)
        except ValueError as exc:
            raise ValueError(
                "SHANNON_MANAGER_OPERATION_TIMEOUT_S must be numeric"
            ) from exc
    else:
        manager_seconds = replay_seconds + 600.0
    if manager_seconds < replay_seconds:
        raise ValueError(
            "manager operation timeout cannot be below the replay budget"
        )
    return ProofToolTimingBudget.from_manager_budget(manager_seconds)


@dataclass(frozen=True)
class ProofMcpLaunchSpec:
    """Provider-independent description of the private stdio MCP child."""

    manifest: ProofToolContractManifest
    endpoint_host: str
    endpoint_port: int
    endpoint_token: str
    private_dir: Path
    timing: ProofToolTimingBudget
    node_deadline_epoch: float | None = None
    python_executable: str = sys.executable
    adapter_module: str = "workflow.proof_tool.proof_node_mcp_server"

    def __post_init__(self) -> None:
        if not self.endpoint_host:
            raise ValueError("proof-tool endpoint host must be non-empty")
        if self.endpoint_port <= 0:
            raise ValueError("proof-tool endpoint port must be positive")
        if not self.endpoint_token:
            raise ValueError("proof-tool endpoint token must be non-empty")
        if self.node_deadline_epoch is not None:
            deadline = float(self.node_deadline_epoch)
            if not math.isfinite(deadline) or deadline <= 0:
                raise ValueError(
                    "proof-tool node deadline must be finite and positive"
                )
            object.__setattr__(self, "node_deadline_epoch", deadline)

    def child_command(self, launch_id: str) -> tuple[str, tuple[str, ...], dict[str, str]]:
        """Return command, arguments, and environment for one invocation."""

        invocation = _launch_id(launch_id)
        arguments = (
            "-m",
            self.adapter_module,
            "--host",
            self.endpoint_host,
            "--port",
            str(self.endpoint_port),
            # A urlsafe bearer token may legitimately begin with ``-``. Keep
            # the option and value in one argv element so argparse cannot
            # reinterpret the secret as another flag.
            f"--token={self.endpoint_token}",
            "--launch-id",
            invocation,
            "--manifest-json",
            json.dumps(
                self.manifest.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "--manager-timeout-seconds",
            str(self.timing.manager_operation_seconds),
            "--endpoint-timeout-seconds",
            str(self.timing.endpoint_read_seconds),
            *(
                (
                    "--node-deadline-epoch",
                    str(self.node_deadline_epoch),
                )
                if self.node_deadline_epoch is not None
                else ()
            ),
        )
        # Repo root = two packages up (workflow/proof_tool/ -> workflow/ ->
        # root). The old parent.parent silently became workflow/ when this
        # module moved into its layer package, and every MCP child died on
        # import — caught live 2026-08-19, invisible to the smoke test because
        # it overrides PYTHONPATH itself.
        env = {"PYTHONPATH": str(Path(__file__).resolve().parents[2])}
        return self.python_executable, arguments, env


def render_claude_mcp_config(
    spec: ProofMcpLaunchSpec,
    *,
    launch_id: str,
) -> dict[str, Any]:
    command, arguments, env = spec.child_command(launch_id)
    return {
        "mcpServers": {
            spec.manifest.identity.server: {
                "type": "stdio",
                # Managed proof tools are the only legal proof-state channel.
                # Claude Code otherwise defers MCP tools behind ToolSearch and
                # starts --mcp-config servers asynchronously.  A proof node can
                # therefore reach its first model turn before this server is in
                # the deferred catalog; the model's exact ToolSearch then finds
                # nothing and exits without ever producing the invocation-bound
                # READY receipt.  Required manager tools must be eager.
                "alwaysLoad": True,
                "command": command,
                "args": list(arguments),
                "env": env,
            },
        },
    }


def render_codex_mcp_overrides(
    spec: ProofMcpLaunchSpec,
    *,
    launch_id: str,
) -> list[str]:
    """Render Codex overrides directly from the neutral launch spec."""

    command, arguments, env = spec.child_command(launch_id)
    prefix = f"mcp_servers.{spec.manifest.identity.server}"
    enabled_tools = json.dumps([
        identity.tool for identity in spec.manifest.tool_identities
    ])
    overrides = [
        f"{prefix}.command={_toml_string(command)}",
        f"{prefix}.args={json.dumps(list(arguments), ensure_ascii=False)}",
        f"{prefix}.required=true",
        f"{prefix}.enabled_tools={enabled_tools}",
        f"{prefix}.default_tools_approval_mode={_toml_string('approve')}",
        f"{prefix}.startup_timeout_sec={int(spec.timing.startup_seconds)}",
        f"{prefix}.tool_timeout_sec={int(spec.timing.provider_tool_seconds)}",
    ]
    for key, value in sorted(env.items()):
        overrides.append(f"{prefix}.env.{key}={_toml_string(value)}")
    return overrides


# These switches are optional ergonomics/defence-in-depth.  The authoritative
# boundary is the outer confinement, exact MCP allowlist, and event guard.
OPTIONAL_CODEX_DISABLED_FEATURES = (
    "apply_patch_freeform",
    "apply_patch_streaming_events",
    "apps",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "code_mode",
    "computer_use",
    "goals",
    "image_generation",
    "in_app_browser",
    "multi_agent",
    "multi_agent_v2",
    "plugins",
    "recommended_plugins",
    "remote_plugin",
    "shell_snapshot",
    "shell_tool",
    "skill_mcp_dependency_install",
    "skill_search",
    "standalone_web_search",
    "tool_suggest",
    "unified_exec",
    "unified_exec_zsh_fork",
    "view_image",
    "workspace_dependencies",
)

# The outer construction agent intentionally retains its local shell and patch
# tools.  Every non-construction feature is disabled from the same canonical
# list as the managed proof node so newly discovered provider features cannot
# drift between two hand-maintained policies.
OUTER_CODEX_RETAINED_FEATURES = frozenset({
    "apply_patch_freeform",
    "apply_patch_streaming_events",
    "shell_snapshot",
    "shell_tool",
    "unified_exec",
    "unified_exec_zsh_fork",
})


@dataclass(frozen=True)
class CodexCapabilities:
    """Capabilities discovered from one installed Codex binary."""

    binary: str
    version: str
    features: frozenset[str]
    exec_options: frozenset[str]
    resume_options: frozenset[str]

    @property
    def optional_disabled_features(self) -> tuple[str, ...]:
        return tuple(
            feature
            for feature in OPTIONAL_CODEX_DISABLED_FEATURES
            if feature in self.features
        )

    def require_managed_proof_node(self) -> None:
        required_exec = {
            "--config",
            "--disable",
            "--ignore-user-config",
            "--json",
            "--sandbox",
            "--strict-config",
        }
        required_resume = {
            "--config",
            "--disable",
            "--ignore-user-config",
            "--json",
            "--strict-config",
        }
        missing_exec = sorted(required_exec - self.exec_options)
        missing_resume = sorted(required_resume - self.resume_options)
        if missing_exec or missing_resume:
            pieces: list[str] = []
            if missing_exec:
                pieces.append("exec missing " + ", ".join(missing_exec))
            if missing_resume:
                pieces.append("resume missing " + ", ".join(missing_resume))
            raise ProviderCapabilityError(
                "installed Codex lacks required managed-proof capabilities: "
                + "; ".join(pieces)
            )

    def require_outer_construction_agent(self) -> None:
        required_exec = {
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
        }
        missing_exec = sorted(required_exec - self.exec_options)
        if missing_exec:
            raise ProviderCapabilityError(
                "installed Codex lacks required outer-agent capabilities: "
                + ", ".join(missing_exec)
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "binary": self.binary,
            "version": self.version,
            "features": sorted(self.features),
            "exec_options": sorted(self.exec_options),
            "resume_options": sorted(self.resume_options),
            "optional_disabled_features": list(self.optional_disabled_features),
        }


def discover_codex_capabilities(
    binary: str,
    *,
    timeout_seconds: float = 10.0,
    probe_resume: bool = True,
) -> CodexCapabilities:
    """Probe only the Codex surfaces required by the selected runtime roles."""

    version = _probe(binary, ("--version",), timeout_seconds).strip()
    exec_help = _probe(binary, ("exec", "--help"), timeout_seconds)
    resume_help = (
        _probe(binary, ("exec", "resume", "--help"), timeout_seconds)
        if probe_resume
        else ""
    )
    features_text = _probe(binary, ("features", "list"), timeout_seconds)
    capabilities = CodexCapabilities(
        binary=binary,
        version=version,
        features=frozenset(_feature_names(features_text)),
        exec_options=frozenset(_option_names(exec_help)),
        resume_options=frozenset(_option_names(resume_help)),
    )
    return capabilities


def codex_feature_disable_args(capabilities: CodexCapabilities) -> list[str]:
    args: list[str] = []
    for feature in capabilities.optional_disabled_features:
        args.extend(["--disable", feature])
    return args


def outer_codex_feature_disable_args(
    capabilities: CodexCapabilities | frozenset[str] | set[str],
) -> list[str]:
    args: list[str] = []
    available = (
        capabilities.optional_disabled_features
        if isinstance(capabilities, CodexCapabilities)
        else tuple(
            feature
            for feature in OPTIONAL_CODEX_DISABLED_FEATURES
            if feature in capabilities
        )
    )
    for feature in available:
        if feature not in OUTER_CODEX_RETAINED_FEATURES:
            args.extend(["--disable", feature])
    return args


def _probe(binary: str, args: tuple[str, ...], timeout_seconds: float) -> str:
    try:
        completed = subprocess.run(
            [binary, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout_seconds)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderCapabilityError(
            f"could not probe provider capability via {binary} {' '.join(args)}"
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[:500]
        raise ProviderCapabilityError(
            f"provider capability probe failed for {binary} {' '.join(args)}: "
            + detail
        )
    return completed.stdout


def _option_names(help_text: str) -> set[str]:
    options: set[str] = set()
    for line in help_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        head = stripped.split("<", 1)[0]
        for token in head.replace(",", " ").split():
            if token.startswith("--"):
                options.add(token)
    return options


def _feature_names(features_text: str) -> set[str]:
    names: set[str] = set()
    for line in features_text.splitlines():
        fields = line.split()
        if fields and not fields[0].startswith("WARNING"):
            names.add(fields[0])
    return names


def _launch_id(value: str) -> str:
    launch_id = str(value or "").strip()
    if not launch_id:
        raise ValueError("proof-tool launch id must be non-empty")
    return launch_id


def _toml_string(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)
