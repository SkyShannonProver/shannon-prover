from core.context_intents import (
    intent_spec,
    persistent_control_specs,
)
from workflow.proof_state_compiler.runtime_profiles import (
    allowed_runtime_intents,
    current_surface_profile_names,
)


def test_persistent_control_catalog_is_registry_owned() -> None:
    specs = persistent_control_specs()

    assert [spec.name for spec in specs] == [
        "commit_tactic",
        "undo_last_step",
        "undo_to_checkpoint",
        "fresh_restart",
        "amend_and_replay",
        "finish",
    ]
    assert specs[0].control_requires_input == ("tactic",)
    assert specs[2].control_interaction == "menu"
    assert specs[4].control_requires_input == ("index", "tactic")


def test_amend_and_replay_payload_matches_the_executor_contract() -> None:
    assert intent_spec("amend_and_replay").payload_fields == ("index", "tactic")
    assert intent_spec("amend_and_replay").advertised is True
    assert intent_spec("amend_and_replay").persistent_control is True


def test_persistent_controls_carry_the_rendered_labels() -> None:
    specs = persistent_control_specs()

    assert specs[0].control_interaction == "input"
    assert specs[2].display_label == "Rewind"
    assert specs[4].display_label == "Amend & replay"


def test_amend_and_replay_is_available_in_every_managed_profile() -> None:
    for profile in current_surface_profile_names():
        assert "amend_and_replay" in allowed_runtime_intents(profile)
