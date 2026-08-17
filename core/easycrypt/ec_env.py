"""Single environment authority for the repository-locked EasyCrypt runtime."""

from __future__ import annotations

from pathlib import Path
import subprocess

from core.easycrypt.toolchain import managed_easycrypt_environment


MANAGED_WHY3_CONFIG_ENV = "SHANNON_WHY3_CONFIG"


def managed_why3_config_path(env: dict[str, str]) -> Path:
    """Resolve the same EasyCrypt XDG Why3 configuration as the CLI.

    Native companions link ``ecLib`` directly rather than entering through the
    EasyCrypt CLI, so they must receive this exact path explicitly.  Falling
    back to Why3's ambient default silently changes the available prover set.
    """

    config_root = env.get("XDG_CONFIG_HOME", "").strip()
    if config_root:
        path = Path(config_root) / "easycrypt" / "why3.conf"
    else:
        home = env.get("HOME", "").strip()
        if not home:
            raise RuntimeError("managed EasyCrypt environment has no HOME")
        path = Path(home) / ".config" / "easycrypt" / "why3.conf"
    if not path.is_file():
        raise RuntimeError(
            "repository-managed EasyCrypt Why3 configuration is missing; "
            "run tools/bootstrap_easycrypt.py"
        )
    return path.resolve()


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
            ["easycrypt", "why3config"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"managed EasyCrypt is not runnable: {exc}"
    if result.returncode != 0:
        return False, f"easycrypt why3config failed: {result.stderr[:200]}"
    return True, "repository-locked EasyCrypt is available"
