"""Feature-neutral P3 dependency planning for native EasyCrypt semantics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    NativePlanningBudget,
    NativeSemanticExecutionUnit,
    NativeSemanticPlan,
    NativeSemanticPlanningDecision,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    ProofCoordinate,
    ProofIR,
)
from core.easycrypt.proof_state_compiler.contracts.native_semantics import (
    NATIVE_PRODUCTION_ABSTAINED,
    NATIVE_PRODUCTION_READY,
)
from core.easycrypt.proof_state_compiler.middle_end.coordinate import (
    analyze_coordinate,
)


class NativeSemanticRequestProducer(Protocol):
    """One active feature's complete, budget-aware request producer.

    Producers describe semantic dependencies only. They never invoke EasyCrypt
    and cannot place a verifier result directly into the IR. They must return a
    typed abstention rather than truncate an over-budget candidate population.
    """

    def __call__(
        self,
        proof_ir: ProofIR,
        coordinate: ProofCoordinate,
        invocation: CompilerInvocationContext,
        budget: NativePlanningBudget,
    ) -> NativeSemanticRequestProduction: ...


@dataclass(frozen=True)
class NativeSemanticProducerBinding:
    """Composition-root ownership for one feature-local native producer."""

    feature_id: str
    producer: NativeSemanticRequestProducer

    def __post_init__(self) -> None:
        if not self.feature_id or not callable(self.producer):
            raise ValueError("native semantic producer binding is invalid")


@dataclass(frozen=True)
class _PreparedProduction:
    feature_id: str
    production: NativeSemanticRequestProduction
    unresolved: tuple[NativeSemanticRequest, ...]


def plan_native_semantics(
    proof_ir: ProofIR,
    producers: tuple[NativeSemanticProducerBinding, ...],
    invocation: CompilerInvocationContext,
    budget: NativePlanningBudget | None = None,
) -> NativeSemanticPlan:
    """Collect a complete, bounded native plan for the exact current StateRef.

    Capacity is an ordinary compiler admission decision, not an exception. A
    feature whose complete unresolved request population does not fit is
    dropped as one typed abstention. If multiple individually valid features
    cannot fit together, all conflicting contributions abstain; registration
    order never selects a winner. Contract violations (stale state, duplicate
    identity, malformed production) still fail closed.
    """

    if invocation.state_ref != proof_ir.state_ref:
        raise ValueError("native semantic planning invocation is stale")
    budget = budget or NativePlanningBudget()
    coordinate = analyze_coordinate(proof_ir)
    observed = {
        item.request_id: item
        for item in proof_ir.native_semantic_observations
    }
    prepared: list[_PreparedProduction] = []
    seen_producers: set[str] = set()
    seen_requests: set[str] = set()
    for binding in producers:
        production = binding.producer(
            proof_ir, coordinate, invocation, budget
        )
        if not isinstance(production, NativeSemanticRequestProduction):
            raise TypeError(
                "native semantic producer returned an invalid production"
            )
        if production.producer_id in seen_producers:
            raise ValueError("native semantic producer identity is duplicated")
        seen_producers.add(production.producer_id)
        unresolved: list[NativeSemanticRequest] = []
        for produced_request in production.requests:
            if not isinstance(produced_request, NativeSemanticRequest):
                raise TypeError(
                    "native semantic producer returned an invalid request"
                )
            if (
                produced_request.feature_id
                and produced_request.feature_id != binding.feature_id
            ):
                raise ValueError(
                    "native semantic request crossed feature ownership"
                )
            if produced_request.evaluation_prefix:
                raise ValueError(
                    "feature producer cannot choose a native evaluation prefix"
                )
            handoff = (
                None
                if proof_ir.attempted_operation is None
                else proof_ir.attempted_operation.recovery_handoff
            )
            evaluation_prefix = (
                ()
                if handoff is None
                or binding.feature_id == handoff.source_feature_id
                else (handoff.accepted_prefix_tactic,)
            )
            request = replace(
                produced_request,
                feature_id=binding.feature_id,
                evaluation_prefix=evaluation_prefix,
            )
            if request.state_ref != proof_ir.state_ref:
                raise ValueError("native semantic producer crossed StateRef")
            if request.request_id in seen_requests:
                raise ValueError(
                    "native semantic producers emitted duplicate request IDs"
                )
            seen_requests.add(request.request_id)
            observation = observed.get(request.request_id)
            if observation is None:
                unresolved.append(request)
            elif observation.request_identity_sha256 != request.identity_sha256:
                raise ValueError(
                    "native semantic request identity collided with observation"
                )
            elif observation.producer_id != request.producer_id:
                raise ValueError(
                    "native semantic observation crossed producer ownership"
                )
        prepared.append(_PreparedProduction(
            feature_id=binding.feature_id,
            production=production,
            unresolved=tuple(unresolved),
        ))

    # Producer call order is not semantic. Canonicalize before allocation and
    # output so deleting or reordering another feature cannot select a winner.
    prepared.sort(key=lambda item: (
        item.feature_id, item.production.producer_id
    ))
    ready_by_feature: dict[str, list[_PreparedProduction]] = {}
    for item in prepared:
        if (
            item.production.disposition == NATIVE_PRODUCTION_READY
            and item.unresolved
        ):
            ready_by_feature.setdefault(item.feature_id, []).append(item)

    over_budget_features: set[str] = set()
    for feature_id, items in ready_by_feature.items():
        feature_requests = tuple(
            request for item in items for request in item.unresolved
        )
        feature_units = _execution_units(proof_ir, feature_requests)
        if (
            len(feature_requests) > budget.remaining_consumer_requests
            or len(feature_units) > budget.remaining_execution_units
        ):
            over_budget_features.add(feature_id)

    admitted = tuple(
        request
        for item in prepared
        if item.feature_id not in over_budget_features
        and item.production.disposition == NATIVE_PRODUCTION_READY
        for request in item.unresolved
    )
    admitted_units = _execution_units(proof_ir, admitted)
    shared_conflict_features: set[str] = set()
    if (
        len(admitted) > budget.remaining_consumer_requests
        or len(admitted_units) > budget.remaining_execution_units
    ):
        shared_conflict_features = {
            item.feature_id
            for item in prepared
            if item.feature_id not in over_budget_features
            and item.production.disposition == NATIVE_PRODUCTION_READY
            and item.unresolved
        }
        admitted = tuple(
            request
            for item in prepared
            if item.feature_id not in over_budget_features
            and item.feature_id not in shared_conflict_features
            and item.production.disposition == NATIVE_PRODUCTION_READY
            for request in item.unresolved
        )
        admitted_units = _execution_units(proof_ir, admitted)

    decisions = []
    for item in prepared:
        production = item.production
        disposition = production.disposition
        reason = production.reason
        if item.feature_id in over_budget_features and item.unresolved:
            disposition = NATIVE_PRODUCTION_ABSTAINED
            reason = "feature_complete_request_population_exceeds_native_budget"
        elif item.feature_id in shared_conflict_features and item.unresolved:
            disposition = NATIVE_PRODUCTION_ABSTAINED
            reason = "shared_native_budget_conflict"
        decisions.append(NativeSemanticPlanningDecision(
            feature_id=item.feature_id,
            producer_id=production.producer_id,
            disposition=disposition,
            reason=reason,
            considered_candidate_count=production.considered_candidate_count,
            proposed_request_ids=tuple(sorted(
                request.request_id for request in production.requests
            )),
            unresolved_request_count=len(item.unresolved),
            unresolved_execution_unit_count=len(_execution_units(
                proof_ir, item.unresolved
            )),
        ))
    return NativeSemanticPlan(
        state_ref=proof_ir.state_ref,
        requests=admitted,
        execution_units=admitted_units,
        budget=budget,
        decisions=tuple(decisions),
    )


def _execution_units(
    proof_ir: ProofIR,
    requests: tuple[NativeSemanticRequest, ...],
) -> tuple[NativeSemanticExecutionUnit, ...]:
    grouped: dict[str, list[NativeSemanticRequest]] = {}
    for request in requests:
        grouped.setdefault(request.semantic_unit_sha256, []).append(request)
    return tuple(
        NativeSemanticExecutionUnit(
            unit_id=unit_id,
            state_ref=proof_ir.state_ref,
            query=members[0].query,
            requests=tuple(members),
        )
        for unit_id, members in grouped.items()
    )
