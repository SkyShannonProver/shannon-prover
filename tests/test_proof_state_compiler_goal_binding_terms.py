from core.easycrypt.proof_state_compiler.contracts import StateRef
from core.easycrypt.proof_state_compiler.frontend.native_state_lowering import (
    lower_native_goal,
)
from core.easycrypt.proof_state_compiler.middle_end.goal_binding_terms import (
    bounded_goal_binding_terms,
)
from tests.proof_state_compiler_test_support import (
    module_path,
    native_state,
    typed_node,
)


def _state_ref() -> StateRef:
    return StateRef(
        session_id="goal-binding-terms",
        state_version=1,
        goal_identity="goal-binding-identity",
        goal_identity_required=True,
        committed_prefix_identity="p" * 64,
    )


def _probability_goal():
    event = typed_node(
        "program_variable",
        "res{hr}",
        memory="&hr",
        identity="res",
    )
    probability = typed_node(
        "probability",
        "Pr[Game(A, Wrap(St)).main() @ &m : res]",
        type_text="real",
        children=(typed_node("true", "true"), event),
        child_roles=("arguments", "event"),
        memory="&m",
        procedure="Game(A, Wrap(St)).main",
        procedure_module=module_path(
            "Game(A, Wrap(St))",
            module_path("A"),
            module_path("Wrap(St)", module_path("St")),
        ),
    )
    return lower_native_goal(native_state(
        _state_ref(),
        judgment_kind="probability",
        formula=probability,
    ))


def test_goal_binding_terms_use_native_module_leaves_and_boundary_memory() -> None:
    pool = bounded_goal_binding_terms(
        _probability_goal(),
        max_module_terms=4,
        max_memory_terms=2,
    )

    assert pool is not None
    assert pool.module_terms == ("A", "St")
    assert pool.memory_terms == ("&m",)


def test_goal_binding_terms_abstain_instead_of_truncating_module_pool() -> None:
    assert bounded_goal_binding_terms(
        _probability_goal(),
        max_module_terms=1,
        max_memory_terms=2,
    ) is None
