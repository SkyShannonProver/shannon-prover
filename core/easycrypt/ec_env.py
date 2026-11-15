"""Single environment authority for the repository-locked EasyCrypt runtime."""

from __future__ import annotations

import re

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


# Every proof check runs the same smt portfolio: the provers below that the
# managed Why3 configuration registers, all at once. EasyCrypt's own default
# list does not include CVC5, so with this toolchain every check ran Z3
# alone (plus Alt-Ergo only where it is installed). Measured on the step4_1 failures
# and four verified proofs, adding provers proved goals Z3 could not (in
# 0.1-0.4 s) while longer timeouts proved none. The manager's session and
# final verification must share the set: a session step that only CVC5 proves
# is otherwise rejected by verification. The session timeout bounds a failing
# smt call the agent waits for; verification allows more under load.
SMT_PORTFOLIO = ("Z3", "CVC5", "Alt-Ergo")
SESSION_SMT_TIMEOUT_SECONDS = 3
VERIFICATION_SMT_TIMEOUT_SECONDS = 30
SMT_PROVERS_ENV = "SHANNON_SMT_PROVERS"
SMT_TIMEOUT_ENV = "SHANNON_SMT_TIMEOUT"
_PROVER_NAME = re.compile(r'^\s*name\s*=\s*"([^"]+)"\s*$')
_PROVER_SECTION = re.compile(r"^\s*\[(?:partial_)?prover\]\s*$")


def managed_smt_provers() -> tuple[str, ...]:
    """The portfolio provers the managed Why3 configuration registers."""

    try:
        lines = managed_why3_config_file().read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()
    registered: set[str] = set()
    in_prover = False
    for line in lines:
        if line.strip().startswith("["):
            in_prover = bool(_PROVER_SECTION.match(line))
            continue
        match = _PROVER_NAME.match(line) if in_prover else None
        if match:
            registered.add(match.group(1))
    return tuple(name for name in SMT_PORTFOLIO if name in registered)


def smt_arguments(timeout: int) -> list[str]:
    """``-p`` per portfolio prover, all run together, and the smt timeout."""

    provers = managed_smt_provers()
    arguments: list[str] = []
    for name in provers:
        arguments += ["-p", name]
    if provers:
        arguments += ["-max-provers", str(len(provers))]
    return arguments + ["-timeout", str(int(timeout))]


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
    # Native companions run smt in-process; they read the same portfolio.
    env[SMT_PROVERS_ENV] = ",".join(managed_smt_provers())
    env[SMT_TIMEOUT_ENV] = str(SESSION_SMT_TIMEOUT_SECONDS)
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
