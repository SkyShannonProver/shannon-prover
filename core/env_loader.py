"""The single source of truth for parsing boolean environment knobs.

:func:`env_bool` gives one vocabulary and a strict mode that fails loudly on
unrecognized values; :func:`warn_unknown_shannon_env` flags misspelled
``SHANNON_*`` knob names.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("core.env_loader")

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})

# Known framework env knob names. Used by warn_unknown_shannon_env() to flag a
# typo'd NAME (e.g. SHANNON_DISABLE_PORBE) that would otherwise silently
# disable nothing. tests/public/core/test_env_loader_registry.py checks that
# every SHANNON_* name the code mentions is listed and every listed name is
# still mentioned.
KNOWN_ENV_FLAGS = frozenset({
    "EC_DAEMON_DISABLE", "EC_DAEMON_SESSION_TTL_SECONDS", "EC_DAEMON_SOCKET",
    "EC_SESSION_DIR", "EVAL_TARGET_LEMMA",
    "SHANNON_BUNDLE_INTERNAL", "SHANNON_CTX_RESPAWN_MAX",
    "SHANNON_CTX_RESPAWN_MIN_RUNWAY_S", "SHANNON_CTX_WATERMARK_TOKENS",
    "SHANNON_CTX_WATERMARK_TURNS",
    "SHANNON_DISABLE_CTX_RESPAWN", "SHANNON_EC_DAEMON",
    "SHANNON_EC_STEP_TIMEOUT",
    "SHANNON_EASYCRYPT_SOURCE_MANIFEST",
    "SHANNON_EVAL_CONFINEMENT_MANIFEST", "SHANNON_EVAL_CONFINEMENT_REQUIRED",
    "SHANNON_GIVE_UP_ALLOW_AFTER",
    "SHANNON_GIVE_UP_WINDOW_S",
    "SHANNON_INTERLEAVED_ANSWER_SOURCE", "SHANNON_INTERLEAVED_PROJECT",
    "SHANNON_MANAGER_OPERATION_TIMEOUT_S", "SHANNON_MANAGER_STALL_WATCHDOG",
    "SHANNON_MCP_READY_TIMEOUT_S",
    "SHANNON_MCP_SPAWN_RETRIES", "SHANNON_NODE_DEADLINE_EPOCH",
    "SHANNON_RECENT_REASONING_K",
    "SHANNON_REPLAY_AGG_BUDGET", "SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC",
    "SHANNON_SKIP_BOOTSTRAP_GUARD", "SHANNON_SUITE_WILL_BUNDLE",
    "SHANNON_TMP_DIR",
    "SHANNON_WHY3_CONFIG",
    "SHANNON_WORKER_PGID_MANIFEST",
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
