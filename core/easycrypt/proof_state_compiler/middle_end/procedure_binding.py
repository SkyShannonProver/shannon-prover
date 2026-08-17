"""Shared structural procedure and module-argument unification."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.syntax.module_terms import (
    ModuleTermParseError,
    parse_procedure_term,
    render_module_term,
    render_procedure_term,
    substitute_module_term,
    unify_module_term,
)


@dataclass(frozen=True)
class ProcedureBinding:
    target: str
    resolved_modules: tuple[tuple[str, str], ...]
    instantiated_premises: tuple[str, ...]


def bind_procedure_resource(
    *,
    conclusion_procedure: str,
    target_procedure: str,
    module_parameters: tuple[str, ...],
    premise_procedures: tuple[str, ...],
) -> ProcedureBinding | None:
    """Unify a resource conclusion with one active qualified procedure."""

    try:
        pattern = parse_procedure_term(conclusion_procedure)
        target = parse_procedure_term(target_procedure)
    except ModuleTermParseError:
        return None
    if pattern.procedure != target.procedure:
        return None
    substitutions = {}
    variables = frozenset(module_parameters)
    if not unify_module_term(pattern.module, target.module, variables, substitutions):
        return None
    if any(parameter not in substitutions for parameter in module_parameters):
        return None
    instantiated = []
    try:
        for premise in premise_procedures:
            procedure = parse_procedure_term(premise)
            substituted = type(procedure)(
                module=substitute_module_term(procedure.module, substitutions),
                procedure=procedure.procedure,
            )
            instantiated.append(render_procedure_term(substituted))
    except ModuleTermParseError:
        return None
    return ProcedureBinding(
        target=target_procedure,
        resolved_modules=tuple(
            (parameter, render_module_term(substitutions[parameter]))
            for parameter in module_parameters
        ),
        instantiated_premises=tuple(instantiated),
    )
