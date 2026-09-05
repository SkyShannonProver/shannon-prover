"""Provider profiles for the interleaved Shannon product runtime."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROFILE_PATH = Path(__file__).with_name("agent_profiles.json")
SUPPORTED_PROVIDERS = frozenset({"claude", "codex"})
PROFILE_SCHEMA_VERSION = 2
PROVIDER_ADAPTERS = {
    "claude": {
        "backend": "claude",
        "cli_provider": "claude-code",
        "binary_name": "claude",
    },
    "codex": {
        "backend": "codex",
        "cli_provider": "codex",
        "binary_name": "codex",
    },
}
if set(PROVIDER_ADAPTERS) != SUPPORTED_PROVIDERS:
    raise RuntimeError("provider adapter keys must match supported providers")
PROFILE_FIELDS = frozenset({
    "model",
    "effort",
    "outer_max_turns",
    "outer_max_budget_usd",
})
PROVIDER_IDENTITY_FIELDS = (
    "agent_backend",
    "model",
    "binary_sha256",
    "version",
)


def provider_identity_projection(value: dict[str, Any]) -> dict[str, str]:
    """Return the provider facts that are semantically invocation-binding.

    Runtime identity artifacts also carry envelope metadata such as ``kind``
    and ``schema_version``.  Those fields describe the artifact container, not
    the provider being selected.  Expected and observed identities must be
    compared and fingerprinted through this one projection so harmless JSON
    formatting or envelope fields cannot manufacture a mismatch.
    """

    identity = {
        field: str(value.get(field) or "")
        for field in PROVIDER_IDENTITY_FIELDS
    }
    if any(not identity[field] for field in PROVIDER_IDENTITY_FIELDS):
        raise ValueError("provider identity has an empty required field")
    return identity


def provider_identity_sha256(value: dict[str, Any]) -> str:
    projected = provider_identity_projection(value)
    encoded = json.dumps(
        projected,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def agent_profile_sha256(value: "AgentProfile | dict[str, Any]") -> str:
    """Hash only the selected role profile, not unrelated config entries."""

    profile = value.base_dict() if isinstance(value, AgentProfile) else dict(value)
    encoded = json.dumps(
        profile,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AgentProfile:
    key: str
    backend: str
    cli_provider: str
    binary_name: str
    model: str
    effort: str
    outer_max_turns: int | None = None
    outer_max_budget_usd: int | None = None

    def base_dict(self) -> dict[str, Any]:
        return {
            "profile": self.key,
            "backend": self.backend,
            "cli_provider": self.cli_provider,
            "binary_name": self.binary_name,
            "model": self.model,
            "effort": self.effort,
        }

    def outer_dict(self) -> dict[str, Any]:
        return {
            **self.base_dict(),
            "outer_max_turns": self.outer_max_turns,
            "outer_max_budget_usd": self.outer_max_budget_usd,
        }


@dataclass(frozen=True)
class InterleavedAgentConfig:
    outer: AgentProfile
    inner: AgentProfile

    @property
    def required_provider_keys(self) -> frozenset[str]:
        """Providers whose runtimes are needed by the selected role pair."""
        return frozenset({self.outer.key, self.inner.key})


def load_agent_profiles(
    path: Path = PROFILE_PATH,
) -> tuple[dict[str, AgentProfile], dict[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ValueError(
            f"agent profile config must have schema_version {PROFILE_SCHEMA_VERSION}"
        )
    unknown_top = set(raw) - {"schema_version", "profiles", "defaults"}
    if unknown_top:
        raise ValueError(
            "agent profile config has unknown fields: "
            + ", ".join(sorted(unknown_top))
        )
    raw_profiles = raw.get("profiles")
    raw_defaults = raw.get("defaults")
    if not isinstance(raw_profiles, dict) or not isinstance(raw_defaults, dict):
        raise ValueError("agent profile config requires profiles and defaults")
    if set(raw_defaults) != {"outer_provider", "inner_provider"}:
        raise ValueError(
            "agent profile defaults must define exactly outer_provider and "
            "inner_provider"
        )
    if set(raw_profiles) != SUPPORTED_PROVIDERS:
        raise ValueError("agent profile config must define exactly claude and codex")

    profiles: dict[str, AgentProfile] = {}
    for key, value in raw_profiles.items():
        if not isinstance(value, dict):
            raise ValueError(f"agent profile {key} must be an object")
        unknown = set(value) - PROFILE_FIELDS
        if unknown:
            raise ValueError(
                f"agent profile {key} has unknown fields: "
                + ", ".join(sorted(unknown))
            )
        has_turn_limit = value.get("outer_max_turns") is not None
        has_budget_limit = value.get("outer_max_budget_usd") is not None
        if key == "claude" and not (has_turn_limit and has_budget_limit):
            raise ValueError(
                "Claude profile requires outer_max_turns and "
                "outer_max_budget_usd"
            )
        if key == "codex" and (has_turn_limit or has_budget_limit):
            raise ValueError(
                "Codex profile must not declare unsupported outer budget or "
                "turn limits"
            )
        adapter = PROVIDER_ADAPTERS[key]
        profile = AgentProfile(
            key=key,
            backend=adapter["backend"],
            cli_provider=adapter["cli_provider"],
            binary_name=adapter["binary_name"],
            model=str(value.get("model") or ""),
            effort=str(value.get("effort") or ""),
            outer_max_turns=_optional_positive_int(
                value.get("outer_max_turns"), f"{key}.outer_max_turns"
            ),
            outer_max_budget_usd=_optional_positive_int(
                value.get("outer_max_budget_usd"),
                f"{key}.outer_max_budget_usd",
            ),
        )
        if not all((profile.model, profile.effort)):
            raise ValueError(f"agent profile {key} has an empty required field")
        profiles[key] = profile

    defaults = {
        "outer_provider": str(raw_defaults.get("outer_provider") or ""),
        "inner_provider": str(raw_defaults.get("inner_provider") or ""),
    }
    if any(value not in profiles for value in defaults.values()):
        raise ValueError("agent profile defaults must name configured providers")
    return profiles, defaults


def resolve_agent_config(
    *,
    outer_provider: str | None = None,
    inner_provider: str | None = None,
    path: Path = PROFILE_PATH,
) -> InterleavedAgentConfig:
    profiles, defaults = load_agent_profiles(path)
    outer_key = str(outer_provider or defaults["outer_provider"])
    inner_key = str(inner_provider or defaults["inner_provider"])
    try:
        return InterleavedAgentConfig(
            outer=profiles[outer_key],
            inner=profiles[inner_key],
        )
    except KeyError as exc:
        raise ValueError(f"unsupported agent provider: {exc.args[0]}") from exc


def profile_for(provider: str, path: Path = PROFILE_PATH) -> AgentProfile:
    profiles, _ = load_agent_profiles(path)
    try:
        return profiles[provider]
    except KeyError as exc:
        raise ValueError(f"unsupported agent provider: {provider}") from exc


def _optional_positive_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer or null")
    return value
