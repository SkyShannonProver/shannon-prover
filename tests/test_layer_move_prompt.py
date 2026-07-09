"""Tests for layer-move actions in child prover prompts."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.agents.prover_prompt import _build_child_prover_prompt  # noqa: E402


def _common_args() -> dict:
    return dict(
        file_path="artifacts/live_smoke/step1/chacha_poly.ec",
        lemma_name="step1",
        include_dir="easycrypt-src/theories",
        session_tag="prover_tree_0_0_0",
        replay_prefix=["proc.", "wp."],
        negative_signal=["apply (pr_RO_FinRO_D G2 &m)."],
    )


def test_no_layer_move_action_means_no_layer_move_section() -> None:
    prompt = _build_child_prover_prompt(**_common_args())
    assert "Layer-move action" not in prompt


def test_layer_move_action_injects_layer_move_experiment() -> None:
    action = {
        "kind": "layer_move_action",
        "current_layer": "pr",
        "move": "down",
        "move_label": "move to a lower abstraction layer",
        "focus": [
            "commit to pRHL/call rather than another Pr rewrite",
            "preserve call sites when oracle equivalences may apply",
        ],
        "first_failed_tactic": "have := MainD(G2, FinRO).distinguish(()).",
        "failed_experiment": {
            "experiment_kind": "bridge_rewrite",
            "failure_shape": "wrong_number_of_arguments",
            "subject": "MainD",
            "count": 2,
            "sample_tactics": [
                "have := MainD(G2, FinRO).distinguish(()).",
                "have H := MainD(G2, FinRO).distinguish(()).",
            ],
        },
    }
    prompt = _build_child_prover_prompt(
        **_common_args(),
        layer_move_action=action,
    )
    assert "Layer-move action" in prompt
    assert "current `pr` proof layer" in prompt
    assert "move to a lower abstraction layer" in prompt
    assert "bridge_rewrite" in prompt
    assert "wrong_number_of_arguments" in prompt
    assert "MainD" in prompt


def test_layer_move_action_is_explicitly_not_policy_verdict() -> None:
    action = {
        "kind": "layer_move_action",
        "current_layer": "procedure",
        "move": "up",
        "move_label": "move to a higher abstraction layer",
        "focus": ["look for a Pr-level pivot"],
    }
    prompt = _build_child_prover_prompt(
        **_common_args(),
        layer_move_action=action,
    )
    # The layer-move is a non-binding search hint, never a policy verdict the
    # child must obey — it must explicitly defer to EasyCrypt / the actual goal.
    assert "non-binding search hint" in prompt
    assert "not a proof fact, a verdict, or an instruction" in prompt
    assert "EasyCrypt is the authority" in prompt
    assert "move to a higher abstraction layer" in prompt


def test_failed_experiment_memory_truncates_samples() -> None:
    action = {
        "kind": "layer_move_action",
        "current_layer": "pr",
        "move": "same",
        "move_label": "try a distinct strategy at the current abstraction layer",
        "failed_experiment": {
            "experiment_kind": "bridge_rewrite",
            "failure_shape": "wrong_number_of_arguments",
            "subject": "MainD",
            "count": 10,
            "sample_tactics": [f"have variant_{i}." for i in range(10)],
        },
    }
    prompt = _build_child_prover_prompt(
        **_common_args(),
        layer_move_action=action,
    )
    assert "variant_0" in prompt
    assert "variant_1" in prompt
    assert "variant_2" in prompt
    assert "variant_5" not in prompt
    assert "variant_9" not in prompt


def test_layer_move_prompt_includes_proof_ir_slice() -> None:
    action = {
        "kind": "layer_move_action",
        "current_layer": "call",
        "move": "down",
        "move_label": "move to a lower abstraction layer",
        "proof_ir_slice": {
            "move": "down",
            "current_layer": "call_site",
            "goal_kind": "pRHL",
            "liveness": {
                "live_call_site_count": 2,
                "live_callable_lemma_count": 1,
            },
            "phase": {
                "prefer": ["use wp/seq to expose frontier"],
                "avoid": ["inline * before live handles"],
            },
            "program_action_plans": [{
                "procedure_tail": "Poly.mac",
                "phase_order": [{
                    "kind": "expose_last_call_frontier",
                    "tactic_hint": "wp.",
                    "reason": "not frontier",
                }, {
                    "kind": "call_named_equiv",
                    "tactic_template": "call poly_mac1.",
                    "reason": "consume handle",
                }],
            }],
            "callable_lemmas": [{
                "lemma": "poly_mac1",
                "procedure": "Poly.mac",
                "frontier_status": "requires_cut",
                "repair_hint": "Expose Poly.mac first.",
            }],
        },
    }
    prompt = _build_child_prover_prompt(
        **_common_args(),
        layer_move_action=action,
    )
    assert "ProofIR Slice for This Child" in prompt
    assert "Program action plan candidates" in prompt
    assert "call poly_mac1." in prompt
    assert "Live callable lemma handles" in prompt


def test_probability_budget_child_prompt_does_not_ban_all_seq() -> None:
    args = _common_args()
    args["negative_signal"] = [
        "seq 11 : (size G3.cilog <= PKE_.qD) "
        "((PKE_.qD%r / order%r) ^ 3)."
    ]
    args["parent_goal_state"] = """
Current goal
Bound   : [<=] ((PKE_.qD%r / order%r) ^ 3) * (PKE_.qD%r / (order - 1)%r)
post = (G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog
"""

    prompt = _build_child_prover_prompt(**args)

    # The probability-budget signal is a neutral structural FACT, never a ban:
    # it must defer to EasyCrypt and must not forbid `seq`/`call` outright.
    assert "not a ban" in prompt
    assert "EasyCrypt is the authority" in prompt
    assert "Do not repeat this exact failed shape" not in prompt
    assert "Do NOT use `seq` or any variation" not in prompt


def main() -> int:
    tests = [
        test_no_layer_move_action_means_no_layer_move_section,
        test_layer_move_action_injects_layer_move_experiment,
        test_layer_move_action_is_explicitly_not_policy_verdict,
        test_failed_experiment_memory_truncates_samples,
        test_layer_move_prompt_includes_proof_ir_slice,
        test_probability_budget_child_prompt_does_not_ban_all_seq,
    ]
    for t in tests:
        t()
    print("PASS test_layer_move_prompt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
