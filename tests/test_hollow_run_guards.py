"""Regression tests for the hollow-run guards (Layer A).

A "hollow run" is when a target file fails to load (e.g. a missing `require`d
theory) so the lemma never opens: EC stays at top level, the agent submits
tactics into a REPL with no proof, every one errors `cannot process [proof
script] outside a proof script`, and the whole budget burns on a fake proof.

Two independent guards must keep catching it:
  * eval_suite.run._preflight_target_loads — compile-check at launch.
  * workflow.agents.prover._bootstrap_opened_real_proof — runtime backstop.
"""
from __future__ import annotations

import json
import subprocess
import types

import pytest

from core.easycrypt.eval_source_prep import (
    assert_unique_eval_target,
    prepare_eval_source,
    replace_target_proof_with_admit,
)
from core.easycrypt.lemma_decls import lemma_decl_lines
from eval_suite import run as suite_run
from workflow.agents.prover import _bootstrap_opened_real_proof


# ── bootstrap guard (pure logic, no EC) ──────────────────────────────────────

_HOLLOW_VIEW = {
    "workspace_view": {
        "proof_status": {"status": "unknown", "remaining_goals_known": False},
        "current_goal": {"lines": ["[12|check]>"]},
    }
}
_HEALTHY_VIEW = {
    "workspace_view": {
        "proof_status": {"status": "open", "remaining_goals_known": True},
        "current_goal": {"lines": ["pre =", "  ={glob H}", "post ="]},
    }
}


def test_bootstrap_guard_blocks_hollow():
    assert _bootstrap_opened_real_proof(_HOLLOW_VIEW) is False


def test_bootstrap_guard_passes_healthy_open_proof():
    assert _bootstrap_opened_real_proof(_HEALTHY_VIEW) is True


def test_bootstrap_guard_passes_complete_proof_with_count():
    # remaining_goals_known=True even at 0 goals => real (complete) proof.
    bs = {"workspace_view": {"proof_status": {
        "status": "unknown", "remaining_goals_known": True}}}
    assert _bootstrap_opened_real_proof(bs) is True


@pytest.mark.parametrize("bs", [{}, {"workspace_view": {}},
                                {"workspace_view": {"proof_status": {}}}])
def test_bootstrap_guard_fails_open_on_unknown_schema(bs):
    # Must never block when it cannot read the signal (preflight is primary).
    assert _bootstrap_opened_real_proof(bs) is True


# ── preflight (monkeypatched EC invocation) ──────────────────────────────────

def _cmd(ec_file: str) -> list[str]:
    return ["python", "-m", "workflow.orchestrator", "--file", ec_file,
            "--lemma", "L", "--include-dir", "easycrypt-src/theories"]


@pytest.fixture
def ec_file(tmp_path):
    f = tmp_path / "T.ec"
    f.write_text("lemma L: true. proof. trivial. qed.\n")
    return str(f)


def _patch_ec(monkeypatch, *, stdout="", returncode=0, raises=None):
    monkeypatch.setattr(
        "core.easycrypt.ec_env.get_ec_env", lambda: {}, raising=True)

    def fake_run(*a, **k):
        if raises is not None:
            raise raises
        return types.SimpleNamespace(stdout=stdout, stderr="",
                                     returncode=returncode)

    monkeypatch.setattr(suite_run.subprocess, "run", fake_run)


def test_preflight_blocks_missing_theory(monkeypatch, ec_file):
    _patch_ec(monkeypatch,
              stdout="[critical] In external theory Schemes: cannot locate "
                     "theory ABitstring",
              returncode=1)
    ok, reason = suite_run._preflight_target_loads(_cmd(ec_file))
    assert ok is False
    assert "failed to load" in reason


def test_preflight_passes_clean_compile(monkeypatch, ec_file):
    _patch_ec(monkeypatch, stdout="", returncode=0)
    ok, _ = suite_run._preflight_target_loads(_cmd(ec_file))
    assert ok is True


def test_preflight_tolerates_admit_warnings(monkeypatch, ec_file):
    # Non-zero rc but no [error/[critical line (e.g. proof-stripped admits) is
    # NOT a load failure.
    _patch_ec(monkeypatch,
              stdout="[warning] proof script contains admit", returncode=1)
    ok, _ = suite_run._preflight_target_loads(_cmd(ec_file))
    assert ok is True


def test_preflight_fails_open_when_easycrypt_missing(monkeypatch, ec_file):
    _patch_ec(monkeypatch, raises=FileNotFoundError())
    ok, reason = suite_run._preflight_target_loads(_cmd(ec_file))
    assert ok is True


def test_preflight_fails_open_on_timeout(monkeypatch, ec_file):
    _patch_ec(monkeypatch, raises=subprocess.TimeoutExpired("easycrypt", 1))
    ok, _ = suite_run._preflight_target_loads(_cmd(ec_file))
    assert ok is True


def test_preflight_blocks_missing_target_file():
    ok, reason = suite_run._preflight_target_loads(_cmd("/no/such/file.ec"))
    assert ok is False
    assert "not found" in reason


# ── duplicate-lemma guard (ambiguous eval target) ────────────────────────────
#
# A lemma name declared more than once in the target file makes the run
# silently unwinnable: source prep, goal-open, proof write-back, and the
# post-verify admit check all locate the lemma BY NAME, so they can resolve to
# different declarations (observed: `xorK1` declared in both `theory Byte` and
# `abstract theory GenBlock` of ChaChaPoly/chacha_poly.ec, 2026-06-11 — the
# proof closed in-session, then the admit check matched the OTHER declaration
# and reverted it). The suite must fail fast at preparation instead.

_DUP_LEMMA_EC = """\
theory Byte.
  lemma xorK1 b1 b2 : b1 = b1 +^ b2 +^ b2.
  proof.
    admit.
  qed.
end Byte.

abstract theory GenBlock.
  lemma addK b : b +^ b = zero.
  proof. trivial. qed.

  lemma xorK1 b1 b2 : b1 = b1 +^ b2 +^ b2.
  proof.
    admit.
  qed.
end GenBlock.
"""


def test_lemma_decl_lines_finds_all_duplicates():
    assert lemma_decl_lines(_DUP_LEMMA_EC, "xorK1") == [2, 12]
    assert lemma_decl_lines(_DUP_LEMMA_EC, "addK") == [9]


def test_lemma_decl_lines_ignores_commented_out_and_prefix_names():
    content = (
        "(* lemma xorK1 old : true.\n   proof. admit. qed. *)\n"
        "lemma xorK1 b : b = b.\n"
        "proof. admit. qed.\n"
        "lemma xorK1_alt b : b = b.\n"
        "proof. admit. qed.\n"
    )
    assert lemma_decl_lines(content, "xorK1") == [3]


def test_eval_source_prep_rejects_duplicate_lemma_declarations(tmp_path):
    f = tmp_path / "dup.ec"
    f.write_text(_DUP_LEMMA_EC)
    with pytest.raises(ValueError) as exc:
        assert_unique_eval_target(f, "xorK1")
    msg = str(exc.value)
    assert "declared 2 times" in msg
    assert "lines 2, 12" in msg
    # The file must be left untouched — no partial source prep.
    assert f.read_text() == _DUP_LEMMA_EC


def test_eval_source_prep_rejects_proved_duplicates_in_local_sections(tmp_path):
    """Second real-world shape (`local_conclusion` in MEE-CBC's
    MAC_then_Pad_then_CBC.eca, 2026-06-11): the duplicates have DIFFERENT
    statements, live in two different local sections, and both are fully
    PROVED. Without the guard the target name can bind to one declaration at
    source-prep time and another declaration at write-back/no-admit time,
    causing false skips or false admit failures.
    The guard must fire on this shape before any source prep happens.
    """
    content = (
        "section A.\n"
        "  local lemma conclusion &m: Pr[G1.main() @ &m : res] <= e1.\n"
        "  proof. by apply (B1 &m). qed.\n"
        "end section.\n"
        "section B.\n"
        "  local lemma conclusion &m: Pr[G2.main() @ &m : res] <= e2.\n"
        "  proof. by apply (B2 &m). qed.\n"
        "end section.\n"
    )
    f = tmp_path / "mte.eca"
    f.write_text(content)
    with pytest.raises(ValueError, match="declared 2 times"):
        assert_unique_eval_target(f, "conclusion")
    assert f.read_text() == content  # no partial source prep → no false-skip bait


def test_legacy_single_target_admit_replacement_still_uses_core_helper(tmp_path):
    f = tmp_path / "ok.ec"
    f.write_text(
        "lemma L b : b = b.\n"
        "proof.\n"
        "  trivial.\n"
        "qed.\n"
    )
    assert replace_target_proof_with_admit(f, "L") is True
    out = f.read_text()
    assert "admit." in out
    assert "trivial." not in out


def test_eval_source_prep_strips_target_and_sibling_files(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    target = root / "Main.ec"
    sibling = root / "Helper.eca"
    target.write_text(
        "require Helper.\n"
        "lemma Target : true.\n"
        "proof.\n"
        "  trivial.\n"
        "qed.\n",
        encoding="utf-8",
    )
    sibling.write_text(
        "lemma HelperLemma : true.\n"
        "proof.\n"
        "  trivial.\n"
        "qed.\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = prepare_eval_source(
        source_file=target,
        target_lemma="Target",
        output_dir=out,
        copy_root=root,
        strip_proofs=True,
    )
    prepared_target = result.isolated_file.read_text(encoding="utf-8")
    prepared_sibling = (result.isolated_root / "Helper.eca").read_text(encoding="utf-8")
    assert "trivial." not in prepared_target
    assert "trivial." not in prepared_sibling
    assert prepared_target.count("admit.") == 1
    assert prepared_sibling.count("admit.") == 1
    assert result.manifest["source_contract"] == "proof_stripped_project"
    assert result.manifest["stripped_file_count"] == 2
    assert result.manifest["proofs_replaced_total"] == 2


def test_suite_skips_duplicate_lemma_target_and_records_status(tmp_path):
    """End-to-end through main(): a duplicate-lemma target is skipped with a
    `prepare_failed` eval_metrics record and rc=2 — the suite never launches
    the prover (no EC subprocess is reached: prepare fails before preflight).
    """
    fixture = tmp_path / "dup.ec"
    fixture.write_text(_DUP_LEMMA_EC)
    out_root = tmp_path / "out"
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({
        "suite": "dup_suite",
        "profiles": ["l1_goal_projection"],
        "defaults": {"output_dir": str(out_root)},
        "targets": [
            {"id": "t_dup", "lemma": "xorK1", "file": str(fixture)},
        ],
    }))
    rc = suite_run.main(["--suite", str(suite)])
    assert rc == 2
    metrics = json.loads(
        (out_root / "dup_suite" / "l1_goal_projection" / "t_dup" / "r01"
         / "eval_metrics.json").read_text())
    assert metrics["status"] == "prepare_failed"
    assert "declared 2 times" in metrics["reason"]
    assert metrics["lemma"] == "xorK1"
