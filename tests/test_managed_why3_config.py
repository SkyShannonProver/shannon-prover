"""Repository-local solver configuration must not mutate ambient settings."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from core.easycrypt import ec_env
from core.easycrypt.ec_proc import emacs_command
from core.easycrypt.toolchain import managed_easycrypt_environment
from tools import bootstrap_easycrypt as bootstrap


def _bind_config(monkeypatch, path: Path) -> None:
    monkeypatch.setattr(ec_env, "managed_why3_config_file", lambda: path)
    monkeypatch.setattr(bootstrap, "managed_why3_config_file", lambda: path)


def test_missing_local_config_never_uses_existing_global_config(
    tmp_path, monkeypatch,
) -> None:
    global_config = tmp_path / "user-config" / "easycrypt" / "why3.conf"
    global_config.parent.mkdir(parents=True)
    global_config.write_text("user configuration\n")
    _bind_config(monkeypatch, tmp_path / "toolchain" / "why3.conf")

    with pytest.raises(RuntimeError, match="--configure-solvers"):
        ec_env.managed_why3_config_path({"XDG_CONFIG_HOME": str(global_config.parent.parent)})

    assert global_config.read_text() == "user configuration\n"


def test_environment_binds_local_config_without_redirecting_credentials(
    tmp_path, monkeypatch,
) -> None:
    local = tmp_path / "why3.conf"
    local.write_text("managed configuration\n")
    _bind_config(monkeypatch, local)
    base = {"HOME": "/user/home", "XDG_CONFIG_HOME": "/user/config", "CODEX_HOME": "/user/codex"}
    monkeypatch.setattr(ec_env, "managed_easycrypt_environment", lambda: dict(base))

    environment = ec_env.get_ec_env()

    assert environment == {**base, "SHANNON_WHY3_CONFIG": str(local)}
    assert base == {"HOME": "/user/home", "XDG_CONFIG_HOME": "/user/config", "CODEX_HOME": "/user/codex"}
    assert emacs_command()[-2:] == ["-why3", str(local)]


def test_availability_check_is_read_only(tmp_path, monkeypatch) -> None:
    local = tmp_path / "why3.conf"
    local.write_text("managed configuration\n")
    _bind_config(monkeypatch, local)
    monkeypatch.setattr(ec_env, "managed_easycrypt_environment", lambda: {})
    before = local.stat().st_mtime_ns

    def run(command, **kwargs):
        assert command == ["easycrypt", "config", "-why3", str(local)]
        assert kwargs["env"]["SHANNON_WHY3_CONFIG"] == str(local)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(ec_env.subprocess, "run", run)
    assert ec_env.check_ec_available()[0]
    assert local.stat().st_mtime_ns == before
    assert local.read_text() == "managed configuration\n"


def test_failed_detection_preserves_existing_managed_config(
    tmp_path, monkeypatch,
) -> None:
    local = tmp_path / "why3.conf"
    local.write_text("previous working configuration\n")
    _bind_config(monkeypatch, local)

    def fail(command, **kwargs):
        generated = Path(command[command.index("-why3") + 1])
        assert generated != local
        generated.write_text("incomplete\n")
        raise RuntimeError("detection failed")

    monkeypatch.setattr(bootstrap, "_run", fail)
    with pytest.raises(RuntimeError, match="detection failed"):
        bootstrap._configure_solvers(Path("easycrypt"), {})
    assert local.read_text() == "previous working configuration\n"
    assert list(tmp_path.iterdir()) == [local]


def test_configure_solvers_migrates_verified_install_without_rebuilding(
    tmp_path, monkeypatch, capsys,
) -> None:
    _bind_config(monkeypatch, tmp_path / "why3.conf")
    monkeypatch.setattr(bootstrap.sys, "argv", ["bootstrap_easycrypt.py", "--configure-solvers"])
    monkeypatch.setattr(bootstrap, "verify_locked_easycrypt_source", lambda: SimpleNamespace(
        release_tag="test", source_commit="test",
    ))
    calls = []
    receipt = SimpleNamespace(payload=lambda: {})

    def verify(*, require_solver_config=True):
        calls.append(("verify", require_solver_config))
        return receipt, (Path("easycrypt"), Path("ecLib.cmxa"))

    monkeypatch.setattr(bootstrap, "_verify_installed", verify)
    monkeypatch.setattr(bootstrap.shutil, "which", lambda _: "/tools/opam")
    monkeypatch.setattr(bootstrap, "_switch_env", lambda *args: {})
    monkeypatch.setattr(bootstrap, "_required_tool", lambda *args: Path("easycrypt"))
    monkeypatch.setattr(bootstrap, "_configure_solvers", lambda *args: calls.append(("configure",)))
    monkeypatch.setattr(bootstrap, "_bootstrap", lambda *args: pytest.fail("must not rebuild"))

    assert bootstrap.main() == 0
    assert calls == [("verify", False), ("configure",), ("verify", True)]
    assert '"why3_config"' in capsys.readouterr().out


def test_real_detection_and_cli_ignore_global_and_project_config(
    tmp_path, monkeypatch,
) -> None:
    environment = managed_easycrypt_environment()
    binary = shutil.which("easycrypt", path=environment["PATH"])
    assert binary is not None
    user_config = tmp_path / "user-config" / "easycrypt" / "why3.conf"
    user_config.parent.mkdir(parents=True)
    user_config.write_text("user configuration must remain untouched\n")
    environment["XDG_CONFIG_HOME"] = str(user_config.parent.parent)
    # The override is confined to this test process's EC subprocess environment.
    # Production never changes HOME or XDG_CONFIG_HOME.
    local = tmp_path / "toolchain" / "why3.conf"
    _bind_config(monkeypatch, local)
    monkeypatch.setattr(ec_env, "managed_easycrypt_environment", lambda: dict(environment))
    before = user_config.stat().st_mtime_ns
    (tmp_path / "easycrypt.project").write_text(
        "[general]\nwhy3conf = /missing/conflicting-project-why3.conf\n"
    )
    monkeypatch.chdir(tmp_path)

    bootstrap._configure_solvers(Path(binary), environment)
    managed_before = (local.read_bytes(), local.stat().st_mtime_ns)
    assert ec_env.check_ec_available()[0]
    result = subprocess.run(
        ec_env.easycrypt_command("config"), env=ec_env.get_ec_env(),
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert str(local) in result.stdout + result.stderr
    assert ec_env.get_ec_env()["SHANNON_WHY3_CONFIG"] == str(local)
    assert (local.read_bytes(), local.stat().st_mtime_ns) == managed_before
    assert user_config.read_text() == "user configuration must remain untouched\n"
    assert user_config.stat().st_mtime_ns == before
