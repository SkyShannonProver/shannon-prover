"""Load .env from the project root into os.environ (no extra dependencies).

Also the single source of truth for parsing boolean env knobs. Hand-rolled
``os.environ.get(...).lower() in ("1","true","yes","on")`` checks were scattered
across ~8 modules; the danger for paper measurements is a *typo'd value*
(``SHANNON_DISABLE_PROBE=ture``) silently reading as falsy, leaving probe ON and
mislabelling an L4-no-probe ablation arm. :func:`env_bool` gives one vocabulary
and a ``strict`` mode that fails loudly on an unrecognized value; the ablation
kill-switches use it. (Audit §8 #11 — subset: helper + ablation knobs. The full
typed-registry migration of the other knobs is deferred.)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("core.env_loader")

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})

# Known framework env knob names. Used only by warn_unknown_shannon_env() to
# flag a typo'd NAME (e.g. SHANNON_DISABLE_PORBE) that would otherwise silently
# disable nothing. WARN-only — keep roughly in sync; a missing entry just yields
# a spurious warning, never a broken run.
KNOWN_ENV_FLAGS = frozenset({
    "EC_DAEMON_DISABLE", "EC_DAEMON_SESSION_TTL_SECONDS", "EC_DAEMON_SOCKET",
    "EC_DAEMON_SOCKET_NAME_TEMPLATE", "EC_SESSION_DIR", "EVAL_TARGET_LEMMA",
    "SHANNON_BRIDGE_CONNECT_TIMEOUT", "SHANNON_BRIDGE_READ_TIMEOUT",
    "SHANNON_BUNDLE_INTERNAL", "SHANNON_CTX_RESPAWN_MAX",
    "SHANNON_CTX_RESPAWN_MIN_RUNWAY_S", "SHANNON_CTX_WATERMARK_TOKENS",
    "SHANNON_CTX_WATERMARK_TURNS", "SHANNON_DEEP_GOAL_SHRINK_CHARS",
    "SHANNON_DISABLE_CTX_RESPAWN", "SHANNON_DISABLE_PROBE",
    "SHANNON_EC_DAEMON", "SHANNON_ENABLE_PROBE",
    "SHANNON_FINISH_WITH_ADMIT_ALLOW_AFTER", "SHANNON_GIVE_UP_ALLOW_AFTER",
    "SHANNON_GIVE_UP_WINDOW_S", "SHANNON_LEGACY_DISPLAY",
    "SHANNON_MCP_DEBUG_LOG", "SHANNON_MCP_READY_TIMEOUT_S",
    "SHANNON_MCP_SPAWN_RETRIES", "SHANNON_NODE_DEADLINE_EPOCH",
    "SHANNON_PANEL_INVARIANTS", "SHANNON_RECENT_REASONING_K",
    "SHANNON_RECORD_PROOF_BANK",
    "SHANNON_REPLAY_AGG_BUDGET", "SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC",
    "SHANNON_SKIP_BOOTSTRAP_GUARD", "SHANNON_SUITE_WILL_BUNDLE",
    "SHANNON_SURFACE_PROFILE", "SHANNON_TMP_DIR",
    "SHANNON_VIEW_NEUTRALITY_STRICT", "SHANNON_WORKER_PGID_MANIFEST",
    "WHY3EC_SOCKET",
})


def env_bool(name: str, default: bool = False, *, strict: bool = False) -> bool:
    """Parse a boolean env knob with one canonical vocabulary.

    Unset or empty → ``default``. Recognized truthy/falsy tokens
    (case-insensitive: 1/true/yes/on, 0/false/no/off) → the obvious bool. An
    UNRECOGNIZED value is the dangerous case: ``strict=True`` raises ValueError
    (fail-fast — better than a mislabelled ablation run); otherwise it logs a
    loud warning and falls back to ``default``.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value == "":
        return default
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    msg = (
        f"env knob {name}={raw!r} is not a recognized boolean "
        f"(expected one of {sorted(_TRUTHY | _FALSY)}); "
        f"falling back to default={default!r}. A typo here can silently "
        f"mislabel a run — fix the value."
    )
    if strict:
        raise ValueError(msg)
    logger.warning(msg)
    return default


def warn_unknown_shannon_env() -> list[str]:
    """Warn for each ``SHANNON_*`` env var set to a name not in the registry.

    Catches a typo'd knob NAME (e.g. ``SHANNON_DISABLE_PORBE=1``) that would
    otherwise silently disable nothing and corrupt an ablation arm. Returns the
    list of unknown names (also for tests). Non-fatal by design.
    """
    unknown = sorted(
        name for name in os.environ
        if name.startswith("SHANNON_") and name not in KNOWN_ENV_FLAGS
    )
    for name in unknown:
        logger.warning(
            "unknown SHANNON_* env var %s is set — likely a typo of a real "
            "knob (it currently has NO effect). Known knobs: see "
            "core.env_loader.KNOWN_ENV_FLAGS.", name,
        )
    return unknown


def load_env(env_path: Path | None = None) -> None:
    """Read a .env file and set os.environ for keys that are not already set.

    Lines are stripped. Empty lines and lines starting with # are skipped.
    Format: KEY=VALUE (first '=' separates key from value; value is not quoted).
    """
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key:
                os.environ[key] = value
