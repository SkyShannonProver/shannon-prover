"""P2 assembly from shared parsers and registered resource discoverers."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts.environment import CompilationEnvironment
from core.easycrypt.proof_state_compiler.contracts.delivery import CompilerInvocationContext
from core.easycrypt.proof_state_compiler.contracts.projected_state import ProjectedProofState
from core.easycrypt.proof_state_compiler.contracts.proof_ir import GoalIR, ProofIR
from core.easycrypt.proof_state_compiler.contracts.native_semantics import (
    NativeSemanticPlanningReport,
)
from core.easycrypt.proof_state_compiler.derived_provenance import derived_provenance
from core.easycrypt.proof_state_compiler.frontend.fact_parser import (
    parse_source_declaration_facts,
)
from core.easycrypt.proof_state_compiler.frontend.native_state_lowering import (
    lower_native_current_facts,
    lower_native_goal,
    lower_native_program_statements,
)
from core.easycrypt.proof_state_compiler.frontend.resource_discovery import (
    ResourceDiscoverer,
    discover_resources,
)
from core.easycrypt.proof_state_compiler.frontend.attempted_operation import (
    parse_attempted_operation,
)
from core.easycrypt.proof_state_compiler.frontend.module_spelling_inventory import (
    bounded_module_spelling_inventory,
    needs_module_spelling_inventory,
)


def build_proof_ir(
    state: ProjectedProofState,
    environment: CompilationEnvironment,
    discoverers: tuple[ResourceDiscoverer, ...] = (),
    invocation: CompilerInvocationContext | None = None,
    planning_report: NativeSemanticPlanningReport | None = None,
    include_module_spelling_inventory: bool = False,
) -> ProofIR:
    if invocation is None:
        from core.easycrypt.proof_state_compiler.contracts.delivery import (
            compiler_invocation_context,
        )
        invocation = compiler_invocation_context(
            state.state_ref,
            source_event_id=state.provenance.source_event_id,
        )
    if invocation.state_ref != state.state_ref:
        raise ValueError("P2 invocation context is stale")
    event_trigger = invocation.event_trigger
    attempted_operation = parse_attempted_operation(
        invocation.failure_observation,
        environment.native_semantic_observations,
        trigger_id=event_trigger.trigger_id if event_trigger is not None else "",
    )
    native = state.native_state
    goal = (
        GoalIR(status="unknown", kind="unknown")
        if native is None
        else lower_native_goal(native)
    )
    statements = () if native is None else lower_native_program_statements(native)
    current_facts = () if native is None else lower_native_current_facts(native)
    module_inventory = (
        bounded_module_spelling_inventory(
            goal, environment, max_terms=96
        )
        if include_module_spelling_inventory
        and needs_module_spelling_inventory(attempted_operation)
        else None
    )
    base = ProofIR(
        state_ref=state.state_ref,
        provenance=derived_provenance("p2.proof_ir", state.state_ref, state.provenance),
        goal=goal,
        statements=statements,
        facts=current_facts + parse_source_declaration_facts(environment),
        module_spelling_inventory=module_inventory,
        attempted_operation=attempted_operation,
        native_semantic_observations=environment.native_semantic_observations,
        native_semantic_planning_report=planning_report,
    )
    resources = discover_resources(
        state, environment, base, discoverers, invocation
    )
    return ProofIR(
        state_ref=base.state_ref,
        provenance=base.provenance,
        goal=base.goal,
        statements=base.statements,
        facts=base.facts,
        resources=resources,
        module_spelling_inventory=base.module_spelling_inventory,
        attempted_operation=base.attempted_operation,
        native_semantic_observations=base.native_semantic_observations,
        native_semantic_planning_report=base.native_semantic_planning_report,
    )
