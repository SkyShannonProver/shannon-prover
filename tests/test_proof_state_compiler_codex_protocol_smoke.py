"""No-model contracts for the one-call Codex protocol diagnostic."""

from __future__ import annotations

from workflow.validation.proof_state_compiler_codex_protocol_smoke import (
    EFFORT,
    MODEL,
    MODEL_BACKEND,
    PROMPT,
)
from workflow.validation.proof_state_compiler_one_step_model import (
    CODEX_ONE_STEP_DISABLED_FEATURES,
)


def test_protocol_smoke_is_one_provider_question_not_an_efficacy_trial() -> None:
    assert MODEL_BACKEND == "openai"
    assert MODEL == "gpt-5.6-sol"
    assert EFFORT == "high"
    assert "no proof state" in PROMPT
    assert "Do not use any tool" in PROMPT
    assert "trivial." in PROMPT


def test_code_mode_is_disabled_while_its_internal_host_remains_inert() -> None:
    disabled = set(CODEX_ONE_STEP_DISABLED_FEATURES)

    assert "code_mode" in disabled
    assert "code_mode_host" not in disabled
    assert "shell_tool" in disabled
    assert "unified_exec" in disabled
