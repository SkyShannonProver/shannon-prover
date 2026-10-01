"""Single environment authority for the repository-locked EasyCrypt runtime."""

from __future__ import annotations

from pathlib import Path
import subprocess

from core.easycrypt.toolchain import (
    managed_easycrypt_environment,
    managed_why3_config_file,
)


MANAGED_WHY3_CONFIG_ENV = "SHANNON_WHY3_CONFIG"


def managed_why3_config_path(env: dict[str, str]) -> Path:
    """Require the same repository-local configuration passed to the CLI.

    Native companions link ``ecLib`` directly rather than entering through the
    EasyCrypt CLI, so they must receive this exact path explicitly.  Falling
    back to Why3's ambient default silently changes the available prover set.
    """

    path = managed_why3_config_file()
    if not path.is_file():
        raise RuntimeError(
            "repository-managed EasyCrypt Why3 configuration is missing; "
            "run tools/bootstrap_easycrypt.py --configure-solvers"
        )
    return path.resolve()


def easycrypt_command(*args: str, binary: str = "easycrypt") -> list[str]:
    """Bind CLI processes to the same config as native companions.

    An explicit option also overrides ``why3conf`` in an EasyCrypt project or
    system ini. Do not change HOME or XDG_CONFIG_HOME: the managed environment
    can also be inherited by model CLIs with existing login credentials.
    """

    return [binary, *args, "-why3", str(managed_why3_config_file())]


def get_ec_env() -> dict[str, str]:
    """Return a fresh environment for the verified managed toolchain.

    There is no fallback to an ambient/global opam switch.  Bootstrap with
    ``uv run python tools/bootstrap_easycrypt.py`` when the receipt is missing.
    """

    env = managed_easycrypt_environment()
    env[MANAGED_WHY3_CONFIG_ENV] = str(managed_why3_config_path(env))
    return env


def check_ec_available() -> tuple[bool, str]:
    try:
        env = get_ec_env()
    except RuntimeError as exc:
        return False, str(exc)
    try:
        result = subprocess.run(
            easycrypt_command("config"),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"managed EasyCrypt is not runnable: {exc}"
    if result.returncode != 0:
        return False, f"easycrypt config failed: {result.stderr[:200]}"
    return True, "repository-locked EasyCrypt is available"
