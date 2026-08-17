"""Repository-locked EasyCrypt toolchain foundation sentinels."""

from __future__ import annotations

from pathlib import Path

from core.easycrypt.ec_env import get_ec_env
from core.easycrypt.ec_runtime_identity import discover_easycrypt_runtime_identity
from core.easycrypt.native_semantics.companion import NATIVE_ADAPTER_ABI
from core.easycrypt.toolchain import (
    load_easycrypt_lock,
    load_toolchain_receipt,
    managed_opam_root,
    managed_switch_name,
    repository_storage_root,
    verify_locked_easycrypt_source,
)


ROOT = Path(__file__).resolve().parents[1]


def test_easycrypt_release_and_vendored_snapshot_are_exactly_locked() -> None:
    lock = verify_locked_easycrypt_source()

    assert lock.release_tag == "r2026.06"
    assert lock.source_commit == "1c7e6d78eb1cfb44a4c98e00e1b5ef8b5bfd30c9"
    assert lock.expected_build_id == "r2026.06"
    assert lock.ocaml_package == "ocaml-base-compiler.4.14.2"
    assert lock.native_adapter_abi == NATIVE_ADAPTER_ABI == 3


def test_managed_toolchain_receipt_binds_runtime_and_library() -> None:
    lock = load_easycrypt_lock()
    receipt = load_toolchain_receipt()
    runtime = discover_easycrypt_runtime_identity()

    assert receipt.lock_identity_sha256 == lock.identity_sha256
    assert receipt.build_id == runtime.build_id == lock.expected_build_id
    assert receipt.executable_sha256 == runtime.binary_sha256


def test_easycrypt_environment_ignores_ambient_opam_switch() -> None:
    environment = get_ec_env()
    storage_root = repository_storage_root().resolve()

    assert Path(environment["OPAMROOT"]).resolve() == managed_opam_root()
    assert environment["OPAMSWITCH"] == managed_switch_name()
    assert managed_opam_root().resolve().is_relative_to(storage_root)


def test_runtime_code_has_no_legacy_easycrypt_switch_bypass() -> None:
    runtime_roots = (
        ROOT / "core",
        ROOT / "workflow",
        ROOT / "eval_suite",
        ROOT / "playground",
    )
    for runtime_root in runtime_roots:
        for path in runtime_root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "--switch=easycrypt" not in source, path
            assert '"--switch", "easycrypt"' not in source, path
