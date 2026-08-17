"""Generic lowering of structured P3 applications to exact tactics."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts.analyzed_state import (
    ApplicationCandidate,
)
from core.easycrypt.proof_state_compiler.contracts.candidate_surface import (
    ActionCandidate,
)
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.contracts.strategy import (
    StrategyContract,
)


def lower_application_action(
    application: ApplicationCandidate,
    *,
    feature_id: str,
    certification_policy: str,
    strategy_contract: StrategyContract,
) -> ActionCandidate:
    return ActionCandidate(
        candidate_id=application.candidate_id,
        feature_id=feature_id,
        intent="commit_tactic",
        payload=freeze_json_object({
            "tactic": render_application_tactic(application),
        }),
        unresolved_premises=application.unresolved_premises,
        certification_policy=certification_policy,
        strategy_contract=strategy_contract,
        evidence_refs=application.evidence_refs,
        trigger_id=application.trigger_id,
    )


def render_application_tactic(application: ApplicationCandidate) -> str:
    if application.operation == "apply":
        return f"apply ({application.application_term})."
    if application.operation == "exact":
        return f"exact ({application.application_term})."
    if application.operation == "call":
        return f"call ({application.application_term})."
    if application.operation == "conseq":
        return f"conseq ({application.application_term})."
    raise ValueError(
        f"unsupported application operation {application.operation!r}"
    )
