"""P2 lowering from the validated EasyCrypt typed-state source projection.

This is the only module allowed to know the native projection JSON schema.
Goal text remains available for display and identity, but it is never parsed to
recover proof kind, formulas, locals, or program structure.
"""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonArray,
    FrozenJsonObject,
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.contracts.native_state import (
    NativeProofStateSnapshot,
)
from core.easycrypt.proof_state_compiler.contracts.proof_ir import (
    FormulaRelation,
    GoalIR,
    ProgramStatement,
    ProofFact,
    ProofJudgment,
    TypedTermIR,
)
from core.easycrypt.proof_state_compiler.syntax.formulas import normalize_formula


_GOAL_KINDS = {
    "pure": "formula",
    "hoare_function": "hoare",
    "hoare_statement": "hoare",
    "bounded_hoare_function": "phoare",
    "bounded_hoare_statement": "phoare",
    "expectation_hoare_function": "ehoare",
    "expectation_hoare_statement": "ehoare",
    "equivalence_function": "equiv",
    "equivalence_statement": "equiv",
    "eager_equivalence": "equiv",
    "probability": "probability",
}
_STATEMENT_KINDS = {
    "assign": "assign",
    "sample": "sample",
    "call": "call",
    "if": "if",
    "while": "while",
    "match": "other",
    "raise": "other",
    "abstract": "other",
}


def lower_native_goal(native: NativeProofStateSnapshot) -> GoalIR:
    evidence = _evidence(native, "focused_goal.formula")
    if not native.complete:
        return GoalIR(status="unknown", kind="unknown")
    focused = _object(native.projection["focused_goal"], "focused_goal")
    formula = _term(_object(focused["formula"], "focused_goal.formula"))
    judgment_kind = _string(focused["judgment_kind"], "judgment_kind")
    kind = _GOAL_KINDS.get(judgment_kind)
    if kind == "formula" and _contains_kind(formula, "probability"):
        kind = "probability"
    if kind is None:
        return GoalIR(status="unknown", kind="unknown")
    roles = _role_map(formula)
    comparison = str(formula.properties.get("comparison", ""))
    bound = roles.get("bound")
    postcondition = roles.get("postcondition")
    return GoalIR(
        status="known",
        kind=kind,
        formula=formula.text,
        bound_relation=comparison,
        bound_value=bound.text if bound is not None else "",
        precondition=(
            roles["precondition"].text if "precondition" in roles else ""
        ),
        postcondition=(
            _normal_postcondition(postcondition).text
            if postcondition is not None else ""
        ),
        relation=_relation(formula),
        formula_ir=formula,
        evidence_refs=(evidence,),
    )


def lower_native_program_statements(
    native: NativeProofStateSnapshot,
) -> tuple[ProgramStatement, ...]:
    if not native.complete:
        return ()
    focused = _object(native.projection["focused_goal"], "focused_goal")
    programs = _array(focused["programs"], "focused_goal.programs")
    statements: list[ProgramStatement] = []
    for program_index, value in enumerate(programs):
        program = _object(value, f"programs[{program_index}]")
        side = _string(program["side"], "program.side")
        statement = _object(program["statement"], "program.statement")
        instructions = _array(statement["instructions"], "statement.instructions")
        for instruction_index, item in enumerate(instructions):
            instruction = _object(item, "instruction")
            position = instruction.get("top_level_position")
            if type(position) is not int or position < 1:
                raise ValueError("native top-level instruction lacks position")
            native_kind = _string(instruction["kind"], "instruction.kind")
            procedure = (
                _string(instruction["procedure"], "instruction.procedure")
                if native_kind == "call"
                else ""
            )
            path = tuple(
                _string(part, "instruction.structural_path")
                for part in _array(
                    instruction["structural_path"],
                    "instruction.structural_path",
                )
            )
            statements.append(ProgramStatement(
                side=side,
                position=position,
                kind=_STATEMENT_KINDS[native_kind],
                text=_string(instruction["text"], "instruction.text"),
                procedure=procedure,
                structural_path=path,
                evidence_refs=(
                    _evidence(
                        native,
                        f"focused_goal.programs/{program_index}/"
                        f"statement/instructions/{instruction_index}",
                    ),
                ),
            ))
    return tuple(sorted(
        statements,
        key=lambda item: (
            {"single": 0, "left": 1, "right": 2}[item.side],
            item.position,
        ),
    ))


def lower_native_current_facts(
    native: NativeProofStateSnapshot,
) -> tuple[ProofFact, ...]:
    if not native.complete:
        return ()
    declarations = _array(
        native.projection["local_declarations"],
        "local_declarations",
    )
    facts = []
    for index, value in enumerate(declarations):
        declaration = _object(value, f"local_declarations[{index}]")
        if declaration["kind"] != "hypothesis":
            continue
        name = _string(declaration["name"], "local hypothesis name")
        formula = _term(_object(declaration["formula"], "local formula"))
        evidence = _evidence(native, f"local_declarations/{index}/formula")
        identity = hashlib.sha256(
            f"{name}\0{formula.text}\0{evidence.source_sha256}".encode()
        ).hexdigest()[:20]
        facts.append(ProofFact(
            fact_id=f"proof-fact:{identity}",
            name=name,
            judgment=_judgment(formula),
            origin="current_context",
            evidence_refs=(evidence,),
        ))
    return tuple(facts)


def _term(node: FrozenJsonObject) -> TypedTermIR:
    if node.get("complete") is not True or node.get("kind") == "truncated":
        raise ValueError("incomplete native term reached P2 lowering")
    children = tuple(
        _term(_object(item, "typed term child"))
        for item in _array(node["children"], "typed term children")
    )
    roles_value = node.get("child_roles")
    roles = (
        tuple(
            _string(item, "typed term child role")
            for item in _array(roles_value, "typed term child roles")
        )
        if roles_value is not None
        else ()
    )
    raw = node.to_dict()
    for field in ("kind", "complete", "text", "type", "children", "child_roles"):
        raw.pop(field, None)
    return TypedTermIR(
        kind=_string(node["kind"], "typed term kind"),
        text=_string(node["text"], "typed term text"),
        type_text=_string(node["type"], "typed term type"),
        children=children,
        child_roles=roles,
        properties=freeze_json_object(raw),
    )


def _judgment(formula: TypedTermIR) -> ProofJudgment:
    kind = _GOAL_KINDS.get(formula.kind, "formula")
    procedure = str(formula.properties.get("procedure", ""))
    if formula.properties.get("lossless") is True:
        kind = "lossless"
    return ProofJudgment(
        kind=kind,
        text=formula.text,
        subject=procedure,
        procedure=procedure if kind == "lossless" else "",
        relation=_relation(formula),
        formula_ir=formula,
    )


def _relation(formula: TypedTermIR) -> FormulaRelation | None:
    operator = ""
    if formula.kind == "equality":
        operator = "="
    elif formula.kind == "iff":
        operator = "<=>"
    elif formula.kind == "operator_application":
        operator = str(formula.properties.get("relation_operator", ""))
    if not operator or len(formula.children) != 2:
        return None
    return FormulaRelation(
        operator=operator,
        left=formula.children[0].text,
        right=formula.children[1].text,
    )


def _role_map(formula: TypedTermIR) -> dict[str, TypedTermIR]:
    return dict(zip(formula.child_roles, formula.children))


def _normal_postcondition(postcondition: TypedTermIR) -> TypedTermIR:
    """Select the ordinary result while retaining exception branches in IR."""

    if postcondition.kind != "exceptional_postcondition":
        return postcondition
    roles = _role_map(postcondition)
    normal = roles.get("normal_postcondition")
    if normal is None:
        raise ValueError("native exceptional postcondition lacks normal branch")
    return normal


def _contains_kind(formula: TypedTermIR, kind: str) -> bool:
    return formula.kind == kind or any(
        _contains_kind(child, kind) for child in formula.children
    )


def _evidence(native: NativeProofStateSnapshot, anchor: str) -> EvidenceRef:
    identity = hashlib.sha256(
        f"{native.provenance.source_sha256}\0{anchor}".encode()
    ).hexdigest()[:16]
    return EvidenceRef(
        evidence_id=f"p2.native.{identity}",
        source_kind="native_typed_state",
        source_ref=f"{native.provenance.artifact_ref}#projection/{anchor}",
        source_sha256=native.provenance.source_sha256,
    )


def _object(value: object, label: str) -> FrozenJsonObject:
    if not isinstance(value, FrozenJsonObject):
        raise ValueError(f"native {label} is not an object")
    return value


def _array(value: object, label: str) -> FrozenJsonArray:
    if not isinstance(value, FrozenJsonArray):
        raise ValueError(f"native {label} is not an array")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"native {label} is not a non-empty string")
    return value
