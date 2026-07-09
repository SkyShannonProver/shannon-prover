from __future__ import annotations

import json

from core.easycrypt.narrative_safety import (
    CLEAN_INPUT_MODE,
    RAW_INPUT_MODE,
    build_provenance,
    proof_stripped_text,
    sanitize_narrative_for_eval,
    validate_eval_narrative,
)
from workflow.tools.narrative_annotator import (
    _PROMPT_TEMPLATE,
    _prepare_annotator_input,
)


# Benchmark identifiers that must never be baked into the eval-facing annotator
# prompt. PR #7 decoupled the shared `test_no_compiler_lemma_hardcodes` guard
# from this template (it travels with the narrative change); the check is
# re-added here, in the narrative-owned test, so the annotator prompt stays
# benchmark-clean on its own.
_FORBIDDEN_PROMPT_EXAMPLES = (
    "ChaChaPoly",
    "chacha_poly",
    "OChaChaPoly",
    "I_stateless",
    "IFinRO",
    "pr_CCP_OCCP",
    "OpCCinit",
    "pr_RO_FinRO_D",
    "equ_cc",
    "UFCMA_genCC",
    "CCA_CPA_UFCMA",
    "poly_mac1",
    "poly_mac2",
    "chacha_enc1",
    "chacha_enc2",
)


def test_proof_stripped_input_removes_proof_only_tokens() -> None:
    raw = """
lemma foo : true.
proof.
  have secret_proof_only_token : true by trivial.
  exact secret_proof_only_token.
qed.

lemma bar :
  true
by exact/secret_short_token.

clone import T with type t <- int
proof *.
realize ax by exact/realize_secret.
"""
    stripped, count = proof_stripped_text(raw)

    assert count >= 3
    assert "secret_proof_only_token" not in stripped
    assert "secret_short_token" not in stripped
    assert "realize_secret" not in stripped
    assert "admit." in stripped


def test_annotator_default_input_is_proof_stripped() -> None:
    raw = """
lemma foo : true.
proof.
  exact proof_body_token.
qed.
"""
    annotator_input, proofs_replaced, mode = _prepare_annotator_input(
        raw,
        "proof-stripped",
    )

    assert mode == CLEAN_INPUT_MODE
    assert proofs_replaced == 1
    assert "proof_body_token" not in annotator_input


def test_eval_loader_rejects_legacy_raw_and_stale_narratives(tmp_path) -> None:
    source = tmp_path / "toy.ec"
    raw = "lemma foo : true.\nproof.\n  trivial.\nqed.\n"
    source.write_text(raw, encoding="utf-8")

    assert validate_eval_narrative({}, source)[0] is False

    raw_prov = build_provenance(
        raw_text=raw,
        annotator_input_text=raw,
        input_mode=RAW_INPUT_MODE,
        proofs_replaced=0,
        model="test-model",
        annotator_version="test",
    )
    assert validate_eval_narrative({"provenance": raw_prov}, source)[0] is False

    stripped, replaced = proof_stripped_text(raw)
    clean_prov = build_provenance(
        raw_text=raw,
        annotator_input_text=stripped,
        input_mode=CLEAN_INPUT_MODE,
        proofs_replaced=replaced,
        model="test-model",
        annotator_version="test",
    )
    assert validate_eval_narrative({"provenance": clean_prov}, source) == (True, "ok")

    raw_with_different_proof = (
        "lemma foo : true.\nproof.\n  have proof_body_changed : true by trivial.\n"
        "  exact proof_body_changed.\nqed.\n"
    )
    source.write_text(raw_with_different_proof, encoding="utf-8")
    assert validate_eval_narrative({"provenance": clean_prov}, source) == (True, "ok")

    source.write_text(raw + "\nlemma new_stmt : true.\n", encoding="utf-8")
    ok, reason = validate_eval_narrative({"provenance": clean_prov}, source)
    assert ok is False
    assert "hash_mismatch" in reason


def test_eval_sanitizer_removes_target_route_fields() -> None:
    narrative = {
        "proof_strategy_overview": "target route",
        "lemma_catalog": [
            {
                "name": "target",
                "role": "main_reduction",
                "hop": ["G0", "G1"],
                "narrative": "do exact route",
                "semantic_delta": "route",
                "rewrite_form": "rewrite target_bridge.",
                "closer_hints": {"typical_tail": "smt()."},
                "call_template": "call H.",
            },
            {
                "name": "bridge",
                "role": "bridge_lemma",
                "semantic_delta": "statement-derived delta",
                "rewrite_form": "rewrite bridge.",
                "closer_hints": {"typical_tail": "smt()."},
            },
        ],
    }

    clean = sanitize_narrative_for_eval(json.loads(json.dumps(narrative)), "target")
    target = clean["lemma_catalog"][0]
    bridge = clean["lemma_catalog"][1]

    assert "proof_strategy_overview" not in clean
    assert set(target) == {"name", "role", "hop", "eval_note"}
    assert "closer_hints" not in bridge
    assert "rewrite_form" not in bridge


def test_annotator_prompt_template_has_no_benchmark_examples() -> None:
    offenders = [name for name in _FORBIDDEN_PROMPT_EXAMPLES if name in _PROMPT_TEMPLATE]
    assert offenders == [], f"benchmark identifiers leaked into annotator prompt: {offenders}"
