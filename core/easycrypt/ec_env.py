"""EasyCrypt environment configuration.

Single source of truth for opam switch name and environment setup.
All code that needs to run `easycrypt` or `session_cli` should use
get_ec_env() from this module.

To configure for a different machine, change OPAM_SWITCH below.
"""

from __future__ import annotations

import os
import re
import subprocess

# ── Configure this for your machine ──────────────────────────────────────
# Set to None to use the current/default opam switch.
OPAM_SWITCH: str | None = "easycrypt"
# ─────────────────────────────────────────────────────────────────────────



def get_ec_env() -> dict:
    """Return os.environ augmented with opam variables for EasyCrypt.

    Use this as the `env` parameter for subprocess calls:
        subprocess.run(["easycrypt", ...], env=get_ec_env())
    """
    env = os.environ.copy()
    cmds = []
    if OPAM_SWITCH:
        cmds.append(["opam", "env", f"--switch={OPAM_SWITCH}"])
    cmds.append(["opam", "env"])

    for cmd in cmds:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    m = re.match(r"(\w+)='([^']*)'", line)
                    if m:
                        env[m.group(1)] = m.group(2)
                return env
        except Exception:
            continue
    return env


def check_ec_available() -> tuple[bool, str]:
    """Precheck: verify that easycrypt is runnable.

    Returns (ok, message). Call this before launching provers.
    """
    # Check opam exists
    try:
        subprocess.run(
            ["opam", "--version"],
            capture_output=True, text=True, timeout=5,
        )
    except FileNotFoundError:
        return False, "opam not found. Install opam and EasyCrypt first."

    # Check switch exists (if configured)
    if OPAM_SWITCH:
        result = subprocess.run(
            ["opam", "switch", "list", "--short"],
            capture_output=True, text=True, timeout=10,
        )
        switches = result.stdout.strip().splitlines()
        if OPAM_SWITCH not in switches:
            return False, (
                f"opam switch '{OPAM_SWITCH}' not found. "
                f"Available switches: {', '.join(switches)}. "
                f"Edit OPAM_SWITCH in core/easycrypt/ec_env.py."
            )

    # Check easycrypt binary
    env = get_ec_env()
    try:
        result = subprocess.run(
            ["easycrypt", "why3config"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        if result.returncode != 0:
            return False, f"easycrypt why3config failed: {result.stderr[:200]}"
    except FileNotFoundError:
        return False, (
            "easycrypt not found in PATH after opam env. "
            "Check that easycrypt is installed in the configured switch."
        )

    return True, "easycrypt is available"
