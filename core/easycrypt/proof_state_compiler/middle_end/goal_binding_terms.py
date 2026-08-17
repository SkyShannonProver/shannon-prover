"""Feature-neutral bounded terms exposed by the native current-goal AST.

This module performs no theorem/result matching.  It only collects exact
module leaves and memory names that EasyCrypt already placed in the current
typed goal.  Feature slices may enumerate a bounded product of these spellings;
native proof-term elaboration remains responsible for module types,
restrictions, argument matching, and result/goal convertibility.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import GoalIR, TypedTermIR
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonArray,
    FrozenJsonObject,
)


@dataclass(frozen=True)
class GoalBindingTermPool:
    module_terms: tuple[str, ...]
    memory_terms: tuple[str, ...]


def bounded_goal_binding_terms(
    goal: GoalIR,
    *,
    max_module_terms: int,
    max_memory_terms: int,
) -> GoalBindingTermPool | None:
    """Return a complete bounded pool, or abstain instead of truncating it."""

    if max_module_terms < 1 or max_memory_terms < 1:
        raise ValueError("goal binding term budgets must be positive")
    if goal.status != "known" or goal.formula_ir is None:
        return None
    modules: list[str] = []
    memories: list[str] = []
    if not _collect_terms(goal.formula_ir, modules=modules, memories=memories):
        return None
    module_terms = tuple(dict.fromkeys(modules))
    memory_terms = tuple(dict.fromkeys(memories))
    if (
        len(module_terms) > max_module_terms
        or len(memory_terms) > max_memory_terms
    ):
        return None
    return GoalBindingTermPool(
        module_terms=module_terms,
        memory_terms=memory_terms,
    )


def _collect_terms(
    term: TypedTermIR,
    *,
    modules: list[str],
    memories: list[str],
) -> bool:
    module_path = term.properties.get("procedure_module")
    if module_path is not None:
        if not isinstance(module_path, FrozenJsonObject):
            return False
        if not _collect_module_leaves(module_path, modules):
            return False
    memory = term.properties.get("memory") if term.kind == "probability" else None
    if memory is not None:
        if type(memory) is not str or not memory.startswith("&"):
            return False
        memories.append(memory)
    return all(
        _collect_terms(child, modules=modules, memories=memories)
        for child in term.children
    )


def _collect_module_leaves(
    module_path: FrozenJsonObject,
    target: list[str],
) -> bool:
    term = module_path.get("term")
    arguments = module_path.get("arguments")
    if type(term) is not str or not term or not isinstance(arguments, FrozenJsonArray):
        return False
    if not arguments:
        target.append(term)
        return True
    return all(
        isinstance(argument, FrozenJsonObject)
        and _collect_module_leaves(argument, target)
        for argument in arguments
    )
