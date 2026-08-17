from core.context_intents import (
    intent_payload_fields,
    intent_spec,
    persistent_control_catalog,
    persistent_control_specs,
)
from workflow.proof_state_compiler.runtime_profiles import allowed_runtime_intents
from workflow.proof_state_compiler.surface_profiles import CURRENT_SURFACE_PROFILES


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
    assert intent_payload_fields("amend_and_replay") == ("index", "tactic")
    assert intent_spec("amend_and_replay").advertised is True
    assert intent_spec("amend_and_replay").persistent_control is True


def test_persistent_control_catalog_drives_human_and_agent_labels() -> None:
    catalog = persistent_control_catalog()

    assert [item["intent"] for item in catalog] == [
        "commit_tactic",
        "undo_last_step",
        "undo_to_checkpoint",
        "fresh_restart",
        "amend_and_replay",
        "finish",
    ]
    assert catalog[0]["interaction"] == "input"
    assert catalog[0]["requires_input"] == ["tactic"]
    assert catalog[2]["label"] == "Rewind"
    assert catalog[4]["label"] == "Amend & replay"
    assert catalog[4]["requires_input"] == ["index", "tactic"]


def test_amend_and_replay_is_available_in_every_managed_profile() -> None:
    for profile in CURRENT_SURFACE_PROFILES:
        assert "amend_and_replay" in allowed_runtime_intents(profile)
