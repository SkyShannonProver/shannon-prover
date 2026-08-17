from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from workflow.proof_management.checkpoint_store import ProofCheckpointManager

# Agent-facing surfaces must never mention any resume/floor/prefix concept.
_RESUME_LEAK_RE = re.compile(
    r"crosses_resume_floor|resume_start|resume_local|resume handoff|"
    r"verified.*prefix|resume floor|resume boundary",
    re.IGNORECASE,
)


def _history_hash(tactics: list[str]) -> str:
    return hashlib.sha1("\n".join(tactics).encode("utf-8")).hexdigest()


def _confirmation_id(*parts: object) -> str:
    return hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]


def _checkpoint_payload(*, node_id: str = "Tree-unit") -> dict:
    return {
        "schema_version": 1,
        "kind": "proof_checkpoint_state",
        "node_id": node_id,
        "pre_rewind_restore_anchor": {
            "restore_id": "restore_current",
            "tactics": ["proc.", "wp."],
            "from_checkpoint_id": "cp_current",
            "from_tactic_index": 2,
        },
    }


def test_checkpoint_manager_tracks_rewind_confirmation() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )

    token = manager.rewind_confirmation_token(
        tactics=["proc.", "call H."],
        state_version=3,
        checkpoint_id="cp_2",
    )

    assert manager.is_rewind_confirmed(
        {"confirm": True, "confirmation_id": token},
        checkpoint_id="cp_2",
    )
    assert not manager.is_rewind_confirmed(
        {"confirm": True, "confirmation_id": token},
        checkpoint_id="cp_other",
    )

    manager.clear_rewind_confirmation()
    assert not manager.is_rewind_confirmed(
        {"confirm": True, "confirmation_id": token},
        checkpoint_id="cp_2",
    )


def test_rewind_confirm_survives_stale_token_for_same_checkpoint() -> None:
    # Panel-defect #2 (P0): the confirmation_id was bound to repl.state_version,
    # so after any intervening turn the token the agent was shown went stale and a
    # re-submitted confirm silently degraded to the menu (perceived no-op). A
    # confirm that carries the SAME checkpoint_id we asked the agent to confirm
    # must still be honored even if the version-bound token is now stale.
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    manager.rewind_confirmation_token(
        tactics=["proc.", "call H."],
        state_version=3,
        checkpoint_id="cp_2_abcd",
    )
    # Agent re-submits with a STALE/absent token but the correct checkpoint_id.
    assert manager.is_rewind_confirmed(
        {"confirm": True, "confirmation_id": "stale-token-from-an-older-version"},
        checkpoint_id="cp_2_abcd",
    )
    assert manager.is_rewind_confirmed(
        {"confirm": True},  # no token at all
        checkpoint_id="cp_2_abcd",
    )
    # A confirm for a DIFFERENT checkpoint is still rejected.
    assert not manager.is_rewind_confirmed(
        {"confirm": True},
        checkpoint_id="cp_9_zzzz",
    )
    # No confirm flag => never confirmed.
    assert not manager.is_rewind_confirmed(
        {"checkpoint_id": "cp_2_abcd"},
        checkpoint_id="cp_2_abcd",
    )


def test_checkpoint_manager_tracks_fresh_restart_confirmation() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )

    token = manager.fresh_restart_confirmation_token(
        tactics=["proc.", "wp."],
        state_version=4,
    )

    assert manager.is_fresh_restart_confirmed({
        "confirm": True,
        "confirmation_id": token,
    })
    assert not manager.is_fresh_restart_confirmed({
        "confirm": True,
        "confirmation_id": "wrong",
    })

    manager.clear_fresh_restart_confirmation()
    assert not manager.is_fresh_restart_confirmed({
        "confirm": True,
        "confirmation_id": token,
    })


def test_checkpoint_manager_tracks_restore_anchor() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )

    anchor = manager.save_pre_rewind_restore_anchor(
        tactics=["proc.", "wp."],
        checkpoint_id="cp_1",
        tactic_index=1,
        state_version=5,
    )

    assert anchor["restore_id"].startswith("restore_")
    assert manager.restore_anchor(anchor["restore_id"]) == anchor
    assert manager.restore_anchor("restore_wrong") == {}

    manager.clear_restore_anchor()
    assert manager.restore_anchor(anchor["restore_id"]) == {}


def test_checkpoint_manager_exposes_pre_rewind_restore_option() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )

    assert manager.pre_rewind_restore_option() == {}
    anchor = manager.save_pre_rewind_restore_anchor(
        tactics=["proc.", "wp."],
        checkpoint_id="cp_1",
        tactic_index=1,
        state_version=5,
    )
    option = manager.pre_rewind_restore_option()

    assert option["semantic_id"] == "restore_before_last_rewind"
    assert option["submit"] == {
        "intent": "undo_to_checkpoint",
        "payload": {"restore_id": anchor["restore_id"]},
    }


def test_checkpoint_manager_persists_only_current_restore_anchor(
    tmp_path: Path,
) -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        run_dir=tmp_path,
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    anchor = manager.save_pre_rewind_restore_anchor(
        tactics=["proc.", "wp."],
        checkpoint_id="cp_1",
        tactic_index=1,
        state_version=5,
    )
    sidecar = json.loads(
        (
            tmp_path
            / "checkpoint_state"
            / "Tree-unit_checkpoint_state.json"
        ).read_text(encoding="utf-8")
    )

    assert sidecar == {
        "schema_version": 1,
        "kind": "proof_checkpoint_state",
        "node_id": "Tree-unit",
        "pre_rewind_restore_anchor": anchor,
    }
    reloaded = ProofCheckpointManager(
        node_id="Tree-unit",
        run_dir=tmp_path,
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    assert reloaded.restore_anchor(anchor["restore_id"]) == anchor


def test_checkpoint_manager_ignores_retired_restore_option_payload() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    manager.seed_resume_payload({
        "schema_version": 1,
        "kind": "proof_checkpoint_state",
        "legacy_pre_rewind_restore_option": {
            "semantic_id": "restore_before_last_rewind",
        },
    })

    assert manager.pre_rewind_restore_option() == {}


def test_checkpoint_manager_seeds_only_exact_node_owned_payload() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )

    manager.seed_resume_payload(_checkpoint_payload())

    assert manager.restore_anchor("restore_current")["tactics"] == [
        "proc.",
        "wp.",
    ]


@pytest.mark.parametrize("schema_version", [None, "1", True, 0, 2])
def test_checkpoint_manager_requires_exact_schema_version(
    schema_version: object,
) -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    payload = _checkpoint_payload()
    if schema_version is None:
        payload.pop("schema_version")
    else:
        payload["schema_version"] = schema_version

    manager.seed_resume_payload(payload)

    assert manager.pre_rewind_restore_anchor == {}


def test_checkpoint_manager_rejects_wrong_node_and_unknown_outer_fields() -> None:
    for payload in (
        _checkpoint_payload(node_id="Tree-other"),
        {**_checkpoint_payload(), "legacy_restore_option": {}},
    ):
        manager = ProofCheckpointManager(
            node_id="Tree-unit",
            history_hash=_history_hash,
            confirmation_id=_confirmation_id,
        )

        manager.seed_resume_payload(payload)

        assert manager.pre_rewind_restore_anchor == {}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda anchor: anchor.pop("restore_id"),
        lambda anchor: anchor.update({"tactics": [7]}),
        lambda anchor: anchor.update({"from_tactic_index": True}),
        lambda anchor: anchor.update({"retired_alias": "cp_old"}),
    ],
)
def test_checkpoint_manager_rejects_malformed_restore_anchor(mutate) -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    payload = _checkpoint_payload()
    mutate(payload["pre_rewind_restore_anchor"])

    manager.seed_resume_payload(payload)

    assert manager.pre_rewind_restore_anchor == {}


def test_checkpoint_manager_builds_checkpoint_index() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )

    index = manager.build_index(
        menu_options=[{"checkpoint_id": "cp_1", "semantic_id": "before_seq_cut"}],
        structural_items=[{"checkpoint_id": "cp_2", "semantic_id": "after_seq_opened"}],
        restore_option={"restore_id": "restore_1", "semantic_id": "restore_before_last_rewind"},
    )

    assert index.menu_surface()[0]["restore_id"] == "restore_1"
    assert index.menu_surface()[1]["checkpoint_id"] == "cp_1"
    assert index.structural_surface()[0]["restore_id"] == "restore_1"
    assert index.structural_surface()[1]["checkpoint_id"] == "cp_2"
    assert index.restore_option is not None


def test_checkpoint_manager_builds_semantic_checkpoint_surfaces() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    tactics = [
        "byequiv=>//.",
        "proc.",
        "seq 1 1 : (={x}).",
        "call (_: inv).",
        "inline *.",
        "wp.",
    ]

    structural = manager.structural_surface(tactics)
    menu = manager.menu_options(tactics)

    structural_ids = {
        item["semantic_id"]
        for item in structural
        if item.get("semantic_id")
    }
    menu_ids = {
        item["semantic_id"]
        for item in menu
        if item.get("semantic_id")
    }
    assert "before_seq_cut" in structural_ids
    assert "after_call_opened" in menu_ids
    assert "after_call_opened" in structural_ids
    assert all(item["submit"]["intent"] == "undo_to_checkpoint" for item in structural)
    assert menu[0]["checkpoint_id"].startswith("cp_")
    assert manager.parse_checkpoint_id(menu[0]["checkpoint_id"]) is not None


def test_checkpoint_manager_owns_recovery_boundary_predicates() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    tactics = ["proc.", "seq 1 1 : P.", "wp.", "call H.", "auto."]

    assert manager.structural_recovery_available(tactics)
    assert manager.rewind_leaves_current_call_scope(tactics, 2)
    assert not manager.rewind_leaves_current_call_scope(tactics, 4)
    assert not manager.structural_recovery_available(["proc."])


def test_checkpoint_manager_renders_checkpoint_observations() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    index = manager.build_index(
        menu_options=[{"checkpoint_id": "cp_1", "label": "Before proc"}],
    )

    selection = manager.checkpoint_selection_observation(
        intent="undo_to_checkpoint",
        notice="stale checkpoint",
        checkpoint_index=index,
    )
    rewind = manager.checkpoint_rewind_observation(
        intent="undo_to_checkpoint",
        payload={"checkpoint_id": "cp_2"},
        tactic_index=2,
        committed_tactic="seq 1 1 : P.",
        committed_tactics=["proc.", "seq 1 1 : P.", "wp."],
    )
    restore = manager.checkpoint_restore_observation(
        intent="undo_to_checkpoint",
        payload={"restore_id": "restore_1"},
        anchor={"from_checkpoint_id": "cp_2"},
    )
    confirmation = manager.checkpoint_rewind_confirmation_observation(
        intent="undo_to_checkpoint",
        checkpoint={"checkpoint_id": "cp_2"},
    )

    assert selection["kind"] == "checkpoint_selection"
    assert selection["control_menu"]["items"][0]["checkpoint_id"] == "cp_1"
    assert selection["control_menu"]["notice"] == "stale checkpoint"
    assert rewind["kind"] == "checkpoint_rewind"
    assert rewind["undone_tactic_count"] == 2
    assert restore["kind"] == "checkpoint_restore"
    assert restore["restored_from"] == "cp_2"
    assert confirmation["kind"] == "checkpoint_rewind_confirmation"
    assert confirmation["control_menu"]["items"][0]["checkpoint_id"] == "cp_2"
    assert confirmation["control_menu"]["items"][1]["submit"]["intent"] == "undo_to_checkpoint"


def test_checkpoint_manager_renders_fresh_restart_observations() -> None:
    manager = ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    tactics = ["proc.", "seq 1 1 : P.", "wp.", "auto."]

    structural = manager.structural_recovery_observation(
        intent="fresh_restart",
        tactics=tactics,
        state_version=1,
        replay_prefix_count=0,
    )
    confirmation = manager.fresh_restart_confirmation_observation(
        intent="fresh_restart",
        tactics=tactics,
        state_version=2,
        replay_prefix_count=2,
        notice="resume restart disabled",
    )
    confirmed = manager.fresh_restart_confirmed_observation(
        intent="fresh_restart",
    )

    assert structural["kind"] == "structural_recovery_menu"
    assert structural["control_menu"]["items"]
    restart = structural["control_menu"]["items"][-1]["submit"]
    assert restart["intent"] == "fresh_restart"
    assert restart["payload"]["confirm"] is True
    assert confirmation["kind"] == "fresh_restart_confirmation"
    assert confirmation["control_menu"]["notice"] == "resume restart disabled"
    # Transparent resume: no agent-facing resume/prefix concept leaks into the
    # confirmation observation, and no "Return to resume start" option appears.
    assert "resume_prefix" not in confirmation
    assert all(
        option.get("label") != "Return to resume start"
        for option in confirmation["control_menu"]["items"]
    )
    assert not _RESUME_LEAK_RE.search(json.dumps(confirmation)), confirmation
    # The functional gate is preserved: with a replayed prefix present, the
    # destructive in-node fresh_restart option is still withheld.
    assert all(
        option["submit"]["intent"] != "fresh_restart"
        for option in confirmation["control_menu"]["items"]
    )
    assert confirmed["kind"] == "fresh_restart_confirmed"


# --- transparent resume: the replayed prefix is just ordinary history --------
#
# A resumed node replays a verified prefix internally, but the agent must
# perceive a SINGLE continuous proof it fully owns. The agent-facing surface
# therefore carries NO resume/floor/prefix concept: structural checkpoints
# inside the replayed prefix surface as ORDINARY checkpoints, rewindable like
# any other, and no item exposes a `crosses_resume_floor`/`resume_start`/
# `resume_local`/`upstream_resume_prefix` flag or label.

_RESUME_TACTICS = [
    "proc.",            # 1  replayed prefix
    "inline*.",         # 2  replayed prefix
    "call (_: inv).",   # 3  replayed prefix (structural boundary)
    "wp.",              # 4  replayed prefix
    "rnd.",             # 5  replayed prefix
    "auto.",            # 6  replayed prefix
    "seq 1: (m).",      # 7  post-resume
    "sp.",              # 8  post-resume
    "smt().",           # 9  post-resume
]
_RESUME_PREFIX_COUNT = 6


def _manager() -> ProofCheckpointManager:
    return ProofCheckpointManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )


def _assert_no_resume_framing(items: list[dict]) -> None:
    for item in items:
        # No resume-concept KEY anywhere in the agent-facing dict.
        assert "crosses_resume_floor" not in item, item
        assert item.get("undo_scope") != "resume_local", item
        assert item.get("undo_scope") != "upstream_resume_prefix", item
        assert "resume_start" not in (item.get("semantic_ids") or []), item
        assert item.get("semantic_id") != "resume_start", item
        assert "upstream_resume_prefix_repair" not in (
            item.get("semantic_ids") or []
        ), item
        # No resume-concept TEXT anywhere in the serialised dict.
        assert not _RESUME_LEAK_RE.search(json.dumps(item)), item


def test_resumed_surface_offers_prefix_checkpoints_as_ordinary() -> None:
    # The replayed-prefix structural boundaries (idx 2 inline, idx 3 call) are
    # surfaced as ORDINARY checkpoints, not suppressed and not floor-labelled.
    surface = _manager().structural_surface(
        _RESUME_TACTICS,
        replay_prefix_count=_RESUME_PREFIX_COUNT,
    )

    assert surface, "structural surface should be non-empty"
    _assert_no_resume_framing(surface)

    below = [i for i in surface if i["committed_step_index"] <= _RESUME_PREFIX_COUNT]
    assert below, "below-prefix structural checkpoints must still surface"
    # The call boundary inside the prefix (idx 3) is rewindable like any other.
    call_cp = next(i for i in below if i["committed_step_index"] == 3)
    assert call_cp["submit"]["intent"] == "undo_to_checkpoint"
    assert call_cp["submit"]["payload"]["checkpoint_id"]
    # Its scope is the ordinary structural scope, with no resume framing.
    assert call_cp.get("undo_scope") in {"call_local", "structural_boundary"}


def test_resumed_menu_options_carry_no_resume_framing() -> None:
    # The full rewind menu is identical in shape to a from-scratch run.
    options = _manager().menu_options(
        _RESUME_TACTICS,
        replay_prefix_count=_RESUME_PREFIX_COUNT,
    )

    assert options, "menu options should be non-empty"
    _assert_no_resume_framing(options)

    # The route-health repair still surfaces the in-prefix boundary as a normal
    # rewind target (the agent can rewind into the prefix), it just is not
    # labelled as crossing any floor.
    idx3 = [o for o in options if o["committed_step_index"] == 3]
    assert idx3, "in-prefix boundary at idx 3 still appears as a rewind option"
    for opt in idx3:
        assert opt["submit"]["intent"] == "undo_to_checkpoint"
        assert opt["submit"]["payload"]["checkpoint_id"]


def test_resumed_surface_matches_from_scratch_shape() -> None:
    # A resumed surface and a from-scratch surface over the same history expose
    # the same keys (no extra resume-only key appears when a prefix is present).
    resumed = _manager().structural_surface(
        _RESUME_TACTICS, replay_prefix_count=_RESUME_PREFIX_COUNT,
    )
    scratch = _manager().structural_surface(
        _RESUME_TACTICS, replay_prefix_count=0,
    )
    resumed_keys = {k for item in resumed for k in item}
    scratch_keys = {k for item in scratch for k in item}
    assert resumed_keys == scratch_keys, (resumed_keys ^ scratch_keys)
    _assert_no_resume_framing(resumed)
    _assert_no_resume_framing(scratch)
