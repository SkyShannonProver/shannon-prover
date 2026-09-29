from __future__ import annotations

from core.easycrypt.tactic_envelope import extract_structural_tactic_envelope


def test_byequiv_closing_tactical_is_outside_relation_core() -> None:
    tactic = (
        "byequiv (_: ={glob A} ==> res{1} => res{2} \\/ Bad P.logP{2} F.m{2})"
        "=> //."
    )

    envelope = extract_structural_tactic_envelope(tactic)

    assert envelope.exact is True
    assert envelope.head == "byequiv"
    assert envelope.core.endswith("F.m{2})")
    assert envelope.continuation == "=> //."
    assert envelope.raw_tactic == tactic


def test_call_branch_tactical_is_outside_call_contract() -> None:
    tactic = (
        "+ 1: call (_: SampleB.bad, ={SampleB.bad}, ={SampleB.bad}); "
        "1: apply A_ll."
    )

    envelope = extract_structural_tactic_envelope(tactic)

    assert envelope.exact is True
    assert envelope.leading_control == "+ 1:"
    assert envelope.head == "call"
    assert envelope.core == "call (_: SampleB.bad, ={SampleB.bad}, ={SampleB.bad})"
    assert envelope.continuation == "; 1: apply A_ll."


def test_period_terminated_call_keeps_following_branch_outside_core() -> None:
    tactic = "call (_: ={glob Log, glob LRO}). + proc; inline *; auto."

    envelope = extract_structural_tactic_envelope(tactic)

    assert envelope.exact is True
    assert envelope.core == "call (_: ={glob Log, glob LRO})."
    assert envelope.continuation == "+ proc; inline *; auto."


def test_one_sided_call_keeps_side_selector_in_structural_core() -> None:
    tactic = "call{1} (_: true ==> true); 1: by islossless."

    envelope = extract_structural_tactic_envelope(tactic)

    assert envelope.exact is True
    assert envelope.head == "call"
    assert envelope.core == "call{1} (_: true ==> true)"
    assert envelope.continuation == "; 1: by islossless."


def test_compact_relation_suffix_is_split_at_top_level_arrow() -> None:
    envelope = extract_structural_tactic_envelope(
        "byequiv: Game.bad=> //=; 2:smt ml=0."
    )

    assert envelope.exact is True
    assert envelope.core == "byequiv: Game.bad"
    assert envelope.continuation == "=> //=; 2:smt ml=0."


def test_colon_payload_and_control_contract_stay_in_relation_core() -> None:
    tactic = (
        "byequiv (: true ==> ={Game.bad} /\\ (!Game.bad{2} => ={res})) "
        ": Game.bad => //."
    )

    envelope = extract_structural_tactic_envelope(tactic)

    assert envelope.exact is True
    assert envelope.head == "byequiv"
    assert envelope.core.endswith(": Game.bad")
    assert envelope.continuation == "=> //."


def test_colon_payload_without_control_contract_is_balanced() -> None:
    tactic = "byequiv (: ={glob A} ==> ={res}) => //."

    envelope = extract_structural_tactic_envelope(tactic)

    assert envelope.exact is True
    assert envelope.core == "byequiv (: ={glob A} ==> ={res})"
    assert envelope.continuation == "=> //."


def test_unbalanced_structural_payload_is_not_guessed() -> None:
    tactic = "call (_: Game.bad, ={Game.bad}; 1: apply A_ll."

    envelope = extract_structural_tactic_envelope(tactic)

    assert envelope.exact is False
    assert envelope.core == tactic
    assert envelope.continuation == ""


def test_compound_command_without_contract_keeps_followup_as_continuation() -> None:
    envelope = extract_structural_tactic_envelope("proc; while (={i}).")

    assert envelope.exact is True
    assert envelope.head == "proc"
    assert envelope.core == "proc"
    assert envelope.continuation == "; while (={i})."


def test_later_structural_payload_is_not_claimed_by_leading_command() -> None:
    tactic = (
        "+ byequiv=> //=; conseq (_: ={glob D} ==> ={res}) "
        "(_: true ==> D.c <= q)=> //=."
    )

    envelope = extract_structural_tactic_envelope(tactic)

    assert envelope.exact is True
    assert envelope.head == "byequiv"
    assert envelope.core == "byequiv"
    assert envelope.continuation.startswith("=> //=; conseq")


def test_multi_argument_conseq_keeps_all_arguments_in_core() -> None:
    tactic = (
        "conseq (: ={glob A} ==> ={Vars.log} /\\ "
        "(res{1} => collision Vars.log{2})) _ hinv => //."
    )

    envelope = extract_structural_tactic_envelope(tactic)

    assert envelope.exact is True
    assert envelope.head == "conseq"
    assert envelope.core.endswith("_ hinv")
    assert envelope.continuation == "=> //."
