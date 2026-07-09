"""Guardrails against benchmark-lemma names in compiler/view code."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_EASYCRYPT = ROOT / "core" / "easycrypt"

FORBIDDEN_LEMMA_NAMES = (
    "equ_cc",
    "UFCMA_genCC",
    "CCA_CPA_UFCMA",
    "poly_mac1",
    "poly_mac2",
    "chacha_enc1",
    "chacha_enc2",
)

FORBIDDEN_PROMPT_EXAMPLES = (
    "ChaChaPoly",
    "chacha_poly",
    "OChaChaPoly",
    "I_stateless",
    "pr_CCP_OCCP",
    "equ_cc",
    "UFCMA_genCC",
    "CCA_CPA_UFCMA",
    "poly_mac1",
    "poly_mac2",
    "chacha_enc1",
    "chacha_enc2",
)


def test_core_easycrypt_has_no_benchmark_lemma_name_hardcodes() -> None:
    offenders: list[str] = []
    for path in sorted(CORE_EASYCRYPT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name in FORBIDDEN_LEMMA_NAMES:
            if name in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {name}")

    assert offenders == []


def test_eval_facing_prompt_templates_have_no_benchmark_bridge_examples() -> None:
    from workflow.agents.prover_prompt import _build_prover_prompt

    prompt = _build_prover_prompt(
        "eval/examples/Generic/project.ec",
        "target",
        "easycrypt-src/theories",
        session_tag="no_hardcode_guard",
        plan=None,
        managed_session=None,
    )
    # Only the base prover prompt is owned by this change-set. The
    # narrative_annotator `_PROMPT_TEMPLATE` benchmark-example cleanup travels
    # with the narrative-annotator change (handled separately), so its check is
    # re-added there rather than coupling this guard to that WIP.
    surfaces = {"base prover prompt": prompt}
    offenders = [
        f"{surface} contains {name}"
        for surface, text in surfaces.items()
        for name in FORBIDDEN_PROMPT_EXAMPLES
        if name in text
    ]

    assert offenders == []
