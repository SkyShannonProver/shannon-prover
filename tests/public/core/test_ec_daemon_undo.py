"""F2: the daemon's committed EasyCrypt process rewinds with ``undo <level>.``.

Pins the lexical rule for commands ``undo`` cannot revert, and on a real
``ECSubprocess`` (skipped without the managed toolchain): the recorded undo
levels, the restored state after a rewind, every refusal (which must leave
the process untouched), desynchronization when EasyCrypt does not report the
recorded level and mode, and the pre-commit level after a rejected
transaction.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

from core.easycrypt.committed_history import committed_prefix_identity  # noqa: E402
from core.easycrypt.ec_env import get_ec_env  # noqa: E402
from core.easycrypt.proof_text import undo_unsafe_sentence  # noqa: E402
from core.easycrypt.session.session_display import compress_current_state  # noqa: E402

try:
    _MANAGED_EC_AVAILABLE = shutil.which(
        "easycrypt", path=get_ec_env().get("PATH")
    ) is not None
except RuntimeError:
    _MANAGED_EC_AVAILABLE = False

needs_ec = pytest.mark.skipif(
    not _MANAGED_EC_AVAILABLE,
    reason="repository-managed EasyCrypt is unavailable",
)


# ---------------------------------------------------------------------------
# Commands undo cannot revert
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("transaction", "unsafe"),
    [
        ("pragma Proofs:weak. auto.", "pragma Proofs:weak."),
        ("auto. pragma +PP:showtvi.", "pragma +PP:showtvi."),
        ("pragma x = 3.", "pragma x = 3."),
        ("undo 3.", "undo 3."),
        ("move=> h. (* pragma *) auto.", ""),
        ("+ smt().", ""),
        ("proc; inline *.", ""),
        ("apply pragma_lemma.", ""),
        ("pragmatic.", ""),
    ],
)
def test_undo_unsafe_sentence_is_the_pragma_or_level_command(
    transaction: str, unsafe: str,
) -> None:
    assert undo_unsafe_sentence(transaction) == unsafe


# ---------------------------------------------------------------------------
# ECSubprocess (real EasyCrypt)
# ---------------------------------------------------------------------------

_EC_SOURCE = """\
require import AllCore.

lemma f2_chain (a b c : bool) : a => b => c => a /\\ b /\\ c.
proof.
"""
_CHAIN = ["move=> ha.", "move=> hb.", "move=> hc.", "split; first assumption.", "by split."]


@pytest.fixture
def ec(tmp_path: Path):
    from core.easycrypt.ec_daemon import ECSubprocess

    source = tmp_path / "f2.ec"
    source.write_text(_EC_SOURCE + "qed.\n", encoding="utf-8")
    process = ECSubprocess([str(ROOT / "easycrypt-src" / "theories")], None)
    process.spawn()
    process.load_context_and_enter_proof(source, "f2_chain")
    yield process
    process.close()


def _identity(ec, keep: int) -> str:
    return committed_prefix_identity(ec._committed_requests[:keep])


@pytest.mark.easycrypt
@needs_ec
def test_levels_rise_per_transaction_and_rewind_restores_each(ec) -> None:
    outputs = []
    for tactic in _CHAIN:
        outcome = ec.execute(tactic)
        assert outcome.accepted
        outputs.append(outcome.raw_output)
    levels = [entry.level for entry in ec._levels]
    assert levels == sorted(set(levels)) and len(levels) == len(_CHAIN) + 1
    assert ec._levels[-1].open_goal is False   # by split. closed the goal
    for keep in (4, 2, 0):
        held = ec._committed_requests[:]
        result = ec.rewind(
            keep,
            keep_identity=_identity(ec, keep),
            held_identity=committed_prefix_identity(held),
        )
        assert result["undone"] == len(held) - keep
        assert result["level"] == levels[keep]
        assert ec.committed_count == keep
        assert ec._committed_tactics == [t for t in _CHAIN[:keep]]
        if keep:
            # Same compressed state as the commit that first reached it.
            assert compress_current_state(result["raw"]) == compress_current_state(
                outputs[keep - 1]
            )
        for tactic in _CHAIN[keep:]:
            assert ec.execute(tactic).accepted
        assert [entry.level for entry in ec._levels] == levels


@pytest.mark.easycrypt
@needs_ec
def test_rewind_refuses_without_touching_the_process(ec) -> None:
    from core.easycrypt.ec_daemon import RewindRefused

    for tactic in _CHAIN:
        ec.execute(tactic)
    prompt = ec._prompt
    cases = [
        dict(keep=2, keep_identity="0" * 64),
        dict(keep=9, keep_identity=_identity(ec, 2)),
        dict(keep=2, keep_identity=_identity(ec, 2), held_identity="0" * 64),
        # The state after all five commands shows no open goal.
        dict(keep=5, keep_identity=_identity(ec, 5), require_open_goal=True),
    ]
    reasons = []
    for kwargs in cases:
        keep = kwargs.pop("keep")
        with pytest.raises(RewindRefused) as refused:
            ec.rewind(keep, **kwargs)
        reasons.append(str(refused.value))
    assert reasons == [
        "keep_identity_mismatch",
        "keep_out_of_range",
        "held_identity_mismatch",
        "target_state_has_no_open_goal",
    ]
    assert ec._prompt == prompt and not ec.desynchronized
    assert ec.committed_count == len(_CHAIN)


@pytest.mark.easycrypt
@needs_ec
def test_level_or_mode_mismatch_after_undo_desynchronizes(ec) -> None:
    from core.easycrypt.ec_daemon import _Level

    for tactic in _CHAIN[:3]:
        ec.execute(tactic)
    target = ec._levels[1]
    ec._levels[1] = _Level(target.level, "weakcheck", True, True)
    with pytest.raises(RuntimeError, match="session discarded"):
        ec.rewind(1, keep_identity=_identity(ec, 1))
    assert ec.desynchronized


@pytest.mark.easycrypt
@needs_ec
def test_rejected_transaction_returns_to_its_pre_commit_level(ec) -> None:
    ec.execute(_CHAIN[0])
    before = ec._prompt
    outcome = ec.execute("move=> hb. bogus_f2_tactic.")
    assert not outcome.accepted
    assert ec._prompt == before and not ec.desynchronized
    assert ec.committed_count == 1
    # The next commit sees the pre-commit state: hb is not yet introduced.
    assert ec.execute(_CHAIN[1]).accepted


@pytest.mark.easycrypt
@needs_ec
def test_rejected_transaction_with_a_pragma_discards_the_session(ec) -> None:
    ec.execute(_CHAIN[0])
    outcome = ec.execute("pragma Proofs:weak. bogus_f2_tactic.")
    assert not outcome.accepted
    assert ec.desynchronized


@pytest.mark.easycrypt
@needs_ec
def test_pragma_transaction_is_recorded_as_not_undoable(ec) -> None:
    from core.easycrypt.ec_daemon import RewindRefused

    ec.execute(_CHAIN[0])
    assert ec.execute(f"pragma Proofs:weak. {_CHAIN[1]}").accepted
    assert ec._levels[-1].undoable is False
    assert ec._levels[-1].mode == "weakcheck"
    with pytest.raises(RewindRefused, match="transaction_2_not_undoable"):
        ec.rewind(1, keep_identity=_identity(ec, 1))
