#!/usr/bin/env python3
"""Build or verify Shannon's repository-locked EasyCrypt toolchain."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.easycrypt.toolchain import (  # noqa: E402
    EasyCryptToolchainReceipt,
    load_easycrypt_lock,
    load_toolchain_receipt,
    managed_opam_root,
    managed_switch_name,
    sha256_file,
    toolchain_receipt_path,
    verify_locked_easycrypt_source,
)


_BUILD_ID_RE = re.compile(r"^git-hash:\s*(\S+)\s*$", re.MULTILINE)
_ENV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)='([^']*)'; export \1;$")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="validate the existing receipt and artifacts without installing",
    )
    mode.add_argument(
        "--print-env",
        action="store_true",
        help="print verified shell exports for developer-only direct commands",
    )
    args = parser.parse_args()
    lock = verify_locked_easycrypt_source()
    if not args.verify_only and not args.print_env:
        _bootstrap(
            lock.source_repository,
            lock.source_commit,
            lock.ocaml_package,
        )
    receipt, paths = _verify_installed()
    if args.print_env:
        _print_environment()
        return 0
    print(json.dumps({
        "status": "verified",
        "release_tag": lock.release_tag,
        "source_commit": lock.source_commit,
        "opam_root": str(managed_opam_root()),
        "switch": managed_switch_name(),
        "easycrypt": str(paths[0]),
        "ecLib": str(paths[1]),
        "receipt": receipt.payload(),
    }, indent=2, sort_keys=True))
    return 0


def _print_environment() -> None:
    opam = shutil.which("opam")
    if not opam:
        raise RuntimeError("opam is required to select EasyCrypt")
    environment = _switch_env(
        opam,
        managed_opam_root(),
        managed_switch_name(),
        dict(os.environ),
    )
    for name in (
        "OPAMROOT",
        "OPAMSWITCH",
        "OPAM_SWITCH_PREFIX",
        "CAML_LD_LIBRARY_PATH",
        "OCAML_TOPLEVEL_PATH",
        "MANPATH",
        "PATH",
    ):
        value = environment.get(name)
        if value is not None:
            print(f"export {name}={shlex.quote(value)}")


def _bootstrap(repository: str, commit: str, ocaml_package: str) -> None:
    opam = shutil.which("opam")
    if not opam:
        raise RuntimeError("opam is required to bootstrap EasyCrypt")
    root = managed_opam_root()
    root.mkdir(parents=True, exist_ok=True)
    base = dict(os.environ)
    base["OPAMROOT"] = str(root)
    if not (root / "config").is_file():
        _run([
            opam, "init", "--bare", "--disable-sandboxing", "--yes",
            "--root", str(root),
        ], env=base, timeout=600)
    switches = _run([
        opam, "switch", "list", "--short", "--root", str(root),
    ], env=base, timeout=60).stdout.splitlines()
    switch = managed_switch_name()
    if switch not in {line.strip() for line in switches}:
        _run([
            opam, "switch", "create", switch, ocaml_package, "--yes",
            "--root", str(root),
        ], env=base, timeout=3600)
    _verify_ocaml_package(opam, root, switch, base, ocaml_package)
    _run([
        opam, "pin", "add", "easycrypt",
        f"git+{repository}#{commit}", "--yes", "--no-action",
        "--root", str(root), "--switch", switch,
    ], env=base, timeout=600)
    _run([
        opam, "install", "--yes", "--assume-depexts",
        "easycrypt",
        "--root", str(root), "--switch", switch,
    ], env=base, timeout=3600)
    env = _switch_env(opam, root, switch, base)
    easycrypt = _required_tool("easycrypt", env)
    _run([str(easycrypt), "why3config"], env=env, timeout=120)
    library = _library_archive(env)
    build_id = _easycrypt_build_id(easycrypt, env)
    lock = load_easycrypt_lock()
    if build_id != lock.expected_build_id:
        raise RuntimeError(
            f"EasyCrypt build ID {build_id!r} does not match "
            f"lock {lock.expected_build_id!r}"
        )
    receipt = EasyCryptToolchainReceipt(
        lock_identity_sha256=lock.identity_sha256,
        build_id=build_id,
        executable_sha256=sha256_file(easycrypt),
        library_sha256=sha256_file(library),
    )
    path = toolchain_receipt_path()
    path.write_text(
        json.dumps(receipt.payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _verify_installed() -> tuple[EasyCryptToolchainReceipt, tuple[Path, Path]]:
    lock = load_easycrypt_lock()
    receipt = load_toolchain_receipt()
    opam = shutil.which("opam")
    if not opam:
        raise RuntimeError("opam is required to verify EasyCrypt")
    root = managed_opam_root()
    _verify_ocaml_package(
        opam,
        root,
        managed_switch_name(),
        dict(os.environ),
        lock.ocaml_package,
    )
    env = _switch_env(opam, root, managed_switch_name(), dict(os.environ))
    easycrypt = _required_tool("easycrypt", env)
    library = _library_archive(env)
    build_id = _easycrypt_build_id(easycrypt, env)
    if build_id != receipt.build_id:
        raise RuntimeError("installed EasyCrypt build ID differs from receipt")
    if sha256_file(easycrypt) != receipt.executable_sha256:
        raise RuntimeError("installed EasyCrypt executable differs from receipt")
    if sha256_file(library) != receipt.library_sha256:
        raise RuntimeError("installed EasyCrypt ecLib differs from receipt")
    return receipt, (easycrypt, library)


def _verify_ocaml_package(
    opam: str,
    root: Path,
    switch: str,
    base: dict[str, str],
    expected: str,
) -> None:
    result = _run([
        opam,
        "list",
        "--installed",
        "--short",
        "--columns=package",
        "--root",
        str(root),
        "--switch",
        switch,
        "ocaml-base-compiler",
    ], env=base, timeout=60)
    installed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if installed != [expected]:
        raise RuntimeError(
            f"managed OCaml compiler {installed!r} differs from lock {expected!r}"
        )


def _switch_env(
    opam: str,
    root: Path,
    switch: str,
    base: dict[str, str],
) -> dict[str, str]:
    base = dict(base)
    base["OPAMROOT"] = str(root)
    result = _run([
        opam, "env", "--shell=sh", "--root", str(root),
        "--switch", switch, "--set-switch",
    ], env=base, timeout=60)
    env = dict(base)
    for line in result.stdout.splitlines():
        match = _ENV_RE.match(line.strip())
        if match:
            env[match.group(1)] = match.group(2)
    if env.get("OPAMROOT") != str(root) or env.get("OPAMSWITCH") != switch:
        raise RuntimeError("opam did not select the managed EasyCrypt switch")
    return env


def _library_archive(env: dict[str, str]) -> Path:
    ocamlfind = _required_tool("ocamlfind", env)
    result = _run([
        str(ocamlfind), "query", "-format", "%d", "easycrypt.ecLib",
    ], env=env, timeout=60)
    archive = Path(result.stdout.strip()) / "ecLib.cmxa"
    if not archive.is_file():
        raise RuntimeError("managed EasyCrypt ecLib archive is unavailable")
    return archive.resolve()


def _easycrypt_build_id(binary: Path, env: dict[str, str]) -> str:
    result = _run([str(binary), "config"], env=env, timeout=60)
    match = _BUILD_ID_RE.search(result.stdout + "\n" + result.stderr)
    if match is None or match.group(1) in {"n/a", "[unspecified]"}:
        raise RuntimeError("managed EasyCrypt did not report a locked build ID")
    return match.group(1)


def _required_tool(name: str, env: dict[str, str]) -> Path:
    value = shutil.which(name, path=env.get("PATH"))
    if not value:
        raise RuntimeError(f"managed EasyCrypt tool {name!r} is unavailable")
    return Path(value).resolve()


def _run(
    command: list[str],
    *,
    env: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-4000:]
        raise RuntimeError(f"command failed: {' '.join(command)}\n{detail}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
