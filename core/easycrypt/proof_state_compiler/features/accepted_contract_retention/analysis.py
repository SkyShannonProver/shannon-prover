"""P3 comparison against one exact accepted structural contract anchor."""

from __future__ import annotations

import hashlib
import json
import re

from core.easycrypt.proof_state_compiler.contracts import (
    AGENT_SELECTED_OPERATION,
    EXPLANATION_ONLY,
    StructuredDiagnostic,
    CompilerInvocationContext,
    EvidenceRef,
    ProofCoordinate,
    ProofIR,
)
from core.easycrypt.proof_state_compiler.features.accepted_contract_retention.contracts import (
    AcceptedContractRetention,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)


ACCEPTED_CONTRACT_RETENTION_PRODUCER_ID = "accepted_contract_retention.analysis"


def analyze_accepted_contract_retention(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    trigger = invocation.event_trigger
    if (
        trigger is None
        or trigger.trigger_kind != AGENT_SELECTED_OPERATION
        or trigger.commitment_anchor is None
        or trigger.commitment_anchor.anchor_kind != "accepted_proof_operation"
        or trigger.state_ref != proof_ir.state_ref
    ):
        return AnalysisContribution()
    subject = trigger.commitment_anchor.subject.to_dict()
    payload = subject.get("payload")
    tactic = payload.get("tactic") if isinstance(payload, dict) else None
    parsed = _accepted_while_contract(str(tactic or ""))
    active = coordinate.tactic_active_boundary
    if (
        parsed is None
        or coordinate.status != "known"
        or active is None
        or active.kind != "while"
    ):
        return AnalysisContribution()
    conjuncts = _top_level_conjuncts(parsed)
    if len(conjuncts) < 2:
        return AnalysisContribution()
    visible = _visible_formulas(proof_ir)
    missing = tuple(
        conjunct for conjunct in conjuncts
        if _normalize_formula(conjunct) not in visible
    )
    if not missing:
        return AnalysisContribution()
    anchor_evidence = _anchor_evidence(invocation)
    evidence = tuple(dict.fromkeys(
        (anchor_evidence,)
        + tuple(ref for fact in proof_ir.facts for ref in fact.evidence_refs)
        + proof_ir.goal.evidence_refs
        + active.evidence_refs
    ))
    boundary_identity = f"while:{active.position}:{active.text}"
    result = AcceptedContractRetention(
        anchor_id=trigger.commitment_anchor.anchor_id,
        anchor_source_event_id=trigger.commitment_anchor.source_event_id,
        anchor_prefix_identity=(
            trigger.commitment_anchor.committed_prefix_identity
        ),
        current_prefix_identity=proof_ir.state_ref.committed_prefix_identity,
        boundary_identity=boundary_identity,
        original_conjuncts=conjuncts,
        missing_conjuncts=missing,
        evidence_refs=evidence,
    )
    message = (
        f"Accepted contract {result.anchor_id} at {result.boundary_identity} "
        f"no longer exposes original conjunct(s): {'; '.join(missing)}."
    )
    return AnalysisContribution(diagnostics=(StructuredDiagnostic(
        producer_id=ACCEPTED_CONTRACT_RETENTION_PRODUCER_ID,
        code="accepted_contract_conjunct_missing",
        primary=message,
        notes=(),
        help="",
        applicability=EXPLANATION_ONLY,
        evidence_refs=result.evidence_refs,
        trigger_id=trigger.trigger_id,
    ),))


def _accepted_while_contract(tactic: str) -> str | None:
    value = tactic.strip()
    if not value.endswith("."):
        return None
    value = value[:-1].strip()
    if not value.startswith("while"):
        return None
    rest = value[len("while"):].strip()
    if not rest.startswith("(") or not rest.endswith(")"):
        return None
    depth = 0
    for index, char in enumerate(rest):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0 or (depth == 0 and index != len(rest) - 1):
                return None
    if depth != 0:
        return None
    contract = rest[1:-1].strip()
    return contract or None


def _top_level_conjuncts(value: str) -> tuple[str, ...]:
    parts: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(value) - 1:
        char = value[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif value[index:index + 2] == "/\\" and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 2
            index += 1
        index += 1
    parts.append(value[start:].strip())
    normalized = tuple(part for part in parts if part)
    return normalized if len(normalized) == len(set(normalized)) else ()


def _visible_formulas(proof_ir: ProofIR) -> frozenset[str]:
    values = [proof_ir.goal.formula]
    values.extend(fact.judgment.text for fact in proof_ir.facts)
    expanded = []
    for value in values:
        if not value:
            continue
        expanded.append(value)
        expanded.extend(_top_level_conjuncts(_strip_outer_parentheses(value)))
    return frozenset(_normalize_formula(value) for value in expanded if value)


def _strip_outer_parentheses(value: str) -> str:
    result = value.strip()
    while result.startswith("(") and result.endswith(")"):
        depth = 0
        encloses = True
        for index, char in enumerate(result):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(result) - 1:
                    encloses = False
                    break
        if not encloses or depth != 0:
            break
        result = result[1:-1].strip()
    return result


def _normalize_formula(value: str) -> str:
    return re.sub(r"\s+", "", _strip_outer_parentheses(value))


def _anchor_evidence(invocation: CompilerInvocationContext) -> EvidenceRef:
    evidence = invocation.turn_evidence
    assert evidence is not None
    encoded = json.dumps(
        evidence.identity_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return EvidenceRef(
        evidence_id=f"accepted-turn.{digest[:16]}",
        source_kind="event_bound_tactic_execution_result",
        source_ref=(
            f"{evidence.artifact_ref}#{evidence.source_event_id}"
        ),
        source_sha256=digest,
    )
